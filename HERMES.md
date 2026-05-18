# Pentru agenții care lucrează la PIF Dashboard (Claude paralele + Hermes)

> Document de briefing pentru ORICE agent care vine în repo. Citește-l până la capăt
> înainte de prima modificare. Audiența principală:
>
> - **Sesiunile Claude spawned** ce rulează în paralel pe laptop-ul Windows al lui Ion
>   în `D:/Projects/pif-dashboard` (PV generation, Import parametri, Equipment card,
>   Budget, etc.). Toate au identity git `Urs1470 <Urs1470@users.noreply.github.com>`.
> - **Claude main** — sesiunea principală a lui Ion, tot pe Windows, aceeași identity.
> - **Hermes** — agent MiniMax pe laptop-server `/home/ion-ursu/Projects/pif-dashboard`,
>   identity `Hermes <hermes@pif.iupif.org>`.
>
> Coliziunile de tip "lost work" pe `templates/`, `static/` apar **între sesiuni Claude
> paralele** care comit pe același worktree Windows cu aceeași identity. Hermes e
> izolat fizic pe alt host și are propria identity; coliziunea cu el e doar la
> nivel de webhook deploy (vezi gotcha-urile la final).

## Cine face ce

- **Ion** — single user al PIF Dashboard, owner repo, owner laptop-server care expune `https://pif.iupif.org` prin Cloudflare Tunnel. Git identity `Urs1470 <Urs1470@users.noreply.github.com>` (GitHub login).
- **Claude (în Claude Code, pe Windows-ul lui Ion, `D:\Projects\pif-dashboard`)** — face majoritatea modificărilor UI/UX, commit + push direct în repo de pe laptopul lui Ion. Auto-deploy webhook aduce schimbările pe laptop-server în ~5–10s.
- **Hermes (tu, MiniMax-M2.7-highspeed via gateway, user system `ion-ursu` pe laptop-server)** — rulezi LOCAL pe laptop-server, în același folder `/home/ion-ursu/Projects/pif-dashboard` ca aplicația. Faci sarcini grele cu costuri mari de tokeni: audit DB față de PDF, batch LLM pe explicații parametri. Git identity `Hermes <hermes@pif.iupif.org>`, SSH key `github_pif`.

Cei doi agenți trebuie să **NU se suprascrie** și să **NU lase fișiere orfane** pe vreuna din mașini.

---

## Stack și topologie

- **Repo**: `https://github.com/Urs1470/pif-dashboard` (private)
- **Worktree local Ion (Windows)**: `D:\Projects\pif-dashboard` — Claude lucrează aici
- **Laptop-server (Linux)**: `/home/ion-ursu/Projects/pif-dashboard` — Hermes lucrează aici **și** aplicația rulează din același folder
- **Service**: `pif-dashboard.service` (systemd, user `ion-ursu`), expus prin `cloudflared.service` la `https://pif.iupif.org/`
- **DB**: `/home/ion-ursu/Projects/pif-dashboard/pif_dashboard.db` (~41MB, **nu în repo**). Backup-uri în `backups/` și `backup-pre-budget-update/` — manuale sau via `backup_db.py`. Niciun cron automat.
- **Backend**: Flask + SQLite single-process, auth PIN (`pif2024` default, `PIF_DASHBOARD_PIN` env var override)
- **Frontend**:
  - Desktop: `templates/index.html` + `static/app.js`
  - Mobile (PWA, ruta `/m`): `templates/mobile.html` + `static/mobile.js`
  - Manifest separat: `static/manifest.json` (desktop, scope `/`) și `static/manifest-mobile.json` (`/m`)
- **Login**: `templates/login.html` (același pentru ambele)
- **Service worker**: `static/service-worker.js` — bump `CACHE_NAME`/`STATIC_CACHE`/`API_CACHE` versions când livrezi static assets noi
- **Auto-deploy**: endpoint `POST /webhook/deploy` în `app.py` (~linia 2616). Verifică `X-Hub-Signature-256` față de secret-ul din `.deploy_secret`, rulează `git pull origin master`, apoi `sudo systemctl restart pif-dashboard`. **NU pune `.deploy_secret` în repo.**
  - **Failure mode cunoscut**: dacă worktree-ul de pe server e dirty când webhook-ul lovește, `git pull` eșuează și endpoint-ul returnează 500. Push-urile ulterioare se acumulează pe GitHub fără să ajungă pe server. GitHub NU retrimite automat — trebuie pull manual sau redelivery din `Settings → Webhooks → Recent Deliveries`.

