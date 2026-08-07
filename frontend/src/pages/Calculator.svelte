<script>
  import { tick } from 'svelte'
  import { ecran } from '../lib/ecran.svelte.js'
  import { slide, fade } from 'svelte/transition'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../lib/motion.svelte.js'
  import { Info, BookOpen, Maximize2, Search, X, ChevronRight, Star, Link2, Download, FolderPlus, Trash2 } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import { MODULES, MODULE_ORDER, SOURCES, CATEGORIES, MOTOR_FAMS, APPLICATIONS, APP_OF, catOf, docsForModule, symTeX, descLabel, computeModule, computeCharts, fmtNum, FIG_LINKS, MODULE_FIG, LIMITS, computeVerdicts, worstVerdict, INTREBARI, ghidCalculator } from '../lib/driveCalc.js'
  import Formula from '../components/ui/Formula.svelte'
  import MathText from '../components/ui/MathText.svelte'
  import Chart from '../components/ui/Chart.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import Select from '../components/ui/Select.svelte'
  import { lookupTerm } from '../lib/driveGlossary.js'
  import { runtime } from '../lib/runtime.svelte.js'

  // standalone=true pe aplicatia publica /calc (impartita cu colegii): ascunde tot ce tine de
  // proiectele mele private (import "Din proiect" etc.). In dashboard (logat) ramane disponibil.
  let { standalone = false } = $props()

  let activeCat = $state('aplicatii')
  let activeMotorFam = $state('asincron')
  let activeApp = $state('pompe-vent')
  let intrebareSel = $state(null)
  let query = $state('')

  // Valorile de intrare per modul, initializate din default-uri.
  let values = $state(
    Object.fromEntries(
      MODULES.map((m) => [m.id, Object.fromEntries(m.fields.map((f) => [f.key, f.default]))])
    )
  )

  const ord = (id) => { const i = MODULE_ORDER.indexOf(id); return i === -1 ? 999 : i }
  const catLabel = (id) => CATEGORIES.find((c) => c.id === id)?.label ?? id

  // Normalizare insensibila la diacritice (1:1 pe caracter => pastreaza lungimea/indicii,
  // ca sa nu strice evidentierea din highlightParts). Foloseste-o pe AMBELE parti ale cautarii.
  const _DIAC = { 'ă':'a','â':'a','î':'i','ș':'s','ț':'t','Ă':'a','Â':'a','Î':'i','Ș':'s','Ț':'t','ş':'s','ţ':'t','Ş':'s','Ţ':'t' }
  const fold = (s) => (s || '').replace(/[ăâîșțĂÂÎȘȚşţŞŢ]/g, (c) => _DIAC[c] || c).toLowerCase()

  // Cautare in titlu / subtitlu / etichete & chei (campuri si rezultate) — insensibila la diacritice.
  function matchQ(m, q) {
    if (fold(m.title).includes(q)) return true
    if (m.subtitle && fold(m.subtitle).includes(q)) return true
    for (const f of m.fields) if (fold(f.label).includes(q) || fold(f.key).includes(q)) return true
    for (const r of m.results) if (fold(r.label).includes(q) || fold(r.key).includes(q)) return true
    return false
  }
  // Lista din tab-ul curent (cautarea NU mai inlocuieste lista — vezi autocomplete-ul acResults).
  const shown = $derived.by(() => {
    // Intrarea pe sarcina: lista e cea a intrebarii alese, in ORDINEA din tabel
    // (ordinea in care deschizi cardurile), nu in ordinea generala a modulelor.
    if (activeCat === 'intrebari') {
      const q = INTREBARI.find((x) => x.id === intrebareSel)
      return q ? q.module.map((id) => MODULES.find((m) => m.id === id)).filter(Boolean) : []
    }
    if (activeCat === 'aplicatii') return MODULES.filter((m) => APP_OF[m.id] === activeApp).sort((a, b) => ord(a.id) - ord(b.id))
    if (activeCat === 'motoare') return MODULES.filter((m) => catOf(m) === 'motoare' && m.family === activeMotorFam).sort((a, b) => ord(a.id) - ord(b.id))
    return MODULES.filter((m) => catOf(m) === activeCat).sort((a, b) => ord(a.id) - ord(b.id))
  })
  // Autocomplete cautare: max 8 potriviri, doar de la 2 caractere.
  const acResults = $derived.by(() => {
    const q = fold(query.trim())
    if (q.length < 2) return []
    return MODULES.filter((m) => matchQ(m, q)).sort((a, b) => ord(a.id) - ord(b.id)).slice(0, 8)
  })

  // Segmenteaza un text in potriviri/nepotriviri pentru evidentiere la cautare.
  function highlightParts(text, q) {
    const needle = (q || '').trim()
    if (!needle) return [{ text, hit: false }]
    const parts = []; const low = fold(text); const nl = fold(needle)
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
  function selectCat(id) { query = ''; activeCat = id; if (id !== 'intrebari') intrebareSel = null }
  function alegeIntrebare(id) { intrebareSel = id; openModule(INTREBARI.find((x) => x.id === id)?.module[0]) }

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
      figLink: FIG_LINKS[item.key] || MODULE_FIG[m.id] || null,
    }
    termOpen = true
  }

  // ---- Acordeon (viewport ingust) + navigator V2 (desktop >=940px) ----
  let expanded = $state(new Set())
  // Ambele praguri vin din lib/ecran.svelte.js, citite deja la incarcarea modulului
  // — deci si aici raman „eager": primul paint pe desktop nu mai arata o clipa
  // acordeonul de telefon.
  const isMobile = $derived(ecran.telefon)
  const isDesktop = $derived(ecran.larg)
  // Desktop: un singur modul ACTIV, ales din navigatorul din stanga; fallback = primul din categorie.
  let activeId = $state(null)
  const activeMod = $derived.by(() => shown.find((x) => x.id === activeId) ?? shown[0] ?? null)
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
    activeId = id
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
    if (isDesktop) document.getElementById('nav-' + id)?.scrollIntoView({ block: 'nearest' })
    else document.getElementById('acc-' + id)?.scrollIntoView({ block: 'start' })
  }
  function step(m, dir) {
    const i = shown.findIndex((x) => x.id === m.id)
    const t = shown[i + dir]; if (!t) return
    if (isDesktop) {
      openModule(t.id)
      tick().then(() => document.getElementById('nav-' + t.id)?.scrollIntoView({ block: 'nearest' }))
      return
    }
    const next = new Set(isMobile ? [] : expanded)
    next.delete(m.id); next.add(t.id)
    expanded = next; pushRecent(t.id)
    tick().then(() => document.getElementById('acc-' + t.id)?.scrollIntoView({ block: 'start' }))
  }
  // ---- Surse & standarde (modal in-app) ----
  let surseOpen = $state(false)
  // Ghidul e o FUNCTIE, nu un text fix: cifrele din el (cate module, cate praguri,
  // cate intrebari) se citesc din driveCalc la fiecare deschidere, ca sa nu ramana
  // in urma aplicatiei. Vezi ghidCalculator() pentru regula de intretinere.
  let ghidOpen = $state(false)
  const ghid = $derived(ghidCalculator())
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
      { key: 'Pn', label: 'Putere motor', unit: 'kW', def: 15, fills: ['Pn', 'P'], sec: 'Placuta' },
      { key: 'In', label: 'Curent nominal', unit: 'A', def: 28, fills: ['In'], sec: 'Placuta' },
      { key: 'n', label: 'Turatie', unit: 'rpm', def: 1450, fills: ['n', 'nbaza', 'nn'], sec: 'Placuta' },
      { key: 'cosphi', label: 'cos φ', unit: '', def: 0.85, fills: ['cosphi', 'cosphin'], sec: 'Placuta' },
      { key: 'eta', label: 'Randament', unit: '%', def: 90, fills: ['eta'], sec: 'Placuta' },
      { key: 'poli', label: 'Poli', unit: '', def: 4, fills: ['p'], sec: 'Placuta' },
      // date extinse importabile din backup-uri drive (unitatile trebuie IDENTICE cu cele din driveCalc.js)
      { key: 'nmax', label: 'Turatie maxima', unit: 'rpm', def: 3000, fills: ['nmax'], sec: 'Date drive' },
      { key: 'tdec', label: 'Timp decelerare', unit: 's', def: 5, fills: ['tdec'], sec: 'Date drive' },
      { key: 'fsw', label: 'Frecventa comutatie', unit: 'kHz', def: 4, fills: ['fsw'], sec: 'Date drive' },
      { key: 'R1', label: 'Rezistenta stator', unit: 'Ω', def: 0.5, fills: ['R1'], sec: 'Date drive' },
      { key: 'J', label: 'Inertie', unit: 'kg·m²', def: 2, fills: ['J', 'Jmot'], sec: 'Date drive' },
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
  // imparte conceptele unui grup pe sub-sectiuni (ex. Placuta / Date drive la asincron); fara `sec` -> o sectiune fara titlu
  function sectionsFor(g) {
    const out = []
    for (const c of EQUIP_GROUPS[g]) {
      const lbl = c.sec || ''
      let s = out.find((x) => x.label === lbl)
      if (!s) { s = { label: lbl, items: [] }; out.push(s) }
      s.items.push(c)
    }
    return out
  }
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

  // rezumat compact pt navigatorul V2 (primele 3 marimi ale grupului activ, ex. "15 kW · 28 A · 1450 rpm")
  const equipSummary = $derived.by(() => {
    const g = activeGroup || 'asincron'
    return EQUIP_GROUPS[g].slice(0, 3).map((c) => `${equip[g][c.key]}${c.unit ? ' ' + c.unit : ''}`).join(' · ')
  })
  // panoul "Date echipament" exista doar pe tabul Motoare -> de pe alt tab, click = du-te acolo si deschide-l
  function openEquipPanel() {
    if (activeCat === 'motoare') panelOpen = !panelOpen
    else { selectCat('motoare'); panelOpen = true }
  }

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

  // ---- Verdicte (vezi LIMITS din driveCalc.js) ----
  // Starea unui card = cel mai grav verdict al rezultatelor lui. Se calculeaza
  // doar pentru modulele care AU praguri definite; restul raman fara bulina —
  // "fara verdict" inseamna "pragul inca nu e scris", nu "totul e in regula",
  // si de aia nu punem verde pe ele.
  function verdictsFor(m) {
    if (!LIMITS[m.id]) return {}
    const ev = effVals(m)
    return computeVerdicts(m, ev, computeModule(m, ev))
  }
  // Starea per modul din lista curenta, recalculata cand se schimba valorile.
  const stariModule = $derived.by(() => {
    const out = new Map()
    for (const m of shown) {
      if (!LIMITS[m.id]) continue
      const st = worstVerdict(verdictsFor(m))
      if (st) out.set(m.id, st)
    }
    return out
  })
  const VERDICT_TITLU = { ok: 'În limite', atentie: 'De verificat', critic: 'În afara limitelor' }

  // ---- Ataseaza calculul la un proiect ----
  // Calculul era efemer: il faceai pe teren, apoi il retastai in debrief si in PV.
  // Se trimite ce s-a vazut pe ecran (intrari + rezultate + verdicte), serverul
  // nu recalculeaza nimic — e o consemnare, nu o formula vie (vezi migratia v37).
  let attachOpen = $state(false)
  let attachMod = $state(null)
  let attachProiecte = $state([])
  let attachProiectId = $state('')
  let attachTitlu = $state('')
  let attachNota = $state('')
  let attachBusy = $state(false)
  let attachMsg = $state('')

  async function openAttach(m) {
    attachMod = m
    attachTitlu = m.title
    attachNota = ''
    attachMsg = ''
    attachOpen = true
    if (!attachProiecte.length) {
      try {
        const lista = await apiJson('/api/proiecte?limit=500')
        attachProiecte = (Array.isArray(lista) ? lista : lista.proiecte || [])
          .filter((p) => p.status !== 'finalizat')
          .concat((Array.isArray(lista) ? lista : lista.proiecte || []).filter((p) => p.status === 'finalizat'))
        if (!attachProiectId && attachProiecte.length) attachProiectId = attachProiecte[0].id
      } catch (e) {
        attachMsg = 'Nu am putut incarca lista de proiecte: ' + e.message
      }
    }
  }

  async function saveAttach() {
    if (!attachMod || !attachProiectId) return
    attachBusy = true
    attachMsg = ''
    try {
      const ev = effVals(attachMod)
      const r = computeModule(attachMod, ev)
      const vd = LIMITS[attachMod.id] ? computeVerdicts(attachMod, ev, r) : {}
      // Etichetele intra in payload: peste un an, "dUproc: 1.93" nu spune nimic
      // singur, iar cheile se pot redenumi.
      const intrari = {}
      for (const f of attachMod.fields) intrari[f.key] = { eticheta: descLabel(f.label, f.key), valoare: ev[f.key], um: f.unit || '' }
      const rezultate = {}
      for (const res of attachMod.results) rezultate[res.key] = { eticheta: res.label, valoare: r[res.key], um: res.unit || '' }
      await apiJson(`/api/proiecte/${attachProiectId}/calcule`, {
        method: 'POST',
        body: {
          titlu: attachTitlu.trim() || attachMod.title,
          modul_id: attachMod.id,
          modul_titlu: attachMod.title,
          intrari, rezultate, verdicte: vd,
          stare: worstVerdict(vd) || '',
          nota: attachNota.trim(),
        },
      })
      attachMsg = 'Salvat la proiect.'
      setTimeout(() => { attachOpen = false; attachMsg = '' }, 1200)
    } catch (e) {
      attachMsg = 'Nu am putut salva: ' + e.message
    } finally {
      attachBusy = false
    }
  }

  // export rezultate (cardurile deschise) pentru raportul PIF
  function exportResults() {
    const work = shown.filter((m) => expanded.has(m.id))
    const list = work.length ? work : shown
    const L = ['# Rezultate calculator acționări electrice', '', '## Date echipament']
    for (const g of ['retea', ...MACHINE_GROUPS]) {
      L.push(`### ${groupLabel(g)}`)
      for (const c of EQUIP_GROUPS[g]) L.push(`- ${c.label}: ${equip[g][c.key]}${c.unit ? ' ' + c.unit : ''}`)
    }
    L.push('')
    const SEMN = { ok: 'OK', atentie: 'ATENTIE', critic: 'IN AFARA LIMITELOR' }
    for (const m of list) {
      const ev = effVals(m), r = computeModule(m, ev)
      const vd = LIMITS[m.id] ? computeVerdicts(m, ev, r) : {}
      L.push('## ' + m.title)
      for (const f of m.fields) L.push(`  ${descLabel(f.label, f.key)}: ${ev[f.key]}${f.unit ? ' ' + f.unit : ''}`)
      for (const res of m.results) {
        L.push(`- ${res.label} = ${fmtNum(r[res.key], res.dec)}${res.unit ? ' ' + res.unit : ''}`)
        // Verdictul intra in raport langa valoare: PV-ul are nevoie de concluzie,
        // nu doar de cifra.
        const v = vd[res.key]
        if (v) L.push(`  [${SEMN[v.st]}] ${v.de}${v.src ? ` (${v.src})` : ''}`)
      }
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
      { label: 'Control', ids: ['moduri-control', 'control-vf', 'modulatie-busdc', 'ripple-pwm'] },
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
      { label: 'Protectii', ids: ['protectie-motor', 'pe-defect'] },
      { label: 'Izolatie & EMC', ids: ['izolatie', 'retea-emc'] },
    ],
    termic: [
      { label: 'Model termic motor', ids: ['motor-termic', 'porniri-ora', 'regimuri-s', 'viata-termica-s10'] },
      { label: 'Eficienta', ids: ['clase-ie'] },
      { label: 'Derating & energie', ids: ['derating-armonici-motor', 'energie-roi', 'lcc', 'termic'] },
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

  // ============ Import din backup-uri drive ============
  // "Incarca backup" e PUBLIC (merge si pe /calc, fara login - util pt colegi); "Din proiect" cere login.
  // coduri reale de placuta verificate pe backup-uri: ABB grup 99 (Drive Composer .dcparamsbak),
  // Siemens p03xx (STARTER), Danfoss 1-xx. ABB nu are eta/poli ca parametru direct.
  // nameplate = grup 99 ABB / p030x Siemens / 1-2x Danfoss; date extinse: rampa/turatie max/comutatie/Rs/inertie
  const NAMEPLATE_CODES = {
    ABB: { Pn: '99.10', U: '99.07', n: '99.09', In: '99.06', cosphi: '99.11', f: '99.08', nmax: '30.12', tdec: '23.13' },
    Siemens: { Pn: 'p0307', U: 'p0304', In: 'p0305', cosphi: 'p0308', eta: 'p0309', n: 'p0311', poli: 'p0314', f: 'p0310', nmax: 'p1082', tdec: 'p1121', fsw: 'p1800', R1: 'p0350', J: 'p0341' },
    Danfoss: { Pn: '1-20', U: '1-22', f: '1-23', In: '1-24', n: '1-25', poli: '1-39' },
  }
  let authed = $state(false)
  let importOpen = $state(false)
  let importMsg = $state('')
  let importBusy = $state(false)
  let importDrives = $state([])
  $effect(() => {
    fetch('/api/me', { credentials: 'same-origin' }).then((r) => (r.ok ? r.json() : null)).then((d) => { authed = !!(d && d.authenticated) }).catch(() => {})
  })
  function csrfHeader() {
    const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
    return m ? { 'X-CSRF-Token': decodeURIComponent(m[1]) } : {}
  }
  // valoarea poate fi "220 kW" (ABB) sau "400" (Siemens) -> scoate numarul
  const _num = (v) => { const x = parseFloat(String(v).replace(',', '.')); return Number.isFinite(x) ? x : null }
  const TYPE_LABEL = { asincron: 'asincron', cc: 'c.c.', servo: 'servo / PMSM', sincron: 'sincron' }
  // tipul masinii din backup (ca sa nu importi un drive c.c. pe tabul asincron)
  function backupType(producator, params, model) {
    if (/dcs|simoreg|6ra/i.test(model || '')) return 'cc'
    if (producator === 'ABB') {
      const mt = String((params || {})['99.03'] || '').toLowerCase()
      if (mt.includes('permanent')) return 'servo'
      if (mt.includes('reluctance') || (mt.includes('synchronous') && !mt.includes('asynchronous'))) return 'sincron'
      return 'asincron'
    }
    if (producator === 'Siemens') {
      const mt = String((params || {})['p0300'] || '')
      if (parseInt(mt) === 2 || parseInt(mt) === 5 || /perman|sync/i.test(mt)) return 'servo'
      return 'asincron'
    }
    return 'asincron'
  }
  function drivePreview(producator, params) {
    const map = NAMEPLATE_CODES[producator] || NAMEPLATE_CODES.ABB
    const g = (code) => { const x = _num((params || {})[code]); return x != null && x > 0 ? x : null }
    const bits = []; const P = g(map.Pn), U = g(map.U), I = g(map.In)
    if (P) bits.push(P + ' kW'); if (U) bits.push(U + ' V'); if (I) bits.push(I + ' A')
    return bits.join(' · ')
  }
  function applyImport(producator, params, model) {
    // pe un tab de masina non-asincron: importul aduce date de motor asincron -> nu lasa
    if (activeCat === 'motoare' && activeMotorFam !== 'asincron') {
      importMsg = `Esti pe tabul ${groupLabel(activeMotorFam)}. Importul aduce date de motor — comuta pe tabul Asincron.`; return
    }
    const t = backupType(producator, params, model)
    if (t !== 'asincron') {
      importMsg = `Backup-ul pare un motor ${TYPE_LABEL[t] || t} — importul suporta deocamdata doar motoare asincrone.`; return
    }
    const map = NAMEPLATE_CODES[producator] || NAMEPLATE_CODES.ABB
    let n = 0
    const set = (g, k, code, mult = 1) => { if (!code) return; const x = _num((params || {})[code]); if (x != null && x > 0) { equip[g][k] = x * mult; n++ } }
    set('retea', 'U', map.U); set('retea', 'f', map.f)
    set('asincron', 'Pn', map.Pn); set('asincron', 'In', map.In); set('asincron', 'n', map.n)
    set('asincron', 'cosphi', map.cosphi); set('asincron', 'eta', map.eta)
    // Siemens p0314 = PERECHI de poli -> nr poli = 2x; ABB n-are cod direct, Danfoss 1-39 = nr poli
    const _poliBefore = equip.asincron.poli
    set('asincron', 'poli', map.poli, producator === 'Siemens' ? 2 : 1)
    // nr poli lipsa din backup (ABB n-are cod, Siemens p0314=0) -> deriva din frecventa si turatie:
    // cei mai multi poli (turatia sincrona cea mai mica) inca peste turatia nominala
    if (equip.asincron.poli === _poliBefore) {
      const fv = _num((params || {})[map.f]), nv = _num((params || {})[map.n])
      if (fv > 0 && nv > 0) {
        let pp = 0
        for (let k = 2; k <= 16; k += 2) if ((120 * fv) / k >= nv) pp = k
        if (pp) { equip.asincron.poli = pp; n++ }
      }
    }
    // date extinse de drive/motor: turatie max, rampa decelerare, frecventa comutatie, Rs stator, inertie
    set('asincron', 'nmax', map.nmax); set('asincron', 'tdec', map.tdec)
    set('asincron', 'fsw', map.fsw); set('asincron', 'R1', map.R1); set('asincron', 'J', map.J)
    overrides = new Set()
    const jImported = !!(map.J && _num((params || {})[map.J]) > 0)
    importMsg = n
      ? `Importat ${n} valori în Asincron + Rețea.${jImported ? ' Inerția importată e a motorului — adaugă sarcina.' : ''} Verifică poli/cosphi.`
      : 'Nu am găsit date de plăcuță în acest backup.'
    if (n) { importDrives = []; setTimeout(() => (importOpen = false), 1500) }
  }
  // v28: tabul „Din proiect" a disparut odata cu tabela `echipamente`. Importul
  // se face direct din fisierul de backup — parserul citeste placuta din
  // .dcparamsbak / STARTER .zip fara sa treaca prin DB.
  function openImport() {
    importOpen = true; importMsg = ''; importDrives = []
  }
  async function onBackupFile(e) {
    const files = e.target.files; if (!files || !files.length) return
    importBusy = true; importMsg = 'Se încarcă...'; importDrives = []
    const isZip = /\.zip$/i.test(files[0].name)
    const fd = new FormData()
    if (isZip) fd.append('file', files[0]); else for (const f of files) fd.append('files', f)
    const url = isZip ? '/api/import-archive/preview' : '/api/import-abb-multi/preview'
    try {
      const r = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: csrfHeader(), body: fd })
      if (!r.ok) { importMsg = r.status === 413 ? 'Fisier prea mare (max 30 MB).' : 'Eroare ' + r.status + ' la citirea backup-ului.'; importBusy = false; e.target.value = ''; return }
      const d = await r.json(); const drives = d.drives || []
      if (!drives.length) importMsg = 'Backup fără date de plăcuță.'
      else if (drives.length === 1) applyImport(drives[0].producator, drives[0].params || {}, drives[0].model || '')
      else importDrives = drives
    } catch { importMsg = 'Nu am putut citi backup-ul.' }
    importBusy = false; e.target.value = ''
  }
