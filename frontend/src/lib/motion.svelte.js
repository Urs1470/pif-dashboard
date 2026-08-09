// Oglinda numerica a lui `--dur-*` din tokens.css (proprietatile CSS nu se pot
// citi ca numere in parametrii tranzitiilor Svelte), plus o singura sursa
// reactiva pentru `prefers-reduced-motion`, ca preferinta schimbata la mijlocul
// sesiunii sa ajunga in toate componentele deodata.
//
// TREI DURATE, NIMIC INTRE ELE (redesign 2026-08-08):
//   90  apasare — sub ~100ms legatura cauza-efect se citeste ca instantanee
//   220 element — un rand, un chip, un toast: lucruri de marimea unui deget
//   280 suprafata — o foaie, un panou, un modal: lucruri cat ecranul
// `--dur-fast` (120) nu e in scara: e vopsea (hover, culoare), nu miscare.
export const DUR_FAST = 120
export const DUR_BASE = 220
export const DUR_SLOW = 280
export const DUR_PRESS = 90

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
export const EASE = bezier(0.32, 0.72, 0.28, 1)

// Perechea exacta a lui `--ease-spring`. O SINGURA curba cu depasire in tot
// sistemul (era esantionata dintr-un `linear()` cu opt opriri; acum e aceeasi
// bezier pe care o scrie si CSS-ul, deci nu mai exista doua arcuri usor
// diferite dupa cine deseneaza miscarea). Depaseste tinta cu ~35% si revine —
// corect pentru un obiect care urmareste degetul (cursorul de tab, revenirea
// dintr-un gest), gresit pentru orice altceva. De aceea nu e implicitul.
export const SPRING = bezier(0.34, 1.35, 0.42, 1)

function readReducedMotion() {
  return typeof window !== 'undefined'
    && (window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false)
}

export const motion = $state({ reduced: readReducedMotion() })

if (typeof window !== 'undefined' && window.matchMedia) {
  window.matchMedia('(prefers-reduced-motion: reduce)')
    .addEventListener?.('change', (e) => { motion.reduced = e.matches })
}

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
export function sosire(node, { duration = DUR_BASE } = {}) {
  const d = motionDuration(duration)
  // Sub `reduced-motion` ramane doar stingerea: translatia e exact ce a cerut
  // utilizatorul sa nu se mai intample.
  const dz = motion.reduced ? 0 : 5
  return {
    duration: d,
    easing: EASE,
    css: (t) => `opacity: ${t}; transform: translateY(${(1 - t) * dz}px);`,
  }
}

/** PANOUL LATERAL DE PE DESKTOP: 200ms, 8px, dinspre marginea din dreapta.
 *
 *  E aceeasi componenta ca foaia de jos de pe telefon (280/220), doar ca pe
 *  desktop intra ca panou — deci are propria pereche de numere, scrisa in sistem:
 *  „pe desktop aceeasi componenta intra ca panou lateral: 200ms, 8px".
 *  Mai scurt decat o suprafata (280) fiindca nu acopera nimic: face loc, iar
 *  latimea coloanei se anima oricum din grila.
 *  Ca peste tot, `reduced-motion` lasa doar stingerea, fara drum. */
export function panou(node, { duration = 200 } = {}) {
  const d = motionDuration(duration)
  const dx = motion.reduced ? 0 : 8
  return {
    duration: d,
    easing: EASE,
    css: (t) => `opacity: ${t}; transform: translateX(${(1 - t) * dx}px);`,
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

// DESFACEREA UNUI PANOU (taskul deschis in lista).
//
// `slide` din Svelte masoara inaltimea O SINGURA DATA, la primul cadru, si
// animeaza spre ea cu `overflow: hidden`. Daca panoul se randeaza INAINTE ca
// datele sa fie acolo, tinta e inaltimea starii de asteptare: continutul care
// soseste dupa aceea nu incape si se vede TAIAT pana cand tranzitia se termina
// si inaltimea sare la loc. De aceea panoul se deschide numai cu datele in
// mana (vezi `toggleTaskExpand`) — iar aici masuram ansamblul final.
//
// Fata de `slide`: opacitatea urca pe prima jumatate a miscarii, nu in primele
// 5% ca la Svelte. Inaltimea singura se citeste ca o stergere de sus in jos;
// cu stingerea peste ea, panoul APARE, nu e descoperit.
export function desfacere(node, { duration = DUR_SLOW } = {}) {
  const d = motionDuration(duration)
  const s = getComputedStyle(node)
  const nr = (v) => parseFloat(v) || 0
  // TOT ce ocupa spatiu pe verticala, nu doar inaltimea: panoul din pagina de
  // proiect are rama pe patru laturi si margine jos, iar cel din /tasks doar
  // linie sus. Daca marginea si ramele nu se strang odata cu inaltimea, raman
  // ~13px care apar dintr-un cadru — adica exact saritura pe care o repara asta.
  const h = nr(s.height)
  const pt = nr(s.paddingTop)
  const pb = nr(s.paddingBottom)
  const mt = nr(s.marginTop)
  const mb = nr(s.marginBottom)
  const bt = nr(s.borderTopWidth)
  const bb = nr(s.borderBottomWidth)
  return {
    duration: d,
    // `--ease`, ca tot restul. Era `cubicOut` — a doua curba pe acelasi ecran:
    // panoul se desfacea pe una si randurile din el soseau pe alta.
    easing: EASE,
    css: (t) => `
      overflow: hidden;
      height: ${t * h}px;
      padding-top: ${t * pt}px;
      padding-bottom: ${t * pb}px;
      margin-top: ${t * mt}px;
      margin-bottom: ${t * mb}px;
      border-top-width: ${t * bt}px;
      border-bottom-width: ${t * bb}px;
      opacity: ${Math.min(1, t * 2)};
    `,
  }
}

export function plecare(node, { duration = DUR_BASE } = {}) {
  const d = motionDuration(duration)
  const s = getComputedStyle(node)
  const nr = (v) => parseFloat(v) || 0
  const h = nr(s.height)
  const mb = nr(s.marginBottom)
  const bt = nr(s.borderTopWidth)
  const bb = nr(s.borderBottomWidth)
  return {
    duration: d,
    easing: EASE,
    // `translateX` a plecat. Pe telefon bifezi GLISAND spre dreapta, deci gestul
    // a dat deja directia, iar impingerea de 10px se adauga peste ea ca o a doua
    // miscare pe aceeasi axa. Pe desktop, unde bifezi din click, randul se stinge
    // si se strange — atat; directia n-o mai imprumuta de la un gest care n-a
    // avut loc. Inaltimea se strange in continuare cu patratul lui `t`: pleaca
    // repede si se aseaza lin.
    css: (t) => `
      overflow: hidden;
      opacity: ${t};
      height: ${t * t * h}px;
      margin-bottom: ${t * t * mb}px;
      border-top-width: ${t * bt}px;
      border-bottom-width: ${t * bb}px;
    `,
  }
}
