// ===== CE CREEAZA „+" — declarat de PAGINA, desenat de DOCK =====
//
// AURORA muta butonul plutitor din coltul ecranului IN dock, ca sa nu mai acopere
// ultimul rand din lista. Dar ce creeaza el depinde de pagina: pe Acasa un task
// pentru azi, pe Proiecte un proiect, in pagina unui proiect un task al lui.
// Inainte, fiecare pagina isi desena propriul `.fab` — patru copii ale aceleiasi
// cutii, in patru fisiere.
//
// Registrul inverseaza relatia: pagina spune CE face, dockul stie CUM arata.
//
// PE PAGINILE FARA CREARE PROPRIE BUTONUL RAMANE (Ion, 2026-08-23). Prima
// varianta il facea sa DISPARA acolo, si iesise prost de doua ori: intai geometria
// dockului sarea de la o pagina la alta (reparat separat, cu coada de latime fixa),
// dar si dupa aceea ramanea intrebarea „unde s-a dus butonul?". O unealta care
// apare si dispare dupa camera in care esti nu se invata niciodata.
// Acum exista o ACTIUNE IMPLICITA: te duce la taskurile generale si deschide
// direct foaia de creare. Butonul face mereu acelasi lucru — creeaza ceva — iar
// pagina doar alege CE, cand are o parere.
//
// Se foloseste asa, in pagina:
//     $effect(() => inregistreazaActiune('Adaugă task', () => { showAdauga = true }))
// `$effect` cheama singur functia de curatare la demontare, deci nu ramane
// agatata o actiune a unei pagini pe care ai parasit-o.

// NUMELE E `inregistreazaActiune`, NU `inregistreaza`: acela exista deja, in
// `lib/reincarcare.svelte.js` (trage-ca-sa-reincarci), si multe pagini il importa.
// Doua importuri cu acelasi nume in acelasi fisier nu compileaza.
let curenta = $state(null)

// Foaia de creare implicita e GLOBALA (gazduita in App.svelte), NU pe /tasks.
//
// Inainte, „+" de pe o pagina fara creare proprie NAVIGA la /tasks si deschidea foaia
// acolo. Navigarea aia se vedea ca o „migrare" (Ion, 2026-08-24: „tranzitia de mutare
// nu este fluida, parca se vede un schelet la migrare"): pagina de sub deget se schimba
// in Taskuri — alt antet, alta lista, uneori un schelet de lista — chiar in timp ce foaia
// urca. Doua miscari peste aceiasi pixeli, exact ce sistemul evita peste tot.
//
// Acum foaia se ridica PESTE pagina curenta, fara sa se schimbe nimic dedesubt. Semnalul
// e REACTIV (nu mai e o cerere consumabila): App tine o foaie legata de `deschis`, iar
// foaia insasi il pune pe `false` la inchidere. Pe /tasks aterizezi abia DUPA ce chiar
// creezi un task — vezi `App.svelte`, `dupaCreareImplicita` — deci „du-ma la taskuri" al
// lui Ion se pastreaza, dar fara migrarea vizibila; daca renunti, ramai unde erai.
export const creareImplicita = $state({ deschis: false })

/** Apasat de pe o pagina fara creare proprie: ridica foaia GLOBALA, in loc. */
export function cereTaskNou() {
  creareImplicita.deschis = true
}

// Fara `cale`: „+" implicit nu mai navigheaza. Navigarea catre /tasks, cand se
// intampla, e a foii globale (dupa o creare reusita), nu a apasarii.
const IMPLICITA = {
  eticheta: 'Adaugă task',
  fa: cereTaskNou,
}

/** Ce actiune e disponibila acum: cea a paginii, altfel cea implicita. */
export function actiuneNoua() {
  return curenta || IMPLICITA
}

/**
 * @param {string} eticheta  ce scrie pe buton (aria-label + title)
 * @param {() => void} fa    ce se intampla la apasare
 * @returns {() => void}     curatare, pentru `$effect`
 */
export function inregistreazaActiune(eticheta, fa) {
  curenta = { eticheta, fa }
  // Curatarea e CONDITIONATA: intre demontarea paginii vechi si montarea celei
  // noi ordinea nu e garantata, iar o stergere oarba ar putea sterge exact
  // actiunea pe care pagina urmatoare tocmai a inregistrat-o. Acelasi tipar ca
  // garda de la `--dock-h` din `Dock.svelte` si `BaraSus.svelte`.
  return () => {
    if (curenta && curenta.fa === fa) curenta = null
  }
}
