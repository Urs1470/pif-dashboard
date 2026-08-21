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

## Runda următoare: saltul devine mișcare (fără să redevină layout)

Ion, după ce a primit reparația: *„E mult mai bine. Ce mai arată rău e momentul când vine
tastatura: modalul se ridică puțin și se face o animație bruscă. La închidere e ok."*

Corect — scosesem lagul, dar rămăsese un **salt sec**: foaia își lua poziția nouă într-un
cadru. Nu putem urmări animația IME-ului (insets-urile sosesc o dată, cu valoarea finală), dar
putem să nu sărim: **FLIP**. Geometria nouă se aplică instant (deci zero layout animat), apoi
foaia e desenată înapoi în locul vechi cu un `transform` și lăsată să gliseze la zero — un
singur canal, pe compozitor.

Trei capcane, toate măsurate, fiecare ar fi lăsat glisarea moartă sau urâtă:

1. **Reper învechit.** Îl capturam o dată, la înregistrare — adică la *începutul* animației de
   deschidere, când foaia e încă sub ecran. Reperul rămânea `top = 844`, deci diferența ieșea
   681 px în loc de 131 și garda de rotație o respingea: nu pornea niciodată. Acum se
   reîmprospătează la fiecare cadru, cât există foi deschise.
2. **Cursă cu propriul reper.** Evenimentul de redimensionare sosește *după* ce layoutul s-a
   schimbat. Dacă diferența s-ar calcula într-un `rAF`, reîmprospătarea de la (1) ar putea rula
   între timp și ar șterge tocmai valoarea de dinainte.
3. **Pâlpâire.** Cât timp glisarea era amânată pe `rAF`, foaia apuca să se deseneze 1–2 cadre în
   poziția *nouă*, apoi sărea înapoi și de-abia atunci glisa. Acum transformul se pune **sincron**,
   în același cadru cu schimbarea de layout; coalescența celor două evenimente (`visualViewport`
   și `window`) se face prin steag, nu prin amânare.

Gărzi: nu glisează cât foaia **pleacă** (`.iese` — acolo geometria e înghețată dinadins) și nici
cât **degetul o trage** (`.trage` — ar fi a doua mână pe același obiect). Verificat: bucla `rAF`
se oprește complet când nu mai e nicio foaie deschisă (0 cadre în 600 ms), iar în timpul
gestului nu pornește nicio animație.

Contractul din audit distinge acum cele două: **înălțimea (layout) în același cadru**, dar
**poziția are voie să gliseze** — măsurat 16 cadre, într-un singur sens, fără pâlpâire.

### Ce a găsit verificarea adversarială pe glisare (și de ce testele mele n-au prins-o)

Probele mele au trecut: bucla se oprea, garda de gest funcționa, zero erori. Dar testasem
doar cazurile simple — **o** foaie, un gest, o redimensionare. Verificarea (3 lentile + juriu,
15 agenți) a găsit **șapte** defecte reale, toate în cazuri compuse:

1. **Buclele rAF se înmulțeau.** `foiDeschise` e un Set de modul, dar `tineReperul()` n-avea
   gardă de re-intrare: fiecare foaie deschisă *peste* alta (foaia taskului → „Alege ziua",
   perioadă → confirmare) pornea încă un lanț, iar lanțurile nu mureau decât când se golea
   Set-ul. Măsurat de agent: 11 apeluri rAF pe cadru după zece imbricări. `ceasReper` era
   scris și niciodată citit — cod mort care ascundea exact lipsa pe care trebuia s-o acopere.
   *Reparat: un steag de re-intrare + `cancelAnimationFrame` la golire. Verificat: 37 apeluri
   în 600 ms după 6 imbricări = exact o buclă.*
2. **Clasa `iese` se punea și nu se scotea niciodată.** La o închidere întreruptă, Svelte
   reutilizează **același nod** (verificat în sursa Svelte 5.56.3), deci foaia rămânea fără
   glisare pentru totdeauna. *Reparat prin ștergerea mecanismului: garda (5) de mai jos
   acoperă și ieșirea, și intrarea.*
