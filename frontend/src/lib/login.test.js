// Teste pe scriptul paginii de login (templates/login.html): unde te duce dupa PIN.
//
// Rulare: `npm test` (runner-ul built-in `node --test`).
//
// De ce. `/login?next=/torqa/` trebuie sa te intoarca la Torqa dupa PIN, iar un `next`
// care ar duce pe alt site trebuie sa duca la `/`. Regula e verificata pe server
// (teste/test_login_next.py), dar redirectul il face SCRIPTUL din pagina: daca nu mai
// trimite `next` sau nu mai citeste raspunsul, serverul isi face treaba degeaba si
// utilizatorul ajunge pe `/`, fara nicio eroare. Aici se ruleaza scriptul real din sablon,
// intr-un context `vm` cu un document de mana si un `fetch` care noteaza ce primeste.

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const HTML = readFileSync(new URL('../../../templates/login.html', import.meta.url), 'utf8')
// Cele doua <script>-uri cu nonce: primul e bootstrap-ul de tema din <head>, ultimul e logica.
const SCRIPTURI = [...HTML.matchAll(/<script nonce="\{\{ csp_nonce \}\}">([\s\S]*?)<\/script>/g)].map((m) => m[1])
const SCRIPT_LOGIN = SCRIPTURI[SCRIPTURI.length - 1]

function element(extra = {}) {
  return {
    value: '', dataset: {}, style: {},
    classList: { add() {}, remove() {}, contains: () => false },
    addEventListener() {}, setAttribute() {}, removeAttribute() {}, focus() {},
    ...extra,
  }
}

/** Pagina de login: formularul cu `data-next`, un PIN tastat, un `fetch` pe care il controlezi. */
function pagina({ dataNext = '/torqa/', raspuns }) {
  const elemente = {
    pin: element({ value: '135790' }),
    'login-form': element({ dataset: { next: dataNext } }),
    'error-message': element(),
  }
  const apeluri = []
  const fereastra = { location: { href: '' }, matchAll: undefined, matchMedia: () => ({ matches: false, addEventListener() {} }) }
  const ctx = {
    document: {
      getElementById: (id) => elemente[id] || element(),
      querySelector: () => element(),
      documentElement: element(),
    },
    window: fereastra,
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    fetch: async (url, opt) => {
      apeluri.push({ url, metoda: opt.method, corp: JSON.parse(opt.body) })
      return raspuns()
    },
    JSON, Promise, Object, Array, String,
  }
  vm.createContext(ctx)
  vm.runInContext(SCRIPT_LOGIN, ctx)
  return { ctx, apeluri, fereastra, elemente }
}

const ok = (corp) => () => ({ ok: true, json: async () => corp })

test('gaseste scriptul de login in sablon', () => {
  assert.ok(SCRIPTURI.length >= 2, 'doua scripturi cu nonce: tema si login')
  assert.match(SCRIPT_LOGIN, /async function handleLogin/)
})

test('dupa PIN te intoarce unde a cerut `next`, si il trimite serverului', async () => {
  const p = pagina({ dataNext: '/torqa/', raspuns: ok({ success: true, next: '/torqa/' }) })
  await p.ctx.handleLogin({ preventDefault() {} })
  assert.equal(p.apeluri.length, 1)
  assert.equal(p.apeluri[0].url, '/login')
  assert.equal(p.apeluri[0].metoda, 'POST')
  assert.deepEqual({ ...p.apeluri[0].corp }, { pin: '135790', next: '/torqa/' })
  assert.equal(p.fereastra.location.href, '/torqa/')
})

test('fara `next` in pagina te duce la radacina', async () => {
  const p = pagina({ dataNext: '', raspuns: ok({ success: true, next: '/' }) })
  await p.ctx.handleLogin({ preventDefault() {} })
  assert.equal(p.apeluri[0].corp.next, '/')
  assert.equal(p.fereastra.location.href, '/')
})

test('un `next` care ar duce pe alt site nu pleaca nici macar spre server si nu te muta nicaieri', async () => {
  for (const rau of ['//evil.com', 'https://evil.com', '/\\evil.com', 'javascript:alert(1)', '/\t/evil.com']) {
    const p = pagina({ dataNext: rau, raspuns: ok({ success: true, next: '/' }) })
    await p.ctx.handleLogin({ preventDefault() {} })
    assert.equal(p.apeluri[0].corp.next, '/', `trimis: ${JSON.stringify(rau)}`)
    assert.equal(p.fereastra.location.href, '/', `redirect: ${JSON.stringify(rau)}`)
  }
})

test('raspunsul serverului se verifica inca o data: un `next` primejdios de acolo duce la radacina', async () => {
  for (const rau of ['//evil.com', 'https://evil.com', '/\\evil.com', 5, null, ['/x']]) {
    const p = pagina({ dataNext: '/torqa/', raspuns: ok({ success: true, next: rau }) })
    await p.ctx.handleLogin({ preventDefault() {} })
    assert.equal(p.fereastra.location.href, '/', `raspuns: ${JSON.stringify(rau)}`)
  }
})

test('un raspuns fara JSON (server vechi) duce la radacina, nu la o eroare', async () => {
  const p = pagina({ raspuns: () => ({ ok: true, json: async () => { throw new Error('nu e JSON') } }) })
  await p.ctx.handleLogin({ preventDefault() {} })
  assert.equal(p.fereastra.location.href, '/')
})

test('PIN gresit: nu te muta si arata eroarea', async () => {
  let aratat = false
  const p = pagina({ raspuns: () => ({ ok: false, json: async () => ({ error: 'Invalid PIN' }) }) })
  p.elemente['error-message'].classList.add = (c) => { if (c === 'show') aratat = true }
  await p.ctx.handleLogin({ preventDefault() {} })
  assert.equal(p.fereastra.location.href, '')
  assert.ok(aratat, 'mesajul de eroare apare')
})
