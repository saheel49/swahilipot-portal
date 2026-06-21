/**
 * Swahilipot Hub Portal — Google Form → Portal Webhook  (OPTIONAL)
 * ================================================================
 *
 * THE PORTAL WORKS WITHOUT THIS SCRIPT.
 * ─────────────────────────────────────
 * When someone scans the QR code the portal IMMEDIATELY increments the
 * live count and saves an anonymous registration record.  The QR counter
 * is correct whether or not this script is installed.
 *
 * This script only adds name / email / phone to reports.
 * Without it, reports show "(QR Scan)" for anonymous scans.
 * With it, reports show the real name, email, and phone number.
 *
 * HOW IT WORKS:
 * ─────────────
 *   1. Person scans QR → portal counts it immediately (anonymous).
 *   2. Person fills & submits the Google Form.
 *   3. This script fires and posts their details to the portal.
 *   4. Portal enriches the existing placeholder — no double count.
 *   5. Reports now show full name/email/phone for that registration.
 *
 * SETUP (one-time, only needed if you want names in reports):
 * ────────────────────────────────────────────────────────────
 *   1. Open the Google Sheet linked to your form
 *   2. Extensions → Apps Script → paste this file → Save (💾)
 *   3. Triggers (clock icon) → Add Trigger:
 *        Function: onFormSubmit
 *        Event source: From spreadsheet
 *        Event type: On form submit
 *   4. Authorise when prompted
 *   5. Set PORTAL_BASE_URL below to wherever your portal is accessible
 *      (Cloudflare Tunnel, ngrok, or production domain — see SETUP_GOOGLE_FORM.md)
 *
 * REQUIRED GOOGLE FORM FIELDS (exact question titles):
 *   • "Event ID"       — Short answer, Required (pre-filled by QR with event PK)
 *   • "Event Name"     — Short answer, Optional (pre-filled by QR with event title)
 *   • "Full Name"      — Short answer
 *   • "Email Address"  — Short answer
 *   • "Phone Number"   — Short answer
 *
 * CURRENT .env FIELD MAPPING (from your configured Google Form):
 *   Event ID field:    entry.87039877   → set as GOOGLE_FORM_EVENT_ID_FIELD
 *   Event Name field:  entry.1265070359 → set as GOOGLE_FORM_EVENT_NAME_FIELD
 */

// ── CONFIGURATION ──────────────────────────────────────────────────────────
// Change this to your portal's public URL.
// Options:
//   • Cloudflare Tunnel (FREE, permanent): https://your-name.trycloudflare.com
//   • ngrok (free tier, changes each restart): https://abc123.ngrok-free.app
//   • Production server: https://portal.swahilipothub.co.ke
// Leave empty to disable the webhook entirely (live count still works without it).
var PORTAL_BASE_URL = "http://127.0.0.1:8000";
// ───────────────────────────────────────────────────────────────────────────


function onFormSubmit(e) {
  if (!PORTAL_BASE_URL) return; // webhook disabled

  var values = e.namedValues;

  // Read the Event ID pre-filled by the portal QR code
  var eventId = (values["Event ID"] || [""])[0].trim();
  if (!eventId) {
    Logger.log("⚠ No Event ID in submission — skipping.");
    return;
  }

  // Pick first non-empty value from a list of possible field names
  function pick(keys) {
    for (var i = 0; i < keys.length; i++) {
      var v = values[keys[i]];
      if (v && v[0] && v[0].trim()) return v[0].trim();
    }
    return "";
  }

  var payload = {
    event_id:  eventId,
    name:      pick(["Full Name",     "Name",        "full_name"]),
    email:     pick(["Email Address", "Email",       "email"]),
    phone:     pick(["Phone Number",  "Phone",       "phone", "Mobile"]),
    timestamp: new Date().toISOString(),
  };

  // Use the byid endpoint — sends event_id in body, works for all events
  var url = PORTAL_BASE_URL + "/events/form-response/";

  try {
    var resp = UrlFetchApp.fetch(url, {
      method:             "post",
      contentType:        "application/json",
      payload:            JSON.stringify(payload),
      muteHttpExceptions: true,
      followRedirects:    true,
    });

    var code = resp.getResponseCode();
    var body = resp.getContentText();

    Logger.log("Event: " + eventId + " | HTTP: " + code);

    if (code === 200) {
      var data = JSON.parse(body);
      Logger.log(data.enriched
        ? "✅ Enriched existing QR scan record — name/email/phone saved."
        : "✅ New registration record created (direct form fill, no prior QR scan).");
      Logger.log("Count: " + data.form_response_count + "/" + data.capacity);
    } else if (code === 0) {
      Logger.log("⚠ Could not reach portal — is it running and is PORTAL_BASE_URL correct?");
      Logger.log("ℹ QR scan count is still correct. Only name/email/phone in reports will be missing.");
    } else {
      Logger.log("⚠ HTTP " + code + " — portal may be unreachable or URL is wrong.");
      Logger.log("Response: " + body);
      Logger.log("ℹ Live count still works. Only name/email/phone in reports will be missing.");
    }

  } catch (err) {
    Logger.log("❌ Request failed: " + err.toString());
    Logger.log("ℹ Live count still works. Only name/email/phone in reports will be missing.");
  }
}
