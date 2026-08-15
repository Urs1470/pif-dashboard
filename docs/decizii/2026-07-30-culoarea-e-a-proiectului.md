# 2026-07-30 — Culoarea unui proiect era o proprietate a PAGINII, nu a proiectului

- **2026-07-30 (11) — Culoarea unui proiect era o proprietate a PAGINII, nu a proiectului.**
  Cercetare pe sistemele de referinta (Radix Colors — scara de 12 trepte cu rol fix per
  treapta; Linear — LCH, 98 variabile de tema reduse la 3; regulile de miscare din
  performance.dev; WCAG 2.2 tinta 24px) si aplicarea rezultatelor.
  **Ce era stricat, masurat:** paleta de identitate exista in DOUA fisiere
  (`Calendar.svelte` si `Plan.svelte`) cu aceleasi sapte culori dar ROTITE pe ultimele
  trei pozitii; functia de dispersie era identica, deci indexul iesea acelasi si cadea
  pe alta culoare — **43% dintre proiecte aveau o culoare in Calendar si alta in
  Planificator**. In plus, barele din Calendar se colorau dupa `proiect_id` dar sertarul
  „Proiecte fara perioada" dupa `client`, deci acelasi proiect avea doua culori pe
  ACELASI ecran (si cum 11 din 12 perioade sunt la Continental, tot sertarul iesea
  monocrom — exact bug-ul pe care Calendarul il rezolvase deja pentru bare).
  **Sursa unica:** `frontend/src/lib/culori.js` — `culoareProiect(id)`, hash pe
  `proiecte.id` (nu pe client: se repeta; nu pe nume: se redenumeste).
  **Paleta e REZOLVATA, nu aleasa** (`scripts/solve_paleta.py`). Prima incercare —
  „sase nuante egal distantate pe roata" — a iesit la 0,055 separare, MAI PROST decat
  productia (0,064): sub deficienta rosu-verde axa rosu-verde se prabuseste, deci
  distantarea pe roata nu inseamna nimic. Ce supravietuieste e LUMINOZITATEA (de aceea
  paleta finala are contraste intre 4,5:1 si 12,2:1, nu sase nuante la fel de intense).
  Rezultat: **0,221 — de 3,5 ori mai bine decat productia**, o nuanta per familie,
  departe de lobii rezervati (amber=accent, coral=danger) si de tokenurile de locatie.
  Compromis acceptat: 6 culori in loc de 7 => la 18 proiecte ~3 impart o culoare.
  Culoarea NU identifica unic un proiect (n-a facut-o niciodata); face acelasi proiect
  recognoscibil de la o zi si de la un ecran la altul, ceea ce acum chiar face.
  **Locatia a devenit token** (`--loc-site`/`--loc-sediu`): erau 8 valori scrise de mana
  in 4 fisiere, cu TREI ambere diferite pentru acelasi „sediu" (`#c99a3a`, `#b98a2e`,
  `#c9a13a`). Chroma mica cu intentie — locatia e un fapt binar si nu are voie sa
  concureze cu identitatea; inainte `site` era exact `#3f9dc4`, valoare aflata SI in
  paleta de proiecte, deci in Planificator aceeasi culoare insemna cand „proiectul X",
  cand „esti pe teren".
  **CAPCANA (lovita si reparata):** `--loc-*` NU se redefinesc pe tema deschisa. Prima
  varianta le-a inchis „ca sa se citeasca pe alb" — dar rolul lor e FILL sub cerneala
  inchisa (`--on-color`), deci banda a iesit inchisa cu text inchis pe ea. Unde valoarea
  chiar e folosita ca TEXT se amesteca spre `--text` la locul folosirii; procentul e
  **55%**, nu 72% — la 70% eticheta pica sub AA pe tema deschisa (3,79:1 masurat).
  **Miscare:** `transition: all` (16 aparitii) inlocuit cu `--transition-colors` /
  `--transition-pressable` — `all` urmareste si proprietatile care reaseaza pagina.
  `--dur-press 0,05s` (sub pragul de 100ms al legaturii cauza-efect).
  **Apasare:** aplicatia avea 146 de reguli `:hover` si 37 de `:active`; pe telefon
  hover NU EXISTA, deci ~109 suprafete nu confirmau atingerea. Podea globala in
  `global.css` cu `:where(...)` (specificitate zero, deci orice componenta o bate),
  doar pe pointer grosier, exclusiv `transform` (se compune pe GPU, nu reaseaza).
  **Prins pe parcurs:** `--text-tertiary` folosit in ProjectDetail nu exista in tokens
  (fallback tacut) -> `--text-dim`; Dock avea `0.28s`, in afara scarii -> `--dur-base`.
  **Ce tine asta in loc de aici incolo:** `scripts/audit_design.py` (7 reguli, exit 1 pe
  abatere) — verificat ca prinde fiecare regula prin injectare de abateri, nu doar ca
  trece. Regula R6 (token folosit dar nedefinit) a prins `--text-tertiary`.
  Verificat: `audit_design` curat, `smoke_ui` 28/28, `audit_mobil` 0 depasiri + gesturi
  OK, `test_suite` 12/12, si culorile citite din DOM confirma acelasi proiect =
  aceeasi culoare in Calendar si Planificator.
