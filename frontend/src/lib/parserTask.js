// CE SCRIE ION IN CAMPUL DE TITLU, CITIT CA DATE.
//
// „mâine revizie pompa Biochem" e o propozitie care contine deja tot ce cereau
// cele patru campuri ale formularului: ce, cand, unde. Parserul o desface, iar
// foaia arata ce a inteles sub forma de CHIPURI — deci nu ghiceste in tacere:
// vezi ce s-a extras si poti sa-l scoti.
//
// TREI REGULI CARE TIN PARSERUL ONEST
//
//  1. SE TAIE DOAR CE SE ARATA. Un cuvant plecat din titlu trebuie sa apara ca
//     chip; altfel informatia dispare din propoziţie fara sa se duca nicaieri.
//     De asta ORA NU SE TAIE (vezi mai jos).
//  2. SE POTRIVESTE PE CUVINTE INTREGI, cu granite Unicode scrise de mana.
//     `\b` din JavaScript e ASCII: `\bmarti\b` prinde, dar `\bmarți\b` NU se
//     comporta la fel in jurul lui „ț". Fara asta „joia" ar fi „joi" plus „a",
//     iar „azimut" ar fi „azi" plus „mut".
//  3. DIACRITICELE SUNT OPTIONALE LA INTRARE, NICIODATA LA IESIRE. Ion scrie de
//     pe telefon, deci „maine" si „mâine" trebuie sa fie acelasi lucru; dar ce
//     scrie interfata inapoi e mereu forma corecta.
//
// ORA SE TAIE DOAR ACOLO UNDE SE POATE SALVA (`cuOra`)
// Prima versiune a parserului RECUNOSTEA ora dar n-o scotea din titlu, fiindca
// nu exista coloana: un chip ar fi promis o valoare pe care salvarea o arunca.
// De la v41 exista `global_tasks.ora` — dar numai acolo. Taskurile de PROIECT
// (`tasks`) n-au coloana, iar Ion a cerut ora „pana cand doar pentru cele
// personale". Deci decizia nu e a parserului, e a apelantului: `cuOra: true`
// taie ora din titlu si o raporteaza ca valoare de salvat, `cuOra: false` (implicit)
// o raporteaza dar LASA textul intact — mai bine ora rămâne in titlu decat sa
// dispara la salvare.
// `ora` se raporteaza in ambele cazuri: cine intreaba poate vrea doar s-o arate.

import { localToday, addDays, parseISO, isoDate } from './planDates.js'

/** Litera, in sensul limbii — nu al lui ASCII. Folosita ca granita de cuvant. */
const L = 'a-zA-Z0-9ăâîșțĂÂÎȘȚşţŞŢ'

/** Fara diacritice si fara majuscule, DOAR pentru comparat. */
export function normalizeaza(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/[ăâ]/g, 'a')
    .replace(/[îi]/g, 'i')
    .replace(/[șş]/g, 's')
    .replace(/[țţ]/g, 't')
}

// Zilele saptamanii, in ordinea ISO (luni = 1). Formele scrise sunt cele pe care
// le tasteaza cineva grabit, inclusiv fara diacritice — normalizarea le aduce
// oricum la aceeasi forma, deci lista tine doar variantele de RADACINA.
const ZILE = [
  { zi: 1, forme: ['luni'] },
  { zi: 2, forme: ['marti'] },
  { zi: 3, forme: ['miercuri'] },
  { zi: 4, forme: ['joi'] },
  { zi: 5, forme: ['vineri'] },
  { zi: 6, forme: ['sambata'] },
  { zi: 7, forme: ['duminica'] },
]

// SFERA, SCRISA CU CUVINTE — la fel ca ziua (Ion, 2026-09-14: „scrii cu cuvinte").
// DOAR „personal": munca e sfera implicita a unui task nou, deci un cuvant pentru
// ea n-ar comuta nimic (Ion: „job trebuie sa fie implicita de fapt, deci nu are
// sens, cea personala trebuie"). Asa un singur camp poate trimite taskul si in
// personal, nu doar in munca.
// „munca"/„serviciu" n-ar fi oricum cuvinte-cheie bune: apar firesc in titluri de
// lucru („revizie la munca"). Cuvantul se TAIE din titlu, deci apare ca chip (regula #1).
const SFERE = [
  { forma: 'personal', sfera: 'personal', eticheta: 'Personal' },
]

/** Expresie care prinde `cuvant` doar intreg, cu granite care includ diacritice. */
function intreg(cuvant) {
  return new RegExp(`(^|[^${L}])(${cuvant})(?=[^${L}]|$)`, 'i')
}

