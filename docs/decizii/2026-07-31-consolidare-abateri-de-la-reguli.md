# 2026-07-31 — Consolidare UI/UX: unde s-a abatut codul de la propriile lui reguli scrise

- **2026-07-31 (4) — Consolidare UI/UX: unde s-a abatut codul de la propriile lui
  reguli scrise.** Metoda: nu „ce arata prost", ci masurat contra regulilor din
  tokens.css/CLAUDE.md/comentarii. Sapte abateri gasite si reparate, niciuna cu
  vreo eroare aruncata:
  **(1) `.sub-row` declarat de DOUA ori in Tasks.svelte** — a doua declaratie
  (ramasa de la designul de lista) anula tacut `padding: 4px 8px` al cardului
  (masurat: `3px 0` desktop, `2px 0` in foaie; card cu rama la 0px de text). Plus
  o a treia lovitura din blocul mobil. Acum o singura declaratie.
  **(2) Escape inchidea TOT, nu un strat** — redenumirea/compozitorul de subtask
  lasau evenimentul sa urce la backdrop; Select folosea doar `preventDefault`
  (care NU opreste urcarea); DatePicker asculta pe window pe BUBBLING, adica dupa
  backdrop, deci nu putea opri nimic — mutat pe CAPTURA (`onkeydowncapture`) cu
  garda `open`. Regula: Escape inchide stratul cel mai de sus, atat.
  **(3) `.trow:hover` din /tasks aplica `translateX(4px)` dar tranzitia acoperea
  doar `opacity`** — randul SAREA; pe Acasa si in proiect acelasi rand aluneca.
  **(4) Redenumirea inline a subtaskului muta textul** — inputul aducea caseta
  lui (padding+rama = salt de 7px pe x; pe telefon si fontul 14.4→16, fortat de
  regula globala de zoom Safari). Acum inputul are metricile textului de citire
  + o linie de accent; pe telefon citire=scriere=1rem (egalat IN SUS — sub 16px
  nu se poate pe input).
  **(5) Titlurile mosteneau interlinia de PARAGRAF** — tokens.css scrie
  `--lh-tight (display/headings)`, dar reset-ul nu da titlurilor line-height,
  deci h1 avea caseta 43.4px la font 28. Podea in global.css: `h1..h4
  { line-height: var(--lh-tight) }` (specificitate 0,0,1 — orice clasa o bate).
  **(6) Doua limbaje de severitate pe acelasi task** — /tasks: bordura stanga
  (cea documentata in MEMORY (8)); Astăzi + proiect: underline `::after` de 40px,
  care pe telefon nici nu se vedea (sub `.gl-fata`). Unificat pe bordura. CAPCANA:
  hover/active cu `border-color` SCURT vopseau toate laturile, adica stergeau
  exact culoarea rezervata — redeclara `border-left-color`.
  **(7) `isSoon` local zicea „<= 7 zile", dueColor zice „<= 2"** — termen la 5
  zile: bordura gri + data amber, pe acelasi rand. Trei copii locale
  (Tasks/TodayBoard/ProjectDetail) mutate in formatters.js ca
  `esteDepasit/esteAzi/esteCurand`, LANGA dueColor, pe aceleasi praguri si pe
  parsarea locala din `zilePanaLa` (nu `new Date(iso)`, care e UTC).
  **BUG functional gasit pe drum: subtaskurile din pagina de proiect nu se
  incarcau NICIODATA** — `toggleTaskExpand` chema `loadAtt()`, fosila de la
  atasamente (v28); ReferenceError in mijlocul functiei async, inghitit de
  promisiunea neascultata: chip „0/1", lista goala, consola curata. Scos apelul.
  Tot in proiect: antetul de subtaskuri spunea numarul de doua ori, bifa era
  patrat amber (cbx = selectie de lista, nu „făcut") si „sterge subtask" era
  `opacity: 0` pe touch — aliniate la /tasks.
  **Gasit si NEreparat (scop):** redenumirea inline a subtaskurilor exista doar
  in /tasks, nu si in pagina de proiect (ar fi interactiune noua, nu consolidare);
  comentariul din blocul mobil al /tasks promite o „spina" la subtaskuri care nu
  e implementata (blocul e oricum mort pe telefon — acolo se deschide foaia).
  Verificat: audit_design curat, smoke_ui 28/28, audit_mobil complet OK,
  test_suite 11/11 (+warn-ul documentat), capturi inainte/dupa la 390 si 1280.
