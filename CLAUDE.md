# PIF Dashboard

Aplicatie de organizare si monitorizare a proiectelor de punere in functiune, pentru un
singur utilizator (Ion). Flask + SQLite in spate, SPA Svelte 5 in fata, PWA + aplicatie
Android „Torqa". Live la `pif.iupif.org` prin Cloudflare Tunnel.

## Pull FIRST — inainte de orice task

Ruleaza `git pull --rebase origin master`. Repo-ul se modifica de pe alte masini si din alte
sesiuni (pe 2026-07-16 o clona locala era 93 de commituri in urma, iar codul nu se potrivea
cu API-ul live). **Exceptie:** daca arborele e murdar, raporteaza intai — nu trage peste
modificari necomise.

## Unde cauti

| intrebare | fisier |
|---|---|
| ce coloane are tabela X | `docs/memory/DB_MAP.md` — **generat** din baza |
| ce rute exista | `docs/memory/API_MAP.md` — **generat** din decoratori |
| unde e functia Y | `docs/memory/CODE_MAP.md` — **generat** |
| harta, starea, capcanele | `docs/memory/MEMORY.md` |
| cum scriu corect pe API | `SCHEMA_REFERENCE.md` |
| **de ce am facut asa** | `docs/decizii/INDEX.md` (105 decizii, cu carlig fiecare) |
| ce culoare/marime/durata | `frontend/src/styles/tokens.css` — sursa unica |

Cele trei harti se regenereaza la fiecare commit care atinge cod Python. Activeaza hook-ul
o data per clona: `git config core.hooksPath .githooks`.

## Arhitectura

```
app.py              # intrare Flask, auth PIN, CSP, rate limit, webhook deploy
database.py         # schema v40, migrari v1-v40 idempotente, WAL
utils.py            # login_required, UUID, app_settings, norm_date
csrf.py labels.py   # CSRF double-submit; etichetele de status

blueprints/
  projects.py       # /api/proiecte/* — CRUD, perioade, snapshot, import debrief, export
  tasks.py          # taskuri de proiect + globale + subtaskuri + agenda + /api/plan
  admin.py          # /api/calendar, /api/search, /api/stats, export ICS/PDF, backup
  obsidian.py       # citeste vault-ul si scrie frontmatter inapoi in el
  push.py           # Web Push: o notificare pe zi per task personal
  app_update.py     # versiunea si APK-ul aplicatiei Android

frontend/src/       # SPA Svelte 5 -> static/dist/ (Vite)
  pages/            # Home, Projects, ProjectDetail, Tasks, Plan, Calendar, Calculator
  components/ui/    # librarie proprie — FOLOSESTE-O, nu reinventa
  lib/driveCalc.js  # motorul Calculatorului (4.400 linii)
frontend/android/   # Capacitor: WebView peste site + notificari native
static/dist/        # build-ul, VERSIONAT (vezi capcana de mai jos)
static/service-worker.js  # PWA + push; bumpeaza VERSION la orice schimbare de dist
```

## Invarianti de produs

Regulile care nu se deduc din cod uitandu-te la el, si care se strica tacut daca le incalci:

1. **Un task are O SINGURA data** — `data_scadenta`, termenul. Nu exista „data planificata".
   A pune un task pe azi = a-i da termenul de azi; a-l scoate = a-i sterge data.
2. **Un proiect are doua statusuri:** `pregatire` si `finalizat`. Atat.
3. **`data_finalizare` exista daca si numai daca statusul e `finalizat`.** Se pune automat la
   inchidere, se **sterge** la redeschidere. Fara invariant, formularul tine data agatata si
   o re-inchidere te intoarce tacut in ziua veche.
4. **`implementari.faza`** (`pregatire`|`implementare`) **e independenta de `locatie`**
   (`site`|`sediu`). „Unde esti" si „in ce faza esti" sunt doua fapte, nu unul cu doua nume.
5. **„S-a facut" e despre PERIOADA**, nu despre proiect: scrie `implementari.confirmata`.
   Statusul proiectului se schimba doar din formularul lui. Altfel o deplasare bifata inchide
   lucrarea si urmatoarea vizita nu mai poate fi planificata.
6. **Taierea perioadelor la `data_finalizare` se face doar la CITIRE** (`/api/calendar`,
   `/api/export/ics`). Baza ramane neatinsa.
7. **`sfera`** (`munca`|`personal`) e opt-in la citire: implicit se intorc doar cele de munca,
   iar o valoare necunoscuta da 400, nu se corecteaza tacit.

**Proprietatea suprafetelor.** Calendarul detine **perioadele** (se creeaza, se muta, se scot
doar de acolo). Planificatorul detine **taskurile**; benzile de perioada sunt context. Pagina
proiectului le detine pe amandoua.

