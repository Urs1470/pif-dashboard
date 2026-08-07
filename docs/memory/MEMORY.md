# MEMORY — PIF Dashboard

Persistent project memory for AI sessions. Read this INSTEAD of re-exploring the codebase.
Companion files (auto-generated, regenerate with `python scripts/gen_memory.py`):
- `CODE_MAP.md` — every JS section + top-level function with line numbers
- `API_MAP.md` — all Flask routes (method, path, handler, line)

Other authoritative docs (do not duplicate here):
- `CLAUDE.md` — stack, env vars, deploy, key patterns, design system (sectiune proprie)
- `SCHEMA_REFERENCE.md` — full SQL schema (all 9 tables, columns, FKs, indexes)

## Database map by domain

| Domain | Tables |
|---|---|
| Projects core | `proiecte`, `clienti`, `implementari` |
| Tasks | `tasks`, `task_subtasks`, `task_dependencies`, `global_tasks` |
| System | `app_settings` (KV), `schema_version` |

Migrations: in-code in `database.py` (`run_migrations()`), currently **v28**, idempotent, auto-run via `before_request`.

> **v28 (2026-07-27) a sters `parametri_master`, `fault_codes`, `echipamente`, `atasamente`.**
> Nu le recrea si nu adauga self-heal pentru ele — un self-heal le-ar reinvia la fiecare pornire
> (de aia au fost scoase si cele doua self-heal-uri existente). Functiile de migratie istorice
> (v1->v2, v9->v10, v17->v18) inca le creeaza pe drumul spre v28; e intentionat si idempotent.
> Datele: `raw/pif-dashboard/2026-07-27-inainte-de-v28/` in vault.

## Feature status (last verified 2026-07-27)

- Module active: Proiecte, Taskuri, Taskuri zilnice, Planificator (Gantt), Calculator, tab Wiki, Admin.
- Cowork API: Bearer `PIF_API_TOKEN`, endpoints `/api/proiecte`, `/api/proiecte/<id>/snapshot`, `/api/import/debrief`.
- `/api/import/debrief` accepta `echipamente[]` dar le IGNORA din v28 — le numara in
  `sumar.echipamente_ignorate`. Skill-ul `pif-debrief` inca le genereaza; nu e bug.
- Parsarea backup-urilor de drive traieste in continuare: `/api/import-abb-multi/preview` si
  `/api/import-archive/preview` (`scripts/parse_params/`) alimenteaza Calculatorul. Nu ating DB-ul.
  `_familie_param_meta()` din `blueprints/projects.py` e un stub care returneaza `{}` (catalogul de
  parametri nu mai exista) — preview-ul arata exact ce scrie in fisier, fara imbogatire.

## Gotchas

- `static/app.js` (~8k lines) and `static/mobile.js` (~4.8k) are SEPARATE bundles — a desktop feature usually needs a mobile twin. Use CODE_MAP.md to find the section, then read only that range.
- JS section headers: `// ============ NAME ============`. Keep this format — `gen_memory.py` parses it.
- Asset cache-busting is automatic (SHA256 `?v=` via context processor) — no manual version bumps.
- CSRF: client reads `csrf_token` cookie → sends `X-CSRF-Token` header. GET/HEAD/OPTIONS and `/webhook/*` exempt; Bearer-token requests exempt.
- Status values are magic strings (`'in_lucru'`, `'finalizat'`...) — labels centralized in `labels.py` (backend) and `static/core.js` (frontend); keep both in sync.
- Recurring tasks (zilnic/saptamanal/lunar) auto-spawn the next instance on completion — completion logic must preserve this.
- Tests: no pytest; run `python scripts/test_suite.py` (plus feature scripts in `scripts/`).
- Multi-agent: always `git fetch && git pull --rebase` before push; never force-push; respect domain split in `CLAUDE.md` (Multi-Agent Collision Rules).

## Maintenance protocol (for every AI session)

1. Start by reading this file + `CODE_MAP.md`/`API_MAP.md` — do NOT scan app.js/blueprints blindly.
2. Maps auto-regenerate on commit via `.githooks/pre-commit` (activate once per clone: `git config core.hooksPath .githooks`). Without the hook, run `python scripts/gen_memory.py` manually after adding/removing functions, sections, or routes.
3. Made a non-obvious decision, found a new gotcha, or changed feature status? Append one dated line to **Recent decisions** below (newest first, keep ≤ 30 entries, prune oldest).

## Recent decisions

- **2026-08-07 — „S-a facut" e despre PERIOADA, nu despre proiect (v39).**
  Butonul „Da" din panoul zilei chema `PUT /api/proiecte {status:'finalizat'}`:
  intrebarea era despre perioada, raspunsul inchidea proiectul. Ion: dupa
  implementare mai raman PV-uri, si poate o vizita pe care inca n-o poti data.
  Greseala se auto-ascundea — proiectul inchis iese din `neplanificate`, deci
  exact vizita aia nu mai avea de unde sa fie planificata. Acum
  `implementari.confirmata`; `necesita_decizie` = trecut SI `confirmata=0` SI
  proiect nedeschis, aceeasi conditie in `de_decis`. Bifa se vede ca „Făcut"
  (panoul zilei + `ImplPeriods`), se scoate cu „Nu s-a făcut", si NU se pierde
  la mutarea perioadei. Statusul proiectului se schimba doar din formularul lui.
  Capcana obisnuita: `INSERT INTO implementari` din restore-ul de backup
  enumera coloanele explicit — fara `confirmata` acolo, un restore stergea
  bifele in tacere.
- **2026-08-07 — `scripts/test_suite.py` crapa pe Windows inainte de orice test.**
  `Path.read_text()` fara `encoding` cade pe cp1252, iar `google_calendar.py` are
  ghilimele romanesti in comentarii: `UnicodeDecodeError` in analiza statica, deci
  ZERO teste rulate. Cele trei citiri au acum `encoding='utf-8'`.
- **2026-08-04 (5) — Sfera nu e filtru: comutator segmentat, nu chip-uri.**
  Ion, a doua observatie pe acelasi rand: Munca/Personal aratau tot ca
  Active/Arhiva. Dar sfera schimba IN CE LUME esti; filtrul alege ce subset
  vezi din ea. Acum sfera e `.sfere`/`.seg` — capsula unita cu segmentul activ
  RIDICAT pe suprafata neutra (bg-elevated + shadow-sm, NU amber: amber la
  activ ramane limbajul filtrelor de langa el). Punctul violet ramane pe
  segmentul Personal. Pe telefon tinta de 44px vine din segment, nu din
  padding-ul capsulei.

- **2026-08-04 (4) — Butonul Google nu mai e chip: iconita-fantoma cu punct de eroare.**
  Ion: chip-urile din toolbarul /tasks sunt FILTRE (Munca/Personal,
  Active/Arhiva), iar Google Calendar era o actiune de setari desenata identic
  — aceeasi haina pentru lucruri diferite. Acum e `.g-ico`, iconita ghost la
  capatul randului (doar in vederea Personal), cu un punct `--danger` care
  apare DOAR cand `last_error` e setat — sincronizarea merge singura, iar
  intrarea exista ca o stare stricata sa aiba unde sa se arate si ca
  Resincronizeaza/Deconecteaza sa ramana accesibile. Statusul se ia o data la
  intrarea in vederea Personal (altfel punctul n-ar avea de unde sa stie).

- **2026-08-04 (3) — Credentialele Google se pot lipi din UI; pasul systemd a disparut.**
  Ion a intrebat daca poate trimite JSON-ul OAuth prin chat ca sa-i punem noi
  env vars pe server. Nu: secretele nu circula prin chat si sesiunile remote
  n-au SSH la server. In loc: `PUT /api/google/credentials` — JSON-ul descarcat
  din consola se lipeste in modalul Google din /tasks; validare server-side
  (tip `installed` respins cu explicatie; fail-early daca `redirect_uris` nu
  contine callback-ul nostru), stocare in app_settings sub `google_client_id`/
  `google_client_secret` — prefixul `google_` le tine automat afara din backup
  si le pastreaza la restore. ENV ARE PRIORITATE (si PUT-ul refuza cand sursa
  e env). DISCONNECT NU sterge credentialele (deconectarea rupe legatura cu
  contul, nu deconfigureaza; `GOOGLE_KEYS` ramane doar tokens+calendar+stare).
  `/api/google/status` are acum `sursa: 'env'|'setari'|''`.

- **2026-08-04 (2) — Google Calendar API: push instant pentru taskurile personale.**
  Cerinta Ion („vreau sincronizare automata prin Google Calendar API"). Blueprint
  nou `blueprints/google_calendar.py`: OAuth 2.0 web flow server-side
  (`/oauth/google/start` -> consent -> `/oauth/google/callback`, state in
  sesiune, SameSite=Lax supravietuieste; rute in afara /api = fara rate limit),
  creds in env (`GOOGLE_CLIENT_ID/SECRET`), tokens in app_settings sub chei
  `google_*`. Sync ONE-WAY dashboard->Google, hook-uri post-commit in
  POST/PUT/DELETE global-tasks (tipar `sync_project_frontmatter`: thread daemon
  best-effort; PUT trimite si ocurenta recurenta spawn-uita). Scope granular
  `calendar.app.created`; calendarul „PIF Personal" e creat de app. Id eveniment
  = uuid-ul taskului fara cratime (determinist, fara tabela de mapare).
  **Capcana load-bearing:** Google nu elibereaza NICIODATA un id de eveniment
  sters — insert dupa delete da 409 pe veci; upsert = insert, la 409 patch cu
  `status:'confirmed'` (reinvie evenimentul anulat). Bifat = evenimentul RAMANE
  cu prefix „✓ " (ales de Ion) — divergenta INTENTIONATA fata de .ics, care
  exclude finalizatele; nu o „reparati". `invalid_grant` (revocare sau consent
  screen ramas in Testing — expira la 7 zile; appul trebuie PUBLICAT in
  Production) -> stare deconectat + mesaj in `/api/google/status`. Backup JSON
  EXCLUDE cheile `google_*`; restore le PASTREAZA peste DELETE si ignora
  `google_*` venite din fisier (anti-injectare). Nota: `ics_feed_key` curge in
  continuare in backup (clasa preexistenta, miza mica); db-dump e baza bruta.
  Resync bidirectional (`/api/google/resync`): sterge si orfanii din calendar.
  Zero dependente noi (stdlib urllib, timeout 15s peste tot). Fara migrare.

