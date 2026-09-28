// Parserul din foaia de adaugare: ce se taie din titlu si ce nu.
//
// De ce are test si nu doar o proba pe ecran: parserul TAIE text din ce a scris
// Ion. O granita de cuvant greșită nu crapa si nu se vede la o proba grabita —
// produce un titlu ciuntit („azimut" -> „mut") pe care il descoperi peste o
// saptamana, in lista. Cazurile de mai jos sunt exact capcanele din antetul
// fisierului, plus cele pe care le-am gresit scriindu-l.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseTask, normalizeaza, sugereazaProiecte, faraCuvinte, marcheaza } from './parserTask.js'
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
  assert.equal(r.sfera, null)
  assert.equal(r.titlu, 'schimbat filtrul de ulei')
})

test('sfera scrisa: „personal" comuta si se taie din titlu', () => {
  const r = parseTask('personal sună la dentist')
  assert.equal(r.sfera, 'personal')
  assert.equal(r.etichetaSfera, 'Personal')
  assert.equal(r.titlu, 'sună la dentist')
})

test('„personal" pe cuvant intreg: „personalul" NU e sfera', () => {
  // Aceeasi capcana ca „azimut” -> „azi mut”: granita de dupa trebuie sa cada.
  const r = parseTask('verificat personalul de tura')
  assert.equal(r.sfera, null, 'personalul nu e personal')
  assert.equal(r.titlu, 'verificat personalul de tura')
})

test('munca n-are cuvant-cheie (e implicita): „job" ramane in titlu', () => {
  const r = parseTask('job nou de organizat')
  assert.equal(r.sfera, null)
  assert.equal(r.titlu, 'job nou de organizat')
})

test('sfera + zi deodata, titlul ramane curat', () => {
  const r = parseTask('mâine personal sună dentist')
  assert.equal(r.etichetaZi, 'mâine')
  assert.equal(r.sfera, 'personal')
  assert.equal(r.titlu, 'sună dentist')
})

test('normalizeaza pastreaza lungimea (indicii de taiere depind de asta)', () => {
  for (const s of ['mâine', 'sâmbătă', 'șțĂÂÎ', 'Biochem Podari']) {
    assert.equal(normalizeaza(s).length, s.length, s)
  }
})

