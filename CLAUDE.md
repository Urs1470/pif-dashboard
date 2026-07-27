# PIF Dashboard

Industrial commissioning & project management SPA for Ion Ursu.
Single-user Flask app with SQLite, deployed via Gunicorn + Cloudflare Tunnel (HTTPS at pif.iupif.org).

## Stack

- **Backend:** Flask 3.1.3, SQLite (WAL mode, foreign keys ON), Gunicorn 23.0.0
- **Frontend:** Svelte 5 SPA (Vite build in `static/dist/`), Lucide icons, KaTeX. Tema „Bento" (dark warm + amber `#ffb454`, fonturi Inter/Space Grotesk/JetBrains Mono, navigatie prin Dock plutitor). Responsive — covers mobile too (the legacy vanilla-JS app + the separate `/m` PWA were removed 2026-06-17). The only server-rendered template left is `login.html`.
- **Auth:** PIN-based (env `PIF_DASHBOARD_PIN`), session cookie (30d), CSRF double-submit
- **Deploy:** systemd service on Ubuntu laptop-server, Cloudflare Tunnel, webhook auto-deploy

## Pull FIRST — before any task

Before reading or editing anything for a task, run `git pull --rebase origin master`. This repo
is modified from other machines and sessions (on 2026-07-16 a local clone was 93 commits behind
and the code didn't match the live API). Exception: if the working tree is dirty, report it
first — never pull over uncommitted changes.

## Persistent Memory — READ FIRST

To avoid re-exploring the codebase every session, start here instead of scanning large files:

- `docs/memory/MEMORY.md` — curated memory: DB map, feature status, gotchas, recent decisions
- `docs/memory/CODE_MAP.md` — auto-generated: top-level functions per Python module with line numbers (e.g. database.py is ~1200 lines — find the function here, then read only that range)
- `docs/memory/API_MAP.md` — auto-generated: all Flask routes (method, path, handler, line)
- `SCHEMA_REFERENCE.md` — full SQL schema; `HERMES.md` — multi-agent rules + design system

The maps regenerate automatically on commit via a versioned pre-commit hook (`.githooks/pre-commit`). Activate it once per clone:

```bash
git config core.hooksPath .githooks
```

If the hook isn't active (or to refresh manually), run:

```bash
python scripts/gen_memory.py
```

Append important decisions/gotchas to the "Recent decisions" section of `docs/memory/MEMORY.md`.

## Architecture

```
app.py                    # Flask entry, auth, CSP headers, rate limiter
database.py               # Schema (9 tables), migrations v1-v28, WAL config
utils.py                  # login_required decorator, UUID, app_settings KV
csrf.py                   # Double-submit CSRF (cookie + X-CSRF-Token header)
labels.py                 # Centralized status labels (project + task states)

blueprints/
  projects.py             # /api/proiecte/* — CRUD, filters, Excel/PDF export, snapshot
  tasks.py                # /api/proiecte/<id>/tasks/* — CRUD, subtasks, recurring
  obsidian.py             # /api/obsidian/* — read-only vault integration
  admin.py                # /api/stats/*, /api/export/*, /api/search/* — analytics, backup

templates/
  login.html              # PIN login (only remaining server-rendered template)

static/
  dist/                   # Svelte SPA build (Vite) — the app, served at /
  service-worker.js       # PWA cache strategy (STATIC_CACHE + API_CACHE); registered by the SPA
  login.css               # login page styling
```

## Database

SQLite file: `pif_dashboard.db` (gitignored). 9 tables, 29 migrations (idempotent).

**Core tables:** proiecte, tasks, task_subtasks (FK CASCADE), task_dependencies, global_tasks, implementari, clienti

**Specialized:** app_settings (KV store), schema_version

**Migrations:** `database.py` — `run_migrations()` chains v1 through v29. Each is idempotent. Auto-runs on first request via `before_request`. (v20 dropped Budget Tracker; v22 dropped timer & jurnal — orele se ponteaza in e100, jurnalul se scrie in observatii; v23 dropped Checklist PIF + Project Templates + Hermes AI — cod mort, zero UI; **v28 dropped parametri_master, fault_codes, echipamente, atasamente** — restrangere de scop la organizare/monitorizare de proiecte, vezi mai jos.)

### Restrangere de scop (v28, 2026-07-27)

Dashboard-ul nu mai dubleaza wiki-ul si manualele. Ce a plecat si de ce:

- **parametri_master** (14.813 randuri) si **fault_codes** (3.851) — catalog de referinta fara nicio
  legatura cu proiectele. Parametrii si codurile de eroare se iau din manual sau prin Cowork, unde
  ai sursa citabila.
- **echipamente** (26 randuri, in 4 din 20 de proiecte) — reintroducere manuala a ceva ce skill-ul
  `drive-backup` extrage determinist din `.dcparamsbak` / STARTER, direct in wiki.
- **atasamente** (30 fisiere) — backup-urile brute stau in vault, la `raw/projects/<slug>/`.
  Fisierele urcate NU au fost sterse de pe disc; doar tabela.

Ce **nu** s-a atins: Calculatorul, inclusiv `/api/import-abb-multi/preview` si
`/api/import-archive/preview` — ele parseaza un backup de drive fara sa atinga DB-ul si alimenteaza
placuta motorului. Blueprint-ul `obsidian.py` ramane: el tine sincronizarea wiki <-> dashboard.

Arhiva completa a datelor sterse: `raw/pif-dashboard/2026-07-27-inainte-de-v28/` in vault
(JSON + CSV per tabela, snapshot integral, seed-uri, README cu procedura de recuperare).

### Date calendaristice (v29, 2026-07-27)

**Nu stocam niciodata o data pe care nu o putem citi.** `utils.norm_date()`, chemata din
`get_json_or_400()` — palnia unica a tuturor scrierilor JSON — accepta ISO si formatele
romanesti (`23.02.2026`, `5/3/2026`), respinge cu 400 orice altceva, si lasa neatinse
valorile care incep deja cu ISO (ca sa nu ciunteasca timestampurile). Migrarea v29 a
normalizat ce intrase inainte de paza: `23.02.2026` pe un proiect, `02.07.2026` pe un task.

`/api/calendar` intoarce `probleme[]` cu orice data pe care SQLite nu o poate interpreta,
iar Calendarul o arata ca un KPI rosu. Motivul: o data necitibila nu se aseaza pe nicio zi,
deci randul disparea din calendar **fara niciun semn** — iar o absenta tacuta te invata sa
nu te bazezi pe restul.

### Proprietatea suprafetelor de planificare

Fiecare vedere generala detine un singur obiect; pagina proiectului le detine pe ale ei:

- **Calendar** = perioadele (deplasarile). Se creeaza, se muta si se scot doar de aici.
  Termenele apar ca semnal, nu se editeaza.
- **Planificator** = taskurile. Benzile de perioada sunt context — click pe ele duce la
  `#/calendar?zi=AAAA-LL-ZZ`, nu deschide un editor.
- **ProjectDetail** pastreaza CRUD complet pe ambele (`ImplPeriods`, `ProjectGantt`).

Vocabular: **perioada** = interval (unde esti), **termen** = punct (pana cand). „Data" nu se
mai foloseste ca eticheta — sertarele sunt „Proiecte fara perioada" (Calendar) si „Taskuri
fara termen" (Planificator), lucruri diferite cu nume care o spun.

### Planul de departament (`/departament`)

Planul intregii echipe sta intr-o aplicatie externa (`app.projectplan-powerpoint.com`) si e
**incorporat** in SPA, nu importat — e o plansa, nu o structura cu API. Linkul de partajare
contine cheia de acces in fragment (dupa `#`), deci nu ajunge la serverul lor prin cererea
HTTP. Se tine in `app_settings` prin `GET/PUT /api/settings/plan-departament`, **niciodata
in cod sau in `wiki/`** (care e urmarit de git). Domeniul apare in doua locuri care trebuie
sa ramana sincronizate: `utils.PLAN_DEPT_HOST` (validare pe server) si `frame-src` din CSP
(`app.py`).

## Key Patterns

- **All SQL uses parameterized queries** (no string interpolation)
- **CSRF:** exempt GET/HEAD/OPTIONS and /webhook/*. Client reads `csrf_token` cookie, sends back in `X-CSRF-Token` header
- **Rate limiting:** 60 req/min per IP on `/api/*` + POST `/login`
- **Asset versioning:** SHA256 hash busting via context processor (`?v=<hash>`)
- **Session cookie:** Secure=true (HTTPS only), HttpOnly, SameSite=Lax
- **CSP:** `unsafe-inline` (hundreds of onclick handlers; nonce migration is future work)
- **Recurring tasks:** zilnic/saptamanal/lunar — auto-spawn next on completion

## Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `PIF_DASHBOARD_PIN` | Yes (prod) | none | Login fails without it |
| `SECRET_KEY` | No | auto-generated `.secret_key` file | Session signing |
| `SESSION_COOKIE_SECURE` | No | `true` | Set `false` for local HTTP dev |
| `PIF_USE_DIST` | No | `false` | Use minified builds from static/dist/ |
| `PIF_API_TOKEN` | No | none | Bearer token for machine-to-machine API access (Cowork). CSRF-exempt. |
| `PIF_DB_PATH` | No | `pif_dashboard.db` next to the code | Alternate DB file. Used by `scripts/smoke_ui.py` to run on a throwaway copy. |
| `PIF_RATE_LIMIT` | No | `60` | Requests/min per IP on `/api/*`. Raised only by the smoke test; keep 60 in prod. |

## Cowork Integration

Cowork (Claude AI) can read and write Dashboard data via REST API using a Bearer token:

```bash
# Read project list
curl -H "Authorization: Bearer $PIF_API_TOKEN" https://pif.iupif.org/api/proiecte?status=in_lucru

# Read full project snapshot (all child data)
curl -H "Authorization: Bearer $PIF_API_TOKEN" https://pif.iupif.org/api/proiecte/<id>/snapshot

# Import debrief (create project + all child data)
curl -X POST -H "Authorization: Bearer $PIF_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d @debrief.json https://pif.iupif.org/api/import/debrief
```

## Server

- **Host:** ion-ursu-ThinkPad-T450, user `ion-ursu`, SSH port 22
- **Path:** `/home/ion-ursu/Projects/pif-dashboard`
- **Service:** `sudo systemctl restart pif-dashboard`
- **Gunicorn:** `--bind 0.0.0.0:5000 --workers 2 --timeout 120`
- **HTTPS:** Cloudflare Tunnel to `pif.iupif.org`
- **DB backups:** `backup_db.py` (keeps last 30)

## Deploy Workflow

```bash
git push origin master           # from Windows dev machine
ssh ion-ursu@192.168.0.107       # to server
cd ~/Projects/pif-dashboard
git pull origin master
source venv/bin/activate
pip install -r requirements.txt  # if deps changed
sudo systemctl restart pif-dashboard
```

Or via webhook: push triggers POST `/webhook/deploy` (validates X-Hub-Signature-256).

## Testing

Ad-hoc test scripts in `scripts/`:
- `test_suite.py` — API/backend harness. `python scripts/test_suite.py`
- `smoke_ui.py` — **test de fum pentru SPA.** Porneste singur aplicatia pe un port
  liber si pe o COPIE a bazei (`PIF_DB_PATH`), apoi deschide in Chromium headless
  fiecare ruta, fiecare proiect si fiecare tab, pe desktop si pe mobil. Pica la
  orice exceptie neprinsa, eroare de consola, pagina goala sau schelet care nu
  dispare.

```bash
python scripts/smoke_ui.py
```

De ce exista: build-ul Svelte compileaza CURAT o pagina care crapa la rulare —
componentele din template se rezolva la RULARE. Pe 2026-07-27 un import lipsa
(`AlertCircle`) a lasat toate proiectele de tip Service pe schelet, cu build verde
si `test_suite` 12/12, pentru ca greseala statea pe ramura `{#if tip === 'Service'}`.
Ruleaza-l dupa orice curatenie de importuri sau modificare de pagina.

Cerinte, o singura data si doar pe masina de dezvoltare (NU in `requirements.txt`):

```bash
pip install playwright && python -m playwright install chromium
```

No pytest/unittest framework.

## Multi-Agent Collision Rules

Shared working tree → shared git index, so coordinate before staging/committing. When spawning sub-sessions:
- **Main app (SPA):** `frontend/src/` (Svelte components/pages) → built into `static/dist/`
- **Import session:** `scripts/parse_params/*`
- Always `git fetch && git pull --rebase` before push. No force push.

> See `HERMES.md` (architecture + design system + git protocol) and `AGENT_BRIEFING.md` (spawn template) for the full multi-agent workflow.

## Known Limitations

- CSP uses `unsafe-inline` — migrating to nonce requires refactoring all onclick handlers
- UPLOAD_FOLDER not configurable via env var (hardcoded in utils.py)
- Status values are magic strings (e.g. `'in_lucru'`, `'finalizat'`) — centralized in labels.py but not enforced at DB level
- CDN dependencies (jsdelivr, cdnjs) — SRI hashes added but no local fallback for all
- No formal test framework (pytest) — scripts/ has ad-hoc tests
