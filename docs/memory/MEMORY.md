# MEMORY — PIF Dashboard

Persistent project memory for AI sessions. Read this INSTEAD of re-exploring the codebase.
Companion files (auto-generated, regenerate with `python scripts/gen_memory.py`):
- `CODE_MAP.md` — every JS section + top-level function with line numbers
- `API_MAP.md` — all Flask routes (method, path, handler, line)

Other authoritative docs (do not duplicate here):
- `CLAUDE.md` — stack, env vars, deploy, key patterns
- `HERMES.md` — multi-agent collision rules, shared-file BEGIN/END protocol, design system
- `SCHEMA_REFERENCE.md` — full SQL schema (all 10 tables, columns, FKs, indexes)

## Database map by domain

| Domain | Tables |
|---|---|
| Projects core | `proiecte`, `atasamente`, `echipamente`, `clienti` |
| Tasks | `tasks`, `task_subtasks`, `global_tasks` |
| Drive knowledge | `parametri_master` (~15.3k params, 7 families), `fault_codes` (8 families, seeded from `data/fault_codes/*.json`) |
| System | `app_settings` (KV), `schema_version` |

Migrations: in-code in `database.py` (`run_migrations()`), currently **v23**, idempotent, auto-run via `before_request`.

## Feature status (last verified 2026-06-11)

- Parameter LLM enrichment (`explicatie`/`influenteaza`/`categorie`): ABB + Siemens 100%; Danfoss FC302 + Lenze pending. Rules in `LLM_ENRICH_BRIEF.md` (Romanian, no diacritics, LaTeX `$...$`).
- Fault codes browser: all 8 families seeded and browsable (desktop + param/fault detail modals).
- PDF manuals browser wired into param/fault detail.
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

- **2026-07-03 — 2 bug-uri agenda „Astăzi" (raportate de Ion)** (SW v74): (1) **Deadline nu se muta
  la amânare** — un task cu `data_scadenta`=azi apare în agendă (clauza due-today din `_AGENDA_WHERE`).
  Amânarea din agendă seta doar `data_planificata`, lăsând deadline-ul în trecut → task veșnic restant.
  Fix în `stores/agenda.svelte.js`: `moveToDate`/`moveToTomorrow` acceptă `opts.data_scadenta` și mută
  ȘI `data_scadenta` pe noua zi. **v75 (cerut de Ion):** deadline-ul existent se mută ÎNTOTDEAUNA la
  reprogramare (apropiat sau îndepărtat) — nu doar când e ≤ azi — fiindcă noua dată reflectă când crede
  că se poate face. Taskurile FĂRĂ deadline rămân fără (nu inventăm termen din simpla planificare).
  TodayBoard paseaza `{data_scadenta: it.data_scadenta}` la onTomorrow/onMoveDate. Verificat E2E: task
  due-azi → amânat +9z → `data_scadenta` mutat, iese din azi, pe ziua-țintă e scadent nu restant.
  (2) **Bifarea în „Astăzi" nu updata cardul „urgente"** până la refresh/schimbare tab — TodayBoard
  (store `agenda`) și cardul urgente (`dashboard.urgent_tasks` din `/api/dashboard/home`) sunt surse
  separate. Fix: TodayBoard primeste prop `onchange`; Home îl leagă la `loadDashboard(true)` (reload
  **silent** — fără skeleton pe toată pagina). Efectul de animație KPI acum face *snap* la reload-urile
  ulterioare (nu reanimă de la 0, dar actualizează cifra). `onchange()` apelat după toggle/tomorrow/
  remove/moveDate/quickAdd. Verificat Playwright: bifez task urgent în agendă → dispare din card fără refresh.

- **2026-07-03 — P5 consistență design (parțial, vizibil)** (SW v73): unificat iconografia mixtă —
  înlocuit glifele Unicode cu Lucide/SVG: `≔`→`ListTodo`, `!`→`AlertTriangle` (Tasks), `◔`→`CalendarDays`
  (AgendaColumn), `◳`/`⟳`→`Zap`/`Wrench` (tip-chip PIF/Service în Projects), `&times;`→`<X>` (Modal close).
  Nou token `--radius-chip: 7px` (consolidează radiile ad-hoc 7/8px pe `.ico` + `.tip-chip`). Verificat
  Playwright: `.ico svg`/`.tip-chip svg`/`.ico-vio svg` prezente, 0 erori. **Deliberat amânat** (refactor
  intern, zero payoff vizual, risc de regresie pe 6 search-box-uri funcționale): componentele comune
  `SearchPill`/`CountBadge`/`DropdownMenu`. Rămâne oportunist.

