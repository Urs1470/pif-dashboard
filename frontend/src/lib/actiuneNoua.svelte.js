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

// Cerere in asteptare: „am apasat + de pe o pagina care nu creeaza nimic".
// NEreactiva si CONSUMABILA o singura data — daca ar fi un semnal reactiv, o
// intoarcere ulterioara pe /tasks ar redeschide foaia din senin. Nu e nici in URL
// din acelasi motiv: o reincarcare a paginii n-are de ce sa te puna sa scrii un task.
let cerut = false

/** Apasat de pe o pagina fara creare proprie: du-ma unde se creeaza, si deschide. */
export function cereTaskNou() {
  cerut = true
}

/** Chemat de /tasks la montare. Intoarce `true` O SINGURA data dupa fiecare cerere. */
export function consumaCerereTaskNou() {
  const c = cerut
  cerut = false
  return c
}

const IMPLICITA = {
  eticheta: 'Adaugă task',
  cale: '/tasks',
  fa: cereTaskNou,   // navigarea o face dockul, ca sa poata folosi `link`/preincarcarea
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
