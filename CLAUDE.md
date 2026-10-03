# PIF Dashboard

Backend-ul Torqa pentru organizarea si monitorizarea proiectelor de punere in functiune, pentru
un singur utilizator (Ion): Flask + SQLite, API-ul `/api/*`, loginul cu PIN si Torqa web la
`/torqa/` (build-ul Angular al Torqa, urcat pe server). Live la `pif.iupif.org` prin Cloudflare
Tunnel.

**Interfata veche a fost retrasa pe 2026-10-03** (SPA-ul Svelte 5, calculatorul `/calc`, planul de
departament, notificarile push, aplicatia Android `org.iupif.pif`): Torqa a preluat tot ce
foloseste Ion. Ultima stare cu ea e eticheta git `inainte-de-retragere`; ce s-a scos, ce a
ramas si cum se aduce inapoi: `docs/decizii/2026-10-03-retragerea-interfetei-vechi.md`.

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
| **de ce am facut asa** | `docs/decizii/INDEX.md` (decizii, cu carlig fiecare) |
| ce a fost interfata veche | eticheta `inainte-de-retragere` + `docs/decizii/2026-10-03-retragerea-interfetei-vechi.md` |

Cele trei harti se regenereaza la fiecare commit care atinge cod Python. Activeaza hook-ul
o data per clona: `git config core.hooksPath .githooks`.

## Arhitectura

```
app.py              # intrare Flask, auth PIN, CSP (nonce, fara surse externe), rate limit pe IP-ul din
                    #   socket (CF-Connecting-IP doar de la proxy de incredere), webhook deploy; / duce la /torqa/
database.py         # schema v43, migrari v1-v43 idempotente, WAL
utils.py            # login_required, UUID, app_settings, norm_date, tokenurile de masina/dispozitiv
csrf.py labels.py   # CSRF double-submit; etichetele de status

blueprints/
  projects.py       # /api/proiecte/* — CRUD, perioade, snapshot, import debrief, export
  tasks.py          # taskuri de proiect + globale + subtaskuri
  admin.py          # /api/calendar, /api/stats, backup/restore, db-upload / db-dump
  obsidian.py       # citeste vault-ul si scrie frontmatter inapoi in el
  sync.py           # /api/sync/snapshot — imaginea completa pentru Torqa
  app_update.py     # versiunea si APK-ul aplicatiei Android (canale: pif, torqa)
  torqa_web.py      # Torqa web (build Angular) la /torqa/: urcare, versiuni, servire

templates/login.html  static/login.css   # singura pagina randata de server (PIN)
static/service-worker.js                 # worker care se retrage singur: scapa browserele
                                         #   care au instalat interfata veche de ea
teste/                                   # unittest (Python) si teste/js/ (node --test)
scripts/                                 # verifica.py, lint.py, test_suite.py, banc.py,
                                         #   gen_memory.py, upload_db.py, sync_db_from_server.sh
```

Nu exista pas de build in repo si nu exista npm pe server: ce se construieste (Torqa web, APK-ul
Torqa) vine din repo-ul Torqa si se urca (vezi mai jos).

## Invarianti de produs

Regulile datelor, care nu se deduc din cod uitandu-te la el, si care se strica tacut daca le incalci:

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
6. **Taierea perioadelor la `data_finalizare` se face doar la CITIRE** (`/api/calendar`).
   Baza ramane neatinsa.
7. **`sfera`** (`munca`|`personal`) e opt-in la citire: implicit se intorc doar cele de munca,
   iar o valoare necunoscuta da 400, nu se corecteaza tacit.

