// Oglinda numerica a lui `--dur-*` din tokens.css (proprietatile CSS nu se pot
// citi ca numere in parametrii tranzitiilor Svelte). Aici traia si sursa reactiva
// pentru `prefers-reduced-motion`; e stinsa cu buna stiinta — vezi `motion` mai jos,
// unde scrie de ce si cum se pune inapoi dintr-o linie.
//
// CINCI DURATE (handoff motion 2026-08-24, model Apple WWDC 2023-2025):
//   90   apasare — sub ~100ms legatura cauza-efect se citeste ca instantanee
//   150  micro — vopsea: hover, culoare, umbra, opacitate
//   300  fast — element: press vizibil, tooltip, tab switch
//   700  normal — suprafata: modal, foaie, panou (DESCHIDERE)
//   900  slow — scena: tranzitie pagina, hero, task adaugare/stergere
// Iesirile sunt mai scurte: 500 suprafata, 800 task exit.
export const DUR_PRESS = 90
export const DUR_MICRO = 150
export const DUR_FAST = 300
export const DUR_NORMAL = 700
export const DUR_CLOSE = 500
export const DUR_SLOW = 900
// Compatibilitate — consumatorii vechi; se migreaza gradual.
export const DUR_BASE = 220

/** Cat tine animatia de bifare inainte ca randul sa plece din lista.
 *  `taskComplete` dureaza 650ms — randul sta cat se joaca pulsul + stingerea,
 *  apoi iese cu `plecare` (800ms). */
export const INTARZIERE_BIFA = 700

// Cat tine o tranzitie cand utilizatorul a cerut mai putina miscare. NU zero:
// vezi `motionDuration`.
const DUR_REDUSA = 120

// CURBA — A PATRA LIMBA VORBITA IN ACELASI ECRAN.
//
// `--ease` era tokenizata si respectata peste tot in CSS, dar NICIO tranzitie
// Svelte n-o folosea. Motivul nu era o decizie, era o linie lipsa: fisierul asta
// exporta duratele si atat, deci `fade`, `sosire` si `plecare` ramaneau pe
// implicitul Svelte — care e LINIAR. Aceeasi distanta, aceeasi durata (240ms),
// sosiri diferite: randul de task iesea din lista in linie dreapta, langa un
// panou care se deschidea pe curba. Linia dreapta se citeste ca mecanica.
//
// `svelte/easing` NU exporta un `cubicBezier` generic (are doar familiile fixe:
// cubicOut, quintOut…), deci curba se rezolva aici. Newton-Raphson pe x, cu
// cadere pe injumatatire cand derivata e prea mica ca sa fie de incredere —
// aceeasi metoda pe care o folosesc browserele pentru `cubic-bezier()`.
function bezier(x1, y1, x2, y2) {
  const A = (a, b) => 1 - 3 * b + 3 * a
  const B = (a, b) => 3 * b - 6 * a
  const C = (a) => 3 * a
  const calc = (t, a, b) => ((A(a, b) * t + B(a, b)) * t + C(a)) * t
  const panta = (t, a, b) => 3 * A(a, b) * t * t + 2 * B(a, b) * t + C(a)
  return (x) => {
    if (x <= 0) return 0
    if (x >= 1) return 1
    let t = x
    for (let i = 0; i < 8; i++) {
      const p = panta(t, x1, x2)
      if (p === 0) break
      const e = calc(t, x1, x2) - x
      if (Math.abs(e) < 1e-6) return calc(t, y1, y2)
      t -= e / p
    }
    let lo = 0, hi = 1
    t = x
    while (lo < hi) {
      const e = calc(t, x1, x2)
      if (Math.abs(e - x) < 1e-6) break
      if (x > e) lo = t; else hi = t
      t = (hi - lo) / 2 + lo
    }
    return calc(t, y1, y2)
  }
}

// Perechea exacta a lui `--ease` din tokens.css. O schimbi acolo, o schimbi aici.
// Punctele stau intr-un singur loc IN JS: din ele iese si functia de easing
// pentru tranzitiile Svelte, si sirul pe care il cere WAAPI (vezi `easeCss`).
// Erau trei copii ale acelorasi patru numere — a treia scrisa de mana in
// `aterizare`, deci o schimbare de curba ar fi lasat exact o animatie in urma,
// tacut.
const PUNCTE_EASE = [0.32, 0.72, 0.28, 1]
export const EASE = bezier(...PUNCTE_EASE)

