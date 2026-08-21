<script module>
  import { untrack as _untrack } from 'svelte'

  // Comune tuturor instantelor de Modal (vezi blocarea derularii mai jos).
  let blocari = 0
  let yBlocat = 0

  // ===== STIVA DE MODALE =====
  // Un modal poate deschide alt modal (foaia taskului -> „Alege ziua",
  // ImplPeriodModal -> ConfirmDialog, paleta peste o foaie). Pana acum toate
  // stateau pe acelasi `--z-modal`, deci ordinea de pictare venea din ordinea
  // din DOM — adica din intamplare — si nu se stia CE inchizi cu Escape.
  //
  // `varf` e nivelul celui de deasupra. Fiecare instanta isi retine nivelul
  // primit la deschidere si se compara cu el; asta e tot ce trebuie ca sa
  // stie daca ea e cea care raspunde la Escape.
  //
  // CAT TIMP EXISTA UN MODAL DESCHIS, DOCK-UL DE TELEFON COBOARA (Ion:
  // „modalul de detalii zi se ascunde o parte sub dock... vezi daca vreun modal
  // se ascunde sub dock"). Sub un voal dock-ul oricum nu face nimic, iar
  // z-indexul singur nu e o garantie: orice stramos cu transform tranzitoriu
  // (`.ruta-in`, alunecarea de ruta) face din pagina blocul de referinta al
  // voalului `fixed`, si atunci dock-ul — frate cu pagina, nu copil — picteaza
  // deasupra. Clasa de pe <html> taie problema din radacina, pentru TOATE
  // modalele deodata (toate trec pe aici); regula CSS e in global.css.
  const stiva = $state({ varf: 0 })

  // AMANDOUA SE APELEAZA DINTR-UN `$effect`, DECI SE PAZESC SINGURE.
  // `stiva.varf++` CITESTE si scrie aceeasi stare reactiva. Chemat dintr-un
  // efect, citirea devine dependenta lui, iar scrierea il re-porneste — la
  // Modal a iesit `effect_update_depth_exceeded` (si odata cu el a murit
  // Escape), la DatePicker o oscilatie tacuta nivelNou/nivelInchis care lasa
  // varful pe o valoare gresita. Garda sta AICI, in functie, nu la fiecare
  // apelant: altfel al treilea consumator o va uita din nou, si simptomul lui
  // va arata cu totul altfel decat al primilor doi.
  export function nivelNou() {
    return _untrack(() => {
      stiva.varf++
      document.documentElement.classList.add('are-modal')
      return stiva.varf
    })
  }
  export function nivelInchis() {
    return _untrack(() => {
      stiva.varf = Math.max(0, stiva.varf - 1)
      document.documentElement.classList.toggle('are-modal', stiva.varf > 0)
      return stiva.varf
    })
  }
  /** Nivelul de deasupra, reactiv — il citesc si consumatorii din afara
   *  (CommandPalette intra in aceeasi stiva). */
  export function varfulStivei() { return stiva.varf }

  // ===== INALTIMEA TASTATURII, O SINGURA DATA PENTRU TOATA APLICATIA =====
  // `100dvh` NU se micsoreaza sub tastatura in WebView-ul Capacitor (aplicatia
  // ruleaza cu `server.url` remote), deci o foaie „pe tot ecranul" isi tine
  // butoanele sub tastatura. Sursa de adevar e `visualViewport`.
  // Se scrie pe <html>, deci o pot citi si paleta, si orice alt strat.
  //
  // ===== TASTATURA SE PREVEDE, NU DOAR SE MASOARA =====
  // `visualViewport` spune cat acopera tastatura abia DUPA ce a urcat — pe
  // Android la ~250-300ms dupa focus, adica exact cand foaia tocmai s-a asezat.
  // Masurat cadru cu cadru pe „Adaugă task": foaia urca 280ms (844 -> 296),
  // sta, apoi la 306ms soseste `--kb` si o mai impinge o data 224px in 220ms,
  // timp in care i se si scurteaza inaltimea de jos. Doua sosiri pentru un
  // singur gest — Ion: „cand se deschide tastatura sa fie frumos, nu rupt".
  // Inaltimea tastaturii e insa aceeasi de fiecare data pe acelasi telefon.
  // Deci se TINE MINTE (localStorage) si se pune pe <html> INAINTE ca foaia sa
  // se randeze: voalul se naste cu podeaua ridicata, foaia urca o singura data,
  // direct la locul ei, in acelasi timp cu tastatura care urca nativ dedesubt.
  // Cand vine masuratoarea reala, ea bate prevederea (de obicei e identica).
  // Daca tastatura NU vine deloc (tastatura fizica, focus pierdut), prevederea
  // expira si adevarul se reia — o foaie ridicata deasupra unei tastaturi care
  // nu exista ar fi mai rau decat saltul pe care il repara.
  const CHEIE_KB = 'pif-kb'
  let kbStiut = 0
  try { kbStiut = parseInt(localStorage.getItem(CHEIE_KB) || '', 10) || 0 } catch (_) {}
  let prevazut = false
  let ceasPrevedere = null
  const vv = typeof window !== 'undefined' ? (window.visualViewport || null) : null

  function scrieKb(kb) {
    const html = document.documentElement
    html.style.setProperty('--kb', kb + 'px')
    // Clasa spune „tastatura e sus" acolo unde o variabila nu poate conditiona
    // nimic: insetul de siguranta de jos nu mai are sens sub tastatura (ea il
    // acopera), iar toastul trebuie sa urce deasupra ei.
    html.classList.toggle('are-tastatura', kb > 0)
  }

  function scrie(e) {
    if (!vv) return
    const kb = Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop))
    // Cat timp prevederea e in vigoare, un `scroll` al viewportului (focusul
    // care aduce campul la vedere) nu o strica: tastatura inca urca. Doar un
    // `resize` spune adevarul despre ea, in ambele sensuri.
    if (prevazut && kb === 0 && e?.type !== 'resize') return
    if (kb > 0 || e?.type === 'resize') {
      prevazut = false
      clearTimeout(ceasPrevedere)
    }
    if (kb > 0 && kb !== kbStiut) {
      kbStiut = kb
      try { localStorage.setItem(CHEIE_KB, String(kb)) } catch (_) {}
    }
    scrieKb(kb)
  }

  if (vv) {
    vv.addEventListener('resize', scrie)
    vv.addEventListener('scroll', scrie)
    scrie()
  } else if (typeof document !== 'undefined') {
    // Fara `visualViewport` variabila trebuie sa EXISTE, altfel `calc()`-urile
    // care o scad cad pe invalid si inaltimea foii dispare cu totul.
    scrieKb(0)
  }

  /** Cat tine tastatura foaia ridicata, ACUM, in px. */
  function kbAcum() {
    if (typeof document === 'undefined') return 0
    return parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--kb')) || 0
  }

  /** Ridica podeaua la inaltimea STIUTA a tastaturii, inainte ca ea sa urce.
   *  Intoarce cat a prevazut (0 = nimic de prevazut: nu stim inca inaltimea,
   *  sau tastatura e deja sus). Expira singura daca masuratoarea nu vine. */
  export function prevedeTastatura() {
    if (!kbStiut || typeof document === 'undefined' || kbAcum() > 0) return 0
    prevazut = true
    scrieKb(kbStiut)
    clearTimeout(ceasPrevedere)
    ceasPrevedere = setTimeout(() => {
      if (!prevazut) return
      prevazut = false
      if (vv) scrie({ type: 'resize' })
      else scrieKb(0)
    }, 1200)
    return kbStiut
  }

  /** Prevederea se retrage cand foaia care a cerut-o pleaca fara ca tastatura
   *  sa fi venit; altfel urmatoarea foaie s-ar naste ridicata degeaba. */
  export function uitaPrevederea() {
    if (!prevazut) return
    prevazut = false
    clearTimeout(ceasPrevedere)
    if (vv) scrie({ type: 'resize' })
    else scrieKb(0)
  }

  // Ultima apasare pe ecran — partajata de TOATE instantele. Fiecare modal o
  // citeste cand se deschide ca sa creasca din punctul unde ai atins.
  let ultimaApasare = { x: 0, y: 0, cand: 0 }
  if (typeof window !== 'undefined') {
    window.addEventListener('pointerdown', (e) => {
      ultimaApasare = { x: e.clientX, y: e.clientY, cand: Date.now() }
    }, { capture: true, passive: true })
  }
</script>

