# 2026-08-21 — Mișcarea din Taskuri: reparație de fond, după cercetare

Ion, după patru runde de reparații punctuale: *„pe partea de taskuri stăm groaznic cu
animațiile… trebuie să ne oprim, să facem research și apoi un plan."* A avut dreptate:
reparațiile veneau dintr-un diagnostic făcut în **emulare**, iar emularea reproducea un
aparat care nu există.

## Cauza reală #1 — ne luptam cu o redimensionare pe care Capacitor o face deja

`SystemBars` (plugin de **core**, înregistrat automat) vede `viewport-fit=cover` și, la
apariția IME-ului, pune `setPadding(0,0,0,imeInsets.bottom)` pe părintele WebView-ului:
**micșorează fizic WebView-ul, într-o singură trecere de layout**. Nimeni nu instalează un
`WindowInsetsAnimationCallback`, deci insets-urile sosesc **o dată, cu valoarea finală**.

Iar CSS-ul nostru *anima* 220 ms ca să-l ajungă din urmă (`max-height` pe foaie,
`padding-bottom` pe voal și pe corp). De aici:
- **„apare brusc tastatura, se rupe animația"** — viewportul sare într-un cadru, foaia
  rămâne 220 ms în urmă;
- **„se închide în două etape"** — simetric: foaia *crește* înapoi în timp ce coboară.

Și de-asta emularea zicea „OK": ținea `innerHeight` constant, deci formula
`innerHeight - vv.height` dădea valoarea intenționată. Pe aparat ambele scad împreună →
`--kb` = **0**, corect. **Trei runde de reglaje pe `--kb` n-au atins niciodată telefonul lui Ion.**

**Reparația e o scoatere, nu o adăugare:** zero tranziții pe `height`/`max-height`/
`padding-bottom`. Geometria urmează viewportul în același cadru — ca o aplicație nativă.
Măsurat: **7 ms** (un cadru).

Foaia care **pleacă** își îngheață geometria (înălțimea voalului și a ei) și merge pe o
distanță în **px**, nu `100%` — procentul se reevalua când creștea înălțimea în zbor, de unde
saltul de 192 px măsurat la închidere. Iar `--safe-*` citesc acum variabilele injectate de
Capacitor (coerente cu redimensionarea), nu doar `env()`, care sărea în alt cadru.

## Cauza reală #2 — animam layout cadru-cu-cadru pe rânduri de listă

Regula scrisă a casei e „doar `transform`/`opacity` în animații". Realitatea: `plecare`
(rândul bifat/șters) anima `height` + `margin` + două `border-width` din JS, la fiecare cadru,
**simultan cu `animate:flip`** pe frați — două mecanisme pentru același gol, unul pe layout.

Acum rândul care pleacă **iese din flux** (`position: absolute` pe geometria lui), deci golul
se închide în același cadru, iar frații alunecă prin `flip`, pe compozitor.

Odată cu asta: `desfacere` + `expandedTask` șterse (cod mort — blocul nu se mai randa de când
taskul se deschide în panou); `will-change: transform` **permanent** scos de pe fiecare rând
din patru fișiere (pe 40 de taskuri = 40 de straturi de compozitare ținute degeaba, exact ce
interzice regula scrisă în `tragereTimeline.js`); `animate:flip` primește curba casei în toate
cele 7 locuri (rulau pe `cubicOut`); lista personală de pe Acasă primește și ea `flip`.

## Cauza reală #3 — auditul dădea aviz fals

`audit_design.py` raporta `curat`, dar verifica **doar `transition:`**, doar în `.svelte`/`.css`,
iar regula lui de layout căuta `transition: all` — care nu apare nicăieri. Deci exact
categoriile în care sistemul alunecase erau nevăzute.

Extins: prinde și `animation`/`animation-duration`/`animation-delay`; citește și `lib/**/*.js`;
regulă nouă **R3b** care interzice `transition` pe proprietăți de layout; `R8` prinde și
`animate:flip`. A ieșit din asta o derivă reală, acum tokenizată: semnul de aterizare avea
**două durate** (1000 ms pe bandă, 1500 ms pe rând) → `--dur-semn`; scara avea **două trepte**
(40 și 45 ms) → `--pas-scara`. Excepțiile rămase sunt listate explicit, fiecare cu motivul ei.

`audit_tastatura.py` testa un aparat inexistent. Rescris pe **regimul real**: micșorează chiar
viewportul, într-un pas. Contractul nou: *nicio proprietate de layout tranziționată pe foaie
sau voal; geometria nouă în același cadru; la închidere înălțimea nu se schimbă și coborârea
n-are salt.*

## Ce am păstrat, deși planul zicea altfel

Cele trei animații de bifare (inelul se ștampilează, bifa se desenează, tăietura) rulează pe
`clip-path`/`background-size` — paint, nu compozitor. Planul cerea reducerea la
transform+opacity, dar sunt un design cerut explicit de Ion („bifa se desenează", 2026-08-15)
și rulează pe elemente **mici**. Am reparat doar coordonarea: pauza de `400ms` scrisă de mână
în două fișiere devine `INTARZIERE_BIFA`, derivată din duratele care chiar se joacă.

## Ce am aflat că NU merge (ca să nu se mai încerce)

`interactive-widget=` **nu are efect în WebView** (Intent to Ship, textual: *„no intended
behavior change for Android WebView"*). Modurile `resize` din `@capacitor/keyboard` sunt
**iOS only**, iar pe Android `keyboardWillShow` **nu dă niciun avans**. VirtualKeyboard API
n-are suport verificabil în WebView. Deci plugin-ul de tastatură — pe care Ion îl aprobase —
**n-ar fi rezolvat nimic**, și de-aia nu l-am instalat.

Singura cale de a *anima* împreună cu IME-ul rămâne nativă:
`ViewCompat.setWindowInsetsAnimationCallback` (API 30+), cu `onProgress` la fiecare cadru.
Rămâne disponibilă dacă, după toate astea, mișcarea tot nu e destul de fină.