/**
 * Urmatoarea apariție a unei zile ISO (1..7), pornind de MAINE.
 *
 * De ce nu de azi: „vineri", scris vineri, inseamna vinerea VIITOARE — daca ar
 * insemna azi, ai fi scris „azi". Regula asta e cea din toate aplicatiile de
 * to-do, si e singura care nu produce un task deja scadent in clipa creerii.
 */
function urmatoareaZi(ziISO, deLa = localToday()) {
  const d = parseISO(deLa)
  // `getDay()` da 0 pentru duminica; ISO vrea 7.
  const azi = d.getDay() === 0 ? 7 : d.getDay()
  let delta = ziISO - azi
  if (delta <= 0) delta += 7
  return isoDate(new Date(d.getFullYear(), d.getMonth(), d.getDate() + delta))
}

/** Ora, in formele pe care le scrie mana. DOUA treceri, fiecare cu grupul 2 =
 *  EXPRESIA INTREAGA de tăiat (inclusiv „la ", cand e scris) — asa tăierea nu
 *  trebuie sa ghiceasca unde incepe. Cu minute intai: „la 9:30" trebuie sa fie
 *  9:30, nu 9 urmat de „:30" rămas in titlu. */
const RE_ORA = (L) => [
  new RegExp(`(^|[^${L}])((?:la\\s+)?(\\d{1,2})[:.](\\d{2}))(?![\\d${L}])`, 'i'),
  new RegExp(`(^|[^${L}])(la\\s+(\\d{1,2}))(?![\\d${L}:.])`, 'i'),
]

/**
 * @param {string} text ce a scris Ion
 * @param {{ proiecte?: Array<{id: string, nume: string}>, cuOra?: boolean }} opt
 *        `cuOra` = ora se TAIE din titlu (apelantul o poate salva). Fara el, ora se
 *        raporteaza dar textul rămâne intreg — vezi antetul fisierului.
 * @returns {{
 *   titlu: string,          // textul curatat de ce a devenit chip
 *   zi: string|null,        // ISO, daca s-a recunoscut o zi
 *   etichetaZi: string|null,// cum se scrie ea pe chip („azi", „mâine", „vineri")
 *   proiect: object|null,   // proiectul potrivit, daca exista
 *   sfera: string|null,     // 'munca'|'personal', daca s-a scris „job"/„personal"
 *   etichetaSfera: string|null, // cum se scrie pe chip („Muncă"/„Personal")
 *   ora: string|null,       // RECUNOSCUTA, dar NU scoasa din titlu (vezi antetul)
 * }}
 */
