# 2026-07-03 — Gantt de proiect: cele 4 imbunatatiri + faze (Plane-inspired)

- **2026-07-03 — Gantt de proiect: cele 4 imbunatatiri + faze (Plane-inspired)** (SW v87, SCHEMA v25):
  Ion a cerut toate 4 + „conform Plane". **(1) Logo + semnatura PDF:** marca ramp amber desenata in
  reportlab (`_draw_logo`) + wordmark „PIF DASHBOARD" + bloc semnatura jos-dreapta (Intocmit/Aprobat
  client + Data). **(2) Drag/resize pe bare** in ProjectGantt (pointer events ca in Planificator; move
  = tot spanul, margini = o muchie, milestone drag; scrie data_start/data_scadenta). **(3) Reprogramare
  automata:** `_reschedule_project` (forward-pass ASAP, topological Kahn, FS/SS/FF/SF + lag, pastreaza
  durata, muta doar mai tarziu) + `POST /api/proiecte/<id>/reschedule`; buton „Reprogrameaza" + toggle
  „Auto" (localStorage) care ruleaza dupa fiecare `patch`. **(4) Drum critic:** CPM pe frontend (durate +
  DAG, forward/backward, slack=0), toggle „Drum critic" evidentiaza cu rosu barele+sagetile. **(5) Faze
  (Plane cycles):** migratie v24→v25 `tasks.faza TEXT`; view grupeaza pe faza in `displayRows` (rand
  fază = header colapsabil + summary bar cu progres rulat duration-weighted; taskuri indentate; coloana
  „Fază" editabila; `idxMap`/SVG height pe displayRows ca sagetile/critical sa ramana corecte). Backend:
  create/update/collect duc `faza`; EXPORTURILE grupeaza pe faza — PDF cu header bold + summary bar per
  faza, Excel cu coloana „Faza" + tasks sortate pe faza. Verificat E2E: drag/resize, reschedule cascada
  A→B→C, drum critic 3 bare+2 sageti, faze 3 grupuri+collapse (fara regresie), PDF+XLSX randate corect.
  **Gotcha sandbox:** procese `app.py` vechi raman pe portul 5000 (pkill in compound da exit 144 fara sa
  omoare) → `for p in $(pgrep -f app.py); do kill -9 $p; done`. Toate livrate incremental (v83→v87).