</script>

<div class="page">
  <div class="page-head">
    <div class="head-row">
      <SolidIcon name="calculator" size={26} />
      <h1>Calculator acționări electrice</h1>
      <!-- Butoanele stau intr-un container cu `margin-left: auto`, nu fiecare cu al
           lui: doua elemente cu auto margin isi impart spatiul liber intre ele si
           raman despartite in mijlocul randului, nu lipite la dreapta. -->
      <div class="head-actions">
        <button class="surse-btn" onclick={() => (ghidOpen = true)}><Info size={15} /> Ghid</button>
        <button class="surse-btn" onclick={() => (surseOpen = true)}><BookOpen size={15} /> Surse &amp; standarde</button>
      </div>
    </div>
    <p class="sub">Mărimi inginerești pentru motoare și convertizoare — valori orientative, verifică întotdeauna catalogul/manualul.</p>
  </div>

  {#if activeCat === 'motoare'}
  <div class="equip-panel">
    <div class="equip-head">
      <button class="equip-toggle" onclick={() => (panelOpen = !panelOpen)} title="Introdu plăcuța o dată — toate cardurile se completează">
        <span class="equip-chev" class:open={panelOpen}><ChevronRight size={15} /></span>
        <SolidIcon name="cpu" size={16} /> <b>Date echipament</b>
        <span class="equip-sub">plăcuța + date drive — completează automat cardurile</span>
      </button>
      <label class="equip-switch" title="Cardurile folosesc datele de mai jos">
        <input type="checkbox" bind:checked={sharedOn} /> aplică la carduri
      </label>
    </div>
    {#if panelOpen}
      <div class="equip-collapse" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
      <div class="equip-body">
        {#each panelGroups as g (g)}
          <div class="equip-group">
            <span class="equip-group-h">{groupLabel(g)}</span>
            {#each sectionsFor(g) as sec (sec.label)}
              {#if sec.label}<span class="equip-sec-h">{sec.label}</span>{/if}
              <div class="equip-grid">
                {#each sec.items as c (c.key)}
                  <div class="equip-field">
                    <label>{c.label}{c.unit ? ` [${c.unit}]` : ''}</label>
                    <input type="number" step="any" bind:value={equip[g][c.key]} disabled={!sharedOn} />
                  </div>
                {/each}
              </div>
            {/each}
          </div>
        {/each}
      </div>
      <div class="equip-foot">
        <div class="equip-foot-grp">
          <button class="ef-import" onclick={openImport} title="Import din backup-uri drive (ABB/Siemens)">Import backup</button>
          <input class="equip-name" placeholder="nume echipament" bind:value={equipName} />
          <button onclick={saveEquip}>Salvează</button>
        </div>
        <div class="equip-foot-grp">
          <button class="exp-btn" onclick={exportResults} title="Copiaza rezultatele cardurilor deschise (pentru raport)"><Download size={13} /> Export</button>
          <button onclick={resetShared} title="Reseteaza datele la implicit">Reset</button>
        </div>
      </div>
      {#if equipments.length}
        <div class="equip-chips">
          <span class="equip-chips-h">Salvate:</span>
          {#each equipments as e (e.name)}
            <span class="equip-chip"><button onclick={() => loadEquip(e)}>{e.name}</button><button class="chip-x" title="Sterge" onclick={() => delEquip(e)}>×</button></span>
          {/each}
        </div>
      {/if}
      {#if exportMsg}<p class="equip-msg" transition:fade|local={{ duration: motionDuration(DUR_FAST) }}>{exportMsg}</p>{/if}
      </div>
    {/if}
  </div>
  {/if}

  <div class="search-wrap">
    <div class="search-row">
      <span class="search-ic"><Search size={16} /></span>
      <input class="search-inp" type="search" autocomplete="off"
        placeholder="Caută un calcul — titlu, simbol sau mărime (ex. NPSH, cuplu, U_dc)..."
        bind:value={query} onkeydown={onSearchKey} />
      {#if query}<button class="search-clear" title="Sterge cautarea" onclick={() => { query = ''; acIndex = -1 }}><X size={15} /></button>{/if}
    </div>
    {#if acResults.length}
      <ul class="ac-list" role="listbox" transition:fade={{ duration: motionDuration(DUR_FAST) }}>
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
  {:else if activeCat === 'intrebari' && intrebareSel}
    <div class="subfam-tabs">
      <button class="subfam-tab" onclick={() => (intrebareSel = null)}>← Toate întrebările</button>
      <span class="intreb-activa">{INTREBARI.find((x) => x.id === intrebareSel)?.q}</span>
    </div>
  {/if}

  <!-- Intrarea pe sarcina: intrebarea asa cum o pui, nu categoria in care cade -->
  {#if activeCat === 'intrebari' && !intrebareSel}
    <div class="intreb-grid">
      {#each INTREBARI as q (q.id)}
        <button class="intreb-card" onclick={() => alegeIntrebare(q.id)}>
          <span class="intreb-q">{q.q}</span>
          <span class="intreb-nev">Ai nevoie de: {q.nevoie}</span>
          <span class="intreb-mod">{q.module.length} carduri</span>
        </button>
      {/each}
      <p class="intreb-foot">Fiecare întrebare deschide cardurile care răspund la ea, în ordinea în care le parcurgi. Datele de echipament completate o dată se aplică peste tot.</p>
    </div>
  {/if}

  {#if favMods.length || recentMods.length}
    <div class="quick-rows">
      {#if favMods.length}
        <div class="quick-row">
          <span class="quick-h"><SolidIcon name="star" size={13} /> Favorite</span>
          {#each favMods as m (m.id)}<button class="chip" onclick={() => goTo(m.id)}>{m.title}</button>{/each}
        </div>
      {/if}
      {#if recentMods.length}
        <div class="quick-row">
          <span class="quick-h"><SolidIcon name="clock" size={13} /> Recente</span>
          {#each recentMods as m (m.id)}<button class="chip" onclick={() => goTo(m.id)}>{m.title}</button>{/each}
        </div>
      {/if}
    </div>
  {/if}

  {#snippet verdictDot(st, extra = '')}
    <span class="vd-dot {st} {extra}" title={VERDICT_TITLU[st]} aria-label={VERDICT_TITLU[st]}></span>
  {/snippet}

  {#snippet modBody(m)}
    {@const ev = effVals(m)}
    {@const r = computeModule(m, ev)}
    {@const charts = computeCharts(m, ev)}
    {@const vd = LIMITS[m.id] ? computeVerdicts(m, ev, r) : {}}
    <div class="acc-body-head">
      <span class="cat-badge">{catLabel(catOf(m))}</span>
      {#if authed && m.results.length}
        <button class="attach-btn" title="Salvează calculul la un proiect" onclick={() => openAttach(m)}><FolderPlus size={13} /> Proiect</button>
      {/if}
      <button class="reset-btn" title="Reseteaza valorile" onclick={() => resetModule(m)}>Reset</button>
    </div>

    {#if m.fields.length}
    <div class="inputs">
      {#each m.fields as f (f.key)}
        {@const linked = isLinked(m, f)}
        <div class="inp">
          <button type="button" class="inp-label" title="Definiție / de unde se ia" onclick={() => openTerm(f, m, false)}><Formula tex={symTeX(f.key)} inline /> {f.unit ? `[${f.unit}] ` : ''}{descLabel(f.label, f.key)}</button>
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
        <div class="res-row" class:has-vd={vd[res.key] && vd[res.key].st !== 'ok'}>
          <div class="res-head">
            <button type="button" class="res-label" title="Definiție / cum se calculează" onclick={() => openTerm(res, m, true)}><MathText text={res.label} /></button>
            <span class="res-right">
              {#if vd[res.key]}{@render verdictDot(vd[res.key].st)}{/if}
              <span class="res-val">{fmtNum(r[res.key], res.dec)}</span>
              {#if res.unit}<span class="res-unit">{res.unit}</span>{/if}
            </span>
          </div>
          {#if vd[res.key] && vd[res.key].st !== 'ok'}
            <p class="vd-text {vd[res.key].st}">
              {vd[res.key].de}
              {#if vd[res.key].src}<span class="vd-src">{vd[res.key].src}</span>{/if}
            </p>
          {/if}
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
      <span class="docs-h">Documentație:</span>
      {#each docsFor(m) as d}<a class="doc-link" href={d.href} target="_blank" rel="noopener">{d.label}</a>{/each}
    </div>
    {/if}

    <div class="acc-nav">
      <button class="nav-btn" disabled={shown[0]?.id === m.id} onclick={() => step(m, -1)}>‹ Anterior</button>
      <button class="nav-btn" disabled={shown[shown.length - 1]?.id === m.id} onclick={() => step(m, 1)}>Urmator ›</button>
    </div>
  {/snippet}

  {#if isDesktop}
    <!-- V2 desktop: navigator de module in stanga (sticky) + modulul activ in dreapta -->
    <div class="calc-grid">
      <aside class="calc-nav cell-in">
        <button class="nav-equip" onclick={openEquipPanel} title="Date echipament — click pentru panoul complet">
          <span class="nav-equip-h"><SolidIcon name="cpu" size={13} /> Date echipament</span>
          <span class="nav-equip-sum">{equipSummary}</span>
        </button>
        {#each rows as row (row.kind === 'head' ? row.key : row.m.id)}
          {#if row.kind === 'head'}
            <div class="nav-sec">{row.label}</div>
          {:else}
            <div class="nav-item" class:on={activeMod?.id === row.m.id} id={'nav-' + row.m.id}>
              <button class="nav-item-btn" onclick={() => openModule(row.m.id)}>
                {#if stariModule.has(row.m.id)}{@render verdictDot(stariModule.get(row.m.id), 'nav-dot')}{/if}{row.m.title}
              </button>
              <button class="star-btn nav-star" class:on={isFav(row.m.id)} title="Adauga la favorite" aria-label="Favorit"
                onclick={() => toggleFav(row.m.id)}>{#if isFav(row.m.id)}<SolidIcon name="star" size={13} />{:else}<Star size={13} />{/if}</button>
            </div>
          {/if}
        {/each}
        <p class="nav-count">{shown.length} {shown.length === 1 ? 'modul' : 'module'}</p>
      </aside>

      {#if activeMod}
        <section class="mod-cell cell-in" id={'acc-' + activeMod.id}>
          <div class="mod-cell-head">
            <span class="acc-title">{#if stariModule.has(activeMod.id)}{@render verdictDot(stariModule.get(activeMod.id))}{/if}{activeMod.title}{#if activeMod.subtitle}<span class="acc-sub"><MathText text={activeMod.subtitle} /></span>{/if}</span>
            <button class="star-btn" class:on={isFav(activeMod.id)} title="Adauga la favorite" aria-label="Favorit"
              onclick={() => toggleFav(activeMod.id)}>{#if isFav(activeMod.id)}<SolidIcon name="star" size={15} />{:else}<Star size={15} />{/if}</button>
          </div>
          <div class="acc-body">{@render modBody(activeMod)}</div>
        </section>
      {:else}
        <section class="mod-cell mod-cell-empty"><p class="acc-status">Niciun modul in aceasta categorie.</p></section>
      {/if}
    </div>
  {:else}
    <!-- Viewport ingust: acordeonul existent, neschimbat -->
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
            <span class="acc-title">{#if stariModule.has(m.id)}{@render verdictDot(stariModule.get(m.id))}{/if}{m.title}{#if m.subtitle}<span class="acc-sub"><MathText text={m.subtitle} /></span>{/if}</span>
            <button class="star-btn" class:on={isFav(m.id)} title="Adauga la favorite" aria-label="Favorit"
              onclick={(e) => { e.stopPropagation(); toggleFav(m.id) }}>{#if isFav(m.id)}<SolidIcon name="star" size={15} />{:else}<Star size={15} />{/if}</button>
          </div>

          {#if open}
            <div class="acc-body" transition:slide={{ duration: motionDuration(DUR_BASE) }}>{@render modBody(m)}</div>
          {/if}
        </div>
        {/if}
      {/each}
      <p class="acc-status">{shown.length} {shown.length === 1 ? 'modul' : 'module'} • {[...expanded].filter((id) => shown.some((m) => m.id === id)).length} deschise</p>
    </div>
  {/if}

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
          <div class="term-sec"><span class="term-h">Cum se calculează</span><Formula tex={term.tex} display /></div>
        {/if}
        {#if term.g?.def}<div class="term-sec"><span class="term-h">Definiție</span><p><MathText text={term.g.def} /></p></div>{/if}
        {#if term.g?.ia}<div class="term-sec"><span class="term-h">De unde se ia</span><p><MathText text={term.g.ia} /></p></div>{/if}
        {#if term.g?.practic}<div class="term-sec"><span class="term-h">În practică</span><p><MathText text={term.g.practic} /></p></div>{/if}
        {#if term.g?.teorie}<div class="term-sec"><span class="term-h">Principiu / teorie</span><p><MathText text={term.g.teorie} /></p></div>{/if}
        {#if term.figLink}<div class="term-sec"><span class="term-h">Diagramă</span><a class="fig-link" href={term.figLink.href} target="_blank" rel="noopener"><BookOpen size={14} /> {term.figLink.label}</a></div>{/if}
        {#if term.source}<div class="term-sec"><span class="term-h">Sursă</span><p class="term-src"><MathText text={term.source} /></p></div>{/if}
        {#if term.docs?.length}
          <div class="term-sec"><span class="term-h">Documentație</span>
            <div class="term-docs">
              {#each term.docs as d}
                <a class="doc-link" href={d.href} target="_blank" rel="noopener">{d.label}</a>
              {/each}
            </div>
          </div>
        {/if}
        {#if !term.g && !term.tex}<p class="term-empty">Mărime fără definiție detaliată încă. Vezi sursa modulului și formulele asociate.</p>{/if}
      </div>
    {/if}
  </Modal>

  <Modal bind:open={ghidOpen} title="Ghidul calculatorului" size="lg">
    <div class="surse">
      <p class="surse-intro">Cifrele de mai jos se citesc din calculator la deschiderea ghidului, nu sunt scrise de mână — dacă apare un modul sau un prag nou, ghidul îl numără singur.</p>
      {#each ghid as sec}
        <div class="surse-sec ghid-sec">
          <h3>{sec.h}</h3>
          {#each sec.p as par}<p class="ghid-p">{@html par}</p>{/each}
        </div>
      {/each}
    </div>
  </Modal>

  <Modal bind:open={surseOpen} title="Surse & standarde" size="lg">
    <div class="surse">
      <p class="surse-intro">Notație & standarde primare = <b>europene (IEC / EN / ISO)</b>; cele americane (IEEE / NEMA) doar ca echivalent. Fiecare card își afișează sursa proprie. Standardele sunt documente cu plată — citate ca text, nu găzduite. Cărțile au extrase (doar paginile citate) la <b>/docs</b> cu login.</p>
      {#each SURSE as g}
        <div class="surse-sec">
          <h3>{g.h}</h3>
          <ul>{#each g.items as it}<li>{it}</li>{/each}</ul>
        </div>
      {/each}
    </div>
  </Modal>

  <!-- Ataseaza calculul la un proiect (doar logat) -->
  <Modal bind:open={attachOpen} title="Salvează calculul la proiect" size="md">
    <div class="attach-form">
      {#if attachMod}
        <p class="attach-mod">{attachMod.title}</p>
      {/if}
      <label class="attach-l">Proiect
        <Select bind:value={attachProiectId} options={attachProiecte.map((p) => ({ value: p.id, label: `${p.cod_proiect ? p.cod_proiect + ' — ' : ''}${p.nume}` }))} />
      </label>
      <label class="attach-l">Titlu
        <input class="attach-inp" type="text" bind:value={attachTitlu} placeholder="ex. Cablu motor pompa 2" />
      </label>
      <label class="attach-l">Notă (opțional)
        <textarea class="attach-inp attach-ta" rows="2" bind:value={attachNota} placeholder="ce s-a decis, ce rămâne de verificat"></textarea>
      </label>
      <p class="attach-hint">Se salvează intrările, rezultatele și verdictele așa cum sunt acum. Înregistrarea nu se recalculează mai târziu — e consemnarea zilei.</p>
      <div class="attach-actions">
        <button class="attach-save" disabled={attachBusy || !attachProiectId} onclick={saveAttach}>{attachBusy ? 'Se salvează…' : 'Salvează'}</button>
        {#if attachMsg}<span class="attach-msg">{attachMsg}</span>{/if}
      </div>
    </div>
  </Modal>

  <Modal bind:open={importOpen} title="Import date echipament" size="md">
    <div class="imp">
      <p class="imp-hint">Încarcă un backup de drive: ABB <code>.dcparamsbak</code> (poți selecta mai multe) sau Siemens STARTER <code>.zip</code>. Merge și fără login.</p>
      <input type="file" accept=".dcparamsbak,.zip" multiple onchange={onBackupFile} disabled={importBusy} />
      {#if importDrives.length}
        <div class="imp-drives-wrap" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
        <p class="imp-hint">Arhiva contine mai multe drive-uri — alege pe care il importi:</p>
        <div class="imp-equip">
          {#each importDrives as dr, i (i)}
            {@const tp = backupType(dr.producator, dr.params || {}, dr.model || '')}
            {@const pv = drivePreview(dr.producator, dr.params)}
            <button class="imp-eq" onclick={() => applyImport(dr.producator, dr.params || {}, dr.model || '')}>
              <span class="imp-eq-name">{dr.nume || 'Drive'} <em class="imp-eq-tag" class:warn={tp !== 'asincron'}>{TYPE_LABEL[tp] || tp}</em></span>
              <span>{dr.producator || ''} {dr.model || ''}{#if pv} · {pv}{/if}</span>
            </button>
          {/each}
        </div>
        </div>
      {/if}
      {#if importMsg}<p class="imp-msg" transition:fade={{ duration: motionDuration(DUR_FAST) }}>{importMsg}</p>{/if}
      <p class="imp-note">Umple grupul <b>Asincron</b> + <b>Rețea</b>: plăcuța (P/U/I/n/cosφ/η/poli) + date drive când există (turație max, rampă decelerare, frecvență comutație, R stator, inerție). Coduri: ABB grup 99/30/23, Siemens p03xx/p11xx/p18xx, Danfoss 1-xx. Un backup de alt tip (c.c./servo) nu se importă pe tabul asincron.</p>
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
  .head-row h1 { font-size: var(--font-title); font-weight: var(--fw-semibold); }
  .sub {
    font-size: var(--font-small);
    color: var(--text-dim);
    margin-top: 2px;
    max-width: 70ch;
  }
  .head-actions { margin-left: auto; display: flex; align-items: center; gap: var(--space-xs); flex-shrink: 0; }
  .surse-btn {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary);
    padding: 6px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm);
    background: var(--bg-surface); cursor: pointer; transition: var(--transition-colors);
  }
  .surse-btn:hover { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }
  .surse { display: flex; flex-direction: column; gap: var(--space-md); }
  .surse-intro { font-size: var(--font-small); color: var(--text-dim); line-height: var(--lh-normal); }
  .surse-sec h3 { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--accent); margin-bottom: 4px; }
  .surse-sec ul { list-style: none; display: flex; flex-direction: column; gap: 3px; }
  .surse-sec li { font-size: var(--font-small); color: var(--text-secondary); line-height: var(--lh-normal); padding-left: 12px; position: relative; }
  .surse-sec li::before { content: '·'; position: absolute; left: 2px; color: var(--text-dim); }
  .ghid-sec { display: flex; flex-direction: column; gap: 5px; }
  .ghid-p { font-size: var(--font-small); color: var(--text-secondary); line-height: var(--lh-normal); }
  .ghid-p :global(b) { color: var(--text); font-weight: var(--fw-semibold); }

  /* === Date echipament partajate === */
  .equip-panel { border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--bg-surface); margin-bottom: var(--space-md); padding: 10px 12px; }
  .equip-head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; justify-content: space-between; }
  .equip-toggle { display: inline-flex; align-items: center; gap: 7px; font-size: var(--font-small); color: var(--text); cursor: pointer; }
  .equip-sub { font-size: var(--font-small); font-weight: var(--fw-normal); color: var(--text-dim); }
  .equip-chev { display: flex; color: var(--text-dim); transition: transform var(--dur-fast) var(--ease); }
  .equip-chev.open { transform: rotate(90deg); color: var(--accent); }
  .equip-switch { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-small); color: var(--text-secondary); cursor: pointer; }
  .equip-body { margin-top: 4px; }
  /* toolbar de actiuni: stanga = intrare (import backup / salveaza), dreapta = iesire (export / reset) */
  .equip-foot { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; margin-top: 14px; padding-top: 11px; border-top: 1px solid var(--border); }
  .equip-foot-grp { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .equip-foot button {
    font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary);
    padding: 6px 11px; border: 1px solid var(--border); border-radius: var(--radius-sm);
    background: var(--bg-elevated); cursor: pointer; display: inline-flex; align-items: center; gap: 4px;
    transition: var(--transition-colors);
  }
  .equip-foot button:hover { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }
  .equip-foot .ef-import { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .equip-foot .ef-import:hover { filter: brightness(1.07); }
  .equip-name { font-size: var(--font-small); padding: 6px 9px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-elevated); color: var(--text); width: 130px; }
  /* align-items:end -> inputurile se aliniaza la baza chiar daca o eticheta se rupe pe 2 randuri */
  .equip-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(124px, 1fr)); gap: 8px 10px; margin-top: 6px; align-items: end; }
  .equip-field { display: flex; flex-direction: column; gap: 3px; }
  /* min-height = 2 randuri -> etichetele scurte si cele care se rup pe 2 randuri rezerva aceeasi zona,
     deci inputurile se aliniaza uniform (impreuna cu align-items:end pe grid) */
  .equip-field label { font-size: var(--font-small); color: var(--text-dim); line-height: var(--lh-tight); min-height: 2.4em; display: flex; align-items: flex-start; }
  .equip-field input { padding: 7px 9px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-elevated); color: var(--text); font-size: var(--font-small); font-weight: var(--fw-semibold); }
  .equip-field input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }
  .equip-field input:disabled { opacity: 0.45; }
  .equip-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 10px; }
  .equip-chips-h { font-size: var(--font-small); color: var(--text-dim); }
  .equip-chip { display: inline-flex; align-items: center; border: 1px solid var(--border); border-radius: 999px; overflow: hidden; }
  .equip-chip > button { font-size: var(--font-small); padding: 3px 10px; color: var(--text-secondary); cursor: pointer; background: var(--bg-surface); }
  .equip-chip > button:hover { background: var(--accent-subtle); color: var(--accent); }
  .equip-chip .chip-x { padding: 3px 8px; color: var(--text-dim); border-left: 1px solid var(--border); }
  .equip-msg { font-size: var(--font-small); color: var(--accent); margin-top: 8px; }
  /* input cu buton de legare la datele partajate */
  .inp-row { display: flex; align-items: stretch; gap: 4px; margin-top: auto; }
  .inp-row .inp-field { flex: 1; min-width: 0; margin-top: 0; }
  .link-btn { display: flex; align-items: center; justify-content: center; width: 28px; flex-shrink: 0; border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-dim); cursor: pointer; background: var(--bg-surface); }
  .link-btn.on { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .link-btn:hover { color: var(--text); border-color: var(--text-dim); }
  .equip-group { margin-top: 12px; }
  .equip-group-h { display: block; font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-dim); text-transform: uppercase; letter-spacing: var(--tracking-label); margin-bottom: 6px; }
  .equip-sec-h { display: block; font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary); margin: 9px 0 0; }
  .equip-sec-h:first-of-type { margin-top: 2px; }

  /* sub-antet de sectiune in accordion */
  .acc-section-head { font-size: var(--font-small); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); padding: 12px 2px 3px; }

  /* modal import */
  .imp { display: flex; flex-direction: column; gap: var(--space-sm); }
  .imp-equip { display: flex; flex-direction: column; gap: 6px; max-height: 240px; overflow: auto; }
  .imp-eq { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; text-align: left; padding: 8px 11px; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text); font-size: var(--font-small); font-weight: var(--fw-semibold); cursor: pointer; }
  .imp-eq:hover { background: var(--accent-subtle); border-color: var(--accent); }
  .imp-eq span { font-size: var(--font-small); font-weight: var(--fw-normal); color: var(--text-dim); }
  .imp-eq .imp-eq-name { display: flex; align-items: center; gap: 7px; font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); }
  .imp-eq-tag { font-style: normal; font-size: var(--font-small); font-weight: var(--fw-semibold); padding: 1px 7px; border-radius: 999px; background: var(--accent-subtle); color: var(--accent); }
  .imp-eq-tag.warn { background: var(--service-subtle); color: var(--service-accent); }
  .imp input[type=file] { font-size: var(--font-small); color: var(--text-secondary); }
  .imp-hint { font-size: var(--font-small); color: var(--text-dim); }
  .imp-hint code { font-family: var(--font-mono); background: var(--bg-hover); padding: 0 4px; border-radius: 3px; }
  .imp-msg { font-size: var(--font-small); color: var(--accent); font-weight: var(--fw-semibold); }
  .imp-note { font-size: var(--font-small); color: var(--text-dim); border-top: 1px dashed var(--border); padding-top: 8px; }

  .fam-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-xs);
    margin-bottom: var(--space-lg);
    border-bottom: 1px solid var(--border);
    padding-bottom: var(--space-sm);
  }
  /* aceeasi reteta .chip ca filtrele din Proiecte/Taskuri */
  .fam-tab {
    padding: 4px 14px; min-height: 30px;
    border-radius: var(--radius-full);
    font-size: var(--font-small);
    font-weight: var(--fw-medium);
    color: var(--text-secondary);
    background: var(--bg-input);
    border: 1px solid transparent;
    transition: var(--transition-colors);
    cursor: pointer;
  }
  .fam-tab:hover { background: var(--bg-hover); color: var(--text); }
  .fam-tab.active { background: var(--accent-subtle); color: var(--accent-on-subtle); border-color: var(--accent); }
  .fam-tab:active { transform: scale(0.97); }

  /* sub-taburi pentru Motoare (pe tip) */
  .subfam-tabs { display: flex; flex-wrap: wrap; gap: var(--space-xs); margin: calc(-1 * var(--space-md)) 0 var(--space-lg); }
  .intreb-activa { align-self: center; font-size: var(--font-small); color: var(--text-secondary); }

  /* Intrarea pe sarcina */
  .intreb-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-sm);
    margin-bottom: var(--space-lg);
  }
  .intreb-card {
    display: flex; flex-direction: column; gap: 5px;
    text-align: left;
    padding: 12px 14px;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .intreb-card:hover { border-color: var(--accent); background: var(--accent-subtle); }
  .intreb-q { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); line-height: var(--lh-snug); }
  .intreb-nev { font-size: var(--font-small); color: var(--text-dim); line-height: var(--lh-snug); }
  .intreb-mod { font-size: var(--font-small); color: var(--accent); }
  .intreb-foot { grid-column: 1 / -1; font-size: var(--font-small); color: var(--text-dim); line-height: var(--lh-normal); padding-top: 4px; }
  .subfam-tab {
    padding: 3px 13px; min-height: 26px; border-radius: var(--radius-full); font-size: var(--font-small); font-weight: var(--fw-medium);
    color: var(--text-secondary); border: 1px solid transparent; background: var(--bg-input);
    cursor: pointer; transition: var(--transition-pressable);
  }
  .subfam-tab:hover { background: var(--bg-hover); color: var(--text); }
  .subfam-tab.active { background: var(--accent-subtle); color: var(--accent-on-subtle); border-color: var(--accent); }
  .subfam-tab:active { transform: scale(0.97); }

  /* caseta de cautare */
  .search-row { position: relative; display: flex; align-items: center; margin-bottom: var(--space-md); }
  .search-ic { position: absolute; left: 12px; display: flex; color: var(--text-dim); pointer-events: none; }
  .search-inp {
    width: 100%; padding: 9px 38px; border: 1px solid var(--border); border-radius: var(--radius-full);
    background: var(--bg-panel); color: var(--text); font-size: var(--font-body);
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .search-inp:focus { outline: none; border-color: var(--accent); box-shadow: var(--focus-ring); }
  .search-clear { position: absolute; right: 8px; display: flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; }
  .search-clear:hover { background: var(--bg-hover); color: var(--text); }
  .cat-badge { display: inline-block; margin-top: 4px; width: fit-content; font-size: var(--font-small); color: var(--text-dim); background: var(--bg-hover); border-radius: 999px; padding: 1px 9px; }

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
    font-size: var(--font-body); font-weight: var(--fw-semibold); color: var(--text);
  }
  .acc-sub { font-size: var(--font-small); font-weight: var(--fw-normal); color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
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
    font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary);
    padding: 5px 12px; border: 1px solid var(--border); border-radius: var(--radius-sm);
    background: var(--bg-surface); cursor: pointer; transition: var(--transition-colors);
  }
  .nav-btn:hover:not(:disabled) { background: var(--bg-hover); color: var(--text); border-color: var(--text-dim); }
  .nav-btn:disabled { opacity: 0.4; cursor: default; }
  .acc-status { text-align: center; font-size: var(--font-small); color: var(--text-dim); padding-top: var(--space-sm); }

  /* === V2 (desktop >=940px): navigator sticky + modulul activ === */
  .calc-grid { display: grid; grid-template-columns: 270px 1fr; gap: 14px; align-items: start; }
  .calc-nav {
    position: sticky; top: calc(var(--header-height) + 16px);
    max-height: calc(100dvh - var(--header-height) - var(--dock-h) - 48px);
    overflow-y: auto;
    background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg);
    padding: 12px; display: flex; flex-direction: column; gap: 2px;
  }
  .nav-equip {
    display: flex; flex-direction: column; align-items: flex-start; gap: 3px; width: 100%;
    padding: 8px 10px; margin-bottom: 6px; text-align: left;
    border: 1px dashed var(--border); border-radius: var(--radius-md);
    background: var(--bg-elevated); cursor: pointer; transition: var(--transition-colors);
  }
  .nav-equip:hover { border-color: var(--accent); background: var(--accent-subtle); }
  .nav-equip-h { display: inline-flex; align-items: center; gap: 6px; font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary); text-transform: uppercase; letter-spacing: var(--tracking-label); }
  .nav-equip-sum { font-family: var(--font-mono); font-size: var(--font-small); color: var(--text-dim); overflow-wrap: anywhere; }
  /* aceeasi reteta de grup ca nav-ul din Parametri: separator dashed + punct amber */
  .nav-sec {
    font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase;
    letter-spacing: var(--tracking-label); color: var(--text-faint); padding: 14px 10px 6px;
    margin-top: 10px; border-top: 1px dashed var(--border);
    display: flex; align-items: center; gap: 8px;
  }
  .nav-sec::before {
    content: ''; width: 7px; height: 7px; border-radius: 3px;
    background: var(--accent-subtle); border: 1px solid var(--accent-ring); flex-shrink: 0;
  }
  .nav-sec:first-of-type { padding-top: 4px; margin-top: 4px; }
  .nav-item { display: flex; align-items: center; gap: 2px; border-radius: var(--radius-md); transition: background var(--dur-fast) var(--ease); }
  .nav-item:hover { background: var(--bg-hover); }
  .nav-item.on { background: var(--accent-subtle); }
  .nav-item.on .nav-item-btn { color: var(--accent); font-weight: var(--fw-semibold); }
  .nav-item-btn {
    flex: 1; min-width: 0; text-align: left; font-size: var(--font-small); color: var(--text-secondary);
    padding: 7px 4px 7px 10px; border-radius: var(--radius-md); cursor: pointer; overflow-wrap: anywhere;
    transition: color var(--dur-fast) var(--ease);
  }
  .nav-star { opacity: 0; margin-right: 4px; }
  .nav-item:hover .nav-star, .nav-star.on { opacity: 1; }
  .nav-count { font-size: var(--font-small); color: var(--text-dim); text-align: center; padding-top: 8px; }
  .mod-cell { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; min-width: 0; }
  .mod-cell-head { display: flex; align-items: center; gap: 10px; padding: 12px 16px; }
  .mod-cell-empty { padding: var(--space-lg); }

  /* === Autocomplete cautare === */
  .search-wrap { position: relative; margin-bottom: var(--space-md); }
  .search-wrap .search-row { margin-bottom: 0; }
  .ac-list {
    position: absolute; z-index: 30; top: calc(100% + 4px); left: 0; right: 0;
    background: var(--bg-overlay); border: 1px solid var(--border); border-radius: var(--radius-md);
    box-shadow: var(--shadow-lg); padding: 4px;
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
  .quick-h { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-dim); margin-right: 2px; }
  .chip {
    font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary);
    padding: 3px 11px; border-radius: 999px; border: 1px solid var(--border); background: var(--bg-surface);
    cursor: pointer; transition: var(--transition-colors);
  }
  .chip:hover { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }
  .reset-btn {
    font-size: var(--font-small);
    color: var(--text-dim);
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
    transition: var(--transition-colors);
    cursor: pointer;
  }
  .reset-btn:hover { background: var(--bg-hover); color: var(--text); }

  .attach-btn {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: var(--font-small);
    color: var(--text-dim);
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    flex-shrink: 0;
    margin-left: auto;
    transition: var(--transition-colors);
    cursor: pointer;
  }
  .attach-btn:hover { background: var(--accent-subtle); color: var(--accent); }

  .attach-form { display: flex; flex-direction: column; gap: var(--space-sm); }
  .attach-mod {
    font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--accent);
    padding-bottom: 2px;
  }
  .attach-l {
    display: flex; flex-direction: column; gap: 4px;
    font-size: var(--font-small); color: var(--text-dim);
  }
  .attach-inp {
    background: var(--bg-surface); border: 1px solid var(--border);
    border-radius: var(--radius-sm); padding: 7px 9px;
    color: var(--text); font-size: var(--font-small); font-family: inherit;
  }
  .attach-inp:focus { outline: none; border-color: var(--accent); }
  .attach-ta { resize: vertical; }
  .attach-hint { font-size: var(--font-small); color: var(--text-dim); line-height: var(--lh-normal); }
  .attach-actions { display: flex; align-items: center; gap: var(--space-sm); margin-top: 2px; }
  .attach-save {
    background: var(--accent); color: var(--bg);
    border: none; border-radius: var(--radius-sm);
    padding: 7px 14px; font-size: var(--font-small); font-weight: var(--fw-semibold);
    cursor: pointer;
  }
  .attach-save:disabled { opacity: 0.55; cursor: default; }
  .attach-msg { font-size: var(--font-small); color: var(--text-secondary); }

  .inputs {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: var(--space-sm);
  }
  .inp { display: flex; flex-direction: column; gap: 4px; }
  .inp-label {
    font-size: var(--font-small);
    font-weight: var(--fw-medium);
    color: var(--text-secondary);
    line-height: var(--lh-tight);
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
    box-shadow: var(--focus-ring);
  }

  .results {
    display: flex;
    flex-direction: column;
    border-top: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
  }
  .res-row {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: var(--space-sm) 0;
    border-bottom: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
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
    font-size: var(--font-h3);
    font-weight: var(--fw-semibold);
    color: var(--accent);
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
  }
  .res-unit { font-size: var(--font-small); color: var(--text-secondary); }

  /* ---- Verdicte ----
     Bulina e semnalul care se citeste de la distanta (in lista de module);
     propozitia apare doar cand NU e in regula, ca sa nu umple cardul cu
     confirmari inutile. Culoarea nu e singurul canal: fiecare bulina are
     title/aria-label, iar textul spune de ce. */
  .vd-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    display: inline-block;
    align-self: center;
  }
  .vd-dot.ok { background: var(--success); }
  .vd-dot.atentie { background: var(--warning); }
  .vd-dot.critic { background: var(--danger); }
  .vd-dot.nav-dot { margin-right: 6px; vertical-align: middle; }
  .acc-title .vd-dot { margin-right: 7px; vertical-align: middle; }

  .res-row.has-vd { border-left: 2px solid transparent; padding-left: 8px; margin-left: -10px; }
  .res-row.has-vd:has(.vd-text.atentie) { border-left-color: var(--warning); }
  .res-row.has-vd:has(.vd-text.critic) { border-left-color: var(--danger); }

  .vd-text {
    font-size: var(--font-small);
    line-height: var(--lh-normal);
    padding: 5px 7px;
    border-radius: var(--radius-sm);
    margin: 1px 0 2px;
  }
  .vd-text.atentie { color: var(--warning); background: var(--warning-subtle); }
  .vd-text.critic { color: var(--danger); background: var(--danger-subtle); }
  .vd-src {
    display: block;
    margin-top: 2px;
    color: var(--text-dim);
    font-size: var(--font-small);
    opacity: 0.85;
  }

  .mod-note {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    font-size: var(--font-small);
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
    line-height: var(--lh-normal);
  }
  .mod-params {
    font-family: var(--font-mono);
    font-size: var(--font-small);
    color: var(--text-dim);
    border-top: 1px dashed var(--border);
    padding-top: var(--space-sm);
  }
  .mod-source {
    display: flex;
    align-items: flex-start;
    gap: 5px;
    font-size: var(--font-small);
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
  .docs-h { font-size: var(--font-small); color: var(--text-dim); }
  .doc-link {
    display: inline-flex;
    align-items: center;
    font-size: var(--font-small);
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    background: var(--bg-hover);
    border: 1px solid var(--border);
    color: var(--accent);
    text-decoration: none;
    line-height: var(--lh-snug);
  }
  .doc-link:hover { background: var(--bg-surface); border-color: var(--accent); }
  .fig-link {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: var(--font-small); font-weight: var(--fw-semibold);
    padding: 7px 12px; border-radius: var(--radius-md);
    background: var(--accent-subtle); border: 1px solid var(--accent);
    color: var(--accent); text-decoration: none; width: fit-content;
  }
  .fig-link:hover { filter: brightness(1.07); }
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
    font-size: var(--font-small);
    font-weight: var(--fw-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    color: var(--accent);
  }
  .term-sec p { font-size: var(--font-body); color: var(--text); line-height: var(--lh-normal); }
  .term-src { font-family: var(--font-mono); font-size: var(--font-small) !important; color: var(--text-dim) !important; }
  .term-empty { font-size: var(--font-small); color: var(--text-dim); }

  @media (max-width: 768px) {
    .acc-sub { display: none; }
    .acc-head { padding: 10px 12px; gap: 8px; }
    /* Calculatorul se foloseste EXACT acolo unde e greu: langa un dulap, cu
       telefonul intr-o mana. Taburile de familie (30px) si cele de subfamilie
       (26px) erau cele mai mici tinte de aici — si sunt primul lucru pe care il
       atingi la fiecare intrare in pagina.
       Randurile de acordeon si campurile de calcul cresc si ele: `.acc-head` e ce
       deschizi ca sa ajungi la formula. */
    .fam-tab { min-height: var(--tap-min); padding: 4px 16px; }
    /* Subfamiliile raman vizual mai usoare (font mai mic), dar la fel de usor de
       atins — ierarhia se citeste din greutate, nu din cat de greu nimeresti. */
    .subfam-tab { min-height: var(--tap-min); padding: 3px 14px; }
    /* Antetul paginii, pe telefon: titlul se rupe pe doua randuri, iar
       `align-items: center` lasa iconita plutind la mijlocul lor, langa nimic.
       Se aliniaza la PRIMUL rand, ca un semn de titlu, nu ca un vecin.
       „Surse & standarde" coboara pe randul lui: langa un titlu de doua randuri
       se ingusta pana isi rupea si el eticheta in doua. */
    .head-row { flex-wrap: wrap; align-items: flex-start; }
    .head-row :global(svg) { margin-top: 2px; flex-shrink: 0; }
    /* `flex-basis: 0`, nu `auto`: cu `auto` titlul isi cerea latimea intreaga
       (~320px), nu incapea langa iconita si se ducea el pe randul urmator —
       ramanea iconita singura pe un rand, ca un cap de lista fara lista. Cu
       basis 0 titlul ia CE RAMANE si isi rupe textul inauntru, unde e normal
       sa se rupa. */
    .head-row h1 { flex: 1 1 0; min-width: 0; }
    /* `100%` = randul lor, mereu. Altfel butoanele se strecoara langa un titlu
       scurt si se ingusta pana isi rup eticheta in doua. Randul e al
       containerului; cele doua butoane il impart, fiecare peste pragul de
       atingere. */
    .head-actions { flex: 0 0 100%; margin-left: 0; }
    .surse-btn { flex: 1 1 auto; min-height: var(--tap-min);
                 justify-content: center; white-space: nowrap; }
    .fam-tabs, .subfam-tabs { gap: 6px; }
    .acc-head { min-height: var(--tap-min); }
    /* Steaua sta lipita de titlul modulului, in acelasi rand. Umflata la 44px ar
       impinge titlul; asa ramane de 23px la vedere si de 44 la atingere. */
    .star-btn { position: relative; }
    .star-btn::after { content: ''; position: absolute; inset: -11px; }
    /* Campurile de calcul: 43px, cu doua pe rand. Un pixel sub prag, dar tocmai
       aici tastezi cel mai des. */
    .inp-field, .search-inp { min-height: var(--tap-min); }
    /* Scurtaturile catre modulele folosite des („Legile afinității" etc.) — 25px. */
    .chip { min-height: var(--tap-min); }
    /* „Proiect" si „Reset" stau in acelasi rand, deasupra campurilor. Masurate pe
       telefon: 25px inaltime. Umflate la 44 ar impinge randul in jos degeaba —
       primesc aceeasi solutie ca steaua: raman de 25px la vedere, 45 la atingere. */
    .attach-btn, .reset-btn { position: relative; }
    .attach-btn::after, .reset-btn::after { content: ''; position: absolute; inset: -10px; }
    /* Intrarea pe sarcina: o intrebare pe rand, nu doua pe jumatate de latime. */
    .intreb-grid { grid-template-columns: 1fr; }
  }
</style>
