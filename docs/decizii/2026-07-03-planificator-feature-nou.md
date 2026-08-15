# 2026-07-03 — Feature nou „Planificator" (swimlane operational 14 zile)

- **2026-07-03 — Feature nou „Planificator" (swimlane operational 14 zile)** (SW v78, ales de Ion
  dintre 3 schite de Gantt): ruta noua `/plan` in Dock (iconita solid `plan` = calendar cu bare),
  orizont **14 zile fix** de la azi. **Lane colorat per proiect** = intervalul intreg al proiectului
  (`data_incepere→deadline`, clamped la fereastra, cu diamant la deadline) care CONTINE taskurile lui
  ca sub-bare (`data_planificata→data_scadenta`); task fara plan = marker single-day pe ziua termenului.
  Lane „Globale" la final. **Zero schema noua** — reutilizeaza semantica de planificare din agenda
  (bara = planificat→scadent). Backend: endpoint nou `GET /api/plan?start=&days=14&today=` (blueprints/
  tasks.py, langa `/api/agenda/*`) — refoloseste `_agenda_item` + noul `_span_intersects`; exclude
  proiecte anulat/finalizat, taskuri done, recurente viitoare (acelasi idiom ca agenda). Frontend:
  `pages/Plan.svelte` (swimlane CSS-grid/flex + overlay gridlines/weekend/azi, popover de actiuni pe
  click bara: Deschide/Muta pe.. via DatePicker/+1 zi/Bifeaza), `stores/plan.svelte.js` (reuse
  updateTask/updateGlobalTask; reprogramarea muta si deadline-ul daca exista, ca in agenda),
  `lib/planDates.js` (buildDays/spanRect/dayDiff, LOCAL date, nu UTC). Culori lane = hash pe id →
  paleta de 7 hue-uri distincte de amber (accentul ramane rezervat starii active/chrome). **Sub 820px**
  = fallback lista grupata pe proiect (grila de 14 coloane nu incape pe telefon). Reprogramarea prin
  drag&drop + packing pe lane + orizont segmentat 7/14/30 = **Faza 2** (neimplementate). Verificat:
  backend cu test izolat (proiect+taskuri, excludere out-of-window/anulat/recurenta), Playwright E2E
  desktop (4 lane / 8 bare / 14 coloane / popover) + mobil (grupuri+randuri, chart ascuns), 0 erori consola.
