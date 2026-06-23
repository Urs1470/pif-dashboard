<script>
  import { tick } from 'svelte'
  import { Calculator as CalcIcon, Info, BookOpen, Maximize2, Search, X, ChevronRight, Star, Clock, Cpu, Link2, Download } from '@lucide/svelte'
  import { MODULES, MODULE_ORDER, SOURCES, CATEGORIES, MOTOR_FAMS, APPLICATIONS, APP_OF, catOf, docsForModule, symTeX, descLabel, computeModule, computeCharts, fmtNum } from '../lib/driveCalc.js'
  import Formula from '../components/ui/Formula.svelte'
  import MathText from '../components/ui/MathText.svelte'
  import Chart from '../components/ui/Chart.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import { lookupTerm } from '../lib/driveGlossary.js'
  import { runtime } from '../lib/runtime.svelte.js'

  let activeCat = $state('aplicatii')
  let activeMotorFam = $state('asincron')
  let activeApp = $state('pompe-vent')
  let query = $state('')

  // Valorile de intrare per modul, initializate din default-uri.
  let values = $state(
    Object.fromEntries(
      MODULES.map((m) => [m.id, Object.fromEntries(m.fields.map((f) => [f.key, f.default]))])
    )
  )

  const ord = (id) => { const i = MODULE_ORDER.indexOf(id); return i === -1 ? 999 : i }
  const catLabel = (id) => CATEGORIES.find((c) => c.id === id)?.label ?? id

  // Cautare in titlu / subtitlu / etichete & chei (campuri si rezultate).
  function matchQ(m, q) {
    if (m.title.toLowerCase().includes(q)) return true
    if (m.subtitle && m.subtitle.toLowerCase().includes(q)) return true
    for (const f of m.fields) if (f.label.toLowerCase().includes(q) || f.key.toLowerCase().includes(q)) return true
    for (const r of m.results) if (r.label.toLowerCase().includes(q) || r.key.toLowerCase().includes(q)) return true
    return false
  }
  // Lista din tab-ul curent (cautarea NU mai inlocuieste lista — vezi autocomplete-ul acResults).
  const shown = $derived.by(() => {
    if (activeCat === 'aplicatii') return MODULES.filter((m) => APP_OF[m.id] === activeApp).sort((a, b) => ord(a.id) - ord(b.id))
    if (activeCat === 'motoare') return MODULES.filter((m) => catOf(m) === 'motoare' && m.family === activeMotorFam).sort((a, b) => ord(a.id) - ord(b.id))
    return MODULES.filter((m) => catOf(m) === activeCat).sort((a, b) => ord(a.id) - ord(b.id))
  })
  // Autocomplete cautare: max 8 potriviri, doar de la 2 caractere.
  const acResults = $derived.by(() => {
    const q = query.trim().toLowerCase()
    if (q.length < 2) return []
    return MODULES.filter((m) => matchQ(m, q)).sort((a, b) => ord(a.id) - ord(b.id)).slice(0, 8)
  })

  // Segmenteaza un text in potriviri/nepotriviri pentru evidentiere la cautare.
  function highlightParts(text, q) {
    const needle = (q || '').trim()
    if (!needle) return [{ text, hit: false }]
    const parts = []; const low = text.toLowerCase(); const nl = needle.toLowerCase()
    let i = 0
    while (i < text.length) {
      const j = low.indexOf(nl, i)
      if (j === -1) { parts.push({ text: text.slice(i), hit: false }); break }
      if (j > i) parts.push({ text: text.slice(i, j), hit: false })
      parts.push({ text: text.slice(j, j + needle.length), hit: true })
      i = j + needle.length
    }
    return parts
  }
  function selectCat(id) { query = ''; activeCat = id }

  // Extrasele de carti (protected) au drept de autor -> vizibile cand esti logat (dashboard mereu;
  // pe /calc doar dupa verificarea autentificarii). runtime.docsOk e reactiv (vezi runtime.svelte.js).
  const docsFor = (m) => docsForModule(m).filter((d) => runtime.docsOk || !d.protected)

  function resetModule(m) {
    for (const f of m.fields) values[m.id][f.key] = f.default
    overrides = new Set([...overrides].filter((id) => !id.startsWith(m.id + ':')))
  }

  // Zoom grafic in modal (70%)
  let zoomOpen = $state(false)
  let zoomRef = $state(null)
  function openZoom(m, index) { zoomRef = { mod: m, index }; zoomOpen = true }
  const zoomChart = $derived(zoomRef ? computeCharts(zoomRef.mod, effVals(zoomRef.mod))[zoomRef.index] : null)

  // Definitie marime (glosar) la click pe eticheta
  let termOpen = $state(false)
  let term = $state(null)
  function openTerm(item, m, isResult) {
    term = {
      label: item.label,
      unit: item.unit,
      tex: isResult ? item.tex : null,
      g: lookupTerm(item.key, m.family),
      source: isResult ? (SOURCES[m.id] || null) : null,
      docs: docsFor(m),
    }
    termOpen = true
  }

  // ---- Acordeon: ce module sunt deschise (pe mobil doar unul) ----
  let expanded = $state(new Set())
  let isMobile = $state(false)
  $effect(() => {
    const mq = window.matchMedia('(max-width: 768px)')
    const upd = () => (isMobile = mq.matches)
    upd(); mq.addEventListener('change', upd)
    return () => mq.removeEventListener('change', upd)
  })
  function isOpen(id) { return expanded.has(id) }
  function toggle(id) {
    const open = expanded.has(id)
    let next
    if (isMobile) next = open ? new Set() : new Set([id])
    else { next = new Set(expanded); if (open) next.delete(id); else next.add(id) }
    if (!open) pushRecent(id)
    expanded = next
  }
  function openModule(id) {
    expanded = isMobile ? new Set([id]) : new Set(expanded).add(id)
    pushRecent(id)
  }

  // ---- Favorite + Recente (localStorage, partajat dashboard + /calc) ----
  function loadLS(k, def) { try { const v = JSON.parse(localStorage.getItem(k)); return Array.isArray(v) ? v : def } catch { return def } }
  let favorites = $state(loadLS('pif-calc-fav', []))
  let recents = $state(loadLS('pif-calc-recent', []))
  $effect(() => { try { localStorage.setItem('pif-calc-fav', JSON.stringify(favorites)) } catch {} })
  $effect(() => { try { localStorage.setItem('pif-calc-recent', JSON.stringify(recents)) } catch {} })
  function isFav(id) { return favorites.includes(id) }
  function toggleFav(id) { favorites = favorites.includes(id) ? favorites.filter((x) => x !== id) : [...favorites, id] }
  function pushRecent(id) { recents = [id, ...recents.filter((x) => x !== id)].slice(0, 5) }
  const byId = (id) => MODULES.find((m) => m.id === id)
  const favMods = $derived(favorites.map(byId).filter(Boolean))
  const recentMods = $derived(recents.map(byId).filter(Boolean))

  // ---- Navigare la un modul (din chip / autocomplete / prev-next) ----
  function locate(m) {
    const cat = catOf(m)
    activeCat = cat
    if (cat === 'aplicatii') activeApp = APP_OF[m.id]
    else if (cat === 'motoare') activeMotorFam = m.family
  }
  async function goTo(id) {
    const m = byId(id); if (!m) return
    locate(m); openModule(id)
    await tick()
    document.getElementById('acc-' + id)?.scrollIntoView({ block: 'start' })
  }
  function step(m, dir) {
    const i = shown.findIndex((x) => x.id === m.id)
    const t = shown[i + dir]; if (!t) return
    const next = new Set(isMobile ? [] : expanded)
    next.delete(m.id); next.add(t.id)
    expanded = next; pushRecent(t.id)
    tick().then(() => document.getElementById('acc-' + t.id)?.scrollIntoView({ block: 'start' }))
  }
  // ---- Surse & standarde (modal in-app) ----
  let surseOpen = $state(false)
  const SURSE = [
    { h: 'Standarde europene — IEC / EN / ISO (primare)', items: [
      'IEC/EN 60034-1 — masini rotative: regimuri S, derating, demaraj, dezechilibru',
      'IEC 60034-12 — caracteristici de pornire',
      'IEC/EN 60034-18-41 / -25 — izolatie & masina pe convertizor (dv/dt, unda reflectata, encoder)',
      'IEC/EN 60034-27-4 — rezistenta de izolatie & indice de polarizare (PI)',
      'IEC 60034-30-1 / -30-2 — clase de randament IE1-IE5',
      'IEC/EN 61800-2 / -3 / -5-1 / -5-2 — sisteme de actionare (nominale, EMC, siguranta STO/SS1)',
      'IEC 60364 — instalatii JT: ampacitate (-5-52), I²t (-5-54), legare la pamant TN/TT/IT',
      'IEC 61000-2-4 / -3-12 / -4-30 — armonici & calitatea energiei',
      'IEC 60909-0 — curenti de scurtcircuit',
      'IEC 60204-1 — echipament electric masini (categorii de stop) · IEC 60079-7 — Ex (timp tE)',
      'IEC 60076-1 Anexa E — factor K transformator',
      'EN ISO 9906 — incercari pompe (NPSH3) · EN 50160 — calitatea tensiunii (THD_U)',
      'EN 805 — regim tranzitoriu retele de apa (lovitura de berbec)',
    ] },
    { h: 'Echivalent US (citate ca referinta)', items: [
      'IEEE 43 (PI) · IEEE 112 (teste motor) · IEEE 141 (dip de pornire)',
      'IEEE 519 (armonici / TDD) · IEEE C57.110 (derating trafo)',
      'NEMA MG-1 (derating PWM, izolatie, porniri/ora, dezechilibru)',
      'CEMA Belt Book (transportoare) · Hydraulic Institute (pompe)',
    ] },
    { h: 'Carti de referinta (extras la /docs, cu login)', items: [
      'Chapman — Electric Machinery Fundamentals',
      'Mohan — Power Electronics',
      'Hughes — Electric Motors and Drives',
      'Nise — Control Systems Engineering',
      'Leonhard — Control of Electrical Drives · Fitzgerald — Electric Machinery (citate)',
    ] },
    { h: 'Ghiduri & producatori', items: [
      'ABB Technical Guide Book No.1-No.9 (gazduit public)',
      'ABB ACS580/880 (catalog, PID intern) · Siemens SINAMICS S120 / G120 (parametri)',
      'KSB Centrifugal Pump Lexicon · WEG (motoare pe PWM) · Danfoss / SEW (franare)',
    ] },
    { h: 'Resurse online', items: [
      'Wikipedia EN (26 articole de baza) · MathWorks (PMSM / IPMSM)',
      'EngineeringToolbox · Oriental Motor · Schneider EIG · NPTEL · Pumps & Systems',
    ] },
  ]

  // ---- Autocomplete cautare: navigare cu tastatura ----
  let acIndex = $state(-1)
  function acSelect(i) {
    const m = acResults[i] ?? acResults[0]; if (!m) return
    query = ''; acIndex = -1
    goTo(m.id)
  }
  function onSearchKey(e) {
    if (!acResults.length) return
    if (e.key === 'ArrowDown') { e.preventDefault(); acIndex = (acIndex + 1) % acResults.length }
    else if (e.key === 'ArrowUp') { e.preventDefault(); acIndex = (acIndex - 1 + acResults.length) % acResults.length }
    else if (e.key === 'Enter') { e.preventDefault(); acSelect(acIndex < 0 ? 0 : acIndex) }
    else if (e.key === 'Escape') { query = ''; acIndex = -1 }
  }

  // ============ DATE ECHIPAMENT — pe tip de masina (contextual) ============
  // Introduci placuta o data; cardurile cu acelasi camp (cheie + unitate, in grupul masinii sau retea)
  // folosesc valoarea partajata. Override local per camp. Import din backup-uri (doar logat).
  const EQUIP_GROUPS = {
    retea: [
      { key: 'U', label: 'Tensiune retea', unit: 'V', def: 400, fills: ['U', 'Un', 'Ulinie'] },
      { key: 'f', label: 'Frecventa', unit: 'Hz', def: 50, fills: ['f', 'fn', 'f1'] },
    ],
    asincron: [
      { key: 'Pn', label: 'Putere motor', unit: 'kW', def: 15, fills: ['Pn', 'P'] },
      { key: 'In', label: 'Curent nominal', unit: 'A', def: 28, fills: ['In'] },
      { key: 'n', label: 'Turatie', unit: 'rpm', def: 1450, fills: ['n', 'nbaza', 'nn'] },
      { key: 'cosphi', label: 'cos φ', unit: '', def: 0.85, fills: ['cosphi', 'cosphin'] },
      { key: 'eta', label: 'Randament', unit: '%', def: 90, fills: ['eta'] },
      { key: 'poli', label: 'Poli', unit: '', def: 4, fills: ['p'] },
    ],
    cc: [
      { key: 'Ua', label: 'Tensiune indus', unit: 'V', def: 440, fills: ['U'] },
      { key: 'Ia', label: 'Curent indus', unit: 'A', def: 80, fills: ['Ia'] },
      { key: 'Ra', label: 'Rezistenta indus', unit: 'Ω', def: 0.15, fills: ['Ra'] },
      { key: 'kPhi', label: 'Constanta masinii', unit: 'V·s/rad', def: 2.6, fills: ['kPhi'] },
      { key: 'n', label: 'Turatie', unit: 'rpm', def: 1500, fills: ['nbaza', 'ndorit'] },
    ],
    servo: [
      { key: 'ppp', label: 'Perechi de poli', unit: '', def: 4, fills: ['ppp'] },
      { key: 'Kt', label: 'Constanta cuplu', unit: 'Nm/A', def: 1.2, fills: ['Kt'] },
      { key: 'Iq', label: 'Curent cuadratura', unit: 'A', def: 8, fills: ['Iq'] },
      { key: 'psim', label: 'Flux magneti', unit: 'Wb', def: 0.1, fills: ['psim'] },
      { key: 'Lq', label: 'Inductanta', unit: 'mH', def: 8, fills: ['Lq', 'Ld'] },
    ],
    sincron: [
      { key: 'Xs', label: 'Reactanta sincrona', unit: 'Ω', def: 2.5, fills: ['Xs'] },
      { key: 'E', label: 'T.e.m. excitatie', unit: 'V', def: 420, fills: ['E'] },
      { key: 'ns', label: 'Turatie sincrona', unit: 'rpm', def: 1500, fills: ['ns'] },
    ],
    transformator: [
      { key: 'Strafo', label: 'Putere trafo', unit: 'kVA', def: 630, fills: ['Strafo'] },
      { key: 'uk', label: 'uk trafo', unit: '%', def: 6, fills: ['uk'] },
      { key: 'cosphi', label: 'cos φ', unit: '', def: 0.85, fills: ['cosphi'] },
    ],
  }
  const MACHINE_GROUPS = ['asincron', 'cc', 'servo', 'sincron', 'transformator']
  const _F2S = {}
  for (const g in EQUIP_GROUPS) { _F2S[g] = {}; for (const c of EQUIP_GROUPS[g]) for (const fk of c.fills) (_F2S[g][fk] = _F2S[g][fk] || []).push(c) }
  function freshEquip() { const o = {}; for (const g in EQUIP_GROUPS) o[g] = Object.fromEntries(EQUIP_GROUPS[g].map((c) => [c.key, c.def])); return o }
  const groupLabel = (g) => (g === 'retea' ? 'Retea' : (MOTOR_FAMS.find((f) => f.id === g)?.label ?? g))
  function groupForModule(m) { return MACHINE_GROUPS.includes(m.family) ? m.family : 'asincron' }
  function loadObj(k) { try { const v = JSON.parse(localStorage.getItem(k)); return v && typeof v === 'object' && !Array.isArray(v) ? v : null } catch { return null } }
  function loadEquipData() {
    const fresh = freshEquip()
    const nested = loadObj('pif-calc-equip-data')
    if (nested) { for (const g in fresh) Object.assign(fresh[g], nested[g] || {}); return fresh }
    const old = loadObj('pif-calc-shared')
    if (old) {
      const r = fresh.retea, a = fresh.asincron, t = fresh.transformator
      if (old.U != null) r.U = old.U; if (old.fn != null) r.f = old.fn
      if (old.P != null) a.Pn = old.P; if (old.In != null) a.In = old.In; if (old.n != null) a.n = old.n
      if (old.cosphi != null) a.cosphi = old.cosphi; if (old.eta != null) a.eta = old.eta; if (old.poli != null) a.poli = old.poli
      if (old.Strafo != null) t.Strafo = old.Strafo; if (old.uk != null) t.uk = old.uk
    }
    return fresh
  }

  let sharedOn = $state(true)
  let panelOpen = $state(true)
  let equip = $state(loadEquipData())
  let overrides = $state(new Set())
  let equipments = $state(loadLS('pif-calc-equip', []))
  let equipName = $state('')
  let exportMsg = $state('')
  $effect(() => { try { localStorage.setItem('pif-calc-equip-data', JSON.stringify(equip)) } catch {} })
  $effect(() => { try { localStorage.setItem('pif-calc-equip', JSON.stringify(equipments)) } catch {} })

  // grupul activ pt PANOU (condus de navigare); pe sistem/aplicatii = asincron (motorul condus)
  const activeGroup = $derived(activeCat === 'motoare' ? activeMotorFam : activeCat === 'utilitare' ? null : 'asincron')
  const panelGroups = $derived(activeGroup ? ['retea', activeGroup] : ['retea'])

  // conceptul partajat pt un camp: grupul masinii intai (cheie + UNITATE), apoi retea
  function conceptFor(m, f) {
    if (!sharedOn) return null
    const u = f.unit ?? ''
    const g = groupForModule(m)
    const inG = (_F2S[g]?.[f.key] || []).find((c) => c.unit === u)
    if (inG) return { group: g, concept: inG }
    const inR = (_F2S.retea[f.key] || []).find((c) => c.unit === u)
    return inR ? { group: 'retea', concept: inR } : null
  }
  const ov = (m, f) => overrides.has(m.id + ':' + f.key)
  function isLinked(m, f) { const s = conceptFor(m, f); return !!(s && !ov(m, f)) }
  function fieldVal(m, f) { const s = conceptFor(m, f); return s && !ov(m, f) ? equip[s.group][s.concept.key] : values[m.id][f.key] }
  function setFieldVal(m, f, raw) {
    const val = raw === '' ? '' : +raw
    const s = conceptFor(m, f)
    if (s && !ov(m, f)) equip[s.group][s.concept.key] = val
    else values[m.id][f.key] = val
  }
  function toggleLink(m, f) {
    const id = m.id + ':' + f.key, next = new Set(overrides)
    if (next.has(id)) next.delete(id)
    else { const s = conceptFor(m, f); if (s) values[m.id][f.key] = equip[s.group][s.concept.key]; next.add(id) }
    overrides = next
  }
  function effVals(m) {
    const v = { ...values[m.id] }
    if (sharedOn) for (const f of m.fields) { const s = conceptFor(m, f); if (s && !ov(m, f)) v[f.key] = equip[s.group][s.concept.key] }
    return v
  }

  // echipamente salvate (intregul equip = toate masinile dintr-un job)
  function mergeEquip(saved) { const base = freshEquip(); for (const g in base) Object.assign(base[g], saved?.[g] || {}); return base }
  function saveEquip() {
    const name = (equipName || '').trim() || ('Echipament ' + (equipments.length + 1))
    equipments = [...equipments.filter((e) => e.name !== name), { name, data: JSON.parse(JSON.stringify(equip)) }]
    equipName = ''
  }
  function loadEquip(e) { equip = mergeEquip(e.data); overrides = new Set() }
  function delEquip(e) { equipments = equipments.filter((x) => x.name !== e.name) }
  function resetShared() { equip = freshEquip(); overrides = new Set() }

  // export rezultate (cardurile deschise) pentru raportul PIF
  function exportResults() {
    const work = shown.filter((m) => expanded.has(m.id))
    const list = work.length ? work : shown
    const L = ['# Rezultate calculator actionari electrice', '', '## Date echipament']
    for (const g of ['retea', ...MACHINE_GROUPS]) {
      L.push(`### ${groupLabel(g)}`)
      for (const c of EQUIP_GROUPS[g]) L.push(`- ${c.label}: ${equip[g][c.key]}${c.unit ? ' ' + c.unit : ''}`)
    }
    L.push('')
    for (const m of list) {
      const ev = effVals(m), r = computeModule(m, ev)
      L.push('## ' + m.title)
      for (const f of m.fields) L.push(`  ${descLabel(f.label, f.key)}: ${ev[f.key]}${f.unit ? ' ' + f.unit : ''}`)
      for (const res of m.results) L.push(`- ${res.label} = ${fmtNum(r[res.key], res.dec)}${res.unit ? ' ' + res.unit : ''}`)
      L.push('')
    }
    const text = L.join('\n')
    try { navigator.clipboard.writeText(text); exportMsg = `Copiat in clipboard (${list.length} ${list.length === 1 ? 'card' : 'carduri'}).` }
    catch { exportMsg = 'Nu am putut copia automat.' }
    setTimeout(() => (exportMsg = ''), 3500)
  }

  // ============ Sub-anteturi de sectiune (taburi de sistem) ============
  const SECTIONS = {
    vfd: [
      { label: 'Convertizor', ids: ['selectie-drive', 'vfd', 'comutatie'] },
      { label: 'Iesire & cablu', ids: ['unda-reflectata', 'filtru-iesire', 'curenti-rulment'] },
      { label: 'Franare & energie', ids: ['franare-rezistenta', 'ride-through', 'kinetic-buffer'] },
      { label: 'Siguranta', ids: ['sto-ss1', 'sil-pl'] },
      { label: 'Motor pe VFD', ids: ['derating-vfd-motor'] },
    ],
    armonici: [
      { label: 'Generare & factor de putere', ids: ['armonici', 'factor-putere-vfd', 'comparatie-frontend'] },
      { label: 'Limite la racord', ids: ['ieee519'] },
      { label: 'Mitigare', ids: ['rezonanta-cond', 'reactor-detunare'] },
    ],
    instalatie: [
      { label: 'Cablu & tensiune', ids: ['cablu', 'cablu-protectii', 'dip-pornire'] },
      { label: 'Scurtcircuit', ids: ['scurtcircuit'] },
      { label: 'Izolatie & EMC', ids: ['izolatie', 'retea-emc'] },
    ],
    termic: [
      { label: 'Model termic motor', ids: ['motor-termic', 'porniri-ora', 'regimuri-s'] },
      { label: 'Eficienta', ids: ['clase-ie'] },
      { label: 'Derating & energie', ids: ['derating-armonici-motor', 'energie-roi', 'termic'] },
    ],
  }
  const rows = $derived.by(() => {
    const secs = SECTIONS[activeCat]
    if (!secs) return shown.map((m) => ({ kind: 'mod', m }))
    const byId = new Map(shown.map((m) => [m.id, m]))
    const out = []; const placed = new Set()
    for (const s of secs) {
      const mods = s.ids.map((id) => byId.get(id)).filter(Boolean)
      if (!mods.length) continue
      out.push({ kind: 'head', label: s.label, key: 'sec:' + s.label })
      for (const m of mods) { out.push({ kind: 'mod', m }); placed.add(m.id) }
    }
    const rest = shown.filter((m) => !placed.has(m.id))
    if (rest.length) { out.push({ kind: 'head', label: 'Altele', key: 'sec:Altele' }); for (const m of rest) out.push({ kind: 'mod', m }) }
    return out
  })

  // ============ Import din backup-uri drive (doar autentificat in dashboard) ============
  // coduri reale de placuta verificate pe backup-uri: ABB grup 99 (Drive Composer .dcparamsbak),
  // Siemens p03xx (STARTER), Danfoss 1-xx. ABB nu are eta/poli ca parametru direct.
  const NAMEPLATE_CODES = {
    ABB: { Pn: '99.10', U: '99.07', n: '99.09', In: '99.06', cosphi: '99.11', f: '99.08' },
    Siemens: { Pn: 'p0307', U: 'p0304', In: 'p0305', cosphi: 'p0308', eta: 'p0309', n: 'p0311', poli: 'p0314', f: 'p0310' },
    Danfoss: { Pn: '1-20', U: '1-22', f: '1-23', In: '1-24', n: '1-25', poli: '1-39' },
  }
  let authed = $state(false)
  let importOpen = $state(false)
  let importTab = $state('proiect')
  let importMsg = $state('')
  let importBusy = $state(false)
  let projList = $state([])
  let selProj = $state('')
  let equipList = $state([])
  let importDrives = $state([])
  $effect(() => {
    fetch('/api/me', { credentials: 'same-origin' }).then((r) => (r.ok ? r.json() : null)).then((d) => { authed = !!(d && d.authenticated) }).catch(() => {})
  })
  function csrfHeader() {
    const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
    return m ? { 'X-CSRF-Token': decodeURIComponent(m[1]) } : {}
  }
  function applyImport(producator, params) {
    const map = NAMEPLATE_CODES[producator] || NAMEPLATE_CODES.ABB
    let n = 0
    // valoarea poate fi "220 kW" (ABB) sau "400" (Siemens) -> scoate numarul; sare valorile <=0 (nesetate)
    const num = (v) => { const x = parseFloat(String(v).replace(',', '.')); return Number.isFinite(x) ? x : null }
    const set = (g, k, code) => { if (!code) return; const x = num(params[code]); if (x != null && x > 0) { equip[g][k] = x; n++ } }
    set('retea', 'U', map.U); set('retea', 'f', map.f)
    set('asincron', 'Pn', map.Pn); set('asincron', 'In', map.In); set('asincron', 'n', map.n)
    set('asincron', 'cosphi', map.cosphi); set('asincron', 'eta', map.eta); set('asincron', 'poli', map.poli)
    overrides = new Set()
    importMsg = n ? `Importat ${n} valori in grupul Asincron (verifica poli/cosphi).` : 'Nu am gasit date de placuta in acest backup.'
    if (n) { importDrives = []; setTimeout(() => (importOpen = false), 1300) }
  }
  async function openImport() {
    importOpen = true; importMsg = ''; importDrives = []
    if (!projList.length) {
      try { const r = await fetch('/api/proiecte', { credentials: 'same-origin' }); if (r.ok) { const d = await r.json(); projList = Array.isArray(d) ? d : (d.proiecte || d.items || []) } } catch {}
    }
  }
  async function onSelProj() {
    equipList = []; if (!selProj) return
    try { const r = await fetch(`/api/proiecte/${selProj}/echipamente`, { credentials: 'same-origin' }); if (r.ok) equipList = await r.json() } catch {}
  }
  function pickEquip(eq) {
    let p = eq.params_json; if (typeof p === 'string') { try { p = JSON.parse(p) } catch { p = {} } }
    applyImport(eq.producator || 'ABB', p || {})
  }
  async function onBackupFile(e) {
    const files = e.target.files; if (!files || !files.length) return
    importBusy = true; importMsg = 'Se incarca...'; importDrives = []
    const isZip = /\.zip$/i.test(files[0].name)
    const fd = new FormData()
    if (isZip) fd.append('file', files[0]); else for (const f of files) fd.append('files', f)
    const url = isZip ? '/api/import-archive/preview' : '/api/import-abb-multi/preview'
    try {
      const r = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: csrfHeader(), body: fd })
      if (!r.ok) { importMsg = 'Eroare ' + r.status + ' (esti logat in dashboard?).'; importBusy = false; e.target.value = ''; return }
      const d = await r.json(); const drives = d.drives || []
      if (!drives.length) importMsg = 'Backup fara date de placuta.'
      else if (drives.length === 1) applyImport(drives[0].producator, drives[0].params || {})
      else importDrives = drives
    } catch { importMsg = 'Nu am putut citi backup-ul.' }
    importBusy = false; e.target.value = ''
  }