*Regulile de proprietate a suprafetelor (ce se editeaza in Calendar, in Taskuri, pe „Astazi") si
planificatorul scos pe 2026-08-26 descriau interfata veche; sunt istorie, in
`docs/decizii/2026-07-27-proprietatea-suprafetelor.md` si
`docs/decizii/2026-08-26-planificatorul-scos-ziua-intreaga.md`. Suprafetele de azi sunt ale Torqa.*

**Vocabular:** *perioada* = interval (unde esti), *termen* = punct (pana cand). „Data" nu se
foloseste ca eticheta.

## Design system

Retras odata cu interfata veche (`frontend/src/styles/tokens.css`, regulile din
`.claude/rules/design.md`, `audit_design`, `audit_contrast`): serverul nu mai are interfata de
proiectat. Ce a ramas: pagina de login isi tine propria copie a tokenurilor in `static/login.css`
(singura pagina randata de server), iar Torqa isi are sistemul de design in repo-ul lui. Sistemul
vechi se citeste din eticheta: `git show inainte-de-retragere:frontend/src/styles/tokens.css`.

## Verificatoare

Un singur punct de intrare. Lista pasilor si regulile portii stau in `scripts/verifica.py`,
nu aici — de acolo le ia si poarta.

```bash
python scripts/verifica.py              # = --rapid, ~30 s: lint, teste JS, teste Python, probe API
python scripts/verifica.py --atinse <fisiere>   # exact ce ar rula poarta pentru ele
python scripts/verifica.py --continua   # nu te opri la primul esec
```

Patru pasi, toti fara browser si fara build:

1. `lint` — pyflakes pe tot proiectul (`scripts/lint.py`).
2. `unitare_js` — `node --test teste/js/*.test.mjs`: scriptul din `templates/login.html` (unde te
   duce dupa PIN) si `static/service-worker.js` (se retrage singur, nu atinge `ngsw:`). Runner-ul
   built-in al lui Node, fara pachete npm.
3. `unitare_py` — `python -m unittest discover -s teste`: functiile pure, garzile, schema pe o baza
   goala, rutele prin clientul de test (APK, Torqa web, login, sync) si `test_retragere` (ce a
   plecat nu mai raspunde).
4. `test_suite` — probele de API prin HTTP pe un server de unica folosinta, cu baza noua
   (`scripts/banc.py`): sfera, ce trimite un proiect inchis, backup-ul fara secrete.

**Poarta** (`.claude/hooks/gate.py`, la Stop) ruleaza, din aceeasi lista (`pasi_pentru`), doar
ce cer fisierele atinse. Nu blocheaza de mai mult de doua ori per sesiune. **O modificare doar
in documentatie nu o declanseaza.** Supapa: `PIF_GATE=skip` — o si anunta in context, deci
n-o poti folosi tacit. Ce pazeste fiecare pas si capcanele lui: `docs/verificatoare.md`.

Cerinte, o singura data, doar pe masina de dezvoltare (NU in `requirements.txt`):
`pip install pyflakes requests` si Node (doar `node`, fara npm; il gaseste si in PATH-ul din registru).

## Mediu, server, deploy

| variabila | obligatorie | implicit | note |
|---|---|---|---|
| `PIF_DASHBOARD_PIN` | da (prod) | — | fara ea login-ul pica |
| `SECRET_KEY` | nu | fisier `.secret_key` | semnarea sesiunii |
| `SESSION_COOKIE_SECURE` | nu | `true` | `false` pentru dev pe HTTP |
| `PIF_API_TOKEN` | nu | — | Bearer pentru masini (Cowork, `pif-sync.py`); scutit de CSRF |
| `PIF_DEVICE_TOKEN` | nu | — | Bearer pentru Torqa (telefon, desktop); fara restore, backup, admin, deploy, upload APK; din vault citeste doar notele din `vault_folder` de proiect, nu scrie nicio nota si nu scrie `vault_folder` |
| `PIF_DB_PATH` | nu | `pif_dashboard.db` | baza alternativa; o folosesc probele |
| `PIF_RATE_LIMIT` | nu | `60` | cereri/minut per IP pe `/api/*` |
| `PIF_TRUSTED_PROXIES` | nu | `127.0.0.1,::1` | adrese sau retele CIDR de la care se crede `CF-Connecting-IP` (cloudflared); de la oricine altcineva, IP-ul clientului e adresa socketului. Daca cloudflared nu ajunge la gunicorn pe loopback, adresa lui se adauga aici; altfel toti clientii prin tunel primesc aceeasi adresa, deci aceeasi limita |

**Server:** `ion-ursu@192.168.0.107`, `/home/ion-ursu/Projects/pif-dashboard`, systemd
(`sudo systemctl restart pif-dashboard`), Gunicorn 2 workers.

**Deploy:** `git push origin master` → webhook `POST /webhook/deploy` (HMAC) face
`git reset --hard` + `pip install` + restart. Nimic de construit pe server si nimic versionat din
build: SPA-ul si `static/dist/` au plecat odata cu interfata veche, iar `.githooks/pre-commit` nu
mai cere bump de `VERSION` (service worker-ul de azi nu are versiune).

**Torqa web si APK-urile nu trec prin git** (`uploads/`, gitignored): build-ul Angular (`--base-href /torqa/`) se urca
ca zip la `POST /api/torqa/web/upload` (camp `zip`, Bearer `PIF_API_TOKEN`) si apare la `/torqa/`; raman live + 2
anterioare (`printf '<versiune>' > uploads/torqa-web/current` = intoarcere). APK-urile: `POST /api/app/upload`, cu
`canal=torqa` (singurul canal din 2026-10-03; `canal` e obligatoriu si la urcare, si la citire: fara el, 400); citire
`GET /api/app/version|apk?canal=torqa`. Canalul `pif` al aplicatiei vechi a plecat. Comenzile si motivele:
`docs/decizii/2026-10-01-torqa-web-si-canalul-apk.md`.

**`/` duce la `/torqa/`** (302, fara sesiune; `/torqa/` cere el sesiunea si trimite la
`/login?next=/torqa/`). `/service-worker.js` serveste worker-ul care se retrage singur, ca browserele
cu interfata veche sa scape de ea; ruta ramane. `/calc`, `/assets/`, `/manifest.json`, `/docs/`,
`/api/me`, `/api/push/*`, `/api/settings/plan-departament` dau 404, ca si rutele fara apelant scoase
dupa retragere: `/api/clienti*`, `/api/agenda/*`, `/api/search`, `/api/export/pdf`,
`/api/import-abb-multi/preview`, `/api/import-archive/preview`, apoi (alegerile lui Ion din
inventarul functiilor) `/api/import/debrief`, `PUT /api/obsidian/note`, `/api/deploy` si `/api/health`.

## Mai multe sesiuni pe acelasi arbore

Indexul git e comun, deci coordoneaza-te inainte sa pui in stage sau sa comiti. **Niciodata
`git add -A`** si niciodata force-push — ambele blocate acum si mecanic de hook-ul
`guard_git` (PreToolUse). Verifica ce e al tau cu `git status`. Sablonul de pornire:
`AGENT_BRIEFING.md`.

## Limitari cunoscute

- Statusurile sunt string-uri magice, centralizate in `labels.py` dar **neimpuse la nivel de
  baza** — un `UPDATE` direct poate scrie orice.
- Ce a ramas fara cod dupa retragere a plecat din baza: cheile `app_settings` `push_*`,
  `plan_departament_url`, `ics_feed_key`, `fault_data_rev` in v42; Ganttul (`task_dependencies`,
  `tasks.data_start/progres/is_milestone`), `ordine_agenda`, `calcule`, `clienti` si
  `proiecte.notify_on_complete` in v43. `/api/backup` exclude inca `push_*` (`CHEI_PROTEJATE`), ca un
  secret pus de mana sa nu plece; `/api/admin/db-dump` e baza bruta.
- Nu exista pytest: testele folosesc biblioteca standard (`unittest`, `node --test`).
- `UPLOAD_FOLDER` nu se poate configura din mediu.
