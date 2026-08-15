# 2026-08-14 — „Apare scheletul?" era INTREBAREA GRESITA

- **2026-08-14 (5) — „Apare scheletul?" era INTREBAREA GRESITA.** Dupa ce
  scheletele au disparut (vezi turul 4), Ion a raportat mai departe: „tot vad
  schelete sau niste ramasite mai intai apoi apare rapid pagina." Avea dreptate,
  si ce vedea nu era un schelet: era **RAMA paginii noi fara continut**.
  Masurat pe telefon, la atingerea tabului Planificator: titlul si bara la 221ms,
  randurile abia la 295 — 74ms de pagina goala cu antet.
  - Cauza: `pregateste()` incalzea raspunsul la hover, dar **nimeni nu-l citea la
    montare**. `preia` cu prospetime 0 cere INTOTDEAUNA de la server, iar
    `loadPlan`/`loadProjects`/`loadGlobalTasks` randau cu store-ul gol si abia
    apoi il umpleau. Pentru Calendar/ProjectDetail/Departament scrisesem seedul
    sincron din `dinCache`; pentru cele trei liste, nu.
  - Acum toate trei se seedeaza SINCRON din `dinCache` inainte de primul cadru.
    Nu au nevoie de garda „doar la montare" ca Calendar: cache-ul lor e sters de
    fiecare scriere, deci ce se gaseste acolo e prin constructie starea de dupa
    ultima scriere.
  - **Scrierile pe taskuri invalideaza si `/api/plan`.** Usor de uitat: mutarile
    din Planificator cheama `updateTask` si apoi `loadPlan()`, care de acum se
    seedeaza sincron — fara invalidare, bara trasa cu degetul ar clipi inapoi in
    pozitia veche exact cand ridici degetul. Taskurile de proiect nu-si stiu
    proiectul in `updateTask`, deci acolo prefixul e cel larg (`/api/proiecte`).
  - **Contractul nou, verificabil:** intre pagina veche si cea noua se perinda
    exact DOUA stari vizuale. Orice a treia e o ramasita, indiferent cum se
    numeste clasa ei. `audit_navigare.py` sectiunea 8 il masoara pe cadre.
