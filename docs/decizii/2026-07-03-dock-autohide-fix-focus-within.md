# 2026-07-03 — Dock autohide: fix `:focus-within` (cauza reala „nu se ascunde")

- **2026-07-03 — Dock autohide: fix `:focus-within` (cauza reala „nu se ascunde")** (SW v64,
  `Dock.svelte`): dupa v60 (scroller corect) userul tot spunea „nu face autohide". Cauza: regula
  CSS `.dock.hidden:focus-within { --dock-shift: 0 }` — cand navighezi CLICKAND pe un item din dock
  (nav-ul principal), link-ul `<a>` ramane focusat → `:focus-within` tinea dock-ul vizibil, deci NU
  se ascundea niciodata la scroll dupa o navigare din dock. Fix: sters regula `:focus-within` +
  `onclick={(e)=>e.currentTarget.blur()}` pe iteme. (Gotcha test: testele Playwright navigau prin
  `goto()`, nu prin click → nu prindeau bug-ul; iar viewport-uri mici / continut scurt faceau
  `atTop`/`atBottom` mereu true → falsa impresie ca „nu se ascunde". Verificat corect cu viewport
  1200×800 + continut inalt fortat: scroll 600 + cursor sus → hidden=true.)
