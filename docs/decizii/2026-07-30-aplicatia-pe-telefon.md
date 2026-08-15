# 2026-07-30 — Aplicatia pe telefon: „fara compromisuri"

- **2026-07-30 (4) — Aplicatia pe telefon: „fara compromisuri".** Ion: „vreau sa faci aplicatia
  maxim de comoda pentru mobil". Auditat automat fiecare ruta la 375×812 si 360×740 (overflow,
  tinte sub 44px, inputuri care declanseaza zoom pe iOS, continut taiat). Ce s-a schimbat:
  **(1) Headerul „sticky" nu se lipise NICIODATA.** `.app-main` avea `overflow: hidden`, ceea ce
  face din el un container de derulare, iar `position: sticky` dinauntru se raporteaza la
  scrollportul LUI (care nu deruleaza). Verificat: derulezi 400px, headerul pleaca cu 400px.
  `overflow-x: clip` taie la fel pe orizontala fara sa creeze container de derulare.
  **(2) Modalele si DatePicker-ul = sheet de jos pe telefon** (≤768px), cu blocarea derularii
  paginii de dedesubt (contor comun intre instante) si tranzitie `translateY(100%)` — nu `fly`,
  care ar avea nevoie de o distanta in px si arata altfel pe un sheet scund fata de unul inalt.
  Zilele din DatePicker: 34px → 45px.
  **(3) `input`/`select`/`textarea` la minim 16px pe telefon** (`!important`, ca la
  `input[type=date]`): sub 16px Safari mareste pagina la focus si NU o micsoreaza inapoi.
  **(4) Tinte de atingere la 44px** peste tot. Unde marimea vizibila conteaza (pastila de status
  din cardul de proiect, steaua din Calculator) creste doar suprafata, printr-un `::after`
  absolut — casetele cresc, semnele nu.
  **(5) Calendar: plasare prin ATINGERE.** Drag-and-drop-ul HTML5 nu se declanseaza la deget,
  deci „Proiecte fara perioada" NU se putea planifica deloc de pe telefon. Acum: alegi proiectul
  (se aprinde), atingi ziua (toate zilele devin tinte punctate), Escape/re-atingere renunta.
  Nu un al doilea calendar peste calendar — acelasi gest, rupt in doua atingeri. Benzile devin
  `pointer-events: none` sub 620px: aveau 12px si furau atingerea celulei de ~50×70.
  **(6) `/plan` se derula LATERAL pe telefon:** `.controls` avea 502px intr-un ecran de 375 si,
  nefiind `flex-wrap`, impingea toata pagina.
  **(7) Tabelele din wiki erau TAIATE** pe telefon (ultima coloana, fara nicio cale spre ea) —
  `display: block` + `overflow-x: auto` doar sub 768px; pe desktop raman `width: 100%`.
  **Capcane:** o regula globala `@media (hover: none) { *:hover { transform: none } }` ar fi
  anulat si `translateX(-50%)` al dock-ului (hover-ul urca la stramosi) — hover-urile care MISCA
  sunt gardate individual cu `@media (hover: hover)`; bara editorului de text NU poate deveni
  scroller orizontal (meniul de stil e pozitionat absolut si ar fi taiat) — doar butoane mai mari;
  `flex: 1 1 auto` pe titlul randului din „Astazi" tot rupea randul, fiindca latimea DORITA intra
  in calculul de wrap — trebuie `flex: 1 1 0` plus un invelis `display: contents` care pe telefon
  devine linia a doua (altfel randul iesea pe trei linii, 172px/task).
  Verificat: `smoke_ui.py` OK pe desktop si mobil, `test_suite.py` 12/12, zero erori de consola,
  desktopul neschimbat (swimlane, dock 50px, randuri pe o linie).
