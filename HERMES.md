# HERMES — briefing pentru agenții care lucrează la PIF Dashboard

> Document de briefing pentru ORICE agent (sesiuni Claude, asistentul in-app, orice
> automatizare) care intră în repo. Citește-l până la capăt înainte de prima modificare.
> Conține: actorii, arhitectura SPA actuală, design system-ul, protocolul anti-coliziune
> și gotcha-urile de deploy. Pereche cu `CLAUDE.md` (instrucțiuni de proiect) și
> `docs/memory/` (memory curat + hărți auto-generate).

> **Istoric:** până la 2026-06-17 aplicația era un app vanilla-JS multi-fișier
> (desktop `templates/index.html` + `static/app.js`, mobile PWA `/m` cu `mobile.html`/
> `mobile.js`). Tot acel strat a fost ȘTERS. Azi e un singur **SPA Svelte 5**, responsive
> (acoperă și mobilul). Dacă vezi pe undeva referințe la `app.js`, `mobile.*`,
> `index.html`, `/m`, markere `BEGIN/END` pe fișiere shared — sunt fosile, ignoră-le.

---

## 1. Actori

- **Ion** — single user, owner repo + owner laptop-server care expune `https://pif.iupif.org`
  prin Cloudflare Tunnel. Git identity `Urs1470 <Urs1470@users.noreply.github.com>`.
- **Sesiuni Claude** (Claude Code pe Windows-ul lui Ion, `C:\Users\ion.ursu\pif-dashboard`)
  — fac majoritatea modificărilor. Commit cu author Ion (`Urs1470`), co-author Claude.
  **Pot rula mai multe în paralel pe ACELAȘI worktree** → vezi §4 (coliziuni reale).
- **Hermes (asistentul in-app)** — feature din aplicație, `blueprints/assistant.py`
  (gateway MiniMax). Nu e un agent care editează repo-ul; e funcționalitate livrată.

---

## 2. Topologie & deploy

- **Repo**: `https://github.com/Urs1470/pif-dashboard` (private), branch principal `master`.
- **Worktree dev (Windows)**: `C:\Users\ion.ursu\pif-dashboard` — aici lucrează Claude.
- **Laptop-server (Linux)**: `/home/ion-ursu/Projects/pif-dashboard` — rulează aplicația.
  Detalii host/SSH/service în `CLAUDE.md` → secțiunea *Server*.
- **Deploy**: `git push origin master` → webhook `POST /webhook/deploy` (handler
  `webhook_deploy` în `app.py`, validează `X-Hub-Signature-256` față de `.deploy_secret`)
  → `git pull` + `sudo systemctl restart pif-dashboard`. ~5–10s până e live.
- **DB**: `pif_dashboard.db` (SQLite WAL), **gitignored**, doar pe server. Backup `backup_db.py`.

**Failure mode critic (deja întâlnit):** dacă worktree-ul de pe server e *dirty* când
lovește webhook-ul, `git pull` eșuează și endpoint-ul dă 500. Push-urile ulterioare se
acumulează pe GitHub fără să ajungă pe server. Regulă: **ține worktree-ul de pe server curat**
(`git status` → `working tree clean`). Re-trigger manual din GitHub → Settings → Webhooks →
Recent Deliveries, sau `git pull` pe server.

---

## 3. Arhitectură (SPA actual)

**Frontend — `frontend/` (Vite + Svelte 5), build în `static/dist/`:**

```
frontend/src/
  main.js              # entry SPA (mount App, înregistrează /service-worker.js, PWA install)
  App.svelte           # root: layout + <slot> pe ruta curentă
  calc-main.js         # entry SEPARAT pentru calculatorul public (/calc)
  CalcApp.svelte
  lib/
    router.svelte.js   # hash router (rune); rutele SPA
    api.js             # fetch wrapper + CSRF + cache (înlocuiește vechiul apiGet/apiPost)
    math.js, markdown.js, formatters.js, driveCalc.js, driveGlossary.js, ...
  stores/              # Svelte 5 rune stores (.svelte.js): ui, projects, tasks, timer, params, agenda
  pages/               # Home, Tasks, Projects, ProjectDetail, Params, Notes, Admin, More, Calculator
  components/
    ui/                # librăria de componente: Button, Card, Badge, Input, Select, Modal,
                       #   ConfirmDialog, Toast, DatePicker, SolidIcon, Chart, RichTextEditor,
                       #   Formula, MathText (KaTeX), Skeleton, EmptyState, AttachmentPreview
    layout/            # Header, Sidebar, BottomNav, CommandPalette
    projects/, params/, notes/, admin/   # componente per-domeniu
  styles/
    tokens.css         # SINGURA sursă de adevăr pentru paletă/spacing/typography (vezi §5)
    global.css, reset.css
```

**Backend — Flask (vezi `CLAUDE.md` → Architecture pentru harta completă):**
`app.py` (entry, auth, CSP, rate-limit, webhook) + `blueprints/` (projects, tasks, timer,
parametri, obsidian, assistant, admin) + `database.py` (schemă + migrații) + `utils.py`,
`csrf.py`, `labels.py`. Singurul template server-rendered rămas: `templates/login.html`.