- **2026-08-04 — Taskuri personale: `global_tasks.sfera` (v38), nu tabela noua.**
  Cerinta Ion: taskuri in afara jobului, NEamestecate cu munca, subtil, corect pe
  mobil. Discriminator `sfera` ('munca'|'personal'), aceeasi tabela — o tabela
  separata ar fi dublat recurenta, subtaskurile si CRUD-ul. Regula: FIECARE
  interogare pe global_tasks isi declara sfera explicit; lipsa parametrului =
  'munca' (fail-closed), valoare necunoscuta = 400. Suprafete: /tasks are
  comutator Munca·Personal (din `router.query.sfera`, adresabil); boardul
  „Astăzi" primeste cheia separata `personale[]` randata ca anexa discreta
  (antet .pers-cap cu punct violet --purple — NU .grup-cap, clasa e citita de
  audit_mobil); Planificator, agenda/candidates si feedul ICS de munca EXCLUD
  personalul; cautarea e singura suprafata cross-sfera (eticheteaza „Personal").
  Spawn-ul recurent COPIAZA sfera (altfel taskul migra la munca la bifare) si
  restore-ul o completeaza cu 'munca' pe backupuri pre-v38. Google Calendar:
  feedul .ics accepta acum `?key=<ics_feed_key din app_settings>` (Google
  descarca fara sesiune/headere) + `?sfera=personal` — feed separat „PIF
  Personal"; butonul „Google Calendar" din vederea personala copiaza linkul.
  Prins pe drum: `focusHref` hardcoda `?` — cu o cale care are deja query
  (`/tasks?sfera=personal`) producea `?...?focus=` si getQuery citea gresit.
  Self-heal aditiv pe lipsa coloanei (nu poate anula nimic). Teste: 11 asertii
  anti-scurgere in test_suite (`sfera_leak_test`), ruta `/tasks?sfera=personal`
  in smoke_ui. Neacoperit inca: scenariu de gest in audit_mobil pentru vederea
  personala (optional, API-ul e acoperit).

- **2026-07-31 (7) — HERMES.md sters (cerinta Ion) + runda de design ca sistem.**
  HERMES.md era briefingul agentului Hermes; partea despre dashboard (sistemul
  de design) traieste acum ca sectiune „Design system (frontend)" in CLAUDE.md.
  Referintele curatate (CLAUDE.md, AGENT_BRIEFING.md, antetul din MEMORY,
  database.py, TodayBoard); intrarile istorice de mai jos raman cum au fost scrise.
  Runda de design, pe patru intrebari:
  **(1) Formularele folosesc libraria** — Categorie era `<input class="mf-input">`
  in ambele modale din /tasks (a treia reteta de camp, langa .field-input si
  .dp-trigger), Descrierea din modalul paginii de proiect era `<textarea>` brut,
  plus un `mf-field` GOL (perechea prioritatii, v34) care impingea Termenul in
  jumatatea dreapta. Toate -> `<Input>`/`<Textarea>`/`<DatePicker label>`;
  stilurile mf-* au plecat din ambele pagini.
  **(2) Acelasi obiect, acelasi desen** — chipul de context (categoria/proiectul)
  avea radius-full in /tasks si radius-xs pe „Astăzi"; pe telefon /tasks il facea
  text simplu, boardul il tinea pastila. Boardul preia reteta din /tasks.
  **(3) Contrastul, masurat automat** (ambele teme, cele 5 pagini): `--text-faint`
  e documentat „doar etichete/large" (3:1), dar scria INFORMATIE la 10-13px:
  clientul de pe cardul de proiect, intervalele din „urmatoarea iesire",
  indicatiile din Planificator, contoarele (tail, ms-c), „Proiect nou". Toate ->
  `--text-dim`; etichetele uppercase si separatorii raman faint. Re-scanat: zero
  informatie sub 4.5:1.
  **(4) Containerele goale** — verificate: sertarul gol din Plan dispare (e
  unealta, nu informatie — corect), Planificatorul si ziua goala din Calendar au
  stari explicate. Nimic de reparat.
  Toate 4 harnessurile verzi.

- **2026-07-31 (6) — Miscarea la standardul gestului: `sosire` + `--ease-spring`.**
  Inventarul miscarii a aratat ca mult e deja la standard (View Transitions API
  nativ pe navigare — masurat un singur `.content-width` pe toata durata; toast
  fly+flip; Select fly; shimmer; apasare <100ms; reduced-motion global). Doua
  lipsuri, ambele reparate:
  **(1) Iesirea exista, intrarea nu** — `sosire` in lib/motion.svelte.js
  (perechea lui `plecare`): opacitate + ridicare 5px, DOAR transform/opacity
  (vecinii isi fac loc prin `animate:flip`; doua animatii de layout pe acelasi
  eveniment s-ar calca). Pe toate cele trei liste, cu `|local` — REGULA: prima
  incarcare a paginii nu se joaca, intrarea e a randului nou (adaugat sau mutat
  intre grupe), nu a paginii. Masurat: opacitate 1 din primul cadru la load,
  ~10 cadre de fade la adaugare.
  **(2) Foaia eliberata se oprea mecanic** — token `--ease-spring` in tokens.css:
  `linear()` care esantioneaza un spring amortizat (~5% depasire), folosit DOAR
  pentru revenirea din gest (translate-ul sheet-ului, cu --dur-slow), cu rezerva
  pe `--ease` pentru browsere fara `linear()` (prima linie de `transition` din
  aceeasi regula). R4 din audit_design ramane curat fiindca tokenul sta in
  tokens.css. Masurat pe gest: 72px -> 0 -> −3.6px -> 0.
  Toate 4 harnessurile verzi dupa.

- **2026-07-31 (5) — Aprofundarea consolidarii: starile, nu doar suprafata.**
  Metoda noua: am TAIAT serverul (500) sub fiecare pagina si am fotografiat ce
  ramane; am masurat ritmul intre pagini; am cautat nume care promit altceva
  decat fac.
  **(1) Acasa avea singurele stari de eroare mute.** Boardul „Astăzi" arata un
  paragraf rosu fara drum inainte (regula de design cere `<ErrorState>` cu retry — toate
  celelalte pagini il aveau); linia „urmatoarea iesire" era mai rea: la esec punea
  `data = null` si DISPAREA — eroarea arata identic cu „nicio iesire planificata",
  exact absenta tacuta despre care scrie lectia v29. Acum: ErrorState pe board,
  iar linia ramane pe ecran cu „Ieșirile nu s-au putut încărca" + Reîncearcă
  inline. Ambele retry-uri verificate cu rutele taiate si apoi eliberate.
  **(2) Ritmul mobil din decizia (9) se aplicase doar pe /tasks.** Masurat pe
  /projects la 390×844: primul card la y=314 — acelasi 37% din ecran pentru care
  /tasks fusese strans. Aceleasi strangeri: 314 -> 282.
  **(3) `.form-row-3` cu DOI copii** — coloana prioritatii (plecata in v34) a
  ramas in grila: o treime din modal, goala, pe ambele formulare de task. Acum
  `.form-row-2`.
  **(4) Grila de proiecte se demola la fiecare actiune** — `{#if projects.loading}`
  fara garda `items.length === 0` (regula scrisa in Tasks/TodayBoard/Plan), desi
  loadProjects() se cheama la comutare de status, stergere si filtre. Masurat
  dupa: zero schelete la filtrare.
  Verificat iar: toate 4 harnessurile verzi.

- **2026-07-31 (4) — Consolidare UI/UX: unde s-a abatut codul de la propriile lui
  reguli scrise.** Metoda: nu „ce arata prost", ci masurat contra regulilor din
  tokens.css/CLAUDE.md/comentarii. Sapte abateri gasite si reparate, niciuna cu
  vreo eroare aruncata:
  **(1) `.sub-row` declarat de DOUA ori in Tasks.svelte** — a doua declaratie
  (ramasa de la designul de lista) anula tacut `padding: 4px 8px` al cardului
  (masurat: `3px 0` desktop, `2px 0` in foaie; card cu rama la 0px de text). Plus
  o a treia lovitura din blocul mobil. Acum o singura declaratie.
  **(2) Escape inchidea TOT, nu un strat** — redenumirea/compozitorul de subtask
  lasau evenimentul sa urce la backdrop; Select folosea doar `preventDefault`
  (care NU opreste urcarea); DatePicker asculta pe window pe BUBBLING, adica dupa
  backdrop, deci nu putea opri nimic — mutat pe CAPTURA (`onkeydowncapture`) cu
  garda `open`. Regula: Escape inchide stratul cel mai de sus, atat.
  **(3) `.trow:hover` din /tasks aplica `translateX(4px)` dar tranzitia acoperea
  doar `opacity`** — randul SAREA; pe Acasa si in proiect acelasi rand aluneca.
  **(4) Redenumirea inline a subtaskului muta textul** — inputul aducea caseta
  lui (padding+rama = salt de 7px pe x; pe telefon si fontul 14.4→16, fortat de
  regula globala de zoom Safari). Acum inputul are metricile textului de citire
  + o linie de accent; pe telefon citire=scriere=1rem (egalat IN SUS — sub 16px
  nu se poate pe input).
  **(5) Titlurile mosteneau interlinia de PARAGRAF** — tokens.css scrie
  `--lh-tight (display/headings)`, dar reset-ul nu da titlurilor line-height,
  deci h1 avea caseta 43.4px la font 28. Podea in global.css: `h1..h4
  { line-height: var(--lh-tight) }` (specificitate 0,0,1 — orice clasa o bate).
  **(6) Doua limbaje de severitate pe acelasi task** — /tasks: bordura stanga
  (cea documentata in MEMORY (8)); Astăzi + proiect: underline `::after` de 40px,
  care pe telefon nici nu se vedea (sub `.gl-fata`). Unificat pe bordura. CAPCANA:
  hover/active cu `border-color` SCURT vopseau toate laturile, adica stergeau
  exact culoarea rezervata — redeclara `border-left-color`.
  **(7) `isSoon` local zicea „<= 7 zile", dueColor zice „<= 2"** — termen la 5
  zile: bordura gri + data amber, pe acelasi rand. Trei copii locale
  (Tasks/TodayBoard/ProjectDetail) mutate in formatters.js ca
  `esteDepasit/esteAzi/esteCurand`, LANGA dueColor, pe aceleasi praguri si pe
  parsarea locala din `zilePanaLa` (nu `new Date(iso)`, care e UTC).
  **BUG functional gasit pe drum: subtaskurile din pagina de proiect nu se
  incarcau NICIODATA** — `toggleTaskExpand` chema `loadAtt()`, fosila de la
  atasamente (v28); ReferenceError in mijlocul functiei async, inghitit de
  promisiunea neascultata: chip „0/1", lista goala, consola curata. Scos apelul.
  Tot in proiect: antetul de subtaskuri spunea numarul de doua ori, bifa era
  patrat amber (cbx = selectie de lista, nu „făcut") si „sterge subtask" era
  `opacity: 0` pe touch — aliniate la /tasks.
  **Gasit si NEreparat (scop):** redenumirea inline a subtaskurilor exista doar
  in /tasks, nu si in pagina de proiect (ar fi interactiune noua, nu consolidare);
  comentariul din blocul mobil al /tasks promite o „spina" la subtaskuri care nu
  e implementata (blocul e oricum mort pe telefon — acolo se deschide foaia).
  Verificat: audit_design curat, smoke_ui 28/28, audit_mobil complet OK,
  test_suite 11/11 (+warn-ul documentat), capturi inainte/dupa la 390 si 1280.

- **2026-07-31 (3) — Dock-ul pe telefon: tinte de 56px si ascundere la derulare,
  ca bara de adresa.** Ion: „sensul era sa le faci si putin mai mari iconitele din
  dock acum, tinand cont de spatiul aparut" + „poti sa faci cu autohide dockul pe
  principiul cum e la browser autohide la bara de cautare".
  **Marime:** tinta 44 -> **56px**, iconita 20 -> **24px**, cu `gap: 4px` si
  separatorul INAPOI (fusesera scoase doar fiindca opt tinte nu incapeau). Socoteala
  pe cel mai ingust telefon testat (360px): `5×56 + 4×4 + 12 = 308px` din 348. Pragul
  CSS e 768px, acelasi cu cel care decide ca sunt cinci — doua praguri diferite ar da
  o latime la care ai opt iconite marite si dock-ul iese din ecran.
  **Ascundere la derulare:** cobori -> pleaca, urci -> revine IMEDIAT (fara prag de
  revenire: cand vrei navigatia, o vrei acum). Sus (<60px) si la capatul paginii sta
  mereu afara. Prag de 8px acumulati, iar `ultimY` NU se actualizeaza sub prag, ca un
  gest lent sa se adune in loc sa fie ignorat la nesfarsit. Deplasarea de ascundere e
  proprie telefonului: cea de desktop (`100% + 6px`) e calibrata sa lase manerul
  afara, dar pe telefon manerul e `display: none`, deci ar ramane o dunga de dock
  peste continut.
  **ASTA INLOCUIESTE regula veche „pe mobil dock FIX, fara autohide"** (tot cerinta
  lui Ion, dar mai veche). Comentariul din cod o spune explicit, ca sa n-o „repare"
  cineva inapoi.
  **BUG-UL DE REACTIVITATE, meritat de retinut:** prima varianta pastra `hidden` ca
  `$state` setat dintr-un `apply()`. Efectul care readuce dock-ul la schimbarea rutei
  chema `apply()`, iar `apply()` CITEA `scrollHidden` — deci efectul devenea dependent
  de el si il stingea imediat ce se aprindea. Dock-ul nu se ascundea NICIODATA, cu
  build verde si zero exceptii. Reparat facand `hidden` `$derived`: fara „cine cheama
  recalcularea" nu mai exista cerc. `isMobile` se citeste acum si el imediat, nu dupa
  montare, ca dock-ul sa nu porneasca ascuns si sa sara la vedere dupa primul paint.
  **Regresie acoperita:** sectiune noua `dockul_pe_telefon` in `audit_mobil.py` (7
  verificari). Ruleaza pe **Calculator**, nu pe Taskuri: cu baza de test lista de
  taskuri incape intr-un ecran, deci nu exista derulare de masurat si prima varianta a
  testului „trecea" degeaba. Verificat prin injectarea ambelor regresii (ascunderea
  dezactivata + deplasarea de desktop): pica exact cele doua randuri asteptate.
  **Capcana de mediu, a doua oara:** pe langa `PIF_RATE_LIMIT` (60/min pe `/api/*`)
  exista un limitator SEPARAT si neconfigurabil pe login — `LOGIN_LIMIT = 5` incercari
  la `LOGIN_WINDOW = 300s`, in memoria procesului. De aici 429-urile care se prezinta
  drept „PIN incorect". Pentru teste: logheaza-te O DATA si refoloseste
  `storage_state`, sau porneste un server nou (contorul e per proces).
  Verificat: `audit_design` curat, `smoke_ui` 28/28, `audit_mobil` complet OK
  (inclusiv cele 7 noi), `test_suite` 12/12.