---

## Reguli stricte (NU le rupe)

### A. Workflow Git

1. **Înainte de orice modificare** rulează `git pull` și `git log --oneline -5` ca să vezi ultimul commit. Verifică dacă cineva (Claude) a făcut modificări recente la fișierele pe care vrei să le atingi. Dacă da, **integrează modificările lui** și nu refă din ce era înainte.
2. **Push imediat după modificare** — nu lăsa modificări locale ne-pushe-uite. Cu cât stai mai mult, cu atât crește riscul ca Claude să facă altă modificare suprapusă.
3. **NU edita direct pe Pi/laptop-server fără să commit-i în repo** — auto-deploy următor va suprascrie. Asta s-a întâmplat deja: `mobile.html` și `mobile.js` au trăit doar pe server săptămâni la rând și au fost recuperate dintr-un backup Telegram când Claude a vrut să le aducă în repo.
4. **Toate fișierele live trebuie să existe în repo**. Nu lăsa nimic orfan.
5. **Commit messages fără diacritice** (PowerShell se incurcă la `-m` cu `@'...'@`). Author-ul tău e deja `Hermes <hermes@pif.iupif.org>` din git config local — Ion vede direct în istoric pe `git log` cine a făcut commit-ul. Co-author opțional dacă vrei să marchezi colaborarea:
   ```
   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
   ```
   Claude folosește pattern-ul invers — author Ion (`Urs1470`), co-author Claude.

### B. Domeniu — cine atinge ce (CRITIC, citit cu atenție)

**Cele 3+ sesiuni rulează paralel pe același worktree.** A se vedea commit `245cf33` ("Restore PV button + pv-modal.js include in index.html (lost in 3e01a8a)") — un caz real de suprascriere între sesiuni. Protocolul mai jos previne asta.

#### Domain map

| Zonă | Owner |
|---|---|
| **PV generation**: `services/pv_generator.py`, `static/pv-modal.js`, `templates/pv/*.docx`, secțiunea PV din `app.py` | **Spawned-PV session** |
| **Import parametri**: `scripts/parse_params/*.py`, endpoint `/api/echipamente/<id>/import-params` în `app.py` | **Spawned-Import session** |
| **Audit PDF**: `scripts/audit_pdf.py`, `scripts/audit_reports/*`, parsers nestate | **Hermes** |
| **LLM batch** pe `parametri_master` (descrieri, explicații) | **Hermes** |
| **UI bugs, Sprint refactor general**: `templates/index.html`, `templates/mobile.html`, `static/app.js`, `static/mobile.js`, `static/service-worker.js`, `templates/login.html` | **Claude main session** |
| **Budget app**: `static/budget/*`, `blueprints/budget.py` | **Spawned-Budget session** (când există) |
| `database.py` migrații | session-ul care introduce schema (anunță prin commit message clar) |
| Manuale PDF în `manuals/` | **Hermes** (descarcă, validează) |
| Memory files Ion (`~/.claude/projects/.../memory/*.md`) | **NU atinge** — locale Ion |

#### Reguli shared files (`templates/index.html`, `static/app.js`, `templates/mobile.html`, `static/mobile.js`)

Aceste 4 fișiere sunt **shared**. Mai multe sesiuni au nevoie să adauge integrări UI mici (un buton, un include de script, un handler).

**Protocol obligatoriu pentru modificări pe shared files:**

1. **Înainte de fiecare push:**
   ```bash
   git fetch origin master
   git pull --rebase origin master
   ```
   Dacă rebase-ul produce conflict pe shared files, **STOP**, citește ce a făcut sesiunea concurentă, integrează manual, retestează.

2. **Marker pentru integrări spawned sessions**: când spawned session adaugă o secțiune mică în index.html / mobile.html / app.js / mobile.js, **wrappuiește cu comentarii de ownership**:
   ```html
   <!-- BEGIN: PV (owned by spawned-pv session) -->
   <button onclick="openPvModal()">Generează PV</button>
   <script src="/static/pv-modal.js"></script>
   <!-- END: PV -->
   ```
   ```js
   // BEGIN: import-params (owned by spawned-import session)
   function openImportParamsModal() { ... }
   // END: import-params
   ```
   Claude main session **NU șterge** secțiuni marcate ca owned de altă sesiune fără să discute cu Ion.

