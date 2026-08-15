# 2026-07-31 — Dock-ul tine CINCI lucruri pe telefon; si o ruta scoasa din navigatie trebuie sa ramana cu un drum

- **2026-07-31 (2) — Dock-ul tine CINCI lucruri pe telefon; si o ruta scoasa din
  navigatie trebuie sa ramana cu un drum.** Ion: „pentru mobil, poti sa pastrezi pe
  dock doar acasa, taskuri, planificator, calendar si search? dar doar pentru mobil?"
  Filtrul e in `Dock.svelte`, `PE_TELEFON = {'/', '/tasks', '/plan', '/calendar'}`,
  aplicat prin `$derived` pe `ecran.telefon`. Desktopul ramane neatins: 8 tinte.
  **De ce `ecran.telefon` si NU `isMobile`-ul local al Dock-ului:** cele doua raspund
  la intrebari diferite. `isMobile` include `pointer: coarse` fiindca decide „dock fix
  sau autohide"; filtrarea decide „cate incap pe lat". Pe o tableta lata cu ecran
  tactil vrei dock fix, dar ai loc de toate sapte. `ecran.telefon` citeste valoarea
  IMEDIAT (nu dupa montare), deci nu apar sapte iconite si abia apoi cinci.
  Masurat: 390px si 360px -> 5 tinte, dock 226px, tinta minima 44px, fara depasire;
  1440px -> 8 tinte, neschimbat.
  **Partea care nu era in cerere, dar fara de care cererea rupea ceva:** Departament
  NU era in `CommandPalette`. Cat timp statea in Dock nu conta; scoasa din Dock si
  lipsa din paleta, devenea o ruta pe care nu o mai poti deschide de pe telefon.
  Adaugata.
  **Al doilea, descoperit verificand primul:** paleta ascundea lista de rute de indata
  ce scriai a DOUA litera (`{#if !isSearchMode}`), deci `keywords` de pe comenzi nu se
  putea folosi niciodata — cautand „calculator" primeai note si proiecte, dar nu si
  PAGINA Calculator. Se vedea putin cat timp toate rutele erau in Dock; de cand paleta
  e singurul drum spre trei dintre ele, reflexul „scriu unde vreau sa ajung" trebuie
  sa mearga. Rutele intra acum in `flatResults` ca grup „Pagini", PRIMUL — asa
  indicii (`selectableIndex`/`nextSelectable`/`totalItems`) raman valizi fara alta
  matematica. `activateResult` intoarce devreme pe `_nav` (o ruta se navigheaza, nu
  se deschide), iar cheia din `{#each}` foloseste `path`, nu `id` (rutele n-au id).
  Verificat pe telefon: „departament"/„proiecte"/„calculator"/„planificator" -> pagina
  respectiva e primul rezultat si Enter ajunge la ea.
  **Capcana de mediu (nu de cod):** login-ul intoarce **429** dupa ~60 de incercari/min,
  iar `login.html` afiseaza „PIN incorect" pentru orice esec — deci un test care
  logheaza des pare ca greseste PIN-ul. Ruleaza pe port nou / asteapta un minut.
  Verificat: `audit_design` curat, `smoke_ui` 28/28, `audit_mobil` complet OK,
  `test_suite` 12/12.