- **2026-07-31 (2) — Dock-ul tine CINCI lucruri pe telefon; si o ruta scoasa din
  navigatie trebuie sa ramana cu un drum.** Ion: „pentru mobil, poti sa pastrezi pe
  dock doar acasa, taskuri, planificator, calendar si search? dar doar pentru mobil?"
  Filtrul e in `Dock.svelte`, `PE_TELEFON = {'/', '/tasks', '/plan', '/calendar'}`,
  aplicat prin `$derived` pe `ecran.telefon`. Desktopul ramane neatins: 8 tinte.
  **De ce `ecran.telefon` si NU `isMobile`-ul local al Dock-ului:** cele doua raspund
  la intrebari diferite. `isMobile` include `pointer: coarse` fiindca decide „dock fix
  sau autohide"; filtrarea decide „cate incap pe lat". Pe o tableta lata cu ecran
  tactil vrei dock fix, dar ai loc de toate sapte. `ecran.telefon` citeste valoarea
  IMEDIAT (nu dupa montare), deci nu apar sapte iconite si abia apoi cinci.
  Masurat: 390px si 360px -> 5 tinte, dock 226px, tinta minima 44px, fara depasire;
  1440px -> 8 tinte, neschimbat.
  **Partea care nu era in cerere, dar fara de care cererea rupea ceva:** Departament
  NU era in `CommandPalette`. Cat timp statea in Dock nu conta; scoasa din Dock si
  lipsa din paleta, devenea o ruta pe care nu o mai poti deschide de pe telefon.
  Adaugata.
  **Al doilea, descoperit verificand primul:** paleta ascundea lista de rute de indata
  ce scriai a DOUA litera (`{#if !isSearchMode}`), deci `keywords` de pe comenzi nu se
  putea folosi niciodata — cautand „calculator" primeai note si proiecte, dar nu si
  PAGINA Calculator. Se vedea putin cat timp toate rutele erau in Dock; de cand paleta
  e singurul drum spre trei dintre ele, reflexul „scriu unde vreau sa ajung" trebuie
  sa mearga. Rutele intra acum in `flatResults` ca grup „Pagini", PRIMUL — asa
  indicii (`selectableIndex`/`nextSelectable`/`totalItems`) raman valizi fara alta
  matematica. `activateResult` intoarce devreme pe `_nav` (o ruta se navigheaza, nu
  se deschide), iar cheia din `{#each}` foloseste `path`, nu `id` (rutele n-au id).
  Verificat pe telefon: „departament"/„proiecte"/„calculator"/„planificator" -> pagina
  respectiva e primul rezultat si Enter ajunge la ea.
  **Capcana de mediu (nu de cod):** login-ul intoarce **429** dupa ~60 de incercari/min,
  iar `login.html` afiseaza „PIN incorect" pentru orice esec — deci un test care
  logheaza des pare ca greseste PIN-ul. Ruleaza pe port nou / asteapta un minut.
  Verificat: `audit_design` curat, `smoke_ui` 28/28, `audit_mobil` complet OK,
  `test_suite` 12/12.

- **2026-07-31 — Glisarea spre dreapta isi spune intentia din primul milimetru.**
  Ion: „glisarea la dreapta pentru indeplinirea taskurilor pe mobil trebuie facuta mai
  frumoasa, o animatie si poate o bifa ce apare — acum doar se coloreaza si nu e
  intuitiv ce face."
  **Problema nu era culoarea, era MOMENTUL.** Singurul semnal (`.gl-bifa`, un fundal
  verde) aparea abia dupa **42%** din latimea randului; pana acolo trageai un rand
  peste nimic. Iar cand aparea, era o culoare — verdele spune „bine", nu spune „FACUT".
  In spatele randului, pe stanga, sta acum `.gl-pista`: bifa + eticheta „Făcut".
  `lib/glisare.js` publica **`--gl-p` (0..1)** = cat din drumul pana la prag s-a facut,
  iar CSS-ul creste fondul, opacitatea si scara bifei continuu — JS-ul nu scrie stiluri
  pe fiecare cadru, scrie o variabila. La prag: pista plina, bifa se umple si pocneste
  (`glPoc`), eticheta intra, plus `navigator.vibrate(12)` (Safari iOS n-o implementeaza,
  deci e optionala, nu o conditie).
  **CSS-ul sta in `global.css`, nu in cele patru componente** — nu doar ca era deja
  copiat de patru ori, dar Svelte TAIE selectorii pusi la rulare din JS (nu doar
  avertizeaza), capcana care odata a lasat o singura regula de gest vie in toata
  aplicatia. In foaia nescopata nu exista scaparea asta.
  **Prins pe parcurs:** panoul de actiuni al gestului OPUS (ancorat la dreapta) iesea
  de sub rand in timpul glisarii spre dreapta — se citea „Azi" in mijlocul confirmarii
  verzi, adica doua raspunsuri la „ce se intampla daca dau drumul". Clasa `gl-dreapta`
  il ascunde cat timp tragi in directia de bifare. Tot atunci: `.gl-pista` are `inset: 0`,
  nu latime dupa continut — altfel verdele se termina dupa eticheta si urma o bucata de
  fundal inchis, deci confirmarea parea o pastila lipita, nu suprafata de sub rand.
  Al treilea: `offsetWidth` se citea la FIECARE `pointermove` (masuratoare de layout in
  mijlocul gestului); acum se citeste o data, la apasare.
  **Regresie acoperita:** sectiunea de gesturi din `audit_mobil.py` esantiona doar
  capatul cursei. Acum esantioneaza tot parcursul si pica daca bifa nu se vede la
  MIJLOC — exact plangerea lui Ion. Verificat prin injectarea regresiei (`opacity: 0`):
  „PICA glisare dreapta: bifa nu se vede pe parcurs (opacitate 0.00 la mijloc)".
  `--gl-p` e declarat in `audit_design.py` la `DIN_JS` — nu e token de design, e stare
  de gest, si de aceea se foloseste mereu cu rezerva `var(--gl-p, 0)`.
  Verificat: `audit_design` curat, `smoke_ui` 28/28, `audit_mobil` complet OK,
  `test_suite` 12/12, plus masuratoare pe gest real (p 0,24 -> 0,60 -> 1,00; scara bifei
  0,66 -> 0,82 -> 1,00; pista `rgb(126,226,168)` la prag; randul chiar se bifeaza).

- **2026-07-30 (11) — Culoarea unui proiect era o proprietate a PAGINII, nu a proiectului.**
  Cercetare pe sistemele de referinta (Radix Colors — scara de 12 trepte cu rol fix per
  treapta; Linear — LCH, 98 variabile de tema reduse la 3; regulile de miscare din
  performance.dev; WCAG 2.2 tinta 24px) si aplicarea rezultatelor.
  **Ce era stricat, masurat:** paleta de identitate exista in DOUA fisiere
  (`Calendar.svelte` si `Plan.svelte`) cu aceleasi sapte culori dar ROTITE pe ultimele
  trei pozitii; functia de dispersie era identica, deci indexul iesea acelasi si cadea
  pe alta culoare — **43% dintre proiecte aveau o culoare in Calendar si alta in
  Planificator**. In plus, barele din Calendar se colorau dupa `proiect_id` dar sertarul
  „Proiecte fara perioada" dupa `client`, deci acelasi proiect avea doua culori pe
  ACELASI ecran (si cum 11 din 12 perioade sunt la Continental, tot sertarul iesea
  monocrom — exact bug-ul pe care Calendarul il rezolvase deja pentru bare).
  **Sursa unica:** `frontend/src/lib/culori.js` — `culoareProiect(id)`, hash pe
  `proiecte.id` (nu pe client: se repeta; nu pe nume: se redenumeste).
  **Paleta e REZOLVATA, nu aleasa** (`scripts/solve_paleta.py`). Prima incercare —
  „sase nuante egal distantate pe roata" — a iesit la 0,055 separare, MAI PROST decat
  productia (0,064): sub deficienta rosu-verde axa rosu-verde se prabuseste, deci
  distantarea pe roata nu inseamna nimic. Ce supravietuieste e LUMINOZITATEA (de aceea
  paleta finala are contraste intre 4,5:1 si 12,2:1, nu sase nuante la fel de intense).
  Rezultat: **0,221 — de 3,5 ori mai bine decat productia**, o nuanta per familie,
  departe de lobii rezervati (amber=accent, coral=danger) si de tokenurile de locatie.
  Compromis acceptat: 6 culori in loc de 7 => la 18 proiecte ~3 impart o culoare.
  Culoarea NU identifica unic un proiect (n-a facut-o niciodata); face acelasi proiect
  recognoscibil de la o zi si de la un ecran la altul, ceea ce acum chiar face.
  **Locatia a devenit token** (`--loc-site`/`--loc-sediu`): erau 8 valori scrise de mana
  in 4 fisiere, cu TREI ambere diferite pentru acelasi „sediu" (`#c99a3a`, `#b98a2e`,
  `#c9a13a`). Chroma mica cu intentie — locatia e un fapt binar si nu are voie sa
  concureze cu identitatea; inainte `site` era exact `#3f9dc4`, valoare aflata SI in
  paleta de proiecte, deci in Planificator aceeasi culoare insemna cand „proiectul X",
  cand „esti pe teren".
  **CAPCANA (lovita si reparata):** `--loc-*` NU se redefinesc pe tema deschisa. Prima
  varianta le-a inchis „ca sa se citeasca pe alb" — dar rolul lor e FILL sub cerneala
  inchisa (`--on-color`), deci banda a iesit inchisa cu text inchis pe ea. Unde valoarea
  chiar e folosita ca TEXT se amesteca spre `--text` la locul folosirii; procentul e
  **55%**, nu 72% — la 70% eticheta pica sub AA pe tema deschisa (3,79:1 masurat).
  **Miscare:** `transition: all` (16 aparitii) inlocuit cu `--transition-colors` /
  `--transition-pressable` — `all` urmareste si proprietatile care reaseaza pagina.
  `--dur-press 0,05s` (sub pragul de 100ms al legaturii cauza-efect).
  **Apasare:** aplicatia avea 146 de reguli `:hover` si 37 de `:active`; pe telefon
  hover NU EXISTA, deci ~109 suprafete nu confirmau atingerea. Podea globala in
  `global.css` cu `:where(...)` (specificitate zero, deci orice componenta o bate),
  doar pe pointer grosier, exclusiv `transform` (se compune pe GPU, nu reaseaza).
  **Prins pe parcurs:** `--text-tertiary` folosit in ProjectDetail nu exista in tokens
  (fallback tacut) -> `--text-dim`; Dock avea `0.28s`, in afara scarii -> `--dur-base`.
  **Ce tine asta in loc de aici incolo:** `scripts/audit_design.py` (7 reguli, exit 1 pe
  abatere) — verificat ca prinde fiecare regula prin injectare de abateri, nu doar ca
  trece. Regula R6 (token folosit dar nedefinit) a prins `--text-tertiary`.
  Verificat: `audit_design` curat, `smoke_ui` 28/28, `audit_mobil` 0 depasiri + gesturi
  OK, `test_suite` 12/12, si culorile citite din DOM confirma acelasi proiect =
  aceeasi culoare in Calendar si Planificator.

