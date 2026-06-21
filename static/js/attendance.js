// ── Live clock & duration ───────────────────────────────────────────────────
(function () {
  function pad(n) { return String(n).padStart(2, '0'); }

  function tick() {
    const now = new Date();
    const clockEl = document.getElementById('liveClock');
    const dateEl  = document.getElementById('liveDate');
    const durEl   = document.getElementById('liveDuration');

    if (clockEl) {
      clockEl.textContent =
        pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
    }
    if (dateEl) {
      dateEl.textContent = now.toLocaleDateString('en-GB', {
        weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
      });
    }
    if (durEl) {
      const checkin = new Date(durEl.dataset.checkin);
      if (!isNaN(checkin)) {
        const secs  = Math.floor((now - checkin) / 1000);
        const h     = Math.floor(secs / 3600);
        const m     = Math.floor((secs % 3600) / 60);
        const s     = secs % 60;
        durEl.textContent = pad(h) + 'h ' + pad(m) + 'm ' + pad(s) + 's';
      }
    }
  }

  tick();
  setInterval(tick, 1000);
})();

// ── GPS form submission ─────────────────────────────────────────────────────
document.querySelectorAll('[data-gps-form]').forEach(function (form) {
  form.addEventListener('submit', function (event) {
    if (form.dataset.ready === '1') return;
    event.preventDefault();

    const btn = form.querySelector('button[type=submit], button:not([type])');
    const origText = btn ? btn.innerHTML : '';
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Getting GPS…';
    }

    navigator.geolocation.getCurrentPosition(
      function (pos) {
        form.querySelector('[name=latitude]').value  = pos.coords.latitude.toFixed(7);
        form.querySelector('[name=longitude]').value = pos.coords.longitude.toFixed(7);
        form.dataset.ready = '1';
        form.requestSubmit();
      },
      function () {
        if (btn) { btn.disabled = false; btn.innerHTML = origText; }
        alert('GPS permission is required for attendance. Please allow location access and try again.');
      },
      { timeout: 15000, maximumAge: 0, enableHighAccuracy: true }
    );
  });
});

// ── Leaflet map ─────────────────────────────────────────────────────────────
if (window.portalSite && document.getElementById('map')) {
  const map = L.map('map').setView([window.portalSite.lat, window.portalSite.lng], 17);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);
  L.marker([window.portalSite.lat, window.portalSite.lng])
    .addTo(map)
    .bindPopup('<strong>Swahilipot Hub</strong>').openPopup();
  L.circle([window.portalSite.lat, window.portalSite.lng], {
    radius: window.portalSite.radius,
    color: '#0F4C81',
    fillColor: '#1E88E5',
    fillOpacity: 0.1
  }).addTo(map);
}