3. **Commit size**: modificările spawned sessions pe shared files să fie **mici și rapide** (un commit per integrare, push imediat). Cu cât stai mai mult cu modificări shared ne-pushed, cu atât crește riscul ca alt agent să facă push peste.

4. **Frequency check**: dacă un agent observă commit-uri masive pe shared files de la altă sesiune în ultimele 5 minute, așteaptă 30s + face git pull înainte să continue.

#### Bug-uri găsite în domain altcuiva

Dacă găsești un bug în zona "Claude" și e mic (typo, bug de o linie), corectează-l cu commit message clar `<scope> fix: ...`. Dacă e mai mare, **NU atingi shared files** — lasă într-un fișier `FOUND_BUGS.md` la root și anunță Ion.

### C. Design system — neapărat respectă

Aplicația are deja paletă, fonturi și pattern-uri stabilite. **NU introduce stiluri ad-hoc.**

**Palete** (vezi `templates/index.html` și `templates/mobile.html`):
- Background: `--bg #0a0d12`, `--bg-elev1 #11161e`, `--bg-elev2 #161c26`, `--bg-elev3 #1d2530`
- Accent turcoaz: `--accent #58d1c9`, cu `--accent-soft` și `--accent-ring`
- Semantic: `--danger #f97066`, `--warning #f5b14d`, `--success #66d19e`, `--violet #8b87ff`
- Light theme are propriile valori — păstrează ambele dacă atingi CSS

**Fonturi**:
- `Plus Jakarta Sans` pentru body
- `JetBrains Mono` pentru orice cifră, cod, valoare numerică, parametru

**Iconițe**:
- **Lucide line-icons EXCLUSIV** (CDN `https://unpkg.com/lucide@latest/dist/umd/lucide.min.js`). Zero emoji în UI. Excepție: emoji-urile DIN DATA (în explicații parametri, observații Ion etc.) — alea sunt conținut, nu UI.
- Iconițe inserate dinamic prin `<i data-lucide="nume-iconita">` + apel `lucide.createIcons()`. Mobile.html are deja un MutationObserver care le rerandează automat, **NU spargi pattern-ul ăsta**.
- Re-entry guard `_iconsRendering` (vezi `static/app.js` `refreshIcons()`) e critic — fără el observer-ul intră în buclă infinită.

**Componente reutilizabile** pe desktop (`app.js`):
- `enhanceSelect()` / `cs-enhance` — transformă `<select>` native în dropdown custom dark. Pe orice `<select>` nou pus în UI, **pune clasa `cs-enhance`** și `enhanceAllSelects()` se ocupă.
- `flatpickr` pentru date — **NU folosi `<input type="date">` native** (Chrome îl afișează alb urât).
- Cache API: `apiGet`, `apiPost`, `apiPut`, `apiDelete`, `apiPrefetch` din `app.js`. `_invalidateCache(url)` face match pe root URL și suprafețe.

**Pe mobile** (`mobile.js`):
- Cache params în IndexedDB cu version bump
- Toate listele de parametri sortate **ASC by cod natural** (folosește `localeCompare` cu `{ numeric: true }`)

### D. Sortare parametri

**Default ASC by cod** pe ambele platforme. Backend (`/api/parametri`, `/api/parametri/bulk`) sortează deja `ORDER BY familie, parametru`. Pe client, dacă filtrezi sau resortezi, păstrează regula. **Nu introduce DESC by ID sau sort by created_at**.

### E. Cache-busting

- Versionează static assets prin query string: `?v=YYYYMMDD` sau `?v={{ js_version }}`
- La modificare în `static/service-worker.js`, bump `CACHE_NAME`/`STATIC_CACHE`/`API_CACHE` (`v1` → `v2` → ...). Activate-event-ul șterge cache-urile vechi automat.

---

## Stadiu curent (snapshot)

### UI
- Login pagină coerentă, fără dependență externă (Lucide ca SVG inline)
- Desktop: 5 taburi (Acasă, Taskuri Zilnice, Proiecte, Parametri, Administrativ), greeting + 4 stats color-coded, drill-down parametri (producător picker → familie mini-tabs → listă)
- Mobile (`/m`): paritate cu desktop ca features. Bottom-nav cu Lucide icons. Drill-down parametri. Buton "+ Proiect nou" și "+ Notiță nouă" inline (NU FAB), Lucide peste tot.
- Budget tracker (`/budget/`): redesign-uit aliniat cu PIF design system (alte sesiuni Claude)

