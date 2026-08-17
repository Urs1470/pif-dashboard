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
// DE CE ORA E RECUNOSCUTA DAR NU EXTRASA
// Handoff-ul cere si ora („la 9", „9:00") ca chip. Nici `global_tasks` nici
// `tasks` nu au coloana de ora — `data_scadenta` e o DATA, iar toata aplicatia o
// citeste asa (`.slice(0, 10)`, comparatii pe zi). Un chip de ora ar promite o
// valoare pe care salvarea o arunca; ora scoasa din titlu s-ar pierde de tot.
// Deci: `ora` se RAPORTEAZA (ca sa se poata decide mai tarziu, cu o coloana
// adevarata), dar nu se scoate din titlu si nu devine chip. Ce vede Ion in titlu
// e ce se salveaza.

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

/**
 * @param {string} text ce a scris Ion
 * @param {{ proiecte?: Array<{id: string, nume: string}> }} opt
 * @returns {{
 *   titlu: string,          // textul curatat de ce a devenit chip
 *   zi: string|null,        // ISO, daca s-a recunoscut o zi
 *   etichetaZi: string|null,// cum se scrie ea pe chip („azi", „mâine", „vineri")
 *   proiect: object|null,   // proiectul potrivit, daca exista
 *   ora: string|null,       // RECUNOSCUTA, dar NU scoasa din titlu (vezi antetul)
 * }}
 */
export function parseTask(text, opt = {}) {
  const { proiecte = [] } = opt
  let rest = String(text || '')
  let zi = null
  let etichetaZi = null
  let proiect = null

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

  // --- ORA --- (recunoscuta, netaiata: vezi antetul fisierului)
  let ora = null
  const mOra = String(rest).match(/(^|[^0-9])(?:la\s+)?([01]?\d|2[0-3])[:.]([0-5]\d)(?=[^0-9]|$)/)
  if (mOra) ora = `${String(mOra[2]).padStart(2, '0')}:${mOra[3]}`
  else {
    const mLa = normalizeaza(rest).match(new RegExp(`(^|[^${L}])la\\s+([01]?\\d|2[0-3])(?=[^0-9]|$)`))
    if (mLa) ora = `${String(mLa[2]).padStart(2, '0')}:00`
  }

  return { titlu: curata(rest), zi, etichetaZi, proiect, ora }
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
