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
  if (typeof window !== 'undefined' && window.visualViewport) {
    const vv = window.visualViewport
    const scrie = () => {
      const kb = Math.max(0, window.innerHeight - vv.height - vv.offsetTop)
      document.documentElement.style.setProperty('--kb', kb + 'px')
    }
    vv.addEventListener('resize', scrie)
    vv.addEventListener('scroll', scrie)
    scrie()
  } else if (typeof document !== 'undefined') {
    // Fara `visualViewport` variabila trebuie sa EXISTE, altfel `calc()`-urile
    // care o scad cad pe invalid si inaltimea foii dispare cu totul.
    document.documentElement.style.setProperty('--kb', '0px')
  }
</script>

<script>
  import { tick } from 'svelte'
  import { X } from '@lucide/svelte'
  import { fade, scale } from 'svelte/transition'
  import { motionDuration, DUR_FAST, DUR_BASE, DUR_SLOW, DUR_ARC, EASE, ARC } from '../../lib/motion.svelte.js'
  import { ecran } from '../../lib/ecran.svelte.js'
  // Foaia si voalul ies in `body`: pagina din spate se RETRAGE (un `transform`
  // pe invelisul ei), iar un obiect dinauntrul acelui invelis s-ar micsora
  // odata cu ce acopera. Vezi nota din `lib/portal.js`.
  import { portal } from '../../lib/portal.js'

  // ===== DE UNDE CRESTE CASETA (Ion, 2026-08-15: „din declansator") =====
  //
  // Scalarea din centru spune „o fereastra s-a deschis undeva". Un modal
  // deschis dintr-un buton anume poate creste DIN butonul acela — o singura
  // proprietate, `transform-origin`.
  //
  // Originea vine din ultima APASARE, nu dintr-o proprietate pasata de fiecare
  // apelant: sunt peste douazeci de locuri care deschid modale, iar o
  // proprietate noua pe fiecare ar fi fost uitata exact acolo unde conteaza.
  // Fereastra de 600ms si distanta plafonata mai jos fac diferenta intre „am
  // apasat ceva si s-a deschis asta" si „modalul a venit din alta parte".
  //
  // Cand NU exista o apasare recenta — deschidere din tastatura, din paleta,
  // dintr-un gest, dintr-o notificare — nu exista nici origine, si caseta creste
  // din centru ca pana acum. O origine gresita e mai rea decat niciuna: caseta
  // ar parea ca vine din alt loc decat ai atins.
  let ultimaApasare = { x: 0, y: 0, cand: 0 }
  if (typeof window !== 'undefined') {
    window.addEventListener('pointerdown', (e) => {
      ultimaApasare = { x: e.clientX, y: e.clientY, cand: Date.now() }
    }, { capture: true, passive: true })
  }

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
  import { PRAG_INCHIDE, PRAG_INTINDE, puls } from '../../lib/gesturi.js'

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
  let { open = $bindable(false), title = '', size = 'md', inalt = false, children, footer, onclose } = $props()
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
    if (sheet) return { duration, easing: EASE, css: (t, u) => `transform: translateY(${u * 100}%)` }
    // PANOUL SOSESTE CU 8px, NU CU O SCALARE. Scalarea spune „fereastra care se
    // deschide din centru"; panoul vine dinspre marginea de care se lipeste, deci
    // o deplasare mica, pe axa lui. Distanta e mica cu bunastiinta: obiectul e
    // deja la locul lui, miscarea doar spune din ce parte a venit.
    if (panou) return { duration, easing: EASE, css: (t, u) => `opacity: ${t}; transform: translateX(${u * 8}px)` }
    // Caseta: creste din declansator daca exista unul, altfel din centru.
    // ARC pe scalare (se misca in spatiu), `--ease` pe opacitate — regula
    // `spatial` / `effects` din tokens.
    const org = origineaCasetei(node)
    if (org) node.style.transformOrigin = org
    return {
      duration: motionDuration(DUR_ARC),
      easing: (t) => t,
      css: (t) => `opacity: ${EASE(t)}; transform: scale(${0.96 + 0.04 * ARC(t)});`,
      // Originea se sterge la final: lasata acolo, ar ramane pe casetă si
      // pentru INCHIDERE, care se joaca din alt punct decat s-a deschis.
      tick: (t) => { if (t === 1) node.style.transformOrigin = '' },
    }
  }

  // ===== TRAGEREA SHEET-ULUI (telefon) =====
  // Ion: „nu poate fi tras pe tot ecranul, nu poti sa-l tragi inapoi, doar prin x".
  // Manerul era pana acum DECOR: un dreptunghi care arata a maner si nu facea
  // nimic. Pe telefon asta e mai rau decat sa nu-l ai — promite un gest care nu
  // exista, deci incerci, nu se intampla nimic, si cauti `X`-ul.
  //
  // Deplasarea merge pe proprietatea `translate`, NU pe `transform`: tranzitiile
  // Svelte de intrare/iesire scriu `transform` inline pe acelasi nod, iar doua
  // surse pe aceeasi proprietate s-ar suprascrie. `translate` e o proprietate
  // separata, deci cele doua se compun in loc sa se bata.
  let trasY = $state(0)
  let trage = $state(false)
  let intins = $state(false)   // tras in sus pana la ecran plin
  let sheetEl = $state(null)
  let y0 = 0
  let idPointer = null
  let pragTrecut = false

  // PROCENTE DIN INALTIMEA FOII, NU PIXELI (T2).
  // 110px fix insemnau doua gesturi diferite: pe o foaie de 300px erau o treime
  // din ea — deci inchideai din greseala deruland — iar pe una de 780 abia o
  // saptime, deci trageai pana obosea degetul. Fractiunile traiesc in
  // `lib/gesturi.js`, langa cele ale randului.
  const inaltimeFoaie = () => sheetEl?.offsetHeight || 1

  function trageJos(e) {
    if (!sheet || e.pointerType === 'mouse') return
    idPointer = e.pointerId
    y0 = e.clientY
    trasY = 0
    pragTrecut = false
    trage = true
    try { e.currentTarget.setPointerCapture?.(e.pointerId) } catch (_) {}
  }

  function trageMisca(e) {
    if (!trage || e.pointerId !== idPointer) return
    const dy = e.clientY - y0
    const h = inaltimeFoaie()
    // In jos e liber (te duci spre inchidere). In sus se opreste scurt daca e deja
    // intins — altfel sheet-ul ar putea fi tras dincolo de marginea de sus.
    // Capatul de sus e tot proportional: de doua ori pragul de intindere.
    trasY = intins ? Math.max(0, dy) : (dy < 0 ? Math.max(dy, -h * PRAG_INTINDE * 2) : dy)
    // Pragul se ANUNTA, ca la rand: degetul acopera manerul, deci confirmarea
    // care nu se vede se simte. O singura data per trecere, nu la fiecare cadru.
    const trecut = trasY > h * PRAG_INCHIDE
    if (trecut !== pragTrecut) {
      pragTrecut = trecut
      if (trecut) puls()
    }
  }

  function trageSus(e) {
    if (!trage || e.pointerId !== idPointer) return
    trage = false
    idPointer = null
    // `trasY` RAMANE unde l-ai lasat. Punandu-l pe 0 aici, doua miscari se
    // compuneau pe acelasi obiect, pe proprietati diferite si in sensuri opuse:
    // `translate` revenea de la 118px la 0 in --dur-slow CU ARC, in timp ce
    // tranzitia de iesire cobora foaia cu toata inaltimea ei. Prima jumatate a
    // iesirii se anula singura — foaia se misca in jos incet, apoi brusc, ceea ce
    // se citeste exact ca lag de atingere. Iar arcul, care are voie sa depaseasca
    // tinta, tragea IN SUS fix in intervalul in care obiectul trebuia sa
    // accelereze in jos. Acum gestul si iesirea merg in acelasi sens.
    const h = inaltimeFoaie()
    if (trasY > h * PRAG_INCHIDE) { inchide(); return }
    if (trasY < -h * PRAG_INTINDE) intins = true
    trasY = 0
  }

  // La fiecare deschidere pornim din starea normala, nu din cea intinsa a
  // taskului dinainte.
  // `trasY` nu se mai zeroeaza la ridicarea degetului (vezi `trageSus`), deci se
  // zeroeaza aici: foaia urmatoare porneste din pozitia ei, nu din cea in care ai
  // lasat-o pe cea dinainte.
  $effect(() => { if (open) { intins = inalt; trasY = 0 } })

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
  let corpY0 = 0
  function corpAtinge(e) {
    if (!sheet || intins) return
    if ((corpEl?.scrollTop ?? 0) > 0) { corpY0 = 0; return }
    corpY0 = e.touches[0].clientY
  }
  function corpTrage(e) {
    if (!sheet || intins || !corpY0) return
    if ((corpEl?.scrollTop ?? 0) > 0) { corpY0 = 0; return }
    const kb = document.documentElement.style.getPropertyValue('--kb')
    if (kb && kb !== '0px') return
    if (corpY0 - e.touches[0].clientY > 56) { intins = true; corpY0 = 0 }
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

  /** Singurul drum de inchidere pornit de utilizator. */
  function inchide() {
    open = false
    onclose?.()
  }

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
  <div class="backdrop" class:varf use:portal bind:this={backdropEl} onclick={onBackdrop} onkeydown={onKey} role="dialog" aria-modal="true" aria-label={title} tabindex="-1"
       style:--nivel={nivel} style:z-index="calc(var(--z-modal) + (var(--nivel) - 1) * 10)"
       in:fade={{ duration: motionDuration(sheet ? DUR_SLOW : DUR_BASE), easing: EASE }}
       out:fade={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
    <div class="modal modal-{size}" class:sheet class:intins class:inalt class:trage class:varf
         class:se-trage={trageManer}
         bind:this={sheetEl} style:--trasY="{trasY}px" in:intra out:intra>
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
        <button class="modal-close" onpointerdown={(e) => e.stopPropagation()} onclick={inchide} aria-label="Închide"><X size={18} /></button>
      </div>
      <div class="modal-body" bind:this={corpEl} ontouchstart={corpAtinge} ontouchmove={corpTrage}>
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
  .backdrop.varf { background: rgba(0, 0, 0, 0.65); }
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
    .backdrop.varf:has(.modal-panou) { background: rgba(0, 0, 0, 0.18); }

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
    color: var(--text-faint);
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
    height: 32px;
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
    .backdrop {
      align-items: flex-end;
      padding: 0;
    }
    .modal {
      max-width: 100%;
      /* dvh urmareste bara de adresa; sheet-ul nu trebuie sa depaseasca ecranul
         nici cat timp bara se retrage. `--kb` (T1b) o scade pe cea a
         tastaturii: foaia se MICSOREAZA, nu-si impinge continutul — un
         `padding-bottom` ar tine butoanele tot sub tastatura, doar mai jos. */
      max-height: min(92dvh, 100dvh - var(--safe-top) - 24px - var(--kb, 0px));
      border-radius: var(--radius-lg) var(--radius-lg) 0 0;
      border-bottom: none;
      /* Umbra urca, nu coboara: sheet-ul se ridica peste pagina. */
      box-shadow: 0 -14px 40px -12px rgba(0, 0, 0, 0.6);
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
      margin: 8px auto 2px;
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
       Prima linie e rezerva pentru browserele fara `linear()`. */
    .modal.sheet {
      translate: 0 var(--trasY, 0px);
      transition: translate var(--dur-base) var(--ease), max-height var(--dur-base) var(--ease);
      transition: translate var(--dur-slow) var(--ease-spring), max-height var(--dur-base) var(--ease);
      will-change: translate;
    }
    .modal.sheet.trage { transition: none; }

    /* Tras in sus = ecran plin. DOAR `max-height`, niciodata si `height`:
       prima varianta le seta pe amandoua, iar `height` fix face saltul pe care Ion
       l-a numit „se rupe modalul si dupa abia se extinde" — continutul se reaseza
       instantaneu, apoi tranzitia pornea de la o geometrie deja schimbata. */
    .modal.sheet.intins {
      max-height: calc(100dvh - var(--safe-top));
    }
    /* `inalt` = FOAIA E O PAGINA. Nu „aproape tot ecranul", ci TOT: `100dvh`,
       pana sub bara de stare. A luat trei runde, si de fiecare data valoarea a
       fost aproape — de aici lectia:
         - `max-height: min(92dvh, …)` din regula de baza taia la 92% (masurat:
           747 din 812) — `height` singur nu bate un plafon, deci se scriu
           amandoua;
         - `calc(100dvh - var(--safe-top))` parea „tot ecranul" pe emulator,
           unde safe-area e 0. Pe telefonul lui Ion, cu edge-to-edge pornit
           (`decorFitsSystemWindows(false)` + `viewport-fit=cover`), `--safe-top`
           e REAL (~50px) — iar foaia fiind ancorata JOS, cei 50px ramaneau o
           fasie de pagina vizibila sus. Exact „nu se urca pana sus".
       Deci inaltimea nu mai scade safe-area: o INCLUDE si o compenseaza cu
       padding, ca manerul si titlul sa nu intre sub bara de stare. Colturile
       de sus se indreapta: la marginea ecranului o raza n-ar avea ce rotunji,
       si ar arata ca o scapare de 20px. */
    .modal.sheet.inalt {
      /* `100dvh` e VIEWPORT, indiferent de parinte — de aceea inaltimea se
         cere asa, si nu prin `position: fixed; inset: 0`. Varianta cu `inset`
         pare mai ferma, dar se raporteaza la primul stramos cu transform, iar
         cat tine animatia de sosire a rutei acela e `.page`: masurat, foaia
         iesea 1596px in loc de 812. `100dvh` nu poate gresi marimea.
         Minus `--kb`: si foaia „pe toata pagina" trebuie sa se stranga cand
         urca tastatura, altfel campul in care tocmai scrii ramane sub ea. */
      height: calc(100dvh - var(--kb, 0px));
      max-height: calc(100dvh - var(--kb, 0px));
      padding-top: var(--safe-top);
      border-radius: 0;
    }
    /* Antetul sheet-ului e o LINIE DE CONTEXT, nu un titlu de fereastra — ca
       „📥 Inbox >" la Todoist. Inainte lua ~90px pe verticala pentru un singur
       cuvant („birou"), fix acolo unde continutul ar trebui sa inceapa. */
    .modal.sheet .modal-header {
      padding: 2px var(--space-md) 0;
      border-bottom: none;
      min-height: 0;
    }
    .modal.sheet .modal-title {
      font-size: var(--font-label);
      text-transform: uppercase;
      letter-spacing: var(--tracking-label);
      font-weight: var(--fw-semibold);
      color: var(--text-faint);
    }
    .modal.sheet .modal-close { width: 40px; height: 40px; margin-right: -6px; }
    /* 32px e o tinta de cursor. Degetul are nevoie de 44, iar `X`-ul e singura
       iesire cand tastatura acopera restul sheet-ului. Marginea negativa il tine
       aliniat optic cu titlul, desi caseta lui a crescut. */
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

    /* doc = sheet pe tot ecranul pe mobil */
    .backdrop:has(.modal-doc) { padding: 0; }
    .modal-doc {
      height: calc(100dvh - var(--kb, 0px)); max-height: calc(100dvh - var(--kb, 0px));
      border-radius: 0; border: none;
      box-shadow: none;
    }
    .modal-doc .modal-header { padding-top: calc(var(--space-md) + var(--safe-top)); }
    .modal-doc .modal-footer { padding-bottom: calc(var(--space-md) + var(--safe-bottom)); }
  }
</style>
