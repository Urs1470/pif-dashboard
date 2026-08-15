# MEMORY — PIF Dashboard

Index, nu jurnal. Citeste asta in loc sa re-explorezi codul; deschide restul doar cand
ai nevoie.

**Ce se genereaza singur** (`python scripts/gen_memory.py`, si automat la commit prin
`.githooks/pre-commit`) — ele sunt mereu adevarate, spre deosebire de orice scrii de mana:

| fisier | ce contine |
|---|---|
| `DB_MAP.md` | schema reala, citita cu PRAGMA dintr-o baza construita pe loc |
| `API_MAP.md` | toate rutele Flask (metoda, cale, handler, linie) |
| `CODE_MAP.md` | functiile top-level per modul Python + service-worker |

**Ce e scris de mana, si unde:** `CLAUDE.md` (regulile de sesiune), `SCHEMA_REFERENCE.md`
(contractul de scriere pe API), `docs/decizii/INDEX.md` (de ce am facut asa).

## Harta datelor

| domeniu | tabele |
|---|---|
| Proiecte | `proiecte`, `clienti`, `implementari` (perioadele) |
| Taskuri | `tasks`, `task_subtasks`, `global_tasks` |
| Fosile | `task_dependencies` (Gantt, fara cititor), `calcule` (vie doar prin `/snapshot`) |
| Sistem | `app_settings` (KV), `schema_version` |

**Schema v40, 10 tabele.** Migrarile stau in `database.py` (`run_migrations()`), sunt
idempotente si ruleaza la prima cerere. Coloanele exacte: `DB_MAP.md`.

> **Ce s-a sters nu se reinvie.** v28 a scos `parametri_master`, `fault_codes`,
> `echipamente`, `atasamente`; v22 timerul si jurnalul; v23 checklistul si template-urile;
> v30 deadline-ul; v33 `data_planificata`; v34 prioritatea; v36 `pm`/`nr_contract`/
> `data_incepere`. **Nu adauga self-heal pentru ele** — un self-heal le readuce la fiecare
> pornire, capcana care a fost lovita de cinci ori. Functiile istorice de migrare inca le
> creeaza pe drumul spre v40; e intentionat si idempotent.
> Datele: `raw/pif-dashboard/2026-07-27-inainte-de-v28/` in vault.

## Stare (verificat 2026-08-15)

- **Pagini:** Acasa, Proiecte, Proiect (taburi Taskuri · Perioade · Wiki), Taskuri,
  Planificator, Calendar, Departament, Calculator (+ build public `/calc`).
- **Verificatoare:** `audit_design` curat, `test_suite` 44/0 cu server pe o copie a bazei.
- **Cei 7 invarianti de produs** (in `CLAUDE.md`) sunt respectati in cod — verificati unul
  cate unul. Singura slabiciune: statusul nu e validat pe server.
- **Fara consumator in SPA:** rutele `calcule` ×3, `/api/proiecte/batch` (are si un bug — la
  stergere uita `implementari`), `/api/export/ics-key` (ruta; helperul e viu), `/login-hash`,
  `/api/obsidian/config` ×2. **`/api/stats` NU e moarta** — o citeste Cowork.
- **Android „Torqa"** (Capacitor, `org.iupif.pif`): WebView peste site-ul live, notificari
  native + alarma de plecare pe teren. `frontend/android/`, `scripts/build-apk.ps1`.

## Capcane

- **`static/dist/` E versionat** si trebuie sa fie: webhook-ul face `git reset --hard` pe
  server, fara npm. De aceea `.githooks/pre-commit` cere bump la `VERSION` in
  `static/service-worker.js` la orice schimbare de dist — altfel build-ul nou nu ajunge pe
  telefon. Costul: `git status` e ~95% zgomot de dist; filtreaza cu
  `git status -- . ':!static/dist'`.
- **Un fisier de context nu declanseaza poarta.** `gate.py` isi calculeaza semnatura doar pe
  fisierele care mapeaza la un verificator; o retusare in `CLAUDE.md` nu mai reruleaza
  build + smoke + audit_mobil. Supapa: `PIF_GATE=skip` (o si anunta in context).
- **`python3` pe Windows e stubul din Microsoft Store** — exista in PATH, iese cu 49.
  Scripturile care aleg interpretorul trebuie sa-l PROBEZE, nu sa-l ia dupa nume.
- **Importul de debrief** scrie client + proiect + `tasks[]`, pune singur `data_finalizare`
  cand statusul e `finalizat` si accepta `vault_folder`. Reparat pe 2026-08-15: pana atunci
  `tasks[]` era acceptat si nu-l scria nimic. Detalii: `SCHEMA_REFERENCE.md`.
- **CSRF:** clientul citeste cookie-ul `csrf_token` si-l trimite ca `X-CSRF-Token`. Scutite:
  GET/HEAD/OPTIONS, `/webhook/*`, si cererile cu Bearer.
- **Taskurile recurente** (zilnic/saptamanal/lunar) isi nasc urmatoarea instanta la bifare —
  orice atingere a logicii de bifare trebuie sa pastreze asta.
- **Cache-busting** e automat (SHA256 `?v=` prin context processor); nu umbla la versiuni.
- **Multi-sesiune:** `git fetch && git pull --rebase` inainte de push, niciodata force-push.
  Arborele e partajat, deci si indexul git — vezi `CLAUDE.md`.

## Protocol

1. Porneste de aici + `DB_MAP`/`API_MAP`/`CODE_MAP`. Nu scana blueprints la intamplare.
2. Hartile se regenereaza la commit. Activeaza hook-ul o data per clona:
   `git config core.hooksPath .githooks`.
3. **O decizie noua se scrie in `docs/decizii/`**, un fisier per decizie, plus un rand in
   `INDEX.md`. NU aici: fisierul asta e index, si un index care creste devine jurnal — a
   fost 187 KB si nimeni nu l-a citit vreodata integral.
4. **Regulile complete de memorie**, cu defectul masurat care a produs fiecare regula:
   `Knowledge/references/memorie-standard.md`. Cele care se aplica cel mai des aici:
   *ce se poate genera se genereaza, iar generatorul citeste sursa care EXECUTA, nu
   descrierea ei* · *fisierul incarcat mereu nu primeste niciodata o intrare datata* ·
   *un fapt, un loc* · *verifica pe codul care ruleaza* · *absenta tacuta e cel mai rau
   mod de esec* · *ce e verificat ramane adevarat*.

## Ultimele decizii

Arhiva completa, cu carlig per decizie: **`docs/decizii/INDEX.md`** (105 intrari).

- [2026-08-15 Poarta alegea un python care nu e python](../decizii/INDEX.md)
- [2026-08-15 Schema se genereaza din baza](../decizii/INDEX.md)
- [2026-08-15 Sfera se comuta cu degetul pe toata pagina](../decizii/2026-08-15-sfera-gest-toata-pagina.md)
- [2026-08-15 Perioada e o sina la baza randului](../decizii/INDEX.md)
- [2026-08-15 Contorul de pasi se intoarce pe rand](../decizii/INDEX.md)
- [2026-08-08 Redesign: otel, Gabarito, o singura axa de culoare](../decizii/INDEX.md)
- [2026-08-07 „S-a facut" e despre PERIOADA, nu despre proiect (v39)](../decizii/INDEX.md)
- [2026-07-30 Un proiect inchis se opreste in ziua inchiderii (v35)](../decizii/INDEX.md)
- [2026-07-27 Restrangere de scop (v28)](../decizii/INDEX.md)
- [2026-07-27 Un task are O SINGURA data (v33)](../decizii/INDEX.md)