### Data
- DB SQLite (`pif_dashboard.db` pe server, **NU în repo** — e în `.gitignore`)
- ~15.274 parametri în `parametri_master`. Calitatea descrierilor inconsistentă — asta e job-ul tău LLM.
- 7 familii: ABB (ACS580, ACS880), Siemens (G120, G130_G150, S120_S150), Danfoss (FC302), Lenze (i550, i950)

### Audit parametri (status la 2026-05-18 sesiunea seara, Claude Opus 4.6)

**Audit-ul PDF e COMPLET** (run local pe `D:\Projects\pif-dashboard` cu Python 3.12):

- 8 PDF-uri oficiale înlocuite în `manuals/` (Lenze i550 era greșit — hardware overview vs commissioning).
- Toate cele 4 parsere (ABB/Danfoss/Lenze/Siemens) rescrise cu full-field extraction:
  - **Siemens** (G120/G130/S120): pdfplumber + Access-level gate, coverage 99-100% desc/type
  - **Lenze** (i550/i950): pdfplumber `extract_tables()` + fallback linear
  - **Danfoss** (FC302): pdfplumber tabular 3-cell layout
  - **ABB** (ACS580/ACS880): **pymupdf** (fitz) word-level cu auto-detect column boundaries (pdfplumber lipea cuvintele pe ACS880)