- **2026-07-30 (10) — Randul bifat pleaca vizibil; si doua capcane Svelte care
  suprimau animatia in tacere.** Ion: „fă". Animatia in sine e cinci linii
  (`plecare` in `lib/motion.svelte.js`: se stinge SI se strange, cu o impingere mica
  spre dreapta — directia gestului de bifare de pe telefon). Drumul pana la ea a
  scos la iveala trei lucruri:
  **(1) Bifarea astepta serverul.** Randul pleca dupa `await update` + `await reload`,
  adica ~200ms de nimic dupa atingere. Acum lista se schimba OPTIMIST, iar `catch`
  reincarca daca cererea pica. Fara asta, animatia nu se citeste ca raspuns la gestul
  tau, ci ca ceva ce se intampla singur, mai tarziu.
  **(2) `{#if globalTasks.loading}` distrugea TOATA lista la fiecare actiune.**
  `loadGlobalTasks()` se cheama dupa orice modificare, deci fiecare bifare / mutare
  de termen / adaugare inlocuia lista cu cinci schelete si o reconstruia. O clipire
  pe fiecare gest, si — efect secundar — nicio animatie de iesire nu se putea vedea,
  fiindca subarborele ei era demolat in aceeasi clipa. Corect: `&& items.length === 0`
  (schelete doar la prima incarcare), regula pe care TodayBoard o avea deja.
  **(3) CAPCANA SVELTE, meritata scrisa:** un `{#each}` IMBRICAT peste obiecte NOI la
  fiecare recalcul face Svelte sa RE-CREEZE blocul interior in loc sa-l actualizeze —
  chiar si cu cheie stabila pe `g.id` — iar randurile dinauntru sunt distruse fara
  sa-si joace tranzitia de iesire. Zero erori, zero avertismente. Masurat: **0 cadre
  de animatie** cu each imbricat pe obiecte, **13 cadre** cu acelasi rand intr-un each
  de nivel superior. Solutia: `grupeazaDupaTermen` intoarce acum un OBIECT, iar
  sablonul itereaza `ORDINE_GRUPE` — un array constant de siruri — si citeste
  `grupe[id]`. Blocul exterior nu se mai schimba niciodata.
  **(3b) Al doilea strat al aceleiasi capcane:** grupele goale trebuie sa ramana in
  obiect. Daca `{#if grupe[gid]}` se stinge cand grupa ramane fara randuri, blocul in
  care tocmai pleaca ULTIMUL rand e distrus — deci exact cazul cel mai vizibil (bifezi
  ultimul restant) ramanea fara animatie. Sablonul ascunde capul gol; un cap n-are
  nevoie de tranzitie, un rand da.
  Verificat cu o sectiune noua in `audit_mobil.py` care esantioneaza OPACITATEA
  randului la fiecare cadru: cere >= 3 cadre intermediare (adica s-a stins, n-a sarit)
  si plecare sub 900ms (adica n-a asteptat serverul). Ambele liste, ambele conditii.

- **2026-07-30 (9) — Trecere de mestesug pe randul de task: o singura axa de culoare,
  si cod care nu se putea randa.** Ion: „vezi ce putem imbunatati, pe plan de stilistica,
  decizii, stil, design, comoditate, UI, UX". (READMEurile de pe GitHub listeaza
  functii, nu mestesug — asa ca masuratoarea a fost pe propriile ecrane.)
  **(1) Ierarhia era pe dos.** Masurat pe desktop: indexul decorativ „01" era
  16px/700/colorat — cel mai tare text din rand; categoria 11.2/600/mov; TITLUL
  12.8/500; termenul 10.4. Adica numarul de ordine batea continutul. Acum: titlu
  `--font-body`, index fantoma (0.8rem/500, severitate la 38%), termen `--font-tiny`.
  **(2) Trei sisteme de culoare pe acelasi rand** — severitate, mov (categorie),
  amber (subtask/recurenta/proiect). Regula noua, in toate cele trei liste:
  **culoarea e rezervata severitatii**; restul metadatelor sunt gri.
  **(3) Boardul „Astăzi" spunea acelasi lucru de trei ori:** pastila rosie „Restant",
  pastila amber „Termen azi", si data colorata dupa severitate. Pe un board unde totul
  e scadent azi sau restant, pastilele doar partitioneaza lista. Ramane data, relativa:
  „azi" / „ieri" / „acum 3 zile" — si starea, si distanta, intr-un singur chip.
  **(4) Sectiunea „N finalizate" din /tasks NU se putea randa niciodata.**
  `/api/global-tasks` adauga `AND status != 'done'` cand nu ceri arhiva, deci
  `doneTasks` e mereu gol in vederea activa — iar sectiunea era gardata pe
  `!showArchive && doneTasks.length > 0`. ~40 de linii de markup, CSS propriu, o stare
  si un `$effect` de deep-link, toate moarte. Sterse. Starea goala spune acum unde au
  plecat cele bifate, si e adevarata si cand n-ai avut niciodata taskuri.
  **(5) Actiunile de pe randul din pagina de proiect erau `opacity: 0` pana la hover**,
  in timp ce aceleasi butoane din /tasks stau mereu la vedere. Doua liste, acelasi rand,
  doua comportamente — si `opacity: 0` + `:hover` inseamna INEXISTENT pe un laptop cu
  ecran tactil intre 768 si 940px, unde nu prinde nici regula de telefon.
  **(6) 22 de `transition: all`** inlocuite cu proprietati numite (`all` interpoleaza
  si latimi/padding-uri, deci o schimbare de culoare la hover poate misca layoutul).
  **(7) Ritmul de deasupra listei:** primul task incepea la y=296 pe 390×800 (37% din
  ecran). Aceleasi elemente, ~30px mai sus.

- **2026-07-30 (8) — Marginea din stanga a randului de task, si invariantul „azi".**
  Ion: „parca ai lasat cam mult spatiu in stanga la taskuri". Avea dreptate, masurat:
  pe 375px titlul incepea la **x=96**, un sfert din latimea ecranului, pe fiecare rand.
  Trei cauze suprapuse: `.page` are 16px, cartonasul `.list-cell` inca 16 (se adunau),
  iar bifa era o caseta de 44px in care statea un cerc de 18 — 13px de aer de fiecare
  parte, plus 8 de spatiu dupa.
  **Bifa: 44px de ATINS, 30px de LATIME.** Caseta se ingusteaza, suprafata de atingere
  revine dintr-un `::after` cu `inset: -7px`, care se intinde in padding-ul randului si
  in spatiul dintre bifa si titlu — dar se opreste la 1px de `.tmain`, ca sa nu fure
  atingerile care trebuie sa DESCHIDA taskul. Aceeasi reteta in toate cele trei liste.
  **Cartonasul listei isi pierde rama si padding-ul lateral pe telefon.** Odata scos
  padding-ul, randurile ajungeau lipite de propria lui rama — o cutie desenata la 1px
  de continut se citeste ca o greseala. Iar gruparea face acum ce facea el: spune unde
  incepe si unde se termina o bucata de lista. Titlul: **96px → 66px**, randul 305 → 337.
  **Invariantul „azi", acum aparat de audit:** boardul „Astăzi" de pe Acasa si grupa
  „Azi" din `/tasks` sunt ACEEASI multime — `_AGENDA_WHERE` e `status != 'done' AND
  date(data_scadenta) <= today`, deci apartenenta e data de TERMEN, nu de vreun steag
  separat (v33). Verificat in ambele sensuri: pui pe „Azi" din /tasks si apare pe Acasa;
  muti pe „Mâine" si pleaca. Doua liste de azi care se contrazic ar fi mai rele decat
  una singura, fiindca n-ai sti care minte.

- **2026-07-30 (7) — Taskurile se comporta ca o lista DE FACUT, nu ca un depozit.**
  Ion: „poti sa faci ca o aplicatie de to do". Ce lipsea nu era aspectul, ci ORDINEA
  si DRUMUL pana la actiune.
  **(1) Ordinea E informatie.** `/api/global-tasks` intoarce `ORDER BY created_at DESC`
  — ordinea in care le-ai scris. Pe ecran iesea: 30.07, 31.07, fara termen, 29.07
  (restant, rosu), fara termen. Adica randul care tipa era al patrulea. Acum
  `lib/grupare.js` grupeaza dupa termen: **Restante → Azi → Mâine → Zilele astea →
  Mai târziu → Fără termen**, cu cap de grupa lipit (`sticky`) si numar. „Fără termen"
  e ULTIMA cu buna stiinta: e sertarul, nu agenda.
  **(2) Termenul se scrie relativ** (`etichetaTermen`): „azi", „mâine", „acum 3 zile",
  „vineri", „12 aug". „30.07.2026" te pune sa calculezi la fiecare rand. Si NU se
  scrie deloc in grupele „Azi"/„Mâine"/„Fără termen" — capul a spus-o deja.
  **(3) Planificarea a urcat in gest.** Panoul de glisare avea Notă/Editează/Șterge,
  deci mutarea unui termen — cea mai deasa actiune de pe un task — costa patru
  atingeri prin modalul de editare. Acum panoul e **Azi · Mâine · Dată · Șterge**,
  identic pe /tasks si in pagina de proiect (doua liste cu acelasi rand n-au voie sa
  raspunda diferit la acelasi gest). Nota si editarea au coborat in randul desfasurat.
  Patru butoane, nu sapte: la 58px bucata, sapte n-ar mai fi lasat nimic din titlu.
  **(4) Adaugarea si planificarea sunt UN gest.** Cat timp ai text in compozitor apar
  chipurile „Azi / Mâine / Alege data"; Enter ramane „fara termen". Focusul ramane in
  camp dupa adaugare — intr-o lista de facut adaugi trei lucruri la rand.
  **(5) „Anulează" la bifat**, pe toate cele trei liste (Astăzi, Taskuri, proiect).
  Pe telefon se bifeaza si prin glisare, deci se bifeaza si din greseala, iar randul
  DISPARE intr-o sectiune inchisa. `toastUndo` exista deja din 2026-07 (era folosit
  doar la stergerea unui subtask).
  **(6) Croma de deasupra listei**, pe telefon: eticheta cartonasului si coloana
  „Agenda — 7 zile" au plecat (a doua e acum o copie a gruparii), cautarea se plieaza
  intr-o iconita de 44px, sageata de desfasurare a plecat de pe rand, iar categoria
  e text simplu — pastila mov era cel mai tare lucru de pe rand, mai tare decat
  titlul si decat termenul. Titlul are voie sa cada pe DOUA randuri: pe una singura,
  „Reinnoire certificat de acces in site Co…" nu spune la ce site.
  **Capcane prinse pe drum:** `.quick-add` era `flex-direction: row`, deci chipurile
  de zi se asezau LANGA camp si ieseau din ecran; `.sub-add-btn` n-avea `flex-shrink: 0`
  si se stringea la 12px (masurat); „sterge subtask" era `opacity: 0` pana la hover,
  adica invizibil pentru totdeauna pe touch; indexul mono renumara de la 01 in
  fiecare grupa („01, 01, 01, 02") pana l-am facut continuu.
  Verificat cu `scripts/audit_mobil.py`, care are acum si sectiunea „lista de facut"
  (12 verificari: gruparea, ordinea grupelor, adaugarea cu zi, mutarea din gest,
  „Anulează" dus si intors). **Gotcha de testare:** un gest sintetic din PointerEvent
  NU produce `click`-ul pe care il trimite browserul dupa ridicarea degetului — iar
  `glisare.js` inghite exact acel click. Fara el in test, steagul „tocmai am glisat"
  ramane ridicat si prima apasare pe un buton din panou e inghitita; arata identic cu
  „butonul nu functioneaza".

- **2026-07-30 (6) — A doua trecere pe telefon: masurata, nu privita. Plus patru
  reguli scrise pentru telefon care nu se aplicau nici pe telefon.** Auditul nou
  (`scripts/audit_mobil.py`, toate rutele × 375/360/390px) a gasit ce nu arunca nicio
  eroare si de aceea trecuse de build, de `smoke_ui` si de `test_suite` 12/12:
  **(1) CSS mobil ANULAT de reguli scrise mai jos in acelasi fisier.** Un `@media` NU
  adauga specificitate — la specificitate egala castiga ultima regula. In `Plan.svelte`
  blocul `@media (max-width: 768px)` statea la mijlocul fisierului, inaintea sectiunilor
  „backlog rail" si „controls": DOUASPREZECE selectoare (`.bl-chip`, `.bl-txt`, `.bl-proj`,
  `.bl-date`, `.page`, `.page-header`, `.controls`…) erau moarte. Masurat in pagina:
  chipul avea tot `max-width: 320px`, butonul de data tot 30px in loc de 44. Blocurile
  mobile sunt acum ULTIMELE din fisier; sectiuni noi se adauga DEASUPRA lor.
  **(2) Svelte TAIE selectorii cu clase puse din JS, nu doar avertizeaza.** `.arow.gl-tras`,
  `.trow.gl-bifa` etc. sunt adaugate la rulare de `glisare.js`, deci compilatorul le crede
  moarte. In CSS-ul LIVRAT supravietuise UNA din toate regulile de gest: glisai spre dreapta
  si nu vedeai verdele care spune „ai trecut pragul". Reteta: `:global()` DOAR pe clasa de
  rulare, ancora ramane scoped — `.arow:global(.gl-bifa)`.
  **(3) Tooltip la ATINGERE.** `pointerover` se apara de touch, dar drumul prin `focusin`
  nu se apara, si el porneste imediat (fara cele 380ms). Pe telefon, orice buton cu `title`
  scotea o bula PESTE exact lucrul atins. Paza: `nod.matches(':focus-visible')` — raspunsul
  browserului la „focusul asta merita aratat?", adevarat la Tab, fals la atingere.
  **(4) Reordonarea „Astăzi" pe touch** — `draggable` HTML5 nu exista pe telefon, iar
  inlocuitorul erau doua sageti de 40×22 pe FIECARE rand (76 pe un ecran). Acum
  `lib/reordonare.js`: maner de 44px cu `touch-action: none` (doar pe el, ca restul randului
  sa deruleze si sa gliseze mai departe), ordinea din DOM NU se atinge in timpul tragerii
  (doar `transform`-uri; Svelte rearanjeaza la final, cu `flip`). Pragul de schimb e la
  JUMATATEA randului tras, nu la mijlocul vecinului — vecinul se da la o parte cand treci
  pe langa el, deci prima varianta sarea o pozitie in loc de doua.
  **(5) Titlurile pe telefon** — `--font-h1` 28→21px etc. intr-un `@media` in `tokens.css`
  (tokenul, nu sapte pagini). Titlul unui proiect cadea pe PATRU randuri; iar cand titlul
  nu se putea micsora, butoanele ieseau din ecran — pe /projects „Proiect Nou" era retezat.
  `.page-header` a primit `flex-wrap`+`gap` (Projects si Tasks n-aveau niciunul).
  **(6) O SINGURA sursa pentru „suntem pe telefon"** — `lib/ecran.svelte.js` (`ecran.telefon`,
  `ecran.larg`), in locul a patru copii de `matchMedia('(max-width: 768px)')` cu propriul
  ascultator (Modal, DatePicker, TodayBoard, Calculator).
  **(7) `init_db()` CRAPA pe o baza NOUA** — `migrate_v1_to_v2` facea index pe `atasamente`
  si `migrate_v17_to_v18` o reconstruia; tabela a plecat in v28, deci un deploy curat murea
  la prima cerere. (`PRAGMA table_info` pe o tabela inexistenta intoarce zero randuri —
  exact semnatura lui „lipseste coloana".) Ambele sunt acum gardate pe existenta tabelei.
  Rezultat masurat: 21 combinatii ruta×latime, zero depasiri, zero tinte sub prag, zero
  campuri sub 16px; singura exceptie acceptata e reperul de o zi din Ganttul Planificatorului
  (26px cu buna stiinta — la 44px reperele din zile alaturate s-ar acoperi unul pe altul).

- **2026-07-30 (5) — Randul de task pe telefon: o linie + glisare; Planificatorul isi
  recapata timpul; Calendarul se reaseaza.** Ion, dupa prima trecere: „acum sunt cam rupte,
  prea mari pe inaltime; sa fie aproape de cum sunt pe aplicatii de to do mobile".
  **(1) `lib/glisare.js`** — actiune Svelte refolosita de toate cele patru liste de taskuri
  (Acasa, Planificator, Taskuri, ProjectDetail). Glisare stanga = panou de actiuni; glisare
  dreapta = bifeaza; atingere pe titlu = deschide. Randurile: 172 -> 62px (Acasa), 110 -> 56
  (Taskuri), doua linii -> 56 (Planificator). **Trei lucruri obligatorii:** directia se decide
  O SINGURA data la primii 8px (altfel lista nu se mai poate derula vertical); `touch-action:
  pan-y` lasa derularea browserului nativa; un singur rand deschis global; `click`-ul de dupa
  gest se inghite in faza de capturare, altfel ajunge la ce era dedesubt.
  **Capcana:** `setPointerCapture`/`releasePointerCapture` arunca `NotFoundError` daca
  pointerul nu mai e activ si rupeau restul gestului — sunt intr-un try/catch, captura e o
  imbunatatire, nu o conditie.
  **(2) `.app-content` avea `overflow-y: auto`** — a doua oara aceeasi capcana ca la
  `.app-main`: face container de derulare, deci ORICE `position: sticky` dintr-o pagina se
  raporta la scrollportul lui, care nu deruleaza niciodata (documentat inca din 2026-07-03:
  fereastra deruleaza, nu `#main-content`). Mureau in tacere: antetul de zile din Planificator,
  bara laterala din pagina de proiect, capul de tabel, navigarea din Calculator. Scos.
  **(3) Planificatorul are timeline si pe telefon.** Sub 820px swimlane-ul era ascuns si ramanea
  o lista fara timp. Acum fiecare grup de proiect are BANDA lui — acelasi lane, intors la latime
  plina, cu numele deasupra in loc de la stanga — plus un antet de zile COMUN si lipicios sub
  bara aplicatiei. Geometria e cea existenta (`spanRect` da procente), zero calcule noi.
  Reperele de task sunt puncte care duc la randul lor din lista, cu `focus-flash` — nu deschid
  un al treilea meniu. **Aliniere:** `--m-pad` = rama grupului (1) + paddingul lui (8) +
  marginea benzii (3); daca cele trei nu sunt in acord, coloana „marti" cade langa marti.
  **(4) Calendar reasezat pe o coloana:** panoul zilei statea DEASUPRA grilei, deci atingeai o
  zi si raspunsul aparea in afara ecranului. Acum harta, apoi ziua atinsa sub ea, apoi
  contoarele (rezumat, nu intrebare de inceput).
  **(5) Legenda chiar era stricata:** „pe teren" si „implementare" aveau EXACT aceeasi umplere
  (45%) — doua patratele identice cu doua intelesuri. Nu e scapare de culoare: ambele axe
  folosesc „plin" pentru valoarea pozitiva. Se repara numind intrebarea („Unde" / „Fază"), nu
  schimband mostra; mostrele folosesc acum aceleasi retete ca benzile din grila.

