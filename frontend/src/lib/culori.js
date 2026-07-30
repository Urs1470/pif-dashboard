// Culoarea de identitate a unui proiect — O SINGURA definitie, pentru tot dashboardul.
//
// De ce exista fisierul asta. Pana acum aceeasi idee („fiecare proiect are culoarea
// lui") era implementata de doua ori, in doua fisiere, cu DOUA PALETE care difereau
// intre ele:
//
//   Calendar.svelte  PALETA       = [...,'#5f8fd0','#c9a13a','#b9a5ff']   (pozitiile 4,5,6)
//   Plan.svelte      LANE_PALETTE = [...,'#b9a5ff','#5f8fd0','#c9a13a']   (aceleasi, ROTITE)
//
// Functia de dispersie era identica, deci indexul iesea acelasi — dar pica pe alta
// culoare. Rezultat masurat: pentru 3 din 7 gaznuiri (43% din proiecte) acelasi proiect
// avea o culoare in Calendar si ALTA in Planificator. Culoarea nu mai era un nume, ci
// o proprietate a paginii pe care te aflai.
//
// A doua ruptura, in interiorul aceleiasi pagini: barele din Calendar se colorau dupa
// `proiect_id`, dar sertarul „Proiecte fara perioada" dupa `client`. Acelasi proiect,
// doua culori, pe acelasi ecran — iar pentru ca 11 din 12 perioade sunt la Continental,
// tot sertarul iesea de o singura culoare.
//
// De aici incolo: o paleta, o functie, un singur fapt codat (PROIECTUL, niciodata
// clientul).

// Amber (--accent/--warning), violetul --info si coralul --danger sunt REZERVATE
// pentru sens, deci lipsesc din paleta de identitate: o bara nu are voie sa arate ca
// o avertizare doar pentru ca asa a cazut dispersia.
//
// Lipsesc si cele doua nuante de LOCATIE (--loc-site, --loc-sediu). Inainte paleta
// continea exact `#3f9dc4` (= site) si `#c9a13a` (~ sediu), deci in Planificator, unde
// benzile de locatie si barele de identitate stau pe acelasi ecran, aceeasi culoare
// insemna cand „proiectul X", cand „esti pe teren". Doua sisteme de culoare care se
// suprapun in valori nu mai sunt doua sisteme.
//
// Paleta NU e aleasa din ochi, e rezolvata numeric (scripts/solve_paleta.py).
// Prima incercare a fost „sase nuante egal distantate pe roata" — si a iesit MAI
// PROASTA decat cea din productie: separare 0,055 fata de 0,064. Motivul e ca sub
// deficienta rosu-verde (deuteranopie/protanopie, ~8% din barbati) axa rosu-verde
// se PRABUSESTE, deci nuante „bine distantate" pe roata ajung sa se suprapuna.
// Ce supravietuieste prabusirii e LUMINOZITATEA si axa albastru-galben — de aceea
// paleta de mai jos are contraste foarte diferite (4,5:1 pana la 12,2:1) in loc de
// sase nuante la fel de intense.
//
// Restrictii date rezolvatorului:
//   - o singura nuanta per familie (verde-galben, verde, teal, indigo, magenta, roz)
//     ca sa ramana o paleta echilibrata, nu trei verzi
//   - departe de lobii REZERVATI: amberul --accent/--warning si coralul --danger,
//     ca o bara sa nu arate ca o avertizare doar pentru ca asa a cazut dispersia
//   - departe de --info (violet) si --success (mint)
//   - departe de --loc-site / --loc-sediu (vezi tokens.css): in Planificator benzile
//     de locatie si barele de proiect stau pe ACELASI ecran. Inainte paleta continea
//     exact `#3f9dc4` (= site) si `#c9a13a` (~ sediu), deci aceeasi culoare insemna
//     cand „proiectul X", cand „esti pe teren".
//   - cerneala inchisa peste fill sa treaca AA: minimul e 4,52:1
//
// Rezultat masurat, separare in cel mai rau caz peste vedere normala + toate cele
// trei deficiente: 0,221 — fata de 0,064 cat avea paleta din productie (3,5x).
export const PALETA_PROIECT = [
  '#afe07e', // verde-galben  contrast pe cerneala 12,2:1
  '#27a348', // verde                              5,7:1
  '#83c1cc', // teal                               9,2:1
  '#867ee0', // indigo                             5,4:1
  '#b858b8', // magenta                            4,5:1
  '#cc6270', // roz                                4,9:1
]

// Randurile care nu apartin niciunui proiect (taskurile globale din Planificator,
// zilele fara client din Calendar). Neutru cu intentie: „fara proiect" nu e un
// proiect cu o culoare proprie.
export const CULOARE_NEUTRA = '#948a7d'

// Dispersie stabila: acelasi id da aceeasi culoare la fiecare incarcare, pe orice
// pagina, fara sa tinem nimic in baza de date.
function disperseaza(cheie) {
  let h = 0
  for (let i = 0; i < cheie.length; i++) h = (h * 31 + cheie.charCodeAt(i)) >>> 0
  return h
}

/**
 * Culoarea de identitate a unui proiect.
 * @param {string} id — `proiecte.id`. NU clientul si NU numele: clientul se repeta
 *   (11 din 12 perioade sunt la acelasi), iar numele se poate redenumi, si atunci
 *   proiectul si-ar schimba culoarea sub ochii tai.
 */
export function culoareProiect(id) {
  const k = (id || '').trim()
  if (!k) return CULOARE_NEUTRA
  return PALETA_PROIECT[disperseaza(k) % PALETA_PROIECT.length]
}
