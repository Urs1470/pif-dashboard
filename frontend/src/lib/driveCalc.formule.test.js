// Teste numerice pe formulele calculatorului.
//
// Rulare: `npm test` (runner-ul built-in `node --test`, zero dependinte noi).
//
// REGULA acestui fisier: valoarea asteptata se scrie din FIZICA sau din sursa
// citata pe card, NU se copiaza din ce intoarce codul azi. Un test care copiaza
// rezultatul curent inghetat nu prinde niciodata o formula gresita — o
// consfinteste. Unde valoarea depinde de o conventie a codului (constanta
// rotunjita 9550, 1.35·U pentru puntea in 6 pulsuri, pragul de 3% la sectiunea
// minima), conventia e scrisa in comentariu ca sa se vada ce anume e blocat.
//
// Acoperire: primul lot de module (asincron, pompe, VFD, instalatie, termic).
// Restul intra pe masura ce le folosim — vezi driveCalc.invariants.test.js
// pentru verificarile care ruleaza deja peste TOATE modulele.

import test from 'node:test'
import assert from 'node:assert/strict'
import { MODULES, computeModule } from './driveCalc.js'

const mod = (id) => {
  const m = MODULES.find((x) => x.id === id)
  if (!m) throw new Error(`modul inexistent: ${id}`)
  return m
}
// Calculeaza un modul pornind de la valorile lui implicite, cu suprascrieri optionale.
const calc = (id, over = {}) => {
  const m = mod(id)
  return computeModule(m, { ...Object.fromEntries(m.fields.map((f) => [f.key, f.default])), ...over })
}
// Comparatie relativa (absoluta langa zero).
function aprox(actual, expected, rel = 1e-9, mesaj = '') {
  const tol = Math.max(Math.abs(expected) * rel, 1e-12)
  assert.ok(
    Math.abs(actual - expected) <= tol,
    `${mesaj || 'valoare'}: ${actual} != ${expected} (toleranta ${tol})`
  )
}

const SQRT3 = Math.sqrt(3)

test('motor-turatie: turatie sincrona, alunecare, viteza unghiulara', () => {
  // Chapman ec. 7-1: n_s = 120 f / p. 50 Hz, 4 poli -> 1500 rpm exact.
  const r = calc('motor-turatie', { f: 50, p: 4, n: 1450 })
  aprox(r.ns, 1500, 0, 'ns')
  aprox(r.s, ((1500 - 1450) / 1500) * 100, 1e-12, 's')   // = 3.3333 %
  aprox(r.w, (2 * Math.PI * 1450) / 60, 1e-12, 'omega')
  aprox(r.fr, (50 / 30), 1e-12, 'f rotoric')             // s·f = 0.03333·50
  // 2 poli la 50 Hz = 3000 rpm; alunecare zero la turatie sincrona.
  aprox(calc('motor-turatie', { f: 50, p: 2, n: 3000 }).ns, 3000, 0, 'ns 2p')
  aprox(calc('motor-turatie', { f: 50, p: 2, n: 3000 }).s, 0, 0, 's la sincronism')
})

test('putere-curent: curentul se intoarce in puterea de la care a plecat', () => {
  // Identitate de verificare (independenta de forma din cod):
  // P_ax = sqrt(3)·U·I·cos(phi)·eta  trebuie sa dea inapoi P_n.
  const v = { Pn: 15, U: 400, cosphi: 0.85, eta: 90 }
  const r = calc('putere-curent', v)
  aprox((SQRT3 * v.U * r.I * v.cosphi * (v.eta / 100)) / 1000, v.Pn, 1e-9, 'round-trip putere')
  aprox(r.Pel, 15 / 0.9, 1e-12, 'putere absorbita')
  aprox(r.S, (SQRT3 * 400 * r.I) / 1000, 1e-12, 'S')
  // Triunghiul puterilor: S² = P² + Q².
  aprox(r.S ** 2, r.Pel ** 2 + r.Q ** 2, 1e-9, 'triunghiul puterilor')
})

