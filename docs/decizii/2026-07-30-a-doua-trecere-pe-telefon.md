# 2026-07-30 — A doua trecere pe telefon: masurata, nu privita

- **2026-07-30 (6) — A doua trecere pe telefon: masurata, nu privita. Plus patru
  reguli scrise pentru telefon care nu se aplicau nici pe telefon.** Auditul nou
  (`scripts/audit_mobil.py`, toate rutele × 375/360/390px) a gasit ce nu arunca nicio
  eroare si de aceea trecuse de build, de `smoke_ui` si de `test_suite` 12/12:
  **(1) CSS mobil ANULAT de reguli scrise mai jos in acelasi fisier.** Un `@media` NU
  adauga specificitate — la specificitate egala castiga ultima regula. In `Plan.svelte`
  blocul `@media (max-width: 768px)` statea la mijlocul fisierului, inaintea sectiunilor
  „backlog rail" si „controls": DOUASPREZECE selectoare (`.bl-chip`, `.bl-txt`, `.bl-proj`,
  `.bl-date`, `.page`, `.page-header`, `.controls`…) erau moarte. Masurat in pagina:
  chipul avea tot `max-width: 320px`, butonul de data tot 30px in loc de 44. Blocurile
  mobile sunt acum ULTIMELE din fisier; sectiuni noi se adauga DEASUPRA lor.
  **(2) Svelte TAIE selectorii cu clase puse din JS, nu doar avertizeaza.** `.arow.gl-tras`,
  `.trow.gl-bifa` etc. sunt adaugate la rulare de `glisare.js`, deci compilatorul le crede
  moarte. In CSS-ul LIVRAT supravietuise UNA din toate regulile de gest: glisai spre dreapta
  si nu vedeai verdele care spune „ai trecut pragul". Reteta: `:global()` DOAR pe clasa de
  rulare, ancora ramane scoped — `.arow:global(.gl-bifa)`.
  **(3) Tooltip la ATINGERE.** `pointerover` se apara de touch, dar drumul prin `focusin`
  nu se apara, si el porneste imediat (fara cele 380ms). Pe telefon, orice buton cu `title`
  scotea o bula PESTE exact lucrul atins. Paza: `nod.matches(':focus-visible')` — raspunsul
  browserului la „focusul asta merita aratat?", adevarat la Tab, fals la atingere.
  **(4) Reordonarea „Astăzi" pe touch** — `draggable` HTML5 nu exista pe telefon, iar
  inlocuitorul erau doua sageti de 40×22 pe FIECARE rand (76 pe un ecran). Acum
  `lib/reordonare.js`: maner de 44px cu `touch-action: none` (doar pe el, ca restul randului
  sa deruleze si sa gliseze mai departe), ordinea din DOM NU se atinge in timpul tragerii
  (doar `transform`-uri; Svelte rearanjeaza la final, cu `flip`). Pragul de schimb e la
  JUMATATEA randului tras, nu la mijlocul vecinului — vecinul se da la o parte cand treci
  pe langa el, deci prima varianta sarea o pozitie in loc de doua.
  **(5) Titlurile pe telefon** — `--font-h1` 28→21px etc. intr-un `@media` in `tokens.css`
  (tokenul, nu sapte pagini). Titlul unui proiect cadea pe PATRU randuri; iar cand titlul
  nu se putea micsora, butoanele ieseau din ecran — pe /projects „Proiect Nou" era retezat.
  `.page-header` a primit `flex-wrap`+`gap` (Projects si Tasks n-aveau niciunul).
  **(6) O SINGURA sursa pentru „suntem pe telefon"** — `lib/ecran.svelte.js` (`ecran.telefon`,
  `ecran.larg`), in locul a patru copii de `matchMedia('(max-width: 768px)')` cu propriul
  ascultator (Modal, DatePicker, TodayBoard, Calculator).
  **(7) `init_db()` CRAPA pe o baza NOUA** — `migrate_v1_to_v2` facea index pe `atasamente`
  si `migrate_v17_to_v18` o reconstruia; tabela a plecat in v28, deci un deploy curat murea
  la prima cerere. (`PRAGMA table_info` pe o tabela inexistenta intoarce zero randuri —
  exact semnatura lui „lipseste coloana".) Ambele sunt acum gardate pe existenta tabelei.
  Rezultat masurat: 21 combinatii ruta×latime, zero depasiri, zero tinte sub prag, zero
  campuri sub 16px; singura exceptie acceptata e reperul de o zi din Ganttul Planificatorului
  (26px cu buna stiinta — la 44px reperele din zile alaturate s-ar acoperi unul pe altul).
