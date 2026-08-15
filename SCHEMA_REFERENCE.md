# Contract de integrare — PIF Dashboard

Pentru cine scrie ceva ce vorbeste cu API-ul din afara aplicatiei (Cowork, skill-uri
din vault, scripturi).

**Schema NU se mai scrie aici.** Sursa unica e `docs/memory/DB_MAP.md`, generat de
`scripts/gen_memory.py` prin PRAGMA pe o baza construita pe loc — deci nu poate ramane
in urma. Rutele: `docs/memory/API_MAP.md`, generat din decoratori. Ambele se
regenereaza la fiecare commit care atinge cod Python (`.githooks/pre-commit`).

Fisierul asta pastreaza doar ce nu se poate genera: regulile de scriere.

## Autentificare

| cine | cum |
|---|---|
| masina (Cowork, `pif-sync.py`, scripturi) | `Authorization: Bearer $PIF_API_TOKEN` — scutit de CSRF |
| browser | cookie de sesiune + `X-CSRF-Token` (valoarea cookie-ului `csrf_token`) |

Rate limit: 60 cereri/minut per IP pe `/api/*`.

## Reguli de scriere

1. **Actualizarea e `PUT`, niciodata `PATCH`.** Nu exista handler PATCH.
2. **Toate scrierile JSON trec prin `get_json_or_400()`**, care normalizeaza datele
   (`utils.norm_date`): accepta ISO si formatele romanesti (`23.02.2026`, `5/3/2026`),
   respinge cu 400 orice altceva. O data pe care baza n-o poate citi nu intra.
3. **`observatii` e HTML**, nu markdown si nu text simplu (o scrie editorul din UI).
4. **Statusuri.** Proiect: `pregatire` | `finalizat`. Task: `to_do` | `done`. Cheile
   vechi (`in_lucru`, `blocat`, …) sunt mapate DOAR la citire, ca un rand nemigrat sa
   nu apara brut; nu le scrie.
5. **`data_finalizare` exista daca si numai daca statusul e `finalizat`.** Serverul o
   pune singur la inchidere si o STERGE la redeschidere — nu o trimite pe cont propriu
   decat cand corectezi ziua unei lucrari inchise mai tarziu.
6. **`implementari.faza` (`pregatire`|`implementare`) e independenta de `locatie`**
   (`site`|`sediu`). Sunt doua fapte, nu unul cu doua nume.
7. **`implementari.confirmata` e raspunsul „s-a facut" pentru PERIOADA.** Nu atinge
   statusul proiectului cand confirmi o deplasare.
8. **`sfera`** (`munca`|`personal`) pe `global_tasks` e opt-in la citire: implicit,
   listele intorc doar `munca`. O valoare necunoscuta da 400, nu se corecteaza tacit.

## Import de debrief — `POST /api/import/debrief`

**Scrie efectiv doar doua lucruri: `client{}` si `proiect{}`.** Verificat in
`blueprints/projects.py:864-1080` — nu exista niciun `INSERT INTO tasks` acolo.

- `meta.debrief_id` face importul idempotent (reimportul aceluiasi debrief intoarce
  proiectul existent, nu-l dubleaza).
- **`tasks[]` se pierde in tacere.** E acceptat de JSON, dar nimic nu-l scrie si nu
  apare in `sumar`. Daca debrief-ul are taskuri, trimite-le separat, dupa import, cu
  `POST /api/proiecte/<id>/tasks`.
- `jurnal[]` se **plieaza in** `observatii` (PIF) / `service_after` (Service) —
  tabela de jurnal a plecat in v22.
- `echipamente[]` e **ignorat** din v28, dar numarat in `sumar.echipamente_ignorate`
  — asta e comportamentul corect: vizibil, nu inghitit.
- `ore[]` ignorat din v22 (orele se ponteaza in e100).
- **Nu exista** `checklist_items[]`, `params_json`, `ore_total_secunde`.

**Doua coloane pe care importul NU le scrie, desi exista:**

- **`data_finalizare`** — deci un debrief cu `status: 'finalizat'` creeaza un proiect
  care incalca invariantul de la punctul 5: inchis, dar fara data inchiderii. Efect
  concret: taierea perioadelor la citire cade pe `date('now')`, adica lucrarea
  ramane in Calendar pana azi in loc sa se opreasca in ziua inchiderii.
- **`vault_folder`** — legatura cu `wiki/job/projects/<client>/<slug>/` nu se face.

Pana cand importul le acopera, dupa un import cu status `finalizat` trimite un
`PUT /api/proiecte/<id>` cu `data_finalizare` si `vault_folder`.

## Export — `GET /api/proiecte/<id>/snapshot`

Intoarce `meta`, `client`, `proiect{}`, `tasks[]` (cu `subtasks[]`), `calcule[]`.
**Nu** intoarce echipamente, checklist, jurnal, ore sau perioade — pentru perioade
cere `GET /api/proiecte/<id>/implementari`.

## Sincronizarea cu vault-ul

`Knowledge/tools/pif-sync.py`: `list · status [slug] · create <slug> · push [slug] ·
pull <slug> · push-obs <slug> <fisier.md> · link [slug]`.

Cheia de legatura e `dashboard_id` din frontmatter-ul lui
`wiki/job/projects/<client>/<slug>/README.md`; `SYNC_KEYS = ('status',)` — se
sincronizeaza doar statusul. In sens invers, serverul scrie frontmatter in vault si
comite (`blueprints/obsidian.py`).

## Ce nu mai exista

Ca sa nu reapara in cod scris de un agent care a citit un document vechi: `deadline`,
`prioritate`, `pm`, `nr_contract`, `data_incepere`, `notify_on_deadline`, timer/ore,
tabelele `jurnal`, `checklist_pif`, `echipamente`, `atasamente`, `parametri_master`,
`fault_codes`, `project_templates`, ruta `GET /api/dashboard/home`, Gantt-ul de
proiect si `gantt.pdf`, tabul Calcule, `static/app.js`, `static/core.js`,
integrarea Google Calendar.
