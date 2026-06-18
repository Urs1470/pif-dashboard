// Calculator actionari electrice — motor de calcul data-driven.
//
// Fiecare modul declara:
//   id, family, tier, title, subtitle?, note?, params? (referinte drive ABB/Siemens)
//   fields[]  : intrari { key, label, unit, default, step?, min? }
//   results[] : iesiri  { key, label, unit, tex (LaTeX), calc(v, r), dec? }
//
// calc(v, r): v = valorile de intrare (coercite la numere), r = rezultatele deja
// calculate in acest modul (in ordine). Intoarce null => se afiseaza "—".
//
// Formule verificate adversarial (workflow drive-calc-equations / -motor-types) si
// confirmate din wiki_job: ABB Technical Guide Book No.7/8/9 + Chapman + Hughes.
// Parametri drive confirmati din manualele de firmware (ACS880/DCS880/G120/S120/DCM).
// Tensiune doar JT (400/690 V).

export const FAMILIES = [
  { id: 'asincron', label: 'Asincron' },
  { id: 'comun', label: 'Comune' },
  { id: 'cc', label: 'Curent continuu' },
  { id: 'servo', label: 'Servo / PMSM' },
  { id: 'sincron', label: 'Sincron' },
]

const SQRT3 = Math.sqrt(3)
const omega = (n) => (2 * Math.PI * n) / 60 // rpm -> rad/s
const rad = (deg) => (deg * Math.PI) / 180

// Culori grafice (CSS vars se adapteaza light/dark; marker = aqua Everforest fix).
const COL = { a: 'var(--accent)', b: 'var(--warning)', c: 'var(--danger)', op: '#7fbbb3' }
// Genereaza puncte {x,y} pentru o functie y=fn(x) pe intervalul [xMin, xMax].
function curve(xMin, xMax, fn, steps = 48) {
  const pts = []
  for (let i = 0; i <= steps; i++) {
    const x = xMin + ((xMax - xMin) * i) / steps
    const y = fn(x)
    if (Number.isFinite(y)) pts.push({ x, y })
  }
  return pts
}

