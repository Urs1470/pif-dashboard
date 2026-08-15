# Modalul se deschide cu datele în mână (2026-08-07)

## Din CLAUDE.md

Ion, în aceeași linie cu tura 13: *„repară animația la modalul de selecție taskuri
pentru ziua de astăzi de pe pagina acasa."*

Măsurat cadru cu cadru, caseta se deschidea la **228px** și **sărea la 374 după
16ms**, cât era încă la opacitate 0,19 — plus 73px pe verticală, fiindcă e
centrată. Scalarea de intrare (0,96 → 1) mișcă vreo 15px; saltul era de **zece
ori** mai mare și se juca peste ea. Ce vedeai nu era un modal care sosește, ci
unul care se corectează.

Cauza: `open` randa imediat, cu `items` gol, deci caseta se dimensiona după o
singură linie de text („Niciun task disponibil de adăugat"), iar lista venea după.
Aceeași regulă ca la `desfacere` din `motion.svelte.js`, unde e scrisă deja: **un
panou se deschide numai cu conținutul măsurabil**, altfel tranziția animează spre
o țintă care se schimbă sub ea.

- **`deschis` e ce vede `<Modal>`; `open` rămâne intenția părintelui.** Închiderea
  pornită de utilizator se întoarce prin `onclose` — singurul drum pe care Modal
  îl semnalează în afară.
- **Plafon de 250ms**, ca butonul să nu pară stricat dacă API-ul întârzie: peste
  atât se deschide oricum, cu **schelet** în locul listei. Scheletul ține locul, deci
  umplerea de după e o înlocuire, nu un salt. Sub plafon nu se vede niciodată.
- **Scheletul e gardat pe `loading && items.length === 0`** (regula din sistemul de
  design): când tastezi o căutare peste o listă deja adusă, rândurile vechi RĂMÂN
  pe ecran — altfel caseta s-ar strânge și s-ar umfla înapoi la fiecare tastă.

**Și o a doua scăpare, în același loc:** caseta se mișca pe `cubicOut` (implicitul
lui `scale`), iar vălul care o ține pe `EASE`. Două curbe pe același obiect: în
prima treime vălul se întuneca vizibil înaintea casetei, și amândouă se opreau
odată — obiectul părea că vine *după* umbra lui. E exact scăparea pe care tura 8 a
reparat-o la `fade`/`sosire`/`plecare`; `scale` n-a fost pe listă atunci fiindcă
`fly` și `slide` — verificate — aveau deja `cubicOut`, și a fost pus în aceeași
găleată fără să fie deschis. Acum ambele ramuri din `intra()` folosesc `EASE`.
Verificat după: caseta pornește la 386px din primul cadru, iar curba ei de
opacitate e identică pe zecimale cu a vălului.

## Din MEMORY.md

- **2026-08-07 (4) — Modalul se deschide cu datele in mana.**
  Selectorul de taskuri (Acasa -> „Adaugă task existent") se deschidea la 228px si
  SAREA la 374 dupa 16ms, cat era inca la opacitate 0,19 — masurat cadru cu cadru.
  Scalarea de intrare misca 15px; saltul era de zece ori mai mare. `open` randa
  imediat, cu `items` gol. Acum `deschis` (ce vede `<Modal>`) se aprinde dupa
  prima cautare, cu plafon de 250ms + schelet pe ramura lenta; `onclose` intoarce
  inchiderea catre parinte. Aceeasi regula ca la `desfacere`.
  **A doua scapare in acelasi loc:** caseta pe `cubicOut` (implicitul lui `scale`),
  voalul pe `EASE` — obiectul parea ca vine dupa umbra lui. `scale` scapase de
  tura 8 fiindca `fly`/`slide` aveau deja `cubicOut` si a fost pus in aceeasi
  galeata. Ambele ramuri din `intra()` folosesc acum `EASE`.
  **Cum s-a gasit:** o sonda `requestAnimationFrame` care esantioneaza
  `offsetHeight` + `opacity` + `transform` pe fiecare cadru. NU
  `getBoundingClientRect`: include scalarea, deci raporteaza chiar animatia ca
  „salt de inaltime". Si sonda nu poate intoarce o promisiune care traieste peste
  un click — Playwright o vede colectata; scrie in `window.__probe`, se citeste dupa.
