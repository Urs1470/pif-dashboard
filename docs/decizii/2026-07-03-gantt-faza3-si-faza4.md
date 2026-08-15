# 2026-07-03 — Gantt de proiect — FAZA 3 (dependente cu sageti) + FAZA 4 (export PDF + Excel)

- **2026-07-03 — Gantt de proiect — FAZA 3 (dependente cu sageti) + FAZA 4 (export PDF + Excel)** (SW v83):
  **Faza 3:** sageti de dependenta desenate ca SVG peste `.g-body` (bind:clientWidth → coordonate px,
  path ortogonal cot + varf), din `data.dependencies`. Creare prin **link-mode** (buton lant `Link2` pe
  rand: click pe predecesor → banner → click pe succesor → POST dependency); stergere prin **click pe
  sageata** (DELETE). Verificat E2E: 1 sageata seed, creare 1→2, stergere 2→1, 0 erori. **Faza 4 (ales
  de Ion: „si si" — PDF SI Excel, per-proiect):** export **SERVER-SIDE** (nu print de browser — client-
  ready, consistent). `GET /api/proiecte/<id>/gantt.pdf` (reportlab canvas, landscape A4): antet
  proiect/client/cod/perioada/generat + gantt desenat (label-uri, bare cu fill de progres, milestone
  diamant, today line, sageti dependenta, zebra, legenda). `GET /api/proiecte/<id>/gantt.xlsx` (openpyxl):
  antet + tabel (#/Task/Start/Sfarsit/Zile/%/Status/Milestone/Depinde de) + **grila saptamanala** cu
  celule colorate pe status (gantt vizual in Excel), freeze panes. Helper comun `_collect_gantt` (JSON +
  ambele exporturi il refolosesc). Butoane „PDF"/„Excel" (anchor GET, sesiune) in toolbar-ul Gantt.
  GOTCHA: `from io import BytesIO` lipsea in tasks.py (500 la prima incercare). Verificat: PDF valid
  (`%PDF-`, randat corect), XLSX zip valid (tabel + grila, 13 coloane). Cele 4 faze COMPLETE.
