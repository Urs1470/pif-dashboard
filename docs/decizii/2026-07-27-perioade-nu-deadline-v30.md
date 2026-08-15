# Doua perioade, zero deadline-uri (v30, 2026-07-27)

## Din CLAUDE.md

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

## Din MEMORY.md

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
