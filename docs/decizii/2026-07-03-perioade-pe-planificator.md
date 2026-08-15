# 2026-07-03 — Perioade de implementare pe Planificator (/plan) + fix Gantt empty-state

- **2026-07-03 — Perioade de implementare pe Planificator (/plan) + fix Gantt empty-state** (SW v90):
  (1) Fix: `ProjectGantt` ascundea tot timeline-ul cand `data.tasks.length===0` → o perioada pe un
  proiect fara taskuri nu se vedea. Acum arata Gantt-ul daca exista taskuri SAU perioade (EmptyState doar
  cand ambele lipsesc). (2) Perioadele apar acum si pe **Planificatorul multi-proiect** (cerut de Ion, „B"):
  `/api/plan` ataseaza `implementari[]` per lane de proiect (cele care intersecteaza fereastra; lane-ul
  apare si daca are DOAR o perioada in fereastra). `Plan.svelte`: `views` calculeaza rect-uri pt perioade,
  randate ca benzi colorate (site=teal #3f9dc4 / sediu=gold #c99a3a) sus in fiecare lane, + in lista mobila
  ca `.mimpl`. Verificat E2E: API 2 impl/lane, 2 benzi pe /plan, 0 erori.
