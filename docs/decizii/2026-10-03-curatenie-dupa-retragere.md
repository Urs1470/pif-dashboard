# 2026-10-03 — Curățenie după retragere: dispozitivul și vault-ul, rute anonime, IP-ul clientului, CSP, restore

**Context.** După retragerea interfeței vechi (`2026-10-03-retragerea-interfetei-vechi.md`), serverul e doar backend-ul
Torqa. Un audit din aceeași zi a găsit ce a rămas din vremea SPA-ului și a calculatorului, plus două defecte de
fond: tokenul de dispozitiv (telefonul) citea și rescria orice notă din vault, iar restore-ul JSON pierdea coloane
(auditul a făcut backup, apoi restore, și le-a găsit goale). Ion a aprobat lucrarea; restore-ul, care e în mod normal
zonă interzisă, a fost aprobat explicit pentru ea.

## Ce s-a decis

1. **Dispozitivul și vault-ul.** `GET /api/obsidian/note` cu tokenul de dispozitiv răspunde doar pentru o notă din
   `vault_folder` al vreunui proiect (exact ce deschide butonul Wiki din Torqa: lista vine de la
   `/api/proiecte/<id>/wiki`); orice altceva e **403**, la fel dacă nota există sau nu (403 vs 404 nu arată ce
   fișiere are vault-ul). `PUT` (și POST/DELETE/PATCH) pe rută e refuzat dispozitivului cu **401**, ca restul listei.
   Regula e una singură, pe metodă: `utils.device_token_denied` (`DEVICE_TOKEN_DENIED` = refuzat cu totul,
   `DEVICE_TOKEN_READ_ONLY` = doar citire). Comparația nota–dosar e pe căi reale (`..`, legături simbolice, un dosar frate
   cu același prefix nu trec); un `vault_folder` absent din vault sau care arată spre rădăcină nu deschide nimic; dosarele
   ascunse (`.trash`, `.git`...) rămân închise, ca în lista Wiki. Tokenul de mașină și sesiunea cu PIN nu se schimbă.
2. **Rute anonime scoase.** `POST /api/import-abb-multi/preview` și `/api/import-archive/preview` (fără login, rămase de
   la `/calc`) pleacă, cu helperii lor din `projects.py`, cu tot `scripts/parse_params/` (singurul importator al
   `abb` și `siemens_starter` era `projects.py`; `danfoss`, `lenze`, `siemens` nu erau importate de nimeni) și cu
   `pdfplumber`. `test_retragere` le ține la 404 și are un gardian: nicio rută `/api` nu răspunde fără credențiale în
   afară de `healthz`.
3. **IP-ul clientului.** `_client_ip()` credea `CF-Connecting-IP` de la oricine, iar `ProxyFix` crede `X-Forwarded-For` la
   fel; limita de logare (5 / 5 min / IP) se ținea pe asta. Acum antetele contează doar dacă **socketul** (citit din
   `werkzeug.proxy_fix.orig`, nu din `remote_addr`, pe care ProxyFix îl rescrie) e al unui proxy de încredere: implicit
   loopback (acolo se conectează cloudflared), un socket UNIX (gunicorn legat pe unix:...), sau ce scrie în
   `PIF_TRUSTED_PROXIES`. Orice altceva e identificat prin adresa socketului. **Ce nu se știe din depozit:** adresa pe care
   ascultă gunicorn și de unde se conectează cloudflared stau în unitatea systemd de pe server, nu în repo; în cod
   există doar `ProxyFix(x_for=1, x_proto=1)`. Dacă după deploy toate cererile din tunel apar cu aceeași adresă în
   `logs/app.log`, cloudflared nu ajunge pe loopback și adresa lui se adaugă în `PIF_TRUSTED_PROXIES`.
4. **APK.** `POST /api/app/upload` fără `canal` dă 400 (înainte ateriza pe canalul retras `pif`); citirea fără `canal`
   rămâne pe `pif`, pentru aplicația veche încă instalată.
5. **Rute fără apelant scoase:** `/api/clienti*` (5), `/api/agenda/*` (3), `/api/search`, `/api/export/pdf` (tabelul de
   taskuri era decalat din v34) și `reportlab`. Rămân `/api/stats`, `/api/import/debrief`, `/api/obsidian/vault-key` și
   `vault-sync`, sănătatea. Tabela `clienti` rămâne vie (o scrie importul de debrief, o citește snapshotul). Verificat prin
   grep în depozit, în sursa Torqa, în uneltele vault-ului și în pașii skill-urilor: singurele mențiuni sunt două pagini
   de documentație din vault (`wiki/job/pif-dashboard.md`, `.claude/skills/proiect/pif-dashboard/MOD.md`), care listează
   rutele ca tabel, nu le cheamă. `test_suite` nu mai sondează rutele scoase: regula „proiect închis" și sfera se citesc
   acum din `/api/sync/snapshot` (`viu`, `sfera`) și din `/api/calendar`.
