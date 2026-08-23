// Motorul de lint pentru SPA. Nu se cheama cu mana — il cheama `scripts/lint.py`,
// care aduna si jumatatea de Python. Cu `--json` scoate date; fara, text.
//
// DE CE COMPILATORUL SVELTE, si nu ESLint. Proiectul n-are ESLint, iar cele trei
// clase de defect care au ajuns efectiv pe telefon nu sunt de stil, ci lucruri pe
// care doar compilatorul le stie:
//   1. `css_unused_selector` NU e un avertisment de curatenie — Svelte TAIE regula
//      din build. Aici s-a intamplat de doua ori: `.trow-wrap.deschis .gl-fata` si
//      `:global(.modal-body) > .td-jos`. Amandoua erau scrise, niciuna nu ajungea
//      in CSS-ul livrat, deci efectul lipsea de pe telefon fara niciun semn.
//      De-aia intra la ERORI, nu la avertismente.
//   2. `non_reactive_update` — in runes, un `let` simplu citit in markup nu
//      redeseneaza cand se schimba. Ecranul ramane pur si simplu pe valoarea veche.
//   3. importul care nu se rezolva — clasa de esec pentru care exista `smoke_ui`
//      ("pagina ramasa pe schelet"), dar aici se prinde in mai putin de o secunda.
//
// Plus doua verificari proprii, pe capcane gasite in acest repo:
//   - `svelte-ignore` cu coduri separate prin SPATIU tace doar PRIMUL cod
//     (verificat cu compilatorul). Separatorul corect e virgula. Un ignore scris
//     cu spatiu arata ca acopera doua avertismente si acopera unul.
//   - importuri neutilizate: iconitele si componentele nefolosite intra in bundle.
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

const AICI = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'))
const RADACINA = path.resolve(AICI, '..')
const FRONTEND = path.join(RADACINA, 'frontend')
const SRC = path.join(FRONTEND, 'src')
const STATIC = path.join(RADACINA, 'static')
const JSON_MOD = process.argv.includes('--json')

// Avertismentele compilatorului care sunt defecte, nu chestiuni de gust.
const GRAVE = new Set(['css_unused_selector', 'non_reactive_update'])

const rez = {
  scanate: { svelte: 0, js: 0 },
  erori: [],          // opresc build-ul sau au efect vizibil pe ecran
  avertismente: [],   // merita reparate, dar nu strica nimic acum
}

const err = (file, line, code, msg) => rez.erori.push({ file, line, code, msg })
const avert = (file, line, code, msg) => rez.avertismente.push({ file, line, code, msg })

function iesi(cod) {
  if (JSON_MOD) {
    process.stdout.write(JSON.stringify(rez))
  } else {
    const p = (t, l) => {
      if (!l.length) return
      console.log('\n== ' + t + ' (' + l.length + ') ==')
      for (const r of l) console.log('  ' + r.file + ':' + r.line + '  [' + r.code + '] ' + r.msg)
    }
    console.log('SPA: ' + rez.scanate.svelte + ' .svelte, ' + rez.scanate.js + ' .js')
    p('ERORI', rez.erori)
    p('AVERTISMENTE', rez.avertismente)
    if (!rez.erori.length && !rez.avertismente.length) console.log('curat')
  }
  process.exit(cod)
}

// Fara node_modules nu se poate compila nimic; a raporta "curat" ar fi o minciuna.
let compile
try {
  const req = createRequire(pathToFileURL(path.join(FRONTEND, 'package.json')).href)
  const m = await import(pathToFileURL(req.resolve('svelte/compiler')).href)
  compile = m.compile || (m.default && m.default.compile)
} catch (e) {
  err('frontend', 0, 'fara_svelte', 'nu gasesc svelte/compiler — ruleaza `npm ci` in frontend/')
  iesi(2)
}
if (typeof compile !== 'function') {
  err('frontend', 0, 'fara_svelte', 'svelte/compiler nu expune compile()')
  iesi(2)
}

const pkg = JSON.parse(fs.readFileSync(path.join(FRONTEND, 'package.json'), 'utf8'))
const declarate = new Set([
  ...Object.keys(pkg.dependencies || {}),
  ...Object.keys(pkg.devDependencies || {}),
])

function mergi(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) mergi(p, out)
    else if (/\.(svelte|js)$/.test(e.name)) out.push(p)
  }
  return out
}

const fisiere = mergi(SRC).sort()
const rel = (p) => path.relative(RADACINA, p).split(path.sep).join('/')
rez.scanate.svelte = fisiere.filter((f) => f.endsWith('.svelte')).length
rez.scanate.js = fisiere.length - rez.scanate.svelte

