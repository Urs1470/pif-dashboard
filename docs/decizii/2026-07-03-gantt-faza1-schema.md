# 2026-07-03 — Gantt de proiect „GanttProject-lite" — FAZA 1: schema + backend

- **2026-07-03 — Gantt de proiect „GanttProject-lite" — FAZA 1: schema + backend** (SCHEMA v24): Ion
  vrea un Gantt per-proiect complet, client-ready (prezentat ca PDF + export Excel, selectand proiectul),
  cu tabel taskuri + start/sfarsit + %progres + dependente cu sageti + milestones. Se construieste in
  faze; asta e fundatia. **Migratie v23→v24** (`migrate_v23_to_v24`, idempotenta + self-heal):
  `tasks.data_start TEXT`, `tasks.progres INTEGER`, `tasks.is_milestone INTEGER` + tabel nou
  `task_dependencies` (id, proiect_id, predecessor_id, successor_id, tip FS/SS/FF/SF, lag, FK CASCADE la
  proiecte+tasks; STRICT intre taskuri de proiect). create_task/update_task extinse cu cele 3 campuri
  (COALESCE, is_milestone normalizat 0/1). delete_task sterge si dependentele (explicit + FK).
  **Endpoint nou** `GET /api/proiecte/<id>/gantt` → {proiect, tasks[], dependencies[]}; task-ul are
  `data_start` (fallback data_planificata), `data_scadenta`, `is_milestone`, `progres` EFECTIV
  (`_effective_progress`: 100 daca done, altfel raport subtaskuri bifate daca are, altfel coloana
  `progres` manuala) + subtask_done/total. `POST /api/proiecte/<id>/dependencies` (valideaza ambele in
  proiect, blocheaza self/duplicat/CICLU via `_would_cycle` DFS pe succesori), `DELETE
  /api/dependencies/<id>`. Verificat: schema v24, done→100%, milestone, subtask-derived 33% (1/3),
  dep 201, ciclu 400, duplicat 409, self 400, cascade la delete task. **URMEAZA:** Faza 2 view (tab
  Gantt in ProjectDetail: tabel taskuri + bare start→end + bara progres + milestones), Faza 3 sageti
  dependente, Faza 4 export PDF profesional (antet proiect/client/perioada + legenda) + export Excel.
