/**
 * geofence.js — Swahilipot Hub Portal
 *
 * Runs on every authenticated page via base.html.
 *
 * WHAT IT DOES:
 *  1. Checks location status every 5 seconds (no page refresh needed).
 *  2. When location turns OFF:
 *       - Plays a distinct "location off" descending sound.
 *       - Reports to /attendance/location-status/ → creates LocationLog.
 *  3. When location turns back ON:
 *       - Plays a distinct "location on" ascending sound.
 *       - Reports to server → closes the open LocationLog (sets turned_on_at).
 *  4. When attendance-checked-in: also pings the geofence endpoint every 60 s.
 *  5. Shows on-screen status on the attendance home page.
 */

(function () {
  "use strict";

  const LOCATION_CHECK_MS = 5_000;   // check location every 5 seconds
  const PING_INTERVAL_MS  = 15_000;  // geofence server ping every 15 s (was 60 s — faster detection while walking)

  const checkedIn         = window.portalCheckedIn === true;
  const pingUrl           = window.geofencePingUrl  || "";
  const locationStatusUrl = window.locationStatusUrl || "";
  const csrf              = window.csrfToken || "";

  if (!navigator.geolocation) return;

  // ── DOM refs — only present on attendance home page ──────────────────────
  const statusBox = document.getElementById("geofenceStatus");
  const gfText    = document.getElementById("gfText");
  const gfSpinner = document.getElementById("gfSpinner");

  // ── State ─────────────────────────────────────────────────────────────────
  let _isOff          = false;  // true = location is currently off
  let _reportedOff    = false;  // sent "off" to server for this cycle
  let _reportedOn     = false;  // sent "on" to server for this cycle (resets when off again)

  // ── UI helpers (silently no-op when not on attendance page) ──────────────

  function setWaiting() {
    if (!statusBox) return;
    statusBox.className = "alert alert-info py-2 px-3 mb-3 d-flex align-items-center gap-2";
    if (gfSpinner) gfSpinner.className = "spinner-grow spinner-grow-sm text-info";
    if (gfText) gfText.innerHTML = "<strong>Location monitoring active</strong> — acquiring GPS…";
  }

  function setInsideSite(distance, radius) {
    if (!statusBox) return;
    statusBox.className = "alert alert-success py-2 px-3 mb-3 d-flex align-items-center gap-2";
    if (gfSpinner) gfSpinner.className = "bi bi-geo-alt-fill text-success fs-5";
    if (gfText) gfText.innerHTML =
      `<strong>Inside site perimeter</strong> — ${distance} m from centre (radius: ${radius} m).`;
  }

  function setOutsideSite(distance, radius) {
    if (!statusBox) return;
    statusBox.className = "alert alert-danger py-2 px-3 mb-3 d-flex align-items-center gap-2 border border-danger border-2";
    if (gfSpinner) gfSpinner.className = "bi bi-exclamation-triangle-fill text-danger fs-5";
    if (gfText) gfText.innerHTML =
      `<strong>⚠ Outside perimeter!</strong> You are <strong>${distance} m</strong> away ` +
      `(allowed: ${radius} m). A violation has been recorded.`;
    showOutsideBanner(distance, radius);
    if (window.portalSound) window.portalSound.play("critical");
  }

  function setLocationOff() {
    if (!statusBox) return;
    statusBox.className = "alert alert-danger py-2 px-3 mb-3 d-flex align-items-center gap-2";
    if (gfSpinner) gfSpinner.className = "bi bi-geo-alt-slash text-danger fs-5";
    if (gfText) gfText.innerHTML =
      "<strong>📵 Location Turned Off</strong> — GPS monitoring paused. " +
      "Re-enable location to continue attendance tracking.";
  }

  function showOutsideBanner(distance, radius) {
    if (document.getElementById("gfBanner")) return;
    const b = document.createElement("div");
    b.id = "gfBanner";
    b.style.cssText =
      "position:fixed;top:0;left:0;right:0;z-index:9999;background:#dc3545;color:#fff;" +
      "padding:14px 20px;display:flex;align-items:center;justify-content:space-between;" +
      "font-weight:600;box-shadow:0 2px 8px rgba(0,0,0,.4);";
    b.innerHTML =
      `<span>⚠ You have left the site perimeter (${distance} m away, max ${radius} m). ` +
      `Management has been alerted.</span>` +
      `<button onclick="document.getElementById('gfBanner').remove()" ` +
      `style="background:none;border:2px solid #fff;color:#fff;border-radius:4px;` +
      `padding:4px 12px;cursor:pointer;font-weight:700;">Dismiss</button>`;
    document.body.prepend(b);
  }

  // ── Server reporting ──────────────────────────────────────────────────────

  function reportStatus(status) {
    if (!locationStatusUrl || !csrf) return;
    fetch(locationStatusUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify({ status }),
    })
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (!data) return;
      // Server triggered an auto-checkout (location off + grace period over)
      if (data.auto_checkout) {
        // Show a brief message then reload so the attendance page reflects the checkout
        const msg = document.createElement("div");
        msg.style.cssText =
          "position:fixed;top:0;left:0;right:0;z-index:9999;background:#dc3545;color:#fff;" +
          "padding:14px 20px;text-align:center;font-weight:600;font-size:.95rem;" +
          "box-shadow:0 2px 8px rgba(0,0,0,.4);";
        msg.textContent =
          "⚠ You have been automatically checked out because your location was turned off after closing time.";
        document.body.prepend(msg);
        setTimeout(function() { window.location.reload(); }, 3500);
      }
    })
    .catch(function() {});
  }

  // ── On location turning OFF ───────────────────────────────────────────────
  function handleLocationOff(reason) {
    if (_reportedOff) return; // already reported this off-cycle
    _reportedOff = true;
    _reportedOn  = false;
    _isOff       = true;
    setLocationOff();
    if (window.portalSound) window.portalSound.play("location_off");
    reportStatus("off");
    console.info("[Geofence] Location OFF —", reason);
  }

  // ── On location turning ON ────────────────────────────────────────────────
  function handleLocationOn() {
    if (!_reportedOff) return; // never went off — nothing to restore
    if (_reportedOn)   return; // already sent "on" for this cycle
    _reportedOn  = true;
    _reportedOff = false;
    _isOff       = false;
    if (window.portalSound) window.portalSound.play("location_on");
    reportStatus("on");
    console.info("[Geofence] Location ON — restored.");
    if (checkedIn && pingUrl) doGeofencePing(); // immediate geofence check
  }

  // ── Permissions API — catches browser-level permission toggle ────────────
  if (navigator.permissions && navigator.permissions.query) {
    navigator.permissions.query({ name: "geolocation" }).then(function (perm) {
      perm.onchange = function () {
        if (perm.state === "denied" || perm.state === "prompt") {
          handleLocationOff("permission-revoked");
        } else if (perm.state === "granted") {
          handleLocationOn();
        }
      };
    }).catch(() => {});
  }

  // ── Geofence server ping ──────────────────────────────────────────────────
  async function pingGeofenceServer(lat, lng) {
    if (!pingUrl || !csrf) return;
    try {
      const r = await fetch(pingUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ latitude: lat, longitude: lng }),
      });
      if (!r.ok) return;
      const data = await r.json();
      if (!data.checked_in) return;
      const radius = data.radius || (window.portalSite && window.portalSite.radius) || 100;
      if (data.inside) {
        setInsideSite(data.distance, radius);
      } else {
        setOutsideSite(data.distance, radius);
      }
    } catch (e) {
      console.warn("[Geofence] ping failed:", e);
    }
  }

  function doGeofencePing() {
    setWaiting();
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        handleLocationOn();
        pingGeofenceServer(pos.coords.latitude, pos.coords.longitude);
      },
      function (err) {
        if (err.code === err.PERMISSION_DENIED)         handleLocationOff("permission-denied");
        else if (err.code === err.POSITION_UNAVAILABLE) handleLocationOff("position-unavailable");
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }  // maximumAge:0 → always fresh GPS
    );
  }

  // ── 5-second location check — runs on ALL pages ───────────────────────────
  function checkLocationStatus() {
    navigator.geolocation.getCurrentPosition(
      function () { handleLocationOn(); },
      function (err) {
        if (err.code === err.PERMISSION_DENIED || err.code === err.POSITION_UNAVAILABLE) {
          handleLocationOff(
            err.code === err.PERMISSION_DENIED ? "permission-denied" : "gps-off"
          );
        }
        // TIMEOUT (code 3) → GPS just slow, not off — ignore
      },
      { enableHighAccuracy: false, timeout: 4000, maximumAge: 0 }  // maximumAge:0 → always fresh
    );
  }

  // ── Start ─────────────────────────────────────────────────────────────────

  // 5-second location check on every page
  setTimeout(checkLocationStatus, 2000); // first check after 2 s
  setInterval(checkLocationStatus, LOCATION_CHECK_MS);

  // 60-second geofence ping only when attendance-checked-in
  if (checkedIn && pingUrl) {
    setTimeout(doGeofencePing, 5000);
    setInterval(doGeofencePing, PING_INTERVAL_MS);
  }

})();
