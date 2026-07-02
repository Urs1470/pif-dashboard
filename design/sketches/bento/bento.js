/* Bento sketches — shared JS: dock injectat, switcher variante, count-up, timer live */
(function () {
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- dock (navigație între schițe) ---------- */
  const ICONS = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>',
    projects: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    tasks: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m4 5 1 1 2-2M4 11l1 1 2-2M4 17l1 1 2-2"/>',
    params: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"/><path d="M2 14h4M10 8h4M18 16h4"/>',
    calculator: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01"/>',
    notes: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
    admin: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.09a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  };
  const PAGES = [
    ['home', 'Acasa'], ['projects', 'Proiecte'], ['tasks', 'Taskuri'], ['params', 'Parametri'],
    ['sep'], ['calculator', 'Calculator'], ['notes', 'Notițe'], ['admin', 'Admin'],
  ];
  const current = (location.pathname.split('/').pop() || 'home.html').replace('.html', '');
  const dock = document.createElement('nav');
  dock.className = 'dock';
  dock.innerHTML = PAGES.map(([key, title]) => {
    if (key === 'sep') return '<span class="sep"></span>';
    const on = key === current ? ' class="on"' : '';
    return `<a href="${key}.html"${on} title="${title}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[key]}</svg></a>`;
  }).join('');
  document.body.appendChild(dock);

  /* ---------- count-up (rAF, ease-out cubic) ---------- */
  function countUp(el) {
    const target = parseFloat(el.dataset.dec || el.dataset.count);
    const isDec = !!el.dataset.dec;
    if (reduced) { el.textContent = isDec ? target.toFixed(1) : target; return; }
    const t0 = performance.now(), dur = 650;
    (function tick(t) {
      const p = Math.min(((t || performance.now()) - t0) / dur, 1);
      const e = 1 - Math.pow(1 - p, 3);
      el.textContent = isDec ? (target * e).toFixed(1) : Math.round(target * e);
      if (p < 1) requestAnimationFrame(tick);
    })();
  }
  function runCountUps(scope) {
    (scope || document).querySelectorAll('[data-count]').forEach(countUp);
  }

  /* ---------- switcher variante ---------- */
  const VNAMES = window.VARIANT_NAMES || {};
  window.setv = function (n) {
    document.querySelectorAll('.variant').forEach(v => v.classList.remove('on'));
    document.querySelectorAll('.vbtn').forEach(b => b.classList.remove('on'));
    const v = document.getElementById('v' + n);
    const b = document.getElementById('vb' + n);
    if (!v) return;
    v.classList.add('on');
    if (b) b.classList.add('on');
    const nameEl = document.querySelector('.vname');
    if (nameEl && VNAMES[n]) nameEl.textContent = VNAMES[n];
    /* re-declanșează animația de intrare a celulelor */
    v.querySelectorAll('.cell').forEach(c => { c.style.animation = 'none'; void c.offsetWidth; c.style.animation = ''; });
    runCountUps(v);
    /* inele de progres din varianta activă */
    v.querySelectorAll('.ring .val[data-pct]').forEach(r => {
      const circ = parseFloat(r.dataset.circ);
      r.style.strokeDashoffset = circ;
      requestAnimationFrame(() => requestAnimationFrame(() => {
        r.style.strokeDashoffset = circ * (1 - parseFloat(r.dataset.pct) / 100);
      }));
    });
    window.scrollTo({ top: 0 });
  };

  /* ---------- timer live (01:42:17 → rulează) ---------- */
  let secs = 1 * 3600 + 42 * 60 + 17;
  setInterval(() => {
    secs++;
    const h = String(Math.floor(secs / 3600)).padStart(2, '0');
    const m = String(Math.floor(secs % 3600 / 60)).padStart(2, '0');
    const s = String(secs % 60).padStart(2, '0');
    document.querySelectorAll('.js-clock').forEach(el => { el.textContent = `${h}:${m}:${s}`; });
    document.querySelectorAll('.js-clock-rich').forEach(el => { el.innerHTML = `${h}:${m}:<span class="sec">${s}</span>`; });
  }, 1000);

  /* ---------- toggle done pe rânduri ---------- */
  window.tgDone = function (el) { el.classList.toggle('done'); };

  document.addEventListener('DOMContentLoaded', () => setv(1));
})();
