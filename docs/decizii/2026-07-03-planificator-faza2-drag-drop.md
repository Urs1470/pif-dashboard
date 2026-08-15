# 2026-07-03 — Planificator Faza 2 + fix Dock reveal-edge

- **2026-07-03 — Planificator Faza 2 + fix Dock reveal-edge** (SW v78, acelasi deploy): (1) **drag &
  drop** pe swimlane — tragi corpul barei = muti tot spanul (pointer events, snap la zi, preview live
  cu datele noi intr-un `.drag-label`); **resize** de la marginile barei (`.rz-l`/`.rz-r`) = muti doar
  o muchie (start=data_planificata / termen=data_scadenta). Commit prin `setTaskDates(tip,id,body)` din
  store (setter EXPLICIT — NU cupleaza plan+scadenta ca `moveTaskDate`; span-drag pastreaza spanul).
  Click (fara miscare) pe bara = deschide popover-ul. Taskurile `done` sunt read-only pe timeline.
  (2) **Packing** — bare care nu se suprapun in timp impart acelasi rand (`packRows`, greedy pe start),
  in loc de un rand per task. (3) **Orizont segmentat 7/14/30** (`setHorizon`, `plan.days` din store;
  coloanele se rescaleaza, `compact` >18 zile ascunde ziua saptamanii). (4) **Toggle „Finalizate"** —
  `?done=1` la `/api/plan` include taskurile done (span din plan/scadenta SAU `data_finalizare` in
  fereastra); `_agenda_item` acum poarta si `data_finalizare`. Bare done = estompate + taiate. Verificat
  E2E: packing (8 bare→4 randuri), orizont 7/14/30, drag (+2 zile pe plan), resize-R (+2 zile pe termen),
  done backend, 0 erori consola. **Fix Dock (cerut de Ion):** `REVEAL_EDGE` in `Dock.svelte` 6px→48px
  (+ `HIDE_ZONE` 110→150) — la 6px trebuia sa ajungi in taskbar-ul Windows si dadeai peste el din
  inertie; la 48px dock-ul apare inainte de marginea sistemului.
