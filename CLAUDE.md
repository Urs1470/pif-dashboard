# PIF Dashboard

Industrial commissioning & project management SPA for Ion Ursu.
Single-user Flask app with SQLite, deployed via Gunicorn + Cloudflare Tunnel (HTTPS at pif.iupif.org).

## Stack

- **Backend:** Flask 3.1.3, SQLite (WAL mode, foreign keys ON), Gunicorn 23.0.0
- **Frontend:** Vanilla JS SPA (no framework), Lucide icons, Flatpickr, Chart.js
- **Mobile:** PWA at `/m` with IndexedDB offline, separate JS bundle
- **Auth:** PIN-based (env `PIF_DASHBOARD_PIN`), session cookie (30d), CSRF double-submit
- **Deploy:** systemd service on Ubuntu laptop-server, Cloudflare Tunnel, webhook auto-deploy

## Persistent Memory — READ FIRST

To avoid re-exploring the codebase every session, start here instead of scanning large files:

- `docs/memory/MEMORY.md` — curated memory: DB map, feature status, gotchas, recent decisions
- `docs/memory/CODE_MAP.md` — auto-generated: every JS section + top-level function with line numbers (app.js is ~8k lines — find the section here, then read only that range)
- `docs/memory/API_MAP.md` — auto-generated: all Flask routes (method, path, handler, line)
- `SCHEMA_REFERENCE.md` — full SQL schema; `HERMES.md` — multi-agent rules + design system

After structural changes (new/removed functions, JS sections, or routes), regenerate the maps and commit them with your change:

```bash
python scripts/gen_memory.py
```

Append important decisions/gotchas to the "Recent decisions" section of `docs/memory/MEMORY.md`.

## Architecture

```
app.py                    # Flask entry, auth, CSP headers, rate limiter
database.py               # Schema (19 tables), migrations v1-v17, WAL config
utils.py                  # login_required decorator, UUID, app_settings KV
csrf.py                   # Double-submit CSRF (cookie + X-CSRF-Token header)
labels.py                 # Centralized status labels (project + task states)

blueprints/
  projects.py             # /api/proiecte/* — CRUD, filters, Excel/PDF export, templates
  tasks.py                # /api/proiecte/<id>/tasks/* — CRUD, subtasks, recurring
  timer.py                # /api/.../timer/* — per-project, per-task, global timers
  parametri.py            # /api/parametri/* — drive params (ABB, Siemens, Danfoss, Lenze)
  budget.py               # /budget/* — standalone budget tracker SPA, audit trail
  obsidian.py             # /api/obsidian/* — read-only vault integration
  assistant.py            # /api/assistant/* — Hermes AI (MiniMax gateway)
  admin.py                # /api/stats/*, /api/export/*, /api/search/* — analytics, backup

templates/
  index.html              # Main SPA shell (desktop)
  mobile.html             # PWA shell (/m)
  login.html              # PIN login

static/
  app.js                  # Desktop app logic
  mobile.js               # Mobile PWA logic
  core.js                 # Shared: API helpers, CSRF, date formatters, status labels
  style.css               # Design system with dark mode
  service-worker.js       # PWA cache strategy (STATIC_CACHE + API_CACHE 30s TTL)
  budget/                 # Standalone budget tracker SPA
    budget-tracker.js     # State machine, ING CSV import, VWCE portfolio
    budget.css
    index.html
```

## Database

SQLite file: `pif_dashboard.db` (gitignored). 19 tables, 17 migrations (idempotent).

**Core tables:** proiecte, tasks, task_subtasks (FK CASCADE), checklist_pif, checklist_categorii, jurnal, timer_sessions, global_tasks, global_task_sessions, atasamente, echipamente, clienti, project_templates

**Specialized:** fault_codes (8 drive families, auto-seeded from data/fault_codes/*.json), budget_state (JSON blob per user), budget_audit (capped 5000 rows/user via trigger), assistant_memory, app_settings (KV store), schema_version

**Migrations:** `database.py` — `run_migrations()` chains v1 through v17. Each is idempotent. Auto-runs on first request via `before_request`.

## Key Patterns

- **All SQL uses parameterized queries** (no string interpolation)
- **CSRF:** exempt GET/HEAD/OPTIONS and /webhook/*. Client reads `csrf_token` cookie, sends back in `X-CSRF-Token` header
- **Rate limiting:** 60 req/min per IP on `/api/*` + POST `/login`
- **Asset versioning:** SHA256 hash busting via context processor (`?v=<hash>`)
- **Session cookie:** Secure=true (HTTPS only), HttpOnly, SameSite=Lax
- **CSP:** `unsafe-inline` (hundreds of onclick handlers; nonce migration is future work)
- **Recurring tasks:** zilnic/saptamanal/lunar — auto-spawn next on completion
- **Budget user:** `session.get('budget_user', 'ion')` — not hardcoded

## Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `PIF_DASHBOARD_PIN` | Yes (prod) | none | Login fails without it |
| `SECRET_KEY` | No | auto-generated `.secret_key` file | Session signing |
| `SESSION_COOKIE_SECURE` | No | `true` | Set `false` for local HTTP dev |
| `PIF_USE_DIST` | No | `false` | Use minified builds from static/dist/ |
| `PIF_API_TOKEN` | No | none | Bearer token for machine-to-machine API access (Cowork). CSRF-exempt. |

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
- `test_suite.py` — main test harness
- `test_timer_all.py` — timer logic
- `test_budget_conflict.py` — budget state collision
- `verify_budget_deploy.py` — deployment verification

No pytest/unittest framework. Run with `python scripts/test_suite.py`.

## Multi-Agent Collision Rules

From `HERMES.md` — when spawning sub-sessions:
- **Main session:** templates/index.html, static/app.js, templates/mobile.html, static/mobile.js
- **Import session:** scripts/parse_params/*
- **Budget session:** static/budget/*, blueprints/budget.py
- Always `git fetch && git pull --rebase` before push. No force push.

## Known Limitations

- CSP uses `unsafe-inline` — migrating to nonce requires refactoring all onclick handlers
- UPLOAD_FOLDER not configurable via env var (hardcoded in utils.py)
- Status values are magic strings (e.g. `'in_lucru'`, `'finalizat'`) — centralized in labels.py but not enforced at DB level
- CDN dependencies (jsdelivr, cdnjs) — SRI hashes added but no local fallback for all
- No formal test framework (pytest) — scripts/ has ad-hoc tests