test('cuplu: M_n din 9550·P/n, coerent cu P = M·omega', () => {
  const r = calc('cuplu', { P: 15, n: 1450, kp: 2, km: 2.5 })
  // Conventia din cod: constanta rotunjita 9550 (exact ar fi 60000/2pi = 9549.297).
  aprox(r.Mn, (9550 * 15) / 1450, 1e-12, 'Mn')
  // Verificare fizica independenta: P = M·omega. Abaterea admisa vine DOAR din
  // rotunjirea lui 9550 (~0.0074 %).
  const omega = (2 * Math.PI * 1450) / 60
  aprox((r.Mn * omega) / 1000, 15, 1e-4, 'P = M·omega')
  aprox(r.Mp, 2 * r.Mn, 1e-12, 'cuplu de pornire = kp·Mn')
  aprox(r.Mmax, 2.5 * r.Mn, 1e-12, 'cuplu maxim = km·Mn')
})

test('pornire: DOL, stea-triunghi, softstart, VFD', () => {
  const r = calc('pornire', { In: 28, kDOL: 6, Usoft: 70, climit: 1.3 })
  aprox(r.IpDOL, 168, 1e-12, 'DOL = 6·In')
  // Stea-triunghi: tensiunea pe faza scade cu sqrt(3) => curentul de linie scade de 3 ori.
  aprox(r.IpY, 168 / 3, 1e-12, 'stea = DOL/3')
  aprox(r.IpSoft, 0.7 * 168, 1e-12, 'softstart: curentul scade proportional cu U')
  // Cuplul scade cu patratul tensiunii: 0.7² = 49 %.
  aprox(r.MSoft, 49, 1e-12, 'cuplu softstart ~ U²')
  aprox(r.IpVFD, 1.3 * 28, 1e-12, 'VFD limitat la climit·In')
})

test('cablu: caderea de tensiune trifazata si sectiunea minima', () => {
  // dU = sqrt(3)·rho·L·I·cos(phi)/S  (bucla trifazata, rezistiv).
  const v = { I: 28, L: 50, U: 400, cosphi: 0.85, S: 6, rho: 0.0225 }
  const r = calc('cablu', v)
  const dU = (SQRT3 * v.rho * v.L * v.I * v.cosphi) / v.S
  aprox(r.dU, dU, 1e-12, 'dU')
  aprox(r.dUproc, (dU / 400) * 100, 1e-12, 'dU %')
  // Conventia din cod: sectiunea minima se calculeaza la pragul de 3 % din U.
  aprox(r.Smin, (SQRT3 * v.rho * v.L * v.I * v.cosphi) / (0.03 * v.U), 1e-12, 'S minim la 3 %')
  // Dublarea lungimii dubleaza caderea; dublarea sectiunii o injumatateste.
  aprox(calc('cablu', { ...v, L: 100 }).dU, 2 * dU, 1e-12, 'dU ~ L')
  aprox(calc('cablu', { ...v, S: 12 }).dU, dU / 2, 1e-12, 'dU ~ 1/S')
})

test('unda-reflectata: lungime critica si supratensiune la borne', () => {
  // Lungimea critica = distanta parcursa de front intr-o jumatate de timp de
  // crestere: L_crit = v_w·t_r/2 (IEC 60034-25).
  const r = calc('unda-reflectata', { tr: 0.1, vw: 150, Udc: 540, L: 30 })
  aprox(r.Lcrit, (150 * 0.1) / 2, 1e-12, 'L critic')
  // Reflexie totala la borne: varful ajunge la dublul tensiunii de bus.
  aprox(r.Upk, 2 * 540, 1e-12, 'U varf = 2·Udc')
  // Zona sigura e sub cea critica.
  assert.ok(r.Lsafe < r.Lcrit, 'L sigur trebuie sa fie sub L critic')
})

