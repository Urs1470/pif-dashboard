# 2026-07-31 — Aprofundarea consolidarii: starile, nu doar suprafata

- **2026-07-31 (5) — Aprofundarea consolidarii: starile, nu doar suprafata.**
  Metoda noua: am TAIAT serverul (500) sub fiecare pagina si am fotografiat ce
  ramane; am masurat ritmul intre pagini; am cautat nume care promit altceva
  decat fac.
  **(1) Acasa avea singurele stari de eroare mute.** Boardul „Astăzi" arata un
  paragraf rosu fara drum inainte (regula de design cere `<ErrorState>` cu retry — toate
  celelalte pagini il aveau); linia „urmatoarea iesire" era mai rea: la esec punea
  `data = null` si DISPAREA — eroarea arata identic cu „nicio iesire planificata",
  exact absenta tacuta despre care scrie lectia v29. Acum: ErrorState pe board,
  iar linia ramane pe ecran cu „Ieșirile nu s-au putut încărca" + Reîncearcă
  inline. Ambele retry-uri verificate cu rutele taiate si apoi eliberate.
  **(2) Ritmul mobil din decizia (9) se aplicase doar pe /tasks.** Masurat pe
  /projects la 390×844: primul card la y=314 — acelasi 37% din ecran pentru care
  /tasks fusese strans. Aceleasi strangeri: 314 -> 282.
  **(3) `.form-row-3` cu DOI copii** — coloana prioritatii (plecata in v34) a
  ramas in grila: o treime din modal, goala, pe ambele formulare de task. Acum
  `.form-row-2`.
  **(4) Grila de proiecte se demola la fiecare actiune** — `{#if projects.loading}`
  fara garda `items.length === 0` (regula scrisa in Tasks/TodayBoard/Plan), desi
  loadProjects() se cheama la comutare de status, stergere si filtre. Masurat
  dupa: zero schelete la filtrare.
  Verificat iar: toate 4 harnessurile verzi.
