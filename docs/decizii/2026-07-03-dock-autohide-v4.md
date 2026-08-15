# 2026-07-03 — Dock autohide v4: pur pe cursor (ascuns by default)

- **2026-07-03 — Dock autohide v4: pur pe cursor (ascuns by default)** (SW v65, `Dock.svelte`):
  Ion a cerut explicit modelul simplu — dock-ul ASCUNS by default TOT timpul, apare DOAR cat timp
  cursorul e in zona de jos, se ascunde imediat ce iesi. Am scos toata logica de scroll (atTop/
  atBottom/scroller-detection — sursa de bug-uri) si dependenta de scroll: `hidden` porneste `true`,
  `apply()` = `hidden = kbLocked ? true : !inZone`, `inZone` din mousemove (`innerHeight-clientY <=
  130` apare / `>160` dispare). Ruta noua -> `hidden=true`. Mobil: manerul peek `revealFromPeek()`
  arata ~4s apoi ascunde. Verificat Playwright: la load (top) ascuns+peek, cursor mijloc ascuns,
  cursor jos apare, cursor sus ascuns, dupa nav din dock + cursor sus ascuns. (v3 arata si la top/
  capat de pagina — Ion NU voia asta.)