test('armonici: inductanta reactorului de linie din caderea procentuala', () => {
  // X = uk·U_faza/I ; L = X/(2·pi·f).
  const v = { Un: 400, In: 28, fn: 50, uk: 4, P: 15 }
  const r = calc('armonici', v)
  const X = (v.uk / 100) * (v.Un / SQRT3) / v.In
  aprox(r.Lr, (X / (2 * Math.PI * v.fn)) * 1000, 1e-9, 'L reactor [mH]')
  aprox(r.dUr, (v.uk / 100) * v.Un, 1e-12, 'cadere pe reactor')
})

test('dinamica: timp de accelerare si energie cinetica', () => {
  // t = J·dOmega/M_net ; E = J·omega²/2.
  const v = { J: 0.5, n1: 0, n2: 1450, Macc: 100, Mload: 40 }
  const r = calc('dinamica', v)
  const dw = (2 * Math.PI * 1450) / 60
  aprox(r.dw, dw, 1e-12, 'delta omega')
  aprox(r.tacc, (0.5 * dw) / (100 - 40), 1e-12, 't accelerare')
  aprox(r.Ecin, 0.5 * 0.5 * dw ** 2, 1e-12, 'energie cinetica')
  // Cuplu net dublu => timp injumatatit.
  aprox(calc('dinamica', { ...v, Macc: 160 }).tacc, r.tacc / 2, 1e-12, 't ~ 1/M net')
})

test('sarcina-afinitate: Q~n, H~n², P~n³', () => {
  const v = { n1: 1450, n2: 1160, Q1: 100, H1: 32, P1: 15 }
  const k = 1160 / 1450   // = 0.8
  const r = calc('sarcina-afinitate', v)
  aprox(r.Q2, 100 * k, 1e-12, 'debit ~ n')
  aprox(r.H2, 32 * k ** 2, 1e-12, 'inaltime ~ n²')
  aprox(r.P2, 15 * k ** 3, 1e-12, 'putere ~ n³')
  aprox(r.econ, (1 - k ** 3) * 100, 1e-12, 'economie')
})

test('npsh: NPSH disponibil, scalarea cu n² si marja', () => {
  // NPSHa = (p_atm - p_vap)/(rho·g) + H_asp - H_frec.
  // Conventia campului (vezi eticheta "+inecat"): H_asp POZITIV = aspiratie inecata.
  const v = { patm: 1.013, pvap: 0.023, rho: 1000, Hasp: 2, Hfrec: 1.5, NPSHrn: 3, nratio: 100 }
  const r = calc('npsh', v)
  const coloana = ((1.013 - 0.023) * 1e5) / (1000 * 9.81)
  aprox(r.NPSHa, coloana + 2 - 1.5, 1e-12, 'NPSH disponibil')
  aprox(r.marja, r.NPSHa - r.NPSHr, 1e-12, 'marja')
  // NPSH cerut creste cu patratul turatiei (+20 % turatie => ×1.44).
  aprox(calc('npsh', { ...v, nratio: 120 }).NPSHr, 3 * 1.2 ** 2, 1e-12, 'NPSHr ~ n²')
})

test('termic: curent echivalent RMS si putere S3', () => {
  // I_ech = sqrt( sum(I²·t) / sum(t) ) — incalzirea urmareste I²t.
  const v = { I1: 30, t1: 20, I2: 10, t2: 40, DC: 40, Ps1: 15, H: 2000, Tamb: 45 }
  const r = calc('termic', v)
  aprox(r.Iech, Math.sqrt((30 ** 2 * 20 + 10 ** 2 * 40) / 60), 1e-12, 'I echivalent')
  aprox(r.Ps3, 15 / Math.sqrt(0.4), 1e-12, 'P la S3 40 %')
})

