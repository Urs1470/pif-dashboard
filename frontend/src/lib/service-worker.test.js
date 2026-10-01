// Teste pe service worker-ul dashboardului (static/service-worker.js): sa lase Torqa web in pace.
//
// Rulare: `npm test` (runner-ul built-in `node --test`).
//
// De ce. Torqa web (build Angular) sta pe acelasi domeniu, la /torqa/, cu propriul service
// worker (`ngsw-worker.js`, scope /torqa/) si propriile cache-uri (`ngsw:...`). Worker-ul
// dashboardului are scope / si ar prinde altfel navigarea LA /torqa/ (pana se instaleaza al
// lui), ar pune in cache raspunsurile API cerute de pagina si le-ar da inapoi cand cade
// reteaua, iar la `activate` ar sterge cache-urile lui Angular. Nimic din asta nu se vede in
// build; se vede abia cand Torqa web „uita” datele sau nu mai porneste offline.
//
// Fisierul service-worker.js nu e modul si nu exporta nimic: se executa intr-un context `vm`
// cu un `self` de mana, iar handler-ele inregistrate prin `addEventListener` se apeleaza cu
// evenimente false.

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const SURSA = readFileSync(new URL('../../../static/service-worker.js', import.meta.url), 'utf8')
const ORIGINE = 'https://pif.test'

function incarca({ cacheuri = [], ferestre = [] } = {}) {
  const handleri = {}
  const sters = []
  const deschise = []
  const ctx = {
    self: {
      location: { origin: ORIGINE },
      addEventListener: (tip, fn) => { handleri[tip] = fn },
      clients: {
        claim: async () => {},
        matchAll: async () => ferestre,
        openWindow: async (u) => { deschise.push(u) },
      },
      registration: { showNotification: async () => {} },
      skipWaiting() {},
    },
    caches: {
      keys: async () => [...cacheuri],
      delete: async (n) => { sters.push(n); return true },
      open: async () => ({ match: async () => undefined, put: async () => {} }),
    },
    fetch: async () => new Response('ok'),
    console: { log() {} },
    URL, Response, Headers, Promise,
  }
  vm.createContext(ctx)
  vm.runInContext(SURSA, ctx)
  return { handleri, sters, deschise, ctx }
}

/** Trimite o cerere GET prin handler-ul `fetch`. Intoarce true daca worker-ul a RASPUNS la ea
 *  (a apelat `respondWith`), false daca a lasat-o sa treaca direct la retea. */
async function raspunde(sw, cale, { antete = {}, accept = 'text/html', mode = 'navigate', origine = ORIGINE } = {}) {
  let raspuns = null
  const h = new Headers({ accept, ...antete })
  const event = {
    request: { url: origine + cale, method: 'GET', headers: h, mode },
    respondWith(p) { raspuns = p },
    waitUntil() {},
  }
  sw.handleri.fetch(event)
  if (raspuns) await raspuns.catch(() => {})
  return raspuns !== null
}

test('nu raspunde la nimic sub /torqa/ — nici documentul, nici fisierele, nici navigarea', async () => {
  const sw = incarca()
  const cai = ['/torqa', '/torqa/', '/torqa/index.html', '/torqa/main-ABCDEFGH.js', '/torqa/ngsw.json',
    '/torqa/ngsw-worker.js', '/torqa/assets/i18n/en.json', '/torqa/tag/azi/tasks', '/torqa/?x=1']
  for (const cale of cai) {
    for (const accept of ['text/html', '*/*', 'application/json']) {
      assert.equal(await raspunde(sw, cale, { accept }), false, `${cale} (${accept})`)
    }
  }
})

test('nu raspunde la cererile cu antetul X-Torqa (API-ul cerut de paginile Torqa)', async () => {
  const sw = incarca()
  for (const antet of ['X-Torqa', 'x-torqa', 'X-TORQA']) {
    assert.equal(await raspunde(sw, '/api/sync/snapshot', { antete: { [antet]: '1' }, accept: '*/*', mode: 'cors' }),
      false, antet)
  }
  assert.equal(await raspunde(sw, '/api/proiecte', { antete: { 'X-Torqa': '1' }, accept: 'application/json', mode: 'cors' }),
    false)
})

