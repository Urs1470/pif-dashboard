// GRUPAREA UNEI LISTE DE TASKURI DUPA TERMEN.
//
// De ce exista: `/api/global-tasks` intoarce `ORDER BY created_at DESC` — ordinea
// in care le-ai scris, care nu spune nimic despre ce ai de facut. Pe ecran arata
// asa: 30.07, 31.07, fara termen, 29.07 (rosu, restant), fara termen. Adica exact
// randul care tipa e al patrulea, sub doua care nu sunt inca scadente. Intr-o
// lista de facut, ordinea E informatie — cea mai ieftina pe care o ai.
//
// Nu inventam o „prioritate" (a plecat in v34, era saturata: 54% urgent). Singurul
// lucru care chiar variaza e TERMENUL, si el ordoneaza singur:
//
//   Restante  ->  Azi  ->  Mâine  ->  Zilele astea (2-7)  ->  Mai târziu  ->  Fără termen
//
// „Fără termen" e ULTIMA, nu prima: e sertarul, nu agenda. Un task fara termen nu
// e urgent prin faptul ca n-are data — e doar unul pe care nu l-ai asezat inca.

import { zilePanaLa } from './formatters.js'

/** Grupele, in ordinea in care se afiseaza. `k` = pana la cate zile intra aici. */
const GRUPE = [
  { id: 'restant', titlu: 'Restante', ton: 'danger', test: (k) => k !== null && k < 0 },
  { id: 'azi', titlu: 'Azi', ton: 'accent', test: (k) => k === 0 },
  // „Mâine" e NORMAL, nu un ton propriu. Purta `warning`, iar de cand sistemul
  // are doua culori de stare (restant / facut) avertismentul a devenit acelasi
  // rosu ca restantul — deci grupa „Mâine" s-ar fi citit ca inca un teanc de
  // intarzieri. Mâine nu e o problema, e o zi.
  { id: 'maine', titlu: 'Mâine', ton: 'normal', test: (k) => k === 1 },
  { id: 'saptamana', titlu: 'Zilele astea', ton: 'normal', test: (k) => k !== null && k >= 2 && k <= 7 },
  { id: 'tarziu', titlu: 'Mai târziu', ton: 'normal', test: (k) => k !== null && k > 7 },
  { id: 'fara', titlu: 'Fără termen', ton: 'sters', test: (k) => k === null },
]

/**
 * @param {Array} taskuri lista, cu `data_scadenta`
 * @param {(t: any) => any} [cheieData] de unde se citeste termenul (implicit `data_scadenta`)
 * @returns {Array<{id, titlu, ton, items}>} doar grupele NEGOALE, in ordine
 */
export function grupeazaDupaTermen(taskuri, cheieData = (t) => t.data_scadenta) {
  const cosuri = new Map(GRUPE.map(g => [g.id, []]))
  for (const t of taskuri) {
    const k = zilePanaLa(cheieData(t))
    const g = GRUPE.find(x => x.test(k)) || GRUPE[GRUPE.length - 1]
    cosuri.get(g.id).push(t)
  }
  // In interiorul unei grupe: dupa termen crescator, apoi ordinea venita de la
  // server (stabila) ca sa nu sara randurile intre doua reincarcari.
  for (const [, lista] of cosuri) {
    lista.sort((a, b) => {
      const da = String(cheieData(a) || '').slice(0, 10)
      const db = String(cheieData(b) || '').slice(0, 10)
      if (da && db && da !== db) return da < db ? -1 : 1
      return 0
    })
  }
  // INTOARCE UN OBIECT, NU O LISTA — si de ce conteaza.
  // Sablonul itereaza `ORDINE_GRUPE`, un array CONSTANT de siruri, si citeste
  // `grupe[id]`. Daca ar itera o lista de obiecte de grupa (noi la fiecare
  // recalcul), Svelte re-CREEAZA blocul interior in loc sa-l actualizeze — chiar
  // si cu cheie pe `g.id` — iar randurile dinauntru sunt distruse FARA sa-si mai
  // joace tranzitia de iesire. Masurat: 0 cadre de animatie cu each imbricat pe
  // obiecte, 13 cadre cu acelasi rand intr-un each de nivel superior.
  // Cu chei constante, blocul exterior nu se mai schimba niciodata, iar cel
  // interior se comporta ca oricare altul.
  // TOATE grupele, inclusiv cele goale. Un `{#if}` care se stinge cand grupa
  // ramane fara randuri ar distruge blocul in care tocmai pleaca ultimul rand —
  // iar atunci Svelte nu-i mai joaca iesirea. Adica exact cazul cel mai vizibil
  // (bifezi ultimul restant) ar fi ramas fara animatie. Sablonul ascunde capul
  // gol; un cap nu are nevoie de tranzitie, un rand da.
  const out = {}
  let n = 0
  for (const g of GRUPE) {
    const items = cosuri.get(g.id)
    // `start` = cate randuri sunt in grupele de dinainte, ca indexul mono din
    // stanga sa numere peste TOATE grupele („01, 02, 03…"), nu de la capat in
    // fiecare.
    out[g.id] = { id: g.id, titlu: g.titlu, ton: g.ton, items, start: n }
    n += items.length
  }
  return out
}

