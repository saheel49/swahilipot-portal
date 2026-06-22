/**
 * notification_sounds.js — Swahilipot Hub Portal
 *
 * Web Audio API — no external files needed.
 *
 * Priority levels:
 *   low        → soft single ping
 *   medium     → double chime
 *   high       → triple alert tone
 *   critical   → rapid pulsing alarm
 *
 * Location-specific sounds:
 *   location_off  → descending warning tone (location disabled)
 *   location_on   → ascending confirmation tone (location restored)
 */

(function () {
  "use strict";

  let ctx = null;

  function getCtx() {
    if (!ctx) {
      try {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
      } catch (e) { return null; }
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  function tone(frequency, duration, volume, startAt, type) {
    const ac = getCtx();
    if (!ac) return;
    type = type || "sine";
    const osc  = ac.createOscillator();
    const gain = ac.createGain();
    const now  = ac.currentTime + startAt;
    osc.type = type;
    osc.frequency.setValueAtTime(frequency, now);
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(volume, now + 0.02);
    gain.gain.setValueAtTime(volume, now + duration - 0.04);
    gain.gain.linearRampToValueAtTime(0, now + duration);
    osc.connect(gain);
    gain.connect(ac.destination);
    osc.start(now);
    osc.stop(now + duration);
  }

  // ── Priority sounds ──────────────────────────────────────────────────────

  function playLow() {
    tone(820, 0.18, 0.18, 0, "sine");
  }

  function playMedium() {
    tone(660, 0.22, 0.32, 0.00, "sine");
    tone(880, 0.22, 0.32, 0.25, "sine");
  }

  function playHigh() {
    tone(440, 0.20, 0.45, 0.00, "triangle");
    tone(660, 0.20, 0.45, 0.22, "triangle");
    tone(880, 0.20, 0.45, 0.44, "triangle");
  }

  function playCritical() {
    for (let i = 0; i < 4; i++) {
      tone(1000, 0.12, 0.7, i * 0.18, "square");
      tone(750,  0.08, 0.5, i * 0.18 + 0.13, "square");
    }
  }

  // ── Location-specific sounds ─────────────────────────────────────────────

  /**
   * LOCATION OFF — descending two-tone warning (900 → 500 Hz)
   * Clearly signals something has been disabled.
   */
  function playLocationOff() {
    tone(900, 0.25, 0.55, 0.00, "triangle");
    tone(500, 0.35, 0.55, 0.28, "triangle");
  }

  /**
   * LOCATION ON — ascending two-tone confirmation (500 → 900 Hz)
   * Mirror of location-off: signals restoration.
   */
  function playLocationOn() {
    tone(500, 0.20, 0.40, 0.00, "sine");
    tone(900, 0.30, 0.45, 0.23, "sine");
  }

  // ── Public API ───────────────────────────────────────────────────────────

  window.portalSound = {
    play: function (priority) {
      const ac = getCtx();
      if (!ac) return;
      switch ((priority || "low").toLowerCase()) {
        case "critical":      playCritical();    break;
        case "high":          playHigh();        break;
        case "medium":        playMedium();      break;
        case "location_off":  playLocationOff(); break;
        case "location_on":   playLocationOn();  break;
        default:              playLow();         break;
      }
    },
    unlock: function () { getCtx(); },
  };

  // Unlock audio context on first user gesture
  ["click", "keydown", "touchstart"].forEach(function (evType) {
    document.addEventListener(evType, function _unlock() {
      window.portalSound.unlock();
      document.removeEventListener(evType, _unlock);
    }, { once: true, passive: true });
  });

})();
