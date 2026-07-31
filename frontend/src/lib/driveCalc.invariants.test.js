// Invariante structurale peste TOATE modulele calculatorului.
//
// Rulare: `npm test` (runner-ul built-in `node --test`, zero dependinte noi).
//
// Ce apara testele astea: driveCalc.js e un fisier de 4000+ de linii scris
// declarativ, in care o greseala de tastare intr-o cheie sau o formula care
// imparte la zero la valorile ei implicite NU da eroare — da doar "—" pe card,
// intr-un modul pe care poate nu-l deschizi luni de zile. Invariantele de mai
// jos transforma tacerea aia in test rosu.
//
// Regula: aici NU verificam valori numerice (alea sunt in driveCalc.formule.test.js),
// ci contractul modelului de date.

import test from 'node:test'
import assert from 'node:assert/strict'
import {
  MODULES, MODULE_ORDER, SOURCES, FAMILIES, CATEGORIES, APP_OF, CAT_OF,
  MOTOR_FAMS, APPLICATIONS, catOf, computeModule, computeCharts, CHART_DESC,
} from './driveCalc.js'

// Carduri pur documentare: nu au intrari si nu calculeaza nimic (tabel/explicatie).
// Lista e explicita ca sa prinda un modul NOU care ramane din greseala fara rezultate.
const CARDURI_REFERINTA = new Set(['grade-ip', 'moduri-control', 'retea-emc'])

const defaults = (m) => Object.fromEntries(m.fields.map((f) => [f.key, f.default]))

test('id-urile modulelor sunt unice', () => {
  const seen = new Set()
  for (const m of MODULES) {
    assert.ok(!seen.has(m.id), `id duplicat: ${m.id}`)
    seen.add(m.id)
  }
})

test('fiecare modul are titlu, familie valida si categorie valida', () => {
  const fams = new Set([...FAMILIES.map((f) => f.id), ...MOTOR_FAMS.map((f) => f.id)])
  const cats = new Set(CATEGORIES.map((c) => c.id))
  for (const m of MODULES) {
    assert.ok(m.title && m.title.trim(), `${m.id}: titlu lipsa`)
    assert.ok(fams.has(m.family), `${m.id}: familie necunoscuta "${m.family}"`)
    assert.ok(cats.has(catOf(m)), `${m.id}: catOf da o categorie inexistenta "${catOf(m)}"`)
  }
})

test('campurile au chei unice si valori implicite finite', () => {
  for (const m of MODULES) {
    const keys = new Set()
    for (const f of m.fields) {
      assert.ok(f.key, `${m.id}: camp fara cheie`)
      assert.ok(!keys.has(f.key), `${m.id}: cheie de camp duplicata "${f.key}"`)
      keys.add(f.key)
      assert.ok(f.label && f.label.trim(), `${m.id}.${f.key}: eticheta lipsa`)
      assert.ok(Number.isFinite(f.default), `${m.id}.${f.key}: default nefinit (${f.default})`)
      if (f.min != null) {
        assert.ok(f.default >= f.min, `${m.id}.${f.key}: default ${f.default} sub min ${f.min}`)
      }
    }
  }
})

test('rezultatele au chei unice, eticheta si functie de calcul', () => {
  for (const m of MODULES) {
    const keys = new Set()
    for (const r of m.results) {
      assert.ok(r.key, `${m.id}: rezultat fara cheie`)
      assert.ok(!keys.has(r.key), `${m.id}: cheie de rezultat duplicata "${r.key}"`)
      keys.add(r.key)
      assert.ok(r.label && r.label.trim(), `${m.id}.${r.key}: eticheta lipsa`)
      assert.equal(typeof r.calc, 'function', `${m.id}.${r.key}: calc nu e functie`)
      if (r.dec != null) {
        assert.ok(Number.isInteger(r.dec) && r.dec >= 0, `${m.id}.${r.key}: dec invalid (${r.dec})`)
      }
    }
  }
})

