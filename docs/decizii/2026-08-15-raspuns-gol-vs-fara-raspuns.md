# 2026-08-15 — „AVEM UN RASPUNS" nu e acelasi lucru cu „AVEM RANDURI"

- **2026-08-15 (2) — „AVEM UN RASPUNS" nu e acelasi lucru cu „AVEM RANDURI".**
  Ion: „au ramas niste ramasite acasa in cazul cand nu este niciun task."
  Garda scrisa peste tot in aplicatie — `loading && items.length === 0` —
  CONFUNDA doua stari: „inca n-am primit nimic" si „raspunsul e gol". Cat timp
  ai randuri, confuzia nu se vede: lista nevida iese din prima ramura. Cand
  n-ai niciunul, fiecare incarcare da schelet, apoi starea goala — si nici
  cache-ul nu putea ajuta, fiindca o lista goala restaurata arata exact ca una
  neincarcata.
  - Fiecare store (`agenda`, `globalTasks`, `projects`, `plan`) are acum
    `incarcat`, pus si cand ce s-a restaurat e GOL.
  - Garda e `!incarcat`, **fara `loading`**: daca n-avem raspuns, asteptam prin
    definitie. Prima varianta (`loading && !incarcat`) a fost gresita si a
    adaugat o stare — la primul cadru, inainte ca incarcarea sa porneasca,
    cadea pe ramura urmatoare si arata STAREA GOALA, apoi scheletul, apoi
    raspunsul.
  - **Cache-ul agendei a trecut de la `sessionStorage` la `localStorage`**,
    rasturnand alegerea de dinainte. Argumentul vechi („accelerator pentru
    sesiunea curenta, nu o sursa care supravietuieste zile") ramane acoperit —
    dar de CHEIA PE ZI, care respinge un board de ieri, nu de tipul de stocare.
    `sessionStorage` moare cand se inchide fila, iar pe Android exact asta
    INSEAMNA „pornirea aplicatiei" — deci acceleratorul lipsea fix unde trebuia.
  - Masurat, Acasa pe o baza fara niciun task: a doua deschidere trece direct in
    starea goala la 16-29ms, o singura forma.
  - Prins in aceeasi trecere: `deleteTask` isi pierduse invalidarea intre doua
    modificari.