export function parseTask(text, opt = {}) {
  const { proiecte = [], cuOra = false } = opt
  let rest = String(text || '')
  let zi = null
  let etichetaZi = null
  let proiect = null
  let sfera = null
  let etichetaSfera = null

  // --- ZIUA ---
  // Ordinea conteaza: „azi"/„mâine"/„poimâine" intai, fiindca sunt cele mai
  // frecvente si nu se pot confunda cu un nume de proiect.
  const relative = [
    { forma: 'azi', zile: 0, eticheta: 'azi' },
    { forma: 'maine', zile: 1, eticheta: 'mâine' },
    { forma: 'poimaine', zile: 2, eticheta: 'poimâine' },
  ]
  // „poimâine" ar fi prins de „mâine" ca subsir; granitele de cuvant o apara,
  // dar ordinea inversa (cel mai lung intai) o apara si daca granitele se
  // schimba vreodata.
  for (const r of [...relative].sort((a, b) => b.forma.length - a.forma.length)) {
    const re = intreg(r.forma)
    const m = normalizeaza(rest).match(re)
    if (!m) continue
    zi = addDays(localToday(), r.zile)
    etichetaZi = r.eticheta
    rest = taieLa(rest, m.index + m[1].length, r.forma.length)
    break
  }

  if (!zi) {
    for (const z of ZILE) {
      const re = intreg(z.forme[0])
      const m = normalizeaza(rest).match(re)
      if (!m) continue
      zi = urmatoareaZi(z.zi)
      // Pe chip se scrie cum e in dicționar, cu diacritice — nu cum a tastat.
      etichetaZi = ['', 'luni', 'marți', 'miercuri', 'joi', 'vineri', 'sâmbătă', 'duminică'][z.zi]
      rest = taieLa(rest, m.index + m[1].length, z.forme[0].length)
      break
    }
  }

  // --- PROIECTUL ---
  // Se caută numele proiectului ca subsir de cuvinte intregi. Cele mai LUNGI
  // intai: „Biochem Podari" trebuie sa bata „Biochem", altfel ar rămâne „Podari"
  // in titlu si chipul ar arata alt proiect decat scrie propoziţia.
  const candidati = [...proiecte]
    .filter(p => p && p.nume && String(p.nume).trim().length >= 3)
    .sort((a, b) => String(b.nume).length - String(a.nume).length)
  for (const p of candidati) {
    const nume = normalizeaza(p.nume).trim()
    // Numele pot conţine caractere cu inteles in regex („S.C. X & Y").
    const sigur = nume.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const m = normalizeaza(rest).match(intreg(sigur))
    if (!m) continue
    proiect = p
    rest = taieLa(rest, m.index + m[1].length, nume.length)
    break
  }

  // --- SFERA ---
  // Dupa proiect: un nume de proiect e mai specific decat un cuvant-cheie general,
  // deci daca s-ar suprapune vreodata (improbabil) proiectul are prioritate la taiere.
  for (const s of SFERE) {
    const m = normalizeaza(rest).match(intreg(s.forma))
    if (!m) continue
    sfera = s.sfera
    etichetaSfera = s.eticheta
    rest = taieLa(rest, m.index + m[1].length, s.forma.length)
    break
  }

  // --- ORA ---
  // Se VALIDEAZA inainte de a se tăia: „presiune 25:99 bar" se potriveste ca forma,
  // dar 25:99 nu e o ora — iar un titlu ciuntit ar fi mai rau decat o ora nerecunoscuta.
  let ora = null
  for (const re of RE_ORA(L)) {
    const m = normalizeaza(rest).match(re)
    if (!m) continue
    const h = parseInt(m[3], 10)
    const mi = m[4] === undefined ? 0 : parseInt(m[4], 10)
    if (h > 23 || mi > 59) continue
    ora = `${String(h).padStart(2, '0')}:${String(mi).padStart(2, '0')}`
    if (cuOra) rest = taieLa(rest, m.index + m[1].length, m[2].length)
    break
  }

  return { titlu: curata(rest), zi, etichetaZi, proiect, sfera, etichetaSfera, ora }
}

/** Scoate `lungime` caractere de la `start`, pe textul ORIGINAL (cu diacritice).
 *  Se lucreaza pe indici, nu pe `replace`: normalizarea pastreaza lungimea
 *  fiecarui caracter (unu-la-unu), deci indicii din forma normalizata sunt
 *  valizi si in cea scrisa — dar textul returnat trebuie sa ramana cel scris. */
function taieLa(text, start, lungime) {
  return text.slice(0, start) + text.slice(start + lungime)
}

/** Spatii duble si semne rămase atarnate dupa ce s-au scos bucati din mijloc. */
function curata(s) {
  return String(s || '')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([,;.])/g, '$1')
    .replace(/^[\s,;.-]+|[\s,;.-]+$/g, '')
    .trim()
}

// ===== SUGESTIILE DE PROIECT =====
//
// `parseTask` recunoaste un proiect doar dupa NUMELE INTREG, iar numele sunt lungi:
// 22 pe server la 2026-09-28, intre 20 si 53 de caractere, cu „—" si familia de
// drive la coada („PIF tablouri MCC Biochem Podari — G120"). Nu le scrie nimeni
// intr-un titlu. Ion, 2026-09-28: „trebuie toata denumirea proiectului, nu ai putea
// sa faci sa-mi apara sugestii din toate proiectele nu doar din cele active?"
//
// Deci un al doilea drum, care PROPUNE si nu ghiceste: un cuvant scris (de la 3
// litere) care e inceputul unui cuvant din numele, codul, clientul sau locatia unui
// proiect il aduce in lista foii. Se ALEGE cu o atingere — nimic nu se ataseaza
// singur. Din TOATE proiectele; la scor egal, cele deschise primele.
//
// UN CUVANT COMUN NU PROPUNE NIMIC. „Upgrade", „PIF", „Service", „G120",
// „Continental" stau in 5–12 proiecte fiecare — si in jumatate din titlurile de
// task, ca simple cuvinte. Un cuvant potrivit cu mai mult de `PRAG_CUVANT` proiecte
// nu deosebeste nimic, deci tace; „Biochem", „Oromax", „Duplex", „26_205" deosebesc
// unul-doua si vorbesc. Scorul: fiecare cuvant care vorbeste da `PRAG_CUVANT + 1 - n`
// fiecaruia dintre cele n proiecte pe care le atinge — deci la „Extruder TDE"
// iese primul proiectul care le are pe AMANDOUA.