test('un modul are si intrari si rezultate (exceptie: cardurile de referinta)', () => {
  for (const m of MODULES) {
    if (CARDURI_REFERINTA.has(m.id)) {
      assert.equal(m.fields.length, 0, `${m.id}: e listat card de referinta dar are campuri`)
      assert.equal(m.results.length, 0, `${m.id}: e listat card de referinta dar are rezultate`)
      continue
    }
    assert.ok(m.fields.length > 0, `${m.id}: fara campuri (daca e card de referinta, adauga-l in lista)`)
    assert.ok(m.results.length > 0, `${m.id}: fara rezultate (daca e card de referinta, adauga-l in lista)`)
  }
})

// Cel mai valoros test din fisier: un card care afiseaza "—" din start e un card
// stricat. La valorile lui implicite, orice rezultat trebuie sa dea un numar.
test('la valorile implicite, fiecare rezultat da un numar finit', () => {
  for (const m of MODULES) {
    const r = computeModule(m, defaults(m))
    for (const res of m.results) {
      assert.ok(
        Number.isFinite(r[res.key]),
        `${m.id}.${res.key}: da "${r[res.key]}" la valorile implicite (card mort la deschidere)`
      )
    }
  }
})

test('computeModule nu arunca pe intrari lipsa sau zero', () => {
  for (const m of MODULES) {
    assert.doesNotThrow(() => computeModule(m, {}), `${m.id}: arunca pe obiect gol`)
    const zero = Object.fromEntries(m.fields.map((f) => [f.key, 0]))
    assert.doesNotThrow(() => computeModule(m, zero), `${m.id}: arunca pe intrari zero`)
  }
})

test('MODULE_ORDER acopera exact modulele existente, fara duplicate', () => {
  const ids = new Set(MODULES.map((m) => m.id))
  const dup = MODULE_ORDER.filter((x, i) => MODULE_ORDER.indexOf(x) !== i)
  assert.deepEqual(dup, [], `duplicate in MODULE_ORDER: ${dup.join(', ')}`)
  const fantoma = MODULE_ORDER.filter((id) => !ids.has(id))
  assert.deepEqual(fantoma, [], `MODULE_ORDER trimite la module inexistente: ${fantoma.join(', ')}`)
  const neasezate = [...ids].filter((id) => !MODULE_ORDER.includes(id))
  assert.deepEqual(neasezate, [], `module fara loc in MODULE_ORDER (apar la coada): ${neasezate.join(', ')}`)
})

test('fiecare modul are sursa citata', () => {
  for (const m of MODULES) {
    assert.ok(
      typeof SOURCES[m.id] === 'string' && SOURCES[m.id].trim(),
      `${m.id}: fara intrare in SOURCES — regula vaultului: nicio valoare fara sursa`
    )
  }
})

test('APP_OF si CAT_OF trimit doar la module existente', () => {
  const ids = new Set(MODULES.map((m) => m.id))
  for (const k of Object.keys(APP_OF)) assert.ok(ids.has(k), `APP_OF["${k}"]: modul inexistent`)
  for (const k of Object.keys(CAT_OF)) assert.ok(ids.has(k), `CAT_OF["${k}"]: modul inexistent`)
  const apps = new Set(APPLICATIONS.map((a) => a.id))
  for (const [k, v] of Object.entries(APP_OF)) {
    assert.ok(apps.has(v), `APP_OF["${k}"] = "${v}": sub-tab de aplicatie inexistent`)
  }
})

test('graficele se construiesc si au descriere pe fiecare', () => {
  for (const m of MODULES) {
    if (!m.charts) continue
    assert.doesNotThrow(() => computeCharts(m, defaults(m)), `${m.id}: computeCharts arunca`)
    const d = CHART_DESC[m.id]
    assert.ok(d, `${m.id}: are ${m.charts.length} grafic(e) dar nicio descriere in CHART_DESC`)
    assert.equal(
      d.length, m.charts.length,
      `${m.id}: ${m.charts.length} grafice dar ${d.length} descrieri`
    )
  }
})
