# 2026-07-03 — Faza 2 quick-wins (batch 1)

- **2026-07-03 — Faza 2 quick-wins (batch 1)** (SW v63): **B1** — codurile de parametri din
  echipament (detaliu proiect) sunt clickabile → deschid detaliul din baza de parametri. Rezolvare
  cod→id prin `GET /api/search?q=<cod>` (ranking exact-pe-cod din `global_search`), apoi deep-link
  `navigate('/params?open=<id>')`; daca nu e in baza → toast. **B7** — buton de copy pe rand
  (`cod = valoare`, apare la hover / vizibil pe touch). **B8** — `shortcuts` in `manifest.json`
  (Astăzi / Taskuri / Calculator). Toate in `pages/ProjectDetail.svelte` (`openParamDetail`,
  `copyParam`, `.eparam-link`/`.eparam-copy`) + `frontend/public/manifest.json`. Ruta detaliu
  proiect = `/projects/:id` (hash). Local `parametri_master` e gol (0) → B1 cade pe toast; pe prod
  are ~14k, rezolva. Ramase din Faza 2: B3 (manual/coduri pe card echipament), B4 (favorite Params),
  B5 (foto camera atasamente), B6 (export ICS).
