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
 * BANDA DE JOS — fasia in care orizontala apartine TABURILOR, nu randului de
 * sub deget.
 *
 * Ion: „vreau sa dau swipe din zona de jos a ecranului, am ecran mare, degetul
 * natural imi cade putin mai sus de dock." Si, dupa prima incercare: „tot banda
 * de swipe e prea sus."
 *
 * Comutarea taburilor era a paginii intregi, cu o exceptie: un gest pornit pe un
 * rand ii apartine randului (acolo orizontala inseamna deja „Făcut" /
 * „Planifică"). Regula e buna, dar pe un telefon inalt lista ACOPERA exact fasia
 * in care sta degetul mare — deci exceptia inghitea gestul in singurul loc din
 * care el chiar se da.
 *
 * PRIMA VERSIUNE MASURA 200px DE LA MARGINEA FERESTREI, si a gresit din doua
 * parti deodata:
 *  — SUS lua prea mult: ~100px de lista peste doc, adica doua randuri in care nu
 *    se mai putea bifa un task prin glisare. Fiecare pixel de banda e un pixel
 *    furat de la gestul pe care il faci de zeci de ori pe zi.
 *  — JOS nu ajungea deloc: docul e FRATE cu continutul, nu copil, deci o apasare
 *    pe el nu ajungea la niciun ascultator. Fix cea mai de jos fasie a ecranului,
 *    unde cade degetul mare cand mana sta relaxata, era moarta.
 *
 * Acum banda se masoara DE LA DOC, nu de la marginea ferestrei, si il include si
 * pe el: „peste doc si doua randuri deasupra lui". Docul e si reperul pe care
 * omul il VEDE — deci pragul e definit de acelasi lucru care il ghideaza pe el,
 * nu de o presupunere despre inaltimea zonei sigure a telefonului lui.
 *
 * 112 = doua randuri de `--row-h-mobile` (52) plus o suflare. Ion, dupa ce
 * fasia a fost o vreme de un singur rand: „vreau mai mult deasupra dock-ului."
 * Costul e cel spus de la inceput si nu s-a schimbat: in banda nu se mai poate
 * bifa un task prin glisare. Sub doc insa nu se putea nici inainte, deci nu se
 * pierde nimic acolo — se castiga.
 */
export const BANDA_PESTE_DOC = 112

/** Zona sigura de jos, in px. Masurata O DATA, cu o sonda: `env()` nu se poate
 *  citi din JS (o proprietate personalizata s-ar intoarce ca text nerezolvat),
 *  iar valoarea difera de la telefon la telefon — pe unul cu navigare din gest e
 *  ~24px, pe unul cu butoane e 0. Exact felul de diferenta care face un prag
 *  scris „din ochi" sa fie corect pe masina de dezvoltare si gresit in mana. */
let _zonaSigura = null
function zonaSigura() {
  if (_zonaSigura !== null) return _zonaSigura
  try {
    const sonda = document.createElement('div')
    sonda.style.cssText = 'position:fixed;bottom:0;left:-9999px;width:0;' +
                          'height:env(safe-area-inset-bottom,0px);pointer-events:none;'
    document.body.appendChild(sonda)
    _zonaSigura = sonda.offsetHeight
    sonda.remove()
  } catch (_) { _zonaSigura = 0 }
  return _zonaSigura
}

/** Cat ocupa docul de la marginea de jos in sus, ca ASEZARE — nu ca pozitie
 *  curenta. `offsetHeight` nu e atins de `transform`, deci raspunsul e acelasi
 *  si cand docul e coborat (ascuns la derulare, dat la o parte de un modal).
 *  Un prag de gest care se muta sub deget ar fi mai rau decat unul aproximativ.
 *  `14` e desprinderea din `Dock.svelte` (`bottom: calc(14px + safe)`). */
function inaltimeaDocului() {
  const doc = document.querySelector('.dock')
  const h = doc?.offsetHeight || 68
  return h + 14 + zonaSigura()
}

/** True cand punctul de PORNIRE al gestului cade in banda de jos. */
export function inBandaTaburi(clientY) {
  return clientY >= window.innerHeight - (inaltimeaDocului() + BANDA_PESTE_DOC)
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
