# Proprietatea suprafetelor de planificare (2026-07-27)

Fiecare vedere generala detine un singur obiect; pagina proiectului le detine pe ale ei:

- **Calendar** = perioadele (deplasarile). Se creeaza, se muta si se scot doar de aici.
  Termenele apar ca semnal, nu se editeaza.
- **Planificator** = taskurile. Benzile de perioada sunt context — click pe ele duce la
  `#/calendar?zi=AAAA-LL-ZZ`, nu deschide un editor.
- **ProjectDetail** pastreaza CRUD complet pe ambele (`ImplPeriods`, `ProjectGantt`).

Vocabular: **perioada** = interval (unde esti), **termen** = punct (pana cand). „Data" nu se
mai foloseste ca eticheta — sertarele sunt „Proiecte fara perioada" (Calendar) si „Taskuri
fara termen" (Planificator), lucruri diferite cu nume care o spun.