<script>
  import { tick, untrack } from 'svelte'
  import { X } from '@lucide/svelte'
  import { fade, scale } from 'svelte/transition'
  import { motionDuration, DUR_FAST, DUR_BASE, DUR_SLOW, DUR_ARC, EASE, EASE_IESIRE, ARC } from '../../lib/motion.svelte.js'
  import { ecran } from '../../lib/ecran.svelte.js'
  // Foaia si voalul ies in `body`: pagina din spate se RETRAGE (un `transform`
  // pe invelisul ei), iar un obiect dinauntrul acelui invelis s-ar micsora
  // odata cu ce acopera. Vezi nota din `lib/portal.js`.
  import { portal } from '../../lib/portal.js'

  function origineaCasetei(node) {
    const a = ultimaApasare
    if (!a.cand || Date.now() - a.cand > 600) return ''
    const r = node.getBoundingClientRect()
    if (!r.width || !r.height) return ''
    const px = ((a.x - r.left) / r.width) * 100
    const py = ((a.y - r.top) / r.height) * 100
    // Peste distanta asta originea nu mai ajuta, incurca: o casetă care creste
    // dintr-un punct aflat departe in afara ei se citeste ca o zvacnire, nu ca
    // o legatura cu ce ai atins.
    if (px < -120 || px > 220 || py < -120 || py > 220) return ''
    return `${px.toFixed(1)}% ${py.toFixed(1)}%`
  }
  import { PRAG_INCHIDE, PRAG_INTINDE, PRAG_DIRECTIE, puls, urmaritor } from '../../lib/gesturi.js'

  // `onclose` se cheama DOAR cand utilizatorul inchide (X, fundal, Escape, tras in
  // jos) — nu cand parintele pune `open = false` singur. Exista fiindca un modal de
  // scriere (notita) pierdea tot ce ai tastat la un click pe fundal: `onBackdrop`
  // stingea `open` si atat, fara sa intrebe si fara sa salveze. Cine deschide un
  // editor decide ce inseamna „am inchis" (la notite: salveaza, cu „Anulează" in
  // toast); cine deschide un formular poate sa nu dea nimic si sa se comporte ca
  // pana acum.
  // `inalt`: foaia se deschide DIRECT intinsa (aproape tot ecranul). Pentru
  // continut care nu incape niciodata intr-o jumatate de foaie — panoul zilei
  // din Calendar (Ion: „fa-l sa se deschida tot timpul aproape pe toata
  // pagina, ca sa incapa deodata toate detaliile"). Gestul de tras in jos
  // inchide, ca oricand.
  // `iesireGest`: PE TELEFON foaia asta nu mai are `X` in colt — iesirea e
  // gestul (tragi in jos de oriunde din continut) plus butonul „inapoi" de pe
  // Android, care ajunge aici ca Escape prin `main.js`. Se cere EXPLICIT, si nu
  // se aplica singura peste tot: intr-o foaie cu campuri, cu tastatura sus,
  // gestul din continut e oprit dinadins (vezi `tastaturaSus`) si atunci `X`-ul
  // chiar e singura iesire vizibila. Pe desktop nu schimba nimic — acolo coltul
  // e la un centimetru de cursor, nu la celalalt capat al mainii.
  // `cuTastatura`: foaia isi focalizeaza singura un camp la deschidere, deci
  // tastatura VINE sigur. Atunci podeaua se ridica dinainte, la inaltimea stiuta
  // a tastaturii (vezi `prevedeTastatura` in <script module>), ca foaia sa urce o
  // singura data. Se cere explicit: o foaie din care doar alegi nu are de ce sa
  // se nasca ridicata.
  let { open = $bindable(false), title = '', size = 'md', inalt = false, iesireGest = false, cuTastatura = false, children, footer, onclose } = $props()
  let backdropEl = $state(null)
  let previousFocus = $state(null)
  let corpEl = $state(null)

  // Nivelul din stiva, primit la deschidere. `varf` spune daca ASTA e cea de
  // deasupra — deci cea care raspunde la Escape si la clicul pe fundal.
  let nivel = $state(0)
  const varf = $derived(nivel > 0 && nivel === stiva.varf)

  // Pe telefon modalul e un SHEET lipit de marginea de jos, nu o caseta centrata:
  // acolo ajunge degetul mare fara sa muti mana, si acolo se asteapta gestul de
  // inchidere. Deci si intrarea trebuie sa vina de jos — un `scale` din centru
  // spune „fereastra", nu „sertar".
  const sheet = $derived(ecran.telefon)

  // Documentul isi tine singur geometria (`.modal-doc`: ecran plin, corp care nu
  // deruleaza, pagina dinauntru cu scroll propriu), deci nu intra in masinaria
  // treptelor — ar fi doua reguli peste aceeasi inaltime. Gestul de coborare il
  // are si el: `trasY` merge pe orice foaie.
  const cuTrepte = $derived(sheet && size !== 'doc')

  // Foaia de dedesubt, cand peste ea s-a deschis alta. Vezi `.acoperit` in CSS.
  const acoperit = $derived(nivel > 0 && nivel < stiva.varf)

  // UN DETALIU, O COMPONENTA: panou lateral pe desktop, foaie de jos pe telefon.
  // Acelasi continut, aceeasi ordine — se schimba doar unde se asaza.
  //
  // Modul asta lipsea din sistem: `size` avea sm/md/lg/xl/wide/zoom/doc, toate
  // casete centrate, deci regula din directie n-avea cu ce sa fie respectata si
  // fiecare detaliu se deschidea ca fereastra. O caseta centrata iti pune
  // continutul peste locul din care ai venit; un panou la margine il lasa la
  // vedere, si tocmai asta face diferenta cand editezi o perioada uitandu-te la
  // lista din care ai deschis-o.
  const panou = $derived(size === 'panou' && !sheet)

  // Cat timp sheet-ul e deschis, pagina de dedesubt nu se mai misca. Fara asta,
  // derularea continua in pagina din spate cand ajungi la capatul continutului din
  // sheet — iesi din modal si ai pierdut si locul din lista.
  //
  // Doar pe telefon: pe desktop pagina din spate se derula dintotdeauna si nimic
  // nu se pierde, iar `position: fixed` pe body langa `scrollbar-gutter: stable`
  // introduce un salt lateral pe care n-are rost sa-l platim.
  //
  // Contorul e pentru cazul in care doua sheet-uri sunt deschise in acelasi timp:
  // al doilea ar citi `scrollY` deja blocat (0) si, la inchidere, ar „restaura"
  // pagina la inceput. Blocheaza primul, deblocheaza ultimul.
  $effect(() => {
    if (!open || !sheet) return
    const b = document.body
    if (blocari === 0) {
      yBlocat = window.scrollY
      b.style.position = 'fixed'
      b.style.top = `-${yBlocat}px`
      b.style.width = '100%'
    }
    blocari++
    return () => {
      blocari--
      if (blocari > 0) return
      // DEBLOCAREA ASTEAPTA SFARSITUL IESIRII. Se elibera in acelasi tact cu
      // `open = false`, deci `window.scrollTo(0, yBlocat)` repozitiona pagina din
      // spate CAT TIMP foaia era inca pe ecran: fundalul sarea sub o foaie care
      // tocmai cobora. Nu se vede in demonstratie, dar pe telefon e primul lucru
      // pe care il observi. Se recontroleaza `blocari` la capat: intre timp poate
      // fi deschisa alta foaie, si atunci pagina trebuie sa ramana blocata.
      setTimeout(() => {
        if (blocari > 0) return
        b.style.position = ''
        b.style.top = ''
        b.style.width = ''
        window.scrollTo(0, yBlocat)
      }, motionDuration(DUR_BASE))
    }
  })

  // Sheet-ul urca de sub marginea ecranului, indiferent cat de inalt e — `fly` ar
  // avea nevoie de o distanta in px, iar aceeasi distanta arata „sarit de jos" pe
  // un sheet scund si „abia miscat" pe unul inalt. Procentul e din propria inaltime,
  // deci pornirea e mereu exact sub margine.
  // O CASETA SI VOALUL EI NU POT AVEA DOUA CEASURI.
  //
  // Voalul foloseste `EASE` (vezi `transition:fade` din markup), caseta ramasese
  // pe implicitul lui `scale` — `cubicOut`. Sunt curbe diferite, deci in prima
  // treime voalul se intuneca vizibil inaintea casetei pe care o tine, si
  // amandoua se opresc in acelasi moment: obiectul pare ca vine DUPA umbra lui.
  // E aceeasi scapare pe care tura 8 a reparat-o la `fade`/`sosire`/`plecare`
  // (`--ease` era respectata peste tot in CSS si de nicio tranzitie Svelte);
  // `scale` n-a fost pe lista atunci fiindca `fly` si `slide` — verificate —
  // aveau deja `cubicOut`, si a fost pus in aceeasi galeata fara sa fie deschis.
  // Perechea din contractul de miscare: foaia INTRA pe 280 (suprafata) si IESE
  // pe 220 (element) — sosirea se vede, plecarea nu te tine. `transition:` da
  // acelasi obiect ambelor sensuri, deci sensul se citeste din faza: la intrare
  // Svelte cheama functia cu `direction: 'in'`.
  function intra(node, _params, opts) {
    const laIntrare = opts?.direction !== 'out'
    const duration = motionDuration(sheet && laIntrare ? DUR_SLOW : DUR_BASE)
    // SOSIREA FRANEAZA, PLECAREA ACCELEREAZA. Pana acum amandoua mergeau pe
    // `--ease`, deci foaia se retragea ca si cum s-ar razgandi: incetinea exact
    // in intervalul in care trebuia sa fie deja plecata. Vezi `--ease-iesire`.
    const curba = laIntrare ? EASE : EASE_IESIRE
    if (sheet) {
      // CAT PLEACA, FOAIA NU MAI ASCULTA DE TASTATURA.
      //
      // Foaia de adaugare vine intotdeauna cu tastatura (campul se focalizeaza
      // singur), iar inchiderea ia focusul — deci tastatura pleaca in ACEEASI
      // clipa cu foaia. Pana aici, doua lucruri se intamplau atunci deodata:
      //   1. `--kb` cadea la 0, iar `max-height`-ul foii (care il scade) NU e
      //      tranzitionat — deci foaia se INTINDEA instant (masurat: 520 -> 550
      //      intr-un cadru), fix in clipa in care trebuia sa plece;
      //   2. voalul isi anima `padding-bottom` 300 -> 0, adica IMPINGEA foaia in
      //      jos pe curba LUI, peste plecarea ei, pe curba EI.
      // Rezultatul: o plecare care se intinde si accelereaza, si care arata
      // altfel cu tastatura decat fara — acelasi gest, alta miscare.
      //
      // Se citeste inaltimea tastaturii O SINGURA DATA, la plecare, si se
      // ingheata pe voal. Fiind proprietate custom, valoarea se mosteneste in
      // tot subarborele modalului, deci si `max-height`-ul foii ramane pe loc.
      // Voalul se recreeaza la fiecare deschidere (e sub `{#if open}`), deci
      // inghetul nu supravietuieste in deschiderea urmatoare.
      //
      // Si atunci plecarea trebuie sa duca singura tot drumul: `100%` e exact
      // distanta pana jos DOAR cand foaia sta pe marginea de jos a ecranului. Cu
      // tastatura sus e cu `--kb` mai sus, deci ii lipseau exact atatia pixeli —
      // pe care ii lua din voal. Acum si-i ia din propria miscare.
      // Se citeste de la INCHIDERE, nu de la pornirea iesirii: intre ele trec
      // cateva cadre, si daca aparatul raporteaza plecarea tastaturii mai
      // devreme (unele o raporteaza dintr-o data, altele treptat), aici ar
      // ajunge deja 0 si n-ar mai fi nimic de inghetat. `kbAcum()` ramane
      // rezerva pentru inchiderile venite din afara, care nu trec prin
      // `inchide()`.
      // LA INTRARE, daca podeaua e deja ridicata (tastatura prevazuta sau deja
      // sus), drumul porneste tot de sub marginea ECRANULUI, nu de sub marginea
      // podelei: foaia urca prin locul tastaturii care urca si ea, in acelasi
      // timp — o singura miscare, nu doua. Nu se ingheata nimic la intrare:
      // masuratoarea reala trebuie sa poata inca sa corecteze prevederea.
      const kb = laIntrare ? kbAcum() : (kbLaInchidere ?? kbAcum())
      if (!laIntrare && kb && backdropEl) backdropEl.style.setProperty('--kb', kb + 'px')
      return {
        duration, easing: curba,
        css: (t, u) => `transform: translateY(calc(${u * 100}% + ${u * kb}px))`,
      }
    }
    // PANOUL SOSESTE CU 8px, NU CU O SCALARE. Scalarea spune „fereastra care se
    // deschide din centru"; panoul vine dinspre marginea de care se lipeste, deci
    // o deplasare mica, pe axa lui. Distanta e mica cu bunastiinta: obiectul e
    // deja la locul lui, miscarea doar spune din ce parte a venit.
    if (panou) return { duration, easing: curba, css: (t, u) => `opacity: ${t}; transform: translateX(${u * 8}px)` }
    // Caseta: creste din declansator daca exista unul, altfel din centru.
    // ARC pe scalare (se misca in spatiu), `--ease` pe opacitate — regula
    // `spatial` / `effects` din tokens.
    const org = origineaCasetei(node)
    if (org) node.style.transformOrigin = org
    // La INCHIDERE caseta nu mai are de ce sa creasca pe arc: arcul e pentru un
    // obiect care soseste si se aseaza. Pleaca pe durata de element, cu curba de
    // iesire pe amandoua canalele.
    if (!laIntrare) {
      return { duration, easing: EASE_IESIRE, css: (t) => `opacity: ${t}; transform: scale(${0.98 + 0.02 * t});` }
    }
    return {
      duration: motionDuration(DUR_ARC),
      easing: (t) => t,
      css: (t) => `opacity: ${EASE(t)}; transform: scale(${0.96 + 0.04 * ARC(t)});`,
      // Originea se sterge la final: lasata acolo, ar ramane pe casetă si
      // pentru INCHIDERE, care se joaca din alt punct decat s-a deschis.
      tick: (t) => { if (t === 1) node.style.transformOrigin = '' },
    }
  }

  // ===== TRAGEREA SHEET-ULUI (telefon) — TREPTE, NU UN PRAG =====
  // Ion: „nu poate fi tras pe tot ecranul, nu poti sa-l tragi inapoi, doar prin x".
  // Manerul era pana atunci DECOR: un dreptunghi care arata a maner si nu facea
  // nimic. Prima reparatie i-a dat gestul, dar l-a facut cu SENS UNIC: trageai in
  // sus peste un prag si foaia se intindea pentru totdeauna — de acolo incolo,
  // tras in jos insemna doar „inchide". Adica jumatatea a doua a reprosului („nu
  // poti sa-l tragi inapoi") a ramas in picioare, doar ca mai greu de vazut.
  //
  // Acum foaia are TREPTE si drumul e continuu in amandoua sensurile. UN SINGUR
  // SCALAR conduce tot gestul: cat din foaie se vede. Peste treapta de baza
  // degetul CRESTE foaia (marginea de jos ramane lipita de ecran, cea de sus
  // urmeaza degetul); sub ea, foaia COBOARA intreaga spre inchidere. Nu mai sunt
  // doua gesturi cu doua mecanisme — unul pe inaltime, altul pe deplasare — ci
  // unul singur cu doua jumatati, si de aceea nu mai poate exista o stare din
  // care sa nu existe drum inapoi.
  //
  // Deplasarea merge pe proprietatea `translate`, NU pe `transform`: tranzitiile
  // Svelte de intrare/iesire scriu `transform` inline pe acelasi nod, iar doua
  // surse pe aceeasi proprietate s-ar suprascrie. `translate` e o proprietate
  // separata, deci cele doua se compun in loc sa se bata.
  //
  // INALTIMEA IN PIXELI E DOAR A GESTULUI. Cat timp degetul e pe ecran foaia
  // primeste o inaltime in px (`--h-foaie`); la ridicare o preda inapoi CSS-ului,
  // care o tine in `dvh` minus tastatura. O valoare in px n-ar sti sa se stranga
  // cand urca tastatura — si tocmai foaia „pe tot ecranul" trebuie sa faca asta
  // (vezi nota lunga de la `--kb`).
  let trasY = $state(0)
  let hFoaie = $state(null)     // inaltimea ceruta in timpul gestului, in px
  let trage = $state(false)
  let intins = $state(false)    // pe treapta de sus (ecran plin)
  let voalP = $state(1)         // opacitatea voalului, 0..1 — urmareste degetul
  let sheetEl = $state(null)
  let idPointer = null
  let pragTrecut = false

  // Starea gestului — `let` simplu: nu se citeste la randare, deci n-are ce
  // cauta in `$state` (o scriere pe cadru ar invalida degeaba componenta).
  let trepte = [0]
  let treapta = 0
  let hBaza = 0
  let hApucat = 0
  let yApucat = 0
  let totalAcum = 0
  let ceasPredare = null
  const vit = urmaritor()

  /** Inaltimea maxima pe care o poate lua foaia. Se MASOARA din voal, nu se
   *  recalculeaza formula din CSS: doua formule pentru acelasi lucru se
   *  desincronizeaza tacut, iar atunci gestul promite o inaltime pe care
   *  randarea o refuza — exact greseala reparata la manerul panoului.
   *  Voalul e `inset: 0` cu `padding-bottom: var(--kb)`, deci caseta lui de
   *  continut E fix spatiul in care incape foaia. */
  function plafonPlin() {
    if (!backdropEl) return window.innerHeight
    const jos = parseFloat(getComputedStyle(backdropEl).paddingBottom) || 0
    return Math.max(1, backdropEl.clientHeight - jos)
  }

  /** Are foaia ce sa arate in plus daca o intinzi? Daca nu, treapta de sus nici
   *  nu exista, si gestul in sus se opreste in arc. O foaie care se intinde ca
   *  sa descopere spatiu gol promite un continut care nu e acolo — aceeasi
   *  greseala ca manerul-decor, doar la alta scara. */
  function poateCreste() {
    if (inalt) return true
    if (!corpEl) return false
    return corpEl.scrollHeight - corpEl.clientHeight > 4
  }

  function reimprospateazaTrepte() {
    const plin = plafonPlin()
    if (inalt) {
      // Foaia care se deschide deja intinsa capata o treapta de MIJLOC: de acolo
      // se vede si ce e dedesubt, fara s-o inchizi. Pana acum singurul drum
      // inapoi din ea era inchiderea.
      trepte = [Math.round(plin * 0.55), plin]
      return
    }
    // Pe treapta de baza inaltimea se RE-MASOARA la fiecare apucare: continutul
    // se poate schimba cat foaia e deschisa (subtaskuri sosite, un camp aparut),
    // si atunci o valoare retinuta de la gestul trecut ar fi treapta altei foi.
    if (treapta === 0 && hFoaie === null) hBaza = sheetEl?.offsetHeight || 0
    trepte = poateCreste() ? [hBaza, plin] : [hBaza]
  }

  /** Cat din foaie se vede acum — punctul de plecare al gestului. */
  function inaltimeVizibila() {
    return Math.max(0, (sheetEl?.offsetHeight || 0) - trasY)
  }

  function apuca(clientY) {
    untrack(reimprospateazaTrepte)
    hApucat = inaltimeVizibila()
    yApucat = clientY
    totalAcum = hApucat
    vit.porneste(hApucat)
    pragTrecut = false
    trage = true
  }

  /** `total` = cat din foaie se vede. Singurul lucru pe care il misca degetul. */
  function aseaza(total) {
    totalAcum = total
    vit.adauga(total)
    const h0 = trepte[0]
    const hMax = trepte[trepte.length - 1]
    let v = total
    if (v > hMax) {
      // CAPATUL DE SUS CEDEAZA, NU E ZID. Un `Math.max` sec se citeste ca
      // interfata blocata; o rezistenta care creste cu distanta spune „aici e
      // capatul" si se intoarce singura cand dai drumul.
      v = hMax + Math.min(30, Math.pow(v - hMax, 0.72))
    }
    if (v >= h0) {
      trasY = 0
      if (cuTrepte) hFoaie = Math.round(v)
      voalP = 1
    } else {
      if (cuTrepte) hFoaie = Math.round(h0)
      trasY = h0 - v
      // VOALUL URMARESTE DEGETUL. Cat timp foaia coboara, opacitatea scade odata
      // cu ea: vezi cat mai ai pana pierzi ce ai deschis, deci gestul e
      // reversibil cu OCHII, nu doar cu degetul.
      voalP = Math.max(0, Math.min(1, v / h0))
    }
    // Pragul se ANUNTA, ca la rand: degetul acopera manerul, deci confirmarea
    // care nu se vede se simte. O singura data per trecere, nu la fiecare cadru.
    const trecut = v < h0 * (1 - PRAG_INCHIDE)
    if (trecut !== pragTrecut) {
      pragTrecut = trecut
      if (trecut) puls()
    }
  }

  function lasa() {
    if (!trage) return
    trage = false
    idPointer = null
    const h0 = trepte[0]
    // NU pozitia in care s-a oprit degetul, ci UNDE AR FI AJUNS daca ar mai fi
    // continuat putin. Asa o aruncare scurta si iute si o tragere lunga si
    // lenesa ajung la aceeasi concluzie — adica exact ce asteapta mana.
    const proiectat = vit.proiectat(totalAcum)
    if (proiectat < h0 * (1 - PRAG_INCHIDE)) {
      // `trasY` RAMANE unde l-a lasat degetul. Zeroit aici, doua miscari s-ar
      // compune pe acelasi obiect in sensuri opuse: revenirea spre 0 CU ARC, in
      // timp ce tranzitia de iesire coboara foaia cu toata inaltimea ei. Prima
      // jumatate a iesirii s-ar anula singura — se citeste exact ca lag.
      inchide()
      return
    }
    let cel = 0, dMin = Infinity
    trepte.forEach((h, i) => {
      const d = Math.abs(h - proiectat)
      if (d < dMin) { dMin = d; cel = i }
    })
    if (cel !== treapta) puls(8)
    duLaTreapta(cel)
  }

  /** Aseaza foaia pe o treapta si PREDA inaltimea inapoi CSS-ului. */
  function duLaTreapta(i) {
    treapta = i
    trasY = 0
    voalP = 1
    intins = trepte.length > 1 && i === trepte.length - 1
    if (!cuTrepte) return
    clearTimeout(ceasPredare)
    if (intins || inalt) {
      // Amandoua treptele astea au o clasa care le da inaltimea in `dvh`, deci
      // px-ul se poate lasa imediat: tranzitia merge intre doua valori calculate.
      hFoaie = null
      return
    }
    // Treapta de baza e `height: auto`, iar spre `auto` nu se poate anima. Se
    // tine valoarea in px cat tine tranzitia, apoi se preda — la aceeasi
    // inaltime, deci fara salt, dar de acolo incolo foaia urmeaza continutul.
    hFoaie = trepte[0]
    ceasPredare = setTimeout(() => {
      if (!trage && treapta === 0) hFoaie = null
    }, motionDuration(DUR_BASE) + 40)
  }

  // Se trage de TOT ANTETUL, nu de bara de 4px. Ion: „pot sa ridic doar daca tin
  // apasat bara aia de sus, nu este prea comod".
  function trageJos(e) {
    if (!sheet || e.pointerType === 'mouse') return
    idPointer = e.pointerId
    apuca(e.clientY)
    try { e.currentTarget.setPointerCapture?.(e.pointerId) } catch (_) {}
  }

  function trageMisca(e) {
    if (!trage || e.pointerId !== idPointer) return
    aseaza(hApucat - (e.clientY - yApucat))
  }

  function trageSus(e) {
    if (!trage || e.pointerId !== idPointer) return
    lasa()
  }

  // La fiecare deschidere pornim din starea de baza, nu din treapta foii
  // dinainte. `trasY` nu se zeroeaza la ridicarea degetului (vezi `lasa`), deci
  // se zeroeaza aici.
  // `untrack`: inauntru se si citesc, si se scriu stari reactive (`treapta` e
  // citita de `reimprospateazaTrepte` si scrisa aici) — fara el efectul s-ar
  // re-porni singur, greseala pe care fisierul asta a facut-o deja o data la
  // stiva de niveluri si o are scrisa in `<script module>`.
  /** Cat s-a prevazut pentru tastatura la deschiderea ASTEIA. */
  let kbPrevazut = 0

  // ===== UN CLIC CONTEAZA DOAR DACA A INCEPUT PE FOAIE =====
  // Foaia de actiuni soseste SUB deget, la apasare lunga. Ridicarea degetului
  // produce un `click` — iar el aterizeaza pe ce e acum sub deget: un rand al
  // foii („Șterge" sta ultimul, exact unde se odihneste degetul pe un rand de
  // jos) sau voalul (care inchide). Masurat: foaia se deschidea la 439ms si se
  // inchidea singura la 657ms, la ridicare. Pe Android, clicul lipseste doar
  // daca tii pana la pragul nativ de 500ms; intre pulsul de la 420 si 500 e un
  // clic adevarat. Deci regula: un clic in foaie e al foii numai daca si
  // apasarea a fost in foaie. Enter de la tastatura are `detail === 0` si trece.
  let apasatInauntru = false
  function pazesteClic(e) {
    if (apasatInauntru || e.detail === 0) return
    e.preventDefault()
    e.stopPropagation()
  }

  // `$effect.pre`, nu `$effect`: STAREA DE PORNIRE TREBUIE SA EXISTE INAINTE DE
  // PRIMUL CADRU. Pusa dupa randare, clasa `intins` a foii `inalt` sosea un tact
  // dupa ce tranzitia Svelte citise deja stilurile foii (ceea ce forteaza un
  // recalcul) — deci `height` TRANZITIONA de la inaltimea continutului la ecranul
  // plin, in acelasi timp cu urcarea. Masurat pe foaia zilei: 464 -> 844px in
  // 300ms, sub o foaie care tocmai urca. Doua miscari pe acelasi obiect.
  // Tot aici se ridica podeaua pentru tastatura: si ea trebuie sa fie la locul
  // ei inainte ca voalul sa se nasca, altfel ar fi a doua sosire.
  $effect.pre(() => {
    if (!open) return
    untrack(() => {
      trasY = 0
      voalP = 1
      hFoaie = null
      treapta = 0
      intins = sheet && inalt
      apasatInauntru = false
      if (sheet && cuTastatura) kbPrevazut = prevedeTastatura()
    })
  })

  $effect(() => {
    if (!open) return
    untrack(() => {
      if (!sheet) return
      reimprospateazaTrepte()
      // `inalt` sta DIRECT pe treapta de sus — fara `hFoaie`, deci fara
      // tranzitie: inaltimea vine din clasa, adica e buna din primul cadru.
      if (inalt && trepte.length > 1) treapta = trepte.length - 1
    })
    // Ceasul de predare a inaltimii nu are voie sa supravietuiasca foii: ar
    // scrie pe starea unei componente inchise.
    return () => {
      clearTimeout(ceasPredare)
      // Foaia a plecat: daca tastatura prevazuta n-a venit intre timp,
      // prevederea se retrage odata cu ea.
      if (kbPrevazut) { kbPrevazut = 0; uitaPrevederea() }
    }
  })


  // Intrarea in stiva (si semnalul pentru dock) — cu curatare, deci si
  // inchiderea, si distrugerea componentei cu modalul deschis o scad corect.
  // Singura dependenta urmarita aici e `open`: `nivelNou`/`nivelInchis` isi
  // poarta propriul `untrack` (vezi nota din `<script module>`).
  $effect(() => {
    if (!open) return
    nivel = nivelNou()
    return () => { nivelInchis(); nivel = 0 }
  })

  // INTINDEREA VINE SI DIN CONTINUT, nu doar din antet (Ion, 2026-08-10, pe
  // foaia zilei din Calendar: „nu pot ridica de tot ca sa vad toate detaliile").
  // Gestul natural e sa tragi de CE VEZI — adica de continut — dar acolo
  // ascultatorul de tragere nu exista, fiindca degetul trebuie sa poata DERULA.
  // Compromisul: o glisare in sus pe corp INTINDE foaia (o singura data, fara
  // preventDefault — derularea continua nestingherita sub acelasi deget; foaia
  // doar creste in timp ce derulezi). Inchiderea ramane pe antet, unde gestul
  // in jos nu se bate cu nimic.
  // TREI GARZI, fiecare pentru un fel de fals-pozitiv (T1c):
  //  - gestul porneste DOAR din capul listei (`scrollTop === 0`), altfel
  //    derularea normala a subtaskurilor intindea foaia sub deget;
  //  - pragul urca de la 24 la 56px, ca o derulare scurta sa nu se citeasca
  //    drept intindere;
  //  - cat timp tastatura e sus nu se intinde nimic: foaia tocmai s-a
  //    micsorat ca sa-i faca loc, iar o intindere ar duce-o inapoi sub ea.
  //
  // …SI INCHIDEREA VINE TOT DIN CONTINUT (tura 16). Ion, despre foaia zilei din
  // Calendar: „X-ul de inchidere din colt, pe mobil e incomod, nu l-am folosit
  // niciodata; pana acum am inchis din gestul inapoi pe Android."
  // Are dreptate, si nu e o chestiune de gust: pe un telefon inalt coltul de sus
  // e singurul loc de pe ecran la care nu ajungi fara sa muti mana din priza.
  // Iesirea exista deja ca gest — tragi de antet in jos — dar antetul e IN
  // ACELASI COLT de neatins. Deci gestul corect nu era inventat, era doar pus
  // unde nu ajunge degetul.
  // Acum se trage de CE VEZI, oriunde in foaie, cu o singura conditie: lista sa
  // fie la capatul de sus. Aceeasi conditie care face intinderea sa nu se bata
  // cu derularea o face si pe inchidere sa nu se bata: cand mai ai continut
  // deasupra, gestul in jos inseamna „deruleaza inapoi" si atat.
  // Acelasi prag (`PRAG_INCHIDE`), acelasi puls la trecerea lui si acelasi
  // `trasY` ca la antet — un singur gest cu doua suprafete, nu doua gesturi.
  let corpY0 = 0
  let corpJos = false           // gestul din corp a devenit o inchidere

  /** Tastatura sus = esti intr-un formular, iar foaia tocmai s-a micsorat ca
   *  sa-i faca loc. Nici intindere, nici inchidere din continut: acolo degetul
   *  scrie, si `X`-ul din antet ramane iesirea (vezi `iesireGest`). */
  const tastaturaSus = () => {
    const kb = document.documentElement.style.getPropertyValue('--kb')
    return !!kb && kb !== '0px'
  }

  function corpAtinge(e) {
    corpJos = false
    corpY0 = 0
    if (!sheet || e.touches.length !== 1 || tastaturaSus()) return
    if ((corpEl?.scrollTop ?? 0) > 0) return
    corpY0 = e.touches[0].clientY
  }
  function corpTrage(e) {
    if (!sheet || !corpY0) return
    const dy = e.touches[0].clientY - corpY0
    // IN SUS — urca o treapta, o SINGURA data si FARA `preventDefault`:
    // derularea continua nestingherita sub acelasi deget, foaia doar creste in
    // timp ce derulezi. Aici, spre deosebire de antet, cresterea NU urmareste
    // degetul cadru cu cadru — s-ar bate cu scroll-ul pentru acelasi gest.
    if (!corpJos && dy < 0) {
      if (intins) { corpY0 = 0; return }
      untrack(reimprospateazaTrepte)
      if (trepte.length > 1 && dy < -trepte[0] * PRAG_INTINDE) {
        duLaTreapta(trepte.length - 1)
        corpY0 = 0
      }
      return
    }
    if (dy <= 0) return
    // IN JOS — acelasi gest ca la antet, cu aceleasi trepte, acelasi prag si
    // aceeasi proiectie de viteza. Se ia decizia o singura data, dupa
    // `PRAG_DIRECTIE`, ca la orice alt gest din aplicatie; pana atunci degetul
    // poate inca sa fie pe drum spre o derulare.
    if (!corpJos) {
      if ((corpEl?.scrollTop ?? 0) > 0) { corpY0 = 0; return }
      if (dy < PRAG_DIRECTIE) return
      corpJos = true
      // Se apuca de unde s-a DECIS directia, nu de unde a inceput atingerea:
      // altfel cei 8px de hotarare s-ar aduna la deplasare si foaia ar sari
      // sub deget in clipa in care gestul devine al ei.
      apuca(corpY0 + PRAG_DIRECTIE)
    }
    // Fara asta, browserul ar face si el ceva cu degetul (saltul de capat de
    // lista) exact cat timp foaia coboara — doua obiecte pe aceeasi axa.
    if (e.cancelable) e.preventDefault()
    aseaza(hApucat - (e.touches[0].clientY - yApucat))
  }
  function corpRidica() {
    corpY0 = 0
    if (!corpJos) return
    corpJos = false
    lasa()
  }

  // ===== REDIMENSIONAREA PANOULUI (T6, doar desktop) =====
  // Latimea traieste pe <html> ca `--panou-w`, nu in starea componentei: e o
  // preferinta a UTILIZATORULUI, nu a unei instante — foaia taskului si cea a
  // perioadei trebuie sa se deschida la aceeasi latime, iar ea supravietuieste
  // reincarcarii. Limitele sunt cele din desen: 380…720.
  const PANOU_MIN = 380
  const PANOU_MAX = 720
  const CHEIE_PANOU = 'pif-panou-w'
  let trageManer = $state(false)

  /** Plafonul REAL, aceeasi formula ca `max-width` din CSS (`min(720px, 46vw)`).
   *  Calculat, nu copiat ca numar: daca cele doua ar diverge, manerul ar promite
   *  o latime pe care randarea o refuza — si tocmai asta era greseala de reparat. */
  const panouMax = () => Math.min(PANOU_MAX, Math.round(window.innerWidth * 0.46))

  if (typeof localStorage !== 'undefined') {
    const salvat = parseInt(localStorage.getItem(CHEIE_PANOU) || '', 10)
    if (salvat >= PANOU_MIN && salvat <= PANOU_MAX) {
      document.documentElement.style.setProperty('--panou-w', salvat + 'px')
    }
  }

  function apucaManer(e) {
    if (!panou) return
    e.preventDefault()
    trageManer = true
    const laMiscare = (ev) => {
      // Panoul e lipit de marginea DIN DREAPTA, deci latimea creste cand
      // cursorul merge spre stanga.
      const w = Math.min(panouMax(), Math.max(PANOU_MIN, window.innerWidth - ev.clientX))
      document.documentElement.style.setProperty('--panou-w', Math.round(w) + 'px')
    }
    const laRidicare = () => {
      trageManer = false
      window.removeEventListener('pointermove', laMiscare)
      window.removeEventListener('pointerup', laRidicare)
      try {
        localStorage.setItem(CHEIE_PANOU,
          parseInt(document.documentElement.style.getPropertyValue('--panou-w'), 10) || '')
      } catch (_) {}
    }
    window.addEventListener('pointermove', laMiscare)
    window.addEventListener('pointerup', laRidicare)
  }

  // LISTA FACE LOC, nu se ascunde sub panou — dar numai cand mai are ce da.
  // Sub 1100px coloana de continut e deja ingusta, iar impinsul ar strange
  // exact randurile pe care panoul ar trebui sa le lase citibile.
  $effect(() => {
    if (!open || !panou) return
    const potriveste = () => document.documentElement.classList.toggle(
      'are-panou', window.innerWidth >= 1100)
    potriveste()
    window.addEventListener('resize', potriveste)
    return () => {
      window.removeEventListener('resize', potriveste)
      document.documentElement.classList.remove('are-panou')
    }
  })

  /** Cat tinea tastatura foaia in clipa in care s-a cerut inchiderea. Vezi nota
   *  lunga din `intra`. Se sterge la redeschidere, in `$effect`-ul de mai jos. */
  let kbLaInchidere = null

  /** Singurul drum de inchidere pornit de utilizator. */
  function inchide() {
    kbLaInchidere = kbAcum()
    open = false
    onclose?.()
  }

  $effect(() => { if (open) kbLaInchidere = null })

  function onBackdrop(e) {
    // Doar varful stivei raspunde: cu doua foi deschise, un clic pe fundal
    // trebuie sa inchida CE VEZI, nu tot teancul.
    if (!varf) return
    if (e.target === e.currentTarget) inchide()
  }

  // CE POATE PRIMI FOCUS CU ADEVARAT.
  // `querySelectorAll` intoarce si butoanele dezactivate, si pe cele dintr-un
  // strat ascuns cu `display: none` — iar amandoua rup lucruri diferite:
  //
  //  - un buton DEZACTIVAT la coada listei („Creează proiectul", cat timp
  //    numele e gol) nu poate fi niciodata `activeElement`, deci conditia de
  //    intoarcere a capcanei nu se indeplineste NICIODATA si Tab pleaca in
  //    pagina de sub voal (masurat: al 7-lea Tab ajungea pe dock);
  //  - `ConfirmDialog` ascunde antetul pe desktop, deci primul „focusabil" din
  //    DOM e chiar `.modal-close` nerandat. `focus()` pe el nu face nimic si nu
  //    raporteaza nimic, deci focusul ramanea AFARA, pe butonul care deschisese
  //    dialogul — iar Escape, ascultat pe backdrop, nu mai ajungea nicaieri.
  //    Exact dialogul care scrie „Nu se poate anula" era cel din care nu se
  //    putea iesi de la tastatura.
  const SELECTOR_FOCUS = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  function focusabile() {
    if (!backdropEl) return []
    return [...backdropEl.querySelectorAll(SELECTOR_FOCUS)].filter(el =>
      !el.disabled &&
      el.getAttribute('aria-disabled') !== 'true' &&
      el.tabIndex !== -1 &&
      // `getClientRects()` gol = nerandat (display:none, stramos ascuns).
      // Nu folosim `offsetParent`, care e null si pentru `position: fixed`.
      el.getClientRects().length > 0)
  }

  function onKey(e) {
    if (e.key !== 'Tab' || !backdropEl) return
    const f = focusabile()
    if (f.length === 0) return
    const first = f[0]
    const last = f[f.length - 1]
    // Focusul poate fi in afara (o inchidere care a mutat DOM-ul sub el):
    // atunci Tab il aduce inapoi, in loc sa-l lase sa plece mai departe.
    if (!backdropEl.contains(document.activeElement)) {
      e.preventDefault()
      ;(e.shiftKey ? last : first).focus()
      return
    }
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }

  // ESCAPE ASCULTA PE FEREASTRA, NU PE VOAL.
  // Legat de backdrop, functiona doar cat timp focusul era inauntru — deci
  // exact in cazurile in care ceva mersese prost, tasta murea. Pe fereastra
  // merge intotdeauna, iar regula „doar varful" o tine `varf`.
  // `DatePicker` asculta pe CAPTURA si opreste propagarea, deci calendarul
  // deschis peste o foaie se inchide singur, fara sa inchida si foaia — si
  // butonul fizic „inapoi" de pe Android (`main.js`, Escape sintetic cu
  // `bubbles: true`) ajunge acum aici oricare ar fi elementul focalizat.
  function peEscape(e) {
    if (e.key !== 'Escape' || !open || !varf) return
    inchide()
  }

  $effect(() => {
    if (open) {
      previousFocus = document.activeElement
      tick().then(() => {
        // CINE A DESCHIS FEREASTRA POATE ALEGE UNDE CADE FOCUSUL, si atunci nu
        // i-l mai luam. Regula de aici („primul focalizabil") e buna cand nu
        // stie nimeni mai bine, dar primul din DOM e `X`-ul din antet — deci un
        // formular al carui unic camp care conteaza e titlul se deschidea cu
        // cursorul pe butonul de inchidere. Apelantul isi punea focusul (vezi
        // `openNewModal` in Tasks) si efectul de aici i-l muta inapoi, o clipa
        // mai tarziu — pe telefon asta inseamna si tastatura care se inchide la
        // loc dupa ce tocmai s-a deschis.
        if (backdropEl?.contains(document.activeElement)) return
        const f = focusabile()
        if (f.length) f[0].focus()
        else backdropEl?.focus()
      })
    } else if (previousFocus) {
      // Elementul poate sa nu mai existe (randul din care s-a deschis tocmai
      // a fost sters): atunci `focus()` ar arunca, iar `isConnected` e
      // verificarea ieftina care o previne.
      if (previousFocus.isConnected) previousFocus.focus()
      previousFocus = null
    }
  })
