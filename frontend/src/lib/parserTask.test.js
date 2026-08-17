// Parserul din foaia de adaugare: ce se taie din titlu si ce nu.
//
// De ce are test si nu doar o proba pe ecran: parserul TAIE text din ce a scris
// Ion. O granita de cuvant greșită nu crapa si nu se vede la o proba grabita —
// produce un titlu ciuntit („azimut" -> „mut") pe care il descoperi peste o
// saptamana, in lista. Cazurile de mai jos sunt exact capcanele din antetul
// fisierului, plus cele pe care le-am gresit scriindu-l.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseTask, normalizeaza } from './parserTask.js'
import { localToday, addDays } from './planDates.js'

const PROIECTE = [
  { id: 'p1', nume: 'Biochem Podari' },
  { id: 'p2', nume: 'Biochem' },
  { id: 'p3', nume: 'IMSAT' },
]

test('zi relativa: azi / mâine / poimâine, cu si fara diacritice', () => {
  for (const [text, zile, eticheta] of [
    ['azi revizie pompa', 0, 'azi'],
    ['mâine revizie pompa', 1, 'mâine'],
    ['maine revizie pompa', 1, 'mâine'],
    ['poimaine revizie pompa', 2, 'poimâine'],
  ]) {
    const r = parseTask(text)
    assert.equal(r.zi, addDays(localToday(), zile), text)
    assert.equal(r.etichetaZi, eticheta, text)
    assert.equal(r.titlu, 'revizie pompa', text)
  }
})

test('„poimâine" nu se citeste ca „mâine"', () => {
  const r = parseTask('poimaine X')
  assert.equal(r.etichetaZi, 'poimâine')
  assert.equal(r.titlu, 'X')
})

test('cuvinte intregi: „azimut" si „joia" nu sunt zile', () => {
  const a = parseTask('reglaj azimut antena')
  assert.equal(a.zi, null)
  assert.equal(a.titlu, 'reglaj azimut antena')

  // „joia" contine „joi" dar nu e ziua — granita de dupa trebuie sa cada.
  const j = parseTask('program joia verde')
  assert.equal(j.zi, null, 'joia nu e joi')
  assert.equal(j.titlu, 'program joia verde')
})

test('zi din saptamana: mereu in VIITOR, niciodata azi', () => {
  const r = parseTask('vineri predare documentatie')
  assert.notEqual(r.zi, null)
  assert.ok(r.zi > localToday(), 'ziua aleasa trebuie sa fie dupa azi')
  assert.equal(r.titlu, 'predare documentatie')
})

test('numele lung al proiectului bate pe cel scurt', () => {
  const r = parseTask('revizie pompa Biochem Podari', { proiecte: PROIECTE })
  assert.equal(r.proiect?.id, 'p1')
  assert.equal(r.titlu, 'revizie pompa', 'nu trebuie sa rămână „Podari" in titlu')
})

test('zi + proiect deodata, titlul rămâne curat', () => {
  const r = parseTask('mâine parametrizare IMSAT', { proiecte: PROIECTE })
  assert.equal(r.etichetaZi, 'mâine')
  assert.equal(r.proiect?.id, 'p3')
  assert.equal(r.titlu, 'parametrizare')
})

test('titlul pastreaza diacriticele scrise, desi potrivirea le ignora', () => {
  const r = parseTask('maine verificare tensiune și curent')
  assert.equal(r.titlu, 'verificare tensiune și curent')
})

test('fara `cuOra`, ora se raporteaza dar NU se taie din titlu', () => {
  // Cazul taskurilor care n-au unde s-o salveze (proiect, sfera munca): mai bine
  // ora rămâne in titlu decat sa dispara la salvare.
  for (const [text, ora] of [
    ['revizie la 9', '09:00'],
    ['revizie 14:30', '14:30'],
    ['revizie la 14:05', '14:05'],
  ]) {
    const r = parseTask(text)
    assert.equal(r.ora, ora, text)
    assert.equal(r.titlu, text, 'titlul rămâne intact — ora nu se pierde')
  }
})

test('cu `cuOra`, ora pleaca din titlu (are coloana: global_tasks.ora, v41)', () => {
  for (const [text, ora, titlu] of [
    ['revizie la 9', '09:00', 'revizie'],
    ['revizie 14:30', '14:30', 'revizie'],
    ['la 7.15 cafea', '07:15', 'cafea'],
    ['mâine la 9 revizie pompa', '09:00', 'revizie pompa'],
  ]) {
    const r = parseTask(text, { cuOra: true })
    assert.equal(r.ora, ora, text)
    assert.equal(r.titlu, titlu, text)
  }
})

test('„la 9:30" e 9:30, nu 9 cu „:30" rămas in titlu', () => {
  const r = parseTask('sedinta la 9:30', { cuOra: true })
  assert.equal(r.ora, '09:30')
  assert.equal(r.titlu, 'sedinta')
})

test('ora invalida nu se inventeaza SI nu ciunteste titlul', () => {
  for (const text of ['presiune 25:99 bar', 'cablu 3x25', 'tensiune 24:70 V']) {
    const r = parseTask(text, { cuOra: true })
    assert.equal(r.ora, null, text)
    assert.equal(r.titlu, text, 'titlul rămâne intreg cand ora nu e ora')
  }
})

test('„la" dintr-un cuvant nu e ora („sala 9")', () => {
  const r = parseTask('verificat sala 9', { cuOra: true })
  assert.equal(r.ora, null)
  assert.equal(r.titlu, 'verificat sala 9')
})

test('zi + ora + proiect deodata', () => {
  const r = parseTask('mâine la 8:30 parametrizare IMSAT', { proiecte: PROIECTE, cuOra: true })
  assert.equal(r.etichetaZi, 'mâine')
  assert.equal(r.ora, '08:30')
  assert.equal(r.proiect?.id, 'p3')
  assert.equal(r.titlu, 'parametrizare')
})

test('text fara nimic de extras trece neatins', () => {
  const r = parseTask('schimbat filtrul de ulei', { proiecte: PROIECTE })
  assert.equal(r.zi, null)
  assert.equal(r.proiect, null)
  assert.equal(r.titlu, 'schimbat filtrul de ulei')
})

test('normalizeaza pastreaza lungimea (indicii de taiere depind de asta)', () => {
  for (const s of ['mâine', 'sâmbătă', 'șțĂÂÎ', 'Biochem Podari']) {
    assert.equal(normalizeaza(s).length, s.length, s)
  }
})
