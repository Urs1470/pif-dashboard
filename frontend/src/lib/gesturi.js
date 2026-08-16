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

/**
 * BANDA DE JOS — px de la marginea de jos a ferestrei in care orizontala
 * apartine TABURILOR, nu randului de sub deget.
 *
 * Ion: „vreau sa dau swipe din zona de jos a ecranului, am ecran mare, degetul
 * natural imi cade putin mai sus de dock."
 *
 * Pana acum comutarea taburilor era a paginii intregi, cu o exceptie: un gest
 * pornit pe un rand ii apartine randului (acolo orizontala inseamna deja
 * „Făcut" / „Planifică"). Regula e buna, dar pe un telefon inalt lista ACOPERA
 * exact fasia in care sta degetul mare — deci exceptia inghitea gestul in
 * singurul loc din care el chiar se da. Un gest care exista peste tot in afara
 * de unde ajunge mana nu exista.
 *
 * 200px, si e o socoteala, nu o cifra rotunda: docul ocupa ~100 (68 inaltime +
 * 14 desprindere + zona sigura), deci raman ~100px de lista deasupra lui —
 * doua randuri de `--row-h-mobile`. Atat, si nu mai mult: fiecare pixel de
 * banda e un pixel in care nu mai poti bifa un task cu degetul, iar bifarea e
 * gestul pe care il faci de zeci de ori pe zi.
 *
 * MASURATA DE LA MARGINEA FERESTREI, nu de la doc: docul se ascunde la derulare
 * si se muta cand se deschide un modal, deci pozitia lui e o tinta in miscare
 * — iar un prag de gest care se muta sub deget e mai rau decat unul asezat
 * cativa pixeli mai sus.
 */
export const BANDA_TABURI = 200

/** True cand punctul de PORNIRE al gestului cade in banda de jos. */
export function inBandaTaburi(clientY) {
  return clientY >= window.innerHeight - BANDA_TABURI
}

/**
 * VITEZA CARE COMITE, in px/ms. Un prag de distanta singur cere un gest LUNG,
 * si asta se simte ca efort („swipeul necesita prea multa presiune"): ca sa
 * comuti trebuia sa duci degetul pana la capat, cu tot cu franarea de la
 * amortizare, care spune exact pe dos — ca obiectul se opune.
 * O aruncare scurta si rapida e acelasi gest, dat de o mana care stie deja unde
 * merge.
 *
 * 0,28px/ms ≈ 4px pe cadru. Era 0,4, si cerea o smucitura anume; acum ca gestul
 * nu mai porneste din greseala (vezi `DOMINANTA` in Tasks.svelte — orizontala
 * trebuie sa fie limpede), pragul de viteza n-are ce sa mai apere. Ce apara el
 * de fapt nu e pornirea, ci INTENTIA: o mana care duce degetul si-l lasa acolo
 * n-a aruncat nimic.
 */
export const VITEZA_ARUNCARE = 0.28

/** px minimi pentru o aruncare — sub atat e o atingere care a tremurat. */
export const PRAG_ARUNCARE = 12

/** px miscati inainte de apasarea lunga = utilizatorul deruleaza, nu apuca. */
export const PRAG_ANULARE = 10

/** ms de apasare fara miscare pana cand degetul „apuca" un obiect. */
export const APASARE_LUNGA = 300

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
