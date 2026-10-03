// Teste pe service worker-ul care se retrage singur (static/service-worker.js).
//
// Rulare: `node --test teste/js/service-worker.test.mjs` (runner-ul built-in, fara pachete npm),
// sau `python scripts/verifica.py`, care le ruleaza pe toate din teste/js/.
//
// De ce. Interfata veche a dashboardului (SPA-ul Svelte) a fost retrasa, dar browserele care o
// instalasera au inca service worker-ul ei, cu scope `/`. Singura cale prin care scapa de el e
// ca URL-ul `/service-worker.js` sa serveasca un worker nou care il inlocuieste si se retrage.
// Modurile de esec, toate invizibile in build si in teste de pagina:
//   - un handler de `fetch` ramas: worker-ul nou ar prinde cereri (inclusiv navigarea la /torqa/
//     si API-ul Torqa) si ar putea sa le serveasca din cache;
//   - un `activate` care sterge `ngsw:...`: Torqa web ar „uita" datele si n-ar mai porni offline;
//   - dezinregistrarea sarita sau pusa dupa reincarcare: ferestrele ar fi controlate iar de el;
//   - reincarcare pe adresa cu fragment (`/#/tasks`): browserul face navigare in pagina, nu
//     reincarcare, si interfata veche ramane pe ecran din cache.
//
// Fisierul service-worker.js nu e modul si nu exporta nimic: se executa intr-un context `vm` cu un
// `self` de mana, iar handler-ele inregistrate prin `addEventListener` se apeleaza cu evenimente
// false. `jurnal` tine, in ordine, ce a facut worker-ul.

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'

const SURSA = readFileSync(new URL('../../static/service-worker.js', import.meta.url), 'utf8')
const ORIGINE = 'https://pif.test'

/** Un worker incarcat intr-un context cu `self`, `caches` si `clients` false.
 *  `ferestre`: ce intoarce `clients.matchAll` (doar cele controlate, ca in browser);
 *  `refuza`: nume de cache-uri sau adrese de ferestre pe care operatia trebuie sa pice. */
function incarca({ cacheuri = [], ferestre = [], refuza = [], unregisterPica = false } = {}) {
  const handleri = {}
  const jurnal = []
  const optiuniMatchAll = []
  const ctx = {
    self: {
      location: { origin: ORIGINE },
      addEventListener: (tip, fn) => { handleri[tip] = fn },
      skipWaiting() { jurnal.push('skipWaiting') },
      registration: {
        unregister: async () => {
          if (unregisterPica) throw new Error('unregister a picat')
          jurnal.push('unregister')
          return true
        },
      },
      clients: {
        matchAll: async (optiuni) => {
          optiuniMatchAll.push(JSON.parse(JSON.stringify(optiuni || {})))
          return ferestre.map((url) => ({
            url: ORIGINE + url,
            navigate: async (adresa) => {
              if (refuza.includes(url)) throw new TypeError('navigate refuzat')
              jurnal.push('navigate:' + adresa.slice(ORIGINE.length))
            },
          }))
        },
      },
    },
    caches: {
      keys: async () => [...cacheuri],
      delete: async (nume) => {
        if (refuza.includes(nume)) throw new Error('delete refuzat')
        jurnal.push('sters:' + nume)
        return true
      },
    },
    URL, Promise, Array, Object, JSON, Error, TypeError,
  }
  vm.createContext(ctx)
  vm.runInContext(SURSA, ctx)
  return { handleri, jurnal, optiuniMatchAll }
}

/** Declanseaza `activate` si asteapta ce a dat `waitUntil`. */
async function activeaza(sw) {
  let asteptat = null
  sw.handleri.activate({ waitUntil(p) { asteptat = p } })
  assert.ok(asteptat, 'activate trebuie sa-si tina worker-ul in viata cu waitUntil')
  await asteptat
}

const sterse = (sw) => sw.jurnal.filter((r) => r.startsWith('sters:')).map((r) => r.slice(6)).sort()
const navigate = (sw) => sw.jurnal.filter((r) => r.startsWith('navigate:')).map((r) => r.slice(9)).sort()

const NGSW = ['ngsw:/torqa/:db:control', 'ngsw:/torqa/:1:assets:app:cache', 'ngsw:/torqa/:db:ngsw:/torqa/:cache']
const VECHI = ['pif-static-v9', 'pif-api-v25', 'torqa-static-v284', 'torqa-api-v284']

test('nu are niciun handler in afara de install si activate: nici fetch, nici push, nici message', () => {
  const sw = incarca()
  assert.deepEqual(Object.keys(sw.handleri).sort(), ['activate', 'install'])
  assert.equal(sw.handleri.fetch, undefined, 'fara fetch nu poate raspunde la nicio cerere, nici sub /torqa/')
})