**Vocabular:** *perioada* = interval (unde esti), *termen* = punct (pana cand). „Data" nu se
foloseste ca eticheta.

## Design system

Regulile complete (culoare, tipografie, mișcare, componente): **`.claude/rules/design.md`** —
se încarcă singur când atingi `frontend/src/**`. Sursa valorilor rămâne
`frontend/src/styles/tokens.css`; verificarea, `python scripts/audit_design.py` înainte de commit.

## Verificatoare

```bash
python scripts/audit_design.py      # coerenta sistemului de design (sub o secunda)
python scripts/test_suite.py        # API + verificari statice (44 de probe)
python scripts/smoke_ui.py          # fiecare ruta in Chromium, desktop + mobil
python scripts/audit_mobil.py       # geometrie si gesturi pe trei latimi de telefon
python scripts/audit_navigare.py    # ce se intampla, masurat, cand schimbi tabul
python scripts/audit_foaie.py       # foaia de pe telefon: trepte, viteza, voal
python scripts/audit_reactivitate.py # cat de repede raspunde si cat de neted curge
```

Fiecare exista fiindca prinde un mod de esec care trece de build: importul lipsa care lasa
pagina pe schelet, butonul taiat de marginea ecranului, a doua paleta rotita cu doua pozitii,
foaia care se intinde si nu se mai poate trage inapoi.

**`audit_foaie.py` cere atingere ADEVARATA** (`Input.dispatchTouchEvent`, ca `audit_mobil`):
mouse-ul lui Playwright emite `pointerType: 'mouse'`, iar foaia iese exact pe conditia asta —
cu mouse-ul, gestul nu porneste deloc si proba ar raporta verde pe un gest inexistent.

**Poarta** (`.claude/hooks/gate.py`, la Stop) le ruleaza singura, pe ce s-a atins: CSS/Svelte
→ `audit_design`; backend → `test_suite`; surse SPA → build + `smoke_ui` + `audit_mobil`.
Nu blocheaza de mai mult de doua ori per sesiune. **O modificare doar in documentatie nu o
declanseaza.** Supapa: `PIF_GATE=skip` — o si anunta in context, deci n-o poti folosi tacit.

Cerinte, o singura data, doar pe masina de dezvoltare (NU in `requirements.txt`):
`pip install playwright && python -m playwright install chromium`.

## Mediu, server, deploy

| variabila | obligatorie | implicit | note |
|---|---|---|---|
| `PIF_DASHBOARD_PIN` | da (prod) | — | fara ea login-ul pica |
| `SECRET_KEY` | nu | fisier `.secret_key` | semnarea sesiunii |
| `SESSION_COOKIE_SECURE` | nu | `true` | `false` pentru dev pe HTTP |
| `PIF_API_TOKEN` | nu | — | Bearer pentru masini (Cowork, `pif-sync.py`); scutit de CSRF |
| `PIF_DB_PATH` | nu | `pif_dashboard.db` | baza alternativa; o folosesc probele |
| `PIF_RATE_LIMIT` | nu | `60` | cereri/minut per IP pe `/api/*` |

**Server:** `ion-ursu@192.168.0.107`, `/home/ion-ursu/Projects/pif-dashboard`, systemd
(`sudo systemctl restart pif-dashboard`), Gunicorn 2 workers.

**Deploy:** `git push origin master` → webhook `POST /webhook/deploy` (HMAC) face
`git reset --hard` + `pip install` + restart. **Nu exista npm pe server**, deci `static/dist/`
TREBUIE sa fie versionat — de aceea `.githooks/pre-commit` cere bump la `VERSION` din
`static/service-worker.js` cand dist-ul se schimba: fara el, build-ul nou nu ajunge pe telefon.

## Mai multe sesiuni pe acelasi arbore

Indexul git e comun, deci coordoneaza-te inainte sa pui in stage sau sa comiti. **Niciodata
`git add -A`** si niciodata force-push. Verifica ce e al tau cu
`git status -- . ':!static/dist'`. Sablonul de pornire: `AGENT_BRIEFING.md`.

## Limitari cunoscute

- Statusurile sunt string-uri magice, centralizate in `labels.py` dar **neimpuse la nivel de
  baza** — un `UPDATE` direct poate scrie orice.
- CSP foloseste `unsafe-inline`. A ramas din aplicatia veche cu sute de `onclick`; azi
  `static/dist/index.html` are un singur script inline (bootstrap-ul de tema), deci migrarea
  la nonce a devenit realista.
- Nu exista framework de teste (pytest); probele din `scripts/` sunt scrise de mana.
- `UPLOAD_FOLDER` nu se poate configura din mediu.
