# 2026-07-03 — Planificator: export PDF (print) + rail „Backlog" + drag-to-schedule

- **2026-07-03 — Planificator: export PDF (print) + rail „Backlog" (taskuri fara termen) + drag-to-schedule**
  (SW v80, alegeri Ion): **(A) Export PDF = print-to-PDF client** (NU reportlab): buton „Export PDF" →
  modal (Modal.svelte) cu alegere scope (checkbox per proiect + „Toate") + optiune „cate un proiect pe
  pagina". `runExport()` forteaza `data-theme=light` (print pe hartie, indiferent de tema app) + clasa
  `body.plan-printing` + optional `body.plan-pagebreak`, apoi `window.print()`; `afterprint` restaureaza
  tema. Print CSS: `@page A4 landscape`, ascunde chrome (header/dock in global.css gated pe
  `body.plan-printing`; controls/hint/mlist/backlog in Plan.svelte), `.inner{min-width:0;width:100%}` ca
  swimlane-ul (tot pct-based) sa se incadreze pe pagina, `.lane.print-hide` pt proiecte deselectate,
  break-after:page per lane cand pagebreak. Titlu print `.print-title` (interval). Verificat cu
  `page.pdf()`: chrome ascuns, tema light, incadrat pe A4, culori pastrate. **(B) Backlog** — endpoint
  `/api/plan` intoarce acum si `backlog[]` = taskuri open FARA plan SI fara scadenta (proiect+global,
  helper `_backlog_item`, LIMIT 300). Rail colapsabil „Fara termen" sub chart cu chip-uri draggable
  (HTML5 DnD). **Drag pe timeline** (`.p-body` = drop zone, `dayFromEvent` calc ziua din X relativ la
  `--lane-w`) → `scheduleBacklog(tip,id,data)` seteaza DOAR `data_planificata` (nu inventam termen).
  Indicator live `.drop-line`+`.drop-tag` la dragover. Fallback fara drag: fiecare chip are un DatePicker
  („Planifica"). Verificat E2E: 3 chip-uri backlog, drag → backlog 3→2 + task planificat, modal export 4
  randuri, 0 erori. **RAMAS (Ion: „mai avem mai multe de gandit"):** asteapta restul ideilor lui.
