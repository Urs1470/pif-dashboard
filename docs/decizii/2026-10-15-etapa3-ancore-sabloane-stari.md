# 2026-10-15 Etapa 3 din Torqa: taskuri ancorate de perioadă, șabloane de lucrare, starea proiectului, recurență de la finalizare (v44)

Ion a aprobat pe 2026-10-15 implementarea, inclusiv schimbarea de schemă. O singură migrare,
`migrate_v43_to_v44` (idempotentă, aditivă, fără backfill), plus forma finală în `init_db()` și
self-heal pe coloană/tabelă lipsă. Deploy-ul și migrarea pe serverul live le face Ion.

## Taskuri ancorate de perioadă

`tasks.implementare_id` (cheie străină spre `implementari`, `ON DELETE SET NULL`) și
`tasks.decalaj_zile` (zile calendaristice față de `implementari.data_start`). Invariantul 1 rămâne:
un task are O SINGURĂ dată, `data_scadenta`; ancora doar o recalculează.

- Perioada își mută `data_start` (`PUT /api/implementari/<id>`): în aceeași tranzacție, taskurile ei
  nefăcute primesc `data_scadenta = noul data_start + decalaj_zile`, fără ajustare de weekend, iar
  `updated_at` li se actualizează (Torqa le trage din imagine după el). Taskurile făcute nu se mută.
  Un start nou gol sau invalid nu mută nimic; comportamentul de azi (un `data_start` `''` suprascrie
  valoarea) rămâne cum era.
- Un `PUT /api/tasks/<id>` care schimbă `data_scadenta` fără cheia `implementare_id` desface ancora
  (a ales Ion o dată anume, ancora n-ar mai spune adevărul). Același termen trimis din nou, ca la un
  PUT cu tot taskul, nu desface nimic. Cu `implementare_id` nevid și `decalaj_zile` întreg, serverul
  verifică perioada (există, a aceluiași proiect, are start; altfel 400) și calculează el termenul,
  ignorând data trimisă în paralel. `implementare_id` null sau `''` desprinde, fără să atingă termenul.
  `POST /api/proiecte/<id>/tasks` primește aceleași două câmpuri.
- Ștergerea perioadei: SQLite acceptă `ADD COLUMN ... REFERENCES ... ON DELETE SET NULL` (implicit
  NULL, cât cere regula lui), deci cheia străină golește `implementare_id`. Ea nu atinge
  `decalaj_zile`, așa că `delete_implementare` golește ambele coloane explicit, înainte de ștergere;
  cheia străină rămâne plasă pentru orice altă ștergere.
- Copia unui task recurent NU moștenește ancora. Apariția următoare cade la o dată pe care o dă
  recurența; o copie ancorată și-ar fi mutat termenul la prima mutare a perioadei, peste ce a calculat
  recurența.
- Respins: ancora ca a doua dată pe task (rupe invariantul 1); mutarea cu delta față de vechiul start
  (derivă când un termen a fost editat); ajustare de weekend la mutare (decalajul e al lui Ion, nu
  al serverului; la recurență regula weekendului rămâne).

## Șabloane de lucrare

Tabelă `sabloane` (`id`, `nume`, `continut` JSON text, `created_at`, `updated_at`). `continut` =
`{"sare_weekend": bool, "taskuri": [{"titlu", "descriere" (opțional), "decalaj_zile", "subtaskuri": [str]}]}`;
orice altă formă e 400 cu mesaj. Rute `GET/POST /api/sabloane`, `PUT/DELETE /api/sabloane/<id>`
(în `blueprints/projects.py`, ca perioadele; fără blueprint nou). `continut` se primește și se
întoarce ca obiect. Serverul doar păstrează șablonul; aplicarea lui (taskurile create cu decalaje
față de o perioadă) o face clientul prin rutele de task cu ancoră. Intră în `VALID_TABLES` și în
backup/restore.

## Starea proiectului

Tabelă `stari_proiect`: jurnal de rânduri adăugate (`in_grafic`|`risc`|`blocat`|`asteptare`), cu
`facut`, `blocaje`, `urmator`, `data` și `implementare_id` opțional (cheie străină `ON DELETE SET
NULL`: starea rămâne, legătura cade). Fără PUT: o stare nouă se adaugă, una greșită se șterge.
`proiect_id` cu `ON DELETE CASCADE`. `GET /api/proiecte` și `/api/proiecte/<id>` adaugă
`stare_curenta` și `stare_data` (ultima după `data`, apoi `created_at`; NULL fără înregistrări).
„finalizat" NU e stare: e statusul proiectului (invariantul 2). `data` se validează în rută cu
`norm_date`, nu prin `DATE_FIELDS`, fiindcă acolo cheia ar fi verificată în orice corp JSON.

## Recurență de la finalizare

`recurenta_baza` (`scadenta`|`finalizare`, implicit `scadenta`) pe `tasks` și `global_tasks`. Cu
`finalizare`, apariția următoare se numără de la ziua serverului (Torqa trimite doar `status: done`,
nu data bifării), nu de la termenul vechi; weekendul se mută luni ca până acum. Copia păstrează
`recurenta_baza`.

`recurenta` primește de acum validare: `''`, `zilnic`, `saptamanal`, `lunar`, altfel 400 (la create
și update, taskuri de proiect și globale). Până acum orice text trecea și o valoare necunoscută
producea o copie cu aceeași dată, fără semn. Nimic din teste, fixturi sau `scripts/` nu trimitea altă
valoare (căutat înainte).

## Backup și restore

`TABELE_BACKUP` pune `implementari` înaintea lui `tasks` (cheia străină `tasks.implementare_id` cere
perioada la reinserare) și `sabloane` / `stari_proiect` după. Un backup mai vechi, fără tabelele
noi, golește tabelele noi (ca orice tabelă lipsă din fișier).

## Pe urmă

Constantele `CLAUDE.md` („schema v43, migrări v1-v43") rămân de actualizat de cine are voie să-l atingă.