- `audit_pdf.py` extins cu `--apply-all`, `--delete-orphans`, `--insert-new`. Toate cele 4 acțiuni rulate local:
  - Update masiv: 6092 descriere + 4604 acces + 2915 tip + 1825 default + 446 unitate + 8459 pagini
  - Șters: 4127 rows orfane (DB had but PDF didn't)
  - Inserat: 4398 params noi (PDF had but DB didn't) — Lenze i950 cel mai mare gap (+1360)
- DB local final: **14743 params**, toate cele 7 câmpuri sincronizate cu PDF, zero diff-uri funcționale.
- DB-ul updated transferat la server prin `/admin/db-upload` (endpoint nou).

**Singurul rest în DB** (TASK-UL TĂU):

Câmpurile LLM-only sunt încă goale/incomplete:
- `explicatie` — text comissioner în română (cel mai important)
- `interconexiuni` — alți params legați (cu cod referință)
- `influenteaza` — params influențați direct
- `categorie` — grupare tematică (poate fi inferată)

**Strategie ACCURACY-FIRST** (Ion explicit: "cat mai accurate, nu conteaza costul"):

1. **Model**: Sonnet 4.7 (sau echivalent best). NU Haiku.
2. **Prompt caching**: 1 system prompt cached per (producator, familie) cu:
   - rol "ești inginer commissioning convertizoare"
   - extracte din manual ca context (doar secțiunile relevante familiei)
   - 3-5 few-shot exemple de explicații bune
3. **Sequential**, nu Batch API — accuracy iterativă peste cost-saving.
4. **Multi-pass**:
   - Pass 1: scrie `explicatie` + `interconexiuni` + `influenteaza` + `categorie`
   - Pass 2 (sample 5-10%): self-review per param să verifici că nu sunt halucinații
5. **Stil**: română fără diacritice (convenția Ion), max 2-3 propoziții, commissioner-friendly.
   Exemplu bun: `"Defineste viteza minima a motorului. Setare critica daca aplicatia cere reverse — pune negativ. Vezi 30.12 pentru limita superioara."`
6. **Skip rule**: dacă `explicatie` deja există și e > 50 chars text natural (nu placeholder), skip cu review minim.
7. **Sources**: folosește `descriere` (deja PDF-extracted) + manualul complet `manuals/<familie>.pdf` ca context. NU genera info care nu-i derivable din descriere + manual.

**NU atinge**: `parametru`, `descriere_scurta`, `descriere`, `acces`, `tip_date`, `valoare_default_str`, `min`, `max`, `unitate`, `pagina` — TOATE sunt PDF-derived și validate.

**Cost estimat**: ~$50-100 cu cache agresiv pentru toate ~14k params, fără cache ~$200+. Folosește cache.

**Pas concret**:
1. `git pull` — ai cod-ul nou + audit_reports JSON ca referință
2. Verifică DB live (`/api/admin/db-dump`) are 14743 params
3. Implementează `scripts/llm_enrich.py` cu argparse `--familie X` + `--field explicatie|...` + resume
4. Test pe 20 params din ACS580 cu sample review manual înainte de scale
5. Update memory `MEMORY.md` la final cu count populat per câmp.

---

## Anti-coliziune — checklist la fiecare sesiune

Înainte să faci orice modificare:

```bash
cd ~/Projects/pif-dashboard            # /home/ion-ursu/... pe server
git fetch origin master
git pull --rebase origin master
git log --oneline -10
git status                              # trebuie clean
```

Dacă vezi commit-uri Claude / spawned sessions foarte recente (ultimele ore), citește-le rapid ca să știi ce a atins. Dacă fișierul pe care vrei să-l modifici a fost atins recent, **citește-l înainte de a-l rescrie** — convențiile pot fi nou-introduse.

**Înainte de fiecare push** (obligatoriu pe shared files):

```bash
git fetch origin master
git pull --rebase origin master
# Rezolvă orice conflict de aici, NU forța push.
git push origin master
```

Author va fi automat `Hermes <hermes@pif.iupif.org>` din git config local. **Nu te masquerade-uia** ca Claude/Ion.

Commit messages: fără diacritice, scope clar (`<scope>: <ce ai facut>`).

Verifică pe live că nu ai spart nimic:

```bash
curl -s -o /dev/null -w "HTTP: %{http_code}\n" --max-time 10 https://pif.iupif.org/login
curl -s -o /dev/null -w "HTTP: %{http_code}\n" --max-time 10 https://pif.iupif.org/m
```

Dacă vezi 500/502/503 după push-ul tău, **rollback imediat**:

```bash
git revert HEAD --no-edit
git push
```

Apoi diagnostichează în pace.

---

## Erori / gotcha cunoscute (pentru tine, ca să nu te lovesti de ele iar)

- **`render_template('mobile.html')` are nevoie de `js_version`** — context processor în `app.py` îl injectează. Dacă faci o rută nouă care randează mobile.html, lasă `{{ js_version }}` referit; nu îl elimina.
- **SQLite nu are REGEXP built-in** — nu folosi `REGEXP` în query-uri. Folosește `LIKE` sau Python regex post-fetch.
- **Service Worker cache-uiește agresiv** — la deploy nou pe static assets, bump versiunile din `service-worker.js` ca activate-event să șteargă cache-ul vechi. Userii vor primi versiunea nouă la următoarea încărcare.
- **`new project form crash` pe desktop** — `#jurnal-data` a fost șters dintr-o iterație anterioară. Codul care îl mai referă trebuie `if (jd) jd.value = ...`. Pattern: guard pe `getElementById` în tot codul care toucheză DOM-ul Acasă.
- **Cloudflare Tunnel poate cădea independent** — 1033 error apare când `cloudflared` e jos pe server. NU e cod-related. Ion îl restart-ează: `sudo systemctl restart cloudflared`.
- **PIN-ul** default e `pif2024`. NU păstra PIN-ul în niciun fișier committed.
- **Webhook auto-deploy crapă tăcut dacă ai modificări locale ne-comitate pe server** — pe laptop-server, dacă tu (Hermes) ai un fișier modificat dar ne-commit-uit (ex: `scripts/audit_pdf.py` în lucru), `git pull` refuză să suprascrie și webhook-ul returnează 500. Toate push-urile ulterioare ale lui Claude se acumulează pe GitHub fără să ajungă pe server. **Regulă**: păstrează worktree-ul de pe server CURAT. Înainte de orice sesiune de lucru pe scripts/audit, fie commit + push WIP, fie `git stash`. Verifică:
  ```bash
  cd ~/Projects/pif-dashboard && git status
  ```
  Trebuie să fie `nothing to commit, working tree clean` între sesiuni.

---

## Comunicare cu Ion

- Mesaje **scurte, directe, în română**.
- Fără introduceri lungi de tipul "Bună ziua, sper că ești bine". Direct la subiect.
- Când termini o sarcină, raportează concret: ce ai schimbat (fișiere), ce ai testat, ce mai e de făcut.
- Dacă ai întrebări, pune-le clar și ofera opțiuni (A / B / C) — Ion alege.
- Dacă nu ești sigur de scope, **întreabă înainte** — task-urile mari care se dovedesc greșite te costă tokeni.

---

*Document menținut de Claude în repo. Update-uri când stadiul aplicației se schimbă semnificativ.*