// CURBA DE IESIRE — `--ease` citita invers.
//
// Perechea exacta a lui `--ease-iesire` din tokens.css, unde e si motivul scris:
// ce SOSESTE franeaza (il urmaresti pana se opreste), ce PLEACA accelereaza (nu-l
// mai urmaresti, deci n-are de ce sa se aseze). Pana acum sistemul avea o singura
// curba pentru amandoua sensurile, si de aceea o foaie care se inchide parea ca
// zaboveste.
//
// NU e oglinda lui `--ease`, desi asta a fost prima incercare si ar fi fost mai
// elegant (un singur set de numere). Motivul complet, cu masuratori, e la
// `--ease-iesire` in tokens.css: oglinda misca foaia 6,9% din drum in primele
// 100ms, adica nimic in fereastra in care ochiul decide daca a raspuns —
// contrazice regula scrisa la `--dur-press`. Aici e accelerarea standard.
// Perechea exacta a tokenului; o schimbi acolo, o schimbi si aici.
const PUNCTE_IESIRE = [0.4, 0, 1, 1]
export const EASE_IESIRE = bezier(...PUNCTE_IESIRE)

/** Curba standard ca SIR, pentru `Element.animate()` — care nu primeste o
 *  functie, ci sintaxa CSS.
 *
 *  Se citeste din TOKEN, la prima chemare, nu la incarcarea modulului: in
 *  build-ul de productie foaia de stil e un `<link>`, deci la momentul in care
 *  modulul se evalueaza `--ease` poate sa nu fie inca rezolvabil. `aterizare`
 *  se cheama oricum dupa un gest, adica mult mai tarziu. Rezerva sunt aceleasi
 *  puncte de mai sus, deci nu exista o a doua valoare de tinut sincronizata. */
let _easeCss = ''
export function easeCss() {
  if (_easeCss) return _easeCss
  const dinToken = typeof document !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--ease').trim()
    : ''
  _easeCss = dinToken || `cubic-bezier(${PUNCTE_EASE.join(',')})`
  return _easeCss
}

// Perechea exacta a lui `--ease-spring`. Depaseste tinta cu ~35% si revine —
// corect pentru un obiect care urmareste degetul (cursorul de tab, revenirea
// dintr-un gest), gresit pentru orice altceva.
export const SPRING = bezier(0.34, 1.35, 0.42, 1)

// Perechea exacta a lui `--spring-bouncy` din tokens.css. Saltareata: FAB,
// popup confirmare, bifa check, toast. Mai multa depasire, dar P2 (.64,1) o
// face sa se ASEZE mai repede — asa popup-ul aterizeaza ferm.
const PUNCTE_BOUNCY = [0.34, 1.4, 0.64, 1]
export const BOUNCY = bezier(...PUNCTE_BOUNCY)
export function bouncyCss() { return `cubic-bezier(${PUNCTE_BOUNCY.join(',')})` }

// ARCUL, IN JS — perechea exacta a lui `--ease-arc` din tokens.css.
//
// CSS-ul il poarta ca `linear()` cu 33 de opriri; tranzitiile Svelte au nevoie
// de o FUNCTIE, deci aici e formula insasi, nu esantioanele ei. Amandoua descriu
// acelasi oscilator amortizat, deci nu exista „doua arcuri usor diferite dupa
// cine deseneaza miscarea" — greseala pe care fisierul asta a facut-o o data cu
// `--ease-spring` si o are scrisa mai sus.
//
// `bounce` e notatia Apple: 0 = fara depasire, .18 = depaseste cu ~1%.
// Rezultatul nu depinde de durata, fiindca pulsatia se alege exact cat sa
// incapa o perioada in ea — deci functia primeste progresul 0..1 si atat.
function arcCu(bounce) {
  const zeta = 1 - bounce
  const wd = Math.sqrt(1 - zeta * zeta)
  return (t) => {
    if (t <= 0) return 0
    if (t >= 1) return 1
    const u = 2 * Math.PI * t
    return 1 - Math.exp(-zeta * u) * (Math.cos(wd * u) + (zeta / wd) * Math.sin(wd * u))
  }
}

/** Arcul pentru ce se MISCA in spatiu. Niciodata pe opacitate sau culoare —
 *  vezi nota din tokens.css. */
export const ARC = arcCu(0.18)
export const DUR_ARC = 420


/** Elanul: acelasi arc, mai vioi. Un singur consumator — tenta din dock. */
export const ARC_ELAN = arcCu(0.28)
export const DUR_ARC_ELAN = 380

/** `--ease-arc` ca SIR, pentru `Element.animate()`. Acelasi mecanism ca
 *  `easeCss` — se citeste din token la prima chemare — dar rezerva se
 *  ESANTIONEAZA din `ARC` de mai sus, deci si ea vine din aceeasi formula.
 *  Definita dupa `ARC` cu buna stiinta: rezerva o foloseste. */
