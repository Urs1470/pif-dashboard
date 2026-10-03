# 2026-10-03 — Retragerea interfeței vechi: serverul rămâne doar backend-ul Torqa

**Context.** Torqa (build propriu din Super Productivity v19.1.0) a preluat tot ce folosește Ion:
proiecte, taskuri, perioade, calendar, wiki, sincronizare, pe web (`/torqa/`) și pe Android
(`org.iupif.torqa`). Interfața veche — SPA-ul Svelte 5, calculatorul public `/calc`, planul de
departament, notificările push și aplicația Android `org.iupif.pif` (un WebView peste site) — nu
mai avea cine s-o folosească, dar continua să fie întreținută, păzită de o poartă întreagă
(build, `smoke_ui`, audituri cu Chromium) și servită. Ion a aprobat retragerea pe 2026-10-03,
după un backup complet: baza de date și exportul JSON, în Drive (calea e în mesajul etichetei,
`git tag -n inainte-de-retragere`). Starea de dinainte e eticheta adnotată **`inainte-de-retragere`**
(commitul `2ce03f9e`), pe origin.

**Ce s-a decis.** Serverul devine API-ul, loginul cu PIN și Torqa web la `/torqa/`. Nimic altceva.

1. **SPA-ul și build-ul lui pleacă.** `frontend/` (sursa Svelte, proiectul Capacitor `android/` al
   aplicației `org.iupif.pif`, pachetele npm) și `static/dist/` (build-ul, care stătea în git fiindcă
   serverul n-are npm). Rutele din `app.py` care îl serveau — `/` (shell-ul), `/assets/<fișier>`,
   `/favicon.svg`, `/manifest.json`, `/icon-<mărime>.png` — dau 404, cu o excepție: **`/` duce
   acum la `/torqa/`** (302, fără sesiune; `/torqa/` își cere singur sesiunea și trimite la
   `/login?next=/torqa/`).
2. **Calculatorul pleacă.** `/calc` (varianta publică, fără login, făcută ca să fie împărțită cu echipa —
   linkul dat colegilor dă de acum 404), `/api/me` (îl chema doar `/calc`, ca să arate extrasele de carte celor logați),
   `/docs/<fișier>` și vizualizatorul PDF.js din `static/pdfjs/` (cu CSP-ul lui dedicat); singurul lor
   consumator era `driveCalc.js`. Extrasele din `private_docs/` rămân în disc și în git, ca date.
3. **Planul de departament pleacă:** `GET`/`PUT /api/settings/plan-departament`, constantele din
   `utils.py` și `frame-src` din CSP-ul implicit.
4. **Notificările push pleacă:** `blueprints/push.py` (9 rute, planificatorul de 08:00 și cel al orelor
   exacte, cheia VAPID), înregistrarea lui în `app.py`, `pywebpush` și `cryptography` din
   `requirements.txt` (a doua venea tranzitiv prin pdfplumber, o fixasem doar pentru push).
5. **Service worker-ul vechi e înlocuit cu unul care se retrage singur** (`static/service-worker.js`,
   servit tot la `/service-worker.js`). Un fișier șters nu retrage nimic: la verificarea de
   actualizare browserul primește 404 și păstrează worker-ul vechi, cu shell-ul vechi din cache. Noul
   worker nu are handler de `fetch` (nu poate servi nimic din Torqa, nici API-ul lui), la `install` își
   ia locul imediat, iar la `activate` șterge cache-urile dashboardului vechi (`pif-static-`, `pif-api-`,
   `torqa-static-`, `torqa-api-`, niciodată `ngsw:`), se dezînregistrează și reîncarcă ferestrele pe care
   le controla, în afară de cele de sub `/torqa/`. Browserul îl găsește la prima verificare (la
   navigare, cel mult o dată la 24 de ore; SPA-ul vechi cerea și singur, la 15 minute).
6. **Uneltele care serveau doar SPA-ul și APK-ul vechi pleacă:** `scripts/build-apk.ps1`,
   `setup-apk-toolchain.ps1`, `gen_icons.py`, `figma_tokens.py`, `solve_paleta.py`, `lint_svelte.mjs`,
   `smoke_ui.py`, cele opt `audit_*` (șase cu browser, plus design și contrast), `filmstrip.py`, `filmeaza_pornirea.py`,
   `aparat.py`, `masoara_*.py`, `proba_mobil.py`, regulile din `.claude/rules/design.md`, macheta
   `ContorPasi.dc.html` (lega `frontend/src/styles/tokens.css`), `.gitattributes` (doar regulile pentru
   `static/dist/`). Cheia release a APK-urilor stă în afara repo-ului și o folosește acum Torqa: nu s-a atins.
7. **Verificatoarele rămân patru, toate fără browser și fără build:** lint Python (pyflakes), testele
   JS ale fișierelor pe care le servește serverul (`templates/login.html`, `static/service-worker.js`;
   mutate din `frontend/src/lib/` în `teste/js/`, rulate cu `node --test`, fără npm), `unittest` și probele
   de API. `scripts/banc.py` păstrează serverul de unică folosință, raportul și codurile de ieșire;
   Playwright, contextul de telefon și degetul au plecat. `.githooks/pre-commit` nu mai cere bump de
   `VERSION` pentru `static/dist/` (nu mai există). `test_retragere` ține la 404 tot ce a plecat.

**Ce a rămas, și de ce.**