</script>

<div class="page">
  <div class="page-head">
    <div class="head-row">
      <CalcIcon size={26} />
      <h1>Calculator actionari electrice</h1>
      <button class="surse-btn" onclick={() => (surseOpen = true)}><BookOpen size={15} /> Surse &amp; standarde</button>
    </div>
    <p class="sub">Marimi inginerești pentru motoare si convertizoare — valori orientative, verifica intotdeauna catalogul/manualul.</p>
  </div>

  <div class="equip-panel">
    <div class="equip-head">
      <button class="equip-toggle" onclick={() => (panelOpen = !panelOpen)} title="Introdu placuta o data — toate cardurile se completeaza">
        <span class="equip-chev" class:open={panelOpen}><ChevronRight size={15} /></span>
        <Cpu size={16} /> <b>Date echipament</b>
      </button>
      <label class="equip-switch" title="Cardurile folosesc datele partajate de mai jos">
        <input type="checkbox" bind:checked={sharedOn} /> partajat
      </label>
      <div class="equip-actions">
        {#if authed}<button onclick={openImport} title="Import din backup-uri drive (ABB/Siemens) sau din proiect">Import</button>{/if}
        <input class="equip-name" placeholder="nume echipament" bind:value={equipName} />
        <button onclick={saveEquip}>Salveaza</button>
        <button class="exp-btn" onclick={exportResults} title="Copiaza rezultatele cardurilor deschise (pentru raport)"><Download size={13} /> Export</button>
        <button onclick={resetShared} title="Reseteaza datele la implicit">Reset</button>
      </div>
    </div>
    {#if panelOpen}
      {#each panelGroups as g (g)}
        <div class="equip-group">
          <span class="equip-group-h">{groupLabel(g)}</span>
          <div class="equip-grid">
            {#each EQUIP_GROUPS[g] as c (c.key)}
              <div class="equip-field">
                <label>{c.label}{c.unit ? ` [${c.unit}]` : ''}</label>
                <input type="number" step="any" bind:value={equip[g][c.key]} disabled={!sharedOn} />
              </div>
            {/each}
          </div>
        </div>
      {/each}
      {#if equipments.length}
        <div class="equip-chips">
          <span class="equip-chips-h">Salvate:</span>
          {#each equipments as e (e.name)}
            <span class="equip-chip"><button onclick={() => loadEquip(e)}>{e.name}</button><button class="chip-x" title="Sterge" onclick={() => delEquip(e)}>×</button></span>
          {/each}
        </div>
      {/if}
      {#if exportMsg}<p class="equip-msg">{exportMsg}</p>{/if}
    {/if}
  </div>

  <div class="search-wrap">
    <div class="search-row">
      <span class="search-ic"><Search size={16} /></span>
      <input class="search-inp" type="search" autocomplete="off"
        placeholder="Cauta un calcul — titlu, simbol sau marime (ex. NPSH, cuplu, U_dc)..."
        bind:value={query} onkeydown={onSearchKey} />
      {#if query}<button class="search-clear" title="Sterge cautarea" onclick={() => { query = ''; acIndex = -1 }}><X size={15} /></button>{/if}
    </div>
    {#if acResults.length}
      <ul class="ac-list" role="listbox">
        {#each acResults as m, i (m.id)}
          <li>
            <button class="ac-item" class:active={i === acIndex} role="option" aria-selected={i === acIndex}
              onmouseenter={() => (acIndex = i)} onclick={() => acSelect(i)}>
              <span class="ac-title">{#each highlightParts(m.title, query) as p}{#if p.hit}<mark>{p.text}</mark>{:else}{p.text}{/if}{/each}{#if m.subtitle}<span class="ac-sub"> — <MathText text={m.subtitle} /></span>{/if}</span>
              <span class="cat-badge">{catLabel(catOf(m))}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  <div class="fam-tabs" role="tablist">
    {#each CATEGORIES as c}
      <button class="fam-tab" class:active={activeCat === c.id} role="tab" aria-selected={activeCat === c.id} onclick={() => selectCat(c.id)}>{c.label}</button>
    {/each}
  </div>
  {#if activeCat === 'motoare'}
    <div class="subfam-tabs" role="tablist">
      {#each MOTOR_FAMS as f}
        <button class="subfam-tab" class:active={activeMotorFam === f.id} role="tab" aria-selected={activeMotorFam === f.id} onclick={() => (activeMotorFam = f.id)}>{f.label}</button>
      {/each}
    </div>
  {:else if activeCat === 'aplicatii'}
    <div class="subfam-tabs" role="tablist">
      {#each APPLICATIONS as a}
        <button class="subfam-tab" class:active={activeApp === a.id} role="tab" aria-selected={activeApp === a.id} onclick={() => (activeApp = a.id)}>{a.label}</button>
      {/each}
    </div>
  {/if}

  {#if favMods.length || recentMods.length}
    <div class="quick-rows">
      {#if favMods.length}
        <div class="quick-row">
          <span class="quick-h"><Star size={13} /> Favorite</span>
          {#each favMods as m (m.id)}<button class="chip" onclick={() => goTo(m.id)}>{m.title}</button>{/each}
        </div>
      {/if}
      {#if recentMods.length}
        <div class="quick-row">
          <span class="quick-h"><Clock size={13} /> Recente</span>
          {#each recentMods as m (m.id)}<button class="chip" onclick={() => goTo(m.id)}>{m.title}</button>{/each}
        </div>
      {/if}
    </div>
  {/if}

  <div class="acc-list">
    {#each rows as row (row.kind === 'head' ? row.key : row.m.id)}
      {#if row.kind === 'head'}
        <div class="acc-section-head">{row.label}</div>
      {:else}
      {@const m = row.m}
      {@const open = isOpen(m.id)}
      <div class="acc-item" id={'acc-' + m.id} class:open>
        <div class="acc-head" role="button" tabindex="0"
          onclick={() => toggle(m.id)}
          onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(m.id) } }}>
          <span class="acc-chev" class:open><ChevronRight size={16} /></span>
          <span class="acc-title">{m.title}{#if m.subtitle}<span class="acc-sub"><MathText text={m.subtitle} /></span>{/if}</span>
          <button class="star-btn" class:on={isFav(m.id)} title="Adauga la favorite" aria-label="Favorit"
            onclick={(e) => { e.stopPropagation(); toggleFav(m.id) }}><Star size={15} /></button>
        </div>

        {#if open}
          {@const ev = effVals(m)}
          {@const r = computeModule(m, ev)}
          {@const charts = computeCharts(m, ev)}
          <div class="acc-body">
            <div class="acc-body-head">
              <span class="cat-badge">{catLabel(catOf(m))}</span>
              <button class="reset-btn" title="Reseteaza valorile" onclick={() => resetModule(m)}>Reset</button>
            </div>

            {#if m.fields.length}
              <div class="inputs">
                {#each m.fields as f (f.key)}
                  {@const linked = isLinked(m, f)}
                  <div class="inp">
                    <button type="button" class="inp-label" title="Definitie / de unde se ia" onclick={() => openTerm(f, m, false)}><Formula tex={symTeX(f.key)} inline /> {f.unit ? `[${f.unit}] ` : ''}{descLabel(f.label, f.key)}</button>
                    <div class="inp-row">
                      <input class="inp-field" type="number" step={f.step ?? 'any'} min={f.min}
                        value={fieldVal(m, f)} oninput={(e) => setFieldVal(m, f, e.target.value)} />
                      {#if conceptFor(m, f)}
                        <button class="link-btn" class:on={linked} title={linked ? 'Legat de datele echipamentului — click pentru valoare locala' : 'Valoare locala — click pentru a lega'} onclick={() => toggleLink(m, f)}><Link2 size={12} /></button>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}

            {#if m.results.length}
              <div class="results">
                {#each m.results as res (res.key)}
                  <div class="res-row">
                    <div class="res-head">
                      <button type="button" class="res-label" title="Definitie / cum se calculeaza" onclick={() => openTerm(res, m, true)}><MathText text={res.label} /></button>
                      <span class="res-right">
                        <span class="res-val">{fmtNum(r[res.key], res.dec)}</span>
                        {#if res.unit}<span class="res-unit">{res.unit}</span>{/if}
                      </span>
                    </div>
                    <Formula tex={res.tex} />
                  </div>
                {/each}
              </div>
            {/if}

            {#if charts.length}
              <div class="charts">
                {#each charts as chart, ci}
                  <div class="chart-zoom" role="button" tabindex="0" title="Click pentru marire"
                    onclick={() => openZoom(m, ci)}
                    onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openZoom(m, ci) } }}>
                    <Chart {chart} />
                    <span class="zoom-hint"><Maximize2 size={14} /></span>
                  </div>
                {/each}
              </div>
            {/if}

            {#if m.note}<p class="mod-note"><Info size={13} /><span class="note-body"><MathText text={m.note} /></span></p>{/if}
            {#if m.params}<p class="mod-params"><MathText text={m.params} /></p>{/if}
            {#if SOURCES[m.id]}<p class="mod-source"><BookOpen size={11} /><span class="note-body"><MathText text={SOURCES[m.id]} /></span></p>{/if}
            {#if docsFor(m).length}
              <div class="mod-docs">
                <span class="docs-h">Documentatie:</span>
                {#each docsFor(m) as d}<a class="doc-link" href={d.href} target="_blank" rel="noopener">{d.label}</a>{/each}
              </div>
            {/if}

            <div class="acc-nav">
              <button class="nav-btn" disabled={shown[0]?.id === m.id} onclick={() => step(m, -1)}>‹ Anterior</button>
              <button class="nav-btn" disabled={shown[shown.length - 1]?.id === m.id} onclick={() => step(m, 1)}>Urmator ›</button>
            </div>
          </div>
        {/if}
      </div>
      {/if}
    {/each}
    <p class="acc-status">{shown.length} {shown.length === 1 ? 'modul' : 'module'} • {[...expanded].filter((id) => shown.some((m) => m.id === id)).length} deschise</p>
  </div>

  <Modal bind:open={zoomOpen} title={zoomRef ? zoomRef.mod.title : ''} size="zoom">
    {#if zoomChart}
      <div class="zoom-body"><Chart chart={zoomChart} /></div>
    {/if}
  </Modal>

  <Modal bind:open={termOpen} title={term ? term.label : ''} size="md">
    {#if term}
      <div class="term">
        {#if term.unit}<div class="term-unit">Unitate: <b>{term.unit}</b></div>{/if}
        {#if term.tex}
          <div class="term-sec"><span class="term-h">Cum se calculeaza</span><Formula tex={term.tex} display /></div>
        {/if}
        {#if term.g?.def}<div class="term-sec"><span class="term-h">Definitie</span><p><MathText text={term.g.def} /></p></div>{/if}
        {#if term.g?.ia}<div class="term-sec"><span class="term-h">De unde se ia</span><p><MathText text={term.g.ia} /></p></div>{/if}
        {#if term.g?.practic}<div class="term-sec"><span class="term-h">In practica</span><p><MathText text={term.g.practic} /></p></div>{/if}
        {#if term.g?.teorie}<div class="term-sec"><span class="term-h">Principiu / teorie</span><p><MathText text={term.g.teorie} /></p></div>{/if}
        {#if term.source}<div class="term-sec"><span class="term-h">Sursa</span><p class="term-src"><MathText text={term.source} /></p></div>{/if}
        {#if term.docs?.length}
          <div class="term-sec"><span class="term-h">Documentatie</span>
            <div class="term-docs">
              {#each term.docs as d}
                <a class="doc-link" href={d.href} target="_blank" rel="noopener">{d.label}</a>
              {/each}
            </div>
          </div>
        {/if}
        {#if !term.g && !term.tex}<p class="term-empty">Marime fara definitie detaliata inca. Vezi sursa modulului si formulele asociate.</p>{/if}
      </div>
    {/if}
  </Modal>

  <Modal bind:open={surseOpen} title="Surse & standarde" size="lg">
    <div class="surse">
      <p class="surse-intro">Notatie & standarde primare = <b>europene (IEC / EN / ISO)</b>; cele americane (IEEE / NEMA) doar ca echivalent. Fiecare card isi afiseaza sursa proprie. Standardele sunt documente cu plata — citate ca text, nu gazduite. Cartile au extrase (doar paginile citate) la <b>/docs</b> cu login.</p>
      {#each SURSE as g}
        <div class="surse-sec">
          <h3>{g.h}</h3>
          <ul>{#each g.items as it}<li>{it}</li>{/each}</ul>
        </div>
      {/each}
    </div>
  </Modal>

  <Modal bind:open={importOpen} title="Import date echipament" size="md">
    <div class="imp">
      <div class="imp-tabs">
        <button class:active={importTab === 'proiect'} onclick={() => (importTab = 'proiect')}>Din proiect</button>
        <button class:active={importTab === 'fisier'} onclick={() => (importTab = 'fisier')}>Incarca backup</button>
      </div>
      {#if importTab === 'proiect'}
        <div class="imp-row">
          <label for="imp-proj">Proiect</label>
          <select id="imp-proj" bind:value={selProj} onchange={onSelProj}>
            <option value="">— alege proiect —</option>
            {#each projList as p (p.id)}<option value={p.id}>{p.nume || p.titlu || p.id}</option>{/each}
          </select>
        </div>
        {#if equipList.length}
          <div class="imp-equip">
            {#each equipList as eq (eq.id)}
              <button class="imp-eq" onclick={() => pickEquip(eq)}>{eq.nume || eq.model || 'Echipament'}<span>{eq.producator || ''} {eq.model || ''}</span></button>
            {/each}
          </div>
        {:else if selProj}<p class="imp-hint">Niciun echipament cu parametri in acest proiect.</p>{/if}
      {:else}
        <p class="imp-hint">Incarca un backup de drive: ABB <code>.dcparamsbak</code> (poti selecta mai multe) sau Siemens STARTER <code>.zip</code>.</p>
        <input type="file" accept=".dcparamsbak,.zip" multiple onchange={onBackupFile} disabled={importBusy} />
        {#if importDrives.length}
          <p class="imp-hint">Mai multe drive-uri — alege:</p>
          <div class="imp-equip">
            {#each importDrives as dr, i (i)}
              <button class="imp-eq" onclick={() => applyImport(dr.producator, dr.params || {})}>{dr.nume || 'Drive'}<span>{dr.producator || ''} {dr.model || ''}</span></button>
            {/each}
          </div>
        {/if}
      {/if}
      {#if importMsg}<p class="imp-msg">{importMsg}</p>{/if}
      <p class="imp-note">Umple grupul <b>Asincron</b> + <b>Retea</b> din datele de placuta ale motorului (cod producator: ABB 30.xx, Siemens p03xx, Danfoss 1-xx).</p>
    </div>
  </Modal>
</div>

<style>
  .page { padding: var(--space-lg); }

  .page-head {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: var(--space-lg);
  }
  .head-row {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    color: var(--text);
  }
  .head-row h1 { font-size: var(--font-h1); font-weight: 700; }
  .sub {
    font-size: var(--font-small);
    color: var(--text-dim);
    margin-top: 2px;
    max-width: 70ch;
  }
  .surse-btn {
    margin-left: auto;
    display: inline-flex; align-items: center; gap: 6px;
    font-size: var(--font-tiny); font-weight: 600; color: var(--text-secondary);
    padding: 6px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm);
    background: var(--bg-surface); cursor: pointer; transition: all var(--dur-fast) var(--ease);
  }
  .surse-btn:hover { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }
  .surse { display: flex; flex-direction: column; gap: var(--space-md); }
  .surse-intro { font-size: var(--font-small); color: var(--text-dim); line-height: 1.5; }
  .surse-sec h3 { font-size: var(--font-small); font-weight: 700; color: var(--accent); margin-bottom: 4px; }
  .surse-sec ul { list-style: none; display: flex; flex-direction: column; gap: 3px; }
  .surse-sec li { font-size: var(--font-tiny); color: var(--text-secondary); line-height: 1.45; padding-left: 12px; position: relative; }
  .surse-sec li::before { content: '·'; position: absolute; left: 2px; color: var(--text-dim); }

  /* === Date echipament partajate === */
  .equip-panel { border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--bg-surface); margin-bottom: var(--space-md); padding: 10px 12px; }
  .equip-head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
  .equip-toggle { display: inline-flex; align-items: center; gap: 7px; font-size: var(--font-small); color: var(--text); cursor: pointer; }
  .equip-chev { display: flex; color: var(--text-dim); transition: transform var(--dur-fast) var(--ease); }
  .equip-chev.open { transform: rotate(90deg); color: var(--accent); }
  .equip-switch { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-tiny); color: var(--text-secondary); cursor: pointer; }
  .equip-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-left: auto; }
  .equip-actions button {
    font-size: var(--font-tiny); font-weight: 600; color: var(--text-secondary);
    padding: 5px 10px; border: 1px solid var(--border); border-radius: var(--radius-sm);
    background: var(--bg-elevated); cursor: pointer; display: inline-flex; align-items: center; gap: 4px;
    transition: all var(--dur-fast) var(--ease);
  }
  .equip-actions button:hover { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }
  .equip-name { font-size: var(--font-tiny); padding: 5px 9px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-elevated); color: var(--text); width: 130px; }
  .equip-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(118px, 1fr)); gap: 8px; margin-top: 10px; }
  .equip-field { display: flex; flex-direction: column; gap: 3px; }
  .equip-field label { font-size: var(--font-tiny); color: var(--text-dim); }
  .equip-field input { padding: 7px 9px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-elevated); color: var(--text); font-size: var(--font-small); font-weight: 600; }
  .equip-field input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }
  .equip-field input:disabled { opacity: 0.45; }
  .equip-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 10px; }
  .equip-chips-h { font-size: var(--font-tiny); color: var(--text-dim); }
  .equip-chip { display: inline-flex; align-items: center; border: 1px solid var(--border); border-radius: 999px; overflow: hidden; }
  .equip-chip > button { font-size: var(--font-tiny); padding: 3px 10px; color: var(--text-secondary); cursor: pointer; background: var(--bg-surface); }
  .equip-chip > button:hover { background: var(--accent-subtle); color: var(--accent); }
  .equip-chip .chip-x { padding: 3px 8px; color: var(--text-dim); border-left: 1px solid var(--border); }
  .equip-msg { font-size: var(--font-tiny); color: var(--accent); margin-top: 8px; }
  /* input cu buton de legare la datele partajate */
  .inp-row { display: flex; align-items: stretch; gap: 4px; margin-top: auto; }
  .inp-row .inp-field { flex: 1; min-width: 0; margin-top: 0; }
  .link-btn { display: flex; align-items: center; justify-content: center; width: 28px; flex-shrink: 0; border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-dim); cursor: pointer; background: var(--bg-surface); }
  .link-btn.on { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .link-btn:hover { color: var(--text); border-color: var(--text-dim); }
  .equip-group { margin-top: 10px; }
  .equip-group-h { display: block; font-size: var(--font-tiny); font-weight: 700; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }

  /* sub-antet de sectiune in accordion */
  .acc-section-head { font-size: var(--font-tiny); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim); padding: 12px 2px 3px; }

  /* modal import */
  .imp { display: flex; flex-direction: column; gap: var(--space-sm); }
  .imp-tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
  .imp-tabs button { font-size: var(--font-small); font-weight: 600; color: var(--text-secondary); padding: 5px 12px; border-radius: var(--radius-sm); cursor: pointer; }
  .imp-tabs button.active { background: var(--accent-subtle); color: var(--accent); }
  .imp-row { display: flex; align-items: center; gap: 8px; }
  .imp-row label { font-size: var(--font-small); color: var(--text-dim); }
  .imp-row select { flex: 1; padding: 7px 9px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-elevated); color: var(--text); font-size: var(--font-small); }
  .imp-equip { display: flex; flex-direction: column; gap: 6px; max-height: 240px; overflow: auto; }
  .imp-eq { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; text-align: left; padding: 8px 11px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text); font-size: var(--font-small); font-weight: 600; cursor: pointer; }
  .imp-eq:hover { background: var(--accent-subtle); border-color: var(--accent); }
  .imp-eq span { font-size: var(--font-tiny); font-weight: 400; color: var(--text-dim); }
  .imp input[type=file] { font-size: var(--font-small); color: var(--text-secondary); }
  .imp-hint { font-size: var(--font-tiny); color: var(--text-dim); }
  .imp-hint code { font-family: var(--font-mono); background: var(--bg-hover); padding: 0 4px; border-radius: 3px; }
  .imp-msg { font-size: var(--font-small); color: var(--accent); font-weight: 600; }
  .imp-note { font-size: var(--font-tiny); color: var(--text-dim); border-top: 1px dashed var(--border); padding-top: 8px; }

  .fam-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    margin-bottom: var(--space-lg);
    border-bottom: 1px solid var(--border);
    padding-bottom: var(--space-sm);
  }
  .fam-tab {
    padding: 6px 14px;
    border-radius: var(--radius-sm);
    font-size: var(--font-small);
    font-weight: 600;
    color: var(--text-secondary);
    transition: all var(--dur-fast) var(--ease);
    cursor: pointer;
  }
  .fam-tab:hover { background: var(--bg-hover); color: var(--text); }
  .fam-tab.active { background: var(--accent-subtle); color: var(--accent); }

  /* sub-taburi pentru Motoare (pe tip) */
  .subfam-tabs { display: flex; flex-wrap: wrap; gap: var(--space-xs); margin: calc(-1 * var(--space-md)) 0 var(--space-lg); }
  .subfam-tab {
    padding: 4px 13px; border-radius: 999px; font-size: var(--font-tiny); font-weight: 600;
    color: var(--text-dim); border: 1px solid var(--border); background: var(--bg-surface);
    cursor: pointer; transition: all var(--dur-fast) var(--ease);
  }
  .subfam-tab:hover { color: var(--text); border-color: var(--text-dim); }
  .subfam-tab.active { background: var(--accent); color: var(--accent-text); border-color: var(--accent); }

  /* caseta de cautare */
  .search-row { position: relative; display: flex; align-items: center; margin-bottom: var(--space-md); }
  .search-ic { position: absolute; left: 12px; display: flex; color: var(--text-dim); pointer-events: none; }
  .search-inp {
    width: 100%; padding: 9px 38px; border: 1px solid var(--border); border-radius: var(--radius-md);
    background: var(--bg-elevated); color: var(--text); font-size: var(--font-body);
  }
  .search-inp:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }
  .search-clear { position: absolute; right: 8px; display: flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; }
  .search-clear:hover { background: var(--bg-hover); color: var(--text); }
  .cat-badge { display: inline-block; margin-top: 4px; width: fit-content; font-size: var(--font-tiny); color: var(--text-dim); background: var(--bg-hover); border-radius: 999px; padding: 1px 9px; }

  /* === Acordeon === */
  .acc-list { display: flex; flex-direction: column; gap: 8px; }
  .acc-item {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    transition: border-color var(--dur-fast) var(--ease);
    scroll-margin-top: 16px; /* la navigare cardul incepe de sus, cu putin spatiu */
  }
  .acc-item.open { border-color: var(--accent); }
  .acc-head {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 14px; cursor: pointer; user-select: none;
    transition: background var(--dur-fast) var(--ease);
  }
  .acc-head:hover { background: var(--bg-hover); }
  .acc-chev { display: flex; flex-shrink: 0; color: var(--text-dim); transition: transform var(--dur-fast) var(--ease); }
  .acc-chev.open { transform: rotate(90deg); color: var(--accent); }
  .acc-title {
    flex: 1; min-width: 0; display: flex; align-items: baseline; gap: 8px;
    font-size: var(--font-body); font-weight: 700; color: var(--text);
  }
  .acc-sub { font-size: var(--font-tiny); font-weight: 400; color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .star-btn { display: flex; flex-shrink: 0; padding: 4px; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; }
  .star-btn:hover { background: var(--bg-hover); color: var(--text); }
  .star-btn.on { color: var(--warning); }
  .star-btn.on :global(svg) { fill: var(--warning); }
  .acc-body {
    padding: var(--space-md); border-top: 1px solid var(--border);
    display: flex; flex-direction: column; gap: var(--space-md); min-width: 0;
  }
  .acc-body-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); }
  .acc-nav { display: flex; justify-content: space-between; gap: var(--space-sm); border-top: 1px dashed var(--border); padding-top: var(--space-sm); }
  .nav-btn {
    font-size: var(--font-tiny); font-weight: 600; color: var(--text-secondary);
    padding: 5px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm);
    background: var(--bg-surface); cursor: pointer; transition: all var(--dur-fast) var(--ease);
  }
  .nav-btn:hover:not(:disabled) { background: var(--bg-hover); color: var(--text); border-color: var(--text-dim); }
  .nav-btn:disabled { opacity: 0.4; cursor: default; }
  .acc-status { text-align: center; font-size: var(--font-tiny); color: var(--text-dim); padding-top: var(--space-sm); }

  /* === Autocomplete cautare === */
  .search-wrap { position: relative; margin-bottom: var(--space-md); }
  .search-wrap .search-row { margin-bottom: 0; }
  .ac-list {
    position: absolute; z-index: 30; top: calc(100% + 4px); left: 0; right: 0;
    background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25); padding: 4px;
  }
  .ac-item {
    display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%;
    padding: 8px 10px; border-radius: var(--radius-sm); cursor: pointer; text-align: left;
  }
  .ac-item.active { background: var(--accent-subtle); }
  .ac-title { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--font-small); color: var(--text); }
  .ac-sub { color: var(--text-dim); }
  .ac-item .cat-badge { margin-top: 0; flex-shrink: 0; }
  .ac-title :global(mark) { background: var(--accent-subtle); color: var(--accent); border-radius: 3px; padding: 0 2px; }

  /* === Favorite / Recente === */
  .quick-rows { display: flex; flex-direction: column; gap: 6px; margin-bottom: var(--space-md); }
  .quick-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .quick-h { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-tiny); font-weight: 700; color: var(--text-dim); margin-right: 2px; }
  .chip {
    font-size: var(--font-tiny); font-weight: 600; color: var(--text-secondary);
    padding: 3px 11px; border-radius: 999px; border: 1px solid var(--border); background: var(--bg-surface);
    cursor: pointer; transition: all var(--dur-fast) var(--ease);
  }
  .chip:hover { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }
  .reset-btn {
    font-size: var(--font-tiny);
    color: var(--text-dim);
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
    transition: all var(--dur-fast) var(--ease);
    cursor: pointer;
  }
  .reset-btn:hover { background: var(--bg-hover); color: var(--text); }

  .inputs {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: var(--space-sm);
  }
  .inp { display: flex; flex-direction: column; gap: 4px; }
  .inp-label {
    font-size: var(--font-tiny);
    font-weight: 500;
    color: var(--text-secondary);
    line-height: 1.2;
    min-height: 2.2em;
    overflow-wrap: anywhere;
    text-align: left;
    background: none;
    border: none;
    padding: 0;
    width: 100%;
    cursor: help;
    transition: color var(--dur-fast) var(--ease);
  }
  .inp-label:hover { color: var(--text); text-decoration: underline dotted; }
  /* titlul = un singur link uniform: simbol, [u.m.], text — acelasi font si culoare */
  .inp-field {
    margin-top: auto;
    padding: 8px 10px;
    min-height: 40px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-family: var(--font-mono);
    font-size: var(--font-body);
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .inp-field:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-subtle);
  }

  .results {
    display: flex;
    flex-direction: column;
    border-top: 1px solid var(--border);
  }
  .res-row {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: var(--space-sm) 0;
    border-bottom: 1px solid var(--border);
  }
  .res-row:last-child { border-bottom: none; }
  .res-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-md);
  }
  .res-label {
    font-size: var(--font-small);
    color: var(--text);
    background: none;
    border: none;
    padding: 0;
    text-align: left;
    cursor: help;
    transition: color var(--dur-fast) var(--ease);
  }
  .res-label:hover { color: var(--accent); text-decoration: underline dotted; }
  .res-right {
    display: flex;
    align-items: baseline;
    gap: 4px;
    flex-shrink: 0;
    white-space: nowrap;
  }
  .res-val {
    font-family: var(--font-mono);
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--accent);
  }
  .res-unit { font-size: var(--font-tiny); color: var(--text-dim); }

  .mod-note {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    font-size: var(--font-tiny);
    color: var(--text-dim);
  }
  /* iconul ramane fix sus; textul + formulele KaTeX curg ca un paragraf normal in note-body */
  .mod-note > :global(svg),
  .mod-source > :global(svg) {
    flex-shrink: 0;
    margin-top: 2px;
  }
  .note-body {
    flex: 1;
    min-width: 0;
    line-height: 1.45;
  }
  .mod-params {
    font-family: var(--font-mono);
    font-size: var(--font-tiny);
    color: var(--text-dim);
    border-top: 1px dashed var(--border);
    padding-top: var(--space-sm);
  }
  .mod-source {
    display: flex;
    align-items: flex-start;
    gap: 5px;
    font-size: var(--font-tiny);
    color: var(--text-dim);
    font-style: italic;
  }
  .mod-docs {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
  }
  .docs-h { font-size: var(--font-tiny); color: var(--text-dim); }
  .doc-link {
    display: inline-flex;
    align-items: center;
    font-size: var(--font-tiny);
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    background: var(--bg-hover);
    border: 1px solid var(--border);
    color: var(--accent);
    text-decoration: none;
    line-height: 1.4;
  }
  .doc-link:hover { background: var(--bg-surface); border-color: var(--accent); }
  .term-docs { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; }

  .charts { display: flex; flex-wrap: wrap; gap: var(--space-md); }
  .chart-zoom {
    position: relative;
    cursor: zoom-in;
    border-radius: var(--radius-sm);
    transition: background var(--dur-fast) var(--ease);
    flex: 1 1 360px;     /* 2 grafice stau alaturat; unul singur nu se intinde peste */
    max-width: 560px;
  }
  .chart-zoom:hover { background: var(--bg-hover); }
  .chart-zoom:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--accent-subtle);
  }
  .zoom-hint {
    position: absolute;
    top: 4px;
    right: 4px;
    color: var(--text-dim);
    opacity: 0;
    transition: opacity var(--dur-fast) var(--ease);
    pointer-events: none;
  }
  .chart-zoom:hover .zoom-hint { opacity: 0.8; }
  .zoom-body { padding: var(--space-xs); }

  .term { display: flex; flex-direction: column; gap: var(--space-md); }
  .term-unit { font-size: var(--font-small); color: var(--text-secondary); }
  .term-unit b { font-family: var(--font-mono); color: var(--text); }
  .term-sec { display: flex; flex-direction: column; gap: 4px; }
  .term-h {
    font-size: var(--font-tiny);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--accent);
  }
  .term-sec p { font-size: var(--font-body); color: var(--text); line-height: 1.5; }
  .term-src { font-family: var(--font-mono); font-size: var(--font-tiny) !important; color: var(--text-dim) !important; }
  .term-empty { font-size: var(--font-small); color: var(--text-dim); }

  @media (max-width: 768px) {
    .acc-sub { display: none; }
    .acc-head { padding: 10px 12px; gap: 8px; }
  }
</style>
