/** Mută nodul în `<body>`, la montare.
 *
 * DE CE E NEVOIE. Un element care trebuie să stea PESTE toată pagina nu poate
 * face asta din locul lui din arbore: orice strămoș cu `transform`, `filter`,
 * `backdrop-filter` sau `contain` devine bloc de referință pentru
 * `position: fixed`, iar orice strămoș cu `overflow` îl taie. Nu contează cât
 * de mare e `z-index`-ul — un frate de mai jos în DOM îl acoperă oricum.
 *
 * Exista deja o copie locala, in `DatePicker.svelte`, scrisa exact pentru
 * cazul asta. A doua a fost ceruta de `Modal`, cand foaia de pe telefon a
 * primit pagina care se retrage in spatele ei: retragerea e un `transform` pe
 * invelisul paginii, iar foaia trebuie sa fie IN AFARA lui, altfel s-ar
 * micsora odata cu pagina pe care o acopera. Doua copii ale aceleiasi
 * functii ar fi fost exact felul de duplicare pe care restul sistemului o
 * evita, deci a devenit un modul.
 *
 * `node.remove()` la distrugere: Svelte scoate nodul din parintele lui REAL,
 * care de acum e `body` — deci nu ramane nimic in urma.
 */
export function portal(node) {
  document.body.appendChild(node)
  return {
    destroy() { node.remove() },
  }
}