</script>

<!-- `<svelte:window>` nu are voie sub `{#if}` — si nici nu trebuie: `peEscape`
     iese singur cand modalul e inchis sau nu e varful stivei. -->
<svelte:window onkeydown={peEscape} />

{#if open}
  <!-- VOALUL PLEACA ODATA CU FOAIA, NU INAINTEA EI. Era stins in --dur-fast
       (120ms), cand foaia mai avea inca ~170px de coborat: ultimele doua treimi
       ale inchiderii se jucau peste o pagina deja limpede si nedimuita, ca si cum
       foaia nu mai apartinea nimanui. Voalul TINE obiectul, deci pleaca odata cu
       el sau dupa el — niciodata inainte. ACELASI ceas cu obiectul, in ambele
       sensuri: la foaie 280 la intrare / 220 la iesire (contractul de miscare),
       la restul 220. `in:`/`out:`, nu `transition:` — doar asa functia de
       tranzitie afla sensul (`direction`), ca sa aleaga durata. -->
  <div class="backdrop" class:varf class:trage use:portal bind:this={backdropEl} onclick={onBackdrop} onkeydown={onKey} role="dialog" aria-modal="true" aria-label={title} tabindex="-1"
       onpointerdowncapture={() => { apasatInauntru = true }} onclickcapture={pazesteClic}
       style:--nivel={nivel} style:--voal-p={voalP} style:z-index="calc(var(--z-modal) + (var(--nivel) - 1) * 10)"
       in:fade={{ duration: motionDuration(sheet ? DUR_SLOW : DUR_BASE), easing: EASE }}
       out:fade={{ duration: motionDuration(DUR_BASE), easing: EASE_IESIRE }}>
    <div class="modal modal-{size}" class:sheet class:intins class:inalt class:trage class:varf
         class:acoperit class:gest={hFoaie !== null} class:mijloc={sheet && inalt && !intins}
         class:se-trage={trageManer}
         bind:this={sheetEl} style:--trasY="{trasY}px" style:--h-foaie={hFoaie === null ? null : `${hFoaie}px`}
         in:intra out:intra>
      {#if panou}
        <!-- Manerul de latime. `<button>`, nu `<div>`: e un control, deci se
             vede la Tab si spune ce e. Nu are actiune la clic — tragerea ii e
             singurul rost — de aceea nu se muta focusul pe el la apasare. -->
        <button class="panou-maner" type="button" aria-label="Trage ca să schimbi lățimea panoului"
                onpointerdown={apucaManer}></button>
      {/if}
      {#if sheet}
        <span class="sheet-grip" aria-hidden="true"></span>
      {/if}
      <!-- Se trage de TOT ANTETUL, nu de bara de 4px. Ion: „pot sa ridic doar daca
           tin apasat bara aia de sus, nu este prea comod". Bara ramane semnul
           vizual; suprafata care raspunde e antetul intreg — titlu, spatiu gol si
           bara — adica vreo 80px inaltime in loc de 4. Butonul de inchidere isi
           opreste singur gestul (`onpointerdown|stopPropagation`), altfel apasarea
           pe `X` ar porni o tragere. -->
      <div class="modal-header"
           onpointerdown={trageJos} onpointermove={trageMisca}
           onpointerup={trageSus} onpointercancel={trageSus}>
        <h2 class="modal-title">{title}</h2>
        {#if !(sheet && iesireGest)}
          <button class="modal-close" onpointerdown={(e) => e.stopPropagation()} onclick={inchide} aria-label="Închide"><X size={18} /></button>
        {/if}
      </div>
      <div class="modal-body" bind:this={corpEl} ontouchstart={corpAtinge} ontouchmove={corpTrage}
           ontouchend={corpRidica} ontouchcancel={corpRidica}>
        {@render children()}
      </div>
      {#if footer}
        <div class="modal-footer">
          {@render footer()}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  /* FARA BLUR PE VOAL. Blurul a iesit din sistem odata cu redesignul — de pe
     header, dock si paleta a fost scos atunci, dar voalul modalului a ramas cu
     `blur(7px)`, adica singurul loc din aplicatie unde fondul mai e sticla.
     Un voal nu are nevoie de el: opacitatea singura desprinde caseta, iar blurul
     costa un strat de compozitare cat ecranul, animat la fiecare deschidere. */
  .backdrop {
    position: fixed;
    inset: 0;
    /* VOALUL SE PICTEAZA DOAR PE VARF. Doua voaluri de 0,65 nu dau 0,65 — dau
       0,88, deci fondul devine negru si foaia de dedesubt, care ar trebui sa
       ramana context, dispare. `z-index` vine din nivel (vezi `--nivel`). */
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: var(--z-modal);
    transition: background-color var(--dur-base) var(--ease);
    padding: calc(var(--space-md) + var(--safe-top)) calc(var(--space-md) + var(--safe-right)) calc(var(--space-md) + var(--safe-bottom)) calc(var(--space-md) + var(--safe-left));
  }
  /* VOALUL URMARESTE DEGETUL. `--voal-p` (0..1) o scrie componenta cat timp foaia
     coboara: la 1 e voalul intreg, la 0 nu mai e nimic din el. Fara asta gestul nu
     era reversibil cu ochii — trageai jumatate de foaie si nimic nu-ti spunea cat
     mai ai pana pierzi ce ai deschis. In repaus e mereu 1, deci pe desktop (unde
     nu exista gest) regula da exact `--scrim`, ca pana acum. */
  .backdrop.varf { background: color-mix(in srgb, var(--scrim) calc(var(--voal-p, 1) * 100%), transparent); }
  /* Cat timp degetul e pe ecran, voalul n-are voie sa ramana in urma lui. */
  .backdrop.trage { transition: none; }
  /* Foaia de dedesubt nu-si mai arata iesirea: butonul ei ar inchide un obiect
     care nu e cel de deasupra. Ramane vizibila ca context, nu ca tinta. */
  .modal:not(.varf) .modal-close { opacity: 0; pointer-events: none; }
  /* SI LINIE, SI UMBRA PE ACEEASI SUPRAFATA PLUTITOARE — chenarul a plecat (A5).
     Doua niveluri de suprafata se desprind prin UMBRA; linia de 1px e separator
     intre randuri, cu marja laterala. Popupul din DatePicker era deja fara. */
  .modal {
    background: var(--bg-overlay);
    border-radius: var(--radius-md);
    width: 100%;
    max-height: 85dvh;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-lg);
  }
  .modal-sm { max-width: 400px; }
  .modal-md { max-width: 560px; }
  .modal-lg { max-width: 720px; }
  .modal-xl { max-width: 960px; }
  .modal-wide { max-width: 80%; }
  .modal-zoom { max-width: 70%; }

  /* ===== Panou lateral (desktop) =====
     Se lipeste de marginea din dreapta si ia inaltimea disponibila. Ramane o
     SUPRAFATA, nu un perete: pastreaza raza de 14 si insetul voalului, deci se
     citeste ca acelasi obiect ca foaia de pe telefon, doar asezat altfel.
     `align-items: stretch` pe voal ii da inaltimea; de aceea `max-height` de la
     `.modal` (85dvh) trebuie anulat, altfel panoul ar sta scurt si centrat. */
  @media (min-width: 769px) {
    .backdrop:has(.modal-panou) {
      justify-content: flex-end;
      align-items: stretch;
    }
    /* LATIMEA E A UTILIZATORULUI (T6). 340px erau prea putini pentru o listă de
       subtaskuri cu titluri reale; acum panoul se trage de muchia din stanga si
       isi tine latimea intre reporniri (`--panou-w`, salvata in localStorage). */
    .modal-panou {
      width: var(--panou-w);
      /* 720, nu 560: plafonul trebuie sa fie cel al MANERULUI, altfel manerul
         minte — tragi pana la 720, se salveaza 720, si se randeaza 560.
         `46vw` ramane paza reala: panoul nu are voie sa manance jumatate din
         ecranul de pe care il citesti, oricat de mult ai trage. JS-ul foloseste
         exact aceeasi formula, deci nu se poate salva o latime nerandabila. */
      max-width: min(720px, 46vw);
      max-height: none;
    }
    /* PANOUL NU ACOPERA CONTEXTUL — DECI NICI VOALUL NU-L ACOPERA.
       Un voal de 0,65 peste exact lista pe care panoul ar trebui s-o lase la
       vedere anuleaza motivul pentru care panoul e panou si nu caseta. */
    .backdrop.varf:has(.modal-panou) { background: var(--scrim-slab); }

    /* Manerul: o bara subtire pe muchia din stanga, cu cursorul care spune ce
       face. Se ingroasa la hover, nu se coloreaza — e o unealta, nu o stare. */
    .panou-maner {
      position: absolute;
      left: 0; top: 0; bottom: 0;
      width: 6px;
      cursor: col-resize;
      background: transparent;
      border: none;
      padding: 0;
      z-index: 2;
      transition: background-color var(--dur-fast) var(--ease);
    }
    .panou-maner:hover, .panou-maner:focus-visible { background: var(--accent-subtle); }
    .modal-panou.se-trage { transition: none; user-select: none; }
    /* 20, nu 24: la 340px de latime cele patru pixeli in plus de fiecare parte se
       iau din coloana de continut, care e deja jumatate cat a unei casete. */
    .modal-panou .modal-body { padding: var(--space-20); }
    .modal-panou .modal-header { padding-left: var(--space-20); padding-right: var(--space-20); }
  }

  /* "doc" — document aproape fullscreen (editor observatii/notite).
     Body-ul nu deruleaza si nu are padding: pagina interioara (RichTextEditor
     variant="doc") isi gestioneaza singura scroll-ul si coloana de text. */
  .modal-doc { max-width: 1060px; height: 95dvh; max-height: 95dvh; }
  /* ANTETUL UNUI DOCUMENT E O LINIE DE CONTEXT, NU UN TITLU DE FEREASTRA.
     Pe telefon asta se decisese deja (vezi `.modal.sheet .modal-title` mai jos);
     pe desktop ramasese varianta tare: Space Grotesk bold la 18.4px, care pe
     „Notițe — Verifică parametrii Danfoss FC302 — stand 4" umple randul si se taie.
     Titlul repeta oricum taskul din care ai venit — deci e context, nu titlu, si
     cel mai bun lucru care i se poate intampla e sa nu-ti ia atentia de la pagina
     goala de dedesubt. */
  .modal-doc .modal-header { border-bottom: none; padding-bottom: var(--space-sm); }
  .modal-doc .modal-title {
    font-family: var(--font-sans);
    font-size: var(--font-label);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    font-weight: var(--fw-semibold);
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .modal-doc .modal-body { padding: 0; overflow: hidden; display: flex; flex-direction: column; }
  .modal-doc .modal-body > :global(*) { flex: 1; min-height: 0; display: flex; flex-direction: column; }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-md) var(--space-lg);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .modal-title {
    font-family: var(--font-heading);
    letter-spacing: var(--tracking-tight);
    font-size: var(--font-h3);
    font-weight: var(--fw-semibold);
    color: var(--text);
  }
  .modal-close {
    width: 32px;
    height: var(--ctrl-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--text-dim);
    /* Fara `font-size`: butonul poarta un `<X>` Lucide (SVG dimensionat prin
       `size`), deci treapta de font nu masura niciodata nimic aici. */
    transition: var(--transition-colors);
  }
  .modal-close:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  .modal-body {
    padding: var(--space-lg);
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .modal-footer {
    padding: var(--space-md) var(--space-lg);
    border-top: 1px solid var(--border);
    flex-shrink: 0;
  }
  /* Randul de actiuni din footer — o singura reteta partajata (global, ca sa fie
     folosita din snippet-urile footer ale tuturor modalelor). :global fiindca e
     randat in slot-ul de footer al altui component. */
  :global(.modal-footer .modal-actions) {
    display: flex;
    gap: var(--space-sm);
    justify-content: flex-end;
    align-items: center;
    flex-wrap: wrap;
  }

  /* ===== Telefon: SHEET, nu caseta centrata =====
     O caseta centrata pe un ecran de 812px iti pune butoanele la mijloc, unde
     degetul mare nu ajunge fara sa muti mana, iar cand se deschide tastatura
     casetei ii ramane jumatate de ecran si sare in sus. Sheet-ul e lipit de
     marginea de jos: acolo ajunge degetul, acolo se opreste tastatura si de acolo
     vine gestul de inchidere.
     Manerul de sus nu e decor — spune „asta se trage/inchide de aici" si da o zona
     de apucat care nu e nici titlu, nici buton. */
  @media (max-width: 768px) {
    /* FOAIA SE RIDICA DEASUPRA TASTATURII, NU DOAR SE MICSOREAZA.
       Regula de mai jos ii scadea inaltimea cu `--kb` si atat — si asta nu
       ajuta, fiindca foaia e ANCORATA JOS (`align-items: flex-end`): micsorata,
       ea isi coboara marginea de sus, iar cea de jos ramane tot la marginea
       ecranului, adica tot sub tastatura. In WebView-ul Capacitor `innerHeight`
       nici nu se micsoreaza cand urca tastatura (vezi nota de la `--kb` din
       <script module>), deci nimic nu o impingea in sus.
       Masurat pe „Task Nou", ecran 915 cu tastatura de 300: foaia tinea 451..915,
       iar din ea se vedea DOAR titlul — „Categorie", „Termen", „Recurență" si
       butonul „Creează" cadeau toate sub tastatura, si corpul nici nu derula, deci
       nu se putea ajunge la ele. Ion: „tastatura putin acopera recurenta taskului."
       Podeaua o ridica VOALUL, nu foaia: un `padding-bottom` pe foaie i-ar impinge
       continutul si i-ar lasa marginea unde era — exact obiectia scrisa mai jos,
       si e corecta. Pe voal insa, `padding-bottom` MUTA copilul ancorat la capat.
       Fara tastatura `--kb` e 0, deci nu se schimba nimic. */
    .backdrop {
      align-items: flex-end;
      padding: 0 0 var(--kb, 0px);
      transition: padding-bottom var(--dur-base) var(--ease);
    }
    .modal {
      max-width: 100%;
      /* dvh urmareste bara de adresa; sheet-ul nu trebuie sa depaseasca ecranul
         nici cat timp bara se retrage. `--kb` (T1b) o scade pe cea a
         tastaturii: foaia se MICSOREAZA, nu-si impinge continutul — un
         `padding-bottom` PE EA ar tine butoanele tot sub tastatura, doar mai jos
         (ridicarea o face voalul, mai sus). */
      max-height: min(92dvh, 100dvh - var(--safe-top) - 24px - var(--kb, 0px));
      border-radius: var(--radius-lg) var(--radius-lg) 0 0;
      border-bottom: none;
      /* Umbra urca, nu coboara: sheet-ul se ridica peste pagina. */
      box-shadow: var(--shadow-foaie);
    }
    /* Pe telefon panoul REDEVINE foaie: acelasi continut, acelasi component, alt
       loc. Fara `.modal-panou` in lista asta ar fi ramas o coloana de 340px lipita
       de marginea de jos a unui ecran de 375. */
    .modal-sm, .modal-md, .modal-lg, .modal-xl, .modal-wide, .modal-zoom, .modal-panou { max-width: 100%; }
    .modal-panou { max-height: min(92dvh, 100dvh - var(--safe-top) - 24px - var(--kb, 0px)); }

    /* Antetul e suprafata de tragere. `touch-action: none` doar aici: gestul e
       al nostru, dar restul sheet-ului trebuie sa se poata DERULA normal. */
    .modal.sheet .modal-header {
      touch-action: none;
      cursor: grab;
      -webkit-user-select: none;
      user-select: none;
    }
    .modal.sheet.trage .modal-header { cursor: grabbing; }
    .sheet-grip {
      width: 38px;
      height: 4px;
      margin: var(--space-sm) auto var(--space-2xs);
      border-radius: var(--radius-full);
      background: var(--border-strong);
      transition: background-color var(--dur-fast) var(--ease), width var(--dur-fast) var(--ease);
    }
    .modal.trage .sheet-grip { background: var(--accent); width: 52px; }

    /* Deplasarea din deget, pe `translate` (vezi nota din <script>). Cat timp
       tragi NU exista tranzitie — altfel sheet-ul ramane in urma degetului si se
       simte ca lag. La ridicare revine animat spre 0.
       Revenirea foloseste ARCUL (--ease-spring): un obiect pe care l-ai tras si
       l-ai eliberat se aseaza cu o depasire mica, nu se opreste mecanic — de
       aceea si durata e --dur-slow, arcul are nevoie de loc sa se aseze.
       `height`/`max-height` sunt proprietati de LAYOUT, deci in mod normal nu se
       anima (regula din tokens: doar transform si opacity). Aici e exceptia
       numita: schimbarea de treapta CHIAR schimba geometria foii, si nu exista
       transform care s-o poata exprima — o scalare ar intinde si textul.
       Rezerva pentru browserele fara `linear()` a plecat: `--ease-spring` e o
       `cubic-bezier` de cand arcul si-a luat token propriu, deci nu mai are de
       ce sa cada. */
    .modal.sheet {
      translate: 0 var(--trasY, 0px);
      transition: translate var(--dur-slow) var(--ease-spring),
                  height var(--dur-base) var(--ease),
                  max-height var(--dur-base) var(--ease),
                  scale var(--dur-slow) var(--ease),
                  border-radius var(--dur-slow) var(--ease);
      will-change: translate;
    }
    .modal.sheet.trage { transition: none; }

    /* ===== TEANCUL ARE ADANCIME =====
       Cand o foaie deschide alta foaie — taskul care deschide „Alege ziua",
       perioada care cere o confirmare — cea de dedesubt se RETRAGE: se
       micsoreaza dinspre marginea de jos si isi rotunjeste coltul la loc.
       Nu e decor. Stiva de niveluri exista si e corecta (Escape stie pe cine
       inchide), dar pe ecran a doua foaie arata exact ca prima, deci nu se vedea
       ca mai ai un pas de facut inapoi pana sa ajungi in lista.
       `scale`, nu `transform`: `transform` e al tranzitiilor Svelte de
       intrare/iesire, iar `translate` e al gestului. Trei proprietati separate,
       trei stapani, zero suprascrieri — aceeasi impartire ca la `--trasY`. */
    .modal.sheet.acoperit {
      scale: 0.94;
      transform-origin: bottom center;
    }

    /* ===== TREPTELE FOII =====
       La ODIHNA inaltimea vine din CSS, in `dvh`, deci se strange singura cand
       urca tastatura. In timpul gestului o scrie JS-ul in px (clasa `.gest`),
       fiindca atunci trebuie sa urmeze degetul cadru cu cadru. Ordinea de aici
       conteaza: `.gest` vine ULTIMA, ca sa bata clasele de treapta — au aceeasi
       specificitate, deci decide pozitia in fisier. */

    /* TREAPTA DE SUS: foaia e o PAGINA, nu „aproape tot ecranul". Regula asta era
       scrisa de DOUA ori — o data pentru `.intins`, o data pentru `.inalt` — cu
       doua inaltimi usor diferite (una scadea `--safe-top`, cealalta il includea),
       deci aceeasi foaie ajungea sus altfel dupa cum se deschisese. Acum e o
       singura treapta.
       Inaltimea INCLUDE safe-area si o compenseaza cu padding: foaia e ancorata
       JOS, iar pe telefonul lui Ion, cu edge-to-edge pornit, `--safe-top` e real
       (~50px) — scazut din inaltime, lasa o fasie de pagina vizibila sus. Exact
       „nu se urca pana sus". Coltul se indreapta: la marginea ecranului o raza
       n-are ce rotunji si arata ca o scapare de var(--space-20).
       `100dvh` e VIEWPORT indiferent de parinte — de aceea inaltimea se cere asa
       si nu prin `position: fixed; inset: 0`, care se raporteaza la primul
       stramos cu transform (cat tine sosirea rutei, acela e `.page`: masurat,
       foaia iesea 1596px in loc de 812). */
    .modal.sheet.intins:not(.modal-doc) {
      height: calc(100dvh - var(--kb, 0px));
      max-height: calc(100dvh - var(--kb, 0px));
      padding-top: var(--safe-top);
      border-radius: 0;
    }
    /* TREAPTA DE MIJLOC — doar pentru foaia care se deschide intinsa (`inalt`).
       Pana acum din ea nu exista drum inapoi decat inchiderea; de aici se vede si
       ce e dedesubt fara s-o pierzi. */
    .modal.sheet.mijloc:not(.modal-doc) {
      height: calc((100dvh - var(--kb, 0px)) * 0.55);
      max-height: calc((100dvh - var(--kb, 0px)) * 0.55);
    }
    /* Inaltimea gestului. Ultima, deci bate treptele cat timp degetul e pe ecran. */
    .modal.sheet.gest:not(.modal-doc) {
      height: var(--h-foaie);
      max-height: var(--h-foaie);
    }
    /* Regula lui `.inalt` a plecat de aici: „se deschide pe tot ecranul" nu mai e
       o geometrie proprie, e TREAPTA DE SUS a oricarei foi (`.intins`, mai sus).
       `inalt` a ramas doar ce a fost mereu — o intentie a apelantului: pe ce
       treapta se deschide. Cat timp erau doua reguli, aceeasi foaie ajungea sus
       altfel dupa cum se deschisese, si nici nu se putea intoarce din ea.
       Ce s-a invatat atunci si e acum in `.intins`: `max-height` fara `height`
       nu urca nimic (plafonul de 92% taia la 747 din 812), iar
       `calc(100dvh - var(--safe-top))` parea corect doar pe emulator, unde
       safe-area e 0. */

    /* Adancimea teancului vine DUPA trepte, cu aceeasi specificitate ca ele:
       la egalitate decide pozitia in fisier, si coltul rotunjit al foii retrase
       trebuie sa bata coltul drept al treptei de sus. */
    .modal.sheet.acoperit:not(.modal-doc) {
      border-radius: var(--radius-md) var(--radius-md) 0 0;
    }
    /* Antetul sheet-ului e o LINIE DE CONTEXT, nu un titlu de fereastra — ca
       „📥 Inbox >" la Todoist. Inainte lua ~90px pe verticala pentru un singur
       cuvant („birou"), fix acolo unde continutul ar trebui sa inceapa. */
    .modal.sheet .modal-header {
      padding: var(--space-2xs) var(--space-md) 0;
      border-bottom: none;
      min-height: 0;
    }
    .modal.sheet .modal-title {
      font-size: var(--font-label);
      text-transform: uppercase;
      letter-spacing: var(--tracking-label);
      font-weight: var(--fw-semibold);
      color: var(--text-dim);
    }
    .modal.sheet .modal-close { width: var(--tap-min); height: var(--tap-min); margin-right: -6px; }
    .modal-close { width: var(--tap-min); height: var(--tap-min); margin-right: -10px; }

    .modal-header { padding-left: var(--space-md); padding-right: var(--space-md); }
    .modal-body {
      padding: var(--space-md);
      /* Ultimul rand din corp nu trebuie sa cada sub bara de gesturi. Cand exista
         footer, el poarta insetul si aici nu se mai adauga. */
      padding-bottom: calc(var(--space-md) + var(--safe-bottom));
      -webkit-overflow-scrolling: touch;
    }
    .modal:has(.modal-footer) .modal-body { padding-bottom: var(--space-md); }
    .modal-footer {
      padding: var(--space-12) var(--space-md) calc(var(--space-12) + var(--safe-bottom));
    }
    /* Actiunile ocupa latimea si stau la indemana: pe telefon un buton de 100px
       intr-un colt e o tinta mai mica decat trebuie, iar ordinea inversata pune
       actiunea principala sub degetul mare, la dreapta. */
    :global(.modal-footer .modal-actions) {
      gap: var(--space-sm);
    }
    :global(.modal-footer .modal-actions > *) {
      flex: 1 1 0;
      min-height: var(--tap-min);
      justify-content: center;
    }

    /* CU TASTATURA SUS, INSETUL DE JOS NU MAI EXISTA: e sub tastatura. Fara
       regula asta, footerul foii pastra 24-34px de spatiu mort exact cand
       ecranul e cel mai mic. */
    :global(html.are-tastatura) .modal-body { padding-bottom: var(--space-md); }
    :global(html.are-tastatura) .modal-footer { padding-bottom: var(--space-12); }

    /* doc = sheet pe tot ecranul pe mobil. PODEAUA URCA SI AICI: `padding: 0`
       batea regula generala (`padding: 0 0 var(--kb)`), deci documentul — inalt
       de `100dvh - kb`, ancorat jos — statea cu 312px sub tastatura si lasa
       pagina la vedere deasupra. Masurat: zona de scris ramanea de 55px. */
    .backdrop:has(.modal-doc) { padding: 0 0 var(--kb, 0px); }
    .modal-doc {
      height: calc(100dvh - var(--kb, 0px)); max-height: calc(100dvh - var(--kb, 0px));
      border-radius: 0; border: none;
      box-shadow: none;
    }
    .modal-doc .modal-header { padding-top: calc(var(--space-md) + var(--safe-top)); }
    .modal-doc .modal-footer { padding-bottom: calc(var(--space-md) + var(--safe-bottom)); }
  }
</style>
