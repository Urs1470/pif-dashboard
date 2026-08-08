// O DEPLASARE = zile CONSECUTIVE cu aceeasi cheie `loc|client`.
//
// Regula asta se citea in doua locuri si trebuia sa insemne acelasi lucru in
// amandoua: in Calendar (unde deseneaza chenarul iesirii si captura din antet) si
// in notificarea de plecare pe teren (turul 15 — alarma pe PRIMA zi a unei iesiri
// la Site, seara dinainte). Scrisa de doua ori, s-ar rupe tacut la prima
// schimbare: calendarul ar arata o iesire, telefonul ar suna de doua ori.
//
// Aici e o singura definitie, peste lista de perioade — aceeasi din care se
// deseneaza calendarul.

import { addDays, diffDays, nextWorkday } from './calendarDates.js'

/** Cheia care spune „aceeasi iesire": unde esti si la cine. */
export function cheieDeplasare(p) {
  const loc = p.locatie === 'sediu' ? 'sediu' : 'site'
  return `${loc}|${(p.client || '').trim().toLowerCase()}`
}

/**
 * Deplasarile dintr-o lista de perioade, in ordinea zilei de plecare.
 *
 * Fiecare: `{ cheie, client, sediu, start, end, items }`, unde `items` e un Map
 * id -> perioada (aceeasi forma pe care o folosea Calendarul).
 *
 * O pauza de o zi RUPE deplasarea in doua: 28-29-30 la Continental e o singura
 * iesire, dar 28 si 30 sunt doua.
 */
export function grupeazaDeplasari(perioade) {
  // zi -> cheie -> perioade
  const peZi = new Map()
  for (const p of perioade || []) {
    const a = p.data_start
    if (!a) continue
    const b = p.data_sfarsit || a
    const n = Math.max(0, diffDays(a, b) ?? 0)
    for (let i = 0; i <= n; i++) {
      const iso = addDays(a, i)
      if (!peZi.has(iso)) peZi.set(iso, new Map())
      const g = peZi.get(iso)
      const k = cheieDeplasare(p)
      if (!g.has(k)) g.set(k, [])
      g.get(k).push(p)
    }
  }

  const perCheie = new Map()
  for (const iso of [...peZi.keys()].sort()) {
    for (const [k, lista] of peZi.get(iso)) {
      if (!perCheie.has(k)) perCheie.set(k, [])
      perCheie.get(k).push({ iso, lista })
    }
  }

  const out = []
  for (const [cheie, zile] of perCheie) {
    let cur = null
    for (const { iso, lista } of zile) {
      if (cur && diffDays(cur.end, iso) === 1) cur.end = iso
      else {
        const p0 = lista[0]
        cur = {
          cheie,
          client: (p0.client || '').trim(),
          sediu: p0.locatie === 'sediu',
          start: iso,
          end: iso,
          items: new Map(),
        }
        out.push(cur)
      }
      for (const p of lista) cur.items.set(p.id, p)
    }
  }
  return out.sort((a, b) => a.start.localeCompare(b.start))
}

/* ==================================================================
   CE SE INTAMPLA CU VECINUL, cand o perioada isi schimba intervalul.

   Regula e a DATELOR, nu a ecranului: se aplica la fel din Calendar (unde tragi
   de capete) si din formularul perioadei (unde scrii datele). De aceea sta aici
   si nu in pagina care se intampla s-o ceara prima.

   Ce se intampla depinde de CINE e vecinul, iar cele doua cazuri nu seamana:

     acelasi `loc|client`  -> nu e coliziune, e CONTINUARE. Nu se scrie nimic in
       plus: `grupeazaDeplasari` uneste deja zilele consecutive pe cheia asta,
       deci in clipa in care se ating, datele spun „o singura iesire".
     alt loc sau alt client -> nu poti fi in doua locuri in aceeasi zi, deci
       vecinul se da mai incolo, cu o zi LUCRATOARE, pastrandu-si durata.
   ================================================================== */

/** Zilele lui `p`, ca pereche [inceput, sfarsit] — sfarsitul lipsa = o zi. */
function interval(p) {
  return [p.data_start, p.data_sfarsit || p.data_start]
}

/** Se ating sau se suprapun cele doua intervale? (lipite = se ating) */
export function seAting(p, start, sfarsit) {
  const [a, b] = interval(p)
  return !(b < addDays(start, -1) || a > addDays(sfarsit, 1))
}

/** Se suprapun efectiv? (lipite NU inseamna suprapuse — poti termina joi la un
 *  client si incepe vineri la altul.) */
export function seSuprapun(p, start, sfarsit) {
  const [a, b] = interval(p)
  return !(b < start || a > sfarsit)
}

/**
 * Deplasarea din care ar face parte `fixata` daca s-ar salva asa, cu vecinii ei
 * la aceeasi cheie. Raspunde la „cate zile are iesirea, cu totul".
 *
 * `fixata` poate fi o perioada noua (fara `id`).
 */
export function deplasareaCu(perioade, fixata) {
  const id = fixata.id ?? '__nou__'
  const lista = [
    { ...fixata, id },
    ...(perioade || []).filter((q) => !(fixata.id != null && q.id === fixata.id)),
  ]
  return grupeazaDeplasari(lista).find((d) => d.items.has(id)) || null
}

/**
 * Perioadele care se muta ca sa nu stea peste `fixata`, care ramane unde ai
 * cerut-o. Intoarce DOAR ce s-a mutat: `[{ p, data_start, data_sfarsit }]`.
 *
 * IMPINGEREA SE PROPAGA. Un singur pas ar putea aseza vecinul fix peste
 * urmatorul — adica exact suprapunerea pe care regula o interzice, doar mutata
 * cu o casuta mai incolo. Deci se rezolva pana nu mai ramane nicio ciocnire.
 * Bucla se opreste fiindca fiecare mutare impinge strict la DREAPTA.
 */
export function rezolvaCiocniri(perioade, fixata) {
  const [s0, f0] = interval(fixata)
  if (!s0 || !f0) return []

  const stare = [{ p: fixata, s: s0, f: f0, cheie: cheieDeplasare(fixata), fix: true }]
  for (const q of perioade || []) {
    if (!q?.data_start) continue
    if (fixata.id != null && q.id === fixata.id) continue
    const [a, b] = interval(q)
    stare.push({ p: q, s: a, f: b, cheie: cheieDeplasare(q), fix: false })
  }

  const mutate = new Map()
  for (let paza = 0; paza < 60; paza++) {
    let schimbat = false
    for (const r of stare) {
      if (r.fix) continue
      let pana = ''
      for (const a of stare) {
        // Aceeasi cheie = aceeasi iesire: se pot atinge, nu se ciocnesc.
        if (a === r || a.cheie === r.cheie) continue
        if (r.f < a.s || r.s > a.f) continue
        // Cine se da la o parte: cel care incepe mai TARZIU. Perioada ceruta e
        // fixa — ea e ce ai scris, restul se aseaza in jurul ei.
        if (a.fix || a.s < r.s || (a.s === r.s && String(a.p.id) < String(r.p.id))) {
          if (a.f > pana) pana = a.f
        }
      }
      if (!pana) continue
      const durata = Math.max(0, diffDays(r.s, r.f))
      r.s = nextWorkday(addDays(pana, 1))
      r.f = addDays(r.s, durata)
      mutate.set(r.p.id, { p: r.p, data_start: r.s, data_sfarsit: r.f })
      schimbat = true
      break                                   // o mutare poate naste alta
    }
    if (!schimbat) break
  }
  return [...mutate.values()].sort((a, b) => a.data_start.localeCompare(b.data_start))
}