- **2026-07-03 — P6 calitate/UX** (SW v72): (1) **ErrorState + retry** pe listele care înghiteau
  erorile → fals „empty": `Tasks.svelte` (pe `globalTasks.error`), `Params.svelte` (nou `curError`
  derivat din `params.error`/`faultCodes.error`; adăugat `faultCodes.error` în store). ProjectDetail
  avea deja. (2) **Undo-toast** — infrastructură nouă în `stores/ui.svelte.js`: `toastUndo(msg,
  {onUndo, onCommit, duration})` cu semantică *deferred-commit* (scoți optimist din UI, ștergerea
  reală rulează în `onCommit` la expirare/închidere ~6s, „Anulează" apelează `onUndo`). `closeToast`
  (X pe un undo-toast încă nedecis = comite) + `runToastAction`. `Toast.svelte` randează butonul
  `actionLabel` + `aria-live=polite`. Aplicat la **ștergerea subtask-ului** din ProjectDetail (era
  instant fără plasă de siguranță → acum reversibil). Task/atașament păstrează ConfirmDialog-urile
  existente (deja au plasă). (3) **Ctrl+Enter / Ctrl+S salvează** în `RichTextEditor` (prop nou
  `onsave`; Ctrl+S nu mai moare degeaba) — legat în ProjectDetail (câmp + notițe task) și Tasks (notițe).

- **2026-07-03 — Șters complet backend Checklist PIF + Template-uri + Hermes AI** (SW v71):
  cod mort — backend complet fără niciun UI în SPA (confirmat zero referințe în frontend). Ion a
  ales ștergerea (peste #168, care le păstra „pentru Hermes viitor" — Hermes însuși e acum șters).
  **Șters:** `blueprints/assistant.py` (838L, tot Hermes + tools + memorie); rutele checklist
  (`/api/proiecte/<id>/checklist*` + `checklist-categorii`) și `/api/templates` +
  `init_default_templates()` din projects.py; `_pdf_section_checklist` + secțiunea checklist din
  export PDF (admin.py); ramura checklist din global_search; cele 4 tabele din backup/restore + din
  `VALID_TABLES` (utils.py). **Migration v22→v23** face `DROP TABLE IF EXISTS` pe `checklist_pif`,
  `checklist_categorii`, `project_templates`, `assistant_memory` + indexurile lor (SCHEMA_VERSION 23).
  `migrate_v4_to_v5` gardat pe existența `checklist_pif` (skip pe DB nou — altfel `ALTER TABLE
  checklist_pif` pica). Migrațiile istorice v1→v2 (creează `project_templates`) rămân — pe DB nou
  rulează apoi v23 le dă drop; NU re-adăuga aceste tabele în `init_db`. Restore ignoră silențios
  checklist/template/assistant din backup-uri vechi. Schema: 14→10 tabele. Snapshot/debrief nu mai
  au chei checklist. `app_settings` + `task_subtasks` PĂSTRATE (alte features). `scripts/llm_enrich*`
  (MiniMax pt enrich parametri) fără legătură cu Hermes — păstrat.

- **2026-07-03 — Faza 2 quick-wins (batch 2) — B3/B4/B5/B6** (SW v70): **B3** buton „Manual" +
  „Coduri erori" pe cardul echipamentului (ProjectDetail) → deschid PDF-ul drive-ului / fault-codes
  filtrate pe familie. Rezolver comun în `frontend/src/lib/manuals.js` (MANUAL_MAP mutat din Params +
  `familieForEquip` care replică `_familie_from_echipament` din backend + `manualUrlForEquip`). Params
  gestionează acum `/params?tab=faults&familie=<X>` (funcția `openFamilie` în `$effect`-ul de query).
  **B4** favorite + recente parametri (localStorage `pif-params-fav`/`pif-params-recent`, strip de
  chips deasupra tabelului + toggle stea în modalul de detaliu; `pushRecent` la deschidere). **B5**
  buton „Cameră" în AttachmentsTab (`<input accept="image/*" capture="environment">`). **B6** endpoint
  `GET /api/export/ics` (admin.py) — deadline-uri proiecte + scadențe taskuri/global_tasks ne-finalizate
  ca `.ics` (Response text/calendar), buton „Calendar (.ics)" în Admin > Export. Verificat: ICS 200 cu
  8 evenimente + diacritice; B3/B5 randează; B4 nu s-a putut testa UI local (parametri_master gol) dar
  compilează. **Gotcha:** kill TOATE procesele `app.py` înainte de restart în sandbox — un proces vechi
  pe portul 5000 servea cod vechi (ICS dădea 404).
- **2026-07-03 — Dock autohide v4: pur pe cursor (ascuns by default)** (SW v65, `Dock.svelte`):
  Ion a cerut explicit modelul simplu — dock-ul ASCUNS by default TOT timpul, apare DOAR cat timp
  cursorul e in zona de jos, se ascunde imediat ce iesi. Am scos toata logica de scroll (atTop/
  atBottom/scroller-detection — sursa de bug-uri) si dependenta de scroll: `hidden` porneste `true`,
  `apply()` = `hidden = kbLocked ? true : !inZone`, `inZone` din mousemove (`innerHeight-clientY <=
  130` apare / `>160` dispare). Ruta noua -> `hidden=true`. Mobil: manerul peek `revealFromPeek()`
  arata ~4s apoi ascunde. Verificat Playwright: la load (top) ascuns+peek, cursor mijloc ascuns,
  cursor jos apare, cursor sus ascuns, dupa nav din dock + cursor sus ascuns. (v3 arata si la top/
  capat de pagina — Ion NU voia asta.)
- **2026-07-03 — Dock autohide: fix `:focus-within` (cauza reala „nu se ascunde")** (SW v64,
  `Dock.svelte`): dupa v60 (scroller corect) userul tot spunea „nu face autohide". Cauza: regula
  CSS `.dock.hidden:focus-within { --dock-shift: 0 }` — cand navighezi CLICKAND pe un item din dock
  (nav-ul principal), link-ul `<a>` ramane focusat → `:focus-within` tinea dock-ul vizibil, deci NU
  se ascundea niciodata la scroll dupa o navigare din dock. Fix: sters regula `:focus-within` +
  `onclick={(e)=>e.currentTarget.blur()}` pe iteme. (Gotcha test: testele Playwright navigau prin
  `goto()`, nu prin click → nu prindeau bug-ul; iar viewport-uri mici / continut scurt faceau
  `atTop`/`atBottom` mereu true → falsa impresie ca „nu se ascunde". Verificat corect cu viewport
  1200×800 + continut inalt fortat: scroll 600 + cursor sus → hidden=true.)
- **2026-07-03 — Faza 2 quick-wins (batch 1)** (SW v63): **B1** — codurile de parametri din
  echipament (detaliu proiect) sunt clickabile → deschid detaliul din baza de parametri. Rezolvare
  cod→id prin `GET /api/search?q=<cod>` (ranking exact-pe-cod din `global_search`), apoi deep-link
  `navigate('/params?open=<id>')`; daca nu e in baza → toast. **B7** — buton de copy pe rand
  (`cod = valoare`, apare la hover / vizibil pe touch). **B8** — `shortcuts` in `manifest.json`
  (Astăzi / Taskuri / Calculator). Toate in `pages/ProjectDetail.svelte` (`openParamDetail`,
  `copyParam`, `.eparam-link`/`.eparam-copy`) + `frontend/public/manifest.json`. Ruta detaliu
  proiect = `/projects/:id` (hash). Local `parametri_master` e gol (0) → B1 cade pe toast; pe prod
  are ~14k, rezolva. Ramase din Faza 2: B3 (manual/coduri pe card echipament), B4 (favorite Params),
  B5 (foto camera atasamente), B6 (export ICS).
- **2026-07-03 — Glosar Rich/Extra: diacritizare completă + fix cheie BVR** (SW v61): agenții
  read-and-rewrite (unul per fișier) au produs în final versiuni curate și mai complete pentru
  `glossaryRich.json` (13558 diac vs ~9838 la pasa scriptată) și `glossaryExtra.json` (3807), cu
  diacritizatoare care tokenizează pe cuvinte (protejează `$...$` byte-for-byte și NU ating cheile).
  Verificat: formule identice (3614/101 segmente `$...$`), chei identice, JSON valid, 0 sedile, 0
  cuvinte lipite. **Bugfix:** v59 livrase din greșeală cheia `BVR__TESTMARKER` (probe de persistență
  scăpată de un agent, prinsă de `git add -A`) în loc de `BVR` — parametrul BVR nu avea detaliu în
  glosar; corectat. (Gotcha: nu face `git add -A` cât rulează agenți în background pe aceleași
  fișiere — pot lăsa artefacte. Verifică `git diff --cached` înainte de commit.)
- **2026-07-03 — Dock autohide v3 (reveal la cursor jos)** (SW v60, `Dock.svelte`): Ion voia ca
  dock-ul sa se ascunda la scroll si sa reapara DOAR cand duci cursorul in zona de jos (unde sta
  dock-ul), si sa se ascunda iar cand pleci cursorul. **Bug-uri gasite:** (1) v2 se ascundea doar la
  `speed>0.5px/ms` — prag prea strict, nu se ascundea niciodata la scroll normal cu mouse-ul;
  (2) **GOTCHA scroller:** desi `.app-content#main-content` are `overflow-y:auto`, in practica
  documentul creste liber si **fereastra** deruleaza (`window.scrollY`), nu `#main-content`
  (`scrollHeight==clientHeight` acolo). Verificat cu Playwright: wheel -> `window.scrollY` se
  schimba, `#main-content.scrollTop` ramane 0. Fix: `mcScrolls()` = foloseste `#main-content`
  DOAR daca chiar deruleaza intern, altfel `window`/`document.scrollingElement`. Model nou:
  `hidden = !(atTop || atBottom || inBottomZone)`; `inBottomZone` = mousemove `innerHeight-clientY <
  120` (reveal) / `>180` (leave). Listeneri pe `window` SI pe `#main-content` (scroll). Manerul peek
  ramane pt mobil (fara cursor).
- **2026-07-03 — Diacritice subsistem Calculator (partea 2)** (SW v59): completat diacriticele
  în `pages/Calculator.svelte`, `CalcApp.svelte`, `App.svelte` (404), `pages/Notes.svelte`,
  `lib/driveCalc.js` (1719 diac) și cele 3 overlay-uri de glosar `lib/glossary{Rich,Extra,Teorie}.json`
  (proza detaliată din modalul de termen). **Gotcha metodă:** agenții de tip read-and-rewrite pe
  fișiere JSON MARI (glossaryRich 1937L, Extra 2407L) au (a) intrat în buclă / s-au împărțit singuri
  în „segment files" throwaway fără reasamblare, și (b) au introdus MANGLE de spațiere („în acest"→
  „înacest", 287 în Rich!). Soluția fiabilă: `git checkout HEAD -- glossary*.json` (revert la ASCII
  curat) + o **pasă scriptată deterministă, space-safe** (regex pe valorile `def/teorie/practic/ia`,
  protejează `$...$` KaTeX, `WORD.sub` nu atinge spațiile) cu reguli de terminație (-ție/-ată/-ează/
  -ață) + map explicit de vocabular + conectori (in→în, si→și). **Gotcha unelte:** `grep -P "[\x{219}]"`
  și `\b` pe caractere unicode dau REZULTATE FALSE (zero-uri) pe acest build de grep — folosește
  ÎNTOTDEAUNA Python (`re` + `io.open(encoding='utf-8')`) pentru scanări de diacritice/mangle.
  Verificare: `json.loads` valid + 0 sedile (ş/ţ U+015E-0163) + 0 „în"+cuvânt lipite. Search-ul din
  Calculator are `fold()` insensibil la diacritice (map cu ș/ț/ş/ţ→ASCII) — cele 8 „sedile" din
  Calculator.svelte sunt acolo intenționat, nu text afișat.
- **2026-07-03 — Diacritice complete + DatePicker portal + Faza 1 audit** (backend): (1)
  diacritice comma-below (ș U+0219 / ț U+021B) pe TOT textul afișat din dashboard — reguli:
  NU se ating valorile `value:`, cheile de status/prioritate ('in_lucru', 'normal'…),
  `familie`/`producator` folosite ca chei, cheile localStorage, comentariile de cod;
  CommandPalette păstrează `keywords` ASCII + variante fără diacritice ca să nu strice
  filtrarea. (2) **Bug fix DatePicker**: `.dp-pop` (position:fixed) era prins în
  stacking-context-ul unui strămoș cu transform (tranziție pagină / `.arow:hover`) → cardul
  „URGENTE" îl acoperea. Fix: acțiune Svelte `use:portal` care ridică pop-up-ul la
  `document.body` (`DatePicker.svelte`); z-tooltip=3000 > z-modal=1000 → merge și în modale.
  (3) **Faza 1 backend** din audit: `parametri.py` guard `sqlite3.OperationalError` pe
  get_parametri / get_parametri_familii / parametri_audit (200 gol în loc de 500 pe DB fără
  seed); reorder_agenda (`tasks.py`) folosește `logger.exception` în loc de linia moartă;
  șterse rute moarte `/api/parametri/{search,bulk,by-producator}`, `/api/fault-codes/lookup`,
  `/api/import-params/preview` + importurile/constantele orfane (math, PRODUCATOR_FAMILII,
  parse_for_producator). (Deja livrate în fazele anterioare: backup/restore complet,
  rate-limit login 5/5min, href-whitelist XSS, guard atomic recurență, indexuri atașamente.)
- **2026-07-02 — Redesign complet „Bento"** (PR #11 + follow-up): temă nouă dark warm
  `#12100d` + amber `#ffb454` (tokens remapați, nume păstrate; `--accent-text` = ink `#1a1206`),
  fonturi self-hosted Inter / Space Grotesk (`--font-heading`) / JetBrains Mono (subseturi
  latin+latin-ext), **Dock plutitor** înlocuiește Sidebar + BottomNav + pagina `/more` (șterse).
  Layouturi noi: Proiecte=carduri, Detaliu proiect=rail sticky, Taskuri=urgente+agendă
  (`components/tasks/AgendaColumn.svelte`), Parametri=sidebar familii, Calculator=navigator
  module (accordion <940px), Admin=4 taburi. `--info` e violet (distinct de warning/accent),
  `in_asteptare` → `--purple`, serii grafic pe `--chart-1/2/3`. Login retemat (fonturile Geist
  au fost șterse). SW VERSION bump obligatoriu la fiecare livrare (v47 curent). Schițele care
  au fundamentat deciziile: `design/sketches/`.

- 2026-06-30: **Agenda fix — explicit plan beats the due-today auto-include.** `_AGENDA_WHERE` (blueprints/tasks.py) now applies the `data_scadenta == today` clause ONLY when the task is unplanned or planned for today; a task planned for another day (e.g. via "Mută pe mâine") leaves the board even though its deadline is today. Without this, moving a due-today task to tomorrow set `data_planificata` ahead but the deadline clause pinned it on today's board (reported bug). Backend-only change (no dist rebuild).
- 2026-06-30: **"Astăzi" daily-planner board on Home** (`frontend/src/components/TodayBoard.svelte` + `TaskPickerModal.svelte` + store `frontend/src/stores/agenda.svelte.js`), replacing Home's old read-only "Task-uri Azi" card. DECISION: planning is a SEPARATE dimension from the deadline — new column **`data_planificata`** (+ board-only `ordine_agenda`) on BOTH `tasks` and `global_tasks` (migration **v21**); planning actions only ever write `data_planificata`/`ordine_agenda`/`status` and NEVER touch `data_scadenta`, so a task can be due Friday but planned today without losing its termen. Backend (all on `tasks_bp`, blueprints/tasks.py): `GET /api/agenda/today` (unified global+project list: planned-today OR rolled-over `data_planificata < today & not done` OR `data_scadenta == today`, future-recurrence excluded like dashboard_home), `GET /api/agenda/candidates?q=` (not-done, NOT-planned-today, cross-project JOIN — the only place that lists tasks across all projects), `POST /api/agenda/reorder` (mixed `[{tip,id}]`, writes 1-based `ordine_agenda`). Each item carries a **`tip` = 'global'|'proiect'** discriminator. Relies on the existing `COALESCE(?, col)` partial-update in update_task/update_global_task: send `''` to clear, omit/`null` to keep. **Local-vs-UTC GOTCHA**: SQLite `date('now')` is UTC, so the client sends `?today=<local YYYY-MM-DD>` (`toLocaleDateString('en-CA')`) to every agenda route. Recurring spawn helpers intentionally do NOT copy `data_planificata` (next occurrence is born unplanned). **RESTORE GOTCHA**: `/api/restore` (admin.py) has hand-maintained INSERT column lists — updated tasks + global_tasks to include the 2 new cols, else a restore silently drops planned dates/order (backup uses `SELECT *`, auto-OK). Verified end-to-end via isolated DB copy (PIN-login + CSRF): quick-add, picker (global+project), schedule/move-tomorrow/move-date/remove, reorder, done — and confirmed `data_scadenta` is never mutated. NOT yet committed/deployed at time of writing; remember `cd frontend && npm run build` already done (dist regenerated).
- 2026-06-26: **GOTCHA — TWO service workers; only `static/service-worker.js` is served.** Flask `/service-worker.js` → `app.send_static_file('service-worker.js')` = `static/service-worker.js` (hand-maintained, was at v41). `main.js` registers `/service-worker.js`, so THAT is the live SW. The Vite build also emits `static/dist/service-worker.js` (from `frontend/public/service-worker.js`) but **nothing serves it** — it's effectively dead. So the cache-busting VERSION to bump on every frontend deploy is **`static/service-worker.js`** (now v42), NOT the dist one. (My earlier theme/logo/icon commits bumped the dist SW v1→v4 by mistake — harmless no-ops; the real reason those deploys still went live is the served SW is network-first on HTML + Vite content-hashes asset filenames, so new builds load regardless of SW version.)
- 2026-06-26: **Solid icons extended app-wide** (beyond nav). `NavIcon.svelte` renamed → **`components/ui/SolidIcon.svelte`** (general; `<SolidIcon name size class/>`, forwards `class`). Added solid icons: file, pencil, trash, clock, star, play, stop, check, cpu (+ the 7 nav). Migrated these Lucide outline → solid everywhere they appear: Pencil/Trash2/Clock/StickyNote(→`notes`)/Play across Tasks, ProjectDetail, Projects, Notes, Home, Header, RichTextEditor, AttachmentPreview, AttachmentsTab; Cpu(→`cpu`) on ProducatorPicker cards + Params header + Calculator; FileText(→`file`) on Params manuals/Notes/ProjectDetail; CalcIcon header + Star on Calculator. STATEFUL EXCEPTIONS kept correct: Calculator favorite toggle = solid star only when `isFav` else Lucide outline `Star`; `Square` stays Lucide outline for the unchecked checkbox in Projects (paired w/ `CheckSquare`) — only the timer STOP `Square` (Header/Home) became solid `stop`. KEPT Lucide outline by design: all small affordances (Plus, Paperclip, Chevron*, Search, X, Download/Upload, ExternalLink, Info, etc.) AND the whole **Admin page** (its icons are tiny inline/button markers, not decorative — solid would look heavy) AND `EmptyState icon={...}` illustrations. SW v42→v43. To add/adjust: edit `SolidIcon.svelte` ICONS map (24-grid, `fill=currentColor`, evenodd holes for transparent cutouts).
- 2026-06-26: **Solid navigation icons.** Lucide (`@lucide/svelte`) is outline-only, so solid nav icons are a custom local set: `frontend/src/components/ui/NavIcon.svelte` (`<NavIcon name size />`, `fill="currentColor"`, interior detail via `fill-rule="evenodd"` holes so cutouts are transparent on any bg). Names: home/projects/tasks/params/calculator/notes/admin (+ `menu` = stroke-only hamburger, no solid form). Wired into `Sidebar.svelte` + `BottomNav.svelte` (nav data now uses string `icon:` names, not Lucide components; `PanelLeft*` toggles stay Lucide). DECISION: solid is for NAVIGATION only — small action/affordance icons across the app (X, chevron, search, trash, plus) stay Lucide outline on purpose (solid affordance icons read worse; this matches how design systems split nav-vs-toolbar). SW VERSION v3→v4. To add a nav icon, add a path entry to NavIcon's `ICONS` map.
- 2026-06-26: **New logo/favicon — "ramp area-chart" mark** (replaced the inconsistent old set: a `P` letter favicon, a different lightning-bolt PWA icon, and the login's teal bolt). Concept: a Geist-blue rounded tile with a white accelerating curve + filled area under it + an operating-point dot (a VFD speed ramp — ties to the calculator's graphs). ONE SVG, reused everywhere: `frontend/public/favicon.svg` (`#0070f3` tile + white mark, the canonical art), URL-encoded copies in `frontend/index.html` apple-touch-icon + `frontend/public/manifest.json` (both 192/512 icons) + `templates/login.html` favicon. The in-app Sidebar mark (`Sidebar.svelte` `.brand-logo`) is the SAME curve scaled to a 32-grid using `var(--accent)`/`var(--accent-text)` so it follows the theme. Path (64-grid): area `M14 48 C27 48 30 40 33 30 S42 16 50 16 L50 48 Z` (fill white @0.3), curve same minus the `L..Z` (stroke white 5.5 round), dot `cx50 cy16 r5`. SW VERSION v2→v3. NOTE: login.html's `> pif` terminal wordmark + its separate teal/slate theme were left as-is (only its favicon updated) — full login re-skin to Geist is a pending follow-up.
- 2026-06-26: **Theme switched Everforest → Geist** (Vercel-style). All palette lives in `frontend/src/styles/tokens.css` (dark `:root`/`[data-theme=dark]` + `[data-theme=light]`): monochrome grayscale + Geist blue accent `#0070f3` (hover `#3291ff` dark / `#0761d1` light), dark bg `#000`/`#0a0a0a`/`#161616`, light bg `#fff`/`#fafafa`/`#f4f4f4`, text `#ededed`/`#171717`, border `#2e2e2e`/`#eaeaea`; success `#45a557` (kept a distinct green for status legibility, NOT authentic-Geist blue-as-success), amber service/warning, danger `#ff4d4f`/`#e00000`, info=accent blue. GOTCHA — hardcoded palette hexes lived OUTSIDE tokens.css and had to be hunted: `driveCalc.js` graph marker (`COL.op` → now `var(--info)`), `Chart.svelte` `.cd-w` + `Calculator.svelte` `.imp-eq-tag.warn` (→ `var(--service-accent)`), and the PWA/browser chrome in `frontend/index.html` + `calc.html` (theme-color + apple-touch-icon), `frontend/public/manifest.json` (bg/theme_color + 2 inline SVG icons), `frontend/public/favicon.svg`. Bumped service-worker `VERSION` v1→v2 to purge stale cache. NOTE: `static/login.css` is a SEPARATE teal/slate theme (never Everforest) — left untouched, out of scope. **Deploy reminder**: the app serves the built `static/dist/` — a token edit is invisible until `cd frontend && npm run build` regenerates dist, then commit BOTH source + `static/dist/`, push, server pulls. (This change was lost-not-live earlier precisely because it was edited locally but never built/committed/pushed.)
- 2026-06-24: **Engineering Calculator** — major feature, heavily expanded 19–24 Jun and previously **undocumented in memory** (this block is a retroactive backfill from git history; the feature predates the shallow-clone boundary so its birth date is unknown). A data-driven drive/motor calc engine. Code: `frontend/src/lib/driveCalc.js` (~4000 lines — the module registry; each module declares id/family/tier/title/fields[]/results[] with a LaTeX `tex` + a `calc(v,r)` fn), `frontend/src/lib/driveGlossary.js` (~484 glossary terms), `frontend/src/pages/Calculator.svelte` (in-dashboard UI). **Standalone public twin**: `frontend/src/CalcApp.svelte` + `frontend/src/calc-main.js` → builds to `static/dist/calc.html`, served by Flask `@app.route('/calc')` → `calc_public()` (app.py ~405) — just the calculator (no sidebar/projects/data), for sharing with colleagues. `/calc` is public but calls `/api/me` (app.py ~318) to show book extracts only when logged in; defaults to light theme. Formulas verified adversarially (workflows drive-calc-equations / -motor-types) against ABB Technical Guide Book No.7/8/9 + Chapman + Hughes; drive params from firmware manuals (ACS880/DCS880/G120/S120/DCM); LV only (400/690 V).
- 2026-06-24: Calculator graphs reworked to graph-paper style (minor/major grid, nice-number axes, sub/superscript axis labels) + interactive crosshair (reads x/y on hover), operating-point markers, theme-aware hatched zones with labels (constant-torque / field-weakening, safe/critical), 160-pt curve resolution, continuous interpolated cursor. Added 5 DC (c.c.) cards (excitation types, field circuit, commutation & armature reaction, thyristor form factor, braking) + 4 PIF cards (thermal motor protection IEC 60947-4-1, PE conductor & fault current IEC 60364-4-41, life-cycle cost LCC, coupling sizing); all formulas adversarially verified. Caveat: the commutation card applies to DC-drive context.
- 2026-06-23: Calculator gained a shared **"Date echipament"** panel (enter the nameplate once, reused across cards; electric-machines tab only) with import from drive backups. GOTCHA — drive param import codes, verified against REAL backups: **ABB group 99** (Pn=99.10, U=99.07, n=99.09, In=99.06, cosφ=99.11, f=99.08 — was wrongly 30.xx); **Siemens p03xx**; parse the numeric value out of strings ("220 kW"→220) and skip values ≤0. Validated on ACS880 + FML3 (13 SINAMICS drives). Siemens motor-data import auto-derives poles from f/n and computes power/cosφ/inertia/Rs. Also: full **S1–S10 duty regimes** (IEC 60034-1) with thermal-equivalent Pech + new thermal-life S10 (TL) card; deep-links from cards/terms to the exact figure/table page in the standard/manual PDF (#page anchors, each verified). An earlier in-modal SVG regime-diagram experiment was REVERTED (test rejected) — links to the real figure won instead.
- 2026-06-22: Calculator restructured from one flat "Comune" wall into 8 domain/task categories: Aplicatii (cross-cutting, sub-tabs per machine/process: pumps/fans/compressors/lifting/conveyors/winder/positioning), Masini electrice (sub-tabs per type + Transformatoare), VFD, Armonici, Instalatie, Termic, Utilitare — dense-card accordion + search with highlight/category badge; an `APP_OF` map keeps one home per card (no duplication). IEC/EN standards now ship as **local section extracts** under `private_docs/standards/`, generated OFFLINE by a one-off `_rich_build/` toolkit (Python/mjs scripts + `in/`/`out/` batches; extracted the on-topic SECTION not the cover/TOC, wrote `_std_anchors.json` for the deep-links). NOTE: that scratch toolkit (hardcoded `C:\Users\ion.ursu\My Drive\...` paths, never imported by Vite/shipped) was **removed from git on 2026-06-26** to de-noise `frontend/src/lib/` — to regenerate standards extracts, recover it from history before commit 26fd40d or rebuild it. New "Surse & standarde" in-app page. Applied corrections from a verification-research workflow (I0 no-load, motor contribution to Icc, imbalance %, L_dc on impedance) + 8 new PIF modules (insulation/PI, run-up vs stall, braking resistor, encoder offset, notch resonance, STO/SS1, water hammer, PID tuning).
- 2026-06-19: Calculator field titles render the symbol with KaTeX (subscript/superscript: U_dc, f_sw, U_ce0, η_p…) via a `symTeX(key)` heuristic+exceptions (validated on 229 keys); the whole title is ONE uniform link "symbol [unit] text" (same font/colour) that opens the source figure/PDF. A `MathText` helper renders inline KaTeX symbols homogeneously across notes/labels/subtitles/sources/glossary. Header bar removed from standalone `/calc` (only a floating theme toggle remains).
- 2026-06-18: Design-handoff UI deltas (from `PIF dashboard feedback.zip`). Home: 4 stat-cards → one unified `.kpi-bar` (grid 4-seg, mono colored values, border-subtle dividers; mobile 2×2). Active timer is now a `.timer-card` top-right of the greeting + a compact `.timer-chip` in `Header.svelte` (shown on every screen) — the old global `.gtb` bar in App.svelte was REMOVED (handoff decision B). Shared helpers added: `formatElapsed` (HH:MM:SS) in formatters.js, `stopActiveTimer()` (kind-dispatch) in timer store. Projects table: columns now Nume·Client·Tip·Status·Deadline — `Tip` is its own column (PIF=accent / Service=service-accent pill), `Producator` column removed (data kept). Tasks: removed "Finalizat" filter chip; status+priority badges fixed-width (min-width 62px, centered) for column alignment; titles single-line (ellipsis); row action buttons always-visible-but-faint (no opacity:0-until-hover). ProjectDetail prio-badge got the same fixed width. Verified live + 4-agent adversarial review = all faithful, 0 issues.
- 2026-06-17: Removed the entire LEGACY frontend (the Svelte SPA is now the ONLY frontend, responsive for mobile too). Deleted `static/app.js`, `static/style.css`, `static/core.js`, `static/mobile.js`, `static/mobile-app.css`, `static/lucide.min.js`, `static/manifest-mobile.json`, `templates/index.html`, `templates/mobile.html` (~1.37 MB). app.py: `_serve_frontend()` now always serves `static/dist/index.html` (no PIF_USE_DIST fallback); the `/m` route + `mobile()` were removed; `_asset_versions` slimmed to just `style_version`=hash(login.css) (the only remaining server template is `login.html`). `static/service-worker.js` STAYS (Svelte registers `/service-worker.js` in main.js) — APP_SHELL trimmed to `['/']`, VERSION bumped v40→v41. Also deleted dead scripts `scripts/build.py` (Vite replaced it) + `migrate_obsidian.py`. KEPT: login.html, static/login.css, static/manifest.json, static/service-worker.js.
- 2026-06-17: AUDIT — checklist (`checklist_pif`/`checklist_categorii`) and `project_templates` were flagged as "unused" but are deeply woven (~130 refs): project delete-cascade, Cowork `/snapshot` + `/import/debrief`, PDF/Excel exports, admin stats/search, backup/restore, and (checklist) the Hermes assistant tools. DECISION: keep both for now — removal is a risky cross-cutting refactor and checklist feeds the planned deeper Hermes AI integration. The dead HTTP endpoints (no UI) are harmless since the legacy UI that used them is gone.
- 2026-06-16: Project tasks (ProjectDetail) had no way to edit the title (only priority/timer/delete). Added inline rename: a `.task-edit` pencil in `.task-actions` → `startRename(t)` swaps `.tmain` for a `.trename` input (bound to `editTaskTitle`, `use:focusSelect` auto-focus+select); Enter/blur → `saveRename` (guards `editTaskId===t.id`, skips if unchanged, calls `updateTask(id,{titlu})` + reloadTasks), Esc cancels. Global Tasks already had a full edit modal — this is the lighter project-task equivalent.
- 2026-06-16: Mobile task rows were too tall — `.task-actions` (`flex-shrink:0`, up to 6 buttons on global tasks) squeezed `.tmain` into a narrow column so long titles wrapped into a tall stack. Fix (Tasks + ProjectDetail, in the `@media (max-width:768px)` block): `.trow { flex-wrap:wrap; align-items:flex-start }` + `.task-actions { flex-basis:100%; justify-content:flex-end }` so the title takes the full first row and the action bar drops to its own line. ProjectDetail's 3 action buttons were wrapped in a new `.task-actions` div to match. Can't get a real mobile viewport via the controlled browser (innerWidth stays 1912) — verify by injecting the mobile rules + a 390px container.
- 2026-06-15: Removed the Budget Tracker feature entirely. Deleted `blueprints/budget.py` (the `/budget/*` blueprint), the legacy vanilla SPA `static/budget/*`, the Svelte page/store/components (`frontend/src/pages/Budget.svelte`, `frontend/src/stores/budget.svelte.js`, `frontend/src/lib/budget-calc.js`, `frontend/src/components/budget/*`), and budget scripts (`dump_budget_state.py`, `sync_budget_from_server.py`, `test_budget_conflict.py`, `verify_budget_deploy.py`, `verify_budget_v2.py`). Removed all integration points: blueprint registration in `app.py`, the `/budget` route + nav entries (Sidebar, BottomNav, More, CommandPalette), the `/budget/api` vite proxy, and `/budget/*` handling in both service workers. Dropped `budget_state`/`budget_audit` (+ `prune_budget_audit` trigger, index) from `init_db` and added **migration v19→v20** to drop them on existing DBs; bumped `SCHEMA_VERSION` to 20. `upload_db.py` no longer pre-pulls budget tables. NOTE: historical migrations v4 (creates tables) and v12 (creates trigger) are left intact — on a fresh DB they run then v20 drops them; never re-add budget table creation to `init_db`.
- 2026-06-13: `task_subtasks` is shared by BOTH project tasks (`tasks.id`) AND global tasks (`global_tasks.id`) — same `task_id` column. The v14 migration wrongly added `FOREIGN KEY task_subtasks.task_id REFERENCES tasks(id)`, so adding a subtask to a GLOBAL task 500'd (FK violation; global ids aren't in `tasks`). Migration v19 drops that FK (table rebuild). Orphan cleanup stays in app code (`delete_task`/`delete_global_task`). Never re-add an FK on `task_subtasks.task_id`.
- 2026-06-13: Display math (`$$...$$`) is left-aligned (`.rich-content .katex-display { text-align:left }`) — KaTeX centers by default, which looked inconsistent next to left-aligned text/tables. RichText gained `collapsible`+`maxHeight` props: clamps tall content with a bottom fade (`--rt-fade` CSS var per context: notes=var(--bg), observatii field-body=var(--bg-surface)) + an "Arata tot/Restrange" toggle; measures overflow via scrollHeight in $effect + rAF. Notes maxHeight 200, observatii 240.
- 2026-06-13: Observatii/notes are paste-and-render (user copy-pastes finished tables + equations, wants the final rendered version always visible — no formatting). Sanitizer (`storedText.js`) now keeps TABLE/THEAD/TBODY/TR/TD/TH/CAPTION/COL + colspan/rowspan. Global `.rich-content` styles (in `global.css`) render tables + KaTeX everywhere RichText is used. Read views are now selectable `<div>`s (not buttons) with an in-flow "Editeaza" button UNDER the note (`.note-block`/`.note-edit-btn`; observatii edit via existing field-header pencil). GOTCHA: do not absolute-position the edit button over the RichText — RichText's root is `position:relative` and paints later (DOM order), so an absolute top-right pencil sat at the far right of the full-width note and was unclickable; in-flow under the content is robust + better UX. RichTextEditor stripped to a paste box + Eye/Pencil preview toggle (no bold/heading/list buttons) and now imports renderStoredText from storedText (deduped). GOTCHA: a `class` prop passed into a child component (RichText) is NOT covered by the parent's scoped CSS — `.note-content` had to move to global.css.
- 2026-06-13: LaTeX/math in observatii + task notes via bundled KaTeX (npm `katex` 0.17, +mhchem for `\ce{}` chemistry). New `lib/math.js` (`renderMath` = katex auto-render: `$...$`/`$$...$$`/`\(\)`/`\[\]`) + `components/ui/RichText.svelte` (read-only display: sets innerHTML=renderStoredText then renderMath, reactive via $effect). RichText replaced all `{@html renderStoredText}` read views (ProjectDetail observatii/service_before/service_after + task note-preview on both pages). RichTextEditor got an Eye/Pencil preview toggle (renders current value with KaTeX in-modal). Fonts bundle to static/dist/assets (same-origin → existing `font-src 'self'` covers; no CSP change). KaTeX lives in the RichTextEditor chunk (~312KB/92KB gz).
- 2026-06-12: Attachment click opens a preview modal instead of a new tab. Shared `components/ui/AttachmentPreview.svelte` (image=`<img>`, PDF=`<iframe>`, other=icon+download). Used by AttachmentsTab + task chips (Tasks + ProjectDetail). Modal now has an optional `footer` snippet (rendered as `.modal-footer`, flex-shrink:0 outside the scrolling `.modal-body`) — preview actions live there so they stay fixed. GOTCHA: global `after_request` sets `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'`, which block ALL iframes incl. same-origin → PDF preview was blank (broken-doc icon). Fix: `download_atasament` sets `X-Frame-Options: SAMEORIGIN` + CSP `frame-ancestors 'self'` on its own response (after_request uses setdefault, so route values win). Images use `<img>` so they were never affected.
- 2026-06-12: Per-task attachments via migration v18: `atasamente` rebuilt with nullable `proiect_id` + `task_id`/`global_task_id` (FK CASCADE). Project-task files keep `proiect_id` set (visible in project Atasamente tab too); global-task files go to `uploads/global-tasks/<id>/`. Endpoints in projects.py reuse `_store_uploaded_file()`; task DELETE endpoints remove files from disk. UI: paperclip chips + count badge in expanded row, both pages.
- 2026-06-12: Task notes upgraded to Observatii concept: rendered preview (max-height+fade) in expanded row + WYSIWYG RichTextEditor modal. Shared helpers extracted to `frontend/src/lib/storedText.js` (sanitizeHtml/renderStoredText — ProjectDetail now imports from there). Fixed pre-existing RichTextEditor `plainToHtml` bug (escaped its own `<br>` tags — affected legacy plain-text in Observatii too).
- 2026-06-12: Task notes = the existing `descriere` column, edited inline in the expanded task row (click text / "Adauga notite..."), on both Tasks page (snippet, active+done) and ProjectDetail. No new table/endpoint; PUT COALESCE accepts '' to clear.
- 2026-06-12: Inline quick-add for tasks (global + project): form under toolbar on Tasks (hidden in Arhiva view), ProjectDetail single-field "Task Nou" modal replaced by inline form. Backend untouched (endpoint defaults cover prioritate/categorie/status).
- 2026-06-11: Added versioned pre-commit hook (`.githooks/pre-commit`) that auto-regenerates CODE_MAP/API_MAP when relevant code is committed; activation per clone via `git config core.hooksPath .githooks`.
- 2026-06-11: Created persistent memory system (`scripts/gen_memory.py` → `docs/memory/`); CLAUDE.md updated to point here; fixed stale migration count (v14 → v17).
- 2026-07-02: **Removed timer & jurnal features entirely** (Ion: orele se ponteaza in e100, softul intern; jurnalul se scrie in observatiile proiectului). Deleted `blueprints/timer.py` + registration, jurnal routes in projects.py, `stores/timer.svelte.js`, timer/jurnal UI in Header/Home/ProjectDetail/Tasks, jurnal in CommandPalette search + /api/search, ore/jurnal in snapshot + exportMd + PDF/Excel exports + backup/restore. Debrief import now folds `jurnal[]` into observatii/service_after and IGNORES `ore[]`. **Migration v21→v22** drops `jurnal`, `timer_sessions`, `global_task_sessions` (SCHEMA_VERSION 22); v2/v8/v17 migrations gated on table existence for fresh DBs; NEVER re-add these tables to `init_db`. Home KPI "Ore Saptamana" → "Finalizate — 7 zile" (`weekly_done`/`weekly_done_delta`/`weekly_spark` = COUNT of tasks+global_tasks cu data_finalizare in fereastra, per zi). Observatii scos din ProjectFormModal (se editeaza doar in Detaliu proiect, rich text); update foloseste COALESCE deci lipsa cheii pastreaza valoarea.
- 2026-07-02: Deploy note: webhook-ul de autodeploy pentru merge-ul PR #13 s-a pierdut (pana de curent la server in momentul livrarii; GitHub nu re-livreaza singur). Re-declansat printr-un push+merge nou. Daca se repeta: Settings -> Webhooks -> Recent Deliveries -> Redeliver, sau POST /api/deploy cu Bearer PIF_API_TOKEN.
- 2026-07-02: **RichTextEditor rescris ca WYSIWYG unic** (cerinta Ion: "ca un Word, fara moduri read/edit, cu headbar de tooluri"). Un singur mod: toolbar execCommand (undo/redo, select stil P/H1/H2/H3/citat, B/I/U/S, UL/OL, citat, HR, curatare format) + buton Σ care deschide o bara de formule (input LaTeX mono + preview live + toggle Bloc). Formulele traiesc in editor ca chip-uri necontenteditable `.mchip` (KaTeX renderToString, sursa in data-tex); click pe chip = editare; `$...$`/`$$...$$` tastate se convertesc automat (heuristica: inline fara spatii la margini, ca sa nu prinda preturi in dolari). La serializare chip-urile redevin text `$...$` + sanitizeHtml — formatul stocat NEschimbat (HTML + delimitatori KaTeX), compatibil cu RichText/PDF/exporturi. Consumatori: ProjectDetail (observatii/service + notite task) si Tasks (notite task) — acelasi component, zero schimbari la ei.
- 2026-07-02: **Observatii V1 "Document"** (alegerea lui Ion dintre 3 variante propuse). Field-section pe ProjectDetail = "coala": gradient cald (accent 5% -> bg-surface), radius-lg + shadow-md, antet cu chip iconita (.f-ico amber / .f-red / .f-green la Service) + meta mono "actualizat {updated_at}" + border dashed; butonul "Arata tot" al RichText centrat. Editorul (observatii + notite task, ProjectDetail si Tasks) se deschide in Modal `size="doc"` (900px, 92dvh; pe mobil sheet 100dvh fara padding via `.backdrop:has(.modal-doc)`) cu RichTextEditor `variant="doc"`: fara chenar, .rte e scrollerul, toolbar pill sticky centrat (blur + shadow), math-bar sticky sub pill, coloana text max-width 74ch centrata, fara footer intern (footerul modalului are Anuleaza/Salveaza).
- 2026-07-02: **Batch omogenizare (feedback Ion)**: (1) Select.svelte rescris ca dropdown CUSTOM (trigger buton + meniu pe tema, check amber, tastatura; API compatibil — onchange primeste {target:{value}}); meniul nativ alb de <select> era neomogen. (2) Editorul are dropdown de stil custom (aceeasi reteta; toolbarul e flex-wrap, NU overflow-x — meniul absolut ar fi taiat). (3) Sortare Proiecte = pill ghost "⇅ Nume ↑" cu meniu; click pe optiunea activa inverseaza directia. (4) Chip "Finalizat" scos din Proiecte (arhiva de jos acopera); Taskuri doar Active|Arhiva (fara Toate/To Do/In Lucru; statusFilter sters). (5) PRIO_CYCLE = normal→urgent→minor (Tasks + ProjectDetail). (6) Countere (.count paginile toate + .tab-count detaliu) = disc accent-subtle 24px mono cu inel. (7) Field observatii/service: intreaga coala e clickabila -> deschide editorul; fara creion si fara "Arata tot" (RichText prop noToggle = clamp+fade fara buton). (8) Home fara sectiunea "Continua". (9) Params detaliu: toate sectiunile ca "Explicatie" (accent-subtle + chenar accent).
- 2026-07-02: **Randuri "insule" V3+V2** (alegerea lui Ion; a respins bara colorata din stanga). Reteta comuna pentru TOATE listele de taskuri (Home urgente + deadline-uri, TodayBoard .arow, Tasks .trow, ProjectDetail .trow): rand = insula (bg-panel, border, radius-md, gap 6px, hover translateX(4px)) cu `--sev` inline (priorityColor sau severitate deadline) care coloreaza (a) underline scurt 40px pe muchia de JOS (::after, glow color-mix) si (b) indexul mono ghost `.tix` ("01") din stanga. Pe Home: sev(deadline) = depasit->danger, azi/maine->accent-hover, rest->border-strong; chip mono dueChip() ("azi"/"maine"/"depasit · data"). Fara border-left nicaieri.
- 2026-07-02: **Cautare globala pe coduri + Dock autohide v2 + fixuri**. (1) /api/search: parametri/fault ranked pe COD (exact > prefix > contine > doar-descriere), gardat cu OperationalError; query care arata ca un cod (regex ^[A-Za-z]{0,2}\d+([.\-_]\d+)?$) urca grupurile Parametri+Coduri primele. CommandPalette: parametru/fault_code -> /params?open=<id>[&tab=faults]; Params are $effect pe router.query.open care deschide modalul de detaliu + aliniaza nav-ul pe familie, apoi applyPath('/params') curata query-ul. FIX paletta: Enter pe selectia initiala (header de grup) activeaza primul rezultat real. (2) Dock v2: se ascunde DOAR la scroll rapid (speed>0.5px/ms + acc>24); revine la idle 1s / capat de pagina (scrollY+inner>=scrollHeight-40) / schimbare ruta / maner .dock-peek (pill 36x5, doar cand hidden && !kbLocked); pe mobil focusin pe camp editabil -> kbLocked (dock+peek ascunse pana la blur); dragstart/dragend global suprima hide in timpul reordonarii. Pe desktop mousemove-proximity readuce dock-ul inainte sa apuci sa dai click pe peek — intentionat. (3) FIX: overflow:hidden scos de pe insulele .arow/.trow — taia popup-ul DatePicker din Astazi. (4) Countere micsorate: .count 19px/font-micro/line-height 1, .tab-count 17px.
