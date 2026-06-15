# MEMORY — PIF Dashboard

Persistent project memory for AI sessions. Read this INSTEAD of re-exploring the codebase.
Companion files (auto-generated, regenerate with `python scripts/gen_memory.py`):
- `CODE_MAP.md` — every JS section + top-level function with line numbers
- `API_MAP.md` — all Flask routes (method, path, handler, line)

Other authoritative docs (do not duplicate here):
- `CLAUDE.md` — stack, env vars, deploy, key patterns
- `HERMES.md` — multi-agent collision rules, shared-file BEGIN/END protocol, design system
- `SCHEMA_REFERENCE.md` — full SQL schema (all 19 tables, columns, FKs, indexes)

## Database map by domain

| Domain | Tables |
|---|---|
| Projects core | `proiecte`, `checklist_pif`, `checklist_categorii`, `jurnal`, `atasamente`, `echipamente`, `clienti`, `project_templates` |
| Tasks & timers | `tasks`, `task_subtasks`, `timer_sessions`, `global_tasks`, `global_task_sessions` |
| Drive knowledge | `parametri_master` (~15.3k params, 7 families), `fault_codes` (8 families, seeded from `data/fault_codes/*.json`) |
| Budget | `budget_state` (JSON blob/user), `budget_audit` (capped 5000 rows/user via trigger) |
| System | `assistant_memory`, `app_settings` (KV), `schema_version` |

Migrations: in-code in `database.py` (`run_migrations()`), currently **v18**, idempotent, auto-run via `before_request`.

## Feature status (last verified 2026-06-11)

- Parameter LLM enrichment (`explicatie`/`influenteaza`/`categorie`): ABB + Siemens 100%; Danfoss FC302 + Lenze pending. Rules in `LLM_ENRICH_BRIEF.md` (Romanian, no diacritics, LaTeX `$...$`).
- Fault codes browser: all 8 families seeded and browsable (desktop + param/fault detail modals).
- Journal: merged journal + timer entries view; manual time on entries with same-day dedup.
- PDF manuals browser wired into param/fault detail.
- Budget tracker: standalone SPA at `/budget/`, own session domain (`static/budget/*`, `blueprints/budget.py`).
- Cowork API: Bearer `PIF_API_TOKEN`, endpoints `/api/proiecte`, `/api/proiecte/<id>/snapshot`, `/api/import/debrief`.

## Gotchas

- `static/app.js` (~8k lines) and `static/mobile.js` (~4.8k) are SEPARATE bundles — a desktop feature usually needs a mobile twin. Use CODE_MAP.md to find the section, then read only that range.
- JS section headers: `// ============ NAME ============`. Keep this format — `gen_memory.py` parses it.
- Asset cache-busting is automatic (SHA256 `?v=` via context processor) — no manual version bumps.
- CSRF: client reads `csrf_token` cookie → sends `X-CSRF-Token` header. GET/HEAD/OPTIONS and `/webhook/*` exempt; Bearer-token requests exempt.
- Status values are magic strings (`'in_lucru'`, `'finalizat'`...) — labels centralized in `labels.py` (backend) and `static/core.js` (frontend); keep both in sync.
- Recurring tasks (zilnic/saptamanal/lunar) auto-spawn the next instance on completion — completion logic must preserve this.
- Tests: no pytest; run `python scripts/test_suite.py` (plus feature scripts in `scripts/`).
- Multi-agent: always `git fetch && git pull --rebase` before push; never force-push; respect domain split in `HERMES.md`.

## Maintenance protocol (for every AI session)

1. Start by reading this file + `CODE_MAP.md`/`API_MAP.md` — do NOT scan app.js/blueprints blindly.
2. Maps auto-regenerate on commit via `.githooks/pre-commit` (activate once per clone: `git config core.hooksPath .githooks`). Without the hook, run `python scripts/gen_memory.py` manually after adding/removing functions, sections, or routes.
3. Made a non-obvious decision, found a new gotcha, or changed feature status? Append one dated line to **Recent decisions** below (newest first, keep ≤ 30 entries, prune oldest).

## Recent decisions

- 2026-06-12: Attachment click opens a preview modal instead of a new tab. Shared `components/ui/AttachmentPreview.svelte` (image=`<img>`, PDF=`<iframe>`, other=icon+download). Used by AttachmentsTab + task chips (Tasks + ProjectDetail). Modal now has an optional `footer` snippet (rendered as `.modal-footer`, flex-shrink:0 outside the scrolling `.modal-body`) — preview actions live there so they stay fixed. GOTCHA: global `after_request` sets `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'`, which block ALL iframes incl. same-origin → PDF preview was blank (broken-doc icon). Fix: `download_atasament` sets `X-Frame-Options: SAMEORIGIN` + CSP `frame-ancestors 'self'` on its own response (after_request uses setdefault, so route values win). Images use `<img>` so they were never affected.
- 2026-06-12: Per-task attachments via migration v18: `atasamente` rebuilt with nullable `proiect_id` + `task_id`/`global_task_id` (FK CASCADE). Project-task files keep `proiect_id` set (visible in project Atasamente tab too); global-task files go to `uploads/global-tasks/<id>/`. Endpoints in projects.py reuse `_store_uploaded_file()`; task DELETE endpoints remove files from disk. UI: paperclip chips + count badge in expanded row, both pages.
- 2026-06-12: Task notes upgraded to Observatii concept: rendered preview (max-height+fade) in expanded row + WYSIWYG RichTextEditor modal. Shared helpers extracted to `frontend/src/lib/storedText.js` (sanitizeHtml/renderStoredText — ProjectDetail now imports from there). Fixed pre-existing RichTextEditor `plainToHtml` bug (escaped its own `<br>` tags — affected legacy plain-text in Observatii too).
- 2026-06-12: Task notes = the existing `descriere` column, edited inline in the expanded task row (click text / "Adauga notite..."), on both Tasks page (snippet, active+done) and ProjectDetail. No new table/endpoint; PUT COALESCE accepts '' to clear.
- 2026-06-12: Inline quick-add for tasks (global + project): form under toolbar on Tasks (hidden in Arhiva view), ProjectDetail single-field "Task Nou" modal replaced by inline form. Backend untouched (endpoint defaults cover prioritate/categorie/status).
- 2026-06-11: Added versioned pre-commit hook (`.githooks/pre-commit`) that auto-regenerates CODE_MAP/API_MAP when relevant code is committed; activation per clone via `git config core.hooksPath .githooks`.
- 2026-06-11: Created persistent memory system (`scripts/gen_memory.py` → `docs/memory/`); CLAUDE.md updated to point here; fixed stale migration count (v14 → v17).
