# 2026-11-22 Lista ascunsa `sistem`: taskurile sistemului nu ajung in Torqa

Ion: „nu vreau sa-mi poluezi Today sau task-urile cu ceea ce e din system. Lasa sa ramana acolo [in System]." Coada lui Claude
(„Claude: X" -> „Claude lucreaza/gata/esuat: X"), amanarile „Revin: rezultatul lui Claude «...»" facute de Tomorrow pe un rezultat
si „Claude: executa A-NNN" erau taskuri globale in `sfera = 'munca'`, deci Torqa le punea in Astazi si in listele lui. Ele raman
vizibile doar in pagina System, prin firul asistentului (`/api/asistent`) si vederea sistemului (`/api/sistem`). Aici e partea de
server; scrierea in `sistem` o fac scripturile din Knowledge (`tools/coada.py`, `tools/asistent/atentie.py`).

- **Constanta, nu rand si nu migrare.** `database.LISTA_SISTEM = 'sistem'`. `global_tasks.sfera` nu e cheie straina (decizia
  2026-10-26-liste.md), deci niciun rand nu e de pus la loc dupa un restore, schema ramane v47 si `liste` ramane exact ce vede Ion.
  Un rand in `liste` ar fi cerut o migrare, un `INSERT OR IGNORE` la fiecare pornire si un filtru in fiecare citire a tabelei, ca
  sa nu apara in Torqa; constanta cere doar filtrul.
- **Ce accepta.** `_sfera_valida` o primeste (creare, `PUT`, `?sfera=sistem`); mesajul 400 al unei sfere necunoscute o enumera la
  sfarsit. `?sfera=toate` intoarce in continuare tot, ca scripturile (coada, atentie, agenda din vault-mcp) sa-si gaseasca taskurile.
  Fara parametru raspunsul ramane doar `munca`.
- **Ce nu intoarce.** `GET /api/sync/snapshot`: taskurile de sistem, subtaskurile lor (`task_subtasks.task_id` din ele) si, oricum,
  lista (nu e in `liste`; si daca un rand `sistem` ar ajunge acolo de mana, `citeste_liste` il filtreaza). `GET /api/liste` si
  `deschise` la fel. `/api/calendar` citea deja doar `sfera = 'munca'` (`blueprints/admin.py`). `/api/stats` numara proiecte.
  `echipa`, `asistent`, `sistem`, `materiale`, `outlook` nu citesc `global_tasks`.
- **Lista nu e a lui Ion.** `POST /api/liste` cu id `sistem` = 400 (id rezervat); `PUT` si `DELETE /api/liste/sistem` = 403;
  `PUT /api/liste/ordine` cu `sistem` in `ids` = 400.
- **Un task intra in `sistem` si nu mai iese.** Un `PUT` cu alta sfera pe un task care e in `sistem` primeste 409 (corpul spune
  `sfera: "sistem"`), cu orice token si cu sesiunea. De ce: Torqa trimite `sfera` intr-un `PUT` doar cand Ion muta taskul intre liste
  (`pif-sync-adapter.service.ts` `_buildTaskBody`) sau cand reia o creare al carei raspuns s-a pierdut (`pif-outbox.service.ts`,
  calea `exists`), dar un task care i-a ramas pe telefon pana la urmatoarea citire si pe care il muta in acel interval l-ar aduce
  inapoi in Astazi. Tokenul nu ajuta: dialogul de conectare al Torqa primeste orice Bearer scris de mana
  (`pif-connect-dialog.component.ts`; comitul 27dbb043 a trebuit sa accepte mesaje ale lui Ion trimise cu tokenul de masina), iar
  Torqa web nu trimite niciun Bearer, ci cookie-ul sesiunii cu PIN (`pif-api.service.ts`). Nimeni nu are nevoie sa scoata un
  task din `sistem`: `revino` (memento-ul lui Ion) nu trece prin `sistem`. Daca vreodata va trebui, se adauga un antet aditiv, nu se
  slabeste regula. Aceeasi valoare (`sistem`) sau lipsa campului trec.
- **Ce vede Ion cand un task existent dispare din snapshot.** Torqa il trateaza ca sters pe server si il sterge local, cu o notificare
  pe fiecare („Remote issue was deleted...", fara actiune); daca taskul are timp inregistrat, cere confirmare (`pif-remote-deletion.service.ts`).
  Deci la prima citire dupa ce scriptul de migrare muta taskurile deschise, Ion primeste cate o notificare pe task.
- **Retry.** `PUT` cu `sfera: 'sistem'` e idempotent (aceeasi valoare). Un `POST` cu `id` repetat primeste 409 ca pana acum.
- **Teste.** `teste/test_lista_sistem.py` (19: sfera, snapshot cu subtaskuri, calendar, `deschise`, regula „nu iese", lista rezervata).
