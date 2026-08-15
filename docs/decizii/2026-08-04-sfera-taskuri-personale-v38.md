# 2026-08-04 — Taskuri personale: `global_tasks.sfera` (v38), nu tabela noua

- **2026-08-04 — Taskuri personale: `global_tasks.sfera` (v38), nu tabela noua.**
  Cerinta Ion: taskuri in afara jobului, NEamestecate cu munca, subtil, corect pe
  mobil. Discriminator `sfera` ('munca'|'personal'), aceeasi tabela — o tabela
  separata ar fi dublat recurenta, subtaskurile si CRUD-ul. Regula: FIECARE
  interogare pe global_tasks isi declara sfera explicit; lipsa parametrului =
  'munca' (fail-closed), valoare necunoscuta = 400. Suprafete: /tasks are
  comutator Munca·Personal (din `router.query.sfera`, adresabil); boardul
  „Astăzi" primeste cheia separata `personale[]` randata ca anexa discreta
  (antet .pers-cap cu punct violet --purple — NU .grup-cap, clasa e citita de
  audit_mobil); Planificator, agenda/candidates si feedul ICS de munca EXCLUD
  personalul; cautarea e singura suprafata cross-sfera (eticheteaza „Personal").
  Spawn-ul recurent COPIAZA sfera (altfel taskul migra la munca la bifare) si
  restore-ul o completeaza cu 'munca' pe backupuri pre-v38. Google Calendar:
  feedul .ics accepta acum `?key=<ics_feed_key din app_settings>` (Google
  descarca fara sesiune/headere) + `?sfera=personal` — feed separat „PIF
  Personal"; butonul „Google Calendar" din vederea personala copiaza linkul.
  Prins pe drum: `focusHref` hardcoda `?` — cu o cale care are deja query
  (`/tasks?sfera=personal`) producea `?...?focus=` si getQuery citea gresit.
  Self-heal aditiv pe lipsa coloanei (nu poate anula nimic). Teste: 11 asertii
  anti-scurgere in test_suite (`sfera_leak_test`), ruta `/tasks?sfera=personal`
  in smoke_ui. Neacoperit inca: scenariu de gest in audit_mobil pentru vederea
  personala (optional, API-ul e acoperit).