export const MODULES = [
  // ============================================================== ASINCRON
  {
    id: 'motor-turatie',
    family: 'asincron',
    tier: 1,
    title: 'Motor & turatie',
    subtitle: 'Turatie sincrona, alunecare, viteza unghiulara',
    params: 'Turatie max: ABB 30.12 · Siemens p1082',
    fields: [
      { key: 'f', label: 'Frecventa', unit: 'Hz', default: 50, step: 1, min: 0 },
      { key: 'p', label: 'Numar de poli', unit: '', default: 4, step: 2, min: 2 },
      { key: 'n', label: 'Turatie masurata', unit: 'rpm', default: 1450, step: 10, min: 0 },
    ],
    results: [
      { key: 'ns', label: 'Turatie sincrona', unit: 'rpm', tex: 'n_s = \\dfrac{120\\,f}{p}',
        calc: (v) => (v.p ? (120 * v.f) / v.p : null), dec: 0 },
      { key: 's', label: 'Alunecare', unit: '%', tex: 's = \\dfrac{n_s - n}{n_s}\\cdot 100',
        calc: (v, r) => (r.ns ? ((r.ns - v.n) / r.ns) * 100 : null), dec: 2 },
      { key: 'w', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega = \\dfrac{2\\pi n}{60}',
        calc: (v) => omega(v.n), dec: 2 },
      { key: 'fr', label: 'Frecventa rotorica', unit: 'Hz', tex: 'f_r = \\dfrac{s}{100}\\,f',
        calc: (v, r) => (r.s != null ? (r.s / 100) * v.f : null), dec: 2 },
    ],
  },
  {
    id: 'putere-curent',
    family: 'asincron',
    tier: 1,
    title: 'Putere & curent',
    subtitle: 'Curent absorbit, putere aparenta si reactiva',
    params: 'Date motor: ABB 99.6-99.12 · Siemens p0304-p0312',
    fields: [
      { key: 'Pn', label: 'Putere nominala', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'cosphi', label: 'Factor de putere cos φ', unit: '', default: 0.85, step: 0.01, min: 0 },
      { key: 'eta', label: 'Randament', unit: '%', default: 90, step: 1, min: 0 },
    ],
    results: [
      { key: 'I', label: 'Curent absorbit', unit: 'A', tex: 'I = \\dfrac{P_n\\cdot 1000}{\\sqrt{3}\\,U\\cos\\varphi\\,\\eta}',
        calc: (v) => { const d = SQRT3 * v.U * v.cosphi * (v.eta / 100); return d ? (v.Pn * 1000) / d : null }, dec: 1 },
      { key: 'Pel', label: 'Putere activa absorbita', unit: 'kW', tex: 'P_{el} = \\dfrac{P_n}{\\eta}',
        calc: (v) => (v.eta ? v.Pn / (v.eta / 100) : null), dec: 2 },
      { key: 'S', label: 'Putere aparenta', unit: 'kVA', tex: 'S = \\dfrac{\\sqrt{3}\\,U I}{1000}',
        calc: (v, r) => (r.I != null ? (SQRT3 * v.U * r.I) / 1000 : null), dec: 2 },
      { key: 'Q', label: 'Putere reactiva', unit: 'kVAr', tex: 'Q = \\sqrt{S^2 - P_{el}^2}',
        calc: (v, r) => { if (r.S == null || r.Pel == null) return null; const q = r.S * r.S - r.Pel * r.Pel; return q > 0 ? Math.sqrt(q) : 0 }, dec: 2 },
    ],
  },
  {
    id: 'cuplu',
    family: 'asincron',
    tier: 1,
    title: 'Cuplu',
    subtitle: 'Cuplu nominal, de pornire si maxim',
    params: 'Limita cuplu: ABB 30.19/30.20 · Siemens p1520',
    charts: [(v) => {
      if (!v.n || !v.P) return null
      const pp = Math.max(1, Math.round(3000 / v.n)); const ns = 3000 / pp
      const Mn = (9550 * v.P) / v.n, Mmax = v.km * Mn, Mstart = v.kp * Mn
      const X = Mstart > 0 ? (2 * Mmax) / Mstart : 0
      let sk = X > 2 ? (X - Math.sqrt(X * X - 4)) / 2 : 0.2
      if (!(sk > 0 && sk < 1)) sk = 0.2
      const kloss = (s) => (2 * Mmax) / (s / sk + sk / s)
      const motor = curve(1, ns, (n) => kloss((ns - n) / ns))
      const load = curve(0, ns, (n) => Mn * (n / v.n) ** 2)
      let op = null
      for (let n = ns * 0.4; n <= ns; n += ns / 240) {
        const Ml = Mn * (n / v.n) ** 2
        if (kloss((ns - n) / ns) <= Ml) { op = { x: Math.round(n), y: Math.round(Ml), label: 'functionare', color: COL.op }; break }
      }
      return {
        xLabel: 'Turatie n [rpm]', yLabel: 'Cuplu M [Nm]',
        series: [{ label: 'M motor', color: COL.a, points: motor }, { label: 'M rezistent (pompa)', color: COL.b, dash: true, points: load }],
        markers: op ? [op] : [],
      }
    }],
    fields: [
      { key: 'P', label: 'Putere', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'n', label: 'Turatie nominala', unit: 'rpm', default: 1450, step: 10, min: 1 },
      { key: 'kp', label: 'Factor cuplu pornire', unit: '×Mn', default: 2.0, step: 0.1, min: 0 },
      { key: 'km', label: 'Factor cuplu maxim', unit: '×Mn', default: 2.5, step: 0.1, min: 0 },
    ],
    results: [
      { key: 'Mn', label: 'Cuplu nominal', unit: 'Nm', tex: 'M_n = \\dfrac{9550\\,P}{n}',
        calc: (v) => (v.n ? (9550 * v.P) / v.n : null), dec: 1 },
      { key: 'Mp', label: 'Cuplu de pornire', unit: 'Nm', tex: 'M_p = k_p\\,M_n',
        calc: (v, r) => (r.Mn != null ? v.kp * r.Mn : null), dec: 1 },
      { key: 'Mmax', label: 'Cuplu maxim (breakdown)', unit: 'Nm', tex: 'M_{max} = k_m\\,M_n',
        calc: (v, r) => (r.Mn != null ? v.km * r.Mn : null), dec: 1 },
      { key: 'w', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega = \\dfrac{2\\pi n}{60}',
        calc: (v) => omega(v.n), dec: 2 },
    ],
  },
  {
    id: 'sarcina-afinitate',
    family: 'asincron',
    tier: 1,
    title: 'Legile afinitatii (pompe/ventilatoare)',
    subtitle: 'Debit, inaltime si putere la turatie variabila',
    note: 'Valabil pentru sarcina patratica (pompe centrifuge, ventilatoare).',
    charts: [
      (v) => {
        if (!v.n1) return null
        const xmax = Math.max(v.n1, v.n2)
        const pts = curve(0, xmax, (n) => v.P1 * (n / v.n1) ** 3)
        const op = { x: v.n2, y: v.P1 * (v.n2 / v.n1) ** 3, label: 'la n2', color: COL.op }
        return { xLabel: 'Turatie n [rpm]', yLabel: 'Putere P [kW]', series: [{ label: 'P(n) ~ n³', color: COL.a, points: pts }], markers: [op] }
      },
      (v) => {
        if (!v.Q1) return null
        const a = v.H1 / v.Q1 ** 2
        const pts = curve(0, v.Q1 * 1.15, (Q) => a * Q ** 2)
        return {
          xLabel: 'Debit Q [m³/h]', yLabel: 'Inaltime H [m]',
          series: [{ label: 'Locus afinitate H~Q²', color: COL.b, points: pts }],
          markers: [{ x: v.Q1, y: v.H1, label: 'n1', color: COL.a }, { x: v.Q1 * (v.n2 / v.n1), y: v.H1 * (v.n2 / v.n1) ** 2, label: 'n2', color: COL.op }],
        }
      },
    ],
    fields: [
      { key: 'n1', label: 'Turatie initiala', unit: 'rpm', default: 1450, step: 10, min: 1 },
      { key: 'n2', label: 'Turatie noua', unit: 'rpm', default: 1160, step: 10, min: 0 },
      { key: 'Q1', label: 'Debit la n1', unit: 'm³/h', default: 100, step: 5, min: 0 },
      { key: 'H1', label: 'Inaltime la n1', unit: 'm', default: 32, step: 1, min: 0 },
      { key: 'P1', label: 'Putere la n1', unit: 'kW', default: 15, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'Q2', label: 'Debit la n2', unit: 'm³/h', tex: 'Q_2 = Q_1\\dfrac{n_2}{n_1}',
        calc: (v) => (v.n1 ? v.Q1 * (v.n2 / v.n1) : null), dec: 1 },
      { key: 'H2', label: 'Inaltime la n2', unit: 'm', tex: 'H_2 = H_1\\left(\\dfrac{n_2}{n_1}\\right)^2',
        calc: (v) => (v.n1 ? v.H1 * (v.n2 / v.n1) ** 2 : null), dec: 1 },
      { key: 'P2', label: 'Putere la n2', unit: 'kW', tex: 'P_2 = P_1\\left(\\dfrac{n_2}{n_1}\\right)^3',
        calc: (v) => (v.n1 ? v.P1 * (v.n2 / v.n1) ** 3 : null), dec: 2 },
      { key: 'econ', label: 'Economie de putere', unit: '%', tex: '\\eta_{ec} = \\left(1-\\left(\\dfrac{n_2}{n_1}\\right)^3\\right)100',
        calc: (v) => (v.n1 ? (1 - (v.n2 / v.n1) ** 3) * 100 : null), dec: 1 },
    ],
  },
  {
    id: 'pornire',
    family: 'asincron',
    tier: 2,
    title: 'Metode de pornire',
    subtitle: 'Curent de pornire: DOL, stea-triunghi, softstart, VFD',
    params: 'Limita curent VFD: ABB 30.17 · Siemens p0640',
    charts: [(v) => {
      const shape = (x) => v.In * (1 + (v.kDOL - 1) * (1 - (x / 100) ** 3))
      return {
        xLabel: 'Turatie [% sincron]', yLabel: 'Curent [A]',
        series: [
          { label: 'DOL', color: COL.c, points: curve(0, 100, shape) },
          { label: 'Softstart', color: COL.b, points: curve(0, 100, (x) => shape(x) * (v.Usoft / 100)) },
          { label: 'VFD', color: COL.a, points: curve(0, 100, () => v.climit * v.In) },
        ],
      }
    }],
    fields: [
      { key: 'In', label: 'Curent nominal', unit: 'A', default: 28, step: 1, min: 0 },
      { key: 'kDOL', label: 'Factor pornire DOL', unit: '×In', default: 6, step: 0.5, min: 0 },
      { key: 'Usoft', label: 'Tensiune softstart', unit: '%', default: 70, step: 5, min: 0 },
      { key: 'climit', label: 'Factor curent VFD', unit: '×In', default: 1.3, step: 0.1, min: 0 },
    ],
    results: [
      { key: 'IpDOL', label: 'Curent pornire DOL', unit: 'A', tex: 'I_{p,DOL} = k\\,I_n',
        calc: (v) => v.kDOL * v.In, dec: 1 },
      { key: 'IpY', label: 'Curent pornire stea-triunghi', unit: 'A', tex: 'I_{p,Y} = I_{p,DOL}/3',
        calc: (v, r) => r.IpDOL / 3, dec: 1 },
      { key: 'IpSoft', label: 'Curent pornire softstart', unit: 'A', tex: 'I_{p,soft} = I_{p,DOL}\\dfrac{U}{U_n}',
        calc: (v, r) => r.IpDOL * (v.Usoft / 100), dec: 1 },
      { key: 'MSoft', label: 'Cuplu pornire softstart', unit: '%', tex: 'M_{p,soft} = \\left(\\dfrac{U}{U_n}\\right)^2 100',
        calc: (v) => (v.Usoft / 100) ** 2 * 100, dec: 0 },
      { key: 'IpVFD', label: 'Curent pornire VFD', unit: 'A', tex: 'I_{p,VFD} = c\\,I_n',
        calc: (v) => v.climit * v.In, dec: 1 },
    ],
  },
  {
    id: 'incarcare',
    family: 'asincron',
    tier: 2,
    title: 'Incarcare din masuratori',
    subtitle: 'Estimarea incarcarii motorului din curent/putere',
    note: 'Estimarea din curent e aproximativa la sarcini mici (cos φ scade).',
    fields: [
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'Im', label: 'Curent masurat', unit: 'A', default: 22, step: 0.5, min: 0 },
      { key: 'cosphi', label: 'cos φ masurat', unit: '', default: 0.82, step: 0.01, min: 0 },
      { key: 'eta', label: 'Randament', unit: '%', default: 90, step: 1, min: 0 },
      { key: 'Pn', label: 'Putere nominala', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'In', label: 'Curent nominal', unit: 'A', default: 28, step: 1, min: 1 },
      { key: 'I0', label: 'Curent mers in gol', unit: 'A', default: 10, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'Pax', label: 'Putere la arbore (estimat)', unit: 'kW', tex: 'P_{ax} = \\dfrac{\\sqrt{3}\\,U I\\cos\\varphi\\,\\eta}{1000}',
        calc: (v) => (SQRT3 * v.U * v.Im * v.cosphi * (v.eta / 100)) / 1000, dec: 2 },
      { key: 'incP', label: 'Incarcare din putere', unit: '%', tex: '\\dfrac{P_{ax}}{P_n}\\cdot 100',
        calc: (v, r) => (v.Pn ? (r.Pax / v.Pn) * 100 : null), dec: 0 },
      { key: 'incI', label: 'Incarcare din curent', unit: '%', tex: '\\dfrac{I - I_0}{I_n - I_0}\\cdot 100',
        calc: (v) => { const d = v.In - v.I0; return d > 0 ? ((v.Im - v.I0) / d) * 100 : null }, dec: 0 },
    ],
  },

  // ================================================================ COMUNE
  {
    id: 'dinamica',
    family: 'comun',
    tier: 1,
    title: 'Dinamica (rampe)',
    subtitle: 'Timp de accelerare si energie cinetica',
    params: 'Rampe: ABB 23.12/23.13 · Siemens p1120/p1121',
    fields: [
      { key: 'J', label: 'Inertie totala', unit: 'kg·m²', default: 0.5, step: 0.1, min: 0 },
      { key: 'n1', label: 'Turatie initiala', unit: 'rpm', default: 0, step: 10, min: 0 },
      { key: 'n2', label: 'Turatie finala', unit: 'rpm', default: 1450, step: 10, min: 0 },
      { key: 'Macc', label: 'Cuplu disponibil', unit: 'Nm', default: 100, step: 5, min: 0 },
      { key: 'Mload', label: 'Cuplu rezistent', unit: 'Nm', default: 40, step: 5, min: 0 },
    ],
    results: [
      { key: 'dw', label: 'Variatie viteza unghiulara', unit: 'rad/s', tex: '\\Delta\\omega = \\dfrac{2\\pi(n_2-n_1)}{60}',
        calc: (v) => omega(v.n2 - v.n1), dec: 2 },
      { key: 'tacc', label: 'Timp de accelerare', unit: 's', tex: 't_{acc} = \\dfrac{J\\,\\Delta\\omega}{M_{acc}-M_{load}}',
        calc: (v, r) => { const dm = v.Macc - v.Mload; return dm > 0 && r.dw != null ? (v.J * r.dw) / dm : null }, dec: 2 },
      { key: 'Ecin', label: 'Energie cinetica (la n2)', unit: 'J', tex: 'E_{cin} = \\tfrac{1}{2} J\\,\\omega_2^{2}',
        calc: (v) => 0.5 * v.J * omega(v.n2) ** 2, dec: 0 },
    ],
  },
  {
    id: 'energie-roi',
    family: 'comun',
    tier: 1,
    title: 'Energie & economii VFD',
    subtitle: 'Economie fata de reglaj prin vana/clapeta + payback',
    note: 'Economia presupune sarcina patratica (pompa/ventilator) reglata prin turatie.',
    fields: [
      { key: 'Pvana', label: 'Putere cu vana (100%)', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'nproc', label: 'Turatie proces', unit: '%', default: 80, step: 1, min: 0 },
      { key: 'ore', label: 'Ore functionare', unit: 'h/an', default: 4000, step: 100, min: 0 },
      { key: 'pret', label: 'Pret energie', unit: 'lei/kWh', default: 0.8, step: 0.05, min: 0 },
      { key: 'invest', label: 'Investitie VFD', unit: 'lei', default: 5000, step: 100, min: 0 },
    ],
    results: [
      { key: 'Pvfd', label: 'Putere cu VFD', unit: 'kW', tex: 'P_{vfd} = P_{vana}\\left(\\dfrac{n\\%}{100}\\right)^3',
        calc: (v) => v.Pvana * (v.nproc / 100) ** 3, dec: 2 },
      { key: 'dP', label: 'Economie de putere', unit: 'kW', tex: '\\Delta P = P_{vana}-P_{vfd}',
        calc: (v, r) => (r.Pvfd != null ? v.Pvana - r.Pvfd : null), dec: 2 },
      { key: 'Wsav', label: 'Economie anuala', unit: 'kWh/an', tex: 'W_{sav} = \\Delta P\\cdot ore',
        calc: (v, r) => (r.dP != null ? r.dP * v.ore : null), dec: 0 },
      { key: 'Csav', label: 'Economie in bani', unit: 'lei/an', tex: 'C_{sav} = W_{sav}\\cdot pret',
        calc: (v, r) => (r.Wsav != null ? r.Wsav * v.pret : null), dec: 0 },
      { key: 'payback', label: 'Recuperare investitie', unit: 'ani', tex: 'T = \\dfrac{Investitie}{C_{sav}}',
        calc: (v, r) => (r.Csav > 0 ? v.invest / r.Csav : null), dec: 1 },
    ],
  },
  {
    id: 'vfd',
    family: 'comun',
    tier: 2,
    title: 'Convertizor de frecventa (VFD)',
    subtitle: 'Tensiune DC bus, V/f, derating, pierderi',
    params: 'V/f: Siemens p1300+ · Udc monitorizat',
    charts: [(v) => {
      if (!v.fn) return null
      const boost = 0.08 * v.Ulinie
      const Uf = (f) => (f <= v.fn ? boost + (v.Ulinie - boost) * (f / v.fn) : v.Ulinie)
      return {
        xLabel: 'Frecventa f [Hz]', yLabel: 'Tensiune U [V]',
        series: [{ label: 'Caracteristica V/f', color: COL.a, points: curve(0, v.fn * 2, Uf) }],
        markers: [{ x: v.f, y: Uf(v.f), label: 'punct curent', color: COL.op }],
      }
    }],
    fields: [
      { key: 'Ulinie', label: 'Tensiune retea/motor', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'fn', label: 'Frecventa nominala', unit: 'Hz', default: 50, step: 1, min: 1 },
      { key: 'f', label: 'Frecventa de lucru', unit: 'Hz', default: 40, step: 1, min: 0 },
      { key: 'Pies', label: 'Putere de iesire', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'Tamb', label: 'Temperatura ambianta', unit: '°C', default: 45, step: 1, min: 0 },
    ],
    results: [
      { key: 'Udc', label: 'Tensiune DC bus', unit: 'V', tex: 'U_{dc} = 1.35\\,U_{linie}',
        calc: (v) => 1.35 * v.Ulinie, dec: 0 },
      { key: 'Udcpk', label: 'DC bus varf (gol)', unit: 'V', tex: 'U_{dc,pk} = \\sqrt{2}\\,U_{linie}',
        calc: (v) => Math.SQRT2 * v.Ulinie, dec: 0 },
      { key: 'Uies', label: 'Tensiune iesire (V/f)', unit: 'V', tex: 'U_{ies} = \\dfrac{U_n}{f_n}\\,f',
        calc: (v) => (v.fn ? (v.Ulinie / v.fn) * v.f : null), dec: 0 },
      { key: 'derT', label: 'Derating temperatura', unit: '%', tex: '1-\\dfrac{T_{amb}-40}{100}',
        calc: (v) => (v.Tamb > 40 ? (1 - (v.Tamb - 40) / 100) * 100 : 100), dec: 0 },
      { key: 'Ppierd', label: 'Pierderi convertizor', unit: 'kW', tex: 'P_{pierderi}\\approx 0.03\\,P_{ies}',
        calc: (v) => 0.03 * v.Pies, dec: 2 },
    ],
  },
  {
    id: 'cablu',
    family: 'comun',
    tier: 2,
    title: 'Cablu & cadere de tensiune',
    subtitle: 'Cadere de tensiune si sectiune minima',
    note: 'rho cupru ≈ 0.0225, aluminiu ≈ 0.036 Ω·mm²/m.',
    params: 'Lungime max cablu motor: vezi manual HW (du/dt)',
    fields: [
      { key: 'I', label: 'Curent', unit: 'A', default: 28, step: 1, min: 0 },
      { key: 'L', label: 'Lungime cablu', unit: 'm', default: 50, step: 5, min: 0 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'cosphi', label: 'cos φ', unit: '', default: 0.85, step: 0.01, min: 0 },
      { key: 'S', label: 'Sectiune cablu', unit: 'mm²', default: 6, step: 1, min: 0.1 },
      { key: 'rho', label: 'Rezistivitate', unit: 'Ω·mm²/m', default: 0.0225, step: 0.001, min: 0 },
    ],
    results: [
      { key: 'dU', label: 'Cadere de tensiune', unit: 'V', tex: '\\Delta U = \\dfrac{\\sqrt{3}\\,\\rho L I\\cos\\varphi}{S}',
        calc: (v) => (v.S ? (SQRT3 * v.rho * v.L * v.I * v.cosphi) / v.S : null), dec: 2 },
      { key: 'dUproc', label: 'Cadere de tensiune', unit: '%', tex: '\\Delta U\\% = \\dfrac{\\Delta U}{U}\\cdot 100',
        calc: (v, r) => (r.dU != null && v.U ? (r.dU / v.U) * 100 : null), dec: 2 },
      { key: 'Smin', label: 'Sectiune minima (3%)', unit: 'mm²', tex: 'S_{min} = \\dfrac{\\sqrt{3}\\,\\rho L I\\cos\\varphi}{0.03\\,U}',
        calc: (v) => (v.U ? (SQRT3 * v.rho * v.L * v.I * v.cosphi) / (0.03 * v.U) : null), dec: 2 },
    ],
  },
  {
    id: 'termic',
    family: 'comun',
    tier: 2,
    title: 'Termic & regimuri',
    subtitle: 'Curent echivalent, regim S3, derating',
    note: 'Derating altitudine doar pentru H > 1000 m. Verifica curba producatorului.',
    fields: [
      { key: 'I1', label: 'Curent segment 1', unit: 'A', default: 30, step: 1, min: 0 },
      { key: 't1', label: 'Timp segment 1', unit: 's', default: 20, step: 1, min: 0 },
      { key: 'I2', label: 'Curent segment 2', unit: 'A', default: 10, step: 1, min: 0 },
      { key: 't2', label: 'Timp segment 2', unit: 's', default: 40, step: 1, min: 0 },
      { key: 'DC', label: 'Durata de conectare (S3)', unit: '%', default: 40, step: 5, min: 1 },
      { key: 'Ps1', label: 'Putere in S1', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'H', label: 'Altitudine', unit: 'm', default: 2000, step: 100, min: 0 },
      { key: 'Tamb', label: 'Temperatura ambianta', unit: '°C', default: 45, step: 1, min: 0 },
    ],
    results: [
      { key: 'Iech', label: 'Curent termic echivalent', unit: 'A', tex: 'I_{ech} = \\sqrt{\\dfrac{I_1^2 t_1 + I_2^2 t_2}{t_1 + t_2}}',
        calc: (v) => { const t = v.t1 + v.t2; return t > 0 ? Math.sqrt((v.I1 ** 2 * v.t1 + v.I2 ** 2 * v.t2) / t) : null }, dec: 1 },
      { key: 'Ps3', label: 'Putere admisibila S3', unit: 'kW', tex: 'P_{S3} = \\dfrac{P_{S1}}{\\sqrt{DC/100}}',
        calc: (v) => (v.DC > 0 ? v.Ps1 / Math.sqrt(v.DC / 100) : null), dec: 2 },
      { key: 'falt', label: 'Factor derating altitudine', unit: '%', tex: 'f_{alt} = 1-\\dfrac{H-1000}{10000}',
        calc: (v) => (v.H > 1000 ? (1 - (v.H - 1000) / 10000) * 100 : 100), dec: 1 },
      { key: 'ftemp', label: 'Factor derating temperatura', unit: '%', tex: 'f_{temp} = 1-\\dfrac{T_{amb}-40}{100}',
        calc: (v) => (v.Tamb > 40 ? (1 - (v.Tamb - 40) / 100) * 100 : 100), dec: 1 },
    ],
  },
  {
    id: 'armonici',
    family: 'comun',
    tier: 2,
    title: 'Armonici & reactoare',
    subtitle: 'Inductanta reactor, cadere, regula THD',
    note: 'THD ~29% (6 pulsuri) cand L_dc[mH]·P[kW] ≈ 100.',
    params: 'Reactor de linie AC / reactor DC bus',
    fields: [
      { key: 'Un', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'In', label: 'Curent nominal', unit: 'A', default: 28, step: 1, min: 1 },
      { key: 'fn', label: 'Frecventa', unit: 'Hz', default: 50, step: 1, min: 1 },
      { key: 'uk', label: 'Impedanta reactor', unit: '%', default: 4, step: 0.5, min: 0 },
      { key: 'P', label: 'Putere motor', unit: 'kW', default: 15, step: 0.5, min: 0.1 },
    ],
    results: [
      { key: 'Lr', label: 'Inductanta reactor', unit: 'mH', tex: 'L = \\dfrac{u_k\\,U_n}{100\\,\\sqrt{3}\\,2\\pi f I_n}',
        calc: (v) => { const d = SQRT3 * 2 * Math.PI * v.fn * v.In; return d ? ((v.uk / 100) * v.Un / d) * 1000 : null }, dec: 2 },
      { key: 'dUr', label: 'Cadere pe reactor', unit: 'V', tex: '\\Delta U = \\sqrt{3}\\,2\\pi f L I_n',
        calc: (v) => { const L = (v.uk / 100) * v.Un / (SQRT3 * 2 * Math.PI * v.fn * v.In); return SQRT3 * 2 * Math.PI * v.fn * L * v.In }, dec: 1 },
      { key: 'Ldc', label: 'L_dc recomandat (THD)', unit: 'mH', tex: 'L_{dc} \\approx \\dfrac{100}{P}',
        calc: (v) => (v.P ? 100 / v.P : null), dec: 2 },
    ],
  },
  {
    id: 'compensare',
    family: 'comun',
    tier: 2,
    title: 'Compensare cos φ',
    subtitle: 'Putere reactiva, capacitate, curent baterie',
    note: 'La motor pe VFD NU compensa in amonte; niciodata condensatoare pe iesirea VFD.',
    fields: [
      { key: 'P', label: 'Putere activa', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'PF1', label: 'cos φ initial', unit: '', default: 0.75, step: 0.01, min: 0.01 },
      { key: 'PF2', label: 'cos φ tinta', unit: '', default: 0.95, step: 0.01, min: 0.01 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'f', label: 'Frecventa', unit: 'Hz', default: 50, step: 1, min: 1 },
    ],
    results: [
      { key: 'k', label: 'Factor compensare', unit: 'kvar/kW', tex: 'k = \\tan\\varphi_1 - \\tan\\varphi_2',
        calc: (v) => Math.tan(Math.acos(v.PF1)) - Math.tan(Math.acos(v.PF2)), dec: 3 },
      { key: 'Qc', label: 'Putere reactiva necesara', unit: 'kVAr', tex: 'Q_c = P(\\tan\\varphi_1 - \\tan\\varphi_2)',
        calc: (v, r) => v.P * r.k, dec: 2 },
      { key: 'Cd', label: 'Capacitate (triunghi)', unit: 'µF', tex: 'C_\\triangle = \\dfrac{Q_c}{3\\cdot 2\\pi f U^2}',
        calc: (v, r) => { const d = 3 * 2 * Math.PI * v.f * v.U ** 2; return d ? (r.Qc * 1000 / d) * 1e6 : null }, dec: 1 },
      { key: 'Ic', label: 'Curent baterie', unit: 'A', tex: 'I_c = \\dfrac{Q_c}{\\sqrt{3}\\,U}',
        calc: (v, r) => (v.U ? (r.Qc * 1000) / (SQRT3 * v.U) : null), dec: 1 },
    ],
  },
  {
    id: 'transmisii',
    family: 'comun',
    tier: 2,
    title: 'Transmisii mecanice',
    subtitle: 'Reductor: turatie, cuplu, inertie redusa, viteza liniara',
    fields: [
      { key: 'Pmotor', label: 'Putere motor', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'nin', label: 'Turatie intrare', unit: 'rpm', default: 1450, step: 10, min: 1 },
      { key: 'i', label: 'Raport de transmisie', unit: ':1', default: 10, step: 0.5, min: 0.1 },
      { key: 'eta', label: 'Randament reductor', unit: '%', default: 95, step: 1, min: 0 },
      { key: 'Jsarc', label: 'Inertie sarcina', unit: 'kg·m²', default: 50, step: 1, min: 0 },
      { key: 'D', label: 'Diametru tambur', unit: 'm', default: 0.3, step: 0.05, min: 0 },
    ],
    results: [
      { key: 'nout', label: 'Turatie iesire', unit: 'rpm', tex: 'n_{out} = n_{in}/i',
        calc: (v) => (v.i ? v.nin / v.i : null), dec: 1 },
      { key: 'Min', label: 'Cuplu la motor', unit: 'Nm', tex: 'M_{in} = \\dfrac{9550\\,P}{n_{in}}',
        calc: (v) => (v.nin ? (9550 * v.Pmotor) / v.nin : null), dec: 1 },
      { key: 'Mout', label: 'Cuplu la iesire', unit: 'Nm', tex: 'M_{out} = M_{in}\\,i\\,\\eta',
        calc: (v, r) => (r.Min != null ? r.Min * v.i * (v.eta / 100) : null), dec: 1 },
      { key: 'Jred', label: 'Inertie redusa la ax motor', unit: 'kg·m²', tex: 'J_{red} = J_{sarcina}/i^2',
        calc: (v) => (v.i ? v.Jsarc / v.i ** 2 : null), dec: 3 },
      { key: 'vlin', label: 'Viteza liniara (tambur)', unit: 'm/s', tex: 'v = \\dfrac{\\pi D\\,n_{out}}{60}',
        calc: (v, r) => (r.nout != null ? (Math.PI * v.D * r.nout) / 60 : null), dec: 2 },
    ],
  },
  {
    id: 'selectie-drive',
    family: 'comun',
    tier: 2,
    title: 'Selectie drive (HD/ND)',
    subtitle: 'Curent si suprasarcina heavy/normal duty',
    note: 'Drive ales dupa curent: I_drive,cont ≥ I_n motor. HD pt. cupluri de soc, ND pt. pompe/vent.',
    fields: [
      { key: 'In', label: 'Curent nominal motor', unit: 'A', default: 28, step: 1, min: 0 },
      { key: 'Pn', label: 'Putere nominala', unit: 'kW', default: 15, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'OLHD', label: 'Suprasarcina HD (150%/60s)', unit: 'A', tex: 'I_{OL,HD} = 1.5\\,I_n',
        calc: (v) => 1.5 * v.In, dec: 1 },
      { key: 'OLND', label: 'Suprasarcina ND (110%/60s)', unit: 'A', tex: 'I_{OL,ND} = 1.1\\,I_n',
        calc: (v) => 1.1 * v.In, dec: 1 },
      { key: 'Inest', label: 'Curent estimat (la 400 V)', unit: 'A', tex: 'I_n \\approx 2\\,P[\\text{kW}]',
        calc: (v) => 2 * v.Pn, dec: 1 },
    ],
  },
  {
    id: 'raport-inertie',
    family: 'comun',
    tier: 2,
    title: 'Raport de inertie',
    subtitle: 'Pentru tuning bucla de turatie',
    note: 'Tinta R_J < 5 (servo) ... < 10 (uz general) pentru reglaj stabil.',
    fields: [
      { key: 'Jmot', label: 'Inertie motor', unit: 'kg·m²', default: 0.05, step: 0.01, min: 0.0001 },
      { key: 'Jsarc', label: 'Inertie sarcina', unit: 'kg·m²', default: 2.5, step: 0.1, min: 0 },
      { key: 'i', label: 'Raport de transmisie', unit: ':1', default: 5, step: 0.5, min: 0.1 },
    ],
    results: [
      { key: 'Jred', label: 'Inertie sarcina redusa', unit: 'kg·m²', tex: 'J_{red} = J_{sarcina}/i^2',
        calc: (v) => (v.i ? v.Jsarc / v.i ** 2 : null), dec: 4 },
      { key: 'RJ', label: 'Raport de inertie', unit: '×', tex: 'R_J = J_{red}/J_{motor}',
        calc: (v, r) => (v.Jmot ? r.Jred / v.Jmot : null), dec: 2 },
    ],
  },
  {
    id: 'turatie-critica',
    family: 'comun',
    tier: 2,
    title: 'Turatie critica & skip',
    subtitle: 'Rezonanta mecanica si benzi de evitat',
    params: 'Skip: ABB 22.51-22.57 · Siemens p1091-1094/p1101',
    fields: [
      { key: 'k', label: 'Rigiditate', unit: 'N/m', default: 1e7, step: 1e5, min: 0 },
      { key: 'm', label: 'Masa', unit: 'kg', default: 50, step: 1, min: 0.1 },
      { key: 'fskip', label: 'Frecventa de evitat', unit: 'Hz', default: 25, step: 1, min: 0 },
      { key: 'df', label: 'Latime banda', unit: 'Hz', default: 2, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'ncrit', label: 'Turatie critica', unit: 'rpm', tex: 'n_{crit} = \\dfrac{60}{2\\pi}\\sqrt{\\dfrac{k}{m}}',
        calc: (v) => (v.m ? (60 / (2 * Math.PI)) * Math.sqrt(v.k / v.m) : null), dec: 0 },
      { key: 'bjos', label: 'Banda skip - jos', unit: 'Hz', tex: 'f_{skip} - \\Delta f',
        calc: (v) => v.fskip - v.df, dec: 1 },
      { key: 'bsus', label: 'Banda skip - sus', unit: 'Hz', tex: 'f_{skip} + \\Delta f',
        calc: (v) => v.fskip + v.df, dec: 1 },
    ],
  },
  {
    id: 'conversii',
    family: 'comun',
    tier: 2,
    title: 'Conversii de unitati',
    subtitle: 'HP, kgf·m, rad/s, kgf',
    fields: [
      { key: 'hp', label: 'Putere', unit: 'HP', default: 20, step: 1, min: 0 },
      { key: 'kgfm', label: 'Cuplu', unit: 'kgf·m', default: 10, step: 1, min: 0 },
      { key: 'rpm', label: 'Turatie', unit: 'rpm', default: 1450, step: 10, min: 0 },
      { key: 'kgf', label: 'Forta', unit: 'kgf', default: 100, step: 5, min: 0 },
    ],
    results: [
      { key: 'kW', label: 'Putere', unit: 'kW', tex: 'kW = HP\\cdot 0.7457',
        calc: (v) => v.hp * 0.7457, dec: 2 },
      { key: 'Nm', label: 'Cuplu', unit: 'Nm', tex: 'Nm = kgf{\\cdot}m\\cdot 9.807',
        calc: (v) => v.kgfm * 9.807, dec: 2 },
      { key: 'rads', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega = rpm\\cdot\\dfrac{2\\pi}{60}',
        calc: (v) => omega(v.rpm), dec: 2 },
      { key: 'N', label: 'Forta', unit: 'N', tex: 'N = kgf\\cdot 9.807',
        calc: (v) => v.kgf * 9.807, dec: 1 },
    ],
  },

  // ======================================================== CURENT CONTINUU
  {
    id: 'cc-baza',
    family: 'cc',
    tier: 2,
    title: 'Motor c.c. — marimi fundamentale',
    subtitle: 'TCEM, turatie, cuplu, putere (flux constant)',
    note: 'k·Φ in SI [V·s/rad = Nm/A]. M = k·Φ·Ia, E = k·Φ·ω.',
    charts: [(v) => {
      if (!v.kPhi) return null
      const Mrated = v.kPhi * v.Ia
      const nM = (M) => ((v.U - (M / v.kPhi) * v.Ra) * 60) / (2 * Math.PI * v.kPhi)
      return {
        xLabel: 'Cuplu M [Nm]', yLabel: 'Turatie n [rpm]',
        series: [{ label: 'n(M) separat excitat', color: COL.a, points: curve(0, Math.max(Mrated * 2, 1), nM) }],
        markers: [{ x: Mrated, y: nM(Mrated), label: 'functionare', color: COL.op }],
      }
    }],
    params: 'DCS880: U arm 99.12, Ia 99.11, Ra 27.32 · DCM: p50101/p50100/p50110',
    fields: [
      { key: 'U', label: 'Tensiune indus', unit: 'V', default: 440, step: 10, min: 0 },
      { key: 'Ia', label: 'Curent indus', unit: 'A', default: 80, step: 1, min: 0 },
      { key: 'Ra', label: 'Rezistenta indus', unit: 'Ω', default: 0.15, step: 0.01, min: 0 },
      { key: 'kPhi', label: 'Constanta k·Φ', unit: 'V·s/rad', default: 2.6, step: 0.1, min: 0.01 },
    ],
    results: [
      { key: 'E', label: 'TCEM (back-EMF)', unit: 'V', tex: 'E = U - I_a R_a',
        calc: (v) => v.U - v.Ia * v.Ra, dec: 1 },
      { key: 'n', label: 'Turatie', unit: 'rpm', tex: 'n = \\dfrac{60\\,E}{2\\pi\\,k\\Phi}',
        calc: (v, r) => (v.kPhi ? (60 * r.E) / (2 * Math.PI * v.kPhi) : null), dec: 0 },
      { key: 'M', label: 'Cuplu electromagnetic', unit: 'Nm', tex: 'M = k\\Phi\\,I_a',
        calc: (v) => v.kPhi * v.Ia, dec: 1 },
      { key: 'Pem', label: 'Putere electromagnetica', unit: 'kW', tex: 'P_{em} = E\\,I_a',
        calc: (v, r) => (r.E * v.Ia) / 1000, dec: 2 },
    ],
  },
  {
    id: 'cc-reglaj',
    family: 'cc',
    tier: 2,
    title: 'Motor c.c. — reglaj de turatie',
    subtitle: 'Turatie de baza si slabire de camp',
    note: 'Peste n_baza: slabire de camp (putere constanta). If din curba de magnetizare.',
    params: 'DCS880: EMF/field mode 28.17, turatie baza 99.14 · DCM: p50081/p50115',
    fields: [
      { key: 'nbaza', label: 'Turatie de baza', unit: 'rpm', default: 1500, step: 10, min: 1 },
      { key: 'ndorit', label: 'Turatie dorita', unit: 'rpm', default: 2200, step: 10, min: 1 },
      { key: 'Mnom', label: 'Cuplu nominal', unit: 'Nm', default: 200, step: 5, min: 0 },
    ],
    results: [
      { key: 'rcamp', label: 'Raport flux (Φ/Φn)', unit: '%', tex: '\\dfrac{\\Phi}{\\Phi_n} = \\dfrac{n_{baza}}{n}',
        calc: (v) => (v.ndorit ? Math.min(1, v.nbaza / v.ndorit) * 100 : null), dec: 1 },
      { key: 'Mdisp', label: 'Cuplu disponibil', unit: 'Nm', tex: 'M = M_n\\dfrac{n_{baza}}{n}',
        calc: (v) => (v.ndorit ? v.Mnom * Math.min(1, v.nbaza / v.ndorit) : null), dec: 1 },
      { key: 'Pconst', label: 'Putere (zona camp slabit)', unit: 'kW', tex: 'P = \\dfrac{M_n\\,n_{baza}}{9550}',
        calc: (v) => (v.Mnom * v.nbaza) / 9550, dec: 2 },
    ],
  },
  {
    id: 'cc-drive',
    family: 'cc',
    tier: 2,
    title: 'Convertor c.c. (DC drive)',
    subtitle: 'Redresor comandat, constante de timp',
    note: 'Punte trifazata complet comandata (B6), functionare in 4 cadrane.',
    params: 'DCS880 / Siemens DCM (redresor cu tiristoare)',
    fields: [
      { key: 'Ulinie', label: 'Tensiune retea', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'alpha', label: 'Unghi de aprindere', unit: '°', default: 20, step: 1, min: 0 },
      { key: 'La', label: 'Inductanta indus', unit: 'mH', default: 5, step: 0.5, min: 0 },
      { key: 'Ra', label: 'Rezistenta indus', unit: 'Ω', default: 0.15, step: 0.01, min: 0.0001 },
      { key: 'J', label: 'Inertie', unit: 'kg·m²', default: 2, step: 0.5, min: 0 },
      { key: 'kPhi', label: 'Constanta k·Φ', unit: 'V·s/rad', default: 2.6, step: 0.1, min: 0.01 },
    ],
    results: [
      { key: 'Ud0', label: 'Tensiune medie max', unit: 'V', tex: 'U_{d0} = 1.35\\,U_{linie}',
        calc: (v) => 1.35 * v.Ulinie, dec: 0 },
      { key: 'Ud', label: 'Tensiune medie indus', unit: 'V', tex: 'U_d = U_{d0}\\cos\\alpha',
        calc: (v, r) => r.Ud0 * Math.cos(rad(v.alpha)), dec: 1 },
      { key: 'taua', label: 'Constanta de timp electrica', unit: 'ms', tex: '\\tau_a = L_a/R_a',
        calc: (v) => (v.Ra ? v.La / v.Ra : null), dec: 1 },
      { key: 'taum', label: 'Constanta de timp mecanica', unit: 's', tex: '\\tau_m = \\dfrac{J R_a}{(k\\Phi)^2}',
        calc: (v) => (v.kPhi ? (v.J * v.Ra) / v.kPhi ** 2 : null), dec: 3 },
    ],
  },

  // =========================================================== SERVO / PMSM
  {
    id: 'pmsm-model',
    family: 'servo',
    tier: 2,
    title: 'Servo / PMSM — model de cuplu',
    subtitle: 'Cuplu, back-EMF, frecventa electrica',
    note: 'Kt din catalog (uzual Nm/A_rms). Kt[Nm/A] = Ke[V·s/rad].',
    charts: [(v) => {
      if (!v.n) return null
      const Mcont = v.Kt * v.Iq, Mpeak = 3 * Mcont, nb = v.n, nmax = v.n * 3
      const env = (Mflat) => curve(0, nmax, (n) => (n <= nb ? Mflat : (Mflat * nb) / n))
      return {
        xLabel: 'Turatie n [rpm]', yLabel: 'Cuplu M [Nm]',
        series: [{ label: 'Cuplu varf (≈3×)', color: COL.b, dash: true, points: env(Mpeak) }, { label: 'Cuplu continuu', color: COL.a, points: env(Mcont) }],
        markers: [{ x: nb, y: Mcont, label: 'nominal', color: COL.op }],
      }
    }],
    params: 'S120: tip motor p0300; Kt/Ke din date motor',
    fields: [
      { key: 'Kt', label: 'Constanta de cuplu', unit: 'Nm/A', default: 1.2, step: 0.1, min: 0 },
      { key: 'Iq', label: 'Curent de cuadratura', unit: 'A', default: 8, step: 0.5, min: 0 },
      { key: 'n', label: 'Turatie', unit: 'rpm', default: 3000, step: 50, min: 0 },
      { key: 'ppp', label: 'Perechi de poli', unit: '', default: 4, step: 1, min: 1 },
    ],
    results: [
      { key: 'M', label: 'Cuplu', unit: 'Nm', tex: 'M = K_t\\,I_q',
        calc: (v) => v.Kt * v.Iq, dec: 2 },
      { key: 'E', label: 'Back-EMF', unit: 'V', tex: 'E = K_e\\,\\omega,\\; K_e = K_t',
        calc: (v) => v.Kt * omega(v.n), dec: 1 },
      { key: 'fe', label: 'Frecventa electrica', unit: 'Hz', tex: 'f_e = \\dfrac{p_{pp}\\,n}{60}',
        calc: (v) => (v.ppp * v.n) / 60, dec: 1 },
      { key: 'P', label: 'Putere', unit: 'kW', tex: 'P = M\\,\\omega',
        calc: (v, r) => (r.M * omega(v.n)) / 1000, dec: 2 },
    ],
  },
  {
    id: 'pmsm-ciclu',
    family: 'servo',
    tier: 2,
    title: 'Servo — dimensionare pe ciclu',
    subtitle: 'Cuplu RMS si cuplu de varf',
    note: 'M_rms ≤ M_continuu(n); M_varf ≤ M_varf_motor(n).',
    fields: [
      { key: 'Macc', label: 'Cuplu accelerare', unit: 'Nm', default: 10, step: 0.5, min: 0 },
      { key: 'tacc', label: 'Timp accelerare', unit: 's', default: 0.2, step: 0.05, min: 0 },
      { key: 'Mconst', label: 'Cuplu constant', unit: 'Nm', default: 4, step: 0.5, min: 0 },
      { key: 'tconst', label: 'Timp constant', unit: 's', default: 1, step: 0.1, min: 0 },
      { key: 'Mdec', label: 'Cuplu decelerare', unit: 'Nm', default: 8, step: 0.5, min: 0 },
      { key: 'tdec', label: 'Timp decelerare', unit: 's', default: 0.2, step: 0.05, min: 0 },
      { key: 'tdwell', label: 'Timp pauza', unit: 's', default: 0.5, step: 0.1, min: 0 },
    ],
    results: [
      { key: 'tciclu', label: 'Timp ciclu', unit: 's', tex: 't_{ciclu} = \\sum t_i',
        calc: (v) => v.tacc + v.tconst + v.tdec + v.tdwell, dec: 2 },
      { key: 'Mrms', label: 'Cuplu RMS (termic)', unit: 'Nm', tex: 'M_{rms} = \\sqrt{\\dfrac{\\sum M_i^2 t_i}{\\sum t_i}}',
        calc: (v, r) => { const num = v.Macc ** 2 * v.tacc + v.Mconst ** 2 * v.tconst + v.Mdec ** 2 * v.tdec; return r.tciclu > 0 ? Math.sqrt(num / r.tciclu) : null }, dec: 2 },
      { key: 'Mvarf', label: 'Cuplu de varf', unit: 'Nm', tex: 'M_{varf} = \\max(M_i)',
        calc: (v) => Math.max(v.Macc, v.Mconst, v.Mdec), dec: 2 },
    ],
  },
  {
    id: 'pmsm-feedback',
    family: 'servo',
    tier: 2,
    title: 'Servo — feedback & dinamica',
    subtitle: 'Encoder, viteza, constante de timp',
    note: 'Cuadratura ×4 la encoder incremental.',
    fields: [
      { key: 'PPR', label: 'Impulsuri/rotatie', unit: 'PPR', default: 2500, step: 100, min: 1 },
      { key: 'imp', label: 'Impulsuri numarate', unit: '', default: 625, step: 1, min: 0 },
      { key: 't', label: 'Timp de masura', unit: 's', default: 0.01, step: 0.001, min: 0.0001 },
      { key: 'L', label: 'Inductanta', unit: 'mH', default: 8, step: 0.5, min: 0 },
      { key: 'R', label: 'Rezistenta', unit: 'Ω', default: 1.5, step: 0.1, min: 0.0001 },
      { key: 'J', label: 'Inertie', unit: 'kg·m²', default: 0.0005, step: 0.0001, min: 0 },
      { key: 'Kt', label: 'Constanta de cuplu', unit: 'Nm/A', default: 1.2, step: 0.1, min: 0.01 },
    ],
    results: [
      { key: 'pas', label: 'Rezolutie unghiulara', unit: '°', tex: '\\Delta\\theta = \\dfrac{360}{4\\,PPR}',
        calc: (v) => (v.PPR ? 360 / (4 * v.PPR) : null), dec: 4 },
      { key: 'nimp', label: 'Turatie din impulsuri', unit: 'rpm', tex: 'n = \\dfrac{60\\,imp}{4\\,PPR\\,t}',
        calc: (v) => { const d = 4 * v.PPR * v.t; return d ? (60 * v.imp) / d : null }, dec: 1 },
      { key: 'taue', label: 'Constanta de timp electrica', unit: 'ms', tex: '\\tau_e = L/R',
        calc: (v) => (v.R ? v.L / v.R : null), dec: 2 },
      { key: 'taum', label: 'Constanta de timp mecanica', unit: 'ms', tex: '\\tau_m = \\dfrac{J R}{K_t^2}',
        calc: (v) => (v.Kt ? (v.J * v.R) / v.Kt ** 2 * 1000 : null), dec: 2 },
    ],
  },

  // ================================================================ SINCRON
  {
    id: 'sincron-turatie',
    family: 'sincron',
    tier: 2,
    title: 'Motor sincron — turatie & excitatie',
    subtitle: 'Turatie sincrona, t.e.m. din excitatie',
    note: 'Alunecare zero (n = n_s). Reglaj FP prin excitatie (supraexcitat = capacitiv).',
    fields: [
      { key: 'f', label: 'Frecventa', unit: 'Hz', default: 50, step: 1, min: 0 },
      { key: 'p', label: 'Numar de poli', unit: '', default: 4, step: 2, min: 2 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'Ia', label: 'Curent indus', unit: 'A', default: 50, step: 1, min: 0 },
      { key: 'Xs', label: 'Reactanta sincrona', unit: 'Ω', default: 2.5, step: 0.1, min: 0 },
      { key: 'phi', label: 'Unghi factor de putere', unit: '°', default: 20, step: 1, min: 0 },
    ],
    results: [
      { key: 'ns', label: 'Turatie sincrona', unit: 'rpm', tex: 'n_s = \\dfrac{120\\,f}{p}',
        calc: (v) => (v.p ? (120 * v.f) / v.p : null), dec: 0 },
      { key: 'ws', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega_s = \\dfrac{2\\pi n_s}{60}',
        calc: (v, r) => (r.ns != null ? omega(r.ns) : null), dec: 2 },
      { key: 'E', label: 'T.e.m. indusa', unit: 'V', tex: 'E = \\sqrt{(U + I_a X_s\\sin\\varphi)^2 + (I_a X_s\\cos\\varphi)^2}',
        calc: (v) => { const a = v.U + v.Ia * v.Xs * Math.sin(rad(v.phi)); const b = v.Ia * v.Xs * Math.cos(rad(v.phi)); return Math.sqrt(a * a + b * b) }, dec: 1 },
    ],
  },
  {
    id: 'sincron-putere',
    family: 'sincron',
    tier: 2,
    title: 'Motor sincron — putere & cuplu',
    subtitle: 'Unghi de sarcina, cuplu de desprindere',
    note: 'U, E = tensiuni de linie. Stabil pentru δ < 90°; pull-out la δ = 90°.',
    charts: [(v) => {
      if (!v.Xs) return null
      const Pmax = (v.U * v.E) / v.Xs / 1000
      return {
        xLabel: 'Unghi de sarcina δ [°]', yLabel: 'Putere P [kW]',
        series: [{ label: 'P(δ) = U·E·sinδ / Xs', color: COL.a, points: curve(0, 180, (deg) => Pmax * Math.sin(rad(deg))) }],
        markers: [{ x: v.delta, y: Pmax * Math.sin(rad(v.delta)), label: 'δ curent', color: COL.op }],
      }
    }],
    fields: [
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'E', label: 'T.e.m. (excitatie)', unit: 'V', default: 420, step: 10, min: 0 },
      { key: 'Xs', label: 'Reactanta sincrona', unit: 'Ω', default: 2.5, step: 0.1, min: 0.01 },
      { key: 'delta', label: 'Unghi de sarcina', unit: '°', default: 30, step: 1, min: 0 },
      { key: 'ns', label: 'Turatie sincrona', unit: 'rpm', default: 1500, step: 10, min: 1 },
    ],
    results: [
      { key: 'ws', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega_s = \\dfrac{2\\pi n_s}{60}',
        calc: (v) => omega(v.ns), dec: 2 },
      { key: 'P', label: 'Putere electromagnetica', unit: 'kW', tex: 'P = \\dfrac{U E\\sin\\delta}{X_s}',
        calc: (v) => (v.Xs ? (v.U * v.E * Math.sin(rad(v.delta))) / v.Xs / 1000 : null), dec: 2 },
      { key: 'M', label: 'Cuplu', unit: 'Nm', tex: 'M = P/\\omega_s',
        calc: (v, r) => (r.ws ? (r.P * 1000) / r.ws : null), dec: 1 },
      { key: 'Mmax', label: 'Cuplu de desprindere', unit: 'Nm', tex: 'M_{max} = \\dfrac{U E}{X_s\\,\\omega_s}',
        calc: (v, r) => (v.Xs && r.ws ? (v.U * v.E) / v.Xs / r.ws : null), dec: 1 },
    ],
  },
]