test('regimuri-s: S2 din constanta termica, S3 din durata de actionare', () => {
  const v = { Ps1: 15, DC: 40, tP: 30, tau: 45 }
  const r = calc('regimuri-s', v)
  // S2 (scurta durata): P_S2 = P_S1 / sqrt(1 - e^(-t/tau)) — IEC 60034-1.
  aprox(r.PS2, 15 / Math.sqrt(1 - Math.exp(-30 / 45)), 1e-9, 'P la S2')
  aprox(r.PS3, 15 / Math.sqrt(0.4), 1e-9, 'P la S3')
  // Durata mult mai lunga decat constanta termica => S2 tinde catre S1.
  aprox(calc('regimuri-s', { ...v, tP: 1000 }).PS2, 15, 1e-6, 'S2 -> S1 la t mare')
})

test('incarcare: putere la ax si grad de incarcare din masuratori', () => {
  const v = { U: 400, Im: 22, cosphi: 0.82, eta: 90, Pn: 15, In: 28, I0: 10 }
  const r = calc('incarcare', v)
  aprox(r.Pax, (SQRT3 * 400 * 22 * 0.82 * 0.9) / 1000, 1e-12, 'P la ax')
  aprox(r.incP, (r.Pax / 15) * 100, 1e-12, 'incarcare dupa putere')
  // Dupa curent, corectat cu mersul in gol: (Im - I0)/(In - I0).
  aprox(r.incI, ((22 - 10) / (28 - 10)) * 100, 1e-12, 'incarcare dupa curent')
})

test('vfd: bus c.c., varf si V/f', () => {
  const r = calc('vfd', { Ulinie: 400, fn: 50, f: 40, Pies: 15, Tamb: 45 })
  // Conventia din cod: valoarea medie a puntii in 6 pulsuri, 1.35·U_linie.
  aprox(r.Udc, 1.35 * 400, 1e-12, 'U bus c.c.')
  aprox(r.Udcpk, Math.SQRT2 * 400, 1e-12, 'varf = sqrt(2)·U')
  // Sub frecventa nominala, V/f constant: U_ies = U·f/fn.
  aprox(r.Uies, 400 * (40 / 50), 1e-12, 'U iesire la 40 Hz')
})

test('transformator: putere aleasa si curent nominal', () => {
  const r = calc('transformator')   // valorile implicite ale cardului
  // Trafo-ul acopera si regimul de durata, si pornirea celui mai mare motor.
  aprox(r.Strafo, Math.max(r.Strec, r.Spor), 1e-12, 'S trafo = max(regim, pornire)')
  aprox(r.Intr, (r.Strafo * 1000) / (SQRT3 * 400), 1e-9, 'curent nominal trafo')
})

test('selectie-drive: suprasarcina heavy si light duty', () => {
  const r = calc('selectie-drive', { In: 28, Pn: 15 })
  aprox(r.OLHD, 1.5 * 28, 1e-12, 'HD 150 %')
  aprox(r.OLND, 1.1 * 28, 1e-12, 'ND 110 %')
})

// ---- Coerenta intre module: aceeasi marime calculata in doua locuri ----
// Astea prind driftul: cineva schimba o formula intr-un card si uita geamanul.

test('viteza unghiulara e aceeasi in toate cardurile care o calculeaza', () => {
  const n = 1450
  const asteptat = (2 * Math.PI * n) / 60
  aprox(calc('motor-turatie', { n }).w, asteptat, 1e-12, 'omega in motor-turatie')
  aprox(calc('cuplu', { n }).w, asteptat, 1e-12, 'omega in cuplu')
  aprox(calc('dinamica', { n1: 0, n2: n }).dw, asteptat, 1e-12, 'omega in dinamica')
})

test('puterea la S3 e aceeasi in "termic" si in "regimuri-s"', () => {
  for (const DC of [25, 40, 60]) {
    aprox(
      calc('termic', { Ps1: 15, DC }).Ps3,
      calc('regimuri-s', { Ps1: 15, DC }).PS3,
      1e-12,
      `S3 la DC=${DC}%`
    )
  }
})
