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
- `SCHEMA_REFERENCE.md` — full SQL schema. Design system: sectiunea „Design system" de mai jos + `frontend/src/styles/tokens.css` (sursa unica).

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
database.py               # Schema (9 tables), migrations v1-v39, WAL config
utils.py                  # login_required decorator, UUID, app_settings KV
csrf.py                   # Double-submit CSRF (cookie + X-CSRF-Token header)
labels.py                 # Centralized status labels (project + task states)

blueprints/
  projects.py             # /api/proiecte/* — CRUD, filters, Excel/PDF export, snapshot
  tasks.py                # /api/proiecte/<id>/tasks/* — CRUD, subtasks, recurring
  obsidian.py             # /api/obsidian/* — read-only vault integration
  admin.py                # /api/stats/*, /api/export/*, /api/search/* — analytics, backup
  push.py                 # /api/push/* — Web Push: o notificare pe zi PER task personal fara termen (>2 zile), cu actiuni „Facut"/„Azi"

templates/
  login.html              # PIN login (only remaining server-rendered template)

static/
  dist/                   # Svelte SPA build (Vite) — the app, served at /
  service-worker.js       # PWA cache + Web Push (push/notificationclick); bump VERSION la orice modificare
  login.css               # login page styling
```

## Database

SQLite file: `pif_dashboard.db` (gitignored). 9 tables, 39 migrations (idempotent).

**Core tables:** proiecte, tasks, task_subtasks (FK CASCADE), task_dependencies, global_tasks, implementari, clienti

**Specialized:** app_settings (KV store), schema_version

**Migrations:** `database.py` — `run_migrations()` chains v1 through v39. Each is idempotent. Auto-runs on first request via `before_request`. (v20 dropped Budget Tracker; v22 dropped timer & jurnal — orele se ponteaza in e100, jurnalul se scrie in observatii; v23 dropped Checklist PIF + Project Templates + Hermes AI — cod mort, zero UI; **v28 dropped parametri_master, fault_codes, echipamente, atasamente** — restrangere de scop la organizare/monitorizare de proiecte, vezi mai jos.)

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

### Doua perioade, zero deadline-uri (v30, 2026-07-27)

Ion: *„eu practic niciodata nu ma iau dupa deadline. Noi nu intram in deadline-uri din
partea clientului niciodata. Practic exista perioada de pregatire proiect si perioada de
implementare in site, care pot sa le stiu."*

Datele confirmau deja: **2 proiecte din 18** aveau deadline, iar unul era scris
`23.02.2026`, invizibil in Calendar luni intregi. `notify_on_deadline` era `1` pe toate
cele 18 — un comutator care nu comuta nimic. Coloanele au plecat (arhiva:
`raw/pif-dashboard/2026-07-27-inainte-de-v30/`).

In loc, `implementari.faza` cu valorile **`pregatire`** si **`implementare`**.

**`faza` e INDEPENDENTA de `locatie`.** PIF-ul poate fi si la sediu, si in site, uneori in
doua etape — deci „unde esti" si „in ce faza esti" sunt doua fapte separate, nu unul cu
doua nume. In Calendar sunt doua axe vizuale care se combina: **textura** = locatie
(hasurat la sediu), **intensitate** = faza (palid la pregatire, plin la implementare).

Ce a luat locul deadline-ului in interfata: **`urmatoarea`** — prima perioada neincheiata,
calculata prin subinterogare in `/api/proiecte` si `/api/proiecte/<id>`. Apare pe cardul de
proiect si in bara laterala a paginii de proiect. Banda proiectului din Planificator merge
acum de la `data_incepere` pana la ultima zi planificata, nu pana la un termen impus.

### Doua statusuri de proiect (v31, 2026-07-27)

Ion: *„practic imi trebuiesc doua statusuri la proiecte: in pregatire si finalizat."*

Datele sustineau restrangerea: din 18 proiecte, 8 erau `finalizat`, 7 `pregatire`, 3
`in_lucru`. **`in_asteptare`, `blocat` si `anulat` erau definite in cod si nefolosite de
niciun rand** — optiuni pe care nu le-a ales nimeni niciodata. Migrarea v31 muta orice nu e
`finalizat` la `pregatire`.

Nu se pierde informatie: distinctia „in lucru" vs „in pregatire" n-a fost folosita la nicio
decizie, iar cand esti efectiv pe teren o spun PERIOADELE, nu statusul.

Atentie la o suprapunere de nume: statusul de proiect **„In pregatire"** si faza de perioada
**„pregatire"** suna la fel dar sunt lucruri diferite (proiectul intreg vs blocul asta de
zile). De aceea in panoul zilei din Calendar statusul NU se mai afiseaza — pe o zi
planificata e evident ca proiectul nu e finalizat, iar chipul s-ar citi ca fiind despre
perioada. Locatia si faza stau lipite (amandoua despre perioada); statusul e despre proiect.

### Cod scos pentru ca nu putea fi folosit (v32, 2026-07-27)

- **`tasks.faza`** — nu era o coloana goala, era o FUNCTIE PE JUMATATE: gruparea taskurilor
  pe faze (WBS) in Gantt-ul de proiect si in exportul PDF/Excel, cu antet si bara de rezumat
  per grup. Codul era viu si corect, dar **niciun formular nu putea seta campul**, deci
  ramura nu s-a executat niciodata. Toate cele 37 de randuri erau goale.
  **Capcana:** un self-heal re-rula v24->v25 cand lipsea coloana; a fost scos in acelasi
  commit, altfel migrarea ar fi fost anulata la prima pornire.
  Daca gruparea pe faze devine utila, se reconstruieste cu un camp real in formularul de task.
- **`GET /api/dashboard/home`** (172 de linii) — singurul consumator era pagina Acasa, care
  nu mai are contoare. Calcula proiecte active, taskuri urgente, finalizate/7 zile + sparkline
  si lista de risc; toate ori au fost respinse de Ion, ori traiesc in Calendar.

### Un task are O SINGURA data (v33, 2026-07-27)

Ion: *„mi-am luat un task fara deadline in ziua de astazi (…) dupa am vazut ca nu se poate
si (…) deja stiu cand l-as putea face. Deci mutarea este practic un deadline. Si trebuie
sa fie adaugat ca deadline pur, sa nu mai dublam atat notiunile."*

Datele confirmau ca distinctia era fictiva. Din 37 de taskuri de proiect: **6 aveau ambele
date si EGALE, 3 le aveau diferite — toate cu exact o zi** (semnatura butonului „mâine" de
pe vechea regula), iar 16 aveau doar una din doua. La cele globale, 1 rand din 15.

`data_planificata` a plecat. Ramane `data_scadenta` — termenul.

- **Boardul „Astazi"** = ce e scadent azi SAU restant. Regula avea trei ramuri si o
  exceptie (fiindca planul si termenul se puteau contrazice); acum are o linie.
- **A pune un task pe azi** = a-i da termenul de azi. **A-l muta** = a-i muta termenul.
  **A-l scoate de pe board** = a-i sterge data; se intoarce in sertarul „fara termen".
- **In Planificator** fiecare task e un semn de o ZI, nu un interval. Mânerele de
  redimensionare au plecat: nu mai exista span de intins.
- Backfill: unde exista doar `data_planificata`, ea a DEVENIT termenul (12 randuri).
  Unde existau amandoua si difereau (4 randuri), am pastrat `data_scadenta` — a lua data
  de plan ar fi amanat in tacere un termen deja depasit.
- **Capcana:** self-heal-ul care re-rula v20->v21 cand lipsea `data_planificata` a fost
  restrans la `ordine_agenda`. Fara asta, coloana revenea la prima pornire.

### Taskul e facut sau nu (v34, 2026-07-27)

Ion: *„in general as scapa si as sterge statusul taskurilor si prioritatea."*
Ales explicit: doar facut / nefacut.

**Statusul era deja mort.** In baza reala existau DOAR `to_do` si `done`, in ambele tabele.
`in_lucru`, `in_asteptare` si `blocat` erau in selector si in `labels.py` — pe zero randuri.

**Prioritatea era completata, dar saturata.** 20 din 37 de taskuri de proiect si 12 din 15
globale erau „urgent" — 54% si 80%. Cand majoritatea e urgenta, cuvantul nu mai selecteaza
nimic. (Aparea si `Normal` cu majuscula langa `normal`, semn ca era bifata mecanic.) De
aceea a plecat, desi — spre deosebire de celelalte curatenii — chiar era folosita.
Arhiva: `raw/pif-dashboard/2026-07-27-inainte-de-v34/`.

Severitatea unui task se citeste acum din **termen**, nu din prioritate: `dueRing()` in
`formatters.js` da rosu pentru depasit si amber pentru azi. Se vede pe **inelul bifei** si
pe **textul termenului** — nu pe bordura randului (vezi tura 9 mai jos). Sortarea din
exportul .md merge tot pe termen.

### Un proiect inchis se opreste in ziua inchiderii (v35, 2026-07-30)

Ion: *„eu am finalizat un proiect de ieri dar a mai aparut si pe azi proiectul cu motoare
extruder."*

Prima incercare taia perioadele unui proiect `finalizat` la **ziua de azi**. Reperul e insa
ziua in care ai INCHIS, nu ziua in care te uiti: proiectul avea perioada 29->30, inchisa pe
29, iar 30 rămânea afisat. Diferenta se vede doar cand inchizi inainte de vreme — exact
cazul care conteaza.

`proiecte.data_finalizare` (v35) e acel reper. Backfill din `updated_at` pentru cele deja
inchise — cea mai buna dovada disponibila si s-a potrivit (proiectul cu motoare avea
`updated_at = 2026-07-29T16:19`).

**Invariantul:** data exista daca si numai daca statusul e `finalizat`. Se pune automat la
inchidere (azi), se STERGE la redeschidere. Fara invariant, formularul tine data agatata
cand redeschizi — `DatePicker`-ul se ascunde, dar valoarea rămâne in `form` — si la o
re-inchidere ai reveni in tacere la ziua veche.

Se poate corecta: cand inchizi acum o lucrare terminata saptamana trecuta, campul
**„Finalizat pe"** apare in formularul de proiect (doar la status `finalizat`). In bara
laterala a paginii de proiect, celula „Urmatoarea perioada" — care pentru un proiect inchis
n-avea decat „Neplanificat" de spus — arata **„Finalizat · <data> · ieri"**. Un camp care
decide ce vezi in Calendar nu are voie sa fie invizibil.

Taierea e doar la CITIRE (`/api/calendar`, `/api/export/ics`); baza rămâne neatinsa, iar
Ganttul propriu al proiectului arata toate perioadele.

### „S-a facut" e despre PERIOADA, nu despre proiect (v39, 2026-08-07)

Ion: *„daca dau ca s-a facut in calendar la o implementare nu trebuie sa se marcheze
ca finalizat proiectul, trebuie sa ramana tot in perioada de pregatire. Dupa
implementare pot sa mai am de facut pv-uri sau altceva, sau poate va mai trebui de
facut vizita pe care nu stiu cand va fi."*

Panoul zilei intreba despre perioada („A trecut. S-a făcut?") si raspundea pe proiect:
butonul „Da" chema `PUT /api/proiecte/<id>` cu `status = 'finalizat'`. Doua obiecte
diferite pe acelasi buton.

Greseala se si auto-ascundea: un proiect inchis iese din „Proiecte fara perioada" (vezi
`neplanificate` in `/api/calendar`), deci exact vizita urmatoare — cea pe care n-o poti
inca data — nu mai avea de unde sa fie planificata. Deplasarea inchidea lucrarea.

`implementari.confirmata` (v39) tine raspunsul acolo unde s-a pus intrebarea.
`necesita_decizie` = a trecut **SI** `confirmata = 0` **SI** proiectul nu e inchis;
aceeasi conditie in `de_decis` (deciziile ramase in urma ferestrei) si in KPI-ul „de
clarificat". Statusul proiectului se schimba **doar** din formularul lui, langa
„Finalizat pe" — un singur loc, cu numele scris pe el.

Bifa se vede in panoul zilei ca eticheta verde „Făcut" (langa loc si faza — toate trei
sunt despre perioada) si in lista de perioade a proiectului. Anularea sta jos, intre
actiuni, si se numeste **„Nu s-a făcut"**: e raspunsul opus la aceeasi intrebare si nu
se poate confunda cu „Scoate", care scoate perioada din calendar.

Mutarea unei perioade **nu** reseteaza bifa: „am fost pe 5, nu pe 4" e o corectare de
consemnare, nu o replanificare.

### Patru locuri pe care gramatica mișcării nu le prinsese (tura 13, 2026-08-07)

Stratul de mișcare e bun — tura 8 i-a pus o curbă, un ceas și o adâncime. Tura 13
nu-l reinventează: caută unde **nu fusese aplicat**. Trei lipsuri sunt deschideri,
al patrulea e o inconsecvență în interiorul aceluiași rând.

- **Deschiderea paginii.** `.cell-in` trăia deja pe Acasă, /tasks, /projects și
  Calculator; Calendarul și Planificatorul apăreau între două cadre — și tocmai
  ele sunt cele pe care le deschizi de mai multe ori pe zi. Acum învelișul rutei
  urcă 10px (`.ruta-in`, nou în `global.css`), apoi celulele intră cu **același**
  pas de 32ms. **10px, nu 22 ca la celule:** aceeași distanță pe un obiect de zece
  ori mai mare nu se citește ca sosire, ci ca zguduire.
  - **`.ruta-in` închide pe `transform: none`, nu pe `translateY(0)`.** Un transform
    rămas — chiar și identitatea — face din înveliș blocul de referință al oricărui
    `position: fixed` dinăuntru (popoverul și eticheta de tragere din Planificator
    sunt fixed) și le-ar deplasa pe toate cu cât e derulată pagina.
  - **`@media print { .cell-in, .ruta-in { opacity: 1 !important } }`** — amândouă
    pornesc de la `opacity: 0`, iar la print animațiile nu se joacă. Fără regulă,
    exportul PDF al Planificatorului (care tipărește exact `.page` cu `.chart`
    înăuntru) ar fi ieșit **alb**. Aceeași grijă în blocul de print din `Plan.svelte`
    pentru `.band` / `.impl-band`.
  - Indicii de celulă merg **prin** `.backlog`: pe telefon sertarul stă DEASUPRA
    listei, deci `.chart`=0, `.backlog`=1, `.mlist`=2 — altfel capul ar sosi după
    coadă, exact bug-ul reparat în tura 8.

- **Schimbarea lunii** era singura navigare fără sens: apăsai „înainte" și grila se
  ÎNLOCUIA. După două apăsări rapide nu mai știai dacă ai mers două luni înainte
  sau una-nainte-una-napoi. `alunecare()` în `motion.svelte.js` — ±10px pe X în
  `--dur-fast`, în sensul apăsării. **Singura mișcare din tură care adaugă
  informație**, nu doar politețe.
  - **`{#key anchor}` pe grilă, nu o clasă comutată:** o clasă care rămâne aceeași
    nu re-pornește o animație CSS, deci două apăsări „înainte" la rând ar fi dat o
    singură alunecare — fix cazul de rezolvat. Bloc nou = tranziție nouă.
  - **`load()` nu mai stinge grila la navigare** (`loading = data === null`).
    `grila` se recalculează SINCRON din `anchor`, deci zilele erau deja gata și doar
    benzile întârziau; scheletul le înlocuia pe amândouă cu o formă care nu seamănă
    cu niciun calendar — și distrugea elementul pe care aleargă alunecarea înainte
    s-o vadă cineva. Scheletul rămâne doar la **prima** încărcare.
  - Orice salt la o zi anume („de clarificat", „Urmează") trece prin `ancoreazaPe()`,
    care calculează sensul **înainte** de a rescrie `anchor`. Fără el, un salt ar fi
    alunecat în direcția ultimei apăsări de lună. (Prins în aceeași trecere:
    „Urmează" ancora cu `monthStart` și în modul 2 săptămâni, unde `anchor` trebuie
    să fie un început de săptămână.)

- **Panoul zilei.** Lucrările se estompau una câte una, dar `.pan-zi` — data zilei,
  adică exact partea care se schimbă cel mai vizibil — sărea. Acum se mișcă panoul
  ÎNTREG, o dată (`{#key selectata}` + `sosire`), iar stingerea de pe rânduri a
  plecat: două sosiri peste aceiași pixeli nu se adună, se încurcă.
  - **`|local`**: la prima încărcare panoul sosește oricum, prin `.cell-in` de pe
    `.side`. `{#key}` pe ZIUA selectată, nu pe conținut — două zile pot avea
    aceleași lucrări și tot trebuie să se vadă că ai schimbat ziua.

- **Benzile din planificator.** Ce are început crește din el; ce doar acoperă un
  interval, apare.
  - **`.impl-band`** are o zi de start reală → se **descoperă** de la stânga
    (`clip-path`), adică dinspre ziua în care începe. **Nu `scaleX`:** ar turti
    eticheta la jumătate de lățime pe la mijlocul mișcării, iar un text care se
    lățește înapoi la normal se citește ca elastic, nu ca o perioadă care începe.
  - **`backwards`, nu `forwards`:** `clip-path` trebuie să se întoarcă la `none`.
    Înghețat pe `inset(0 0 0 0)` ar tăia la border-box, adică ar șterge **definitiv**
    umbra exterioară a blocului.
  - **`.impl-band.clipL`** (tăiată de fereastră la stânga) cade înapoi pe stingere:
    ziua ei de start nu e pe ecran, deci o descoperire din stânga ar inventa un
    început fix acolo unde muchia dreaptă spune „continuă din afară".
  - **`.band` (pregătirea) NU crește** — `segmentePregatire` pornește de la marginea
    ferestrei fiindcă „de când se pregătește" nu se știe, iar capătul stâng e
    estompat tocmai ca să spună asta. O creștere din stânga ar afirma o zi de start
    pe care desenul o neagă la un centimetru mai jos.
  - **Reduced-motion anulează animația, nu doar durata**, și regula stă la **finalul**
    foii: plasa globală scurtează `animation-duration`, dar nu atinge
    `animation-delay` — cu `backwards`, rândul șase ar sta 240ms invizibil și apoi
    ar pocni. Iar un `@media` nu adaugă specificitate, deci scrisă mai sus ar fi
    fost anulată de `.band` / `.impl-band` / `.bar`.
  - **Variabila de decalaj se numește `--rand`**, nu `--celula` (acela e pasul de
    32ms al celulelor de pagină și s-ar moșteni peste orice `.cell-in` de dedesubt)
    și nu `--i` (acela înseamnă deja „rândul benzii" în Calendar).

**Premisa 13e era depășită, și asta a lărgit lucrarea.** Documentul spunea „taskul
crește din ziua lui, iar cele două benzi pe care stă apar instantaneu" și cerea doar
ca benzile să i se potrivească. Taskul **nu** mai creștea: `barIn` scala o LĂȚIME și
a plecat odată cu cutia, în tura în care taskul a devenit un reper de o zi (v33).
Dacă mișcam doar benzile, inconsecvența nu dispărea — se întorcea pe dos, un rând
plin de mișcare cu reperele înghețate deasupra. Deci reperul a primit `reperIn`:
un punct n-are lățime de întins, așa că **crește pe loc**, din ziua lui
(`transform-origin: left`; `right` pe `.bar.flip`, care își scrie eticheta invers).
Pe mobil același `reperIn` merge pe `.mt-pin`, dar **pe buton, nu pe `::before`** —
rombul își ține forma dintr-un `rotate(45deg)`, iar `to { transform: none }` i-ar
șterge rotația și l-ar lăsa pătrat.

### Modalul se deschide cu datele în mână (2026-08-07)

Ion, în aceeași linie cu tura 13: *„repară animația la modalul de selecție taskuri
pentru ziua de astăzi de pe pagina acasa."*

Măsurat cadru cu cadru, caseta se deschidea la **228px** și **sărea la 374 după
16ms**, cât era încă la opacitate 0,19 — plus 73px pe verticală, fiindcă e
centrată. Scalarea de intrare (0,96 → 1) mișcă vreo 15px; saltul era de **zece
ori** mai mare și se juca peste ea. Ce vedeai nu era un modal care sosește, ci
unul care se corectează.

Cauza: `open` randa imediat, cu `items` gol, deci caseta se dimensiona după o
singură linie de text („Niciun task disponibil de adăugat"), iar lista venea după.
Aceeași regulă ca la `desfacere` din `motion.svelte.js`, unde e scrisă deja: **un
panou se deschide numai cu conținutul măsurabil**, altfel tranziția animează spre
o țintă care se schimbă sub ea.

- **`deschis` e ce vede `<Modal>`; `open` rămâne intenția părintelui.** Închiderea
  pornită de utilizator se întoarce prin `onclose` — singurul drum pe care Modal
  îl semnalează în afară.
- **Plafon de 250ms**, ca butonul să nu pară stricat dacă API-ul întârzie: peste
  atât se deschide oricum, cu **schelet** în locul listei. Scheletul ține locul, deci
  umplerea de după e o înlocuire, nu un salt. Sub plafon nu se vede niciodată.
- **Scheletul e gardat pe `loading && items.length === 0`** (regula din sistemul de
  design): când tastezi o căutare peste o listă deja adusă, rândurile vechi RĂMÂN
  pe ecran — altfel caseta s-ar strânge și s-ar umfla înapoi la fiecare tastă.

**Și o a doua scăpare, în același loc:** caseta se mișca pe `cubicOut` (implicitul
lui `scale`), iar vălul care o ține pe `EASE`. Două curbe pe același obiect: în
prima treime vălul se întuneca vizibil înaintea casetei, și amândouă se opreau
odată — obiectul părea că vine *după* umbra lui. E exact scăparea pe care tura 8 a
reparat-o la `fade`/`sosire`/`plecare`; `scale` n-a fost pe listă atunci fiindcă
`fly` și `slide` — verificate — aveau deja `cubicOut`, și a fost pus în aceeași
găleată fără să fie deschis. Acum ambele ramuri din `intra()` folosesc `EASE`.
Verificat după: caseta pornește la 386px din primul cadru, iar curba ei de
opacitate e identică pe zecimale cu a vălului.

### Severitatea pleacă de pe muchie (tura 9, 2026-08-07)

Fiecare rând de task purta o dungă colorată de 3px pe muchia din stânga. Nu spunea
cât de urgent e: `dueColor()` ramifica în cinci, dar **`--accent` și `--warning` sunt
exact același hex** (`#ffb454`), iar ultimele două ramuri cădeau pe `--border-strong`
— culoarea bordurii pe care rândul o are oricum. Cinci ramuri, **două** lucruri
deosebibile: „azi" și „în două zile" erau literalmente același pixel.

Mai grav: aceeași muchie de 3px purta **cinci înțelesuri** în aplicație — severitatea
unui task, identitatea proiectului, locația, tipul unui toast, un citat. În pagina de
proiect un rând de task și unul de implementare stăteau unul sub altul cu aceeași
dungă: una spunea „urgent", cealaltă „proiectul X".

**Muchia colorată de 3px nu mai există nicăieri.** Nu s-a rezervat niciunui rol.
Verificat loc cu loc, în șase din șapte întrebuințări era a doua codificare a unui
lucru **deja spus** — de o iconiță colorată, de un fundal tentat, sau de banda plină
pe care o repeta în aceeași culoare. Ștergerea n-a scos informație, a scos duplicat.

- **Severitatea** = `dueRing()` (trei trepte) pe **inelul bifei** + pe **textul
  termenului**. Cercul e deja la marginea din stânga, deja rotund, și e chiar ținta
  pe care o apeși — culoarea devine invitație, nu etichetă. Ambele canale citesc
  **același `--ring`**, deci nu se pot desincroniza.
- **Neutrul e `--border`, NU `--border-strong`:** inelul în repaus trebuie să rămână
  exact bifa de dinainte, altfel fiecare rând neurgent s-ar schimba la vedere.
- **Hoverul ADAUGĂ un halou**, nu rescrie inelul — exact greșeala de la muchie, unde
  `:hover` ștergea `--sev` și trebuia reafirmat de mână în trei locuri.
- **Bifa era definită de cinci ori** (18/16/14/22px în trei fișiere, plus
  `.mcheck-gol` în Planificator). Acum o singură `.check-empty` în `global.css` —
  neschopat, fiindcă acolo trăiesc regulile puse din markup.
- **Identitatea** trece pe ce avea deja rândul: fill, iconiță, sau — în liste mixte —
  un punct de 6px. `.banda.inceput` din Calendar marchează începutul prin **rază**,
  nu prin culoare: banda e deja plină cu `var(--c)`.
- **Toastul e singurul care primea informație din dungă** (n-are nici iconiță, nici
  fill): o ia o iconiță Lucide în capul rândului.

**Geometrie:** bordura scade de la 3px la 1px, deci fiecare selector atins primește
înapoi în `padding` exact câți pixeli a pierdut. Fără asta, fiecare listă se
decalează față de antetul ei.

Textul suportă **o treaptă în plus** față de inel („mâine" rămâne scris, în gri):
un cuvânt poate ce un cerc de 2px nu poate.

`border-left: 3px` supraviețuiește **doar pe citate și callout-uri** în conținut de
notiță (`MarkdownView`, `RichTextEditor`, `.atentie` din Departament) — convenție
tipografică, nu cod de culoare.

### Mișcarea: o curbă, un ceas, o adâncime (tura 8, 2026-08-07)

Stratul de mișcare era deja construit. Problema era că fiecare bucată fusese reglată
singură — aplicația se mișca bine în bucăți și prost între ele.

- **Curba.** `--ease` era respectată peste tot în CSS, dar **nicio** tranziție Svelte
  n-o folosea — nu dintr-o decizie, ci fiindcă `motion.svelte.js` exporta doar
  duratele. `fade`, `sosire` și `plecare` rămâneau pe implicitul Svelte, care e
  **liniar**. (`fly` și `slide` au deja `cubicOut` — verificat, nu se ating.)
  **`svelte/easing` NU exportă un `cubicBezier` generic**, deci curba se rezolvă
  local (Newton-Raphson + înjumătățire), verificată față de o eșantionare
  parametrică independentă.
- **Bifarea.** Zborul dura 240ms, comiterea venea pe `setTimeout(160)`: rândul era
  **teleportat înapoi în ecran** la opacitate 1, ca apoi `plecare` să-l împingă din
  nou afară. Ultimul lucru pe care îl vedeai nu era plecarea, era revenirea. Acum
  comiterea așteaptă `transitionend`, cu cronometru de rezervă — sub
  `reduced-motion` durata e 0, iar o tranziție de durată zero nu emite eveniment.
- **Foaia.** `trasY = 0` la ridicarea degetului punea revenirea **cu arc** (care are
  voie să depășească) peste ieșirea care cobora foaia: prima jumătate a ieșirii se
  anula singură și se citea ca lag de atingere. Voalul se stingea în 120ms, când
  foaia mai avea ~170px de coborât. **Voalul ține obiectul, deci pleacă odată cu el
  sau după el — niciodată înainte.** Deblocarea derulării așteaptă acum sfârșitul
  ieșirii; altfel `window.scrollTo` mișca pagina din spate sub o foaie încă vizibilă.
- **Tabul.** `startViewTransition` pornea `import()` fără să-l aștepte, deci
  tranziția se termina pe schelet — iar scheletul are aceeași formă pentru Calendar,
  Planificator și Calculator. Routerul nu știe să încarce module (`lazyCache` e în
  App), deci App își **înregistrează** încărcătorul prin `setPreincarcaRuta`, iar
  `navigate` îl așteaptă cu o cursă de 180ms.
- **Staggerul.** Scara `nth-child` se oprea la 8: cardurile 9–12 aveau întârziere 0
  și **soseau primele** — ordinea văzută era inversul ordinii din listă. Indexul vine
  acum de la element. **Variabila se numește `--celula`, nu `--i`:** `--i` înseamnă
  deja „rândul benzii" în Calendar, iar proprietățile custom se moștenesc.
- **Apăsarea.** Durata era tokenizată, adâncimea nu — patru valori scrise de mână.
  `.ts-rand` se strângea cu 0,5% (sub pragul vizibil), `.status-pill` cu 8%. Acum
  `--press-scale` .97 și `--press-scale-sm` .93; nimic nu-și mai alege singur
  adâncimea.

### Un gest = un verb, în ambele sensuri (2026-08-07)

Glisarea spre stânga **descoperea un panou** de 3–4 acțiuni × 58px: 176px (Astăzi)
sau 232px (`/tasks`, proiect) din 390, deci taskul pe care acționai dispărea aproape
complet de sub deget. Iar „Șterge", ultimul din panou, cădea exact unde ajunge o
glisare rapidă. În plus cele două direcții aveau două modele mentale („deschide un
meniu" vs „execută"), deci se învățau separat.

`lib/glisare.js` primește `onAmana`: când e dată **și nu există `latime`**, stânga
execută un verb, simetric cu `onBifa`. Clase la rulare `gl-stanga` / `gl-amana`,
variabilă `--gl-s` (oglinda lui `--gl-p`), același prag de 42%.

**Verbul diferă după ce e pe ecran, deliberat:**

| suprafață | stânga | de ce |
|---|---|---|
| „Astăzi" | deschide **calendarul** (`.dp-gest`) | vezi mai jos |
| `/tasks` | deschide foaia cu **panoul de termen desfăcut** | termenele sunt împrăștiate pe săptămâni; „mâine" ar fi o zi aleasă de aplicație |
| pagina de proiect | deschide **modalul de editare** (are câmpul Termen) | acolo nu există foaie |
| rândul de **subtask** | execută **„Șterge"**, pistă `--danger` (`.gl-sub`) | pubela permanentă de 44px a plecat de pe rând |

Pe „Astăzi" gestul a executat o vreme **„Mâine"** — părea verbul potrivit, fiindcă
tot ce vezi acolo e scadent azi. Ion: *„trebuie data picker"*. Amânarea nu e „încă
o zi": muți un task când știi CÂND îl faci, iar ziua aia e rareori mâine. Deci
toate cele trei liste duc acum la aceeași întrebare — **ce zi?**

Calendarul de pe „Astăzi" e **unul pe board**, nu unul pe rând: pe telefon
`.arow-actions` nu se randează, deci nu există declanșator de apăsat. Instanța stă
într-un înveliș de 0×0 (`.dp-gest`), iar sheet-ul ei se mută oricum în `body`
(`use:portal`), deci învelișul strâns nu-l taie. `DatePicker` a primit
`export function deschideCalendarul()` — aceeași funcție ca la clic, ca luna
afișată să fie așezată la fel.

**Calendarul se deschide pe luna TERMENULUI**, nu pe luna curentă. Pe board
taskurile sunt scadente azi sau restante, deci grila e adesea o lună **trecută** —
iar o zi din trecut lasă taskul pe board, ca restant. E corect; contează doar când
scrii un test (vezi `audit_mobil`, care avansează până strict după luna curentă).

Pe subtask ștergerea din gest e acceptabilă **doar** fiindcă are `toastUndo` cu
commit întârziat — vezi paritatea reparată în `Tasks.svelte`.

`.gl-pista-s` trăiește în `global.css` (neschopat): `gl-amana` e pusă la rulare din
JS, iar Svelte **taie** regulile pe care le crede moarte în componente scopate.

Regresia e prinsă de `audit_mobil.py`, secțiunea **„gesturi"** — care a fost
rescrisă odată cu contractul: nu mai verifică un `transform` rămas după ridicare
(rândul se întoarce la zero, ca la bifare), ci că pista **crește pe parcurs** și
atinge pragul, apoi că verbul chiar s-a executat.

### Perioadele se trag cu mâna (2026-08-07)

Ion: *„in calendar vreau sa iau perioadele si sa le pot muta cu drag drop, acuma scrie
trage ca sa muti dar nu functioneaza. Trebuie sa pot si schimba si perioada cu tragere."*

Gestul era pe **HTML5 drag-and-drop**, si era rupt tacut. Trei motive pentru care a
plecat, nu doua:

1. **Pe touch nu se declanseaza NICIODATA `dragstart`.** Pe telefon perioadele nu se
   puteau muta deloc — iar sub 620px benzile erau in plus `pointer-events: none`, deci
   nici nu existau ca obiect.
2. **Nu poate exprima „trage capatul ca sa lungesti".** API-ul are un singur inteles:
   ridici un obiect intreg si il lasi in alta parte.
3. **Benzile stau PESTE celule**, deci trebuia jonglat cu `pointer-events` ca dropul sa
   stie pe ce zi a cazut.

Acum totul trece prin `lib/tragere.js` (pointer events): **mouse** — gestul incepe dupa
4px de miscare, ca un click sa ramana click; **deget** — dupa 300ms de apasare fara
miscare, ca o atingere scurta sa ramana atingere. Derularea se blocheaza DOAR dupa ce
gestul a inceput, printr-un `touchmove` non-passive — de aceea NU punem `touch-action:
none` pe banda si o glisare pornita din greseala pe ea deruleaza pagina normal.

Trei manere, trei intelesuri: **mijlocul** mută lucrarea, **capetele** îi schimbă
perioada, **captura zilei** mută toată deplasarea.

Patru lucruri care nu sunt evidente:

- **Ziua APUCATA e cea care ajunge sub cursor**, nu inceputul lucrarii. Prinzi o perioada
  de patru zile de a treia zi, o lasi pe joi: a treia zi cade pe joi. Varianta veche
  punea inceputul pe ziua de drop, deci o ajustare de o zi arunca lucrarea cu trei.
- **Fantoma e un al doilea set de benzi**, nu o mutare a celor reale. Motivul e mecanic:
  banda apucata e chiar elementul care primeste evenimentele. Re-randata la fiecare pixel
  (cheia ei contine ziua de inceput), Svelte i-ar distruge nodul, iar pe touch captura
  implicita a pointerului moare odata cu el — gestul s-ar rupe fix cand incepe.
- **`benzi` si `peZi` raman pe datele SALVATE** cat timp tragi. Daca s-ar recalcula, bara
  ar sari de pe un rand pe altul sub deget.
- **Pe telefon banda a ramas „decor peste celula"** — dar prin COMPORTAMENT, nu prin
  `pointer-events: none`: o atingere scurta pe banda cheama `atingeZi` cu ziua de sub
  deget, adica exact ce ar fi facut celula. De aceea e in `ACCEPTATE` din `audit_mobil`:
  regula de 44px exista ca sa nu obtii ALTCEVA cand ratezi, iar aici nu poti obtine
  altceva. Manerele de capat se ascund pe benzile de o zi (`.banda:not(.lat)`): doua
  manere de 9px intr-o celula de 44px n-ar mai lasa de unde s-o apuci.

Regresia e prinsa de `audit_mobil.py`, sectiunea **„perioadele se trag"** — cu intrare
adevarata, nu evenimente fabricate: `page.mouse` pentru mouse si
`Input.dispatchTouchEvent` prin CDP pentru deget. **`page.mouse` produce `pointerType:
'mouse'` chiar si intr-un context `has_touch`** (verificat), deci ar fi ocolit exact
ramura de apasare lunga.

### Trei campuri scoase din formularul de proiect (v36, 2026-07-30)

Ion, intrebat ce se poate sterge din modalul de editare: *„sterge cele 3 puncte."*

| coloana | completata | de ce a plecat |
|---|---|---|
| `nr_contract` | **1/18** | o valoare, pe un proiect |
| `pm` | **4/18** | toate cele patru aveau paranteze explicative („Paul Mandras (inlocuieste…") — folosit ca notita, nu ca date |
| `data_incepere` | **5/18** | **dubla prima perioada** |

`data_incepere` e cea interesanta: nu era doar rar completata, era o a doua sursa pentru un
fapt care exista deja. Inceputul real al proiectului e data primei perioade, iar codul cadea
deja pe fereastra vizibila cand campul era gol — deci pentru 13 proiecte din 18 nu facea nimic.

In loc, banda proiectului (Planificator si Ganttul de proiect) se calculeaza din perioade:
`prima_zi = MIN(implementari.data_start)`, `ultima_zi` = cea mai tarzie zi planificata. Cheia
din `/api/plan` s-a redenumit `data_incepere` -> **`prima_zi`**, ca sa nu rămână un consumator
care citeste in tacere altceva.

Arhiva: `raw/pif-dashboard/2026-07-30-inainte-de-v36/`.

**Capcana, a cincea la rand:** `COLOANE_DATA` din `database.py` (folosita de self-heal-ul de
normalizare) enumera `('proiecte', ('data_incepere',))` — fara scoaterea de acolo, coloana
revine la prima pornire si anuleaza migrarea. Acum `proiecte` nu mai are nicio coloana de data
scrisa de utilizator.

**Prins in aceeasi trecere:** exportul PDF al Ganttului de proiect
(`GET /api/proiecte/<id>/gantt.pdf`) dadea **500 din v32** — referinta la `stasks`, lista
sortata pe faze, a rămas dupa ce gruparea pe faze a plecat. Nicio verificare nu atingea ruta.

### Lista de taskuri e o lista DE FACUT (2026-07-30)

Ion: *„taskurile sunt cele mai importante pentru mine pe mobil. Poti sa faci ca o
aplicatie de to do?"*

Ce lipsea nu era aspectul, ci **ordinea** si **drumul pana la actiune**.

- **Ordinea e informatie.** `/api/global-tasks` intoarce `ORDER BY created_at DESC`,
  adica ordinea in care le-ai scris. `lib/grupare.js` grupeaza la CITIRE dupa termen:
  **Restante → Azi → Mâine → Zilele astea → Mai târziu → Fără termen**, cu cap de
  grupa lipit si numar. „Fără termen" e ULTIMA cu buna stiinta — e sertarul, nu
  agenda; un task fara data nu e urgent prin faptul ca n-are data.
- **Termenul se scrie relativ** (`etichetaTermen`): „azi", „acum 3 zile", „vineri".
  Si nu se scrie deloc in grupele care l-au spus deja in cap.
- **Panoul de glisare e Azi · Mâine · Dată · Șterge**, la fel pe `/tasks` si in
  pagina de proiect. Planificarea e ce faci des cu un task; editarea titlului o faci
  o data. Nota si editarea stau in randul desfasurat.
- **Adaugarea si planificarea sunt un singur gest:** cat timp scrii, sub compozitor
  apar „Azi / Mâine / Alege data". Enter ramane „fara termen".
- **Bifarea se poate anula** (`toastUndo`) pe toate cele trei liste — pe telefon se
  bifeaza si prin glisare, deci si din greseala, iar randul pleaca intr-o sectiune
  inchisa.

Gruparea NU se aplica taskurilor de proiect: acolo randurile sunt o secventa de
lucru cu `ordine`, iar o regrupare dupa zi ar rupe tocmai ce le tine impreuna.

**Culoarea e rezervata severitatii.** Randul avea trei sisteme de culoare care se
bateau — severitatea (pe atunci bordura + termenul; azi inelul bifei + termenul,
vezi tura 9), mov (categoria), amber (subtaskuri,
recurenta, numele proiectului) — iar ierarhia iesea pe dos: indexul decorativ „01"
era 16px/700 colorat, deasupra titlului de 12.8px. Acum titlul e `--font-body`,
indexul e o fantoma, si singurul lucru colorat pe rand e TERMENUL. Pe boardul
„Astăzi" cele doua pastile („Restant", „Termen azi") au plecat: pe un board unde
totul e scadent azi sau restant, ele partitionau lista si atat, iar „Restant"
repeta in cuvinte ce spunea data rosie de langa. Ramane data, scrisa relativ.

**Vederea activa nu contine taskuri bifate.** `/api/global-tasks` adauga
`AND status != 'done'` cand nu ceri arhiva. Deci o sectiune „N finalizate" in
lista activa e cod care nu se poate randa (a existat, gardata pe o conditie
imposibila). Ce ai terminat se vede in „Arhivă", si starea goala o spune.

### Cum arata o zi in Calendar

Prima versiune desena UN bloc per client, etichetat „Continental · 4 lucrari". Datele reale
au aratat de ce e gresit: din 12 perioade ale anului, **11 sunt la Continental**. Codam prin
culoare si grupare exact dimensiunea care nu variaza, si ascundeam dupa un click singura care
variaza — ce lucrare faci. Acum:

- **O bara per lucrare**, cu numele lucrarii (`implementari.eticheta`), nu al clientului.
- **Culoarea urmareste proiectul**, ca aceeasi lucrare sa fie acelasi lucru de la o zi la alta.
- **O lucrare de N zile e UN element de N zile latime**, nu N bucati. Vezi mai jos.
- **Banda (randul) e stabila pe toata durata lucrarii** — impachetare clasica pe intervale.
  Fara asta, o lucrare de doua zile apare pe randul 1 luni si pe randul 2 marti, iar bara nu
  mai citeste ca un singur lucru.
- **Antetul zilei are inaltime FIXA** (numar + captura deplasarii). Captura a stat initial pe
  rand propriu si impingea barele in jos doar in zilele de plecare — un rand in plus intr-o
  singura celula desincronizeaza toata saptamana.
- Captura deplasarii apare **doar in ziua in care incepe** si e manerul cu care muti toata
  iesirea; bara mutata singura muta doar lucrarea ei.
- Inaltimea celulei urmeaza numarul real de benzi din fereastra, ca lunile rare sa nu aiba
  jumatate de celula goala.
- Pe telefon (sub 620px) nu incape text intr-o celula de ~48px: raman barele colorate si
  numarul de lucrari, iar detaliul e in panoul de deasupra.
- Cand ziua selectata e goala, panoul arata **„Urmeaza"** — altfel ai naviga luni intregi
  goale ca sa afli cand iesi data viitoare.

### O perioada de mai multe zile e UN element (2026-07-30)

Ion: *„regandeste cum arata in calendar perioadele de implementare pe mai multe zile."*

Prima versiune desena o bara **in fiecare celula** a perioadei, fiecare cu numele scris din
nou si trunchiat la latimea UNEI zile. Pentru o lucrare de opt zile, „Pregatire documentatie
…" aparea de **noua** ori — si fiecare copie era ciuntita, desi lucrarea avea sase celule de
spatiu. Doua trunchieri diferite ale aceluiasi text, una langa alta, se citesc ca doua lucruri
diferite, nu ca unul care continua.

Acum benzile sunt **elemente ale grilei, peste celule**, cu `grid-column: <col> / span <n>` —
`bare` in `Calendar.svelte` taie fiecare perioada in felii de saptamana. Numele se scrie o
data per felie si foloseste toata latimea. Capetele rotunjite arata inceputul si sfarsitul
REAL; la granita de saptamana capatul rămâne drept si felia urmatoare poarta „…".

Trei capcane, toate lovite:

- **`minmax(0, 1fr)`, nu `1fr`** pentru coloane. `1fr` inseamna `minmax(auto, 1fr)`, deci o
  banda care se intinde peste coloane si are `nowrap` isi impune latimea minima si largeste
  coloanele pe care le acopera. Zilele nu mai erau egale si se desincronizau de antetul
  zilelor saptamanii.
- **Celulele trebuie asezate EXPLICIT** (`grid-row`/`grid-column` calculate din index). Altfel
  auto-plasarea sare peste pozitiile ocupate de benzi si celulele se muta din loc.
- **Benzile devin transparente la cursor cat timp tragi** (`.grid.trag .banda`). Ele stau
  PESTE celule, deci altfel un drop peste o banda de patru zile n-ar sti pe care zi a cazut.

Decalajul de sus al benzii trebuie sa fie exact zona de bare din celula
(`--h-antet: 24px` = bordura 1 + padding 5 + antet 15 + gap 3) cu pasul `--h-banda: 20px`
(bara 17 + gap 3). Numerele sunt aceleasi cu cele din `min-height` al celulei — **se schimba
impreuna**, altfel benzile plutesc pe langa celule.

Bonus prins in aceeasi trecere: clasa `azi` era pe **doua** lucruri diferite — butonul „Azi"
din bara de sus si celula zilei de azi (`.zi.azi`). Selectorul neprefixat `.azi` prindea si
celula, care primea `display: inline-flex` cu centrare si `padding: 0 10px` — de aceea
numarul zilei de azi stătea centrat in mijlocul celulei. Butonul e acum `.b-azi`.

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

- `audit_mobil.py` — **audit mobil masurat.** Ce nu prinde `smoke_ui`: butoane
  taiate de marginea din dreapta (`overflow-x: clip` le ascunde fara niciun semn),
  tinte sub 44px, campuri sub 16px (Safari face zoom la focus), gesturile de pe
  randul de task executate cu deget adevarat, si comportamentul de **lista de
  facut** (gruparea pe termen, adaugarea cu zi, mutarea din glisare, „Anulează").
  Toate rutele × trei latimi de telefon.

```bash
python scripts/audit_mobil.py                 # geometrie + gesturi
python scripts/audit_mobil.py --fara-gesturi  # doar geometrie
```

De ce exista: nimic din ce masoara el nu arunca vreo eroare. Pe 2026-07-30
„Proiect Nou" iesea din ecran pe /projects, taskurile din „Astăzi" aveau 76 de
sageti de 40×22px, un tooltip aparea PESTE lucrul atins, iar blocul mobil din
Planificator era anulat in intregime de reguli scrise mai jos in acelasi fisier —
build verde, `smoke_ui` verde, `test_suite` 12/12.

- `audit_navigare.py` — **ce se intampla, masurat, cand schimbi tabul.** Cinci
  contracte pe care nicio captura de ecran nu le arata: prima incarcare ARE
  `rutaIn`/`cellIn`; schimbarea de tab nu mai are niciuna (tranzitia o detine
  browserul); revenirea pe un tab nu trece prin schelet; hoverul cere modulul si
  datele inainte de click, iar pe date proaspete nu mai cere nimic; o pagina noua
  incepe de sus. Porneste singur aplicatia pe o copie a bazei, ca `smoke_ui`.

```bash
python scripts/audit_navigare.py
```

  De ce exista: pe 2026-08-14, la fiecare apasare de tab se jucau TREI animatii
  de intrare peste aceiasi pixeli, iar Calendarul punea schelet la FIECARE
  intrare — cu build verde, `smoke_ui` verde si `audit_design` curat.

- `audit_design.py` — **coerenta sistemului de design.** Ce nu prinde niciunul
  dintre celelalte: `transition: all`, culori scrise de mana, durate/easing in
  afara scarii, o a doua paleta copiata in alta pagina, tokenuri folosite dar
  nedefinite, tokenuri de culoare care exista doar pe o tema. Nu porneste browser,
  ruleaza in mai putin de o secunda.

```bash
python scripts/audit_design.py            # iese 1 daca sunt abateri
python scripts/audit_design.py --lista    # fiecare aparitie, nu doar primele 5
```

De ce exista: incoerenta se randeaza PERFECT. Pe 2026-07-30 paleta de identitate
traia in doua fisiere cu aceleasi culori rotite cu doua pozitii — build verde,
`smoke_ui` verde, `test_suite` 12/12, `audit_mobil` curat, si totusi 43% dintre
proiecte aveau o culoare in Calendar si alta in Planificator. Se vede doar cand
pui doua ecrane alaturi, sau cand o masoara cineva.

- `solve_paleta.py` — re-rezolva paleta de identitate a proiectelor
  (`frontend/src/lib/culori.js`). Ruleaza-l daca schimbi accentul sau tokenurile
  semantice/de locatie; paleta depinde de ele si se RE-rezolva, nu se ajusteaza
  pe bucati.

Cerinte, o singura data si doar pe masina de dezvoltare (NU in `requirements.txt`):

```bash
pip install playwright && python -m playwright install chromium
```

Daca Chromium e deja instalat in alta parte (container, sesiune la distanta),
`PIF_CHROMIUM=/cale/catre/chromium` il foloseste pe acela, fara descarcare.

No pytest/unittest framework.

## Multi-Agent Collision Rules

Shared working tree → shared git index, so coordinate before staging/committing. When spawning sub-sessions:
- **Main app (SPA):** `frontend/src/` (Svelte components/pages) → built into `static/dist/`
- **Import session:** `scripts/parse_params/*`
- Always `git fetch && git pull --rebase` before push. No force push.

> See `AGENT_BRIEFING.md` (spawn template) for the multi-agent workflow.

### Redesign complet: oțel, Gabarito, o singură axă de culoare (2026-08-08)

Handoff-ul „Design audit complet dashboard" (10 prototipuri `.dc.html` + `DIRECTIA-DE-DESIGN.md`).
Ce s-a schimbat la nivel de sistem și **de ce**, ca să nu se re-deschidă din instinct:

- **Accentul amber a plecat.** Nu ca stil: amberul Bento, movul „info/purple" și „service"
  erau a **doua și a treia culoare de brand**, iar `--accent` și `--warning` erau *exact
  același hex*. Acum accentul e unul, iar restul culorilor spun doar **stare** (restant,
  făcut). Ce era codificat cromatic și nu mai e: identitatea proiectului în Calendar,
  locația (Site/Sediu), tipul PIF/Service, weekendul.
- **Cele ~25 de nume vechi de token sunt ALIASURI**, nu roluri în plus (`--warning` →
  `--danger`, `--purple`/`--info`/`--service-*` → accent, `--text-faint` → `--text-dim`).
  Aliasul rezolvă prin `var()`, deci urmează automat tema țintei — de aceea
  `audit_design.py` scutește aliasurile de regula de paritate între teme (R7); a cere o a
  doua definiție ar însemna exact a doua sursă de adevăr pe care regula o previne.
  `--accent-on-subtle` e literal `--accent-deep`, deci regula „text pe tentă ia adâncul" se
  repară singură în cele ~20 de locuri care o încălcau.
- **Fonturi: Gabarito (text) + DM Mono (cifre)**, self-hosted în `static/fonts/`. Inter,
  Space Grotesk și JetBrains Mono au ieșit. Subsetul `latin` are â/î, `latin-ext` are ă/ș/ț
  — **verificat pe `cmap`, nu presupus**; împreună acoperă româna.
- **Scara: 12 · 13 · 15 · 21 · 25.** Pe telefon **pagina crește** (28) și corpul crește (16);
  rândul rămâne 15, fiindcă el poartă densitate. `--font-h3` s-a colapsat la 15/600
  („etichetă de pagină"), nu la 17 — 17 nu mai există în scară.
- **Raze: 8 chip · 10 control/rând · 14 suprafață · 20 foaie · cerc doar bifa.** Nimic între.
- **Elevația se citește din UMBRĂ, nu din linii peste tot** — două niveluri. Deci: fondul
  redevine o culoare (glowurile radiale de sub fiecare card au plecat), `backdrop-filter`
  a plecat de pe header, dock, paletă și voaluri, iar cardurile pierd chenarul.
- **Mișcare: 90 apăsare · 220 element · 280 suprafață**, o curbă standard și **un singur**
  arc (`cubic-bezier(.34,1.35,.42,1)`). Staggerul e 40ms, plafonat la **șase** celule.
  **`reduced-motion` nu mai înseamnă durată ZERO, ci 120ms fără translație** — o tranziție
  de durată zero nu emite `transitionend`, iar bifarea se sincronizează pe el.

**RÂNDUL DE TASK E UN SINGUR OBIECT, în trei liste.** `/tasks`, boardul „Astăzi" și tabul
Taskuri al proiectului au acum aceeași geometrie, până la pixel: 46px înălțime, gap 12,
**termenul pironit într-o coloană de 46px cu valoare pe fiecare rând**, acțiunile cu **text**
(nu iconițe mute) apărute la hover **la stânga** termenului, titlul cedează lățimea.
Coloana de 16px a mânerului de reordonare e **rezervată pe toate rândurile**, ca absența să
nu pară greșeală. Listele n-au rânduri-card: un separator de 1px cu marjă laterală.
Ce a plecat de pe rând: categoria, indicatorul de notiță, săgeata de desfacere.
(Fracția de pași plecase și ea; s-a întors pe 2026-08-15 — vezi mai jos.)
Dacă schimbi forma, schimb-o în **toate trei** — sursa e `Tasks.svelte`.

**O singură cale de adăugare per ecran:** linia cu Enter pe desktop, butonul mare cu plus pe
telefon (`/tasks`). Pe „Astăzi" rămâne compozitorul, fiindcă acolo e al boardului.

**Căutarea trăiește într-un singur loc: paleta din dock.** Câmpurile locale de pe `/tasks` și
`/projects` au plecat — același gest („caut un task") avea două unelte cu rezultate diferite,
iar paleta le găsește pe toate și aterizează pe rând (`?focus=`). Pe telefon lupa rămâne în
cap, fiindcă dockul de acolo n-o are.

**Panoul face loc, nu acoperă.** În Calendar coloana panoului apare **odată cu el**, iar la
încărcare **nu e selectată nicio zi** — grila trece de la 127 la 176px pe zi, exact pragul de
la care eticheta unei lucrări se poate citi în bara ei. „Proiecte fără perioadă" a urcat din
panou în capul paginii: e o **sursă**, nu un detaliu al zilei, și în panou nu se vedea tocmai
când n-aveai nicio zi deschisă.

**Tabul „Calcule" a plecat din pagina proiectului — și cu el, butonul „Proiect" din
Calculator.** Handoff-ul cerea doar tabul, dar tabul era **singurul cititor** al lui
`POST /api/proiecte/<id>/calcule`: scos singur, ar fi rămas un buton care salvează într-un loc
pe care nu-l mai poți deschide. Ruta de API și datele existente sunt neatinse — dacă
funcția se reia, se reia cu ambele capete.

**Un singur toast pe ecran, 4s.** Cel înlocuit **se comite** (`onCommit`), nu se aruncă:
altfel rândul rămânea șters din interfață și neșters din bază.

### Contorul de pași se întoarce pe rând (2026-08-15)

Ion: *„la taskuri, când are subtaskuri ar fi bine să arate un counter subtil undeva,
câte din câte sunt îndeplinite."* Asta **ridică interdicția E1** („fracția de pași nu
stă pe rând, rândul poartă două lucruri — ce e de făcut și când"), pusă la redesignul
din 8 august. Se ridică în **toate cele patru liste deodată**: `/tasks`, „Astăzi",
tabul Taskuri al proiectului și rândul mobil din Planificator.

- **O rețetă, un loc: `components/ui/ContorPasi.svelte` + `.tpasi` în `global.css`.**
  Forma (SVG-ul) stă în componentă, culorile în `global.css`; apelanții dau doar
  `gata`/`total` și componenta se randează ca **nimic** dacă `total` e 0 — altfel
  același `{#if}` s-ar repeta în patru locuri. Înainte, același fapt avea o haină pe
  „Astăzi" (`.a-pasi`, pe linia a doua), niciuna în celelalte trei, și un
  `.tsub-chip` mort în `global.css` fără niciun consumator.
- **Inel + fracție, și inelul e o FELIE, nu un arc.** Direcția a ales-o Ion dintre
  șapte machete (`ContorPasi.dc.html`). Prima versiune a inelului desena `r=5` cu
  `stroke-width: 2` și **nu se citea**: la 12px un arc de două puncte n-are suprafață
  din care să vezi cât e umplut — măsurat pe machetă, „0/3" și „5/5" arătau aproape
  la fel. Trucul care rezolvă: `r=3` cu `stroke-width: 6` întinde conturul de la
  centru (r=0) până la marginea cercului (r=6), deci pata plină a unei felii,
  desenată fără niciun `path`. La 100% devine disc plin.
  Asta răspunde și obiecției „al doilea cerc pe rând, lângă bifă": bifa e un cerc
  **gol** de 18px, felia e o **pată** de 12 — se confundă doar la 0%, unde felia e
  și mai mică, și mai stinsă.
  `rotate` se scrie ca **atribut SVG**, nu `transform-origin` în CSS: pe elementele
  SVG originea implicită e colțul viewport-ului, și ar cere și `transform-box`.
- **Lângă titlu, nu într-o coloană.** O coloană ar fi goală pe majoritatea rândurilor,
  iar o coloană cu goluri nu se mai citește pe verticală — adică pierde exact singurul
  motiv pentru care termenul e coloană. Contorul răspunde la „cât din lucrul ăsta",
  deci se leagă de titlu; termenul răspunde la „când" și rămâne pironit la dreapta.
- **Fără culoare, nici la 5/5.** Pe rândul de task culoarea e rezervată severității
  (inelul bifei + textul termenului, amândouă din `--ring`); o tentă verde ar fi al
  treilea canal cromatic, adică fix ce a demontat tura 9. Că e gata pe dinăuntru o
  spune cifra — și tot ea spune și cât mai e, ceea ce o tentă nu poate.
- **Și fără mono** — Gabarito 13/400, sub cele 15/500 ale titlului. Prima livrare l-a
  scris în DM Mono și Ion a cerut „mai subtil și mai estetic"; regula era deja scrisă
  mai sus: *mono = cifre care se compară pe verticală*. Termenul e mono fiindcă e o
  coloană pironită, citită de sus în jos; contorul plutește după un titlu de lungime
  variabilă, deci nu se aliniază cu nimic și n-are ce compara. Lângă literele rotunde
  ale lui Gabarito, cifrele late și bara oblică groasă a unui monospațiat se citeau ca
  un fragment de cod lipit pe rând. Măsurat: „1/4" trece de la 23px la 16, iar pe
  telefon nu se mai citește împreună cu termenul mono de alături.
  **`tabular-nums` a plecat atunci și s-a întors odată cu inelul**, din alt motiv:
  nu alinierea, ci stabilitatea. Cu cifre proporționale „1/4" și „2/4" n-au aceeași
  lățime, deci la fiecare bifă tot contorul — inclusiv felia — s-ar deplasa lateral.
  Singurul lucru care are voie să se miște când bifezi un pas e felia care crește.
- **Cea mai proaspătă sursă câștigă.** `pasi()` (în `Tasks.svelte` și `ProjectDetail`)
  citește din `subtasksCache` când există, altfel din `subtask_total`/`_done` de la
  server. Fără asta, bifarea unui pas în rândul desfăcut nu mișca cifra de deasupra
  lui: `toggleSubtaskDone` scrie în cache și **nu** reîncarcă lista. Un `[]` în cache
  înseamnă „am întrebat, n-are niciunul", deci scoate contorul.
- **Scrierile de subtask invalidează acum listele** (`uitaSubtaskuri` în
  `stores/tasks.svelte.js` → `/api/global-tasks`, `/api/plan`, `/api/proiecte`).
  Fișierul își scria regula în cap — „orice scriere invalidează lista" — dar cele trei
  mutații de subtask erau singurele scutite. Era invizibil cât timp nicio listă nu
  arăta date de subtask; de acum, fără ele, bifai un pas, plecai de pe pagină și
  cifra veche revenea din cache. Toate trei prefixele, fiindcă `updateSubtask` are
  doar id-ul subtaskului: de acolo nu se poate ști dacă părintele e task de proiect
  sau global.
- **`.mrow-main` din Planificator și `.amain` de pe „Astăzi" sunt coloane**, deci
  titlul a primit un înveliș de rând (`.mrow-titlu` / `.atitlu`). Pe „Astăzi",
  `align-self: flex-start` a urcat pe înveliș: pe titlu ar fi însemnat aliniere pe
  verticală, iar el era acolo ca tăietura de „done" să se oprească la ultima literă.
- **`.tmain` din `ProjectDetail` era coloană degeaba** — rămăsese de pe vremea celei
  de-a doua linii (`.tinfo`), care n-avea niciun consumator în markup de la E1 încoace.
  Cu ea, contorul ar fi aterizat *sub* titlu aici și lângă el în celelalte trei.
- **Prins în aceeași trecere:** pe „Astăzi" contorul era gardat pe `contextRand(it)`
  împreună cu întreaga linie a doua, deci un task cu pași dar fără proiect și fără
  categorie nu-l arăta deloc.

### Un singur editor pentru toate câmpurile lungi (Proiecte 5a, 2026-08-08)

Observații tehnice, Constatări, Acțiuni și rezultat, nota unui task: patru drumuri către
același lucru, și nu se purtau la fel. Notele salvau la închidere cu toast de anulare;
câmpurile de proiect aveau „Anulează" și „Salvează", dar X / fundal / Escape **aruncau
în tăcere** ce scriseseși. Același gest, două înțelesuri opuse, în aceeași pagină.

`components/ui/EditorLung.svelte` e acum shell-ul unic: Modal `doc` + editor + o bară de
jos cu indiciul la stânga și „Salvează" la dreapta. **Închiderea COMITE**, cu „Anulează"
în toast; nu există buton care aruncă.

- **`$effect.pre` + `untrack`, nu `$effect`.** `RichTextEditor` își umple contenteditable-ul
  **la montare**, din valoarea de atunci; un efect obișnuit rulează după montare, deci
  editorul s-ar deschide cu textul dinainte. `untrack` fiindcă singura dependență e `open`:
  dacă părintele reîncarcă datele cât scrii, ciorna nu are voie să fie înlocuită sub degete.
- **Funcția de scriere se capturează la comitere** (`const scrie = salveaza`). Toastul
  trăiește 4s, timp în care poți deschide alt câmp — iar `salveaza` e o proprietate, deci
  citită la apăsarea pe „Anulează" ar fi cea a câmpului NOU: textul vechi al observațiilor
  s-ar scrie peste nota altui task. Din același motiv fiecare `open*` construiește
  închiderea cu ținta în ea, nu citește starea curentă.
- **Pe eroare modalul se REDESCHIDE** cu ciorna intactă: `Modal.inchide()` face `open = false`
  *înainte* de `onclose`, deci fără asta pagina dispărea cu tot cu textul.
- `RichTextEditor` a rămas cu o singură formă. Varianta `box` (casetă cu chenar, numărător de
  caractere) n-avea niciun consumator după unificare, iar `backdrop-filter: blur(14px)` de pe
  pilula plutitoare a plecat: sticla e scoasă din sistem, și aici nici nu era decor — pilula
  plutește **peste** textul pe care-l editezi, deci rândurile de dedesubt se citeau prin ea.

### Fereastra de notificări: patru reglaje, aceleași de pe orice dispozitiv (14b, 2026-08-08)

Nu se face pagină de Setări. Singurele reglaje sunt cele patru ale notificărilor și trăiesc
în fereastra clopoțelului din `/tasks`, vizibil doar în sfera Personal.

- **Nu mai sunt ascunse pe web.** Erau gardate pe `esteNativ()` cu motivul „pe web nu există
  canalul local pe care să-l regleze" — dar cele patru nu sunt ale canalului, sunt ale
  REGULII, iar regula o citește și planificatorul de pe server. Deci ora la care sună
  telefonul se putea schimba doar de pe telefon, deși setarea era comună. Acum se arată
  oriunde există ceva de programat (nativ mereu; pe web când există măcar un dispozitiv
  abonat — de pe PC reglezi ce sună pe telefon).
- **Comutatorul „scadente" chiar comută ceva.** `check_and_send_daily` trimitea DOAR taskurile
  fără termen (`if setari['faraTermen']`); motivul `scadent` exista doar pe telefon
  (`lib/notificari.js`). Adăugat `taskuri_scadente()` + `_de_notificat()` în `push.py`. Cu el
  a trebuit și **al doilea buton din payload** (`a2`): pe un task scadent azi, „Azi" ar scrie
  data pe care o are deja — service worker-ul îl avea scris în cod. Rezerva rămâne „Azi",
  pentru notificările vechi din coadă. `VERSION` bumpat la `v100`.
- **Salvarea confirmă cu numărul** („Salvat — 4 notificări programate"): pe telefon din
  reprogramarea locală, pe web din `programate`, întors acum de `PUT /api/push/setari`.
- **Proba stă la stânga, departe de „Salvează"**: una verifică lanțul acum, cealaltă schimbă
  ce se întâmplă mâine. „Nu mai trimite pe dispozitivul ăsta" a coborât lângă numărul de
  dispozitive — e despre ACEST aparat, nu despre regulă, deci n-are ce căuta al treilea verb
  în bara de jos.
- Regula „cel puțin un fel pornit" e **scrisă în fereastră**, nu descoperită dintr-o eroare
  după ce ai apăsat Salvează.

### Perioada se întinde, iar vecinul se dă la o parte (Calendar, turele 7–8, 2026-08-08)

`redimensioneaza()` scria capetele și lăsa coliziunea să se întâmple, deși „perioadele nu se
suprapun" era deja regula. Înlocuit cu `intinde()`, care decide după CINE e vecinul:

- **același `loc\|client` = continuare, nu coliziune.** Nu se scrie nimic în plus: `deplasari`
  grupează deja zilele consecutive pe cheia asta, deci în clipa atingerii datele spun „o
  singură ieșire". Toastul o spune („o deplasare, 8 zile") și se poate anula. Se anunță
  **doar când chiar s-a alipit ceva nou** — doi vecini care se atingeau și înainte erau deja
  o deplasare.
- **alt loc sau alt client = vecinul e împins**, cu o zi **lucrătoare** (`nextWorkday` în
  `calendarDates.js`), păstrându-și durata. **Împingerea se propagă**: un singur pas ar putea
  așeza vecinul fix peste următorul, adică aceeași suprapunere mutată cu o căsuță. Bucla e
  mărginită (fiecare mutare împinge strict la dreapta) și toastul spune câte s-au mutat.
- **Anulează readuce TOT** — perioada trasă și fiecare vecin împins. O propagare tăcută ar fi
  fost singurul lucru inacceptabil.
- **Fantoma e CONTUR peste banda reală, nu o mută.** Banda apucată nu se mai stinge la 32%:
  la întindere cele două se suprapun aproape complet, deci vedeai un dreptunghi cu două
  opacități și nu mai știai care e starea de acum. Fără fundal și fără text — al doilea
  exemplar al aceluiași nume, decalat cu o zi, se citește ca două lucrări.
- **Mânerele sunt două bare subțiri de accent**, la hover, pe toată înălțimea benzii (era o
  pastilă albă de 2×9px în mijloc).
- **`chenar` — ieșirea ca un singur obiect.** Fără el alipirea n-avea ce să arate: două
  perioade care se ating devin o deplasare, dar pe ecran rămâneau două bare la fel ca înainte.
  Chenarul acoperă zilele consecutive la același `loc\|client` și exact benzile lucrărilor lui;
  raza stă **doar pe capetele adevărate**, deci la alipire cele două muchii rotunjite din
  mijloc dispar — asta e „peretele se stinge". Lucrările rămân bare separate înăuntru: s-au
  unit ieșirile, nu lucrările.
- **Pe telefon pista se citește, nu se manipulează.** Gestul e oprit în `seManipuleaza()`
  (`ecran.telefon || ecran.grosier` — perechea în JS a lui `@media (hover: none)`, ca desenul
  și comportamentul să nu se desincronizeze), iar mânerele sunt `display: none`. Asta
  **răstoarnă** decizia din 7 august („Perioadele se trag cu mâna" acoperă acum doar mouse-ul):
  alegi o ZI dintr-o celulă de ~48px acoperită de benzi, iar ce iese din gest nu e „aproape ce
  voiai", e altă zi scrisă în bază. `audit_mobil.py`, secțiunea „perioadele se trag", a fost
  întoarsă odată cu contractul: la deget verifică acum că **nu** există mânere și că apăsarea
  lungă + tragerea **nu** mută nimic.

### Android: fără rețea, barele sistemului, plecarea pe teren (12c/12d/15, 2026-08-08)

- **„Fără rețea" (12c).** `capacitor.config.json` are `server.url`, deci aplicația **e**
  site-ul: fără rețea rămâneai cu pagina de eroare a lui Chrome. `server.errorPath`
  încarcă acum `fara-retea.html`, care vine din **asset-urile aplicației** (Capacitor îl
  servește de pe `https://localhost`), deci nu cere nimic din rețea. Scris de mână, cu
  patru culori copiate din `tokens.css`: foaia aia e în bundle-ul de pe server, adică
  exact lucrul care lipsește.
  - **Nu poate citi `localStorage`-ul aplicației** — alt origin. Ce spune („ultima dată
    văzut", „N notificări programate") vine de la partea nativă, prin `NotificariPif.stare()`.
    Ultima vizită o scrie `MainActivity` dintr-un `WebViewListener`, **filtrat pe adresa
    serverului**: `onPageLoaded` vine și pentru pagina locală de eroare, deci fără filtru
    „ultima dată văzut" ar fi mereu „acum".
  - „Încearcă din nou" cheamă `NotificariPif.reincarca()`, care ia adresa din punte — o a
    doua copie a ei în HTML ar fi cea care rămâne în urmă.
- **Barele sistemului (12d).** `setDecorFitsSystemWindows(false)` + bare transparente +
  `setNavigationBarContrastEnforced(false)` (altfel Android desenează singur un scrim gri,
  adică exact culoarea proprie pe care n-o vrem). Merge doar împreună cu
  `viewport-fit=cover`, care era deja în `index.html` — abia atunci WebView-ul dă valori
  reale în `env(safe-area-inset-*)`, din care ies `--safe-top/bottom`. Iconițele barelor
  comută cu tema sistemului.
- **Alarma exactă se verifică la fiecare pornire** (`MainActivity.onResume`), dar ecranul de
  sistem se deschide **o singură dată per retragere** (`exacte_intrebat`, resetat când
  permisiunea revine): un ecran de sistem care se deschide singur de fiecare dată e o
  capcană, nu un ajutor. Drumul care rămâne mereu la îndemână e caseta din fereastra de
  notificări, cu „Deschide ecranul".
- **Turul 15 — notificarea de plecare pe teren.** Alarmă pe **prima zi** a unei ieșiri cu
  `loc = Site`, **seara dinainte** (18:00 implicit, reglabil), pe canalul propriu
  „Deplasări", **fără butoane** (o plecare nu se bifează, iar un buton care mută planul de
  pe ecranul de blocare e ireversibil de acolo).
  - **Canalul e unitatea pe care o poate opri utilizatorul din Android.** „Nu vreau să mă
    anunțe seara că plec" și „nu vreau taskurile de dimineață" sunt două decizii diferite;
    pe același canal ar trebui luate împreună.
  - **Regula ieșirii trăiește acum într-un singur loc:** `lib/deplasari.js`
    (`grupeazaDeplasari`, cheia `loc|client`). Calendarul o folosește în locul derivării
    lui locale. Scrisă de două ori s-ar fi rupt tăcut — calendarul ar arăta o ieșire,
    telefonul ar suna de două ori. De aici ies gratis cele trei cazuri care **nu**
    declanșează: pregătirea la Sediu, zilele 2…n, și a doua perioadă alipită la același
    `loc|client`.
  - **Fereastra e de 60 de zile, nu 7** ca la dimineți: diminețile se recalculează din
    lista de taskuri, care se schimbă zilnic; o deplasare se pune în calendar cu săptămâni
    înainte și nu se mai schimbă. Alarmele sunt ieftine, tăcerea nu.
  - Al treilea comutator, cu ora lui, e în fereastra de notificări și **nu** intră în regula
    „cel puțin un fel pornit" — aia păzește taskurile. Rândul lui **nu e un `<label>`
    întreg**: eticheta ar prinde și clicul pe selectorul de oră, deci alegerea orei ar
    stinge comutatorul.
  - Prins în aceeași trecere: `zileDeCand` din `notificari.js` returna `ZILE_VECHIME`, o
    constantă **inexistentă în modul** — pe un `created_at` necitibil arunca ReferenceError
    și tăcea toată reprogramarea, nu doar taskul cu data stricată.
### Planificator: înălțimea vine din împachetare (turele 4–6, 2026-08-08)

Ultima bucată a handoff-ului. Restul turei era deja construit din runde vechi (fereastra din
azi, cele cinci orizonturi, banda de perioadă, coloana de restanțe); ce lipsea era **regula
rândurilor**, **antetul de timp** și **orizontul lung**.

- **`packRows` măsoară ce se desenează, nu ziua.** Reperul e acum chiar coloana termenului
  (bară de o zi, 20px, contur = de făcut · plin = în lucru · tentă verde cu bifă = făcut), iar
  titlul **iese din ea**, la dreapta. Deci întinderea unui reper e *bara + titlul*, nu una din
  ele. ~~Rândul: `14 + n×20 + (n−1)×4 + 6`, minim 48~~ → **înlocuit 2026-08-15**, vezi
  „Perioada e o șină la baza rândului" mai jos: `6 + n×20 + (n−1)×4 + 20`, minim 44 →
  **1 reper 46 · 2 repere 70 · 3 repere 94**. Stiva nu se mai centrează, se **ancorează sus**.
  - ~~**Eticheta perioadei ține rândul întâi**~~ — **nu mai e adevărat.** Perioada nu mai scrie
    nimic în pistă, deci `packRows` se cheamă cu `blocate` GOL. Asta e chiar sursa scăderii de
    înălțime: rândul nu mai crește din coliziuni.
  - **Suprapunerea se testează cu TOT rândul, nu cu ultimul așezat.** Greedy-ul clasic „după
    ultimul" presupune că totul intră în ordine. Regula rămâne corectă și utilă (două repere
    apropiate), chiar dacă rândul întâi nu mai pornește ocupat.
  - **Numele de proiect a revenit pe UN rând.** Cu două rânduri, eticheta cerea 73px și
    `min-height: 48` nu mai însemna nimic: o bandă cu un reper și una cu trei arătau la fel —
    adică exact ce trebuia să spună înălțimea. Numele reale se despart de la primele caractere;
    ce se repetă e *sufixul* de client („— Continental"), adică fix ce pierde o trunchiere la
    dreapta.
  - **Întoarcerea titlului (`flip`) e geometrică, nu un prag.** Era `left > 62`, ales pentru
    altă geometrie: un reper la 64% cu titlu de 15% se măsura spre STÂNGA, peste bandă, și
    cobora trei rânduri degeaba. Acum se întoarce doar când n-ar încăpea la dreapta.
    (Se aplica ~~și etichetei unei perioade~~ — de la 2026-08-15 perioada n-are etichetă în
    pistă, deci `flip` a rămas doar al reperelor.)
- **Antetul are o singură structură: grosier peste fin.** Rând de săptămâni (S32 · S33)
  peste rândul de zile (inițială + cifră), 52px. Separator `--border` între coloane,
  `--border-strong` la granița grupei, **coborând continuu prin toate benzile**. Grupele nu-și
  recalculează muchiile: le adună din coloanele fine (`grupeazaColoane`), altfel două socoteli
  ale aceleiași margini se despart la a treia zecimală — și se vede, fiindcă linia groasă
  coboară prin bandă. **`.col-line` stă pe muchia din STÂNGA**, deci granița ei e `i-1`.
  - **Luna nu stă în antet** — o spune subtitlul paginii („de azi, 14 zile · 8–21 aug").
  - **„Azi" are aceeași formă ca orice coloană**, doar că scrie „azi" în loc de inițială, în
    accent, pe tentă. **Fără inel** (rezervat zilei de sub cursor la tragere) și **fără linia
    de 2px**: fereastra pornind mereu din azi, linia stătea la `left: 0`, lipită de cusătură,
    unde citea ca bordură de tabel. Rămâne coloana tentată, cu două muchii de accent.
- **La 3L/6L antetul urcă un nivel: luni peste SĂPTĂMÂNI.** De aceea `buildColumns` primește
  `unitCerut` și Planificatorul cere `week` și la 6L — implicitul dădea luni, iar peste luni
  n-are ce să mai urce. Ganttul de proiect nu cere nimic și rămâne pe scara veche: fereastra
  lui vine din date și poate ține un an, unde 52 de coloane de săptămână ar fi trei ecrane.
  - ~~Perioadele devin **bare pe rândul întâi** cu eticheta **lângă** ele~~ — **scos
    2026-08-15.** Exact mecanismul ăsta (`.ib-out`) avea un bug: eticheta ieșea din bandă fără
    să verifice dacă locul de afară e liber, deci două perioade pe același rând își tipăreau
    numele **una peste alta**, ilizibil (măsurat: 2 perechi, la 3L și la 6L). Acum perioada e
    aceeași șină la toate orizonturile; **lățimea minimă de 11px a rămas**, ca regulă CSS.
  - **Reperele se strâng într-un număr pe săptămână** (`.count accent`, aceeași pastilă ca
    peste tot). Nu deschide nimic și nici n-ar avea unde: fereastra pornește mereu din azi,
    deci nu există zi pe care să aterizezi. Spune în ce săptămână se îngrămădesc — adică unde
    cobori la 14z. Indicația de sub pistă se schimbă odată cu ele: una care promite un gest
    inexistent e mai rea decât niciuna.
  - Pe telefon scara arată **grupele** (lunile) la 3L/6L: 27 de coloane de săptămână pe 350px
    ar fi 13px fiecare, adică o dungă fără cifre.
  - **`iso` rămâne gol pe coloanele de săptămână.** Ganttul de proiect îl compară cu ziua de
    azi (`c.iso === today`); cu data de luni acolo, săptămâna s-ar aprinde o zi din șapte.
    Coloana care CONȚINE azi se află din procente (`contineAzi`), nu dintr-o egalitate.

### Perioada e o șină la baza rândului (2026-08-15)

Ion: *„nu arată prea bine"* — despre perioadele de o zi, tăiate. Simptomul era însă al unei
structuri: perioada e un **interval** care ținea toată înălțimea rândului și își scria numele
**înăuntru**, pe aceiași pixeli orizontali pe care îi voiau titlurile taskurilor, care sunt
**puncte**. Măsurat pe aplicație (14z, pistă 1034px, 4 proiecte, 6 perioade, 13 taskuri):

| orizont | text tăiat | text peste text | benzi fără nume |
|---|---|---|---|
| 7z | 3 | 0 | 0 |
| 14z | **4** | 0 | 0 |
| 30z | 1 | 0 | **4** |
| 3L / 6L | 0 | **2** | 0 |

Cazul cel mai rău: „Sediu EGB · Verificare parametri" primea **36px din 183** — 20% din nume.
Iar înălțimea venea din **coliziuni**, nu din conținut: eticheta benzii ținea rândul întâi al
împachetării, deci un proiect cu patru taskuri ajungea la 112px.

**Perioada e CONTEXT („unde ești"), taskul e CONȚINUT („ce ai de făcut").** Contextul coboară
într-o **șină de 4px la baza rândului** — convenția baseline din Gantt, unde bara subțire e
contextul și cea groasă e subiectul. Aceeași gramatică o folosesc uneltele de resurse (Float,
Resource Guru țin disponibilitatea într-o bară separată de rezervări). Rezultat măsurat:
**0 tăiat și 0 suprapus pe toate cele cinci orizonturi**, graficul de la 410 la 371px.

- **Fâșia de jos e goală, deci eticheta are loc.** Locul se scrie într-o **pastilă la capul
  șinei** („⚲ Site" / „🏢 Sediu EGB"), iar golul se măsoară până la **începutul perioadei
  următoare** — deci pastila încape întreagă sau nu se randează. Nu există stare în care se
  taie. Vechiul prag (`BANDA_TEXT_MIN`, în **procente din fereastră**) pretindea că măsoară
  dacă textul încape, dar procentele nu spun nimic despre pixeli: o zi la 14z trece pragul de
  6,5% fie că înseamnă 48px, fie 95.
- **`packRows(repere, [])`** — `blocate` a rămas fără obiect. De aici vine scăderea de
  înălțime, fără să dispară nimic de pe ecran.
- **`.lane-track` se ancorează sus** (`flex-start`), nu se mai centrează. Înălțimea rândului
  poate fi dictată de coloana din stânga când ea cere mai mult decât formula (nume + contor +
  chip, ~25px); centrată, surplusul cobora stiva în fâșia șinei — măsurat, exact așa apărea o
  suprapunere între eticheta unei perioade și titlul unui task.
- **Pastila merge cu zilele.** Fereastra pornește mereu din azi, deci o deplasare **în curs**
  e tăiată la stânga; ancorată la capul *vizibil* al șinei, pastila stă pe muchia ferestrei și
  avansează pe măsură ce perioada se scurtează — rămâne citibilă exact când ești pe teren.
  **Pe `clipL` șina nu primește terminator**, altfel capul ei ar afirma că deplasarea începe azi.
- **Șina e plină, nu tentă.** Pe 4px înălțime o tentă de 10% nu se mai vede — aceeași
  compensare de suprafață pe care pista mobilă (34px) o făcea deja, desenând banda mai tare
  decât desktopul.
- **Au plecat:** `.impl-band.lung`, `.ib-out`, `.ib-txt`, `.ib-zile`, `flip` de pe bandă,
  `BANDA_TEXT_MIN`, `BANDA_ZILE_MIN`, și `--h-stiva` n-a mai rămas cu niciun consumator în CSS.
- **Capcană, pista mobilă:** `.mp-track .impl-band` trebuie să-și **reafirme `height: auto` și
  `display: flex`**. Cu `top`, `bottom` și `height` puse toate trei, `height` câștigă — deci
  fără prima, blocul de 34px de pe telefon devenea șina de 4px; fără a doua, iconița cădea în
  colțul din stânga-sus, fiindcă baza nouă nu mai e flex.

## Design system (frontend)

**Sursa unică: `frontend/src/styles/tokens.css`** — citește-l înainte să atingi CSS.
Estetica e **oțel pe hârtie** (redesign 2026-08-08, handoff „Design audit complet
dashboard"): opt roluri, două seturi de valori, **un singur accent** (`#5980a6` deschis /
`#8ab2d9` întunecat). Două teme (`dark` default, `light`), ambele în tokens — dacă atingi
culori, păstrează ambele.

- **Suprafețe (elevație): DOUĂ niveluri plus o tentă.** `--bg` (pagină) < `--bg-surface`
  (card) < `--bg-elevated` (suprafață 2: câmp, chip, celulă inset). Elevația se citește din
  `--shadow-sm`/`--shadow-md`, **nu din chenare peste tot** — și nu din `backdrop-filter`,
  care a ieșit din sistem. `--bg-panel`/`--bg-input`/`--bg-overlay` sunt aliasuri.
  Text: `--text` / `--text-secondary` / `--text-dim`; **`--text-dim` e podeaua pentru text
  mic** (verificat pe FOND, nu doar pe suprafață) — `--text-faint` e alias către el.
- **Culoarea e stare, nu decor. UN accent (oțel).** `--accent` / `--accent-deep` (cerneala pe
  tentă) / `--accent-subtle` (tentă, SOLIDĂ) / `--accent-text` (cerneala pe fill). Restul:
  `--danger` + `--danger-deep`, `--success` + `--success-deep`. **Text pe o tentă ia
  întotdeauna varianta `-deep`, niciodată culoarea plină.** `--warning`, `--info`,
  `--purple`, `--service-*` sunt aliasuri — nu introduce o a treia stare.
  Pe rândurile de task culoarea e rezervată **severității** (inelul bifei + textul
  termenului, amândouă din `--ring`, pus cu `dueRing()`). **Muchia colorată de 3px nu mai
  există nicăieri.**
- **Identitatea proiectului NU se mai codează cromatic în Calendar** (11 din 12 perioade
  sunt la același client, deci nu selecta nimic): forma spune faza, textura spune locul,
  numele lucrării scrie în bară. `lib/culori.js` + `solve_paleta.py` rămân pentru
  Planificator; `--loc-site`/`--loc-sediu` sunt aliasuri neutre — **locul se scrie**.
- **Mișcare — trei durate, două curbe:** `--dur-press` 90 (apăsare, `--press-scale` .965) ·
  `--dur-base` 220 (element) · `--dur-slow` 280 (suprafață). `--dur-fast` 120 e VOPSEA
  (hover/culoare), nu e în scara de mișcare. `--ease` peste tot; `--ease-spring` doar unde
  ceva urmărește degetul. NU `transition: all` — `--transition-colors` sau
  `--transition-pressable`.
  Doar `transform`/`opacity` pe animații; ieșirea/intrarea rândurilor: `plecare`/`sosire`
  din `lib/motion.svelte.js` (`sosire` cu `|local`). Reduced-motion e global.
- **Apăsare:** pe pointer grosier există podeaua globală de `:active` din `global.css`
  (`:where()`, specificitate zero). Control nou = dă-i `:active`. Ținte touch: `--tap-min` 44px.
- **Componente — folosește librăria `components/ui/`, nu reinventa:** `<Input>`/`<Textarea>`
  (NU `<input>` brut în formulare), `<Select>` (NU `<select>` nativ), `<DatePicker>`
  (NU `type="date"`), `<Modal>`/`<ConfirmDialog>`, `<Toast>`, `<EmptyState>`,
  `<ErrorState>` (cu retry; `marime="sectiune"` pentru o bucată căzută, ca să nu golească
  pagina), `<Skeleton>` (DOAR prima încărcare: gardă `loading && items.length === 0`;
  `varianta="rand"` are forma rândului real), `<SelectorZi>` (Azi · Mâine · Alege +
  Scoate — oriunde se replanifică ceva). Butoanele modalului în
  `{#snippet footer()}` cu `.modal-actions`.
- **Iconițe:** `<SolidIcon>` pentru navigație/feature (solid); Lucide outline pentru
  afordanțe mici (plus, chevron, search, x). Zero emoji în UI.
- **Tipografie — cinci trepte, DOUĂ familii.** Scara: `--font-title` 25 · `--font-h2` 21 ·
  `--font-h3` = `--font-body` 15 · `--font-small` 13 · `--font-label` 12 (DOAR etichete
  majuscule, 600, `--tracking-label` .05em). În plus: `--font-control` 13/600 (control în
  rând) și `--font-brand` 18/600 (marca — singura treaptă din afara scării, fiindcă e
  logotip). **Nu se introduce 14px nicăieri.** Pe telefon **cresc** `--font-title` (→28) și
  `--font-body` (→16); rândul de listă rămâne 15.
  Familii: **Gabarito** = tot textul (titlu și corp, deosebite de mărime și greutate);
  **DM Mono** = cifre care se compară pe verticală. Regula se verifică singură: *dacă
  textul se poate traduce, nu e mono*. Tracking: `--tracking-tight/-normal/-label`. Line-height:
  `--lh-tight/snug/normal/relaxed`. Greutăți: 400/500/600 (`--fw-bold` nu mai există).
  **Nimic scris de mână** — `font-size` în `rem`/`px`, `letter-spacing` sau
  `line-height` în afara `tokens.css` sunt abateri, prinse de `audit_design.py`.
  Numărătorile folosesc `.count` din global.css (+`.accent`/`.danger`), nu o pastilă
  nouă per pagină. Titlurile au podeaua `--lh-tight` din global.css.
- **Înainte de commit:** `python scripts/audit_design.py` — singurul test care prinde
  incoerența (build-ul și smoke trec vesel peste o a doua paletă copiată).

## Known Limitations

- CSP uses `unsafe-inline` — migrating to nonce requires refactoring all onclick handlers
- UPLOAD_FOLDER not configurable via env var (hardcoded in utils.py)
- Status values are magic strings (e.g. `'in_lucru'`, `'finalizat'`) — centralized in labels.py but not enforced at DB level
- CDN dependencies (jsdelivr, cdnjs) — SRI hashes added but no local fallback for all
- No formal test framework (pytest) — scripts/ has ad-hoc tests
