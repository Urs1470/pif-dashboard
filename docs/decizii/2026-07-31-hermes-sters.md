# 2026-07-31 — HERMES.md sters (cerinta Ion) + runda de design ca sistem

- **2026-07-31 (7) — HERMES.md sters (cerinta Ion) + runda de design ca sistem.**
  HERMES.md era briefingul agentului Hermes; partea despre dashboard (sistemul
  de design) traieste acum ca sectiune „Design system (frontend)" in CLAUDE.md.
  Referintele curatate (CLAUDE.md, AGENT_BRIEFING.md, antetul din MEMORY,
  database.py, TodayBoard); intrarile istorice de mai jos raman cum au fost scrise.
  Runda de design, pe patru intrebari:
  **(1) Formularele folosesc libraria** — Categorie era `<input class="mf-input">`
  in ambele modale din /tasks (a treia reteta de camp, langa .field-input si
  .dp-trigger), Descrierea din modalul paginii de proiect era `<textarea>` brut,
  plus un `mf-field` GOL (perechea prioritatii, v34) care impingea Termenul in
  jumatatea dreapta. Toate -> `<Input>`/`<Textarea>`/`<DatePicker label>`;
  stilurile mf-* au plecat din ambele pagini.
  **(2) Acelasi obiect, acelasi desen** — chipul de context (categoria/proiectul)
  avea radius-full in /tasks si radius-xs pe „Astăzi"; pe telefon /tasks il facea
  text simplu, boardul il tinea pastila. Boardul preia reteta din /tasks.
  **(3) Contrastul, masurat automat** (ambele teme, cele 5 pagini): `--text-faint`
  e documentat „doar etichete/large" (3:1), dar scria INFORMATIE la 10-13px:
  clientul de pe cardul de proiect, intervalele din „urmatoarea iesire",
  indicatiile din Planificator, contoarele (tail, ms-c), „Proiect nou". Toate ->
  `--text-dim`; etichetele uppercase si separatorii raman faint. Re-scanat: zero
  informatie sub 4.5:1.
  **(4) Containerele goale** — verificate: sertarul gol din Plan dispare (e
  unealta, nu informatie — corect), Planificatorul si ziua goala din Calendar au
  stari explicate. Nimic de reparat.
  Toate 4 harnessurile verzi.
