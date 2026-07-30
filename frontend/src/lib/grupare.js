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
  { id: 'maine', titlu: 'Mâine', ton: 'warning', test: (k) => k === 1 },
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
  return GRUPE
    .map(g => ({ id: g.id, titlu: g.titlu, ton: g.ton, items: cosuri.get(g.id) }))
    .filter(g => g.items.length)
}

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
