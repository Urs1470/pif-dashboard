# Sfera se comută cu degetul, pe toată pagina (2026-08-15)

## Din CLAUDE.md

Ion: *„vreau să comut cu gest de swipe pe Android între personale și lucru."*

Gestul exista deja — dar **doar pe bara de unelte**. Măsurat cu deget adevărat:
funcționa, comuta corect; numai că bara e o bandă de **46px dintr-un ecran de 844**,
sus, adică exact unde nu stă degetul când citești lista. Un gest care există pe 5%
din ecran nu există. Acum e al **paginii întregi** (`.page`), cu o singură excepție.

- **Un gest care începe pe un RÂND aparține rândului.** Acolo orizontala e deja un
  verb — dreapta „Făcut", stânga „Planifică" — iar regula care ține gesturile din
  aplicație e că **o ratare n-are voie să producă ALTCEVA**. Dacă sfera s-ar comuta
  și de pe rând, o țintă ratată ar bifa un task.
  **Costul, măsurat, și e real:** cu lista plină (15 taskuri pe 390×844) rândurile
  acoperă 627px, deci gestului îi rămân **217px, 26% din ecran**; cu listă scurtă,
  82%. Ce rămâne mereu la îndemână: capul paginii, bara, **capul de grupă — care e
  lipit sus, deci vizibil oricât ai derula** — golurile dintre rânduri și spațiul de
  sub listă.
- **Feedback viu, altfel gestul e o loterie.** Conținutul (`.list-cell`) urmează
  degetul amortizat (0,42 din distanță, plafon 64px); la margine se lasă de două ori
  mai puțin și nu comută — ăsta **e** răspunsul „nu ai unde să mergi", spus în timpul
  gestului, nu după. Pragul dă același `puls()` ca la rânduri: două gesturi diferite,
  dar „ai trecut pragul" trebuie să se simtă la fel.
- **Transformul se scrie DOAR cât ține gestul.** Un `transform` rămas — chiar și
  identitatea — face din element blocul de referință al oricărui `position: fixed`
  dinăuntru; capcană plătită deja o dată la `.ruta-in`.
- **Gestul înghite clicul de la ridicarea degetului** (fază de capturare, ca în
  `lib/glisare.js`), și aici e obligatoriu, nu igienă: bara conține chiar cele două
  segmente, deci un gest pornit **pe** „Personal" se termina cu un clic pe „Personal",
  care naviga înapoi și anula exact comutarea cerută. Prins de probă, nu dedus.
- Verticala câștigă la egalitate, decis o singură dată la 10px; ascultătorii sunt
  pasivi și nu se cheamă `preventDefault` nicăieri, deci derularea nativă nu e
  niciodată blocată.

## Din MEMORY.md

- **2026-08-15 (7) — Gestul de sfera pe toata pagina, si banda de pregatire scoasa.**
  Doua cereri ale lui Ion in aceeasi tura.
  - **„vreau sa comut cu gest de swipe pe android intre personale si lucru".**
    Gestul EXISTA deja, si masurat cu deget adevarat CHIAR FUNCTIONA — dar doar pe
    `.toolbar`, o banda de 46px din 844. Lectia: „e implementat" si „e la indemana"
    sunt lucruri diferite; masoara SUPRAFATA pe care raspunde un gest, nu doar
    daca raspunde. Acum e pe `.page`.
  - **Exceptia care ramane: un gest pornit pe `.trow` e al randului** (dreapta
    „Făcut", stanga „Planifică"). Regula aplicatiei: o ratare n-are voie sa
    produca ALTCEVA. Costul e masurat si real — cu lista plina randurile acoperă
    627px din 844, deci gestului ii raman 26% din ecran; cu lista scurta, 82%.
    Capul de grupa e LIPIT sus, deci ramane la indemana oricat derulezi.
  - **Bug prins de proba, nu dedus:** gestul nu inghitea clicul de la ridicarea
    degetului, iar bara contine chiar cele doua segmente — deci un gest pornit PE
    „Personal" se termina cu un click pe „Personal" si anula comutarea. Acum e
    inghitit in faza de CAPTURARE, ca in `lib/glisare.js`.
  - **Doua capcane de MASURAT, amandoua m-au pacalit intai:** (1) citirea DOM-ului
    sincron, imediat dupa `dispatchEvent`, vede starea VECHE — Svelte scrie pe
    microtask, deci proba raporta „0 cadre de feedback" pentru un feedback care
    exista; fiecare pas al gestului trebuie dat intr-un APEL SEPARAT. (2) clicul
    sintetic de la finalul tragerii cade pe elementul de START, deci o proba care
    porneste gestul pe un buton masoara butonul, nu gestul.
  - **Banda de pregatire din Planificator a plecat** („e clar ca este in pregatire
    fara sa vad pe planificator, dar acum arata straniu"). Era DERIVATA — golul
    dintre etape — si isi recunostea singura capatul inventat (stanga estompata,
    fiindca „de cand se pregateste" nu se stie de la v36). Dupa ce perioada a
    devenit sina de 4px, ea ramasese singurul lucru lat de pe pista: fundalul era
    mai prezent decat datele.
    **NU confunda cu faza `pregatire` a unei PERIOADE reale** (`implementari.faza`,
    `.impl-band.pregatire`, `.banda.pregatire` din Calendar) — aceea ramane.
    Keyframe-ul `pregatireIn` NU a plecat cu ea: il foloseste `.impl-band.clipL`;
    redenumit `apareIn`.
  - Verificat: build curat, `audit_design` curat, `smoke_ui` 20/20, `audit_mobil`
    curat, plus o proba proprie de 14 verificari pentru gest (comuta de pe cele
    patru suprafete, NU de pe rand, verticala castiga, margine, prag, clicul
    inghitit, feedback viu, zero transform ramas).
