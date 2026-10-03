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

**Schema v41, 10 tabele.** Migrarile stau in `database.py` (`run_migrations()`), sunt
idempotente si ruleaza la prima cerere. Coloanele exacte: `DB_MAP.md`.

> **Ce s-a sters nu se reinvie.** v28 a scos `parametri_master`, `fault_codes`,
> `echipamente`, `atasamente`; v22 timerul si jurnalul; v23 checklistul si template-urile;
> v30 deadline-ul; v33 `data_planificata`; v34 prioritatea; v36 `pm`/`nr_contract`/
> `data_incepere`. **Nu adauga self-heal pentru ele** — un self-heal le readuce la fiecare
> pornire, capcana care a fost lovita de cinci ori. Functiile istorice de migrare inca le
> creeaza pe drumul spre v40; e intentionat si idempotent.
> Datele: `raw/pif-dashboard/2026-07-27-inainte-de-v28/` in vault.

## Stare

- **Serverul e backend-ul Torqa (2026-10-03):** API-ul `/api/*`, loginul cu PIN, Torqa web la
  `/torqa/` (build Angular urcat, nu din git) si `/service-worker.js` (worker care se retrage
  singur). `/` duce la `/torqa/`. Interfata veche — SPA-ul Svelte (Acasa, Proiecte, Proiect,
  Taskuri, Calendar, Departament, Calculator + `/calc`), notificarile push, planul de departament
  si aplicatia Android `org.iupif.pif` — a plecat; baza nu s-a atins. Ce s-a scos, ce a ramas si
  cum se aduce inapoi: `docs/decizii/2026-10-03-retragerea-interfetei-vechi.md`; starea de
  dinainte e eticheta git `inainte-de-retragere`.
- **Verificatoare:** `python scripts/verifica.py` — lint, `teste/js` (node), `teste/` (unittest),
  `test_suite` (probe de API pe un server de unica folosinta). Fara browser, fara build.
- **Cei 7 invarianti de produs** (in `CLAUDE.md`) sunt respectati in cod — verificati unul
  cate unul pe 2026-08-15. Singura slabiciune: statusul nu e validat pe server.
- **Rutele fara consumator** gasite la verificare au fost scoase: `calcule` ×3,
  `/api/proiecte/batch`, `/login-hash` si `/api/obsidian/config` ×2 in `97a5c791` (2026-08-15),
  `/api/export/ics-key` in `847327ee` (2026-08-27). **`/api/stats` NU e moarta** — o citeste Cowork.
  La retragerea din 2026-10-03 au plecat rutele interfetei vechi (push ×9, plan-departament ×2,
  `/api/me`, `/calc`, `/docs`, fisierele SPA-ului), iar la curatenia de dupa ea (aceeasi zi) cele ramase
  fara apelant — nici in Torqa, nici in unelte, nici intr-un pas de skill: `/api/clienti*` ×5,
  `/api/agenda/*` ×3, `/api/search`, `/api/export/pdf` si cele doua previzualizari de import, care erau
  si FARA LOGIN (`docs/decizii/2026-10-03-curatenie-dupa-retragere.md`). Au ramas `/api/stats`,
  `/api/import/debrief`, `/api/obsidian/vault-key` si `vault-sync`, sanatatea. Tabela `clienti` ramane
  (o scrie importul de debrief, o citeste snapshotul), la fel `ordine_agenda` pe taskuri.
- **Android:** `org.iupif.torqa` (Torqa nativ, build propriu din Super Productivity) are canalul de
  APK `torqa`. `org.iupif.pif` (WebView peste site) a fost retrasa; canalul `pif` din
  `blueprints/app_update.py` ramane servit.

## Capcane

- **`/service-worker.js` trebuie sa ramana.** Serveste worker-ul care se retrage singur: un
  fisier sters ar da 404 la verificarea de actualizare, iar browserele care au instalat interfata
  veche ar pastra worker-ul ei si shell-ul din cache. Fara handler de `fetch` si fara `ngsw:`
  (cache-urile Torqa web). Fisierul poate pleca abia cand nu mai are cine sa-l ceara.
- **Un `git checkout inainte-de-retragere -- <cale>` aduce o bucata, nu interfata.** SPA-ul, push-ul
  si `/calc` se tin de rute, CSP, cheile din `app_settings` si hook-ul de pre-commit; restaurarea
  intreaga e un `git revert` al retragerii (pasii in decizia din 2026-10-03).
- **Un fisier de context nu declanseaza poarta.** `gate.py` isi calculeaza semnatura doar pe
  fisierele care mapeaza la un verificator; o retusare in `CLAUDE.md` nu mai reruleaza
  testele. Supapa: `PIF_GATE=skip` (o si anunta in context).
- **`python3` pe Windows e stubul din Microsoft Store** — exista in PATH, iese cu 49.
  Scripturile care aleg interpretorul trebuie sa-l PROBEZE, nu sa-l ia dupa nume.
- **Importul de debrief** scrie client + proiect + `tasks[]`, pune singur `data_finalizare`
  cand statusul e `finalizat` si accepta `vault_folder`. Reparat pe 2026-08-15: pana atunci
  `tasks[]` era acceptat si nu-l scria nimic. Detalii: `SCHEMA_REFERENCE.md`.
- **CSRF:** clientul citeste cookie-ul `csrf_token` si-l trimite ca `X-CSRF-Token`. Scutite:
  GET/HEAD/OPTIONS, `/webhook/*`, si cererile cu Bearer (plus endpointul `push.push_action`, mort
  din 2026-10-03: `csrf.py` n-a fost atins).
- **Taskurile recurente** (zilnic/saptamanal/lunar) isi nasc urmatoarea instanta la bifare —
  orice atingere a logicii de bifare trebuie sa pastreze asta.
- **Cache-busting** pentru pagina de login: `static/login.css?v=<SHA256>` prin context
  processor (`style_version`); nu umbla la versiuni. Torqa web isi are cache-ul lui (`ngsw:`).
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

Arhiva completa, cu carlig per decizie: **`docs/decizii/INDEX.md`**.

- [2026-10-03 Retragerea interfetei vechi](../decizii/2026-10-03-retragerea-interfetei-vechi.md)
- [2026-10-01 Torqa web pe acelasi server si canal propriu pentru APK](../decizii/2026-10-01-torqa-web-si-canalul-apk.md)
- [2026-10-01 Torqa: imaginea completa si tokenul de dispozitiv](../decizii/2026-10-01-torqa-imagine-si-token-dispozitiv.md)
- [2026-09-28 Verificatoarele: un banc, trei trepte, teste unitare](../decizii/2026-09-28-verificatoarele-un-banc-si-trei-trepte.md)
- [2026-09-28 Sugestii de proiect; proiectul inchis trimite ce adaugi dupa](../decizii/2026-09-28-sugestii-proiect-si-proiectul-inchis.md)
- [2026-08-08 Redesign: otel, Gabarito, o singura axa de culoare](../decizii/INDEX.md)
- [2026-08-07 „S-a facut" e despre PERIOADA, nu despre proiect (v39)](../decizii/INDEX.md)
- [2026-07-30 Un proiect inchis se opreste in ziua inchiderii (v35)](../decizii/INDEX.md)
- [2026-07-27 Restrangere de scop (v28)](../decizii/INDEX.md)
- [2026-07-27 Un task are O SINGURA data (v33)](../decizii/INDEX.md)