3. **Glisarea tăia sosirea foii.** Svelte 5 joacă tranzițiile `css:` tot prin WAAPI, deci
   `el.animate()` pe `transform` le **suprascrie**. O redimensionare venită cât foaia încă urcă
   îi curma urcarea. *Reparat: nu se glisează cât rulează orice altă animație pe element.*
4. **A doua redimensionare pornea din poziția desenată**, nu din cea de layout —
   `getBoundingClientRect` include transformul propriei glisări în zbor. Măsurat de agent:
   salturi de 93 px. *Reparat: se scade `m42` din matricea curentă.*
5. **Se adunau glisări** peste același `transform`. *Reparat: fiecare drum nou o anulează pe
   precedenta, prin `id`.*
6. **Garda de gest era unidirecțională** — oprea pornirea, dar nu anula una deja pornită.
   *Reparat: `apuca()` anulează glisarea în curs.*
7. **Pinch-zoom pornea glisări** în regim browser: `vv.height` scade fără ca `innerHeight` să
   scadă, deci formula dădea `--kb` = 483 px și 13 animații simultane. *Reparat: ce le
   deosebește nu e `--kb`, ci `vv.scale` — la tastatură rămâne 1.*

Și o corecție de metodă pentru mine: un test care confirmă cazul simplu nu spune nimic despre
cel compus. Cele mai grave două (1 și 2) apar **doar** cu foi suprapuse și închideri întrerupte
— exact ce nu încercasem.

### Glisarea scoasă: nu era reparabilă, era greșită din geometrie

A stat o zi și a trecut șapte reparații. Ion, uitându-se la ea: *„modalul parcă este tăiat, de
reușesc să văd și butonul de dedesubt de creare task."* Măsurat: **14 cadre în care foaia era
desenată sub marginea viewportului, până la 131 px** — adică exact subsolul ei, cu butonul.

Cauza nu e un defect de reglaj, ci imposibilitatea: **locul vechi al foii nu mai există pe
ecran.** Capacitor a micșorat deja WebView-ul, deci tot ce era sub noua margine de jos e în
afara suprafeței desenabile. Un FLIP desenează elementul în locul de dinainte — aici, în afara
ecranului. Nici invers nu merge (să pornească mai sus și să coboare): atunci se deschide o fâșie
între foaie și margine, prin care se vede pagina. Orice catch-up cere spațiu în afara foii, iar
foaia e lipită de margine: spațiul acela nu există în niciun sens.

Deci foaia se așază în același cadru cu viewportul, împreună cu voalul, cu butonul plutitor și
cu tot restul — un singur pas, nimic în urmă, exact ce face o suprafață nativă când i se
redimensionează fereastra. Contractul din `audit_tastatura.py` s-a inversat pe măsură: nu
„poziția glisează", ci **„nicio foaie nu e desenată niciun cadru sub marginea viewportului"**.

Singurul mod real de a face mișcarea lină e ca **redimensionarea însăși** să fie lină, iar asta
se decide nativ: `ViewCompat.setWindowInsetsAnimationCallback` în `MainActivity.java` (API 30+)
dă `onProgress` cu `interpolatedFraction` la fiecare cadru al IME-ului. Cât timp nimeni nu-l
instalează, insets-urile sosesc o singură dată cu valoarea finală — și atunci saltul e
informația corectă, nu un defect de ascuns.

**Lecția, a doua oară în aceeași zi:** prima reparație a fost o *scoatere* (tranzițiile de
layout) și a ținut. A doua a fost o *adăugare* (glisarea) și a produs un defect nou pe care
șapte reparații nu l-au atins, fiindcă niciuna nu punea la îndoială premisa. Când repar
adăugând un strat, întâi întreb dacă stratul poate exista.
