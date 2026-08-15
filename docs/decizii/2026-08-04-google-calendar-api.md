# 2026-08-04 — Google Calendar API: push instant pentru taskurile personale

- **2026-08-04 (2) — Google Calendar API: push instant pentru taskurile personale.**
  Cerinta Ion („vreau sincronizare automata prin Google Calendar API"). Blueprint
  nou `blueprints/google_calendar.py`: OAuth 2.0 web flow server-side
  (`/oauth/google/start` -> consent -> `/oauth/google/callback`, state in
  sesiune, SameSite=Lax supravietuieste; rute in afara /api = fara rate limit),
  creds in env (`GOOGLE_CLIENT_ID/SECRET`), tokens in app_settings sub chei
  `google_*`. Sync ONE-WAY dashboard->Google, hook-uri post-commit in
  POST/PUT/DELETE global-tasks (tipar `sync_project_frontmatter`: thread daemon
  best-effort; PUT trimite si ocurenta recurenta spawn-uita). Scope granular
  `calendar.app.created`; calendarul „PIF Personal" e creat de app. Id eveniment
  = uuid-ul taskului fara cratime (determinist, fara tabela de mapare).
  **Capcana load-bearing:** Google nu elibereaza NICIODATA un id de eveniment
  sters — insert dupa delete da 409 pe veci; upsert = insert, la 409 patch cu
  `status:'confirmed'` (reinvie evenimentul anulat). Bifat = evenimentul RAMANE
  cu prefix „✓ " (ales de Ion) — divergenta INTENTIONATA fata de .ics, care
  exclude finalizatele; nu o „reparati". `invalid_grant` (revocare sau consent
  screen ramas in Testing — expira la 7 zile; appul trebuie PUBLICAT in
  Production) -> stare deconectat + mesaj in `/api/google/status`. Backup JSON
  EXCLUDE cheile `google_*`; restore le PASTREAZA peste DELETE si ignora
  `google_*` venite din fisier (anti-injectare). Nota: `ics_feed_key` curge in
  continuare in backup (clasa preexistenta, miza mica); db-dump e baza bruta.
  Resync bidirectional (`/api/google/resync`): sterge si orfanii din calendar.
  Zero dependente noi (stdlib urllib, timeout 15s peste tot). Fara migrare.
