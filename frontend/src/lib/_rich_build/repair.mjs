// Repara backslash-urile lone (neescapate) din fisierele JSON, pastrand perechile \\ valide.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const outDir = path.join(here, 'out')
const files = process.argv.slice(2)
if (!files.length) { console.log('Usage: node repair.mjs <file.json> ...'); process.exit(1) }

const VALID = '"\\/bfnrtu' // caractere care urmeaza unui backslash valid in JSON
for (const name of files) {
  const p = path.join(outDir, name)
  let t = fs.readFileSync(p, 'utf8')
  // consuma backslash + char: daca e escape valid pastreaza, altfel dubleaza backslash-ul lone
  const fixed = t.replace(/\\([\s\S])/g, (m, c) => (VALID.includes(c) ? m : '\\\\' + c))
  try {
    const arr = JSON.parse(fixed)
    fs.writeFileSync(p, JSON.stringify(arr, null, 1))
    console.log(`OK ${name}: ${arr.length} elemente, parse valid dupa reparatie`)
  } catch (e) {
    console.log(`ESEC ${name}: inca invalid -> ${e.message}`)
  }
}
