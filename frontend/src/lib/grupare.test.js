// Gruparea pe termen: aceeasi functie aseaza „Există deja" din foaia de adaugare si
// listele de taskuri, deci o greseala aici muta un task restant sub cele de maine pe
// toate ecranele deodata. Termenele se construiesc RELATIV la azi (ziua locala), ca
// testul sa spuna acelasi lucru in orice zi ar rula.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { grupeazaDupaTermen, ORDINE_GRUPE, etichetaTermen, etichetaTermenScurt } from './grupare.js'
import { localToday, addDays } from './planDates.js'

const zi = (n) => addDays(localToday(), n)
const ids = (g) => g.items.map(t => t.id)

test('ordinea grupelor: restante, azi, maine, zilele astea, mai tarziu, fara termen', () => {
  assert.deepEqual(ORDINE_GRUPE, ['restant', 'azi', 'maine', 'saptamana', 'tarziu', 'fara'])
})

test('fiecare task in grupa termenului lui', () => {
  const g = grupeazaDupaTermen([
    { id: 'r', data_scadenta: zi(-2) },
    { id: 'a', data_scadenta: zi(0) },
    { id: 'm', data_scadenta: zi(1) },
    { id: 's2', data_scadenta: zi(2) },
    { id: 's7', data_scadenta: zi(7) },
    { id: 't', data_scadenta: zi(8) },
    { id: 'f', data_scadenta: '' },
    { id: 'n', data_scadenta: null },
  ])
  assert.deepEqual(ids(g.restant), ['r'])
  assert.deepEqual(ids(g.azi), ['a'])
  assert.deepEqual(ids(g.maine), ['m'])
  assert.deepEqual(ids(g.saptamana), ['s2', 's7'])
  assert.deepEqual(ids(g.tarziu), ['t'])
  assert.deepEqual(ids(g.fara), ['f', 'n'])
})

test('toate grupele exista, si cele goale (altfel iesirea ultimului rand n-ar mai juca)', () => {
  const g = grupeazaDupaTermen([])
  assert.deepEqual(Object.keys(g), ORDINE_GRUPE)
  for (const id of ORDINE_GRUPE) assert.deepEqual(g[id].items, [], id)
})

test('in grupa: termen crescator, iar la egalitate ordinea venita de la server', () => {
  const g = grupeazaDupaTermen([
    { id: 'x5', data_scadenta: zi(5) },
    { id: 'x3a', data_scadenta: zi(3) },
    { id: 'x3b', data_scadenta: zi(3) },
    { id: 'x2', data_scadenta: zi(2) },
  ])
  assert.deepEqual(ids(g.saptamana), ['x2', 'x3a', 'x3b', 'x5'])
})

test('`start` numara peste toate grupele (indexul „01, 02…" nu reincepe)', () => {
  const g = grupeazaDupaTermen([
    { id: 'r', data_scadenta: zi(-1) }, { id: 'a1', data_scadenta: zi(0) },
    { id: 'a2', data_scadenta: zi(0) }, { id: 'f', data_scadenta: '' },
  ])
  assert.equal(g.restant.start, 0)
  assert.equal(g.azi.start, 1)
  assert.equal(g.fara.start, 3)
})

test('termenul se poate citi din alt camp', () => {
  const g = grupeazaDupaTermen([{ id: 'p', zi: zi(0) }], (t) => t.zi)
  assert.deepEqual(ids(g.azi), ['p'])
})

test('etichetele de termen', () => {
  assert.equal(etichetaTermen(zi(0)), 'azi')
  assert.equal(etichetaTermen(zi(1)), 'mâine')
  assert.equal(etichetaTermen(zi(-1)), 'ieri')
  assert.equal(etichetaTermen(zi(-3)), 'acum 3 zile')
  assert.equal(etichetaTermen(''), '')
  // Coloana scurta: minusul TIPOGRAFIC (U+2212), nu cratima — vezi comentariul din grupare.js.
  assert.equal(etichetaTermenScurt(zi(-12)), '−12 z')
  assert.equal(etichetaTermenScurt(zi(0)), 'azi')
  assert.equal(etichetaTermenScurt(null), '—')
})
