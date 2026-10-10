# 2026-10-10 Limita de PIN comună, `.map` cu login, CSRF doar pentru Bearer valid, `PIF_UPLOAD_FOLDER`

Închide E-289 (cele trei constatări rămase din E-263) și E-004.

- **Limita de PIN** (5 încercări / 5 min / IP) stătea într-un dict per worker Gunicorn și se golea la
  fiecare redeploy: în practică până la 10 încercări pe fereastră, resetate la fiecare push. Acum stă
  într-un fișier SQLite separat, `<PIF_DB_PATH>.ratelimit` (`ratelimit.py`), tranzacție `BEGIN
  IMMEDIATE` per încercare. Ales în loc de o tabelă în baza aplicației (ar fi fost schimbare de
  schemă, iar restore-ul și `db-upload` ar fi șters istoricul) și în loc de `fcntl` pe un JSON
  (mai mult cod pentru aceeași atomicitate). Dacă fișierul nu merge, se loghează eroarea și limita
  cade pe memoria workerului (comportamentul vechi), ca un fișier de ajutor să nu încuie loginul.
  Limita generală de 60 cereri/min rămâne în memorie: nu apără un secret.
- **`*.map` din `/torqa/`** cer sesiune (401 JSON fără); `private, no-cache`. Restul fișierelor
  rămân publice, fără cookie. Torqa web nu cere hărți în funcționare; doar uneltele unui browser logat.
- **CSRF**: se sare doar pentru un Bearer VALID (`utils._check_api_token`). Un Bearer greșit (sau
  tokenul de dispozitiv pe o rută interzisă lui) pe o cerere cu sesiune cere antetul `X-CSRF-Token`.
  Contractul APK-ului nu se schimbă: Torqa trimite tokenul valid.
- **`PIF_UPLOAD_FOLDER`** alege directorul fișierelor urcate; implicit tot `uploads/` de lângă cod.
