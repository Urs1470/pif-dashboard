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

SQLite file: `pif_dashboard.db` (gitignored). 9 tables, 34 migrations (idempotent).

**Core tables:** proiecte, tasks, task_subtasks (FK CASCADE), task_dependencies, global_tasks, implementari, clienti

**Specialized:** app_settings (KV store), schema_version

**Migrations:** `database.py` — `run_migrations()` chains v1 through v34. Each is idempotent. Auto-runs on first request via `before_request`. (v20 dropped Budget Tracker; v22 dropped timer & jurnal — orele se ponteaza in e100, jurnalul se scrie in observatii; v23 dropped Checklist PIF + Project Templates + Hermes AI — cod mort, zero UI; **v28 dropped parametri_master, fault_codes, echipamente, atasamente** — restrangere de scop la organizare/monitorizare de proiecte, vezi mai jos.)

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

Severitatea unui task se citeste acum din **termen**, nu din prioritate: `dueColor()` in
`formatters.js` da rosu pentru depasit, amber pentru azi, warning pentru urmatoarele doua
zile. Bordura din stanga randului o foloseste. Sortarea din exportul .md merge tot pe termen.

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
bateau — severitatea (bordura + termenul), mov (categoria), amber (subtaskuri,
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

> See `HERMES.md` (architecture + design system + git protocol) and `AGENT_BRIEFING.md` (spawn template) for the full multi-agent workflow.

## Known Limitations

- CSP uses `unsafe-inline` — migrating to nonce requires refactoring all onclick handlers
- UPLOAD_FOLDER not configurable via env var (hardcoded in utils.py)
- Status values are magic strings (e.g. `'in_lucru'`, `'finalizat'`) — centralized in labels.py but not enforced at DB level
- CDN dependencies (jsdelivr, cdnjs) — SRI hashes added but no local fallback for all
- No formal test framework (pytest) — scripts/ has ad-hoc tests
