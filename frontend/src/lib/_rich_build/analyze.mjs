// Analiza scopului pentru imbogatirea glosarului.
// Pentru fiecare marime DISTINCTA afisata in calculator (camp + rezultat din module),
// rezolva intrarea de baza (GLOSSARY/EXTRA) si cheia sub care e gasita (matchedKey),
// aduna toate contextele (etichete, unitati, module, categorii) si scrie fisiere
// de intrare per-categorie in _rich_build/in/<cat>.json pentru agentii de imbogatire.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { MODULES, catOf } from '../driveCalc.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const libDir = path.join(here, '..')
const outDir = path.join(here, 'in')
fs.mkdirSync(outDir, { recursive: true })

// GLOSSARY e obiect JS in driveGlossary.js (nu JSON) -> il extragem din text
const gsrc = fs.readFileSync(path.join(libDir, 'driveGlossary.js'), 'utf8')
const gStart = gsrc.indexOf('export const GLOSSARY =')
const gEnd = gsrc.indexOf('\n// Glosar extins')
const objText = gsrc.slice(gsrc.indexOf('{', gStart), gEnd).replace(/\}\s*$/, '}')
// eslint-disable-next-line no-eval
const GLOSSARY = eval('(' + objText.replace(/}\s*$/, '}') + ')')
const EXTRA = JSON.parse(fs.readFileSync(path.join(libDir, 'glossaryExtra.json'), 'utf8'))
const TEORIE = JSON.parse(fs.readFileSync(path.join(libDir, 'glossaryTeorie.json'), 'utf8'))

function resolve(key, family) {
  const cands = [`${family}:${key}`, key]
  for (const c of cands) if (GLOSSARY[c]) return { mk: c, base: GLOSSARY[c], src: 'G' }
  for (const c of cands) if (EXTRA[c]) return { mk: c, base: EXTRA[c], src: 'E' }
  return null
}
function teorieOf(key, family, base) {
  if (base && base.teorie && String(base.teorie).trim()) return base.teorie
  return TEORIE[`${family}:${key}`] || TEORIE[key] || ''
}

const byMk = new Map()
const missing = []
for (const m of MODULES) {
  const cat = catOf(m)
  const fam = m.family
  for (const it of [...(m.fields || []), ...(m.results || [])]) {
    if (!it.key) continue
    const r = resolve(it.key, fam)
    if (!r) { missing.push(`${m.id}:${it.key}`); continue }
    if (!byMk.has(r.mk)) {
      byMk.set(r.mk, {
        mk: r.mk, key: it.key, family: fam,
        labels: new Set(), units: new Set(), cats: new Set(), modules: new Set(),
        def: r.base.def || '', ia: r.base.ia || '', practic: r.base.practic || '',
        teorie: teorieOf(it.key, fam, r.base),
      })
    }
    const e = byMk.get(r.mk)
    if (it.label) e.labels.add(it.label)
    if (it.unit) e.units.add(it.unit)
    e.cats.add(cat)
    e.modules.add(`${m.title}${m.subtitle ? ' / ' + m.subtitle : ''}`)
  }
}

const groups = {}
for (const e of byMk.values()) {
  const rec = {
    mk: e.mk, key: e.key, family: e.family,
    labels: [...e.labels], units: [...e.units], modules: [...e.modules].slice(0, 6),
    def: e.def, ia: e.ia, practic: e.practic, teorie: e.teorie,
  }
  const cat = [...e.cats][0] || 'altele'
  ;(groups[cat] = groups[cat] || []).push(rec)
}

let total = 0
const summary = {}
for (const [cat, arr] of Object.entries(groups)) {
  arr.sort((a, b) => a.mk.localeCompare(b.mk))
  fs.writeFileSync(path.join(outDir, `${cat}.json`), JSON.stringify(arr, null, 1))
  summary[cat] = arr.length
  total += arr.length
}
console.log('TOTAL marimi distincte:', total)
console.log('Pe categorii:', JSON.stringify(summary))
console.log('Lipsa din glosar:', missing.length, missing.slice(0, 20).join(', '))