export const PRAG_CUVANT = 3
const LITERE_MIN = 3
const SUGESTII_MAX = 3
const CAMPURI = ['nume', 'cod_proiect', 'client', 'locatie']

// `_` e litera aici: codurile de proiect („26_205") trebuie sa ramana un cuvant.
const RE_CUVANT = new RegExp(`[${L}_]+`, 'g')

/** Cuvintele unui text, normalizate, cu locul lor — valabil si pe textul ORIGINAL,
 *  fiindca normalizarea pastreaza lungimea (vezi `taieLa`). */
function cuvinte(text) {
  return [...normalizeaza(text).matchAll(RE_CUVANT)]
    .map(m => ({ w: m[0], start: m.index, end: m.index + m[0].length }))
}

/**
 * Proiectele propuse de text, cele mai sigure primele (cel mult `SUGESTII_MAX`).
 * @returns {Array<{ proiect: object, scor: number,
 *   cuvinte: Array<{w: string, start: number, end: number}>, campuri: Set<string> }>}
 *   `cuvinte` = ce anume din text l-a propus (pleaca din camp la alegere);
 *   `campuri` = unde s-a potrivit (randul arata locatia, daca de acolo vine).
 */
export function sugereazaProiecte(text, proiecte = []) {
  const scrise = cuvinte(text).filter(c => c.w.length >= LITERE_MIN)
  if (!scrise.length) return []
  const index = proiecte.filter(p => p && p.id).map(p => ({
    p,
    campuri: CAMPURI.map(camp => ({ camp, w: cuvinte(p[camp]).map(c => c.w) })),
  }))
  const gasite = new Map()
  for (const c of scrise) {
    const lovite = []
    for (const e of index) {
      const campuri = e.campuri.filter(k => k.w.some(w => w.startsWith(c.w))).map(k => k.camp)
      if (campuri.length) lovite.push({ e, campuri })
    }
    if (!lovite.length || lovite.length > PRAG_CUVANT) continue
    for (const { e, campuri } of lovite) {
      const s = gasite.get(e.p.id) || { proiect: e.p, scor: 0, cuvinte: [], campuri: new Set() }
      s.scor += PRAG_CUVANT + 1 - lovite.length
      s.cuvinte.push(c)
      for (const k of campuri) s.campuri.add(k)
      gasite.set(e.p.id, s)
    }
  }
  // La egalitate: deschise intai, apoi ordinea listei (API-ul le da pe cele noi primele).
  const loc = new Map(proiecte.map((p, i) => [p?.id, i]))
  const inchis = p => (p.status === 'finalizat' ? 1 : 0)
  return [...gasite.values()]
    .sort((a, b) => (b.scor - a.scor)
      || (inchis(a.proiect) - inchis(b.proiect))
      || (loc.get(a.proiect.id) - loc.get(b.proiect.id)))
    .slice(0, SUGESTII_MAX)
}

/** Textul fara cuvintele care au propus proiectul ales: au devenit chipul lui, deci
 *  nu se mai scriu o data in titlu (regula #1, vazuta din partea cealalta). Un
 *  spatiu ramane la coada, ca sa scrii mai departe fara sa-l pui tu. */
export function faraCuvinte(text, taiate = []) {
  let t = String(text || '')
  for (const c of [...taiate].sort((a, b) => b.start - a.start)) t = t.slice(0, c.start) + t.slice(c.end)
  t = t.replace(/\s{2,}/g, ' ').replace(/^[\s,;:.–—-]+|[\s,;:.–—-]+$/g, '')
  return t ? t + ' ' : ''
}

/** Textul in bucati, cu inceputurile de cuvant potrivite marcate (`m: true`) — ca
 *  randul unei sugestii sa arate DE CE a fost propus. `scrise` = cuvinte normalizate. */
export function marcheaza(text, scrise = []) {
  const t = String(text || '')
  const out = []
  let i = 0
  for (const c of cuvinte(t)) {
    const lung = Math.max(0, ...scrise.filter(w => c.w.startsWith(w)).map(w => w.length))
    if (!lung) continue
    if (c.start > i) out.push({ text: t.slice(i, c.start), m: false })
    out.push({ text: t.slice(c.start, c.start + lung), m: true })
    i = c.start + lung
  }
  if (i < t.length) out.push({ text: t.slice(i), m: false })
  return out
}
