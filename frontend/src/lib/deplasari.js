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

import { addDays, diffDays } from './calendarDates.js'

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