- **2026-07-30 (4) — Aplicatia pe telefon: „fara compromisuri".** Ion: „vreau sa faci aplicatia
  maxim de comoda pentru mobil". Auditat automat fiecare ruta la 375×812 si 360×740 (overflow,
  tinte sub 44px, inputuri care declanseaza zoom pe iOS, continut taiat). Ce s-a schimbat:
  **(1) Headerul „sticky" nu se lipise NICIODATA.** `.app-main` avea `overflow: hidden`, ceea ce
  face din el un container de derulare, iar `position: sticky` dinauntru se raporteaza la
  scrollportul LUI (care nu deruleaza). Verificat: derulezi 400px, headerul pleaca cu 400px.
  `overflow-x: clip` taie la fel pe orizontala fara sa creeze container de derulare.
  **(2) Modalele si DatePicker-ul = sheet de jos pe telefon** (≤768px), cu blocarea derularii
  paginii de dedesubt (contor comun intre instante) si tranzitie `translateY(100%)` — nu `fly`,
  care ar avea nevoie de o distanta in px si arata altfel pe un sheet scund fata de unul inalt.
  Zilele din DatePicker: 34px → 45px.
  **(3) `input`/`select`/`textarea` la minim 16px pe telefon** (`!important`, ca la
  `input[type=date]`): sub 16px Safari mareste pagina la focus si NU o micsoreaza inapoi.
  **(4) Tinte de atingere la 44px** peste tot. Unde marimea vizibila conteaza (pastila de status
  din cardul de proiect, steaua din Calculator) creste doar suprafata, printr-un `::after`
  absolut — casetele cresc, semnele nu.
  **(5) Calendar: plasare prin ATINGERE.** Drag-and-drop-ul HTML5 nu se declanseaza la deget,
  deci „Proiecte fara perioada" NU se putea planifica deloc de pe telefon. Acum: alegi proiectul
  (se aprinde), atingi ziua (toate zilele devin tinte punctate), Escape/re-atingere renunta.
  Nu un al doilea calendar peste calendar — acelasi gest, rupt in doua atingeri. Benzile devin
  `pointer-events: none` sub 620px: aveau 12px si furau atingerea celulei de ~50×70.
  **(6) `/plan` se derula LATERAL pe telefon:** `.controls` avea 502px intr-un ecran de 375 si,
  nefiind `flex-wrap`, impingea toata pagina.
  **(7) Tabelele din wiki erau TAIATE** pe telefon (ultima coloana, fara nicio cale spre ea) —
  `display: block` + `overflow-x: auto` doar sub 768px; pe desktop raman `width: 100%`.
  **Capcane:** o regula globala `@media (hover: none) { *:hover { transform: none } }` ar fi
  anulat si `translateX(-50%)` al dock-ului (hover-ul urca la stramosi) — hover-urile care MISCA
  sunt gardate individual cu `@media (hover: hover)`; bara editorului de text NU poate deveni
  scroller orizontal (meniul de stil e pozitionat absolut si ar fi taiat) — doar butoane mai mari;
  `flex: 1 1 auto` pe titlul randului din „Astazi" tot rupea randul, fiindca latimea DORITA intra
  in calculul de wrap — trebuie `flex: 1 1 0` plus un invelis `display: contents` care pe telefon
  devine linia a doua (altfel randul iesea pe trei linii, 172px/task).
  Verificat: `smoke_ui.py` OK pe desktop si mobil, `test_suite.py` 12/12, zero erori de consola,
  desktopul neschimbat (swimlane, dock 50px, randuri pe o linie).

- **2026-07-30 (3) — Trei campuri scoase din formularul de proiect (v36).** Ion: „sterge cele 3
  puncte". `nr_contract` (1/18), `pm` (4/18 — si toate cu paranteze explicative, deci notita nu
  date), `data_incepere` (5/18 si **dubla prima perioada**). Banda proiectului se calculeaza acum
  din perioade: `prima_zi = MIN(implementari.data_start)`, `ultima_zi` = cea mai tarzie zi
  planificata; cheia din `/api/plan` s-a redenumit ca sa nu rămână un consumator care citeste
  tacit altceva. Arhiva: `raw/pif-dashboard/2026-07-30-inainte-de-v36/`.
  **Capcana a cincea:** `COLOANE_DATA` enumera `('proiecte', ('data_incepere',))` — self-heal-ul
  ar fi re-adaugat coloana la prima pornire.
  **Bug vechi prins:** `gantt.pdf` dadea 500 din v32 (`stasks` orfan dupa scoaterea gruparii pe
  faze). Nicio verificare nu atingea ruta — de aceea testul nou chema efectiv fiecare scriere si
  fiecare export, nu doar numara semnele de intrebare din INSERT.

- **2026-07-30 (2) — O perioada de mai multe zile e UN element, nu N bucati.** Ion: „regandeste
  cum arata in calendar perioadele de implementare pe mai multe zile". Desenam o bara in fiecare
  celula, fiecare cu numele scris din nou si tăiat la latimea unei zile — o lucrare de 8 zile
  aparea ca 9 obiecte ciuntite, desi avea 6 celule de spatiu. Acum benzile sunt elemente ale
  grilei, cu `grid-column: <col> / span <n>`, taiate doar la granita de saptamana.
  **Trei capcane:** `1fr` e `minmax(auto, 1fr)`, deci o banda cu `nowrap` largea coloanele si
  strica alinierea — trebuie `minmax(0, 1fr)`; celulele trebuie asezate explicit in grila,
  altfel auto-plasarea sare peste pozitiile benzilor; benzile trebuie sa devina transparente la
  cursor cat timp tragi, altfel dropul nu ajunge la celula.
  **Bug vechi prins:** clasa `azi` era pe butonul „Azi" SI pe celula zilei de azi, iar `.azi`
  neprefixat centra numarul in mijlocul celulei. Butonul e acum `.b-azi`.

