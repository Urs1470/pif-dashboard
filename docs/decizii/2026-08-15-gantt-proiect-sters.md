# 2026-08-15 — Ganttul din pagina de proiect a plecat, cu tot cu server

- **2026-08-15 (3) — Ganttul din pagina de proiect a plecat, cu tot cu server.**
  Ion: „vom sterge gantt in interiorul proiectului, trebuie sa ramana doar
  optiunea de adaugare perioade de implementare", apoi, despre rutele ramase
  fara cititor: „sterge si alea".
  - Tabul „Gantt" a devenit „Perioade" si contine doar `ImplPeriods`.
  - `components/gantt/ProjectGantt.svelte` sters (directorul a ramas gol si a
    plecat si el), impreuna cu `openTaskFromGantt`.
  - **Pe server:** `/api/proiecte/<id>/gantt`, `/gantt.pdf` si `/gantt.xlsx`, plus
    ajutoarele lor (`_collect_gantt`, `_gantt_window`, `_effective_progress`) —
    **705 linii** din `blueprints/tasks.py`. Toate trei aveau un singur cititor,
    care era chiar tabul. `send_file` si `BytesIO` au iesit din importuri odata
    cu ele. Verificat dupa: 89 de rute, niciuna cu „gantt".
  - **Exportul PDF al proiectului NU a disparut:** `exportPdf` din antetul paginii
    foloseste `/api/export/pdf?project_id=`, alta ruta, care ramane.
  - Prima varianta MUTASE butoanele de export langa perioade, ca sa nu piara doua
    functii care mergeau. Ion a cerut sa plece si ele — corect: tipareau exact
    vederea in timp pe care tocmai o scoteam, deci fara Gantt n-aveau ce
    reprezenta.
  - **Taburile din pagina de proiect trec acum si ele prin memorie** (era ultimul
    loc cu schelet la fiecare intrare): lista de note wiki, continutul notei, si
    perioadele. Salvarea unei note uita nota; salvarea unei perioade uita si
    `/api/calendar` si `/api/plan`, unde perioadele se vad la fel.
