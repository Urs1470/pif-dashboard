// Teste pentru stratul de verdicte (LIMITS / computeVerdicts / worstVerdict).
//
// Rulare: `npm test`.
//
// Ce apara: un verdict gresit e mai rau decat lipsa lui — spune "e in regula"
// unde nu e. De aia se verifica si structura (fiecare regula trimite la un
// rezultat care exista, fiecare verdict are motiv scris), si comportamentul la
// praguri (sub prag / peste prag / la limita).

import test from 'node:test'
import assert from 'node:assert/strict'
import { MODULES, LIMITS, VERDICT_RANK, computeModule, computeVerdicts, worstVerdict } from './driveCalc.js'

const mod = (id) => MODULES.find((m) => m.id === id)
const vals = (m, over = {}) => ({ ...Object.fromEntries(m.fields.map((f) => [f.key, f.default])), ...over })
// Verdictele unui modul pentru un set de intrari.
function verd(id, over = {}) {
  const m = mod(id)
  const v = vals(m, over)
  return computeVerdicts(m, v, computeModule(m, v))
}
const stare = (id, cheie, over = {}) => verd(id, over)[cheie]?.st

test('LIMITS trimite doar la module si rezultate care exista', () => {
  for (const [id, reguli] of Object.entries(LIMITS)) {
    const m = mod(id)
    assert.ok(m, `LIMITS["${id}"]: modul inexistent`)
    const chei = new Set(m.results.map((r) => r.key))
    for (const k of Object.keys(reguli)) {
      assert.ok(chei.has(k), `LIMITS["${id}"]["${k}"]: rezultat inexistent in modul`)
      assert.equal(typeof reguli[k], 'function', `LIMITS["${id}"]["${k}"]: nu e functie`)
    }
  }
})

test('fiecare verdict are stare valida si motiv scris', () => {
  for (const id of Object.keys(LIMITS)) {
    const m = mod(id)
    const v = vals(m)
    const vd = computeVerdicts(m, v, computeModule(m, v))
    for (const [k, x] of Object.entries(vd)) {
      assert.ok(VERDICT_RANK[x.st] != null, `${id}.${k}: stare necunoscuta "${x.st}"`)
      assert.ok(
        typeof x.de === 'string' && x.de.trim().length > 10,
        `${id}.${k}: verdict fara motiv scris — o bulina fara explicatie nu ajuta pe nimeni`
      )
      // Sursa pragului e obligatorie cand spui ca ceva e in afara limitelor.
      if (x.st !== 'ok') {
        assert.ok(x.src && x.src.trim(), `${id}.${k}: verdict "${x.st}" fara sursa pragului`)
      }
    }
  }
})

test('verdictele nu arunca pe intrari zero sau lipsa', () => {
  for (const id of Object.keys(LIMITS)) {
    const m = mod(id)
    const zero = Object.fromEntries(m.fields.map((f) => [f.key, 0]))
    assert.doesNotThrow(() => computeVerdicts(m, zero, computeModule(m, zero)), `${id}: arunca pe zero`)
    assert.doesNotThrow(() => computeVerdicts(m, {}, {}), `${id}: arunca pe obiect gol`)
  }
})

test('worstVerdict alege cea mai grava stare', () => {
  assert.equal(worstVerdict({}), null)
  assert.equal(worstVerdict({ a: { st: 'ok' } }), 'ok')
  assert.equal(worstVerdict({ a: { st: 'ok' }, b: { st: 'atentie' } }), 'atentie')
  assert.equal(worstVerdict({ a: { st: 'critic' }, b: { st: 'atentie' } }), 'critic')
})

test('un modul fara praguri nu primeste verdict (≠ "e in regula")', () => {
  const fara = MODULES.find((m) => !LIMITS[m.id] && m.results.length)
  assert.ok(fara, 'ar trebui sa existe module inca fara praguri')
  assert.deepEqual(computeVerdicts(fara, vals(fara), {}), {})
  assert.equal(worstVerdict(computeVerdicts(fara, vals(fara), {})), null)
})

// ---- Comportament la praguri ----