- **2026-07-30 — Un proiect inchis se opreste in ziua INCHIDERII, nu azi (v35).** Prima
  incercare taia perioadele proiectelor `finalizat` la `date('now')`. Ion: „am finalizat un
  proiect de ieri dar a mai aparut si pe azi". Perioada era 29->30, inchisa pe 29 — deci
  ziua 30 rămânea. Reperul corect e `proiecte.data_finalizare` (v35), backfill din
  `updated_at` (a nimerit: proiectul cu motoare avea `updated_at = 2026-07-29T16:19`).
  **Invariant:** data exista daca si numai daca statusul e `finalizat` — se pune la
  inchidere, se sterge la redeschidere. Fara el, formularul trimite data veche la
  redeschidere (DatePicker-ul se ascunde, valoarea rămâne in `form`) si o re-inchidere ar
  reveni in tacere la ziua veche. Corectabila din „Finalizat pe" in formularul de proiect;
  vizibila in bara laterala, in locul celulei „Urmatoarea perioada" (care pentru un proiect
  inchis n-avea decat „Neplanificat" de spus). Taierea e doar la citire — `/api/calendar` si
  `/api/export/ics`; DB neatins, Ganttul proiectului arata tot.
  **Lectia:** „scoate-l din calendar cand il inchid" nu e acelasi lucru cu „taie la azi";
  diferenta apare doar cand inchizi inainte de vreme, adica in cazul care l-a deranjat.

- **2026-07-27 (3) — Calendar, in locul celor trei liste.** Feedback Ion: „nu prea inteleg sensul,
  nu se poate mai elegant si mai interactiv?" — avea dreptate. Raspunsesem la o intrebare SPATIALA
  („unde sunt marti") cu trei liste de text (rand de cifre in Planificator, card pe Acasa, pagina
  /review). Aplicatia avea deja destule liste.
  **Inlocuite toate trei cu `/calendar`** (`Calendar.svelte` + `lib/calendarDates.js`, `GET /api/calendar`):
  grila lunara sau 2 saptamani, culoarea codeaza **clientul** (unitatea reala e DEPLASAREA, nu
  lucrarea), blocuri continue pe zile multiple, azi si zilele care cer o decizie marcate pe zi.
  Interactiune: click pe zi -> panou cu lucrarile si actiunile; **drag** unei perioade pe alta zi =
  replanificare cu pastrarea duratei; **drag** dintr-un proiect din banda „Fara data" pe o zi = creeaza
  perioada; buton „Muta" cu DatePicker pentru mobil (drag HTML5 nu merge la atingere).
  „Deplasari" = zile CONSECUTIVE la acelasi client (28-29-30 la Continental = 1 iesire, nu 3).
  Home pastreaza doar KPI-ul „Ce alunecă" (numar), care duce in calendar — detaliul sta pe ziua lui.
  Sterse: `Review.svelte`, `/api/review`, randul „Pe teren" din Plan.svelte, `client`/`locatie` de pe
  lane-urile `/api/plan` (calendarul are endpointul lui).
  **Lectie:** cand intrebarea e „unde/cand", raspunsul trebuie sa fie o harta sau un calendar, nu o
  lista. Verificat inainte de a construi cu un mockup pe date reale, aprobat de Ion.

- **2026-07-27 (2) — monitorizare pe PERIOADE, nu pe deadline.** Datele reale: doar 2 din 20 de
  proiecte au deadline, dar 12 au perioade de implementare (14 in total). Taskurile cu date sunt
  nefolosite (1 cu `data_start`, 0 progres, 0 milestones, 0 dependente) — planificarea reala a lui
  Ion sunt PERIOADELE, iar Ganttul de taskuri e practic mort. Tot ce e monitorizare se citeste de
  acolo. Trei lucruri livrate:
  1. **Rand „Pe teren" in Planificator** — cate lucrari pe zi; grupate pe `client` (adaugat in
     `/api/plan`, pe lane). Mai multe la acelasi client = o deplasare (chip neutru), la clienti
     diferiti = suprapunere reala (chip amber + „N zile de verificat"). Doar in modul pe zile.
  2. **Card „Ce alunecă" pe Home** (inlocuieste cardul + KPI-ul de Deadline-uri, care aratau max 2
     randuri). Trei semnale in `/api/dashboard/home` -> `risc`: perioada trecuta cu status nemiscat;
     perioada in <7 zile pe proiect fara taskuri; proiect `in_lucru` fara nicio perioada viitoare.
  3. **Pagina `/review`** (`GET /api/review`) — De clarificat / Urmeaza / S-a facut, cu butoane care
     schimba statusul din lista (S-a facut, In lucru, Replanifica — replanificarea pastreaza durata
     perioadei) + rezumat text copiabil.
  **Dependente NU s-au construit** — datele arata zero utilizare; ar fi fost aceeasi greseala ca la
  parametri (structura corecta teoretic, deconectata de cum lucreaza).
  **Bug reparat pe drum:** `/api/backup` NU includea `implementari` si `task_dependencies` — un
  restore din JSON ar fi sters in tacere toate cele 14 perioade. Adaugate in backup + restore.
  **Alt fix:** `pregatire` lipsea din `PROJECT_STATUS_LABELS` (backend + frontend) desi 10 din 20 de
  proiecte il au — se afisa raw peste tot.
  Curatat si Admin: scos campul „Foldere" (filtru care servea doar pagina Notite) + rutele
  `/api/obsidian/notes` si `/api/obsidian/search`, ramase fara consumator dupa v28.

- **2026-07-27 — v28: restrangere de scop.** Dashboard-ul nu mai dubleaza wiki-ul si manualele.
  Sterse: `parametri_master` (14.813 randuri), `fault_codes` (3.851), `echipamente` (26, in 4 din 20
  de proiecte), `atasamente` (30 fisiere). Sterse si: `blueprints/parametri.py`, paginile
  `Params.svelte` / `Notes.svelte`, `AttachmentsTab`, `EquipmentFormModal`, `AttachmentPreview`,
  `data/fault_codes/` (3,84 MB seed), `scripts/enrich_params_from_backup.py`, endpoint-urile
  `/api/admin/enrich-params` + `/api/admin/bulk-add-params`, sectiunea „Audit DB Parametri" din
  Admin, sectiunea de echipamente din exportul PDF si Markdown.
  **Motiv:** catalogul de 18k randuri nu avea nicio legatura cu proiectele — parametrii si codurile
  de eroare se iau din manual (sursa citabila), backup-urile de drive stau brute in vault unde le
  citeste `drive-backup`.
  **NU s-a atins Calculatorul.** Atentie: el depinde de `/api/import-abb-multi/preview` si
  `/api/import-archive/preview` — le-am sters din greseala si le-am repus; `scripts/parse_params/`
  trebuie sa ramana. Tabul „Din proiect" din modalul de import a disparut (depindea de tabela
  `echipamente`); tabul de incarcat fisier ramane si merge fara login.
  **Verificat:** migratia ruleaza curat pe DB local (v27 -> v28, 4 tabele + 6 indexuri sterse),
  `/api/import-abb-multi/preview` parseaza un `.dcparamsbak` real (70 parametri, placuta motor
  80 A / 686 V / 75 kW / 2960 rpm), build trece, fara erori in consola.
  **Arhiva:** `raw/pif-dashboard/2026-07-27-inainte-de-v28/` in vault (JSON + CSV per tabela,
  snapshot integral, seed-uri fault codes, parsere, README cu procedura de recuperare). `raw/` e
  gitignored — arhiva e propagata prin Google Drive, nu prin git.
  **Migrare echipamente:** cele 13 de la Retrofit FML3 -> `wiki/job/projects/continental-fml3/`
  (`backup-<drive>.md` + `backups-index.md`). Restul erau deja acoperite in wiki, cu mai multi
  parametri decat in DB. Bonus: recuperat `FAA.dcparamsbak` (backup final) din atasamentul
  `Backupuri Multidrive.zip` — nu exista in vault; nota `backup-FAA.md` ramane de generat.

- **2026-07-15 — Taskuri = repere cu etichetă (Gantt + Planificator)** (SW v94): Taskurile lui
  Ion sunt aproape toate de o zi → pe un timeline de luni întregi barele deveneau dungi de ~3px
  invizibile (mai ales pe tema deschisă). Decizie (ales de Ion): „Timeline = perioade + repere".
  **ProjectGantt.svelte**: taskurile nu mai sunt bare, ci **puncte** (`.dot`, colorate pe status)
  la data scadentă, cu **linie subțire** start→scadență dacă au durată reală; milestone = romb.
  Fiecare marker are **etichetă cu titlul** lângă el (`.mk-label`, flip la stânga peste 58% ca
  să nu iasă din ecran). Adăugat marcaj **deadline** (linie punctată). **Plan.svelte**: taskurile
  de o zi arătau doar `◆` fără text (`.bar.single .bar-txt{display:none}` + `::after '◆'`) →
  acum romb (`.pin-dot`) + eticheta titlului lângă el (flip peste 62%). Motiv: Ion nu-și dădea
  seama ce task e fără hover. Tot needitabil în Gantt; export PDF/Excel **încă desenează bare**
  (follow-up: de trecut și exportul pe repere pt PDF-ul de client).

