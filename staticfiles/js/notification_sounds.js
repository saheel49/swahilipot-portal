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

  // ── Task notification sounds ─────────────────────────────────────────────

  /**
   * TASK LOW — soft single ding (clean sine, quiet)
   * "Something new, no rush."
   */
  function playTaskLow() {
    tone(740, 0.20, 0.20, 0.00, "sine");
  }

  /**
   * TASK MEDIUM — two-note rising task chime
   * "Pay attention — you have a new task."
   */
  function playTaskMedium() {
    tone(523, 0.18, 0.30, 0.00, "sine");  // C5
    tone(784, 0.22, 0.35, 0.20, "sine");  // G5
  }

  /**
   * TASK HIGH — three-note ascending alert
   * "Important task assigned."
   */
  function playTaskHigh() {
    tone(523, 0.16, 0.40, 0.00, "triangle");  // C5
    tone(659, 0.16, 0.40, 0.18, "triangle");  // E5
    tone(784, 0.20, 0.45, 0.36, "triangle");  // G5
  }

  /**
   * TASK CRITICAL — urgent four-note staccato
   * "Drop everything — critical task."
   */
  function playTaskCritical() {
    tone(880, 0.10, 0.60, 0.00, "square");
    tone(988, 0.10, 0.60, 0.14, "square");
    tone(880, 0.10, 0.60, 0.28, "square");
    tone(1047, 0.18, 0.70, 0.42, "square");
  }

  // ── Event notification sounds ────────────────────────────────────────────

  /**
   * EVENT — cheerful two-tone fanfare (major interval)
   * "Something is happening — an event update."
   * Uses the same sound regardless of priority for a consistent event feel.
   */
  function playEvent() {
    tone(659, 0.22, 0.35, 0.00, "sine");   // E5
    tone(784, 0.16, 0.28, 0.24, "sine");   // G5
    tone(1047, 0.28, 0.40, 0.42, "sine");  // C6 — bright finish
  }

  // ── Public API ───────────────────────────────────────────────────────────

  window.portalSound = {
    /**
     * play(priority, type)
     *
     * priority : "low" | "medium" | "high" | "critical"
     *            OR a named sound: "location_off" | "location_on"
     * type     : (optional) "task" | "event" | "location" | "general"
     *
     * When type is provided, task and event notifications get their own
     * distinct sounds that still scale with criticality.
     */
    play: function (priority, type) {
      const ac = getCtx();
      if (!ac) return;

      const p = (priority || "low").toLowerCase();
      const t = (type || "general").toLowerCase();

      // Named sounds — always play regardless of type
      if (p === "location_off")  { playLocationOff(); return; }
      if (p === "location_on")   { playLocationOn();  return; }

      // Task sounds — distinct per criticality
      if (t === "task") {
        switch (p) {
          case "critical": playTaskCritical(); return;
          case "high":     playTaskHigh();     return;
          case "medium":   playTaskMedium();   return;
          default:         playTaskLow();      return;
        }
      }

      // Event sounds — same cheerful fanfare for all priorities
      if (t === "event") {
        playEvent();
        return;
      }

      // General / location notifications — use priority-based sounds
      switch (p) {
        case "critical": playCritical(); break;
        case "high":     playHigh();     break;
        case "medium":   playMedium();   break;
        default:         playLow();      break;
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
