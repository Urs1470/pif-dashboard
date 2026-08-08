// O SINGURA SURSA PENTRU „SUNTEM PE TELEFON".
//
// Pragul de 768px era scris de patru ori in JS (Modal, DatePicker, TodayBoard,
// Calculator), fiecare cu propriul `onMount`/`$effect`, propriul ascultator si
// propria copie a numarului — pe langa zecile de `@media (max-width: 768px)` din
// CSS. Patru copii ale aceleiasi constante inseamna ca a cincea o poate scrie
// altfel, si nimic nu semnaleaza cand se desincronizeaza: interfata s-ar comporta
// ca pe telefon si ar arata ca pe desktop, sau invers.
//
// Aici e o singura stare reactiva, un singur ascultator pe toata aplicatia, iar
// componentele doar citesc `ecran.telefon`. Ca la `motion.svelte.js` de alaturi.
//
// Valorile se citesc IMEDIAT, nu dupa montare: un `false` initial urmat de `true`
// dupa primul paint inseamna ca modalul apare o clipa ca fereastra centrata si
// abia apoi devine sertar.

export const PRAG_TELEFON = '(max-width: 768px)'
export const PRAG_LARG = '(min-width: 940px)'
// Deget, nu cursor. Perechea in JS a lui `@media (hover: none)` din CSS: unde
// nu exista hover, nu exista nici „apropii cursorul si apare manerul", deci
// gesturile de precizie (intinsul unei perioade) nu se ofera deloc — vezi
// Calendar.
export const PRAG_GROSIER = '(hover: none)'

const are = (q) => typeof window !== 'undefined'
  && (window.matchMedia?.(q)?.matches ?? false)

export const ecran = $state({
  telefon: are(PRAG_TELEFON),
  larg: are(PRAG_LARG),
  grosier: are(PRAG_GROSIER),
})

if (typeof window !== 'undefined' && window.matchMedia) {
  const lega = (q, cheie) => {
    const mq = window.matchMedia(q)
    const pune = () => { ecran[cheie] = mq.matches }
    pune()
    mq.addEventListener?.('change', pune)
  }
  lega(PRAG_TELEFON, 'telefon')
  lega(PRAG_LARG, 'larg')
  lega(PRAG_GROSIER, 'grosier')
}
