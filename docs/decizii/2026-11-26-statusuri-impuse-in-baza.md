# Statusurile impuse in baza: triggere de status, schema v48 (2026-11-26, E-015)

## Problema

Pana in v47 vocabularul de status era o conventie a aplicatiei: `labels.py` il tinea, iar
`status_proiect` din `blueprints/projects.py` il verifica doar pe rutele de proiect. Taskurile
(`/api/proiecte/<id>/tasks`, `/api/tasks/<id>`, `/api/global-tasks`) primeau orice sir, un `UPDATE`
direct sau un restore dintr-un backup vechi puteau scrie orice. Limitarea era scrisa in `CLAUDE.md`
(„Limitari cunoscute”) si in backlog-ul Knowledge ca E-015.

## Ce s-a decis

- Triggere, nu CHECK. SQLite nu adauga un CHECK cu `ALTER TABLE`; reconstruirea `proiecte` si
  `tasks` ar fi atins cheile straine si cascada `ON DELETE`. Sase triggere `BEFORE INSERT` si
  `BEFORE UPDATE OF status` (`status_<tabela>_insert|update`) dau `RAISE(ABORT)` pentru orice valoare
  din afara vocabularului, inclusiv NULL, fara sa mute vreun rand.
- Vocabularul se scrie o data: `labels.PROJECT_STATUSES` (`pregatire`, `finalizat`) si
  `labels.TASK_STATUSES` (`to_do`, `done`). Triggerele, rutele, restore-ul si `DB_MAP.md` le citesc de acolo.
- Randurile existente se strang, nu se refuza: `database.impune_statusurile` (la migrarea v47->v48 si la
  fiecare pornire, dupa self-heal) duce la proiecte orice alta valoare in `pregatire` si goleste
  `data_finalizare` (invariantul 3), iar la taskuri `done`/`finalizat` in `done`, restul in `to_do`.
  Fiecare strangere apare in log (`Statusuri stranse in ...`). La fiecare pornire, fiindca o baza veche
  urcata cu `/admin/db-upload` sau o tabela reconstruita de un heal ar ramane altfel fara triggere.
- Rutele de task traduc cheile vechi din `labels.py` (`finalizat` -> `done`, `in_lucru` -> `to_do`) si
  dau 400 la o valoare necunoscuta, ca proiectele; `status: null` la creare inseamna `to_do`. Fara asta,
  triggerul ar fi transformat un status gresit intr-un 500.
- Restore-ul (`AJUSTARI_RESTORE` din `blueprints/admin.py`) strange statusul cu aceeasi regula, ca un
  backup de dinainte de v31/v34 sa se restaureze, nu sa anuleze tot restore-ul.

## Ce nu s-a atins

`stari_proiect` (jurnalul starii, alt vocabular), `implementari.faza` si `locatie` raman fara triggere:
E-015 a cerut statusurile. `blueprints/echipa.py` citeste si `anulat`, o valoare care nu mai poate
exista in baza; citirea e inofensiva.

## Verificare

`teste/test_statusuri.py` (triggerele pe o baza noua, strangerea idempotenta, 400 pe rute, restore
dintr-un backup vechi); `teste/test_backup_restore.py` foloseste acum statusuri permise in randurile de proba.
