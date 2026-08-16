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
