# 2026-10-01 — Torqa web pe același server și canal propriu pentru APK-ul Torqa

**Context.** Torqa e build-ul privat al lui Ion din Super Productivity v19.1.0 (Angular, PWA; pe
Android, `org.iupif.torqa`). Decizia din aceeași zi (`2026-10-01-torqa-imagine-si-token-dispozitiv.md`)
i-a dat imaginea completă a datelor și tokenul de dispozitiv. Aici: build-ul web stă pe același
server, la `pif.iupif.org/torqa/`, fără alt serviciu de întreținut, iar APK-ul Torqa primește
propriul canal de actualizare. Ion a cerut să se termine „și web, și APK”, cu deciziile delegate.
Datele rămân în `/api/*` (aceeași sesiune, același CSRF): pagina doar se găzduiește.

**Ce s-a decis.**

1. **Build-ul web se urcă, nu stă în git.** Un build are 705 fișiere și 21 MB (8 MB în zip), sau 1234
   și 50 MB cu source map-uri, cu nume hash-uite care se schimbă la fiecare compilare. În istoric ar
   rămâne pentru totdeauna, iar serverul nu are npm ca să-l refacă (`CLAUDE.md` § Mediu): același
   raționament ca la APK (`blueprints/app_update.py`). Se urcă la `POST /api/torqa/web/upload`
   (`blueprints/torqa_web.py`): zip cu **conținutul** folderului `browser`, câmpul `zip`, doar Bearer
   `PIF_API_TOKEN`. Fără sesiune, iar `PIF_DEVICE_TOKEN` e refuzat (prefixul `/api/torqa/web/` în
   `DEVICE_TOKEN_DENIED`): ruta înlocuiește cod care rulează în browserul lui Ion, pe domeniul
   dashboardului, deci un telefon pierdut nu are voie s-o apeleze. Se respinge, cu 400 (413 la
   mărime) și fără să atingă versiunea live: ce nu începe cu `PK\x03\x04`; peste 80 MB comprimat
   (sub plafonul de 100 MB al planului gratuit Cloudflare), peste 300 MB descomprimat sau 5000 de
   intrări; căi absolute, cu `..`, cu `:` sau cu `\` care ies din director (zip-slip); legături
   simbolice și alte fișiere speciale; intrări criptate; nume duplicate sau care sunt și fișier,
   și director; lipsa `index.html` din rădăcină (mesajul spune că zip-ul se face din conținutul lui
   `browser`, nu din folder). Separatorii `\` din numele intrărilor se normalizează, fiindcă
   unele unelte Windows îi scriu așa.

2. **Versiuni și schimbare atomică.** Fiecare urcare se extrage în `uploads/torqa-web/<id>/`
   (`<an><lună><zi>T<oră>-<microsecunde>`, UTC, deci ordinea lexicografică e cea cronologică), iar
   abia apoi pointerul `uploads/torqa-web/current` se rescrie cu `os.replace`: o cerere vede ori
   tot build-ul vechi, ori tot pe cel nou. Rămân live + 2 anterioare; restul se șterg. Întoarcerea la
   o versiune: `printf '<id>' > uploads/torqa-web/current` (fără repornire; ids: `ls
   uploads/torqa-web`). Id-ul e **strict mai mare** decât orice versiune de pe disc: ceasul singur nu
   garantează asta (unul cu rezoluție grosieră dă același id la două urcări apropiate, unul dat înapoi
   dă unei versiuni noi un id mai mic decât al uneia vechi, iar tăierea depinde de ordine), iar două
   urcări simultane care aleg același id se rezolvă prin reîncercare. `uploads/` e gitignored, deci
   deploy-ul (`git reset --hard`) nu atinge versiunile. Nu intră în backup: build-ul se reface din
   repo-ul Torqa.

3. **Documentul cere sesiune, fișierele nu.** `/torqa/`, `index.html` și orice cale fără extensie
   (rutele aplicației) cer sesiune de dashboard; fără ea, redirect la `/login?next=/torqa/`
   (și înainte de pagina „neinstalat”). Fișierele (JS, CSS, fonturi, imagini, `ngsw*`, manifest) se dau
   fără login: nu conțin date, iar browserul și service worker-ul Angular le descarcă singure, în
   fundal, fără o pagină în față care să te trimită la PIN. Un fișier care lipsește dă 404, nu
   documentul (un chunk lipsă răspuns cu HTML ajunge în browser ca JavaScript stricat); o cale în
   afara versiunii nu se servește niciodată (`safe_join`, apoi `realpath`, apoi doar fișiere
   obișnuite). Fără nicio versiune urcată: 503 simplu, „Torqa web nu este instalat încă”.
   **Limita, spusă:** poarta de PIN pe document nu protejează date. După prima încărcare,
   service worker-ul Angular servește `index.html` din cache fără să întrebe serverul. Datele sunt
   protejate de `/api/*`; pagina din cache, cu sesiunea expirată, primește 401 și **Torqa trebuie să
   ducă utilizatorul la `/login?next=/torqa/`** la un 401 (în caz contrar rămâne blocat pe o pagină
   fără date).

4. **Fișierele nu ating sesiunea.** Sesiunea lui Flask e permanentă și se reînnoiește la fiecare
   răspuns, iar `csrf.py` scrie `csrf_token` pe fiecare răspuns autentificat. Pe un fișier static
   ar ieși un `Set-Cookie` nou și `Vary: Cookie`, iar un `Vary: Cookie` cu un cookie care se
   schimbă la fiecare cerere face ca browserul să nu refolosească niciodată fișierul din cache, oricât
   de lung ar fi `max-age` (raționament după RFC 9111; comportamentul browserului nu l-am măsurat).
   `SesiuneFaraStatice` (în `torqa_web.py`, instalat în `app.py`) dă cererii `/torqa/<fișier cu
   extensie>` o sesiune goală și nu scrie nimic înapoi; orice altă cerere merge ca înainte. Cache:
   `index.html`, `ngsw.json`, `ngsw-worker.js`, `manifest.json` → `no-cache`; bundle-urile cu hash
   în nume (`main-XXXXXXXX.js`, `chunk-…`, `styles-…`, `media/…`) → `public, max-age=31536000,
   immutable`; restul, inclusiv tot ce e sub `assets/` (Angular nu-l hash-uiește), → `no-cache` cu ETag
   (304 ieftin). Tipurile MIME sunt într-un tabel al nostru, nu din sistem: pe un Linux fără
   `mime.types`, un `.mjs` sau `.webmanifest` ar ieși `octet-stream`, iar cu `nosniff` un modul
   cu tip greșit nu se execută.

5. **CSP propriu pe `/torqa/`** (ca cel de la `/static/pdfjs/`, în `after_request`):
   `default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self'
   'unsafe-inline'; img-src 'self' data: blob:; object-src 'none'; form-action 'self'; frame-ancestors
   'none'; base-uri 'self'`. Găsit empiric, cu Chromium headless pe build-ul real (serverul real, baza
   de unică folosință, build-ul urcat prin ruta reală; parcurs: login → prima pagină → „Simple Todo
   List” → un task adăugat și bifat → 11 rute → panoul de detalii → 8 rute de pluginuri → setări), scoțând
   pe rând fiecare element. Fără `'unsafe-eval'`: 9 încălcări și 3 erori de pagină (runtime-ul de
   pluginuri rulează cod prin `new Function`, `src/app/plugins/plugin-runner.ts`); fără
   `'unsafe-inline'` la scripturi: 2 (bootstrap-ul inline din `index.html` și handlerul
   `onload="this.media='all'"` care aprinde CSS-ul); fără `'unsafe-inline'` la stiluri: 212 (Angular
   Material). `data:` și `blob:` la imagini **nu** apar în parcurs, dar le cere codul (imaginile lipite în
   note devin `blob:` în `core/clipboard-image/clipboard-image.service.ts`; kit-ul de UI al
   pluginurilor are un `url(data:image/svg+xml…)`). Restul (`connect-src`, `font-src`, `media-src`,
   `worker-src`, `frame-src`, `manifest-src`) cade pe `default-src 'self'` și nu a cerut nimic mai
   mult: API-ul e pe același domeniu, fonturile și sunetele vin din build, pluginurile își pun UI-ul
   în `iframe srcdoc` (nu intră sub `frame-src`). **Rămân blocate, intenționat:** integrările externe
   ale Super Productivity (Jira, CalDAV, Dropbox, SuperSync, WebDAV) și un worker `blob:` (`fflate`,
   la instalarea unui plugin dintr-un zip). Dacă o funcție nu mai merge, consola spune `Refused to
   …`: se adaugă exact acel element, nu un `https:` oarecare. Meta-ul CSP din `index.html` e și mai
   larg (`default-src *`); cele două politici se intersectează, deci contează antetul nostru.
   `unsafe-eval` și `unsafe-inline` sunt ale aplicației, nu o alegere de aici (comentariul din
   `index.html` spune același lucru); pe același domeniu cu dashboardul, un XSS în Torqa ar putea
   apela `/api/*` cu sesiunea lui Ion, la fel ca la `unsafe-inline` din dashboard — risc asumat,
   pentru o unealtă personală.

6. **Service worker-ul dashboardului lasă Torqa în pace** (`static/service-worker.js`, VERSION
   v283 → v284). Scope-ul lui e `/`, al lui Angular `/torqa/`; fără reguli, cel al dashboardului ar
   prinde navigarea LA `/torqa/` (la prima vizită, până se instalează al lui Angular), ar pune în cache
   documentul și răspunsurile API cerute de pagină și le-ar da înapoi când cade rețeaua. Acum: nu
   răspunde la `/torqa` și `/torqa/*` și la nicio cerere cu antetul `X-Torqa` (Torqa îl pune pe
   apelurile lui de API); la `activate` nu mai șterge cache-urile `ngsw:` ale lui Angular; la apăsarea
   pe o notificare nu mai aduce în față o fereastră Torqa (n-ar înțelege `NAVIGHEAZA`). **Cea de a
   doua regulă a fost găsită de verificare, nu gândită dinainte:** `activate` ștergea orice cache care
   nu era al lui, deci la fiecare deploy cu VERSION urcat dispăreau toate cache-urile Torqa web
   (12 la build-ul de probă), adică Torqa web nu mai pornea offline până la următoarea conectare.
   Același parcurs în browser, făcut cu service worker-ul vechi (`git show HEAD:static/service-worker.js`):
   `/torqa/` ajungea în `torqa-static-v283` și, după activarea versiunii următoare, `ngsw:` dispărea;
   cu cel nou nu ajunge nimic din Torqa în cache-urile dashboardului și toate cele 12 `ngsw:` rămân.

7. **Întoarcerea după login.** `/login?next=/torqa/` duce la `/torqa/` după PIN. `next` e acceptat
   doar ca cale a acestui site (`utils.safe_next_url`): un singur `/` la început, doar ASCII
   tipăribil, fără `\` (browserul îl citește ca `/`), fără tab/newline (browserul le scoate din URL,
   deci `/<tab>/host` devine `//host`), cel mult 2048 de caractere; orice altceva → `/`. Regula e în
   două locuri, la server și în `destinatie()` din `templates/login.html`, și un test le rulează pe
   aceleași intrări. Serverul decide: `POST /login` răspunde `{success, next}` (câmp nou, cele vechi
   neschimbate), iar pagina validează încă o dată ce primește. Un utilizator deja autentificat care
   deschide `/login?next=…` e redirectat la destinație.

8. **Canale pentru APK** (`blueprints/app_update.py`). `canal` pe rutele existente: câmp de formular
   la `POST /api/app/upload`, parametru de query la `GET /api/app/version` și `GET /api/app/apk`.
   `pif` (implicit: un apel fără `canal` face exact ce făcea, cu aceleași fișiere `uploads/app/pif.apk`
   + `meta.json`, același răspuns, același nume `pif-<versiune>.apk`) și `torqa` (`uploads/app/
   torqa.apk` + `torqa-meta.json`, nume `torqa-<versiune>.apk`). O valoare necunoscută dă 400, **și una
   goală**: o variabilă nesetată în scriptul de build nu are voie să cadă pe canalul implicit și să
   suprascrie aplicația veche cu cea nouă. Numele se normalizează (`strip`, minuscule). Tokenul de
   dispozitiv rămâne refuzat la urcare pe ambele canale, dar citește (Torqa nativ își verifică
   versiunea cu el).

9. **`<base href>` se verifică la urcare.** Build-ul se face cu `--base-href /torqa/`; altfel tot ce
   e relativ (fișiere, rute, service worker) se rezolvă greșit și pagina iese albă fără nicio eroare
   la urcare. S-a și întâmplat, la primul build de probă: în Git Bash, `/torqa/` e rescris de MSYS într-o
   cale de Windows (`C:/Users/…/Git/torqa/`), iar `index.html` și `ngsw.json` au ieșit cu ea. Un
   `<base>` diferit de `/torqa/` se respinge, cu leacul în mesaj (`MSYS_NO_PATHCONV=1` în Git Bash sau
   PowerShell); unul lipsă trece, cu un avertisment în răspuns (`warnings`).

**Capcane găsite.**

- `sync-config.service.ts:215` (`src/app/imex/sync/`) cere `fetch('/assets/sync-config-default-override.json')`,
  cu `/` la început, deci în afara `<base>`: lovește `/assets/` al dashboardului și primește 404 la
  fiecare pornire. Aplicația îl tolerează; trebuie corectat în Torqa (cale relativă), nu aici.
- Un zip făcut cu `Compress-Archive` din Windows PowerShell 5.1 poate avea `\` în nume: serverul le
  normalizează. Un zip făcut din folderul `browser` (nu din conținutul lui) e respins cu mesaj.
- Configurația gunicorn de pe server (timeout, workeri) nu e în repo. O urcare lentă a unui zip de
  16 MB poate trece de timeout-ul implicit de 30 s al unui worker sincron; zip-ul fără `*.map` are ~8 MB
  (nu sunt necesare la rulare: `ngsw.json` nu le listează).

**Cum se publică** (tokenul vine din mediu, niciodată scris în comandă; în PowerShell, `curl.exe` și
`$env:PIF_API_TOKEN`; `-A` pune același User-Agent ca `scripts/build-apk.ps1`, ca să nu-l taie
Cloudflare). Comenzile de mai jos au rulat identic, cu `curl` din Git Bash, pe un server de probă:

```
# 1. Build-ul Angular cu --base-href /torqa/ (în Git Bash: MSYS_NO_PATHCONV=1 în fața comenzii),
#    apoi zip cu CONTINUTUL lui `browser` (index.html la rădăcină).
# 2. Urcarea:
curl -sS -A "Cowork-PIF/1.0" -H "Authorization: Bearer $PIF_API_TOKEN" \
  -F "zip=@torqa-web.zip;type=application/zip" \
  -w "\nHTTP %{http_code}\n" https://pif.iupif.org/api/torqa/web/upload
# răspuns: {ok, version, files, size, zip_size, at, kept, warnings}; deschis la https://pif.iupif.org/torqa/

# APK Torqa (versionCode/versionName se citesc din APK, cu aapt2 dump badging, ca în build-apk.ps1):
curl -sS -A "Cowork-PIF/1.0" -H "Authorization: Bearer $PIF_API_TOKEN" \
  -F "canal=torqa" -F "versionCode=<N>" -F "versionName=<X.Y.Z>" -F "notes=<text>" \
  -F "apk=@torqa-release.apk;type=application/vnd.android.package-archive" \
  -w "\nHTTP %{http_code}\n" https://pif.iupif.org/api/app/upload
# citire (aplicația Torqa, cu tokenul de dispozitiv):
#   GET /api/app/version?canal=torqa    GET /api/app/apk?canal=torqa
```

**Verificat** (2026-10-01, pe worktree-ul `torqa-web`; nimic pe serverul real).

- `teste/` (unittest): 56 → 168 de teste verzi (3 sărite, ca înainte: `pywebpush` lipsește pe mașina asta).
  Fișiere noi: `test_app_update.py` (canale, compatibilitate), `test_torqa_web.py` (urcare respinsă și
  acceptată, schimbare atomică, retenție, servire, cache, MIME, sesiune pe fișiere, traversare, CSP, CSRF),
  `test_login_next.py`, ajutorul `_aplicatia.py`. În `frontend/src/lib/`: `service-worker.test.js` și
  `login.test.js` (7 + 7) rulează scripturile reale, în `vm`. Total `npm test`: 102 verzi.
  `scripts/verifica.py --rapid`: 6 pași curați în 62 s; `--atinse` pe fișierele atinse (lint, unitare_js,
  unitare_py, test_suite, smoke_ui): 5 pași curați în 101 s.
- Mutații (câte o stricare a codului, pe o copie a arborelui): 59 în serverul Python (zip-slip, plafoane,
  garda de token, retenție, pointer, id-uri, login, `next`, sesiune, CSP, CSRF, canale APK), toate duc la cel
  puțin un test picat, în afară de una echivalentă (scoaterea doar a lui `safe_join`: `realpath` oprește
  singur traversarea, iar scoase amândouă pică); 6 în service worker și 9 în scriptul de login, toate
  prinse. Cele nedetectate la prima trecere au adus teste noi: plafonul din `_extrage`, mesajul semnăturii
  `PK`, un pointer spre un director din afară, jonctiune/legătură simbolică, id-urile pe ceas grosier sau dat
  înapoi, reîncercarea la `PermissionError`.
- APK fără `canal`: același modul din `git HEAD` și cel curent, pe aceleași cereri (urcare, versiune,
  descărcare, cinci feluri de eroare): răspunsuri, antete, corpuri și fișiere scrise identice pe octeți
  (în afară de ceasul `at`).
- Browser (Chromium headless, serverul real pe baza de unică folosință, build-ul real de 1234 de fișiere,
  50.374.988 B, zip 15.866.525 B, urcat prin `POST /api/torqa/web/upload`): anonim `/torqa/` →
  `/login?next=/torqa/` → PIN → înapoi la `/torqa/`; prima pagină („How do you want to use Torqa?”) și
  aplicația întreagă desenate; 292 de cereri la pornire, toate pe același domeniu; **0 încălcări CSP, 0
  erori de pagină, 0 cereri eșuate** pe tot parcursul de la punctul 5; singura eroare din consolă e 404-ul de
  la `sync-config-default-override.json` (capcana de mai sus). Din pagina `/torqa/`: `csrf_token` e
  citibil din JavaScript, iar POST/PUT/DELETE cu `X-CSRF-Token` și `X-Torqa` dau 201/200/200, fără antet
  403, cu datele schimbate pe server. Cu service worker-ele active, cel al dashboardului și Angular
  coexistă (scope `/` și `/torqa/`), iar parcursul de la punctul 6 dă rezultatele descrise acolo.
- Comenzile `curl` de mai sus, rulate identic cu tokenul din mediu pe serverul de probă: urcarea web
  (HTTP 200, 1234 de fișiere), urcarea APK cu `canal=torqa` (200), citirea ambelor canale, 400 la un canal
  necunoscut, `torqa-1.0.0.apk` la descărcare, `/torqa/` anonim → 302 la login.

**Neverificat.** Nimic pe serverul de producție (rutele, Cloudflare, plafonul de 100 MB, timeout-ul
gunicorn, versiunea de Python de acolo; sintaxa e verificată doar pentru 3.8+). Calea de actualizare a lui
`ngsw` între două versiuni urcate una după alta. Comportamentul offline al Torqa web, instalarea ca PWA,
alte browsere decât Chromium. Funcțiile Torqa care nu apar în parcurs: imagini lipite în note, instalarea
unui plugin din zip, pluginurile cu UI (activate), sincronizarea (build-ul de probă nu face încă apeluri
`/api/*` de la sine). APK-ul Torqa nativ. Cele 3 teste `test_push` sărite.