test('install preia imediat locul worker-ului vechi, fara sa astepte inchiderea paginilor', () => {
  const sw = incarca()
  sw.handleri.install({ waitUntil() {} })
  assert.deepEqual(sw.jurnal, ['skipWaiting'])
})

test('activate sterge cache-urile dashboardului vechi, din ambele serii de nume', async () => {
  const sw = incarca({ cacheuri: VECHI })
  await activeaza(sw)
  assert.deepEqual(sterse(sw), [...VECHI].sort())
})

test('activate nu atinge cache-urile Angular (ngsw:...) ale Torqa web, nici altceva ce nu e al lui', async () => {
  const straine = ['cache-strain', 'torqa-ceva-nou', 'pif']
  const sw = incarca({ cacheuri: [...VECHI, ...NGSW, ...straine] })
  await activeaza(sw)
  assert.deepEqual(sterse(sw), [...VECHI].sort(), 'doar cele patru prefixe vechi')
  for (const nume of [...NGSW, ...straine]) assert.ok(!sw.jurnal.includes('sters:' + nume), `${nume} ramane`)
})

test('activate se dezinregistreaza dupa ce a sters cache-urile si inainte sa reincarce ferestrele', async () => {
  const sw = incarca({ cacheuri: VECHI, ferestre: ['/#/tasks', '/calc'] })
  await activeaza(sw)
  const ordine = sw.jurnal.map((r) => r.split(':')[0])
  assert.equal(ordine.filter((r) => r === 'unregister').length, 1, 'o singura dezinregistrare')
  const unreg = ordine.indexOf('unregister')
  assert.ok(ordine.lastIndexOf('sters') < unreg, 'cache-urile se sterg inainte')
  assert.ok(ordine.indexOf('navigate') > unreg, 'ferestrele se reincarca dupa')
})

test('activate cere doar ferestrele controlate de el, nu pe cele necontrolate', async () => {
  const sw = incarca({ ferestre: ['/'] })
  await activeaza(sw)
  assert.equal(sw.optiuniMatchAll.length, 1)
  assert.equal(sw.optiuniMatchAll[0].type, 'window')
  assert.notEqual(sw.optiuniMatchAll[0].includeUncontrolled, true)
})

test('activate reincarca ferestrele din afara /torqa/, pe adresa FARA fragment', async () => {
  // Interfata veche tinea ruta in fragment: `navigate('/#/tasks')` din `/#/tasks` ar fi o navigare in
  // pagina, nu o reincarcare. Fara fragment, cererea merge la server, care raspunde cu 302 spre /torqa/.
  const sw = incarca({ ferestre: ['/#/tasks/abc', '/', '/calc', '/login?next=/torqa/', '/torqa-vechi/x', '/torqau'] })
  await activeaza(sw)
  assert.deepEqual(navigate(sw), ['/', '/', '/calc', '/login?next=/torqa/', '/torqa-vechi/x', '/torqau'].sort())
})

test('activate nu reincarca nicio fereastra Torqa web (/torqa si /torqa/...)', async () => {
  const sw = incarca({
    ferestre: ['/torqa', '/torqa/', '/torqa/tasks', '/torqa/tag/azi/tasks#x', '/torqa/?x=1', '/torqa/assets/i18n/en.json'],
  })
  await activeaza(sw)
  assert.deepEqual(navigate(sw), [])
  assert.ok(sw.jurnal.includes('unregister'), 'se dezinregistreaza oricum')
})

test('un cache care nu se sterge nu opreste dezinregistrarea si nici celelalte stergeri', async () => {
  const sw = incarca({ cacheuri: VECHI, ferestre: ['/'], refuza: ['pif-static-v9'] })
  await activeaza(sw)
  assert.deepEqual(sterse(sw), VECHI.filter((n) => n !== 'pif-static-v9').sort())
  assert.ok(sw.jurnal.includes('unregister'))
  assert.deepEqual(navigate(sw), ['/'])
})

test('o fereastra care refuza navigarea nu le opreste pe celelalte', async () => {
  const sw = incarca({ ferestre: ['/calc', '/', '/login'], refuza: ['/calc'] })
  await activeaza(sw)
  assert.deepEqual(navigate(sw), ['/', '/login'].sort())
})

test('daca dezinregistrarea pica, ferestrele se reincarca totusi si activate nu arunca', async () => {
  const sw = incarca({ cacheuri: VECHI, ferestre: ['/'], unregisterPica: true })
  await activeaza(sw)
  assert.deepEqual(sterse(sw), [...VECHI].sort())
  assert.deepEqual(navigate(sw), ['/'])
})

test('fara cache-uri si fara ferestre, activate doar se dezinregistreaza', async () => {
  const sw = incarca()
  await activeaza(sw)
  assert.deepEqual(sw.jurnal, ['unregister'])
})