**Parsers parametri:** `scripts/parse_params/*.py` (abb, danfoss, lenze, siemens, siemens_starter).

> Pentru locații exacte (linie:funcție / rută) folosește hărțile auto-generate din
> `docs/memory/CODE_MAP.md` și `docs/memory/API_MAP.md` (regenerate la fiecare commit
> de hook-ul `.githooks/pre-commit`). NU căuta în fișiere mari pe orbește.

---

## 4. Reguli Git & anti-coliziune (NU le rupe)

**Mai multe sesiuni Claude pot rula pe același worktree Windows → ACELAȘI `.git`, ACELAȘI
index.** Asta înseamnă coliziuni reale:
- Modificările necommit-ate ale unei sesiuni sunt vizibile în working tree-ul celeilalte.
- Ce stage-ezi (`git add`/`git rm`) intră în indexul **partajat** — un `git commit -a` sau
  `git add -A` al celeilalte sesiuni îți poate înghiți modificările.

**Protocol:**
1. **La început** și **înainte de fiecare push**:
   ```bash
   git fetch origin master
   git pull --rebase origin master
   git log --oneline -10
   git status            # vezi exact ce e în tree/index
   ```
2. **Nu folosi `git commit -a` / `git add -A`** dacă tree-ul nu e clar al tău — stage
   explicit doar fișierele tale, ca să nu prinzi munca altei sesiuni.
3. **Push imediat** după fiecare felie funcțională. Cu cât stau modificări nepushate, cu
   atât crește riscul de suprapunere.
4. **NU force push. NU rescrie istoria** pe `master`.
5. **Dacă vezi că altă sesiune scrie activ** (fișiere modificate la secundă, commit-uri în
   ultimele minute) → oprește-te, las-o să termine/commit-eze, apoi `pull --rebase`.
6. Commit messages: scope clar (`<zonă>: ce ai făcut`), author Ion + co-author Claude.

**Suprafața de coliziune azi e mai mică** decât pe vechiul app (componentele Svelte sunt
fișiere separate). Hub-urile unde două sesiuni se pot ciocni: `App.svelte`,
`lib/router.svelte.js`, `stores/*`, `styles/tokens.css`/`global.css`, `app.py`,
`database.py` (migrații). Pe astea, fii mic și rapid și `pull --rebase` înainte de push.

---

## 5. Design system (respectă-l — NU stiluri ad-hoc)

**Sursa unică de adevăr: `frontend/src/styles/tokens.css`.** Citește-l înainte să atingi CSS.
Estetica e **Geist** (Vercel-like): negru pur + albastru. Două teme (`[data-theme="dark"]`
default și `[data-theme="light"]`), ambele definite în tokens — dacă atingi culori,
păstrează ambele.

**Paletă (dark, valori actuale):**
- Accent (identitate PIF): `--accent #0070f3`, hover `#3291ff`, `--accent-subtle`, `--accent-ring`;
  text pe fundal subtle → `--accent-on-subtle #3291ff` (nu `--accent`, pică AA)
- Service: `--service-accent #f5a623`; secundar `--purple #8e6fff`
- **Scară de suprafețe (elevație)** — folosește token-ul potrivit rolului, nu unul la întâmplare:
  `--bg #050505` (pagină, near-black anti-OLED-smear) < `--bg-surface #0a0a0a` (card) <
  `--bg-panel #141414` (panou nested în card) < `--bg-input #161616` (input/chip/th) <
  `--bg-overlay #1c1c1c` (modal/toast/palette/popover). `--bg-hover #1f1f1f`, `--bg-active #2a2a2a`.
  (`--bg-elevated` = alias legacy pe `--bg-input`.)
- Text (contrast AA-safe): `--text #ededed`, `--text-secondary #a1a1a1`, `--text-dim #8f8f8f`,
  `--text-faint #7a7a7a`
- Borders: `--border #2e2e2e`, `--border-subtle #1f1f1f`
- Semantic: `--success #45a557`, `--warning #f5a623`, `--danger #ff4d4f`, `--info #0070f3`
- Elevation → shadow: card `--shadow-sm`, popover `--shadow-md`, modal/toast `--shadow-lg`.

**Scale noi (folosește token, nu valori hardcodate):**
- Font-weight: `--fw-normal/medium/semibold/bold` (400/500/600/700).
- Line-height: `--lh-tight 1.15` (display/headings), `--lh-normal 1.55` (body).
- Tracking: `--tracking-wide 0.04em` (default uppercase), `--tracking-wider 0.08em` (th mici).
- Font-size: în plus față de h1..tiny — `--font-display 1.875rem` (cifre KPI/stat), `--font-micro 0.65rem` (label-uri uppercase).
- Spacing: pe lângă t-shirt, punțile `--space-12/20/40`. Card padding: `--card-pad` / `--card-pad-compact`.
- Focus: `--focus-ring` (reutilizat de inputuri + regula globală `:focus-visible` din global.css). Touch: `--tap-min 44px`.
- Tabele: `.data-table th` sunt sticky; coloane numerice → clasă `.num` (dreapta + tabular). Pe mobil `.data-table.reflow` devine carduri (label via `data-label`). Densitate mare → `.data-table.zebra`.

