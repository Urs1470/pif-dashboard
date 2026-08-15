# 2026-08-04 — Credentialele Google se pot lipi din UI; pasul systemd a disparut

- **2026-08-04 (3) — Credentialele Google se pot lipi din UI; pasul systemd a disparut.**
  Ion a intrebat daca poate trimite JSON-ul OAuth prin chat ca sa-i punem noi
  env vars pe server. Nu: secretele nu circula prin chat si sesiunile remote
  n-au SSH la server. In loc: `PUT /api/google/credentials` — JSON-ul descarcat
  din consola se lipeste in modalul Google din /tasks; validare server-side
  (tip `installed` respins cu explicatie; fail-early daca `redirect_uris` nu
  contine callback-ul nostru), stocare in app_settings sub `google_client_id`/
  `google_client_secret` — prefixul `google_` le tine automat afara din backup
  si le pastreaza la restore. ENV ARE PRIORITATE (si PUT-ul refuza cand sursa
  e env). DISCONNECT NU sterge credentialele (deconectarea rupe legatura cu
  contul, nu deconfigureaza; `GOOGLE_KEYS` ramane doar tokens+calendar+stare).
  `/api/google/status` are acum `sursa: 'env'|'setari'|''`.
