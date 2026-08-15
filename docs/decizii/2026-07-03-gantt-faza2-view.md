# 2026-07-03 — Gantt de proiect — FAZA 2: view-ul (tab in ProjectDetail)

- **2026-07-03 — Gantt de proiect — FAZA 2: view-ul (tab in ProjectDetail)** (SW v82): tab nou „Gantt"
  in `pages/ProjectDetail.svelte` (dupa Taskuri) → `components/gantt/ProjectGantt.svelte`. Layout
  two-pane GanttProject-style: **tabel taskuri stanga** (# / Nume / Start / Sfarsit / Zile / % / actiuni)
  + **timeline dreapta** (overflow-x). Randurile aliniate prin inaltimi fixe (`--row-h`/`--head-h`),
  scroll vertical comun (pagina), doar timeline-ul scrolleaza orizontal. Fereastra se **auto-fit** pe
  spanul real al proiectului (taskuri + data_incepere/deadline, padded) + coloane adaptive
  (`buildColumns` refolosit). Bare start→end cu **fill de progres** (latime = progres%), **milestone**
  = diamant (is_milestone), status = culoare (done verde / in_lucru amber / to_do contur), today line +
  weekend. **Editare inline in tabel**: Start/Sfarsit via DatePicker, % via input (blur/Enter),
  milestone toggle (flag), rename (click pe nume), sterge, „Task nou". % din subtaskuri e READ-ONLY
  (afisat cu tooltip done/total); doar taskurile fara subtaskuri au input manual. Foloseste
  createTask/updateTask/deleteTask din store + `/api/proiecte/<id>/gantt`. Verificat E2E: 6 randuri, 5
  bare + 1 milestone, fills 100/100/40/0/0, 0 erori. **URMEAZA:** Faza 3 sageti dependente (datele vin
  deja in payload), Faza 4 export PDF profesional + Excel.