**Tipografie:** `--font-sans` = **Plus Jakarta Sans** (body), `--font-mono` = **JetBrains Mono**
pentru ORICE cifră / cod / valoare numerică / parametru. (Notă: migrarea la fontul *Geist Sans*
există doar în branch-ul nemergeat `theme-wip` — în `master` body-ul e încă Plus Jakarta.)

**Iconițe — hibrid (vezi `components/ui/SolidIcon.svelte`):**
- `<SolidIcon name="..." />` — set custom **solid/filled** pentru navigație + iconițe de
  feature/acțiune care arată bine pline (home, projects, tasks, params, file, pencil, trash,
  clock, play, stop, check, ...). Culoare via `currentColor`.
- Iconițele mici de afordanță (plus, chevron, search, x, paperclip, download) rămân
  **Lucide outline**. Zero emoji în UI (emoji din DATA = conținut, e ok).

**Componente — folosește librăria `components/ui/`, nu reinventa:**
- Dropdown: `<Select>` (NU `<select>` native stilizat ad-hoc, NU vechiul `enhanceSelect`/`cs-enhance`).
- Text: `<Input>` / `<Textarea>` (au hover + focus-ring + error/aria-invalid; NU `<input>`/`<textarea>` brut).
- Date: `<DatePicker>` (NU `<input type="date">` native, NU flatpickr).
- Dialoguri: `<Modal>` / `<ConfirmDialog>`; feedback: `<Toast>`; goluri: `<EmptyState>`; erori: `<ErrorState>` (cu retry); încărcare: `<Skeleton>`.
- Formule: `<Formula>` / `<MathText>` randează LaTeX cu KaTeX.
- **Butoanele de acțiune ale unui Modal** merg în `{#snippet footer()}` cu `<div class="modal-actions">`
  (rămân fixate sub scroll, cu separator) — NU în corpul modalului.
- **Tab-uri underline**: clasele partajate `.tabs`/`.tab`/`.tab.active` din `global.css` (ProjectDetail, Params).
  Categoriile din Calculator (`.fam-tab` pill) sunt un pattern distinct, intenționat.

**Service worker / cache-busting:** SPA înregistrează `/service-worker.js`
(`static/service-worker.js`, servit de `app.py`). La livrare de assets noi, bump versiunile
de cache din service-worker (activate-event șterge cache-ul vechi). Vite hash-uiește deja
bundle-urile din `static/dist/assets/`.

---

## 6. Convenții de date (parametri)

- **Sortare:** default **ASC by cod natural** (`localeCompare` cu `{ numeric: true }`).
  Backend sortează deja `ORDER BY familie, parametru`. Nu introduce DESC by id / created_at.
- **8 familii drive** în `fault_codes` + parametri: ABB (ACS580, ACS880), Siemens
  (G120, G130_G150, S120_S150), Danfoss (FC302), Lenze (i550, i950).
- **Explicații parametri** (câmpuri LLM): română **fără diacritice**, 2–3 propoziții,
  commissioner-friendly, accuracy-first — derivate din descrierea din manual, niciodată
  inventate. Formule electrotehnice în LaTeX inline `$...$` (randate KaTeX): variabile cu
  indici `$T_n$`, fracții `$\dfrac{a}{b}$`, unități în `\text{}` cu `\,`, `\cdot` pentru
  înmulțire. NU LaTeX pentru valori simple (`30.12`, `1500 rpm`).

---

## 7. Gotcha-uri cunoscute

- **Worktree dirty pe server → webhook deploy 500** (vezi §2). Cel mai frecvent mod de a
  „rupe” deploy-ul fără să rupi cod.
- **SQLite nu are REGEXP** built-in — folosește `LIKE` sau regex Python post-fetch.
- **Service Worker cache-uiește agresiv** — bump versiunile la deploy de assets noi, altfel
  userii primesc versiunea veche până la următoarea încărcare.
- **Cloudflare Tunnel poate cădea independent** (eroare 1033) — nu e cod-related; Ion face
  `sudo systemctl restart cloudflared`.
- **PIN** doar prin env `PIF_DASHBOARD_PIN`. Niciodată în repo. La fel `.deploy_secret`,
  `.secret_key`, `.env`, `.assistant_config` (toate gitignored).
- **CSP** folosește `unsafe-inline` (limitare cunoscută, vezi `CLAUDE.md`).

---

## 8. Comunicare cu Ion

- Mesaje **scurte, directe, în română**. Fără introduceri de complezență — direct la subiect.
- La final raportează concret: ce fișiere ai schimbat, ce ai testat, ce mai rămâne.
- Întrebări cu opțiuni clare (A / B / C) — Ion alege.
- Dacă nu ești sigur de scope, **întreabă înainte** — task-urile mari greșite costă tokeni.

---

*Document menținut în repo. Update-ază-l când arhitectura sau design system-ul se schimbă
semnificativ. Pereche cu `CLAUDE.md` și `docs/memory/`.*
