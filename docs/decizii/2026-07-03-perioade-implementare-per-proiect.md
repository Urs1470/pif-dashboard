# 2026-07-03 — Perioade de implementare per proiect (Site / Sediu EGB)

- **2026-07-03 — Perioade de implementare per proiect (Site / Sediu EGB)** (SW v88, SCHEMA v26): cerut de
  Ion — pe proiect, perioade de implementare SEPARATE de taskuri, cu locatia Site (santier) / Sediu EGB;
  mai multe per proiect; afisate SI ca banda pe Gantt SI in tabul Info. **Migratie v25→v26:** tabel
  `implementari` (proiect_id FK CASCADE, data_start, data_sfarsit, locatie 'site'|'sediu', eticheta,
  ordine). **Backend (projects.py):** CRUD `GET/POST /api/proiecte/<id>/implementari`, `PUT/DELETE
  /api/implementari/<id>`; `_collect_gantt` (tasks.py) intoarce si `implementari[]`. **Frontend:**
  `components/projects/ImplPeriodModal.svelte` (form partajat: DatePicker×2 + toggle Site/Sediu EGB +
  eticheta + delete); `ImplPeriods.svelte` (tabel in Info, add/edit/delete); in `ProjectGantt` perioadele
  = rZnduri `kind:'impl'` la INCEPUTUL `displayRows` (banda colorata site=teal #3f9dc4 / sediu=gold
  #c99a3a, separata de bare), buton „Perioadă" in toolbar, click→modal. Fereastra Gantt include datele
  perioadelor. **Exporturi:** PDF (rand+banda colorata sus) si Excel (randuri impl sus cu celule
  colorate) le includ. Verificat E2E: 2 benzi Gantt + 2 randuri Info + modal, PDF+XLSX cu perioadele.
