# Patru locuri pe care gramatica mișcării nu le prinsese (tura 13, 2026-08-07)

## Din CLAUDE.md

Stratul de mișcare e bun — tura 8 i-a pus o curbă, un ceas și o adâncime. Tura 13
nu-l reinventează: caută unde **nu fusese aplicat**. Trei lipsuri sunt deschideri,
al patrulea e o inconsecvență în interiorul aceluiași rând.

- **Deschiderea paginii.** `.cell-in` trăia deja pe Acasă, /tasks, /projects și
  Calculator; Calendarul și Planificatorul apăreau între două cadre — și tocmai
  ele sunt cele pe care le deschizi de mai multe ori pe zi. Acum învelișul rutei
  urcă 10px (`.ruta-in`, nou în `global.css`), apoi celulele intră cu **același**
  pas de 32ms. **10px, nu 22 ca la celule:** aceeași distanță pe un obiect de zece
  ori mai mare nu se citește ca sosire, ci ca zguduire.
  - **`.ruta-in` închide pe `transform: none`, nu pe `translateY(0)`.** Un transform
    rămas — chiar și identitatea — face din înveliș blocul de referință al oricărui
    `position: fixed` dinăuntru (popoverul și eticheta de tragere din Planificator
    sunt fixed) și le-ar deplasa pe toate cu cât e derulată pagina.
  - **`@media print { .cell-in, .ruta-in { opacity: 1 !important } }`** — amândouă
    pornesc de la `opacity: 0`, iar la print animațiile nu se joacă. Fără regulă,
    exportul PDF al Planificatorului (care tipărește exact `.page` cu `.chart`
    înăuntru) ar fi ieșit **alb**. Aceeași grijă în blocul de print din `Plan.svelte`
    pentru `.impl-band`.
  - Indicii de celulă merg **prin** `.backlog`: pe telefon sertarul stă DEASUPRA
    listei, deci `.chart`=0, `.backlog`=1, `.mlist`=2 — altfel capul ar sosi după
    coadă, exact bug-ul reparat în tura 8.

- **Schimbarea lunii** era singura navigare fără sens: apăsai „înainte" și grila se
  ÎNLOCUIA. După două apăsări rapide nu mai știai dacă ai mers două luni înainte
  sau una-nainte-una-napoi. `alunecare()` în `motion.svelte.js` — ±10px pe X în
  `--dur-fast`, în sensul apăsării. **Singura mișcare din tură care adaugă
  informație**, nu doar politețe.
  - **`{#key anchor}` pe grilă, nu o clasă comutată:** o clasă care rămâne aceeași
    nu re-pornește o animație CSS, deci două apăsări „înainte" la rând ar fi dat o
    singură alunecare — fix cazul de rezolvat. Bloc nou = tranziție nouă.
  - **`load()` nu mai stinge grila la navigare** (`loading = data === null`).
    `grila` se recalculează SINCRON din `anchor`, deci zilele erau deja gata și doar
    benzile întârziau; scheletul le înlocuia pe amândouă cu o formă care nu seamănă
    cu niciun calendar — și distrugea elementul pe care aleargă alunecarea înainte
    s-o vadă cineva. Scheletul rămâne doar la **prima** încărcare.
  - Orice salt la o zi anume („de clarificat", „Urmează") trece prin `ancoreazaPe()`,
    care calculează sensul **înainte** de a rescrie `anchor`. Fără el, un salt ar fi
    alunecat în direcția ultimei apăsări de lună. (Prins în aceeași trecere:
    „Urmează" ancora cu `monthStart` și în modul 2 săptămâni, unde `anchor` trebuie
    să fie un început de săptămână.)

- **Panoul zilei.** Lucrările se estompau una câte una, dar `.pan-zi` — data zilei,
  adică exact partea care se schimbă cel mai vizibil — sărea. Acum se mișcă panoul
  ÎNTREG, o dată (`{#key selectata}` + `sosire`), iar stingerea de pe rânduri a
  plecat: două sosiri peste aceiași pixeli nu se adună, se încurcă.
  - **`|local`**: la prima încărcare panoul sosește oricum, prin `.cell-in` de pe
    `.side`. `{#key}` pe ZIUA selectată, nu pe conținut — două zile pot avea
    aceleași lucrări și tot trebuie să se vadă că ai schimbat ziua.

