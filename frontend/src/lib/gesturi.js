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

/**
 * ms de apasare pana cand se DESCHIDE ceva (foaia de actiuni a unui rand).
 *
 * DE CE NU E ACEEASI VALOARE CA `APASARE_LUNGA`, desi fisierul asta exista tocmai
 * ca sa nu existe doua praguri pentru acelasi lucru: nu e acelasi lucru. Cele
 * doua gesturi cer altceva de la mana:
 *   APUCI un obiect (banda din Calendar, randul de reordonat) — degetul RAMANE jos
 *     si continua sa lucreze, deci pragul trebuie sa fie scurt: pana simti c-ai
 *     prins, ai si inceput sa tragi.
 *   DESCHIZI un strat peste ecran — degetul trebuie sa se RIDICE, iar el are nevoie
 *     de timp ca sa afle c-a reusit. La 300ms foaia sosea sub deget inainte sa-l
 *     ridici, si atunci apasarea continua PE FOAIE: WebView-ul o citea ca long-press
 *     pe textul din ea si pornea selectia. Ion, 2026-08-17: „aduce prea rapid
 *     modalul incat nu reusesc sa iau degetul si deja incepe sa se selecteze textul
 *     din modalul aparut."
 * 420 e si valoarea din handoff-ul de design pentru exact gestul asta — doua
 * semnale independente pe aceeasi cifra.
 * Selectia de text e oprita separat, in `global.css` (`user-select: none` pe
 * randurile care poarta gesturi): pragul singur o face improbabila, nu imposibila.
 */
export const APASARE_MENIU = 420

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

// ===== VOCABULARUL VIBRATIILOR — PATRU CUVINTE, NU UNUL =====
//
// `puls()` spunea un singur lucru: „ai trecut un prag". Degetul primea deci
// confirmarea INTENTIEI, dar niciodata pe cea a REZULTATULUI — si tocmai
// rezultatul e ce nu vezi, fiindca in clipa aia degetul acopera randul si ochiul
// e deja in alta parte.
//
// Patru cuvinte, fiecare cu un inteles care nu se suprapune cu altul. Regula de
// mai jos e cea care le tine sa nu se inmulteasca: se vibreaza pentru ce a facut
// DEGETUL, niciodata pentru ce s-a intamplat singur. O notificare, o cerere care
// s-a intors, o reimprospatare de fundal — alea n-au voie sa bata in mana.
//
// De ce PATTERN si nu doar durate: doua vibratii de 12 si 20ms nu se deosebesc
// pe un telefon in buzunar sau in manusa. Doua batai despartite de o pauza, da.

/** „Ai trecut pragul" — cat timp degetul e inca pe ecran, si te poti razgandi.
 *  Cea mai deasa, deci si cea mai scurta. (`puls()` de mai sus, nume vechi
 *  pastrat: are deja sase consumatori.) */
export const pragAtins = puls

/** „S-a asezat pe alta treapta." Mai slaba decat pragul: nu s-a decis nimic,
 *  doar s-a mutat ceva sub deget. */
export function treaptaNoua() { puls(8) }

/** „GATA, s-a facut" — actiunea a fost comisa si datele s-au schimbat.
 *  Doua batai scurte: se simte ca o incheiere, nu ca un avertisment. */
export function facut() {
  try { navigator.vibrate?.([14, 34, 14]) } catch (_) {}
}

/** „NU se poate" — actiunea a fost refuzata sau a picat.
 *  Una lunga: singurul cuvant din vocabular care se simte NEPLACUT, dinadins.
 *  Daca ar semana cu „gata", ar fi mai rau decat sa nu existe. */
export function refuzat() {
  try { navigator.vibrate?.([32, 40, 32]) } catch (_) {}
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