6. **CSP implicit** (tot ce nu e `/torqa/`): fără surse externe (CDN-uri, Google Fonts, `query1.finance.yahoo.com`,
   `img-src https:` pleacă) și fără `unsafe-inline`; `script-src` și `style-src` cer nonce-ul cererii, pe care acum îl
   poartă și antetul, nu doar șablonul. Pentru asta `login.html` nu mai are `onsubmit` (formularul se leagă din script)
   și nici `style="display:none"` (o clasă), iar `/admin/db-upload` își ia nonce pentru `<style>` și `<script>`.
   `test_csp` scanează paginile randate după handlere și stiluri inline. Mai departe: excepția CSRF pentru
   `push.push_action` și docstring-ul „SPA" din `csrf.py`; `flask-compress`, `pyyaml`, `pymupdf` și `openpyxl` din
   `requirements.txt` (nu le importa nimic; `test_cerinte` ține lista și importurile la fel în ambele sensuri);
   comentariile învechite din `login.html`/`login.css`/`labels.py`/`obsidian.py`/`sync.py`/`app_update.py`/`sync_db_from_server.sh`.
7. **Restore.** INSERT-urile de mână enumerau coloanele, deci tot ce s-a adăugat după ele se exporta și nu se mai punea
   înapoi: `proiecte.data_finalizare`, `vault_folder`, `notify_on_complete`; `global_tasks.ora`; `tasks.data_start`,
   `progres`, `is_milestone` (un proiect închis își pierdea ziua închiderii, deci Calendar tăia perioadele la „azi").
   Acum coloanele vin din `PRAGMA table_info`. **Formatul backup-ului nu s-a schimbat**, deci un backup făcut înainte de
   azi se restaurează: coloana care lipsește din rând ia valoarea implicită a coloanei, coloana pe care tabela nu o mai
   are se ignoră, `data_planificata` devine termen unde termenul lipsește, tabelele dispărute nu se citesc, `push_*` al
   mașinii se păstrează. `test_backup_restore` umple FIECARE coloană a FIECĂREI tabele din schemă cu o valoare diferită
   de cea implicită, face backup, restaurează într-o bază nouă și compară tot; o coloană viitoare intră singură.

## Ce a rămas, deschis

- **Închis după revizie: dispozitivul nu-și mai poate lărgi singur citirea.** Putea scrie `vault_folder` pe un proiect
  (`PUT /api/proiecte/<id>`, `POST /api/proiecte`, `POST /api/import/debrief`) și apoi citi orice dosar prin ruta Wiki
  (verificat cu o probă locală). Torqa nu trimite niciodată `vault_folder`, deci câmpul se refuză acum tokenului de
  dispozitiv cu 403, pe toate trei rutele (`utils.refuse_device_token_fields`); tokenul de mașină (`pif-sync.py link`)
  și sesiunea cu PIN îl scriu ca înainte. Testele din `teste/test_sync.py` pică fără regulă.
- **Închis după revizie: `/admin/db-upload` cu sesiunea de PIN.** `fetch`-ul paginii și `scripts/upload_db.py`
  trimit acum `X-CSRF-Token` din cookie (scriptul și `User-Agent: Cowork-PIF/1.0`, fără de care Cloudflare dă 1010).
- **Închis după revizie: `app_settings`.** Migrarea v42 șterge `push_*`, `plan_departament_url`, `ics_feed_key` și
  `fault_data_rev`, pe care nu le mai citește niciun cod.
- **Închis după revizie: documentația din vault** nu mai listează rutele scoase (Knowledge `c897353`).

## După revizie: cele 6 puncte (Ion, 2026-10-03: „Fă cele 6 puncte”)

Pe lângă `app_settings` și `/admin/db-upload` de mai sus:

- **Canalul APK `pif` a plecat.** Aplicația veche (`org.iupif.pif`) se dezinstalează; `torqa` e singurul canal, iar
  `canal` e obligatoriu și la citire (fără el, 400). Fișierele vechi din `uploads/app/` (`pif.apk`, `meta.json`)
  nu se mai servesc; nu le șterge codul.
- **`private_docs/` (11 MB), `manuals/` (69 MB) și `static/docs/` (6,4 MB) au ieșit din depozit**, care e public:
  motivul lor, calculatorul, a plecat. Rămân în istoricul git; copiile locale sunt în `.gitignore`.

## Cum se aduce înapoi

Fiecare punct e un commit separat pe ramura `curatare`; `git revert <commit>`. Starea de dinainte de toată curățenia
e `0fe1d2aa`; starea cu interfața veche, eticheta `inainte-de-retragere`.