// Familiile care au cel putin un modul (pentru tab-uri).
export function visibleFamilies() {
  return FAMILIES.filter((fam) => MODULES.some((m) => m.family === fam.id))
}

// Calculeaza toate rezultatele unui modul din valorile date.
export function computeModule(mod, rawValues) {
  const v = {}
  for (const f of mod.fields) {
    const num = Number(rawValues?.[f.key])
    v[f.key] = Number.isFinite(num) ? num : 0
  }
  const r = {}
  for (const res of mod.results) {
    let out = null
    try {
      out = res.calc(v, r)
    } catch (_) {
      out = null
    }
    r[res.key] = Number.isFinite(out) ? out : null
  }
  return r
}

// Construieste graficele unui modul din valorile date (returneaza [] daca nu are).
export function computeCharts(mod, rawValues) {
  if (!mod.charts) return []
  const v = {}
  for (const f of mod.fields) {
    const num = Number(rawValues?.[f.key])
    v[f.key] = Number.isFinite(num) ? num : 0
  }
  const out = []
  for (const builder of mod.charts) {
    try {
      const c = builder(v)
      if (c && (c.series || []).some((s) => (s.points || []).length > 1)) out.push(c)
    } catch (_) {
      // ignora graficul daca formula esueaza
    }
  }
  return out
}

// Formatare numerica in stil RO (mono in UI).
export function fmtNum(x, dec) {
  if (x == null || !Number.isFinite(x)) return '—'
  const a = Math.abs(x)
  let d = dec
  if (d == null) d = a >= 1000 ? 0 : a >= 100 ? 1 : a >= 10 ? 2 : 3
  return x.toLocaleString('ro-RO', { minimumFractionDigits: d, maximumFractionDigits: d })
}