let _arcCss = ''
export function arcCss() {
  if (_arcCss) return _arcCss
  const dinToken = typeof document !== 'undefined'
    ? getComputedStyle(document.documentElement).getPropertyValue('--ease-arc').trim()
    : ''
  if (dinToken) { _arcCss = dinToken; return _arcCss }
  const n = 32
  const pct = []
  for (let i = 0; i <= n; i++) pct.push(i === n ? 1 : +ARC(i / n).toFixed(4))
  _arcCss = `linear(${pct.join(',')})`
  return _arcCss
}

// MISCAREA NU SE MAI TAIE. Ion, 2026-08-24: „scoate exceptia si limitarea aia cu
// reduced motion, si reduced effects — vreau un dashboard animat".
//
// Am ridicat obiectia o data (e o preferinta de accesibilitate, si chiar sesiunea
// Apple pe Liquid Glass o respecta: „Reduced Motion ... disables any elastic
// properties for the material"), iar decizia a fost asta. E o aplicatie cu UN
// utilizator, pe telefonul lui, deci preferinta sistemului nu vorbeste in numele
// altcuiva.
// PLUMBARIA RAMANE: `motionDuration()` si toti apelantii lui sunt neatinsi, ca
// intoarcerea sa fie o singura linie — se pune inapoi citirea de mai jos.
//   window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false
// Steagul ramane, ca `motionDuration()` si cei ~40 de apelanti ai lui sa nu se
// atinga. Doar sursa lui s-a stins.
export const motion = $state({ reduced: false })

// „MAI PUTINA MISCARE" NU INSEAMNA ZERO.
//
// Pana acum intorcea 0, si asta avea un cost ascuns: o tranzitie de durata zero
// nu emite `transitionend`, iar comiterea bifarii asteapta exact evenimentul ala
// (vezi Tasks.svelte) — deci ramurile care se sincronizeaza pe sfarsitul unei
// tranzitii aveau nevoie de cronometru de rezerva doar pentru cazul asta.
// Mai important: la zero, un rand care pleaca si unul care vine se INLOCUIESC
// intre doua cadre, si nu mai stii care a plecat. Preferinta cere sa nu fie
// MISCARE (translatie, scalare), nu sa nu fie TIMP.
//
// 120ms de stingere, fara translatie — ce se schimba se vede schimbandu-se.
export function motionDuration(ms) {
  return motion.reduced ? Math.min(ms, DUR_REDUSA) : ms
}


// IESIREA UNUI RAND BIFAT.
//
// Un task bifat disparea instantaneu: la un cadru era acolo, la urmatorul nu.
// Confirmarea exista (toastul „Anulează", iar pe telefon verdele de prag), dar
// randul insusi nu spunea nimic — iar el e lucrul pe care tocmai l-ai atins.
//
// Se stinge SI se strange: numai opacitatea ar lasa un gol care se inchide brusc
// dupa aceea, iar numai inaltimea ar arata ca o eroare de layout. Impreuna se
// citesc ca „a plecat de aici". Impingerea mica spre dreapta imprumuta directia
// gestului de bifare de pe telefon (glisare spre dreapta = facut).
//
// Toate valorile se citesc din nodul REAL inainte de animatie: randurile n-au
// aceeasi inaltime (unul cu titlu pe doua linii e mai inalt), deci o inaltime
// fixa ar sari la inceputul tranzitiei.
// SOSIREA UNUI RAND NOU — perechea lui `plecare`.
//
// Iesirea exista (randul bifat se stinge si se strange), dar intrarea lipsea:
// un task adaugat sau mutat intr-o alta grupa APAREA intre doua cadre, fara
// nicio legatura vizibila cu gestul care l-a nascut. Standardul actual (si
// regula deja scrisa la `plecare`): fiecare mutare pe care ai provocat-o tu
// se vede intamplandu-se.
//
// Doar opacitate + o ridicare mica (transform — se compune pe GPU): vecinii
// isi fac singuri loc prin `animate:flip`, deci nu animam inaltimea aici —
// doua animatii de layout pe acelasi eveniment s-ar calca una pe alta.
// Se foloseste cu `|local`, ca prima incarcare a listei sa NU se joace:
// intrarea e pentru randul nou, nu pentru pagina noua.
export function sosire(node, { duration = 1100 } = {}) {
  const d = motionDuration(duration)
  const dy = motion.reduced ? 0 : -14
  return {
    duration: d,
    easing: EASE,
    css: (t, u) => `opacity: ${t}; transform: translateY(${u * dy}px) scale(${0.98 + 0.02 * t});`,
  }
}

export function panou(node, { duration = DUR_NORMAL } = {}) {
  const d = motionDuration(duration)
  const dx = motion.reduced ? 0 : 60
  return {
    duration: d,
    easing: EASE,
    css: (t, u) => `opacity: ${t}; transform: translateX(${u * dx}px);`,
  }
}