- **Benzile din planificator.** Ce are început crește din el; ce doar acoperă un
  interval, apare.
  - **`.impl-band`** are o zi de start reală → se **descoperă** de la stânga
    (`clip-path`), adică dinspre ziua în care începe. **Nu `scaleX`:** ar turti
    eticheta la jumătate de lățime pe la mijlocul mișcării, iar un text care se
    lățește înapoi la normal se citește ca elastic, nu ca o perioadă care începe.
  - **`backwards`, nu `forwards`:** `clip-path` trebuie să se întoarcă la `none`.
    Înghețat pe `inset(0 0 0 0)` ar tăia la border-box, adică ar șterge **definitiv**
    umbra exterioară a blocului.
  - **`.impl-band.clipL`** (tăiată de fereastră la stânga) cade înapoi pe stingere:
    ziua ei de start nu e pe ecran, deci o descoperire din stânga ar inventa un
    început fix acolo unde muchia dreaptă spune „continuă din afară".
  - ~~**`.band` (pregătirea) NU crește**~~ — **banda de pregătire a plecat de tot pe
    2026-08-15**, vezi mai jos. Era singurul obiect de pe rând fără zi de start,
    deci singurul care doar se stingea în loc să crească; keyframe-ul i-a
    supraviețuit (redenumit `apareIn`) fiindcă îl folosește `.impl-band.clipL` — o
    perioadă tăiată de marginea ferestrei n-are nici ea un început vizibil.
  - **Reduced-motion anulează animația, nu doar durata**, și regula stă la **finalul**
    foii: plasa globală scurtează `animation-duration`, dar nu atinge
    `animation-delay` — cu `backwards`, rândul șase ar sta 240ms invizibil și apoi
    ar pocni. Iar un `@media` nu adaugă specificitate, deci scrisă mai sus ar fi
    fost anulată de `.impl-band` / `.bar` (și de `.band`, cât a existat).
  - **Variabila de decalaj se numește `--rand`**, nu `--celula` (acela e pasul de
    32ms al celulelor de pagină și s-ar moșteni peste orice `.cell-in` de dedesubt)
    și nu `--i` (acela înseamnă deja „rândul benzii" în Calendar).

**Premisa 13e era depășită, și asta a lărgit lucrarea.** Documentul spunea „taskul
crește din ziua lui, iar cele două benzi pe care stă apar instantaneu" și cerea doar
ca benzile să i se potrivească. Taskul **nu** mai creștea: `barIn` scala o LĂȚIME și
a plecat odată cu cutia, în tura în care taskul a devenit un reper de o zi (v33).
Dacă mișcam doar benzile, inconsecvența nu dispărea — se întorcea pe dos, un rând
plin de mișcare cu reperele înghețate deasupra. Deci reperul a primit `reperIn`:
un punct n-are lățime de întins, așa că **crește pe loc**, din ziua lui
(`transform-origin: left`; `right` pe `.bar.flip`, care își scrie eticheta invers).
Pe mobil același `reperIn` merge pe `.mt-pin`, dar **pe buton, nu pe `::before`** —
rombul își ține forma dintr-un `rotate(45deg)`, iar `to { transform: none }` i-ar
șterge rotația și l-ar lăsa pătrat.

## Din MEMORY.md

- **2026-08-07 (3) — Tura 13: miscarea nu se reinventeaza, se pune unde lipsea.**
  Patru locuri neprinse de gramatica existenta. (1) Calendar si Plan n-aveau
  deschidere: `.ruta-in` (nou in `global.css`) + `.cell-in` pe celule. (2)
  Schimbarea lunii n-avea sens — `alunecare()` in `motion.svelte.js`, ±10px pe X
  in sensul apasarii, prin `{#key anchor}` (o clasa comutata NU re-porneste
  animatia la a doua apasare in aceeasi directie). (3) Panoul zilei se misca acum
  intreg (`{#key selectata}` + `sosire|local`), fiindca `.pan-zi` — partea care se
  schimba cel mai vizibil — era singura care sarea. (4) Benzile din Planificator:
  `.impl-band` are zi de start reala, deci se DESCOPERA din stanga (`clip-path`,
  fill `backwards` — `forwards` ar ingheta `inset(0 0 0 0)` si ar taia definitiv
  umbra); `.band` (pregatirea) doar se stinge, fiindca n-are inceput cunoscut.
  **Trei capcane de tinut minte:** `.ruta-in` inchide pe `transform: none`, altfel
  invelisul devine blocul de referinta al oricarui `position: fixed` dinauntru
  (`.pop` din Plan); la print `.cell-in`/`.ruta-in` trebuie fortate la `opacity: 1`
  sau exportul PDF iese ALB; anularea la reduced-motion trebuie sa scoata
  `animation`, nu doar durata (plasa globala nu atinge `animation-delay`, iar cu
  `backwards` asta inseamna 240ms de invizibil urmate de o pocnitura) — si trebuie
  scrisa la FINALUL foii, fiindca `@media` nu adauga specificitate.
  **Premisa 13e era depasita:** documentul presupunea ca taskul creste deja din
  ziua lui; `barIn` plecase odata cu cutia in v33. Doar benzile ar fi intors
  inconsecventa pe dos, deci reperul a primit `reperIn` — un punct nu se intinde,
  creste pe loc. Pe mobil animatia sta pe `.mt-pin`, NU pe `::before`: rombul isi
  tine forma dintr-un `rotate(45deg)` pe care `transform: none` l-ar sterge.
  Verificat: build verde, `audit_design` curat, `smoke_ui` 18/18, `audit_mobil`
  curat, `test_suite` 53/53, plus o proba de rulare pe baza insamantata (17/17)
  care confirma in stilul CALCULAT ca Svelte a scopat corect numele de keyframe.