/** Ordinea de randare. Constanta la nivel de modul, deci aceleasi referinte de
 *  fiecare data — vezi comentariul de mai sus. */
export const ORDINE_GRUPE = GRUPE.map(g => g.id)

/** Eticheta scurta a termenului, pentru randul din lista: „azi", „mâine",
 *  „acum 3 zile", „vineri", „12 aug". Data plina nu spune nimic pe telefon —
 *  „30.07.2026" te pune sa calculezi, „mâine" nu. */
const ZILE = ['duminică', 'luni', 'marți', 'miercuri', 'joi', 'vineri', 'sâmbătă']

export function etichetaTermen(d) {
  const k = zilePanaLa(d)
  if (k === null) return ''
  if (k === 0) return 'azi'
  if (k === 1) return 'mâine'
  if (k === -1) return 'ieri'
  if (k < 0) return `acum ${-k} zile`
  // Pana la o saptamana numele zilei e cel mai usor de asezat in cap.
  if (k <= 6) return ZILE[new Date(String(d).slice(0, 10)).getDay()]
  const t = new Date(String(d).slice(0, 10))
  return t.toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })
}

/** Aceeasi informatie, dar pentru COLOANA de 46px de la marginea randului.
 *
 *  `etichetaTermen` scrie „acum 12 zile" — 11 caractere, care la 12px monospace
 *  cer ~80px. Pironita intr-o coloana de 46 ar fi fost taiata pe toate randurile
 *  restante, adica exact pe cele care conteaza. Restanta se scrie deci ca
 *  marime cu semn: „−12 z". Semnul e minusul tipografic (U+2212), nu cratima:
 *  in DM Mono cratima e la jumatatea inaltimii cifrelor si se citea ca liniuta
 *  de despartire, nu ca „minus".
 *
 *  Zilele apropiate raman cuvinte („azi", „mâine", numele zilei): un cuvant se
 *  recunoaste fara sa fie citit, o cifra nu. */
export function etichetaTermenScurt(d) {
  const k = zilePanaLa(d)
  if (k === null) return '—'
  if (k === 0) return 'azi'
  if (k === 1) return 'mâine'
  if (k < 0) return `−${-k} z`
  if (k <= 6) return ZILE[new Date(String(d).slice(0, 10)).getDay()].slice(0, 3)
  // `zz.ll`, NU „26 aug." — coloana termenului are 46px, iar „26 aug." cere ~55
  // in DM Mono la 13px, deci se taia la „26 a…" (raportat de Ion: „se vede doar
  // numarul, luna doar prima litera"). Forma numerica incape, se aliniaza pe
  // cifre ca restul coloanei, si scoate din ea un cuvant care oricum n-avea ce
  // cauta intr-o coloana mono — regula sistemului: daca textul se poate traduce,
  // nu e mono.
  const t = new Date(String(d).slice(0, 10))
  return `${t.getDate()}.${String(t.getMonth() + 1).padStart(2, '0')}`
}