// NAVIGAREA CU DIRECTIE (tura 13).
//
// Schimbarea lunii era singura navigare din aplicatie fara sens: apasai
// „inainte" si grila se INLOCUIA, atat. Toate celelalte spun incotro ai mers —
// ruta face cross-fade, foaia urca, panoul se desface. Aici, dupa doua apasari
// rapide, nu mai stiai daca ai mers doua luni inainte sau una inainte si una
// inapoi: ecranul arata identic in ambele cazuri, iar antetul e singurul care
// te-ar putea lamuri — daca te uiti la el, si tocmai ai fost la grila.
//
// E singura miscare din tura care ADAUGA informatie, nu doar politete: continutul
// vine din partea in care ai apasat, iar mintea citeste „a venit de acolo".
// 240ms — valoarea scrisa in contractul de miscare („schimbare de luna sau
// pagina: 240ms directional"), una din exceptiile lui numite, nu o treapta din
// scara. A stat o vreme pe --dur-fast (120), cu argumentul ca raspunsul imediat
// se simte mai „al tau" — dar contractul o cere literal, iar directia e cea
// care poarta informatia, nu viteza.
export function alunecare(node, { sens = 0, duration = 240 } = {}) {
  // Prima randare nu e o navigare: nu vii de nicaieri. Fara asta, distanta ar fi
  // 0 dar stingerea ar ramane — o a doua sosire peste `.cell-in` care ruleaza
  // deja pe celula de deasupra, adica exact suprapunerea pe care o evitam.
  if (!sens) return { duration: 0 }
  const d = motionDuration(duration)
  const dx = motion.reduced ? 0 : sens * 10
  return {
    duration: d,
    easing: EASE,
    css: (t) => `opacity: ${t}; transform: translateX(${(1 - t) * dx}px);`,
  }
}

// Aici a stat `desfacere` — o tranzitie care anima SAPTE proprietati de layout
// (height, padding x2, margin x2, border-width x2) cadru cu cadru. Singurul ei
// consumator era `Tasks.svelte`, pe un bloc gardat de `expandedTask`, o stare
// care nu se mai asigneaza niciodata de cand taskul se deschide in foaie/panou.
// Deci: cod mort care contrazicea regula „doar transform/opacity". Sters cu tot
// cu consumatorul lui.

export function plecare(node, { duration = 800 } = {}) {
  const d = motionDuration(duration)

  const p = node.parentElement
  let scos = false
  if (p && getComputedStyle(p).position !== 'static') {
    const r = node.getBoundingClientRect()
    const pr = p.getBoundingClientRect()
    node.style.position = 'absolute'
    node.style.top = (r.top - pr.top + p.scrollTop) + 'px'
    node.style.left = (r.left - pr.left) + 'px'
    node.style.width = r.width + 'px'
    node.style.height = r.height + 'px'
    node.style.margin = '0'
    node.style.zIndex = '0'
    node.style.pointerEvents = 'none'
    scos = true
  }

  return {
    duration: d,
    easing: EASE,
    css: scos
      ? (t, u) => `opacity: ${t}; transform: translateX(${u * -28}px) scale(${0.96 + 0.04 * t});`
      : (t) => `opacity: ${t};`,
  }
}

/**
 * ATERIZARE (FLIP) — obiectul mutat ALUNECA spre locul nou, nu se teleporteaza.
 *
 * De ce e nevoie de el: pozitia benzilor vine din `grid-column` (Calendar) sau
 * din `left: %` (Planificator, Gantt), iar niciuna nu se poate anima. Dupa
 * commit + reincarcare obiectul aparea direct pe ziua noua — in timp ce chenarul
 * deplasarii, care ARE `transition: height/margin-top`, se misca animat. Doua
 * ceasuri pe acelasi gest: unul sarea, celalalt aluneca.
 *
 * Se cheama in doi timpi: masori INAINTE de schimbarea datelor, apoi chemi
 * `aterizare(el, masuratoarea)` dupa ce Svelte a re-randat.
 *
 * Durata vine intotdeauna din `motionDuration`, care azi nu mai are pe ce sa cada:
 * steagul `motion.reduced` e fix `false` (vezi nota de la el).
 *
 *   const dinainte = el.getBoundingClientRect()
 *   await salveaza(); await tick()
 *   aterizare(el, dinainte)
 */
export function aterizare(el, dinainte) {
  if (!el || !dinainte) return
  const d = motionDuration(DUR_BASE)
  if (!d) return
  const acum = el.getBoundingClientRect()
  const dx = dinainte.left - acum.left
  const dy = dinainte.top - acum.top
  // Sub o jumatate de pixel nu e o mutare, e zgomot de rotunjire.
  if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return
  // Aterizarea e miscare in spatiu: arc. Sirul vine din acelasi token ca in CSS
  // (`--ease-arc`), deci nu exista o a doua copie a curbei.
  el.animate(
    [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }],
    { duration: motionDuration(DUR_ARC), easing: arcCss() },
  )
}
