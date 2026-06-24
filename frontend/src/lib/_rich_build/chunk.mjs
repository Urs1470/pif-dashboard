// Imparte fisierele per-categorie din in/ in loturi de <= SIZE marimi: in/b_<cat>_<n>.json
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const inDir = path.join(here, 'in')
const outDir = path.join(here, 'out')
fs.mkdirSync(outDir, { recursive: true })
const SIZE = 30

const cats = fs.readdirSync(inDir).filter(f => f.endsWith('.json') && !f.startsWith('b_'))
const batches = []
for (const f of cats) {
  const cat = f.replace('.json', '')
  const arr = JSON.parse(fs.readFileSync(path.join(inDir, f), 'utf8'))
  for (let i = 0, n = 1; i < arr.length; i += SIZE, n++) {
    const name = `b_${cat}_${n}.json`
    fs.writeFileSync(path.join(inDir, name), JSON.stringify(arr.slice(i, i + SIZE), null, 1))
    batches.push({ name, cat, count: Math.min(SIZE, arr.length - i) })
  }
}
fs.writeFileSync(path.join(here, 'batches.json'), JSON.stringify(batches, null, 1))
console.log('Loturi:', batches.length, '| total:', batches.reduce((s, b) => s + b.count, 0))
console.log(batches.map(b => `${b.name}(${b.count})`).join(' '))