// ===== SUGESTIILE DE PROIECT =====
// Lista REALA de pe server, 2026-09-28 (22 de proiecte, 4 deschise), in ordinea
// API-ului (cele noi primele). Conteaza sa fie cea reala: pragul pentru „cuvant
// comun" se sprijina pe cum se repeta cuvintele in numele lui Ion — „Upgrade" x7,
// „G120" x7, „Continental" x12 — iar o lista inventata ar trece testele cu orice prag.
const REALE = [
  { id: 'p01', nume: 'Service FC302 132 kW — degajare de fum, vulcanizare', cod_proiect: 'TBD', client: 'Continental Automotive Products SRL', locatie: 'Timișoara — Vulcanizare', status: 'pregatire' },
  { id: 'p02', nume: 'Upgrade motoare Extruder TSRD — S120', cod_proiect: '26_208', client: 'Continental Automotive Products SRL', locatie: 'Timișoara — Extruder TSRD-MBL', status: 'finalizat' },
  { id: 'p03', nume: 'Service suflantă biogaz — G120', cod_proiect: '', client: 'MASPEX ROMANIA SRL', locatie: 'Vălenii de Munte, jud. Prahova', status: 'finalizat' },
  { id: 'p04', nume: 'Service modul AI stație epurare — S7-1200', cod_proiect: '26_241', client: 'Comuna Zau de Câmpie', locatie: 'Zau de Câmpie, jud. Mureș — stația de epurare', status: 'finalizat' },
  { id: 'p05', nume: 'Upgrade motoare Extruder TDE FML — S120', cod_proiect: '250326E_C1', client: 'Continental Automotive Products SRL', locatie: 'Timișoara — Extruder TDE FML', status: 'finalizat' },
  { id: 'p06', nume: 'Upgrade CU240S PN Carbon Black — G120', cod_proiect: '26_207', client: 'Continental Automotive Products SRL', locatie: 'Timișoara — Carbon Black (Mixing)', status: 'finalizat' },
  { id: 'p07', nume: 'Parametrizare Oromax Triplex 2 — 3WA', cod_proiect: '26_205', client: 'Continental Automotive Products SRL', locatie: 'Timișoara — Oromax Triplex 2', status: 'pregatire' },
  { id: 'p08', nume: 'Înlocuire fibră optică — S150', cod_proiect: '26_162', client: 'Continental Automotive Products SRL', locatie: 'Timișoara', status: 'finalizat' },
  { id: 'p09', nume: 'Upgrade motoare Calandru TSRD — S120', cod_proiect: '26_105', client: 'Continental Automotive Products SRL', locatie: 'Timișoara — Calandru TSRD-MBL', status: 'finalizat' },
  { id: 'p10', nume: 'Service remote ventilator MOT308 — ACS880', cod_proiect: '', client: 'AGFD TANDAREI SRL', locatie: 'Aleea Teilor nr. 2, 925200 Țăndărei, jud. Ialomița', status: 'finalizat' },
  { id: 'p11', nume: 'Migrare CU240S DP → CU240E-2 DP — G120', cod_proiect: '26_175', client: 'Continental Automotive Products SRL', locatie: 'Timișoara — linia Polymer', status: 'finalizat' },
  { id: 'p12', nume: 'Upgrade motor Calandru TDE FML — S120', cod_proiect: '26_083', client: 'Continental Automotive Products SRL', locatie: 'Timișoara — Calandru TDE FML (POMINI)', status: 'finalizat' },
  { id: 'p13', nume: 'PIF tablouri MCC Biochem Podari — G120', cod_proiect: '26_123', client: 'IMSAT SA', locatie: 'Podari, jud. Dolj', status: 'finalizat' },
  { id: 'p14', nume: 'Service pompă noroi B — ACS880', cod_proiect: '', client: 'ICPE ACTEL S.A.', locatie: 'zona Ploiești, jud. Prahova', status: 'finalizat' },
  { id: 'p15', nume: 'Upgrade drive-uri linie Duplex — S120', cod_proiect: '26_147', client: 'Continental Automotive Products SRL', locatie: 'Timișoara — CAP, Linia Duplex', status: 'pregatire' },
  { id: 'p16', nume: 'PIF pompă condensat Oil Field — ACS880', cod_proiect: '26_088', client: 'Spoting SA', locatie: 'Tank Farm 8-13/8-14, Rafinăria Petrobrazi', status: 'pregatire' },
  { id: 'p17', nume: 'PIF linie granulare — ACS880', cod_proiect: '25_020', client: 'AN FEED SRL', locatie: 'Platforma Ungheni nr. 1, Ungheni, jud. Mureș', status: 'finalizat' },
  { id: 'p18', nume: 'Upgrade PILZ și MM440 APEX — G120', cod_proiect: '26_154', client: 'Continental Automotive Products SRL', locatie: 'Timișoara', status: 'finalizat' },
  { id: 'p19', nume: 'Retrofit FML3 — G120', cod_proiect: '260001E_C1', client: 'Continental Automotive Products SRL', locatie: 'Timișoara', status: 'finalizat' },
  { id: 'p20', nume: 'PIF ventilatoare vulcanizare — FC302', cod_proiect: '25_041', client: 'Continental Automotive Products SRL', locatie: 'Timișoara — H1, H4', status: 'finalizat' },
  { id: 'p21', nume: 'Lucrări electrice și automatizări Biomasa Deva — G120', cod_proiect: '250656E', client: 'Carmeuse SRL', locatie: 'Deva', status: 'finalizat' },
  { id: 'p22', nume: 'PIF multidrive Holcim Aleșd — ACS880', cod_proiect: '250826E_C1', client: 'IMSAT SNEF SA', locatie: 'Aleșd, jud. Bihor', status: 'finalizat' },
]
const ids = (text) => sugereazaProiecte(text, REALE).map(s => s.proiect.id)

test('sugestie dintr-o bucata de nume: „raport Oro" propune Oromax', () => {
  assert.deepEqual(ids('raport Oro'), ['p07'])
})

