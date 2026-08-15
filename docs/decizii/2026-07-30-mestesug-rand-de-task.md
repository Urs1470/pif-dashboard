# 2026-07-30 — Trecere de mestesug pe randul de task: o singura axa de culoare, si cod care nu se putea randa

- **2026-07-30 (9) — Trecere de mestesug pe randul de task: o singura axa de culoare,
  si cod care nu se putea randa.** Ion: „vezi ce putem imbunatati, pe plan de stilistica,
  decizii, stil, design, comoditate, UI, UX". (READMEurile de pe GitHub listeaza
  functii, nu mestesug — asa ca masuratoarea a fost pe propriile ecrane.)
  **(1) Ierarhia era pe dos.** Masurat pe desktop: indexul decorativ „01" era
  16px/700/colorat — cel mai tare text din rand; categoria 11.2/600/mov; TITLUL
  12.8/500; termenul 10.4. Adica numarul de ordine batea continutul. Acum: titlu
  `--font-body`, index fantoma (0.8rem/500, severitate la 38%), termen `--font-tiny`.
  **(2) Trei sisteme de culoare pe acelasi rand** — severitate, mov (categorie),
  amber (subtask/recurenta/proiect). Regula noua, in toate cele trei liste:
  **culoarea e rezervata severitatii**; restul metadatelor sunt gri.
  **(3) Boardul „Astăzi" spunea acelasi lucru de trei ori:** pastila rosie „Restant",
  pastila amber „Termen azi", si data colorata dupa severitate. Pe un board unde totul
  e scadent azi sau restant, pastilele doar partitioneaza lista. Ramane data, relativa:
  „azi" / „ieri" / „acum 3 zile" — si starea, si distanta, intr-un singur chip.
  **(4) Sectiunea „N finalizate" din /tasks NU se putea randa niciodata.**
  `/api/global-tasks` adauga `AND status != 'done'` cand nu ceri arhiva, deci
  `doneTasks` e mereu gol in vederea activa — iar sectiunea era gardata pe
  `!showArchive && doneTasks.length > 0`. ~40 de linii de markup, CSS propriu, o stare
  si un `$effect` de deep-link, toate moarte. Sterse. Starea goala spune acum unde au
  plecat cele bifate, si e adevarata si cand n-ai avut niciodata taskuri.
  **(5) Actiunile de pe randul din pagina de proiect erau `opacity: 0` pana la hover**,
  in timp ce aceleasi butoane din /tasks stau mereu la vedere. Doua liste, acelasi rand,
  doua comportamente — si `opacity: 0` + `:hover` inseamna INEXISTENT pe un laptop cu
  ecran tactil intre 768 si 940px, unde nu prinde nici regula de telefon.
  **(6) 22 de `transition: all`** inlocuite cu proprietati numite (`all` interpoleaza
  si latimi/padding-uri, deci o schimbare de culoare la hover poate misca layoutul).
  **(7) Ritmul de deasupra listei:** primul task incepea la y=296 pe 390×800 (37% din
  ecran). Aceleasi elemente, ~30px mai sus.