// ---------------------------------------------------------- 1. compilare
for (const f of fisiere.filter((f) => f.endsWith('.svelte'))) {
  const sursa = fs.readFileSync(f, 'utf8')
  try {
    const { warnings } = compile(sursa, { filename: rel(f), generate: 'client', dev: false })
    for (const w of warnings) {
      const linie = w.start?.line ?? 0
      const mesaj = String(w.message).split('\n')[0]
      if (GRAVE.has(w.code)) {
        err(rel(f), linie, w.code, w.code === 'css_unused_selector'
          ? mesaj + '  (Svelte TAIE regula din build — vezi antetul lint_svelte.mjs)'
          : mesaj)
      } else {
        avert(rel(f), linie, w.code, mesaj)
      }
    }
  } catch (e) {
    err(rel(f), e.start?.line ?? 0, e.code || 'compile_error', String(e.message).split('\n')[0])
  }
}

// -------------------------------------------- 2. svelte-ignore cu spatiu
// `<!-- svelte-ignore a b -->` tace doar `a`. Verificat compiland acelasi fisier
// cu spatiu si cu virgula: cu spatiu ramane al doilea avertisment.
const IGNORE_SPATIU = /svelte-ignore\s+([a-z0-9_]+(?:[ \t]+[a-z0-9_]+)+)\s*(?:-->|\n|$)/g
for (const f of fisiere) {
  const sursa = fs.readFileSync(f, 'utf8')
  for (const m of sursa.matchAll(IGNORE_SPATIU)) {
    const linie = sursa.slice(0, m.index).split('\n').length
    err(rel(f), linie, 'ignore_separat_prin_spatiu',
      'svelte-ignore cu mai multe coduri separate prin spatiu: tace DOAR primul. Separa prin virgula.')
  }
}

// ------------------------------------------------ 3. + 4. importuri SPA
const IMPORT = /^[ \t]*import\s+(?:([\w$]+)\s*,\s*)?(?:\{([^}]*)\}|\*\s+as\s+([\w$]+)|([\w$]+))?\s*(?:from\s*)?['"]([^'"]+)['"]/gm
const EXT = ['', '.js', '.svelte', '/index.js', '.json', '.css']

for (const f of fisiere) {
  const sursa = fs.readFileSync(f, 'utf8')
  // in .svelte doar blocurile <script> declara importuri; folosirea se cauta insa
  // in TOT fisierul, fiindca `<Card />` din markup e o folosire.
  const blocuri = f.endsWith('.svelte')
    ? [...sursa.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1])
    : [sursa]
  const faraImporturi = sursa.replace(IMPORT, '')
  for (const bloc of blocuri) {
    for (const m of bloc.matchAll(IMPORT)) {
      const [linieTxt, def1, numite, stea, def2, spec] = m
      const linie = sursa.indexOf(linieTxt) >= 0
        ? sursa.slice(0, sursa.indexOf(linieTxt)).split('\n').length : 0
      const nume = [def1, stea, def2].filter(Boolean)
      if (numite) {
        for (const parte of numite.split(',')) {
          const t = parte.trim()
          if (!t) continue
          const as = t.split(/\s+as\s+/)
          nume.push((as[1] || as[0]).trim())
        }
      }
      // se rezolva?
      if (spec.startsWith('.')) {
        const baza = path.resolve(path.dirname(f), spec)
        if (!EXT.some((e) => fs.existsSync(baza + e))) {
          err(rel(f), linie, 'import_nerezolvat', "'" + spec + "' nu exista pe disc")
        }
      } else if (!spec.startsWith('$') && !spec.startsWith('/') && !spec.startsWith('node:')) {
        const r = spec.startsWith('@') ? spec.split('/').slice(0, 2).join('/') : spec.split('/')[0]
        if (!declarate.has(r) && !fs.existsSync(path.join(FRONTEND, 'node_modules', r))) {
          err(rel(f), linie, 'import_nedeclarat', "'" + spec + "' nu e in package.json")
        }
      }
      // se foloseste?
      for (const n of nume) {
        if (!n) continue
        const esc = n.replace(/[$]/g, '\\$&')
        if (!new RegExp('\\b' + esc + '\\b').test(faraImporturi)) {
          avert(rel(f), linie, 'import_neutilizat', "'" + n + "' din '" + spec + "' nu e folosit")
        }
      }
    }
  }
}

// ------------------------------------- 5. JS de sine statator din static/
// `service-worker.js` nu trece prin niciun build, deci o greseala de sintaxa in el
// nu e prinsa de nimeni pana cand nu se inregistreaza pe telefon.
if (fs.existsSync(STATIC)) {
  for (const e of fs.readdirSync(STATIC, { withFileTypes: true })) {
    if (!e.isFile() || !e.name.endsWith('.js')) continue
    const p = path.join(STATIC, e.name)
    const sursa = fs.readFileSync(p, 'utf8')
    if (/^[ \t]*(?:import|export)\s/m.test(sursa)) continue // modul, nu script clasic
    try {
      new vm.Script(sursa, { filename: p })
    } catch (ex) {
      err(rel(p), 0, 'sintaxa', String(ex.message).split('\n')[0])
    }
  }
}

iesi(rez.erori.length ? 1 : 0)