- **2026-07-15 — Gantt per-proiect refăcut ca listă read-only + timeline** (SW v93):
  Ion voia taskuri **needitabile** aici (se gestionează în tabul Taskuri), fără procentaje
  (taskurile lui sunt discrete făcut/nefăcut), arătate ca o listă simplă (stil widget-ul
  „Task-uri urgente" de pe Home). `ProjectGantt.svelte` rescris: stânga = listă read-only
  (`.tk-row`: index/bifă + titlu + sub-linie faza/interval + due-chip azi/mâine/depășit),
  dreapta = timeline read-only (bare solide pe status, fără %/fill; milestone ◆; benzi
  Site/Sediu). Finalizate = `CheckCircle2` + titlu tăiat. Click pe task → sare la tabul
  Taskuri cu focus (`ProjectDetail.openTaskFromGantt` setează `router.query.focus` +
  `activeTab='tasks'`; prinde `focusOnLand`). Scos tot ce era editare: tabelul editabil,
  drag/resize, dependențe+săgeți on-screen, Auto/Reprogramează/Drum critic, „Avansat",
  „Task nou". Singura editare rămasă = **perioada de implementare** (`ImplPeriodModal`).
  Export PDF/Excel neschimbat (backend intact; dependențele rămân în DB + în export).
  Tradeoff: `is_milestone`/`faza`/`data_start` nu se mai setează din Gantt (rar folosite).

- **2026-07-15 — Gantt per-proiect simplificat (calm by default)** (SW v92): Ion găsea ganttul din
  proiect prea complicat față de Planificator. `ProjectGantt.svelte`: toggle nou `Avansat` (persistat
  localStorage `pif-gantt-adv`, off implicit) ascunde uneltele PM avansate — dependențe+săgeți, `Auto`
  reschedule, `Drum critic`. Implicit vizibile doar `Task nou / Perioadă / PDF / Excel / Avansat`. Tabel
  redus la `Task | Fază | Start | Sfârșit | %` (scoase coloanele `#` și `Zile`; durata rămâne în tooltip-ul
  barei). Rânduri: 2 iconițe implicit (milestone + șterge), a 3-a (`Link2`) doar sub Avansat. Zero
  modificări backend — dependențele rămân în DB, doar săgețile se ascund. `.g-table` 560→440px.

- **2026-07-03 — Perioade de implementare pe Planificator (/plan) + fix Gantt empty-state** (SW v90):
  (1) Fix: `ProjectGantt` ascundea tot timeline-ul cand `data.tasks.length===0` → o perioada pe un
  proiect fara taskuri nu se vedea. Acum arata Gantt-ul daca exista taskuri SAU perioade (EmptyState doar
  cand ambele lipsesc). (2) Perioadele apar acum si pe **Planificatorul multi-proiect** (cerut de Ion, „B"):
  `/api/plan` ataseaza `implementari[]` per lane de proiect (cele care intersecteaza fereastra; lane-ul
  apare si daca are DOAR o perioada in fereastra). `Plan.svelte`: `views` calculeaza rect-uri pt perioade,
  randate ca benzi colorate (site=teal #3f9dc4 / sediu=gold #c99a3a) sus in fiecare lane, + in lista mobila
  ca `.mimpl`. Verificat E2E: API 2 impl/lane, 2 benzi pe /plan, 0 erori.

- **2026-07-03 — Perioade de implementare per proiect (Site / Sediu EGB)** (SW v88, SCHEMA v26): cerut de
  Ion — pe proiect, perioade de implementare SEPARATE de taskuri, cu locatia Site (santier) / Sediu EGB;
  mai multe per proiect; afisate SI ca banda pe Gantt SI in tabul Info. **Migratie v25→v26:** tabel
  `implementari` (proiect_id FK CASCADE, data_start, data_sfarsit, locatie 'site'|'sediu', eticheta,
  ordine). **Backend (projects.py):** CRUD `GET/POST /api/proiecte/<id>/implementari`, `PUT/DELETE
  /api/implementari/<id>`; `_collect_gantt` (tasks.py) intoarce si `implementari[]`. **Frontend:**
  `components/projects/ImplPeriodModal.svelte` (form partajat: DatePicker×2 + toggle Site/Sediu EGB +
  eticheta + delete); `ImplPeriods.svelte` (tabel in Info, add/edit/delete); in `ProjectGantt` perioadele
  = rZnduri `kind:'impl'` la INCEPUTUL `displayRows` (banda colorata site=teal #3f9dc4 / sediu=gold
  #c99a3a, separata de bare), buton „Perioadă" in toolbar, click→modal. Fereastra Gantt include datele
  perioadelor. **Exporturi:** PDF (rand+banda colorata sus) si Excel (randuri impl sus cu celule
  colorate) le includ. Verificat E2E: 2 benzi Gantt + 2 randuri Info + modal, PDF+XLSX cu perioadele.

- **2026-07-03 — Gantt de proiect: cele 4 imbunatatiri + faze (Plane-inspired)** (SW v87, SCHEMA v25):
  Ion a cerut toate 4 + „conform Plane". **(1) Logo + semnatura PDF:** marca ramp amber desenata in
  reportlab (`_draw_logo`) + wordmark „PIF DASHBOARD" + bloc semnatura jos-dreapta (Intocmit/Aprobat
  client + Data). **(2) Drag/resize pe bare** in ProjectGantt (pointer events ca in Planificator; move
  = tot spanul, margini = o muchie, milestone drag; scrie data_start/data_scadenta). **(3) Reprogramare
  automata:** `_reschedule_project` (forward-pass ASAP, topological Kahn, FS/SS/FF/SF + lag, pastreaza
  durata, muta doar mai tarziu) + `POST /api/proiecte/<id>/reschedule`; buton „Reprogrameaza" + toggle
  „Auto" (localStorage) care ruleaza dupa fiecare `patch`. **(4) Drum critic:** CPM pe frontend (durate +
  DAG, forward/backward, slack=0), toggle „Drum critic" evidentiaza cu rosu barele+sagetile. **(5) Faze
  (Plane cycles):** migratie v24→v25 `tasks.faza TEXT`; view grupeaza pe faza in `displayRows` (rand
  fază = header colapsabil + summary bar cu progres rulat duration-weighted; taskuri indentate; coloana
  „Fază" editabila; `idxMap`/SVG height pe displayRows ca sagetile/critical sa ramana corecte). Backend:
  create/update/collect duc `faza`; EXPORTURILE grupeaza pe faza — PDF cu header bold + summary bar per
  faza, Excel cu coloana „Faza" + tasks sortate pe faza. Verificat E2E: drag/resize, reschedule cascada
  A→B→C, drum critic 3 bare+2 sageti, faze 3 grupuri+collapse (fara regresie), PDF+XLSX randate corect.
  **Gotcha sandbox:** procese `app.py` vechi raman pe portul 5000 (pkill in compound da exit 144 fara sa
  omoare) → `for p in $(pgrep -f app.py); do kill -9 $p; done`. Toate livrate incremental (v83→v87).

- **2026-07-03 — Excel Gantt real (nu tabel + grila coarse)** (cerut de Ion: „excelul trebuie tot sa fie
  Gantt altfel nu are sens"): rescris `export_gantt_xlsx` — coloane pe **ZI** (adaptiv la saptamana daca
  spanul >92z), **banda de luna** merged (RO: Ian..Dec) deasupra, header cu numar zi (weekend gri / azi
  cu fill amber), info stanga compact (#/Task/Start/Sfarsit/Zile/%), **bare = celule colorate** pe span
  cu **progres split** (partea facuta = nuanta inchisa `done_hex`, restul = nuanta deschisa `rem_hex`;
  done_cells = round(barlen*progres/100)), milestone = ◆ in celula de start, `freeze_panes` la prima
  coloana de grila (info + header raman fixe). SHADES per status. Verificat: done=toate inchise,
  in_progress 40%/4z = 2 inchise + 2 deschise, banda „Iun 2026/Iul 2026", freeze G6. (LibreOffice
  headless din sandbox nu incarca xlsx — validat programatic cu openpyxl.)

- **2026-07-03 — Gantt de proiect — FAZA 3 (dependente cu sageti) + FAZA 4 (export PDF + Excel)** (SW v83):
  **Faza 3:** sageti de dependenta desenate ca SVG peste `.g-body` (bind:clientWidth → coordonate px,
  path ortogonal cot + varf), din `data.dependencies`. Creare prin **link-mode** (buton lant `Link2` pe
  rand: click pe predecesor → banner → click pe succesor → POST dependency); stergere prin **click pe
  sageata** (DELETE). Verificat E2E: 1 sageata seed, creare 1→2, stergere 2→1, 0 erori. **Faza 4 (ales
  de Ion: „si si" — PDF SI Excel, per-proiect):** export **SERVER-SIDE** (nu print de browser — client-
  ready, consistent). `GET /api/proiecte/<id>/gantt.pdf` (reportlab canvas, landscape A4): antet
  proiect/client/cod/perioada/generat + gantt desenat (label-uri, bare cu fill de progres, milestone
  diamant, today line, sageti dependenta, zebra, legenda). `GET /api/proiecte/<id>/gantt.xlsx` (openpyxl):
  antet + tabel (#/Task/Start/Sfarsit/Zile/%/Status/Milestone/Depinde de) + **grila saptamanala** cu
  celule colorate pe status (gantt vizual in Excel), freeze panes. Helper comun `_collect_gantt` (JSON +
  ambele exporturi il refolosesc). Butoane „PDF"/„Excel" (anchor GET, sesiune) in toolbar-ul Gantt.
  GOTCHA: `from io import BytesIO` lipsea in tasks.py (500 la prima incercare). Verificat: PDF valid
  (`%PDF-`, randat corect), XLSX zip valid (tabel + grila, 13 coloane). Cele 4 faze COMPLETE.

- **2026-07-03 — Gantt de proiect — FAZA 2: view-ul (tab in ProjectDetail)** (SW v82): tab nou „Gantt"
  in `pages/ProjectDetail.svelte` (dupa Taskuri) → `components/gantt/ProjectGantt.svelte`. Layout
  two-pane GanttProject-style: **tabel taskuri stanga** (# / Nume / Start / Sfarsit / Zile / % / actiuni)
  + **timeline dreapta** (overflow-x). Randurile aliniate prin inaltimi fixe (`--row-h`/`--head-h`),
  scroll vertical comun (pagina), doar timeline-ul scrolleaza orizontal. Fereastra se **auto-fit** pe
  spanul real al proiectului (taskuri + data_incepere/deadline, padded) + coloane adaptive
  (`buildColumns` refolosit). Bare start→end cu **fill de progres** (latime = progres%), **milestone**
  = diamant (is_milestone), status = culoare (done verde / in_lucru amber / to_do contur), today line +
  weekend. **Editare inline in tabel**: Start/Sfarsit via DatePicker, % via input (blur/Enter),
  milestone toggle (flag), rename (click pe nume), sterge, „Task nou". % din subtaskuri e READ-ONLY
  (afisat cu tooltip done/total); doar taskurile fara subtaskuri au input manual. Foloseste
  createTask/updateTask/deleteTask din store + `/api/proiecte/<id>/gantt`. Verificat E2E: 6 randuri, 5
  bare + 1 milestone, fills 100/100/40/0/0, 0 erori. **URMEAZA:** Faza 3 sageti dependente (datele vin
  deja in payload), Faza 4 export PDF profesional + Excel.

- **2026-07-03 — Gantt de proiect „GanttProject-lite" — FAZA 1: schema + backend** (SCHEMA v24): Ion
  vrea un Gantt per-proiect complet, client-ready (prezentat ca PDF + export Excel, selectand proiectul),
  cu tabel taskuri + start/sfarsit + %progres + dependente cu sageti + milestones. Se construieste in
  faze; asta e fundatia. **Migratie v23→v24** (`migrate_v23_to_v24`, idempotenta + self-heal):
  `tasks.data_start TEXT`, `tasks.progres INTEGER`, `tasks.is_milestone INTEGER` + tabel nou
  `task_dependencies` (id, proiect_id, predecessor_id, successor_id, tip FS/SS/FF/SF, lag, FK CASCADE la
  proiecte+tasks; STRICT intre taskuri de proiect). create_task/update_task extinse cu cele 3 campuri
  (COALESCE, is_milestone normalizat 0/1). delete_task sterge si dependentele (explicit + FK).
  **Endpoint nou** `GET /api/proiecte/<id>/gantt` → {proiect, tasks[], dependencies[]}; task-ul are
  `data_start` (fallback data_planificata), `data_scadenta`, `is_milestone`, `progres` EFECTIV
  (`_effective_progress`: 100 daca done, altfel raport subtaskuri bifate daca are, altfel coloana
  `progres` manuala) + subtask_done/total. `POST /api/proiecte/<id>/dependencies` (valideaza ambele in
  proiect, blocheaza self/duplicat/CICLU via `_would_cycle` DFS pe succesori), `DELETE
  /api/dependencies/<id>`. Verificat: schema v24, done→100%, milestone, subtask-derived 33% (1/3),
  dep 201, ciclu 400, duplicat 409, self 400, cascade la delete task. **URMEAZA:** Faza 2 view (tab
  Gantt in ProjectDetail: tabel taskuri + bare start→end + bara progres + milestones), Faza 3 sageti
  dependente, Faza 4 export PDF profesional (antet proiect/client/perioada + legenda) + export Excel.

- **2026-07-03 — FIX export PDF Planificator: pagina alba + portrait** (SW v81, raportat de Ion cu PDF-ul
  real): exportul iesea **pagina alba (doar titlul) si portrait**. Doua cauze: (1) A4 portrait ≈ 794px
  latime CSS < breakpoint-ul `@media (max-width:820px)` care ascunde `.chart` (vederea mobila) — iar
  `.mlist` era si ea ascunsa in print → nimic de aratat. Fix: in print CSS `.chart{display:block!important;
  overflow:visible}` + `.mlist` ramane hidden, ca swimlane-ul sa se afiseze indiferent de latime. (2)
  `@page{size:A4 landscape}` era in `<style>`-ul SCOPED al componentei si NU se aplica → mutat in
  `global.css` (nescopat). Verificat cu `page.pdf({preferCSSPageSize:true})`: 841×595 = A4 landscape +
  swimlane-ul complet randat (testat pe 3L/90z ca in exportul lui Ion). Lectie: testul initial trecuse
  doar fiindca `page.pdf({landscape:true})` forta >820px; testeaza print-ul la latimea REALA a paginii.

- **2026-07-03 — Planificator: export PDF (print) + rail „Backlog" (taskuri fara termen) + drag-to-schedule**
  (SW v80, alegeri Ion): **(A) Export PDF = print-to-PDF client** (NU reportlab): buton „Export PDF" →
  modal (Modal.svelte) cu alegere scope (checkbox per proiect + „Toate") + optiune „cate un proiect pe
  pagina". `runExport()` forteaza `data-theme=light` (print pe hartie, indiferent de tema app) + clasa
  `body.plan-printing` + optional `body.plan-pagebreak`, apoi `window.print()`; `afterprint` restaureaza
  tema. Print CSS: `@page A4 landscape`, ascunde chrome (header/dock in global.css gated pe
  `body.plan-printing`; controls/hint/mlist/backlog in Plan.svelte), `.inner{min-width:0;width:100%}` ca
  swimlane-ul (tot pct-based) sa se incadreze pe pagina, `.lane.print-hide` pt proiecte deselectate,
  break-after:page per lane cand pagebreak. Titlu print `.print-title` (interval). Verificat cu
  `page.pdf()`: chrome ascuns, tema light, incadrat pe A4, culori pastrate. **(B) Backlog** — endpoint
  `/api/plan` intoarce acum si `backlog[]` = taskuri open FARA plan SI fara scadenta (proiect+global,
  helper `_backlog_item`, LIMIT 300). Rail colapsabil „Fara termen" sub chart cu chip-uri draggable
  (HTML5 DnD). **Drag pe timeline** (`.p-body` = drop zone, `dayFromEvent` calc ziua din X relativ la
  `--lane-w`) → `scheduleBacklog(tip,id,data)` seteaza DOAR `data_planificata` (nu inventam termen).
  Indicator live `.drop-line`+`.drop-tag` la dragover. Fallback fara drag: fiecare chip are un DatePicker
  („Planifica"). Verificat E2E: 3 chip-uri backlog, drag → backlog 3→2 + task planificat, modal export 4
  randuri, 0 erori. **RAMAS (Ion: „mai avem mai multe de gandit"):** asteapta restul ideilor lui.

- **2026-07-03 — Planificator: orizonturi lungi (pana la 6 luni) + coloane adaptive + toggle weekend**
  (SW v79): orizonturi noi **7/14/30/90/180** zile (label-uri 7z/14z/30z/3L/6L). **Coloane adaptive**
  (`buildColumns` in `lib/planDates.js`): <=31z = pe ZI (cu weekend), <=92z = pe SAPTAMANA (ISO, label
  „S27 · 29 iun"), altfel pe LUNA („Iul 2026"). Barele raman pozitionate prin `spanRect` pe fractiune de
  zi — granularitatea e doar chestiune de header/gridlines. Coloanele au geometrie in % (partiale la
  margini). `days` clamp in backend ridicat 60→370. **Toggle „Weekend"** (`plan.showWeekends`, persistat
  localStorage `pif-plan-weekends`) — evidentiaza/ascunde benzile de weekend; dezactivat automat in
  modul saptamana/luna (weekendul n-are sens acolo). Verificat E2E: 3L→14 coloane saptamanale, 6L→6
  coloane lunare, weekend on/off 4↔0 benzi, disabled in modul saptamanal, 0 erori. **RAMAS de discutat
  cu Ion (intrebat):** (a) export PDF — abordare (print-to-PDF client vs fisier server reportlab) +
  „toate vs per proiect"; (b) taskurile FARA termen (azi nu apar pe timeline) — rail „backlog" cu drag
  pe timeline vs coloana „fara termen" vs ignorate. „Mai avem mai multe de gandit" (Ion).

- **2026-07-03 — Planificator Faza 2 + fix Dock reveal-edge** (SW v78, acelasi deploy): (1) **drag &
  drop** pe swimlane — tragi corpul barei = muti tot spanul (pointer events, snap la zi, preview live
  cu datele noi intr-un `.drag-label`); **resize** de la marginile barei (`.rz-l`/`.rz-r`) = muti doar
  o muchie (start=data_planificata / termen=data_scadenta). Commit prin `setTaskDates(tip,id,body)` din
  store (setter EXPLICIT — NU cupleaza plan+scadenta ca `moveTaskDate`; span-drag pastreaza spanul).
  Click (fara miscare) pe bara = deschide popover-ul. Taskurile `done` sunt read-only pe timeline.
  (2) **Packing** — bare care nu se suprapun in timp impart acelasi rand (`packRows`, greedy pe start),
  in loc de un rand per task. (3) **Orizont segmentat 7/14/30** (`setHorizon`, `plan.days` din store;
  coloanele se rescaleaza, `compact` >18 zile ascunde ziua saptamanii). (4) **Toggle „Finalizate"** —
  `?done=1` la `/api/plan` include taskurile done (span din plan/scadenta SAU `data_finalizare` in
  fereastra); `_agenda_item` acum poarta si `data_finalizare`. Bare done = estompate + taiate. Verificat
  E2E: packing (8 bare→4 randuri), orizont 7/14/30, drag (+2 zile pe plan), resize-R (+2 zile pe termen),
  done backend, 0 erori consola. **Fix Dock (cerut de Ion):** `REVEAL_EDGE` in `Dock.svelte` 6px→48px
  (+ `HIDE_ZONE` 110→150) — la 6px trebuia sa ajungi in taskbar-ul Windows si dadeai peste el din
  inertie; la 48px dock-ul apare inainte de marginea sistemului.

- **2026-07-03 — Feature nou „Planificator" (swimlane operational 14 zile)** (SW v78, ales de Ion
  dintre 3 schite de Gantt): ruta noua `/plan` in Dock (iconita solid `plan` = calendar cu bare),
  orizont **14 zile fix** de la azi. **Lane colorat per proiect** = intervalul intreg al proiectului
  (`data_incepere→deadline`, clamped la fereastra, cu diamant la deadline) care CONTINE taskurile lui
  ca sub-bare (`data_planificata→data_scadenta`); task fara plan = marker single-day pe ziua termenului.
  Lane „Globale" la final. **Zero schema noua** — reutilizeaza semantica de planificare din agenda
  (bara = planificat→scadent). Backend: endpoint nou `GET /api/plan?start=&days=14&today=` (blueprints/
  tasks.py, langa `/api/agenda/*`) — refoloseste `_agenda_item` + noul `_span_intersects`; exclude
  proiecte anulat/finalizat, taskuri done, recurente viitoare (acelasi idiom ca agenda). Frontend:
  `pages/Plan.svelte` (swimlane CSS-grid/flex + overlay gridlines/weekend/azi, popover de actiuni pe
  click bara: Deschide/Muta pe.. via DatePicker/+1 zi/Bifeaza), `stores/plan.svelte.js` (reuse
  updateTask/updateGlobalTask; reprogramarea muta si deadline-ul daca exista, ca in agenda),
  `lib/planDates.js` (buildDays/spanRect/dayDiff, LOCAL date, nu UTC). Culori lane = hash pe id →
  paleta de 7 hue-uri distincte de amber (accentul ramane rezervat starii active/chrome). **Sub 820px**
  = fallback lista grupata pe proiect (grila de 14 coloane nu incape pe telefon). Reprogramarea prin
  drag&drop + packing pe lane + orizont segmentat 7/14/30 = **Faza 2** (neimplementate). Verificat:
  backend cu test izolat (proiect+taskuri, excludere out-of-window/anulat/recurenta), Playwright E2E
  desktop (4 lane / 8 bare / 14 coloane / popover) + mobil (grupuri+randuri, chart ascuns), 0 erori consola.

- **2026-07-03 — Dock FIX pe mobil (fără autohide)** (SW v77, cerut de Ion): pe touch (`pointer:coarse`
  sau ≤768px) dock-ul e mereu vizibil, fără autohide — se ascunde DOAR cât timp e deschisă tastatura
  (focus pe câmp editabil), ca să nu plutească peste ea. Pe DESKTOP rămâne autohide v4 (cursor push la
  marginea de jos). Implementare în `Dock.svelte`: `isMobile` (matchMedia + resize), `apply()` = pe
  mobil `hidden=kbLocked`, pe desktop `!inZone`. `onMove` (cursor) și `revealFromPeek` no-op pe mobil.
  Manerul „peek" (`.dock-grip`) ascuns pe `pointer:coarse` (afordanță moartă când e fix). Verificat
  Playwright 390px: vizibil la load, se ascunde la focus input, reapare la blur.

- **2026-07-03 — Verificare mobil + fixuri** (SW v76): trecere Playwright la 390px pe toate paginile
  (Home/Tasks/Projects/ProjectDetail/Params/Calculator/Notes/Admin) — **0 overflow orizontal, 0 erori**,
  iconografia nouă (glife→Lucide) OK, dock jos corect. Fixat: (1) **salutul din header se suprapunea
  peste brand pe mobil** (`.header-context` centrat absolut nu încape la 390px) → ascuns pe ≤768px
  (`display:none`, nu doar `.hc-sub`). (2) Diacritice lipsă în `Notes.svelte`: Notițe, Configurează,
  către, în, „Caută în conținut", „Nicio notiță", „Selectează o notiță din listă".

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
- 2026-07-16 (quater): **Frontmatter write-back automat (dashboard → wiki).** `sync_project_frontmatter(vault_folder, fields)` în obsidian.py: la `PUT /api/proiecte/<id>` cu `status`/`deadline` (proiect cu vault_folder), un daemon thread împrospătează mirror-ul, editează liniile `status:`/`deadline:` din frontmatter-ul README-ului de proiect, commit `dashboard: sync frontmatter <slug>` + push. Best-effort (eșecul nu strică PUT-ul; `pif-sync.py status` din Knowledge prinde discrepanțele rămase). NU inventează frontmatter dacă README-ul nu are (return silențios). Harta completă a canalelor de sync: `Knowledge/wiki/job/meta/sync-architecture.md`.
- 2026-07-16 (ter): **Editare note wiki din dashboard cu write-back în git (sursă unică).** `PUT /api/obsidian/note {path, content}` (obsidian.py): refresh mirror → scrie fișierul → commit (autor "PIF Dashboard" cu emailul noreply al lui Ion) → `push origin HEAD:main`; la push eșuat face `reset --hard origin/main` (nu lasă mirror-ul divergent) și întoarce 502. Edit-only (nota trebuie să existe), path-traversal-safe, pe vault non-git (dev local) doar scrie fișierul. **Necesită deploy key cu WRITE** (cel inițial era read-only — re-adăugat pe GitHub cu Allow write access). UI: tab Wiki din ProjectDetail are buton "Editează" sub notă (pattern in-flow, memorie 2026-06-13) → textarea markdown raw + "Salvează + push". Fluxul sursă-unică: documentația de proiect trăiește DOAR în wiki (tab-ul Wiki o randează live); `observatii` rămâne pentru rezumatul narativ de PV/export. SW v95→v96.
- 2026-07-16 (bis): **Vault-ul Knowledge clonat pe server prin deploy key SSH + auto-refresh.** SSH direct la server nu merge din afara LAN-ului de acasă (doar Cloudflare Tunnel), deci sync-ul vault-ului se face PRIN APP: `POST /api/obsidian/vault-key` generează ed25519 (`~/.ssh/vault_deploy_key`, privata nu părăsește serverul) → cheia publică se înregistrează manual ca deploy key read-only pe GitHub/Knowledge → `POST /api/obsidian/vault-sync` face clone shallow (`git@github.com:Urs1470/knowledge.git` — numele repo-ului e lowercase din 2026-07-16; vault-sync face self-heal pe `remote set-url` la clonele vechi) în `~/Projects/Knowledge` și setează `obsidian_vault_path` dacă e invalid. Prospețime: `_maybe_refresh_vault` (obsidian.py) = fetch+reset în daemon thread la accesarea notelor, max 1/10min — NU e cron. Clone pe https a eșuat (repo privat, serverul n-are credențiale GitHub — pif-dashboard e public/pull fără auth). `folders` = `notes, inbox, wiki` (structura nouă a vault-ului; cea veche 10_Library/30_Eng/99_Attachments e moartă din 2026-07-15).
- 2026-07-16: **Wiki tab pe ProjectDetail + proiecte.vault_folder formalizat.** Coloana `vault_folder` (folder vault-relativ, ex. `wiki/job/projects/imsat-biochem-podari`) exista DOAR pe DB-ul de producție (ALTER TABLE manual, dintr-o sesiune Cowork veche — de-asta API-ul o returna prin `SELECT *` deși codul n-o știa). Acum e oficială: migrare v26→v27 (idempotentă — pe prod devine no-op) + self-heal, în INSERT/UPDATE din projects.py și în ProjectFormModal ("Folder wiki (vault)"). Endpoint nou `GET /api/proiecte/<id>/wiki` (în obsidian.py, reuse `_obsidian_vault` + walk; NU aplică filtrul de foldere top-level — ăla e doar pentru browserul de notițe de studiu; are `_obsidian_safe_dir` anti-traversal). Frontend: tab "Wiki" în ProjectDetail (chips cu notele din folder, README primul, MarkdownView + wikilinks rezolvate în folderul proiectului). SW VERSION v94→v95. GOTCHA: vault-ul configurat pe server (`obsidian_vault_path`) arăta spre vechiul Engineering_Vault (Insync) care NU mai există după reorganizarea vault-ului din 2026-07-15 (`valid:false`) — trebuie clonat repo-ul Knowledge pe server + actualizat path-ul din Administrativ. Sincronizarea wiki↔dashboard de pe partea Knowledge: `tools/pif-sync.py` în repo-ul Knowledge + frontmatter `dashboard_id` în README-urile proiectelor.
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