test('dashboardul isi pastreaza comportamentul: API-ul si documentele lui trec prin worker', async () => {
  const sw = incarca()
  assert.equal(await raspunde(sw, '/api/proiecte', { accept: 'application/json', mode: 'cors' }), true, 'API-ul dashboardului')
  assert.equal(await raspunde(sw, '/calc'), true, 'documentul /calc')
  assert.equal(await raspunde(sw, '/'), true, 'documentul /')
  assert.equal(await raspunde(sw, '/assets/index-abc.js', { accept: '*/*', mode: 'cors' }), true, '/assets/')
})

test('prefixul /torqa/ e exact: /torqa-vechi/ si /torqau nu sunt Torqa', async () => {
  const sw = incarca()
  assert.equal(await raspunde(sw, '/torqa-vechi/x'), true)
  assert.equal(await raspunde(sw, '/torqau'), true)
  assert.equal(await raspunde(sw, '/altceva/torqa/x'), true)
})

test('la activate nu se sterg cache-urile Angular (ngsw:...), ci doar cele straine vechi', async () => {
  const sw = incarca()
  const curente = [vm.runInContext('STATIC_CACHE', sw.ctx), vm.runInContext('API_CACHE', sw.ctx)]
  const angular = ['ngsw:/torqa/:db:control', 'ngsw:/torqa/:1:assets:app:cache', 'ngsw:/torqa/:db:ngsw:/torqa/:cache']
  const vechi = ['torqa-static-v1', 'torqa-api-v1', 'cache-strain']
  const sw2 = incarca({ cacheuri: [...curente, ...angular, ...vechi] })
  let asteptat = null
  sw2.handleri.activate({ waitUntil(p) { asteptat = p } })
  await asteptat
  assert.deepEqual(sw2.sters.sort(), [...vechi].sort(), 'doar cele vechi ale dashboardului si cele straine')
  for (const nume of [...curente, ...angular]) assert.ok(!sw2.sters.includes(nume), `${nume} ramane`)
})

test('apasarea pe o notificare nu muta si nu aduce in fata o fereastra Torqa', async () => {
  const mesaje = { torqa: [], dashboard: [] }
  const fereastra = (url, cheie) => ({
    url: ORIGINE + url,
    focus: async () => {},
    postMessage: (m) => mesaje[cheie].push(m),
  })
  const sw = incarca({ ferestre: [fereastra('/torqa/', 'torqa'), fereastra('/#/tasks', 'dashboard')] })
  let asteptat = null
  sw.handleri.notificationclick({
    action: '',
    notification: { data: { url: '/#/tasks/abc' }, close() {}, tag: 't' },
    waitUntil(p) { asteptat = p },
  })
  await asteptat
  assert.equal(mesaje.torqa.length, 0, 'fereastra Torqa nu primeste nimic')
  // Mesajul e creat in contextul `vm` (alt Object.prototype): se compara ca JSON.
  assert.deepEqual(JSON.parse(JSON.stringify(mesaje.dashboard)), [{ type: 'NAVIGHEAZA', url: '/#/tasks/abc' }])
})

test('daca singura fereastra deschisa e Torqa, notificarea deschide dashboardul intr-una noua', async () => {
  const torqa = { url: ORIGINE + '/torqa/', focus: async () => {}, postMessage: () => assert.fail('nu trebuie') }
  const sw = incarca({ ferestre: [torqa] })
  let asteptat = null
  sw.handleri.notificationclick({
    action: '',
    notification: { data: { url: '/#/tasks/abc' }, close() {}, tag: 't' },
    waitUntil(p) { asteptat = p },
  })
  await asteptat
  assert.deepEqual(sw.deschise, ['/#/tasks/abc'])
})
