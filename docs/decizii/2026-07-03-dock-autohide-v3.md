# 2026-07-03 — Dock autohide v3 (reveal la cursor jos)

- **2026-07-03 — Dock autohide v3 (reveal la cursor jos)** (SW v60, `Dock.svelte`): Ion voia ca
  dock-ul sa se ascunda la scroll si sa reapara DOAR cand duci cursorul in zona de jos (unde sta
  dock-ul), si sa se ascunda iar cand pleci cursorul. **Bug-uri gasite:** (1) v2 se ascundea doar la
  `speed>0.5px/ms` — prag prea strict, nu se ascundea niciodata la scroll normal cu mouse-ul;
  (2) **GOTCHA scroller:** desi `.app-content#main-content` are `overflow-y:auto`, in practica
  documentul creste liber si **fereastra** deruleaza (`window.scrollY`), nu `#main-content`
  (`scrollHeight==clientHeight` acolo). Verificat cu Playwright: wheel -> `window.scrollY` se
  schimba, `#main-content.scrollTop` ramane 0. Fix: `mcScrolls()` = foloseste `#main-content`
  DOAR daca chiar deruleaza intern, altfel `window`/`document.scrollingElement`. Model nou:
  `hidden = !(atTop || atBottom || inBottomZone)`; `inBottomZone` = mousemove `innerHeight-clientY <
  120` (reveal) / `>180` (leave). Listeneri pe `window` SI pe `#main-content` (scroll). Manerul peek
  ramane pt mobil (fara cursor).