- **Baza de date, neatinsă** (schema v41, fără migrare). Rămân fără cititor `push_*` din `app_settings`
  (cheia VAPID *privată*, abonamentele, setările) și `plan_departament_url`. `/api/backup` exclude
  `push_*` (`CHEI_PROTEJATE`), iar `test_suite` păzește asta; `/api/admin/db-dump` e baza brută. Tabela
  `calcule` rămâne: o citește `/api/proiecte/<id>/snapshot`.
- **Tot API-ul pe care îl folosește Torqa sau un skill** (proiecte, taskuri, taskuri globale,
  subtaskuri, perioade, calendar, snapshot, wiki și note Obsidian, export PDF, import debrief,
  versiune/APK/upload, `/api/sync/snapshot`, `/api/torqa/web/upload`), plus backup/restore, `/api/deploy`
  și webhook-ul. Skill-urile mai cheamă `/api/search`, `/api/agenda/*` și `/api/stats`: rămân.
- **Rute fără consumator găsit, păstrate** fiindcă nu s-a putut dovedi că nu le citește nimeni:
  `/api/clienti*` (5), `/api/import-abb-multi/preview`, `/api/import-archive/preview`.
- **Neatinse, pe regula „nu atinge”:** `csrf.py` (mai are excepția pentru `push.push_action`, endpoint
  inexistent acum), `blueprints/app_update.py` (canalul `pif`, al aplicației vechi, rămâne servit),
  `blueprints/torqa_web.py`, `blueprints/sync.py`, pagina `/login` cu `templates/login.html` și
  `static/login.css` (ale căror comentarii mai pomenesc `frontend/src/...`).
- **Date care nu țin de interfață:** `private_docs/`, `static/docs/` (două ghiduri ABB, cerute doar de
  calculator; rămân accesibile public la `/static/docs/...`), `manuals/` (parserele de parametri),
  `static/fonts/` (login-ul folosește 3 din 8 fișiere), `design/`, `docs/CALCULATOR_SURSE.md`,
  `docs/mochete/`. Istoria deciziilor (`docs/decizii/`) rămâne întreagă.
- **CSP-ul implicit** (login, API, erori) mai listează CDN-uri și `query1.finance.yahoo.com` din vremea
  SPA-ului: nu s-a strâns, nu era în cerere.

**Cum se aduce înapoi.**

- **Doar să vezi sau să rulezi starea veche:** `git switch -c interfata-veche inainte-de-retragere`
  (codul, `frontend/` și `static/dist/` construit; `npm ci` în `frontend/` pentru dezvoltare). Webhook-ul
  deployează doar `master`, deci pentru producție restaurarea trece prin master.
- **Pe master:** `git log --oneline inainte-de-retragere..master` dă commiturile; cele ale retragerii se
  anulează cu `git revert` (de la cel mai nou la cel mai vechi). Un `git checkout inainte-de-retragere --
  <cale>` aduce doar o bucată (SPA-ul, push-ul și `/calc` se țin de rute, CSP, chei din `app_settings` și
  hook-ul de pre-commit), nu interfața. La un revert, șterge odată cu ea `teste/test_retragere.py`.
- **Baza:** nu s-a schimbat, deci build-ul vechi merge pe ea cum e. Dacă totuși se pierde, backup-ul din
  Drive se pune înapoi: fișierul bazei prin `/admin/db-upload`, exportul JSON prin `POST /api/restore`.
- **Browserele care au scăpat deja de worker-ul vechi** îl primesc iar de la sine: SPA-ul restaurat își
  înregistrează `/service-worker.js` la fiecare încărcare.
- **Android:** `org.iupif.pif` se reface din etichetă cu `scripts/build-apk.ps1` (cheia e în afara repo-ului).

**Verificat.**

- `python scripts/verifica.py --rapid`: lint, `unitare_js` (19 teste), `unitare_py`, `test_suite` — curate.
- Două servere locale, pe baze noi de unică folosință, commitul de bază și codul nou, aceeași secvență de 44 de cereri
  (login, tokenuri de mașină și de dispozitiv, proiecte, taskuri, subtaskuri, perioade, taskuri globale, snapshot,
  calendar, export PDF, import debrief, `/api/app/*`, căutare, agendă, stats, backup): aceleași coduri și aceeași formă
  a răspunsului la toate 44. Diferă, cum trebuia, doar ce a plecat: `/` → 302 `/torqa/`; `/calc`, `/manifest.json`,
  `/favicon.svg`, `/icon-192.png`, `/static/pdfjs/...`, `/api/me`, `/api/push/*`, `/api/settings/plan-departament` → 404.
- **Într-un Chromium real**, cu worker-ul vechi (v284) înregistrat, două servere pe aceeași origine și aceeași
  bază (vechi, apoi nou) și `registration.update()` din pagină: în ~1 s fereastra SPA-ului ajunge la `/torqa/`,
  înregistrarea `/` dispare, cele două cache-uri vechi se șterg, `ngsw:` și un cache străin rămân, un worker de
  scope `/torqa/` rămâne activ, două file `/torqa/` deschise nu sunt atinse. Două lucruri neașteptate: `navigate()`
  reîncarcă și cu fragment în adresă, iar `client.url` are fragment doar dacă documentul a fost *creat* cu el; fragmentul
  contează totuși, fiindcă redirectul de la `/` îl păstrează (`/torqa/#/tasks`), deci worker-ul navighează fără el.
  Verificarea s-a făcut o dată, cu scripturi din afara repo-ului (browserul nu mai are loc în verificatoare).
- **Neverificat:** aplicația `org.iupif.pif` pe telefon (deducție: WebView-ul ei deschide `/`, deci ajunge la Torqa web);
  Torqa web real, cu `ngsw-worker.js` (s-a folosit un build de probă).