test('si proiectele INCHISE se propun (Ion: „din toate proiectele")', () => {
  assert.deepEqual(ids('trimite PV Biochem'), ['p13'])
  assert.equal(REALE.find(p => p.id === 'p13').status, 'finalizat')
})

test('cuvintele comune tac: Upgrade x7, G120 x7, PIF x5, Continental x12', () => {
  for (const text of ['upgrade firmware G120', 'PIF', 'Service', 'Continental', 'Timișoara']) {
    assert.deepEqual(ids(text), [], text)
  }
  // Pragul e de FRECVENTA, nu de inteles: „motor" e un cuvant de rand, dar sta intr-un
  // singur nume („motoare" nu incepe cu „motor"), deci propune. E doar o propunere —
  // o ignori si apesi Enter; mai scump ar fi fost un proiect care nu apare deloc.
  assert.deepEqual(ids('verificare motor'), ['p12'])
})

test('un cuvant comun langa unul care deosebeste: vorbeste doar al doilea', () => {
  const [s] = sugereazaProiecte('upgrade firmware Duplex', REALE)
  assert.equal(s.proiect.id, 'p15')
  assert.deepEqual(s.cuvinte.map(c => c.w), ['duplex'], '„upgrade" nu e dintre cuvintele care l-au propus')
})

test('proiectul care le are pe AMANDOUA iese primul („Extruder TDE")', () => {
  assert.deepEqual(ids('Extruder TDE'), ['p05', 'p02', 'p12'])
})

test('client, locatie si cod propun si ele — si se stie de unde', () => {
  const [pb] = sugereazaProiecte('Petrobrazi', REALE)
  assert.equal(pb.proiect.id, 'p16')
  assert.ok(pb.campuri.has('locatie') && !pb.campuri.has('nume'))
  const [mx] = sugereazaProiecte('maspex', REALE)
  assert.equal(mx.proiect.id, 'p03')
  assert.ok(mx.campuri.has('client'))
  assert.deepEqual(ids('26_205'), ['p07'], 'codul ramane un cuvant, cu tot cu `_`')
})

test('la scor egal, cele deschise primele', () => {
  // „26_20" atinge 26_208, 26_207, 26_205 — toate cu acelasi scor; doar 26_205 e deschis.
  assert.equal(ids('26_20')[0], 'p07')
})

test('diacriticele sunt optionale: „suflanta", „alesd"', () => {
  assert.deepEqual(ids('suflanta'), ['p03'])
  assert.deepEqual(ids('alesd'), ['p22'])
})

test('cel mult trei sugestii, iar sub 3 litere nimic', () => {
  assert.equal(ids('Bio').length, 3, 'biogaz, Biochem, Biomasa')
  assert.deepEqual(ids('PV la 9'), [])
})

test('alegerea taie din camp cuvintele care au propus proiectul, nu pe celelalte', () => {
  const text = 'upgrade firmware Duplex'
  const [s] = sugereazaProiecte(text, REALE)
  assert.equal(faraCuvinte(text, s.cuvinte), 'upgrade firmware ')

  const t2 = 'trimite PV Biochem Podari'
  const [s2] = sugereazaProiecte(t2, REALE)
  assert.equal(faraCuvinte(t2, s2.cuvinte), 'trimite PV ')

  // Proiectul scris primul, apoi ce ai de facut: nu ramane semn atarnat in fata.
  const t3 = 'Oromax: raport final'
  const [s3] = sugereazaProiecte(t3, REALE)
  assert.equal(faraCuvinte(t3, s3.cuvinte), 'raport final ')

  // Doar bucata de proiect scrisa: campul ramane gol, gata pentru titlu.
  const [s4] = sugereazaProiecte('Oro', REALE)
  assert.equal(faraCuvinte('Oro', s4.cuvinte), '')
})

test('marcheaza ingroasa inceputul cuvantului potrivit, pastrand diacriticele', () => {
  assert.deepEqual(marcheaza('Service pompă noroi B', ['pomp']), [
    { text: 'Service ', m: false },
    { text: 'pomp', m: true },
    { text: 'ă noroi B', m: false },
  ])
  assert.deepEqual(marcheaza('Biochem', []), [{ text: 'Biochem', m: false }])
})
