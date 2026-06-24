// Combina out/b_*.json -> glossaryRich.json, cu validare.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const inDir = path.join(here, 'in')
const outDir = path.join(here, 'out')
const target = path.join(here, '..', 'glossaryRich.json')

const batchFiles = fs.readdirSync(inDir).filter(f => /^b_.*\.json$/.test(f))
const expected = new Set()
for (const f of batchFiles) {
  for (const e of JSON.parse(fs.readFileSync(path.join(inDir, f), 'utf8'))) expected.add(e.mk)
}

const RICH = {}
const problems = []
let parsedBatches = 0
for (const f of batchFiles) {
  const p = path.join(outDir, f)
  if (!fs.existsSync(p)) { problems.push(`LIPSA fisier iesire: ${f}`); continue }
  let arr
  try { arr = JSON.parse(fs.readFileSync(p, 'utf8')) } catch (e) { problems.push(`JSON invalid in ${f}: ${e.message}`); continue }
  parsedBatches++
  for (const e of arr) {
    if (!e || !e.mk) { problems.push(`${f}: element fara mk`); continue }
    const def = String(e.def || '').trim()
    const teo = String(e.teorie || '').trim()
    if (!def) problems.push(`${f}/${e.mk}: def gol`)
    if (!teo) problems.push(`${f}/${e.mk}: teorie goala`)
    // $ echilibrat
    if (((def + ' ' + teo).match(/\$/g) || []).length % 2 !== 0) problems.push(`${f}/${e.mk}: $ neimperecheat`)
    // diacritice
    if (/[ăâîşţșțĂÂÎŞŢȘȚ]/.test(def + teo)) problems.push(`${f}/${e.mk}: are diacritice`)
    RICH[e.mk] = { def, teorie: teo }
  }
}

// acoperire
const got = new Set(Object.keys(RICH))
const missing = [...expected].filter(k => !got.has(k))
const extra = [...got].filter(k => !expected.has(k))

console.log('Loturi parsate:', parsedBatches, '/', batchFiles.length)
console.log('Marimi imbogatite:', got.size, '/ asteptate', expected.size)
console.log('Lipsa (neimbogatite):', missing.length, missing.slice(0, 40).join(', '))
console.log('In plus (mk necunoscut):', extra.length, extra.slice(0, 20).join(', '))
console.log('Probleme:', problems.length)
problems.slice(0, 60).forEach(p => console.log('  -', p))

if (process.argv.includes('--write')) {
  // sortat alfabetic pentru diff curat
  const sorted = {}
  for (const k of Object.keys(RICH).sort()) sorted[k] = RICH[k]
  fs.writeFileSync(target, JSON.stringify(sorted, null, 1))
  console.log('SCRIS:', target, '(', Object.keys(sorted).length, 'intrari )')
} else {
  console.log('(dry-run; adauga --write pentru a scrie glossaryRich.json)')
}
