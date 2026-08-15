# 2026-07-03 — Planificator: orizonturi lungi (pana la 6 luni) + coloane adaptive + toggle weekend

- **2026-07-03 — Planificator: orizonturi lungi (pana la 6 luni) + coloane adaptive + toggle weekend**
  (SW v79): orizonturi noi **7/14/30/90/180** zile (label-uri 7z/14z/30z/3L/6L). **Coloane adaptive**
  (`buildColumns` in `lib/planDates.js`): <=31z = pe ZI (cu weekend), <=92z = pe SAPTAMANA (ISO, label
  „S27 · 29 iun"), altfel pe LUNA („Iul 2026"). Barele raman pozitionate prin `spanRect` pe fractiune de
  zi — granularitatea e doar chestiune de header/gridlines. Coloanele au geometrie in % (partiale la
  margini). `days` clamp in backend ridicat 60→370. **Toggle „Weekend"** (`plan.showWeekends`, persistat
  localStorage `pif-plan-weekends`) — evidentiaza/ascunde benzile de weekend; dezactivat automat in
  modul saptamana/luna (weekendul n-are sens acolo). Verificat E2E: 3L→14 coloane saptamanale, 6L→6
  coloane lunare, weekend on/off 4↔0 benzi, disabled in modul saptamanal, 0 erori. **RAMAS de discutat
  cu Ion (intrebat):** (a) export PDF — abordare (print-to-PDF client vs fisier server reportlab) +
  „toate vs per proiect"; (b) taskurile FARA termen (azi nu apar pe timeline) — rail „backlog" cu drag
  pe timeline vs coloana „fara termen" vs ignorate. „Mai avem mai multe de gandit" (Ion).
