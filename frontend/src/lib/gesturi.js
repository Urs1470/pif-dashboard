// PRAGURILE DE GEST — o singura definitie pentru toata aplicatia.
//
// De ce exista fisierul: acelasi ecran avea trei praguri decise separat, si se
// simteau ca trei aplicatii diferite. Randul de task se bifa la 42% din latimea
// LUI; foaia se inchidea la 110px FIX, indiferent daca era o foaie de 300px sau
// una de 780 (deci pe foaia scunda inchideai din greseala, pe cea inalta trageai
// pana obosea degetul); banda din calendar pornea la 300ms + 10px, dar mouse-ul
// la 4px, iar cifrele erau scrise in trei fisiere.
//
// PROCENTE, NU PIXELI, pentru orice prag care se raporteaza la un obiect: un
// prag fix nu inseamna acelasi lucru pe doua obiecte de marimi diferite. Ce
// ramane in px sunt distantele care descriu DEGETUL (cat se misca pana se
// decide o directie), nu obiectul — alea chiar sunt absolute.

/** px pana la care se decide axa gestului; sub atat, nu s-a hotarat nimic. */
export const PRAG_DIRECTIE = 8

/** Fractiune din LATIMEA obiectului: bifare, stergere, amanare. */
export const PRAG_ACTIUNE = 0.42

/** Fractiune din INALTIMEA foii, in jos: peste atat, ridicarea degetului inchide. */
export const PRAG_INCHIDE = 0.28

/** Fractiune din inaltimea foii, in sus: peste atat, foaia se intinde. */
export const PRAG_INTINDE = 0.08

/** px de mouse sub care gestul ramane un click. */
export const PRAG_MOUSE = 4

/** px miscati inainte de apasarea lunga = utilizatorul deruleaza, nu apuca. */
export const PRAG_ANULARE = 10

/** ms de apasare fara miscare pana cand degetul „apuca" un obiect. */
export const APASARE_LUNGA = 300

/* Aici au stat pragurile gestului de comutare a taburilor: banda de jos, zona
   sigura masurata cu o sonda, viteza de aruncare. Au plecat odata cu gestul —
   vezi nota lunga „DE CE NU EXISTA UN GEST DE COMUTARE A SFEREI" din
   `pages/Tasks.svelte`. Nu se sterg doar apelurile si se lasa constantele: o
   valoare fara consumator arata ca o unealta gata de folosit si cheama la loc
   exact ce s-a hotarat sa nu mai existe. */

/**
 * ms cat zboara randul afara inainte sa se comita actiunea.
 * Scurt cu bunastiinta: e confirmarea gestului, nu o animatie de sine
 * statatoare — vezi nota despre `transitionend` din `glisare.js`.
 */
export const DUR_ZBOR = 130

/**
 * Pulsul de la trecerea pragului. Pe telefon degetul acopera exact zona in care
 * se schimba lucrurile, deci confirmarea care nu se vede se simte.
 * Safari pe iOS nu implementeaza `vibrate` — de aceea e optional, nu o
 * conditie a gestului.
 */
export function puls(ms = 12) {
  try { navigator.vibrate?.(ms) } catch (_) {}
}

// ===== VITEZA — A TREIA DIMENSIUNE A UNUI GEST =====
//
// Pana acum fiecare gest din aplicatie se uita la o singura marime: CAT de
// departe a ajuns degetul. Asta face ca gestul sa trebuiasca facut LUNG, iar
// aruncarea scurta si rapida — cea pe care mana o face fara sa se gandeasca —
// sa nu produca nimic. Nu e o preferinta de stil: pe telefon „arunc foaia in
// jos" e gestul implicit de inchidere in tot sistemul de operare, iar o
// interfata care il ignora se simte grea chiar daca fiecare animatie din ea e
// corecta.
//
// Solutia standard (UIKit, si de acolo peste tot): nu compari pozitia, compari
// UNDE AR AJUNGE degetul daca ar mai continua putin. Asa un gest scurt si
// iute si unul lung si lenes ajung la aceeasi concluzie, care e exact ce
// asteapta mana.

/** ms pe care se masoara viteza, inapoi de la ridicarea degetului.
 *  Media pe TOT gestul ar fi gresita: o aruncare incepe incet si se termina
 *  repede, deci media o raporteaza ca lenta — adica exact gestul pe care
 *  proiectia trebuie sa-l prinda ar iesi sub prag. */
export const FEREASTRA_VITEZA = 80

/** ms in viitor pe care se proiecteaza degetul la ridicare. */
export const PROIECTIE = 100

/** px/ms peste care nu se mai crede masuratoarea. Doua esantioane la 1ms
 *  distanta dau viteze absurde (si le dau usor: un `pointermove` intarziat
 *  urmat de doua la rand). Plafonul tine proiectia in aceeasi lume cu ecranul:
 *  3 px/ms × 100ms = 300px, adica deja mai mult decat o latime de telefon. */
const VITEZA_MAX = 3

/**
 * Urmareste pozitia unui deget si spune, la ridicare, unde ar fi ajuns.
 * Se foloseste pe o singura axa — cea pe care s-a decis gestul.
 *
 *   const u = urmaritor()
 *   u.porneste(e.clientY)                 // la pointerdown
 *   u.adauga(e.clientY)                   // la fiecare pointermove
 *   const tinta = u.proiectat(pozitieAcum) // la pointerup
 */
export function urmaritor() {
  let esantioane = []
  const adauga = (v) => {
    esantioane.push({ t: performance.now(), v })
    // Opt e mai mult decat incap in fereastra la 60Hz (~5), deci taierea nu
    // poate pierde un esantion care ar fi contat.
    if (esantioane.length > 8) esantioane.shift()
  }
  const viteza = () => {
    if (esantioane.length < 2) return 0
    const b = esantioane[esantioane.length - 1]
    let a = esantioane[esantioane.length - 2]
    for (let i = esantioane.length - 2; i >= 0; i--) {
      if (b.t - esantioane[i].t > FEREASTRA_VITEZA) break
      a = esantioane[i]
    }
    const dt = b.t - a.t
    if (dt <= 0) return 0
    const v = (b.v - a.v) / dt
    return Math.max(-VITEZA_MAX, Math.min(VITEZA_MAX, v))
  }
  return {
    porneste(v) { esantioane = []; adauga(v) },
    adauga,
    viteza,
    /** Unde ajunge `acum` daca degetul si-ar continua drumul `PROIECTIE` ms. */
    proiectat(acum) { return acum + viteza() * PROIECTIE },
  }
}