test('unda-reflectata: sub sigur / intre / peste critic', () => {
  // Cu tr=0.1 us si vw=150 m/us: L_sigur = 1.5 m, L_critic = 7.5 m.
  assert.equal(stare('unda-reflectata', 'Lcrit', { L: 1 }), 'ok')
  assert.equal(stare('unda-reflectata', 'Lcrit', { L: 5 }), 'atentie')
  assert.equal(stare('unda-reflectata', 'Lcrit', { L: 30 }), 'critic')
})

test('cablu: pragurile de 3 % si 5 % la caderea de tensiune', () => {
  assert.equal(stare('cablu', 'dUproc', { L: 50 }), 'ok')        // ~1.93 %
  assert.equal(stare('cablu', 'dUproc', { L: 100 }), 'atentie')  // ~3.86 %
  assert.equal(stare('cablu', 'dUproc', { L: 160 }), 'critic')   // ~6.18 %
})

test('dezechilibru: peste 5 % nu se porneste motorul', () => {
  assert.equal(stare('dezechilibru', 'UV', { Uab: 400, Ubc: 400, Uca: 400 }), 'ok')
  assert.equal(stare('dezechilibru', 'UV', { Uab: 400, Ubc: 390, Uca: 380 }), 'atentie')
  assert.equal(stare('dezechilibru', 'UV', { Uab: 420, Ubc: 390, Uca: 360 }), 'critic')
})

test('npsh: marja sub 0,5 m inseamna cavitatie', () => {
  assert.equal(stare('npsh', 'marja', { Hasp: 2 }), 'ok')          // marja ~7.6 m
  assert.equal(stare('npsh', 'marja', { Hasp: -4.7 }), 'atentie')  // marja ~0.89 m
  assert.equal(stare('npsh', 'marja', { Hasp: -5.4 }), 'critic')   // marja ~0.19 m
})

test('motor-termic: peste incalzirea nominala e critic', () => {
  assert.equal(stare('motor-termic', 'thetaf', { I: 20, In: 28 }), 'ok')
  assert.equal(stare('motor-termic', 'thetaf', { I: 27, In: 28 }), 'atentie')
  assert.equal(stare('motor-termic', 'thetaf', { I: 33, In: 28 }), 'critic')
})

test('ieee519: depasirea limitei de la PCC', () => {
  assert.equal(stare('ieee519', 'depasire', { THDest: 5 }), 'ok')
  assert.equal(stare('ieee519', 'depasire', { THDest: 10 }), 'atentie')
  assert.equal(stare('ieee519', 'depasire', { THDest: 35 }), 'critic')
})

test('regimuri-s: rezerva termica sub 1 inseamna ciclu prea greu', () => {
  assert.equal(stare('regimuri-s', 'marja', { Pload: 18, tload: 60, tpauza: 90 }), 'ok')
  assert.equal(stare('regimuri-s', 'marja', { Pload: 30, tload: 60, tpauza: 90 }), 'critic')
})

test('raport-inertie: tinta < 5 servo, < 10 uz general', () => {
  // Jsarc = 2.5 kg·m², i = 5 => J redusa = 2.5/25 = 0.1 kg·m².
  // RJ = Jred/Jmot: 0.1/0.05 = 2 (bun), 0.1/0.014 ≈ 7 (uz general), 0.1/0.005 = 20 (instabil).
  assert.equal(stare('raport-inertie', 'RJ', { Jmot: 0.05 }), 'ok')
  assert.equal(stare('raport-inertie', 'RJ', { Jmot: 0.014 }), 'atentie')
  assert.equal(stare('raport-inertie', 'RJ', { Jmot: 0.005 }), 'critic')
  // Verdictul trebuie sa se inrautateasca monoton cu scaderea inertiei motorului.
  const rank = [0.05, 0.014, 0.005].map((j) => VERDICT_RANK[stare('raport-inertie', 'RJ', { Jmot: j })])
  assert.ok(rank[0] <= rank[1] && rank[1] <= rank[2], `verdict nemonoton: ${rank.join(' -> ')}`)
})
