# Trei campuri scoase din formularul de proiect (v36, 2026-07-30)

## Din CLAUDE.md

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

## Din MEMORY.md

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
