/**
 * Swahilipot Hub Portal — Google Form → Portal Webhook
 * ======================================================
 * Paste this entire file into your Google Sheet's Apps Script editor
 * (Extensions > Apps Script), then set up an installable trigger.
 *
 * HOW TO SET UP (one-time):
 * --------------------------
 * 1. Open the Google Sheet linked to your form
 *    (https://docs.google.com/forms/d/1S9tDrq7LLvewqzNiuSOLWbfzDx_rSPDFdqAS_7Bnw0I/edit
 *     → Responses tab → Link to Sheets icon)
 * 2. In the Sheet: Extensions → Apps Script
 * 3. Delete any existing code, paste this entire file, and click Save (💾)
 * 4. Set up the trigger:
 *    - Click the clock icon (Triggers) in the left sidebar
 *    - Click "+ Add Trigger" (bottom right)
 *    - Choose function: onFormSubmit
 *    - Event source: From spreadsheet
 *    - Event type: On form submit
 *    - Click Save
 * 5. Authorise when prompted (Google will ask for permission once)
 * 6. Done — every new form submission will now ping the portal automatically
 *
 * REQUIRED: Add an "Event ID" field to your Google Form
 * -------------------------------------------------------
 * Your form must have a question named exactly:  Event ID
 * Set it to "Short answer" and make it Required.
 * The portal pre-fills this field automatically when opening the form.
 *
 * CONFIGURATION
 * -------------
 * Change PORTAL_BASE_URL to your server's address.
 * WEBHOOK_SECRET must match settings.EVENTS_WEBHOOK_SECRET in your .env
 */

// ── CONFIGURATION ─────────────────────────────────────────────────────────────
var PORTAL_BASE_URL  = "http://127.0.0.1:8000";   // ← change to your live domain
var WEBHOOK_SECRET   = "";                          // ← set in .env as EVENTS_WEBHOOK_SECRET
var EVENT_ID_FIELD   = "Event ID";                  // ← exact question title in your form
// ─────────────────────────────────────────────────────────────────────────────


/**
 * Triggered automatically on every Google Form submission.
 * Reads the Event ID from the response and pings the portal webhook.
 */
function onFormSubmit(e) {
  try {
    var namedValues = e.namedValues;

    // Read the Event ID from the form response
    var eventIdValues = namedValues[EVENT_ID_FIELD];
    if (!eventIdValues || eventIdValues.length === 0 || !eventIdValues[0]) {
      Logger.log("onFormSubmit: '" + EVENT_ID_FIELD + "' field not found or empty. Skipping.");
      return;
    }

    var eventId = String(eventIdValues[0]).trim();
    if (!eventId || isNaN(parseInt(eventId))) {
      Logger.log("onFormSubmit: Invalid event ID value: " + eventId);
      return;
    }

    // Build the webhook URL for this specific event
    var url = PORTAL_BASE_URL + "/events/" + eventId + "/form-response/";

    var payload = JSON.stringify({
      event_id:  eventId,
      timestamp: new Date().toISOString(),
      // Include all form responses for future use
      responses: namedValues
    });

    var options = {
      method:          "post",
      contentType:     "application/json",
      payload:         payload,
      muteHttpExceptions: true,
      headers:         {}
    };

    // Add secret header if configured
    if (WEBHOOK_SECRET) {
      options.headers["X-Webhook-Secret"] = WEBHOOK_SECRET;
    }

    var response = UrlFetchApp.fetch(url, options);
    var code = response.getResponseCode();
    var body = response.getContentText();

    if (code === 200) {
      Logger.log("Portal webhook OK for event " + eventId + ": " + body);
    } else {
      Logger.log("Portal webhook ERROR " + code + " for event " + eventId + ": " + body);
    }

  } catch (err) {
    Logger.log("onFormSubmit exception: " + err.toString());
  }
}


/**
 * Test function — run this manually from the Apps Script editor
 * to verify the connection before setting up the trigger.
 *
 * Steps:
 *   1. Change TEST_EVENT_ID to an existing event's portal ID (e.g. 1)
 *   2. Click Run → testWebhook
 *   3. Check View → Logs for the result
 */
function testWebhook() {
  var TEST_EVENT_ID = "1";  // ← change to a real event ID

  var url = PORTAL_BASE_URL + "/events/" + TEST_EVENT_ID + "/form-response/";

  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({ event_id: TEST_EVENT_ID, timestamp: new Date().toISOString(), test: true }),
    muteHttpExceptions: true,
    headers: {}
  };

  if (WEBHOOK_SECRET) {
    options.headers["X-Webhook-Secret"] = WEBHOOK_SECRET;
  }

  try {
    var resp = UrlFetchApp.fetch(url, options);
    Logger.log("Status: " + resp.getResponseCode());
    Logger.log("Body:   " + resp.getContentText());
  } catch (err) {
    Logger.log("Error: " + err.toString());
  }
}
