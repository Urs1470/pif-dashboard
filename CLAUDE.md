# PIF Dashboard

Industrial commissioning & project management SPA for Ion Ursu.
Single-user Flask app with SQLite, deployed via Gunicorn + Cloudflare Tunnel (HTTPS at pif.iupif.org).

## Stack

- **Backend:** Flask 3.1.3, SQLite (WAL mode, foreign keys ON), Gunicorn 23.0.0
- **Frontend:** Svelte 5 SPA (Vite build in `static/dist/`), Lucide icons, KaTeX. Tema „Bento" (dark warm + amber `#ffb454`, fonturi Inter/Space Grotesk/JetBrains Mono, navigatie prin Dock plutitor). Responsive — covers mobile too (the legacy vanilla-JS app + the separate `/m` PWA were removed 2026-06-17). The only server-rendered template left is `login.html`.
- **Auth:** PIN-based (env `PIF_DASHBOARD_PIN`), session cookie (30d), CSRF double-submit
- **Deploy:** systemd service on Ubuntu laptop-server, Cloudflare Tunnel, webhook auto-deploy

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
database.py               # Schema (14 tables), migrations v1-v22, WAL config
utils.py                  # login_required decorator, UUID, app_settings KV
csrf.py                   # Double-submit CSRF (cookie + X-CSRF-Token header)
labels.py                 # Centralized status labels (project + task states)

blueprints/
  projects.py             # /api/proiecte/* — CRUD, filters, Excel/PDF export, templates
  tasks.py                # /api/proiecte/<id>/tasks/* — CRUD, subtasks, recurring
  parametri.py            # /api/parametri/* — drive params (ABB, Siemens, Danfoss, Lenze)
  obsidian.py             # /api/obsidian/* — read-only vault integration
  assistant.py            # /api/assistant/* — Hermes AI (MiniMax gateway)
  admin.py                # /api/stats/*, /api/export/*, /api/search/* — analytics, backup

templates/
  login.html              # PIN login (only remaining server-rendered template)

static/
  dist/                   # Svelte SPA build (Vite) — the app, served at /
  service-worker.js       # PWA cache strategy (STATIC_CACHE + API_CACHE); registered by the SPA
  login.css               # login page styling
```

## Database

SQLite file: `pif_dashboard.db` (gitignored). 14 tables, 22 migrations (idempotent).

**Core tables:** proiecte, tasks, task_subtasks (FK CASCADE), checklist_pif, checklist_categorii, global_tasks, atasamente, echipamente, clienti, project_templates

**Specialized:** fault_codes (8 drive families, auto-seeded from data/fault_codes/*.json), assistant_memory, app_settings (KV store), schema_version

**Migrations:** `database.py` — `run_migrations()` chains v1 through v22. Each is idempotent. Auto-runs on first request via `before_request`. (v20 dropped Budget Tracker; v22 dropped timer & jurnal — orele se ponteaza in e100, jurnalul se scrie in observatii.)

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

No pytest/unittest framework. Run with `python scripts/test_suite.py`.

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
