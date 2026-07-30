<script>
  import { onMount } from 'svelte'
  import { CalendarRange, ChevronRight, ArrowRight, X, CheckCircle2, Repeat, ExternalLink, Check, FileDown, Inbox, GripVertical, MapPin, Building2 } from '@lucide/svelte'
  import {
    plan, loadPlan, moveTaskDate, moveTaskTomorrow, toggleTaskDone,
    setTaskDates, setHorizon, toggleShowDone, toggleWeekends, scheduleBacklog,
  } from '../stores/plan.svelte.js'
  import { buildColumns, spanRect, dayDiff, addDays, clampNum } from '../lib/planDates.js'
  import { formatDate, formatDateShort, zilePanaLa } from '../lib/formatters.js'
  import { toast } from '../stores/ui.svelte.js'
  import { morphNavigate } from '../lib/focus.js'
  import { glisare } from '../lib/glisare.js'
  import { motion } from '../lib/motion.svelte.js'
  import { navigate } from '../lib/router.svelte.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import Modal from '../components/ui/Modal.svelte'

  // Distinct, CVD-legible lane hues on the warm-dark ground. Amber is reserved for
  // the app accent/active state, so lanes deliberately avoid it.
  const LANE_PALETTE = ['#3f9dc4', '#3fae74', '#8b6fe0', '#d1697f', '#b9a5ff', '#5f8fd0', '#c9a13a']
  // Praguri pentru continutul unei benzi de perioada, in PROCENTE din fereastra —
  // nu in zile: la 6 luni o zi are 6px, la 7 zile are 165. Sub primul prag ramane
  // doar icoana (o litera taiata nu spune nimic, icoana spune „teren" / „sediu");
  // sub al doilea, durata ar manca eticheta, deci o lasam doar in tooltip.
  const BANDA_TEXT_MIN = 6.5
  const BANDA_ZILE_MIN = 14
  const GLOBAL_COLOR = '#948a7d'
  const HORIZONS = [{ d: 7, l: '7z' }, { d: 14, l: '14z' }, { d: 30, l: '30z' }, { d: 90, l: '3L' }, { d: 180, l: '6L' }]

  function laneColor(id) {
    if (id === '__global__') return GLOBAL_COLOR
    let h = 0
    for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0
    return LANE_PALETTE[h % LANE_PALETTE.length]
  }

  const columns = $derived(buildColumns(plan.start, plan.days))
  const unit = $derived(columns.unit)
  const todayIdx = $derived(plan.start && plan.today ? dayDiff(plan.start, plan.today) : null)
  const todayPct = $derived(todayIdx != null ? (todayIdx / plan.days) * 100 : null)
  // Per-column min width by granularity, so a 6-month (monthly) view doesn't force
  // a 180-cell scroll. Daily view stays readable down to ~34px/day.
  const colMin = $derived(unit === 'day' ? (plan.days <= 7 ? 74 : plan.days <= 14 ? 48 : 34) : unit === 'week' ? 66 : 104)
  const contentMin = $derived(240 + colMin * columns.cols.length) // lane-w(240) + cols
  const dayCompact = $derived(unit === 'day' && plan.days > 24)

  function isActive(s) { return s === 'in_progress' || s === 'in_lucru' }
  function isDone(s) { return s === 'done' || s === 'finalizat' }
  function effDue(t) { return t.data_scadenta || (isDone(t.status) ? t.data_finalizare : '') }

  // Greedy interval packing: non-overlapping bars share a row (sorted by start).
  function packRows(tasks) {
    const withRect = tasks.filter(t => t.rect).sort((a, b) => a.rect.left - b.rect.left || a.rect.width - b.rect.width)
    const rows = []
    for (const t of withRect) {
      let placed = false
      for (const row of rows) {
        const last = row[row.length - 1]
        if (t.rect.left >= last.rect.left + last.rect.width - 0.001) { row.push(t); placed = true; break }
      }
      if (!placed) rows.push([t])
    }
    return rows
  }

  // PREGATIREA NU SE INTRODUCE — E GOLUL.
  // Ion: „perioada pana la implementare este perioada de pregatire (…) apoi de la
  // o etapa de implementare la alta la fel este pregatire."
  // Deci nu e un lucru pe care il tastezi, e complementul etapelor: golul de
  // dinaintea primei etape si golurile DINTRE etape. Ion, 2026-07-30: „dupa ultima
  // perioada de implementare nu mai exista perioada de pregatire" — banda nu mai
  // curge pana la marginea ferestrei. Segment DESCHIS la dreapta rămâne un singur
  // caz: nicio etapa fixata, deci tot ce se vede e pregatire pentru o implementare
  // pe care inca n-o sti.
  function segmentePregatire(lane) {
    // Un proiect inchis nu mai pregateste nimic.
    if (lane.tip !== 'proiect' || lane.status === 'finalizat') return []
    // Golul e rupt DOAR de implementari. O zi de pregatire blocata explicit
    // (ex. „Parametrizare atelier", la sediu) face parte din pregatire, nu o
    // intrerupe — se deseneaza peste banda, ca bara plina.
    const etape = (lane.implementari || [])
      .filter(im => im.data_start && (im.faza || 'implementare') === 'implementare')
      .map(im => ({ a: im.data_start.slice(0, 10), b: (im.data_sfarsit || im.data_start).slice(0, 10) }))
      .sort((x, y) => x.a.localeCompare(y.a))
    // De cand se pregateste, nu se mai sti: `data_incepere` a plecat in v36, iar
    // `prima_zi` (min al perioadelor) e chiar prima etapa — pornind de acolo,
    // pregatirea dinaintea primei implementari ar avea latime zero. Deci pornim de
    // la marginea ferestrei: pregatirea e in curs, chiar daca nu stim de cand —
    // iar banda taiata la stanga spune exact asta.
    const inceput = plan.start
    if (!inceput) return []
    const out = []
    let cursor = inceput
    for (const e of etape) {
      // Capatul nesigur e cel din STANGA, nu cel din dreapta: ziua in care s-a
      // apucat de pregatire nu se sti, in timp ce ziua din dreapta e o data reala
      // — prima zi de implementare. Un gol DINTRE doua etape are amandoua capetele
      // sigure (a doua zi dupa etapa precedenta), deci nu se estompeaza.
      if (cursor < e.a) out.push({ de: cursor, la: addDays(e.a, -1), deschis: false, nesigurStart: cursor === plan.start })
      if (e.b >= cursor) cursor = addDays(e.b, 1)
    }
    // Nicio etapa fixata: toata fereastra e pregatire — nesigura la ambele capete.
    // Cand exista etape, ultima INCHEIE pregatirea: nu mai desenam nimic dupa ea.
    if (etape.length === 0) out.push({ de: cursor, la: '', deschis: true, nesigurStart: true })
    return out
  }

  // DOUA PERIOADE LIPITE, DE ACEEASI CATEGORIE, SUNT UNA.
  // Ion, 2026-07-30: „daca sunt doua perioade de implementare de aceeasi categorie
  // pe acelasi proiect, adica doua de site sau doua de birou, sa se contopeasca.
  // Daca sunt diferite atunci trebuie sa se deosebeasca."
  // Contopim doar ce se ATINGE (sau se suprapune): un gol intre doua perioade e
  // pregatire, deci nu poate fi inghitit de banda. „Categorie" = locatie SI faza:
  // o zi de pregatire la sediu si o etapa de implementare la sediu arata diferit
  // (palid vs plin), deci nu pot fi acelasi bloc.
  function contopeste(impls) {
    const ord = (impls || [])
      .filter(im => im.data_start)
      .map(im => ({
        ...im,
        faza: im.faza || 'implementare',
        a: im.data_start.slice(0, 10),
        b: (im.data_sfarsit || im.data_start).slice(0, 10),
      }))
      .sort((x, y) => x.a.localeCompare(y.a) || x.b.localeCompare(y.b))
    const out = []
    for (const im of ord) {
      const last = out[out.length - 1]
      if (last && last.locatie === im.locatie && last.faza === im.faza && im.a <= addDays(last.b, 1)) {
        if (im.b > last.b) last.b = im.b
        last.parti.push(im)
      } else {
        out.push({ ...im, parti: [im] })
      }
    }
    // O singura eticheta per banda, chiar cand s-au contopit mai multe perioade:
    // etichetele distincte, in ordine, separate ca in restul aplicatiei.
    return out.map(im => ({
      ...im,
      eticheta: [...new Set(im.parti.map(p => p.eticheta).filter(Boolean))].join(' · '),
      zile: (dayDiff(im.a, im.b) || 0) + 1,
    }))
  }

  const views = $derived(plan.lanes.map((lane) => {
    const color = laneColor(lane.id)
    // Segmentele de pregatire, decupate pe fereastra vizibila. Cele deschise se
    // intind pana la marginea din dreapta si primesc muchie estompata.
    const pregatire = segmentePregatire(lane)
      .map(seg => {
        const capat = seg.deschis ? addDays(plan.start, plan.days) : seg.la
        const rect = spanRect(seg.de, capat, plan.start, plan.days)
        return rect ? { ...seg, rect } : null
      })
      .filter(Boolean)
    const tasks = lane.tasks.map(t => ({
      ...t,
      rect: spanRect(effDue(t), effDue(t), plan.start, plan.days),
    }))
    const impl = contopeste(lane.implementari)
      .map(im => ({ ...im, rect: spanRect(im.a, im.b, plan.start, plan.days) }))
      .filter(im => im.rect)
    return { ...lane, color, pregatire, tasks, packed: packRows(tasks), impl }
  }))
  function locLabel(l) { return l === 'sediu' ? 'Sediu EGB' : 'Site' }

  // --- action popover (desktop) ---
  let sel = $state(null)
  let anchorEl = null
  let popX = $state(0)
  let popY = $state(0)

  function openPopover(barEl, task, laneNume) {
    anchorEl = barEl
    const r = barEl.getBoundingClientRect()
    popX = Math.max(8, Math.min(r.left, window.innerWidth - 268))
    popY = Math.min(r.bottom + 6, window.innerHeight - 230)
    sel = { ...task, laneNume }
  }
  function closePop() { sel = null; anchorEl = null }

  function openTask(t, srcEl) {
    const el = srcEl || anchorEl
    const task = t || sel
    if (!task) return
    closePop()
    if (task.tip === 'proiect' && task.proiect_id) morphNavigate(el, `/projects/${task.proiect_id}`, 'task', task.id)
    else morphNavigate(el, '/tasks', 'global', task.id)
  }

  async function onMove(t, v) {
    if (!v) return
    try {
      await moveTaskDate(t.tip, t.id, v)
      toast(`Mutat pe ${formatDate(v)}`, 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    closePop()
  }
  async function onTomorrow(t) {
    try { await moveTaskTomorrow(t.tip, t.id); toast('Mutat pe mâine', 'success') }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    closePop()
  }
  async function onDone(t) {
    try {
      const res = await toggleTaskDone(t.tip, t.id, t.status)
      if (res?.recurring_spawned) toast(`Finalizat ✓ — următoarea: ${formatDate(res.recurring_next)}`, 'success')
      else toast(isDone(t.status) ? 'Redeschis' : 'Finalizat ✓', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    closePop()
  }

  function onKey(e) { if (e.key === 'Escape') closePop() }

  /** Punct din banda -> randul lui din lista de dedesubt.
   *  Pe desktop, clickul pe o bara deschide un popover cu actiuni. Pe telefon
   *  actiunile sunt DEJA pe rand, iar un popover peste o banda de 22px ar fi al
   *  treilea loc in care apare acelasi task. Deci punctul nu deschide nimic: te
   *  duce la rand si il aprinde scurt, ca sa vezi care e (`focus-flash` e aceeasi
   *  animatie folosita cand aterizezi pe un task venind din alta pagina). */
  function arata(t) {
    const el = document.querySelector(`.mrow[data-rand="${t.tip}:${t.id}"]`)
    if (!el) return
    el.style.scrollMarginTop = 'calc(var(--header-height) + 46px)'
    el.scrollIntoView({ behavior: motion.reduced ? 'auto' : 'smooth', block: 'center' })
    el.classList.remove('focus-flash')
    void el.offsetWidth   // reporneste animatia daca atingi acelasi punct de doua ori
    el.classList.add('focus-flash')
    setTimeout(() => el.classList.remove('focus-flash'), 1700)
  }

  // --- drag / resize (desktop swimlane) ---
  let drag = null
  let dragLabel = $state(null)

  function startDrag(e, t, mode, laneNume) {
    if (e.button != null && e.button !== 0) return
    if (isDone(t.status)) return // finished tasks are read-only on the timeline
    const barEl = e.currentTarget.closest('.bar')
    const trackEl = barEl?.closest('.lane-track')
    if (!barEl || !trackEl) return
    const w = trackEl.getBoundingClientRect().width
    drag = {
      t, mode, barEl, laneNume,
      startX: e.clientX,
      dayW: w / plan.days,
      unit: 100 / plan.days,
      origLeft: parseFloat(barEl.style.left) || 0,
      origWidth: parseFloat(barEl.style.width) || 0,
      effDelta: 0, moved: false,
    }
    barEl.setPointerCapture?.(e.pointerId)
    document.body.classList.add('plan-dragging')
    window.addEventListener('pointermove', onDragMove)
    window.addEventListener('pointerup', onDragUp)
    e.preventDefault(); e.stopPropagation()
  }

  // Un task e o ZI, nu un interval (v33): la tragere se muta termenul.
  function previewText(d) {
    const base = (d.t.data_scadenta || '').slice(0, 10)
    return base ? `termen ${formatDateShort(addDays(base, d.effDelta))}` : ''
  }

  function onDragMove(e) {
    if (!drag) return
    const dx = e.clientX - drag.startX
    if (Math.abs(dx) > 3) drag.moved = true
    const dd = Math.round(dx / drag.dayW)
    const u = drag.unit
    const el = drag.barEl
    if (drag.mode === 'move') {
      const want = clampNum(drag.origLeft + dd * u, 0, 100 - drag.origWidth)
      el.style.left = want + '%'
      drag.effDelta = Math.round((want - drag.origLeft) / u)
    }
    dragLabel = { x: e.clientX, y: e.clientY, text: previewText(drag) }
  }

  function commitBody(d) {
    const base = (d.t.data_scadenta || '').slice(0, 10)
    const body = {}
    if (base) body.data_scadenta = addDays(base, d.effDelta)
    return body
  }

  async function onDragUp() {
    window.removeEventListener('pointermove', onDragMove)
    window.removeEventListener('pointerup', onDragUp)
    document.body.classList.remove('plan-dragging')
    const d = drag
    drag = null
    dragLabel = null
    if (!d) return
    if (!d.moved || d.effDelta === 0) {
      d.barEl.style.left = d.origLeft + '%'
      d.barEl.style.width = d.origWidth + '%'
      openPopover(d.barEl, d.t, d.laneNume)
      return
    }
    try {
      await setTaskDates(d.t.tip, d.t.id, commitBody(d))
      toast('Reprogramat', 'success')
    } catch (err) {
      toast(`Eroare: ${err.message}`, 'error')
      await loadPlan()
    }
  }

  // --- backlog rail + drag-to-schedule (HTML5 DnD onto the timeline) ---
  let backlogOpen = $state(true)
  let dragTask = null
  let dropDay = $state(null) // {idx, pct, iso} live indicator while dragging

  function backlogDragStart(e, t) {
    dragTask = t
    e.dataTransfer.effectAllowed = 'move'
    try { e.dataTransfer.setData('text/plain', t.id) } catch (_) {}
  }
  function backlogDragEnd() { dragTask = null; dropDay = null }

  function dayFromEvent(e) {
    const body = e.currentTarget
    const rect = body.getBoundingClientRect()
    const laneW = parseFloat(getComputedStyle(body).getPropertyValue('--lane-w')) || 240
    const trackW = rect.width - laneW
    if (trackW <= 0) return null
    const x = e.clientX - rect.left - laneW
    const frac = clampNum(x / trackW, 0, 0.9999)
    const idx = Math.floor(frac * plan.days)
    return { idx, pct: (idx / plan.days) * 100, iso: addDays(plan.start, idx) }
  }
  function onBodyDragOver(e) {
    if (!dragTask) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    dropDay = dayFromEvent(e)
  }
  async function onBodyDrop(e) {
    if (!dragTask) return
    e.preventDefault()
    const d = dayFromEvent(e)
    const t = dragTask
    dragTask = null; dropDay = null
    if (!d) return
    try { await scheduleBacklog(t.tip, t.id, d.iso); toast(`Planificat pe ${formatDate(d.iso)}`, 'success') }
    catch (err) { toast(`Eroare: ${err.message}`, 'error') }
  }
  async function scheduleFromPicker(t, v) {
    if (!v) return
    try { await scheduleBacklog(t.tip, t.id, v); toast(`Planificat pe ${formatDate(v)}`, 'success') }
    catch (err) { toast(`Eroare: ${err.message}`, 'error') }
  }

  // --- PDF export via the browser's print-to-PDF ---
  let showExport = $state(false)
  let exportSel = $state(new Set()) // lane ids to include
  let exportPageBreak = $state(false)
  let savedTheme = null

  const projectLanes = $derived(plan.lanes)

  function openExport() {
    exportSel = new Set(plan.lanes.map(l => l.id)) // default: all
    showExport = true
  }
  function toggleExportLane(id) {
    const next = new Set(exportSel)
    if (next.has(id)) next.delete(id); else next.add(id)
    exportSel = next
  }
  function toggleExportAll() {
    exportSel = exportSel.size === plan.lanes.length ? new Set() : new Set(plan.lanes.map(l => l.id))
  }

  function runExport() {
    showExport = false
    const root = document.documentElement
    savedTheme = root.getAttribute('data-theme')
    root.setAttribute('data-theme', 'light') // print on paper-light regardless of app theme
    document.body.classList.add('plan-printing')
    if (exportPageBreak) document.body.classList.add('plan-pagebreak')
    // let the DOM settle (theme + hide classes) before opening the dialog
    setTimeout(() => window.print(), 80)
  }
  function afterPrint() {
    document.body.classList.remove('plan-printing', 'plan-pagebreak')
    const root = document.documentElement
    if (savedTheme) root.setAttribute('data-theme', savedTheme)
    else root.removeAttribute('data-theme')
    savedTheme = null
  }

  const exportRange = $derived(
    plan.start ? `${formatDate(plan.start)} – ${formatDate(addDays(plan.start, plan.days - 1))}` : ''
  )

  onMount(() => {
    loadPlan()
    window.addEventListener('keydown', onKey)
    window.addEventListener('afterprint', afterPrint)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('afterprint', afterPrint)
    }
  })
</script>

<div class="page">
  <div class="page-header">
    <div class="page-title-row">
      <CalendarRange size={22} />
      <h1>Planificator</h1>
    </div>
    <div class="controls">
      <div class="seg" role="group" aria-label="Orizont">
        {#each HORIZONS as h}
          <button class="seg-btn" class:active={plan.days === h.d} onclick={() => setHorizon(h.d)}>{h.l}</button>
        {/each}
      </div>
      <button class="toggle" class:on={plan.showWeekends} disabled={unit !== 'day'} onclick={toggleWeekends} title={unit === 'day' ? 'Evidențiază weekendurile' : 'Weekendurile apar doar în vederea pe zile'}>
        <span class="tk-box">{#if plan.showWeekends}<Check size={12} />{/if}</span> Weekend
      </button>
      <button class="toggle" class:on={plan.showDone} onclick={toggleShowDone} title="Arată taskurile finalizate">
        <span class="tk-box">{#if plan.showDone}<Check size={12} />{/if}</span> Finalizate
      </button>
      <button class="toggle export" onclick={openExport} disabled={plan.lanes.length === 0} title="Exportă ca PDF (print)">
        <FileDown size={14} /> <span class="tg-lung">Export </span>PDF
      </button>
    </div>
  </div>

  {#if plan.loading && plan.lanes.length === 0}
    <div class="skel">{#each Array(4) as _}<Skeleton height="72px" />{/each}</div>
  {:else if plan.error}
    <ErrorState message={plan.error} onretry={loadPlan} />
  {:else if views.length === 0}
    <EmptyState icon={CalendarRange} title="Nimic în această fereastră" description="Planifică taskuri (din Astăzi sau din proiecte) ca să apară aici pe zile." />
  {:else}
    <!-- ===== Desktop swimlane ===== -->
    <div class="print-title">Planificator · {exportRange}</div>
    <div class="chart">
      <div class="chart-scroll">
        <div class="inner" style="min-width: {contentMin}px">
          <div class="p-head">
            <div class="lane-label head">Proiect</div>
            <div class="days">
              {#each columns.cols as c (c.key)}
                <div class="col-head" class:we={unit === 'day' && plan.showWeekends && c.isWeekend} class:today={c.iso && c.iso === plan.today} class:compact={dayCompact}
                     style="left:{c.leftPct}%; width:{c.widthPct}%">
                  {#if !(dayCompact && unit === 'day')}<span class="ch-sub">{c.sub}</span>{/if}
                  <span class="ch-main">{c.main}</span>
                </div>
              {/each}
            </div>
          </div>

          <div class="p-body" class:drop-active={!!dragTask} ondragover={onBodyDragOver} ondrop={onBodyDrop} role="presentation">
            <div class="overlay">
              {#each columns.cols as c (c.key)}
                <div class="col-line" style="left:{c.leftPct}%"></div>
                {#if unit === 'day' && plan.showWeekends && c.isWeekend}<div class="col-we" style="left:{c.leftPct}%; width:{c.widthPct}%"></div>{/if}
                {#if c.iso && c.iso === plan.today}<div class="col-today" style="left:{c.leftPct}%; width:{c.widthPct}%"></div>{/if}
              {/each}
              {#if todayPct != null && todayPct >= 0 && todayPct < 100}
                <div class="today-line" style="left:{todayPct}%"></div>
              {/if}
              {#if dropDay}
                <div class="drop-line" style="left:{dropDay.pct}%"></div>
                <div class="drop-tag" style="left:{dropDay.pct}%">{formatDateShort(dropDay.iso)}</div>
              {/if}
            </div>

            {#each views as lane (lane.tip + ':' + lane.id)}
              <div class="lane" style="--lane:{lane.color}" class:print-hide={exportSel.size > 0 && !exportSel.has(lane.id)}>
                <div class="lane-label">
                  {#if lane.tip === 'proiect'}
                    <button class="lane-name" onclick={(e) => morphNavigate(e.currentTarget, `/projects/${lane.id}`, 'project', lane.id)} title={lane.nume}>
                      <span class="lane-dot"></span>
                      <span class="lane-txt">{lane.nume}</span>
                    </button>
                    {#if lane.tip_proiect}<span class="tip-chip" class:svc={lane.tip_proiect === 'Service'}>{lane.tip_proiect}</span>{/if}
                  {:else}
                    <span class="lane-name static"><span class="lane-dot"></span><span class="lane-txt">{lane.nume}</span></span>
                  {/if}
                </div>
                <div class="lane-track">
                  {#each lane.pregatire as seg, i (i)}
                    <div class="band" class:clipL={seg.rect.clippedLeft} class:clipR={seg.rect.clippedRight}
                         class:deschis={seg.deschis} class:deschisL={seg.nesigurStart}
                         style="left:{seg.rect.left}%; width:{seg.rect.width}%"
                         title="Pregătire{seg.deschis ? ' — următoarea etapă nu e încă fixată' : ` · ${formatDateShort(seg.de)} – ${formatDateShort(seg.la)}`}"></div>
                  {/each}
                  <!-- Perioada nu e un rand pe langa taskuri — e banda randului, pe
                       toata inaltimea, ca pregatirea (Ion, 2026-07-30). Cele doua
                       benzi paveaza acelasi rand: gol = pregatire, plin = pe teren.
                       Taskurile se deseneaza PESTE. Perioadele se EDITEAZA in
                       Calendar, nu aici — clickul te duce la ziua ei. -->
                  {#each lane.impl as im (im.id)}
                    <button class="impl-band loc-{im.locatie}" style="left:{im.rect.left}%; width:{im.rect.width}%"
                         class:pregatire={im.faza === 'pregatire'} class:doar-ico={im.rect.width < BANDA_TEXT_MIN}
                         class:clipL={im.rect.clippedLeft} class:clipR={im.rect.clippedRight}
                         onclick={() => navigate(`/calendar?zi=${im.a}`)}
                         title="{locLabel(im.locatie)}{im.eticheta ? ' · ' + im.eticheta : ''} · {im.faza === 'pregatire' ? 'pregătire' : 'implementare'} · {formatDateShort(im.a)} → {formatDateShort(im.b)} · {im.zile} {im.zile === 1 ? 'zi' : 'zile'}{im.parti.length > 1 ? ` · ${im.parti.length} perioade lipite` : ''} · click pentru a o vedea în Calendar">
                      {#if im.locatie === 'sediu'}<Building2 size={12} class="ib-ico" />{:else}<MapPin size={12} class="ib-ico" />{/if}
                      {#if im.rect.width >= BANDA_TEXT_MIN}
                        <span class="ib-txt">{locLabel(im.locatie)}{im.eticheta ? ' · ' + im.eticheta : ''}</span>
                      {/if}
                      {#if im.rect.width >= BANDA_ZILE_MIN}<span class="ib-zile">{im.zile} {im.zile === 1 ? 'zi' : 'zile'}</span>{/if}
                    </button>
                  {/each}
                  <div class="rows">
                    {#each lane.packed as row, ri (ri)}
                      <div class="t-row">
                        {#each row as t (t.tip + ':' + t.id)}
                          <div
                            class="bar"
                            class:active={isActive(t.status)}
                            class:todo={!isActive(t.status) && !isDone(t.status)}
                            class:done={isDone(t.status)}
                            class:urgent={zilePanaLa(t.data_scadenta) !== null && zilePanaLa(t.data_scadenta) < 0}
                            class:single={t.rect.single}
                            class:flip={t.rect.single && t.rect.left > 62}
                            class:draggable={!isDone(t.status)}
                            style="left:{t.rect.left}%; width:{t.rect.width}%"
                            role="button"
                            tabindex="0"
                            onpointerdown={(e) => startDrag(e, t, 'move', lane.nume)}
                            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPopover(e.currentTarget, t, lane.nume) } }}
                            title="{t.titlu}{t.data_scadenta ? ' · termen ' + formatDateShort(t.data_scadenta) : ''}"
                          >
                            {#if !isDone(t.status) && !t.rect.single}
                            {/if}
                            {#if t.rect.single}<span class="pin-dot"></span>{/if}
                            <span class="bar-txt">{t.titlu}</span>
                            {#if t.recurenta}<Repeat size={11} />{/if}
                            {#if !isDone(t.status)}
                              <!-- taskurile de o zi capătă doar mânerul din dreapta (alungire); mutarea rămâne pe pin -->
                            {/if}
                          </div>
                        {/each}
                      </div>
                    {/each}
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      </div>
      <p class="hint">Trage o bară de task ca s-o muți · trage marginile ca să întinzi intervalul · click pentru acțiuni · benzile de perioadă se editează în Calendar</p>
    </div>

    <!-- ===== Backlog (taskuri fără termen) ===== -->
    {#if plan.backlog.length > 0}
      <section class="backlog" class:open={backlogOpen}>
        <button class="bl-head" onclick={() => backlogOpen = !backlogOpen} aria-expanded={backlogOpen}>
          <Inbox size={16} />
          <h2>Taskuri fără termen</h2>
          <span class="bl-count">{plan.backlog.length}</span>
          <span class="bl-hint">trage pe o zi ca să planifici</span>
          <ChevronRight size={16} class="bl-chev" />
        </button>
        {#if backlogOpen}
          <div class="bl-items">
            {#each plan.backlog as t (t.tip + ':' + t.id)}
              <div class="bl-chip" class:urgent={zilePanaLa(t.data_scadenta) !== null && zilePanaLa(t.data_scadenta) < 0}
                   draggable="true" ondragstart={(e) => backlogDragStart(e, t)} ondragend={backlogDragEnd}
                   title={t.titlu}>
                <GripVertical size={13} class="bl-grip" />
                <span class="bl-txt">{t.titlu}</span>
                {#if t.proiect_nume}<span class="bl-proj">{t.proiect_nume}</span>{:else if t.categorie}<span class="bl-proj glob">{t.categorie}</span>{/if}
                <span class="bl-date"><DatePicker value="" placeholder="Planifică" onchange={(v) => scheduleFromPicker(t, v)} /></span>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    <!-- ===== Mobile grouped list ===== -->
    <div class="mlist">
      <!-- ANTETUL DE ZILE, COMUN SI LIPICIOS.
           Fara el, benzile de mai jos ar fi N grafice fara legatura: fiecare
           frumoasa in sine, niciuna comparabila cu vecina. Fiind acelasi interval
           si aceeasi scara pentru toate, o coloana inseamna aceeasi zi peste tot,
           iar derularea pe verticala devine exact ce facea ochiul pe desktop cand
           coborai de la un lane la altul. -->
      <div class="m-scale">
        <div class="ms-cols">
          {#each columns.cols as c (c.key)}
            <span class="ms-c" class:we={unit === 'day' && plan.showWeekends && c.isWeekend}
                  class:today={c.iso && c.iso === plan.today}
                  style="left:{c.leftPct}%; width:{c.widthPct}%">{c.main}</span>
          {/each}
        </div>
      </div>

      {#each views as lane (lane.tip + ':' + lane.id)}
        <section class="mgroup" style="--lane:{lane.color}">
          <header class="mg-head">
            <span class="lane-dot"></span>
            <h2>{lane.nume}</h2>
            {#if lane.tip_proiect}<span class="tip-chip" class:svc={lane.tip_proiect === 'Service'}>{lane.tip_proiect}</span>{/if}
            <span class="mg-count">{lane.tasks.length}</span>
          </header>

          <!-- BANDA = LANE-UL DE PE DESKTOP, INTORS LA LATIME PLINA.
               Pe desktop numele sta la STANGA si timpul se intinde in dreapta lui;
               pe un ecran de 375px coloana de nume ar manca doua treimi, de aceea
               swimlane-ul era pur si simplu ascuns si ramanea o lista fara timp.
               Numele urca deasupra, banda ia toata latimea, iar grupurile se
               stivuiesc pe verticala — directia in care telefonul chiar are loc.
               Geometria e aceeasi: `spanRect` da procente, deci merge la orice
               latime, fara niciun calcul nou. -->
          <div class="m-track">
            {#each columns.cols as c (c.key)}
              {#if unit === 'day' && plan.showWeekends && c.isWeekend}
                <div class="mt-we" style="left:{c.leftPct}%; width:{c.widthPct}%"></div>
              {/if}
            {/each}
            {#each lane.pregatire as seg, i (i)}
              <div class="band" class:clipL={seg.rect.clippedLeft} class:clipR={seg.rect.clippedRight}
                   class:deschis={seg.deschis} class:deschisL={seg.nesigurStart}
                   style="left:{seg.rect.left}%; width:{seg.rect.width}%"></div>
            {/each}
            {#each lane.impl as im (im.id)}
              <button class="impl-band loc-{im.locatie}" style="left:{im.rect.left}%; width:{im.rect.width}%"
                      class:pregatire={im.faza === 'pregatire'}
                      class:clipL={im.rect.clippedLeft} class:clipR={im.rect.clippedRight}
                      onclick={() => navigate(`/calendar?zi=${im.a}`)}
                      title="{locLabel(im.locatie)}{im.eticheta ? ' · ' + im.eticheta : ''} · {formatDateShort(im.a)} → {formatDateShort(im.b)}">
                {#if im.locatie === 'sediu'}<Building2 size={11} class="ib-ico" />{:else}<MapPin size={11} class="ib-ico" />{/if}
                {#if im.rect.width >= BANDA_TEXT_MIN}
                  <span class="ib-txt">{im.eticheta || locLabel(im.locatie)}</span>
                {/if}
              </button>
            {/each}
            <!-- Un task e un REPER de o zi (v33), deci un punct — nu o bara pe
                 care s-o intinzi. Atingerea nu deschide un al treilea meniu: te
                 duce la randul lui din lista de dedesubt, unde stau deja toate
                 actiunile. Punctul spune CAND, randul spune CE si CU CE butoane. -->
            {#each lane.tasks as t (t.tip + ':' + t.id)}
              {#if t.rect}
                <button class="mt-pin" class:done={isDone(t.status)}
                        class:urgent={zilePanaLa(t.data_scadenta) !== null && zilePanaLa(t.data_scadenta) < 0}
                        style="left:{t.rect.left}%"
                        onclick={() => arata(t)}
                        title="{t.titlu}{t.data_scadenta ? ' · termen ' + formatDateShort(t.data_scadenta) : ''}"
                        aria-label="{t.titlu} — vezi în listă"></button>
              {/if}
            {/each}
            {#if todayPct != null && todayPct >= 0 && todayPct < 100}
              <div class="mt-azi" style="left:{todayPct}%"></div>
            {/if}
          </div>

          <!-- Randul perioadei e si tinta ei: in banda de 26px un bloc de doua
               zile are 23×20px, adica prea putin ca sa-l nimeresti. Aici are
               latimea intreaga si duce in Calendar, unde perioadele se editeaza. -->
          {#each lane.impl as im (im.id)}
            <button class="mimpl loc-{im.locatie}" class:pregatire={im.faza === 'pregatire'}
                    onclick={() => navigate(`/calendar?zi=${im.a}`)}
                    title="Vezi în Calendar">
              <span class="mimpl-loc">{locLabel(im.locatie)}{im.eticheta ? ' · ' + im.eticheta : ''}</span>
              <span class="mimpl-range">{formatDateShort(im.a)} – {formatDateShort(im.b)}</span>
            </button>
          {/each}
          {#each lane.tasks as t (t.tip + ':' + t.id)}
            <!-- Acelasi rand ca pe „Astazi": o linie, bifa in stanga, actiunile
                 in panoul de sub el (glisare spre stanga). Doua liste care arata
                 acelasi lucru trebuie sa se poarte la fel — altfel inveti gestul
                 de doua ori. -->
            <div class="mrow" data-rand="{t.tip}:{t.id}"
                 class:urgent={zilePanaLa(t.data_scadenta) !== null && zilePanaLa(t.data_scadenta) < 0} class:done={isDone(t.status)}
                 use:glisare={{ latime: 118, activ: true, onBifa: isDone(t.status) ? null : () => onDone(t) }}>
              <div class="gl-actiuni">
                <button class="glb" onclick={() => onTomorrow(t)} title="Mută pe mâine"><ArrowRight size={17} /><span>Mâine</span></button>
                <span class="glb datewrap" title="Mută pe altă zi">
                  <DatePicker value={t.data_scadenta} placeholder="Dată" onchange={(v) => onMove(t, v)} />
                  <span>Dată</span>
                </span>
              </div>
              <div class="gl-fata">
                <button class="mcheck" onclick={() => onDone(t)} title="Bifează">
                  {#if isDone(t.status)}<CheckCircle2 size={18} />{:else}<span class="mcheck-gol"></span>{/if}
                </button>
                <button class="mrow-main" onclick={(e) => openTask(t, e.currentTarget)}>
                  <span class="mrow-title">{t.titlu}</span>
                  <span class="mrow-meta">
                    {#if t.data_scadenta}<span class="chip due">termen {formatDateShort(t.data_scadenta)}</span>{/if}
                    {#if t.recurenta}<span class="chip"><Repeat size={10} /> {t.recurenta}</span>{/if}
                  </span>
                </button>
                <div class="mrow-actions">
                  <button class="mbtn" onclick={() => onTomorrow(t)} title="Mută pe mâine"><ArrowRight size={15} /></button>
                  <span class="mrow-date"><DatePicker value={t.data_scadenta} placeholder="Mută" onchange={(v) => onMove(t, v)} /></span>
                  <button class="mbtn" onclick={() => onDone(t)} title="Bifează"><CheckCircle2 size={16} /></button>
                </div>
              </div>
            </div>
          {/each}
        </section>
      {/each}
    </div>
  {/if}
</div>

{#if dragLabel}
  <div class="drag-label" style="left:{dragLabel.x + 14}px; top:{dragLabel.y - 34}px">{dragLabel.text}</div>
{/if}

{#if sel}
  <div class="pop-backdrop" onclick={closePop} role="presentation"></div>
  <div class="pop" style="left:{popX}px; top:{popY}px" role="dialog" aria-label="Acțiuni task">
    <div class="pop-title">{sel.titlu}</div>
    <div class="pop-meta">
      {#if sel.laneNume}<span>{sel.laneNume}</span>{/if}
      {#if sel.data_scadenta}<span class="pm-due">termen {formatDate(sel.data_scadenta)}</span>{/if}
    </div>
    <button class="pop-act" onclick={() => openTask(sel)}><ExternalLink size={15} /> Deschide</button>
    <div class="pop-act datewrap">
      <span class="pa-ico"><CalendarRange size={15} /></span>
      <span class="pa-label">Mută pe…</span>
      <DatePicker value={sel.data_scadenta} placeholder="alege" onchange={(v) => onMove(sel, v)} />
    </div>
    <button class="pop-act" onclick={() => onTomorrow(sel)}><ArrowRight size={15} /> Mută pe mâine</button>
    <button class="pop-act" onclick={() => onDone(sel)}><CheckCircle2 size={15} /> {isDone(sel.status) ? 'Redeschide' : 'Bifează'}</button>
    <button class="pop-close" onclick={closePop} aria-label="Închide"><X size={14} /></button>
  </div>
{/if}

<Modal bind:open={showExport} title="Export PDF" size="sm">
  <div class="exp">
    <p class="exp-note">Se deschide dialogul de printare al browserului — alege <b>„Salvează ca PDF"</b>. Fereastra exportată: <b>{exportRange}</b>.</p>
    <div class="exp-scope">
      <div class="exp-scope-head">
        <span>Proiecte</span>
        <button class="exp-all" onclick={toggleExportAll}>{exportSel.size === plan.lanes.length ? 'Deselectează' : 'Toate'}</button>
      </div>
      <div class="exp-list">
        {#each plan.lanes as l (l.tip + ':' + l.id)}
          <label class="exp-row">
            <input type="checkbox" checked={exportSel.has(l.id)} onchange={() => toggleExportLane(l.id)} />
            <span class="exp-dot" style="background:{laneColor(l.id)}"></span>
            <span class="exp-name">{l.nume}</span>
          </label>
        {/each}
      </div>
    </div>
    <label class="exp-opt">
      <input type="checkbox" bind:checked={exportPageBreak} />
      <span>Câte un proiect pe pagină</span>
    </label>
  </div>
  {#snippet footer()}
    <div class="modal-actions">
      <button class="btn-ghost" onclick={() => showExport = false}>Anulează</button>
      <button class="btn-primary" onclick={runExport} disabled={exportSel.size === 0}><FileDown size={14} /> Exportă</button>
    </div>
  {/snippet}
</Modal>

<style>
  .page { padding-bottom: 96px; }
  .page-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); margin-bottom: var(--space-md); flex-wrap: wrap; }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-h1); font-weight: var(--fw-bold); font-family: var(--font-heading); letter-spacing: -0.02em; }
  .controls { display: flex; align-items: center; gap: var(--space-sm); }
  .seg { display: inline-flex; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 2px; }
  .seg-btn { padding: 5px 11px; border-radius: var(--radius-sm); font-size: var(--font-small); font-family: var(--font-mono); font-weight: var(--fw-medium); color: var(--text-dim); background: none; border: none; cursor: pointer; transition: color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease); }
  .seg-btn:hover { color: var(--text); }
  .seg-btn.active { background: var(--accent); color: var(--accent-text); }
  .toggle { display: inline-flex; align-items: center; gap: 7px; padding: 6px 12px; font-size: var(--font-small); font-weight: var(--fw-medium); border-radius: var(--radius-md); background: var(--bg-panel); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .toggle:hover { border-color: var(--border-strong); color: var(--text); }
  .toggle.on { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 45%, transparent); }
  .toggle:disabled { opacity: 0.4; cursor: not-allowed; }
  .tk-box { width: 16px; height: 16px; border-radius: 4px; border: 1.5px solid var(--border-strong); display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .toggle.on .tk-box { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }
  .skel { display: flex; flex-direction: column; gap: var(--space-sm); }

  /* ===== chart shell ===== */
  .chart { --lane-w: 240px; --day-min: 48px; --row-h: 28px;
    background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
  .chart-scroll { overflow-x: auto; }
  .inner { position: relative; }

  .p-head { display: flex; border-bottom: 1px solid var(--border-strong); background: var(--bg-overlay); position: sticky; top: 0; z-index: 3; }
  .lane-label { width: var(--lane-w); flex-shrink: 0; box-sizing: border-box; }
  .lane-label.head { padding: 8px 12px; font-family: var(--font-mono); font-size: var(--font-micro); letter-spacing: var(--tracking-wide); text-transform: uppercase; color: var(--text-dim); display: flex; align-items: center; }
  .days { flex: 1; position: relative; min-width: 0; height: 42px; }
  .col-head { position: absolute; top: 0; bottom: 0; padding: 6px 2px 7px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px; border-left: 1px solid var(--border); overflow: hidden; }
  .col-head.compact { padding: 5px 1px; }
  .col-head.we { background: color-mix(in srgb, var(--purple) 6%, transparent); }
  .col-head.today { background: var(--accent-subtle); }
  .ch-sub { font-size: var(--font-micro); color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.03em; white-space: nowrap; }
  .col-head.today .ch-sub { color: var(--accent); }
  .ch-main { font-family: var(--font-mono); font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .col-head.compact .ch-main { font-size: var(--font-tiny); }
  .col-head.today .ch-main { color: var(--accent); }

  .p-body { position: relative; }
  .overlay { position: absolute; top: 0; bottom: 0; left: var(--lane-w); right: 0; pointer-events: none; z-index: 0; }
  .col-line { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--border-subtle); }
  .col-we { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--purple) 5%, transparent); }
  .col-today { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--accent) 7%, transparent); }
  .today-line { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--danger); opacity: 0.75; }

  .lane { display: flex; border-bottom: 1px solid var(--border); min-height: calc(var(--row-h) + 14px); }
  .lane:last-child { border-bottom: 0; }
  .lane-label { padding: 8px 10px; display: flex; align-items: center; gap: 6px; border-right: 1px solid var(--border); background: var(--bg-surface); z-index: 1; }
  .lane-name { display: flex; align-items: flex-start; gap: 7px; min-width: 0; color: var(--text); cursor: pointer; background: none; border: none; text-align: left; font-size: var(--font-small); font-weight: var(--fw-medium); }
  .lane-name.static { cursor: default; }
  .lane-name:not(.static):hover .lane-txt { color: var(--accent); }
  .lane-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--lane); flex-shrink: 0; margin-top: 4px; box-shadow: 0 0 6px color-mix(in srgb, var(--lane) 55%, transparent); }
  /* Numele de proiect sunt lungi si se termina des cu acelasi client
     („… — Continental"), deci trunchierea pe un rand le facea identice: toate
     9 erau taiate. Doua randuri arata partea care le distinge. */
  .lane-txt { min-width: 0; line-height: 1.25; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
  .tip-chip { font-size: var(--font-micro); font-family: var(--font-mono); padding: 1px 6px; border-radius: var(--radius-chip); background: var(--accent-subtle); color: var(--accent); flex-shrink: 0; }
  .tip-chip.svc { background: color-mix(in srgb, var(--purple) 18%, transparent); color: var(--purple); }

  .lane-track { flex: 1; position: relative; min-width: 0; padding: 7px 0; }
  .band { position: absolute; top: 5px; bottom: 5px; border-radius: 8px;
    background: color-mix(in oklab, var(--lane) 13%, transparent);
    border: 1px solid color-mix(in oklab, var(--lane) 28%, transparent); z-index: 0; }
  .band.clipL { border-top-left-radius: 0; border-bottom-left-radius: 0; border-left: 0; }
  .band.clipR { border-top-right-radius: 0; border-bottom-right-radius: 0; border-right: 0; }
  /* CAPATUL NESIGUR SE STINGE, CEL SIGUR RAMANE NET.
     Nesigur e START-ul: nu exista o zi „de cand se pregateste" (v36). Capatul din
     dreapta e prima zi de implementare — data reala, deci muchie clara. Cand nu e
     fixata nicio etapa, si dreapta e nesigura, deci se sting amandoua. Estomparea
     e pe o distanta FIXA, ca sa arate la fel si pe o banda de trei zile si pe una
     de trei luni. */
  .band.deschisL { border-left: 0; border-top-left-radius: 0; border-bottom-left-radius: 0;
    -webkit-mask-image: linear-gradient(to right, transparent 0, #000 56px);
    mask-image: linear-gradient(to right, transparent 0, #000 56px); }
  .band.deschis { border-right: 0; border-top-right-radius: 0; border-bottom-right-radius: 0;
    -webkit-mask-image: linear-gradient(to left, transparent 0, #000 56px);
    mask-image: linear-gradient(to left, transparent 0, #000 56px); }
  .band.deschis.deschisL {
    -webkit-mask-image: linear-gradient(to right, transparent 0, #000 56px, #000 calc(100% - 56px), transparent 100%);
    mask-image: linear-gradient(to right, transparent 0, #000 56px, #000 calc(100% - 56px), transparent 100%); }
  /* Taskurile stau peste benzi, deci randurile lasa clickul sa treaca prin golul
     dintre bare pana la banda de dedesubt. */
  .rows { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 4px; pointer-events: none; }
  .t-row { position: relative; height: var(--row-h); }
  /* Perioada de implementare (Site / Sediu EGB) — banda pe toata inaltimea randului,
     exact insetul benzii de pregatire, ca cele doua sa se imbine fara decalaj.
     Palid = pregatire, plin = pe teren; culoarea spune unde (teal = site, gold =
     sediu), aceeasi gramatica vizuala ca in Calendar. */
  /* BLOC, nu pastila. Un bloc are volum (degrade fin sus→jos), o muchie de intrare
     (bara verticala din stanga = ziua in care ajungi acolo) si o umbra care il
     ridica peste banda de pregatire. Inelul interior tine doua blocuri lipite de
     categorii diferite despartite — doua perioade de aceeasi categorie sunt deja
     UN element (vezi `contopeste`), deci n-au cusatura. */
  .impl-band { position: absolute; top: 5px; bottom: 5px; display: flex; align-items: center; gap: 5px;
    padding: 0 9px; border-radius: 9px; overflow: hidden; z-index: 0; text-align: left; color: #10130f;
    border: none; border-left: 3px solid color-mix(in oklab, var(--il) 58%, #000);
    background: linear-gradient(180deg,
      color-mix(in oklab, var(--il) 88%, #fff) 0%, var(--il) 46%,
      color-mix(in oklab, var(--il) 90%, #000) 100%);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, #10130f 20%, transparent), 0 1px 3px rgba(0,0,0,0.28);
    cursor: pointer; pointer-events: auto; transition: filter var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
  .impl-band.loc-site { --il: #3f9dc4; } .impl-band.loc-sediu { --il: #c99a3a; }
  /* Faza e a doua axa, ca in Calendar: palid = pregatire, plin = implementare.
     O zi de pregatire blocata explicit (parametrizare in atelier) e tot pregatire,
     deci sta peste banda ei, cu conturul culorii, nu ca bloc plin. */
  .impl-band.pregatire { background: color-mix(in oklab, var(--il) 16%, transparent);
    border-left-color: color-mix(in oklab, var(--il) 70%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in oklab, var(--il) 45%, transparent);
    color: color-mix(in oklab, var(--il) 72%, var(--text)); }
  /* Taiata de fereastra: muchie dreapta, fara bara de intrare — ziua de start nu e
     acolo, e mai devreme. */
  .impl-band.clipL { border-top-left-radius: 0; border-bottom-left-radius: 0; border-left-width: 0; }
  .impl-band.clipR { border-top-right-radius: 0; border-bottom-right-radius: 0; }
  .impl-band:hover { filter: brightness(1.08);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, #10130f 20%, transparent),
                0 0 0 2px color-mix(in srgb, var(--bg-panel) 60%, transparent), 0 3px 10px rgba(0,0,0,0.34); }
  .impl-band :global(.ib-ico) { flex: none; opacity: 0.72; }
  /* O zi, la 30 de zile fereastra, are 38px: nu incape nici „Si…". Ramane icoana,
     centrata, si tot tooltipul. */
  .impl-band.doar-ico { padding: 0 2px; justify-content: center; }
  .ib-txt { font-size: var(--font-tiny); font-weight: var(--fw-semibold); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* Durata umple capatul liber al blocurilor late si spune cat stai acolo — pe
     benzile inguste n-ar incapea, deci nici nu se randeaza (vezi `rect.width`). */
  .ib-zile { flex: none; margin-left: auto; padding-left: 8px; font-family: var(--font-mono);
    font-size: var(--font-micro); font-variant-numeric: tabular-nums; opacity: 0.62; white-space: nowrap; }
  .mimpl { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; text-align: left; border: none; cursor: pointer; padding: 6px 10px; border-radius: var(--radius-md); border-left: 3px solid var(--mil); background: color-mix(in srgb, var(--mil) 12%, transparent); margin-bottom: 6px; }
  .mimpl.loc-site { --mil: #3f9dc4; } .mimpl.loc-sediu { --mil: #c99a3a; }
  /* Aceeasi a doua axa ca pe desktop: pregatirea e conturata, nu plina. */
  .mimpl.pregatire { background: none; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--mil) 32%, transparent); border-left-style: dashed; }
  .mimpl-loc { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--mil); }
  .mimpl-range { font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text-dim); }
  .bar { position: absolute; top: 0; bottom: 0; display: flex; align-items: center; gap: 4px;
    padding: 0 8px; border-radius: 7px; font-size: var(--font-tiny); font-weight: var(--fw-semibold);
    white-space: nowrap; overflow: hidden; cursor: pointer; text-align: left; touch-action: none;
    transition: box-shadow var(--dur-fast) var(--ease);
    animation: barIn 0.4s var(--ease) both; pointer-events: auto; }
  @keyframes barIn { from { opacity: 0; transform: scaleX(0.4); transform-origin: left; } }
  .bar.draggable { cursor: grab; }
  .bar:hover { box-shadow: var(--shadow-md); z-index: 5; }
  .bar.active { background: var(--lane); color: #14100a; }
  .bar.todo { background: color-mix(in oklab, var(--lane) 20%, var(--bg-panel));
    border: 1px solid color-mix(in oklab, var(--lane) 45%, var(--bg-panel));
    color: color-mix(in oklab, var(--lane) 70%, var(--text)); }
  .bar.done { background: color-mix(in oklab, var(--lane) 14%, var(--bg-panel));
    border: 1px dashed color-mix(in oklab, var(--lane) 40%, var(--bg-panel));
    color: var(--text-dim); opacity: 0.72; cursor: default; }
  .bar.done .bar-txt { text-decoration: line-through; }
  /* single-day task: a diamond marker + the title label beside it (label spills
     outside the 1-day-wide box), so it's readable without hovering. */
  .bar.single { overflow: visible; background: none; border: none; box-shadow: none;
    padding: 0; justify-content: flex-start; gap: 6px; }
  .bar.single.flip { flex-direction: row-reverse; }
  .bar.single .pin-dot { flex: none; width: 12px; height: 12px; transform: rotate(45deg);
    background: var(--lane); border: 1.5px solid var(--bg-surface);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--lane) 22%, transparent); }
  .bar.single.todo .pin-dot { background: color-mix(in oklab, var(--lane) 55%, var(--bg-panel)); }
  .bar.single.done .pin-dot { background: color-mix(in oklab, var(--lane) 30%, var(--bg-panel)); box-shadow: none; }
  /* Eticheta unui task de o zi pluteste peste fundal, fara cutie proprie — iar
     fundalul poate fi acum blocul plin al unei perioade. Haloul in culoarea
     suprafetei o desprinde de orice ar fi dedesubt, in ambele teme. */
  .bar.single .bar-txt { display: inline; max-width: 220px; color: var(--text);
    text-shadow: 0 0 3px var(--bg-surface), 0 0 6px var(--bg-surface), 0 0 9px var(--bg-surface); }
  .bar.single.done .bar-txt { color: var(--text-dim); text-decoration: line-through; }
  .bar.urgent { box-shadow: inset 3px 0 0 0 var(--danger); }
  .bar.single.urgent { box-shadow: none; }
  .bar.single.urgent .pin-dot { box-shadow: 0 0 0 2px color-mix(in srgb, var(--danger) 40%, transparent); }
  .bar-txt { overflow: hidden; text-overflow: ellipsis; pointer-events: none; }

  /* single-day task: right handle a touch wider + grip tinted so it reads on the
     transparent pin bar (extinde ziua într-un interval) */

  @media (prefers-reduced-motion: reduce) { .bar { animation: none; } }

  .hint { text-align: center; font-size: var(--font-micro); color: var(--text-faint); padding: 8px; border-top: 1px solid var(--border-subtle); }

  .drag-label { position: fixed; z-index: var(--z-tooltip); pointer-events: none; background: var(--bg-overlay);
    border: 1px solid var(--border-strong); border-radius: var(--radius-sm); padding: 3px 8px;
    font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text); box-shadow: var(--shadow-md); white-space: nowrap; }

  /* ===== mobile grouped list ===== */
  .mlist { display: none; flex-direction: column; gap: var(--space-md); }

  /* ANTETUL DE ZILE — lipit sub bara aplicatiei.
     Trebuie sa rămână vizibil cat derulezi, altfel benzile de mai jos nu mai au
     scara si redevin decor. `--m-pad` e insetul lateral al benzii dintr-un grup
     (marginea grupului + paddingul lui), ca sa cada coloana peste coloana. */
  /* `--m-pad` = rama grupului (1) + paddingul lui (8) + marginea benzii (3).
     Cele trei numere trebuie sa rămână in acord cu `.mgroup` si `.m-track`:
     daca antetul si banda nu incep exact in acelasi x, coloana „marti" cade
     langa ziua de marti, si tot graficul minte cu o zi. */
  .m-scale { --m-pad: 12px;
    position: sticky; top: var(--header-height); z-index: 4;
    padding: 6px var(--m-pad) 5px;
    background: color-mix(in srgb, var(--bg) 92%, transparent);
    -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border); border-radius: var(--radius-sm); }
  .ms-cols { position: relative; height: 14px; }
  .ms-c { position: absolute; top: 0; display: flex; align-items: center; justify-content: center;
    height: 14px; font-family: var(--font-mono); font-size: var(--font-micro);
    color: var(--text-faint); font-variant-numeric: tabular-nums;
    overflow: hidden; white-space: nowrap; border-left: 1px solid var(--border-subtle); }
  .ms-c.we { color: var(--purple); }
  .ms-c.today { color: var(--accent); font-weight: var(--fw-bold); }

  /* BANDA PROIECTULUI — acelasi continut ca lane-ul de pe desktop.
     Inaltimea e mica intentionat: e context, nu suprafata de lucru. Ce faci cu un
     task faci pe randul lui, dedesubt. */
  .m-track { position: relative; height: 26px; margin: 0 3px 8px; border-radius: var(--radius-sm);
    background: var(--bg-panel); box-shadow: inset 0 0 0 1px var(--border-subtle); overflow: hidden; }
  .mt-we { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--purple) 7%, transparent); }
  .mt-azi { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--danger); opacity: 0.8; z-index: 3; }
  /* Reperele stau PESTE benzi si sunt singurul lucru din banda pe care il atingi
     des, deci primesc o caseta transparenta de 26px in jurul punctului de 9px.
     Fara ea ai avea de nimerit un punct cat gamalia acului.
     26, NU 44, si ramane asa cu buna stiinta: pe un orizont de 14 zile o zi are
     ~22px, deci doua repere in zile alaturate ar ajunge sa se acopere unul pe
     altul — ai schimba o tinta mica pe una GRESITA, care deschide alt task. Iar
     pretul unei ratari e zero: reperul nu face decat sa te duca la randul
     taskului din lista de dedesubt, iar acel rand e cat toata latimea. */
  .mt-pin { position: absolute; top: 0; bottom: 0; width: 26px; margin-left: -13px;
    display: flex; align-items: center; justify-content: center;
    background: none; border: none; padding: 0; cursor: pointer; z-index: 2; }
  .mt-pin::before { content: ''; width: 9px; height: 9px; border-radius: 2px;
    background: var(--accent); transform: rotate(45deg);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--bg-panel) 85%, transparent); }
  .mt-pin.urgent::before { background: var(--danger); }
  .mt-pin.done::before { background: var(--success); opacity: 0.6; }
  .mt-pin:active::before { transform: rotate(45deg) scale(1.25); }

  /* Benzile refolosesc reteta de pe desktop (aceleasi clase, aceeasi gramatica:
     palid = pregatire, plin = pe teren, teal = site, gold = sediu). Se schimba
     doar dimensiunile, fiindca aici randul are 26px, nu 42. */
  .m-track .band { top: 3px; bottom: 3px; border-radius: 6px; }
  .m-track .impl-band { top: 3px; bottom: 3px; gap: 4px; padding: 0 6px; border-radius: 6px;
    border-left-width: 2px; box-shadow: inset 0 0 0 1px color-mix(in srgb, #10130f 18%, transparent); }
  .m-track .impl-band.pregatire { box-shadow: inset 0 0 0 1px color-mix(in oklab, var(--il) 45%, transparent); }
  .m-track .ib-txt { font-size: var(--font-micro); }
  /* In banda, perioada e DESEN, nu buton: un bloc de doua zile are ~23×20px.
     Cine vrea s-o deschida o atinge pe randul ei, de sub banda (`.mimpl`), unde
     are latimea intreaga. */
  .m-track .impl-band { pointer-events: none; cursor: default; }

  .mgroup { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-sm) var(--space-sm) var(--space-xs); }
  .mg-head { display: flex; align-items: center; gap: 7px; padding: 4px 6px 8px; }
  .mg-head h2 { font-size: var(--font-body); font-weight: var(--fw-semibold); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .mg-count { margin-left: auto; font-size: var(--font-tiny); font-family: var(--font-mono); color: var(--text-dim); background: var(--bg-elevated); padding: 1px 8px; border-radius: var(--radius-full); }
  .mrow { position: relative; display: flex; align-items: center; gap: var(--space-xs); padding: 8px; background: var(--bg-panel); border: 1px solid var(--border); border-left: 3px solid var(--lane); border-radius: var(--radius-md); margin-bottom: 6px; }
  .mrow.urgent { border-left-color: var(--danger); }
  .mrow.done { opacity: 0.6; }
  .mrow.done .mrow-title { text-decoration: line-through; }
  .mrow-main { flex: 1; min-width: 0; text-align: left; background: none; border: none; cursor: pointer; display: flex; flex-direction: column; gap: 3px; }
  .mrow-title { font-size: var(--font-small); color: var(--text); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .mrow-meta { display: flex; flex-wrap: wrap; gap: 4px; }
  .chip { font-size: var(--font-micro); font-family: var(--font-mono); padding: 1px 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-dim); display: inline-flex; align-items: center; gap: 3px; }
  .chip.due { color: var(--accent); background: var(--accent-subtle); }
  .mrow-actions { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
  /* Pe desktop invelisul de glisare nu exista pentru layout, iar panoul lui e
     ascuns: acolo actiunile stau la vedere in rand. */
  .gl-fata { display: contents; }
  .gl-actiuni { display: none; }
  .mcheck { display: none; }
  .mbtn { width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; background: none; border: none; }
  .mbtn:hover { background: var(--bg-hover); color: var(--text); }
  .mrow-date { width: 34px; flex-shrink: 0; }
  .mrow-date :global(.dp-trigger) { width: 34px; min-height: 34px; padding: 0; justify-content: center; background: transparent; border: none; box-shadow: none; color: var(--text-faint); }
  .mrow-date :global(.dp-trigger:hover) { background: var(--bg-hover); color: var(--text); }
  .mrow-date :global(.dp-value) { display: none; }

  /* ===== action popover ===== */
  .pop-backdrop { position: fixed; inset: 0; z-index: var(--z-modal); }
  .pop { position: fixed; z-index: calc(var(--z-modal) + 1); width: 256px; background: var(--bg-overlay);
    border: 1px solid var(--border-strong); border-radius: var(--radius-md); box-shadow: var(--shadow-lg);
    padding: 10px; display: flex; flex-direction: column; gap: 3px; }
  .pop-title { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); padding: 2px 4px 0; padding-right: 22px; }
  .pop-meta { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 4px 6px; font-size: var(--font-micro); color: var(--text-dim); border-bottom: 1px solid var(--border); margin-bottom: 4px; }
  .pop-meta .pm-due { color: var(--accent); }
  .pop-act { display: flex; align-items: center; gap: 8px; padding: 8px 8px; border-radius: var(--radius-sm); background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: var(--font-small); text-align: left; }
  .pop-act:hover { background: var(--bg-hover); color: var(--text); }
  .pop-act.datewrap { cursor: default; }
  .pop-act.datewrap:hover { background: none; }
  .datewrap .pa-ico { display: flex; color: var(--text-faint); }
  .datewrap .pa-label { color: var(--text-secondary); }
  .datewrap :global(.dp-trigger) { margin-left: auto; min-height: 30px; padding: 4px 8px; }
  .pop-close { position: absolute; top: 6px; right: 6px; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); background: none; border: none; cursor: pointer; }
  .pop-close:hover { background: var(--bg-hover); color: var(--text); }

  /* ===== Telefon =====
     Bara de controale avea 502px intr-un ecran de 375: `.page-header` are
     `flex-wrap`, dar `.controls` era un singur bloc `flex` fara wrap, deci nu
     putea fi rupt si impingea TOATA pagina la 502px latime. Rezultatul: fiecare
     ecran din Planificator se derula si lateral, iar barele de zile nu se mai
     aliniau cu ce vedeai. */

  :global(body.plan-dragging) { user-select: none; cursor: grabbing; }
  :global(body.plan-dragging) .bar { cursor: grabbing; }

  /* ===== drop indicator (backlog -> timeline) ===== */
  .p-body.drop-active { outline: 2px dashed color-mix(in srgb, var(--accent) 45%, transparent); outline-offset: -2px; border-radius: var(--radius-sm); }
  .drop-line { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--accent); z-index: 6; }
  .drop-tag { position: absolute; top: 2px; transform: translateX(-50%); background: var(--accent); color: var(--accent-text); font-family: var(--font-mono); font-size: var(--font-micro); padding: 1px 6px; border-radius: var(--radius-xs); z-index: 7; white-space: nowrap; }

  /* ===== backlog rail ===== */
  .backlog { margin-top: var(--space-md); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
  .bl-head { width: 100%; display: flex; align-items: center; gap: var(--space-sm); padding: 12px 16px; background: none; border: none; cursor: pointer; color: var(--text); }
  .bl-head h2 { font-size: var(--font-body); font-weight: var(--fw-semibold); }
  .bl-count { font-size: var(--font-tiny); font-family: var(--font-mono); background: var(--accent-subtle); color: var(--accent); padding: 1px 8px; border-radius: var(--radius-full); }
  .bl-hint { font-size: var(--font-micro); color: var(--text-faint); margin-left: 4px; }
  .bl-head :global(.bl-chev) { margin-left: auto; color: var(--text-faint); transition: transform var(--dur-fast) var(--ease); }
  .backlog.open .bl-head :global(.bl-chev) { transform: rotate(90deg); }
  .bl-items { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 16px 16px; }
  .bl-chip { display: flex; align-items: center; gap: 6px; padding: 6px 8px 6px 4px; background: var(--bg-panel); border: 1px solid var(--border); border-left: 3px solid var(--text-faint); border-radius: var(--radius-md); cursor: grab; max-width: 320px; }
  .bl-chip:hover { border-color: var(--border-strong); }
  .bl-chip:active { cursor: grabbing; }
  .bl-chip.urgent { border-left-color: var(--danger); }
  .bl-chip :global(.bl-grip) { color: var(--text-faint); flex-shrink: 0; }
  .bl-txt { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; }
  .bl-proj { font-size: var(--font-micro); font-family: var(--font-mono); color: var(--accent); background: var(--accent-subtle); padding: 1px 6px; border-radius: var(--radius-xs); white-space: nowrap; max-width: 120px; overflow: hidden; text-overflow: ellipsis; }
  .bl-proj.glob { color: var(--text-dim); background: var(--bg-elevated); }
  .bl-date { width: 30px; flex-shrink: 0; }
  .bl-date :global(.dp-trigger) { width: 30px; min-height: 30px; padding: 0; justify-content: center; background: transparent; border: none; box-shadow: none; color: var(--text-faint); }
  .bl-date :global(.dp-trigger:hover) { background: var(--bg-hover); color: var(--accent); }
  .bl-date :global(.dp-value) { display: none; }

  /* ===== export modal ===== */
  .exp { display: flex; flex-direction: column; gap: 14px; }
  .exp-note { font-size: var(--font-small); color: var(--text-secondary); margin: 0; }
  .exp-note b { color: var(--text); }
  .exp-scope-head { display: flex; align-items: center; justify-content: space-between; font-size: var(--font-micro); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--text-dim); font-family: var(--font-mono); margin-bottom: 6px; }
  .exp-all { background: none; border: none; color: var(--accent); font-size: var(--font-tiny); cursor: pointer; font-family: var(--font-mono); }
  .exp-list { display: flex; flex-direction: column; gap: 2px; max-height: 240px; overflow-y: auto; }
  .exp-row { display: flex; align-items: center; gap: 9px; padding: 7px 8px; border-radius: var(--radius-sm); cursor: pointer; }
  .exp-row:hover { background: var(--bg-hover); }
  .exp-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
  .exp-name { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .exp-opt { display: flex; align-items: center; gap: 9px; font-size: var(--font-small); color: var(--text-secondary); cursor: pointer; padding-top: 6px; border-top: 1px solid var(--border); }
  .modal-actions { display: flex; justify-content: flex-end; gap: var(--space-sm); }
  .btn-ghost { padding: 8px 16px; border-radius: var(--radius-md); background: none; border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; font-size: var(--font-small); }
  .btn-ghost:hover { border-color: var(--border-strong); color: var(--text); }
  .btn-primary { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: var(--radius-md); background: var(--accent); border: none; color: var(--accent-text); cursor: pointer; font-size: var(--font-small); font-weight: var(--fw-semibold); }
  .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ===== telefon =====
     ULTIMELE in fisier, cu buna stiinta. Un `@media` NU adauga specificitate: la
     specificitate egala castiga regula scrisa mai jos. Blocurile astea stateau la
     mijlocul fisierului, inaintea sectiunilor „backlog rail" si „controls" — deci
     `.bl-chip { max-width: none }` de aici era anulat de `.bl-chip { max-width: 320px }`
     de mai incolo, si la fel `.bl-txt`, `.bl-proj`, `.bl-date`, `.page`, `.page-header`,
     `.controls`. Douasprezece reguli scrise pentru telefon care nu se aplicau nici
     pe telefon: masurat in pagina, chipul din „Taskuri fără termen" avea tot
     `max-width: 320px` si butonul de data tot 30px in loc de 44.
     Daca adaugi sectiuni noi de baza, adauga-le DEASUPRA acestui punct. */

  @media (max-width: 820px) {
    .chart { display: none; }
    .mlist { display: flex; }
  }

  @media (max-width: 768px) {
    .page { padding-left: var(--space-md); padding-right: var(--space-md); }
    .page-header { align-items: stretch; }
    .controls { flex-wrap: wrap; width: 100%; }
    /* Orizontul e alegerea principala — ia randul lui, cu cele cinci trepte
       impartite egal. */
    .seg { display: flex; width: 100%; }
    .seg-btn { flex: 1; min-height: var(--tap-min); font-size: var(--font-body); }
    /* `nowrap` + eticheta scurtata: „Export PDF" se rupea pe doua randuri si facea
       butonul cu 10px mai inalt decat vecinii lui, adica un rand strâmb. */
    .toggle { flex: 1 1 0; min-height: var(--tap-min); justify-content: center; white-space: nowrap; padding: 6px 8px; }
    .tg-lung { display: none; }

    /* Randurile listei: butoanele erau de 34px, adica sub pragul la care nimeresti
       din prima. Aici bifezi taskuri cu manusa de lucru pe mana. */
    .mbtn { width: var(--tap-min); height: var(--tap-min); }
    .mrow-date { width: var(--tap-min); }
    .mrow-date :global(.dp-trigger) { width: var(--tap-min); min-height: var(--tap-min); }
    /* Ca pe „Astazi": o linie, bifa la vedere, restul in panoul de sub rand.
       Randul era pe doua linii, cu trei butoane de 44px pe a doua — pe o lista de
       noua proiecte asta inseamna sa derulezi mult ca sa vezi putin. */
    .mrow { padding: 0; overflow: hidden; position: relative; touch-action: pan-y; }
    .gl-fata { display: flex; align-items: center; gap: var(--space-xs); width: 100%;
               padding: 5px 8px; background: var(--bg-panel); position: relative; z-index: 1;
               border-radius: var(--radius-md); will-change: transform; }
    /* `:global(...)` pe clasa pusa din JS, NU pe intreg selectorul.
       Svelte NU se multumeste sa avertizeze „Unused CSS selector": TAIE regula din
       build. Iar `gl-tras`/`gl-bifa` sunt puse la RULARE de `lib/glisare.js`, deci
       nu apar in markup si compilatorul le crede moarte. Efectul, verificat in CSS-ul
       livrat: din toate regulile de gest ale aplicatiei supravietuise UNA. Adica
       glisai spre dreapta si nu vedeai verdele care spune „ai trecut pragul" —
       exact semnalul fara de care gestul e o loterie.
       Ancora (`.arow`/`.trow`/`.mrow`) ramane scoped, deci regula nu scapa in alte
       componente. */
    .mrow:global(.gl-tras) .gl-fata { box-shadow: -6px 0 12px -8px rgba(0,0,0,0.55); }
    .mrow-main { flex: 1 1 0; min-width: 0; padding: 0; min-height: var(--tap-min); justify-content: center; }
    .mrow-title { white-space: nowrap; }
    .mimpl { min-height: var(--tap-min); }
    .mrow-meta { flex-wrap: nowrap; overflow: hidden; }
    .mrow-meta > * { flex-shrink: 0; }
    .mrow-actions { display: none; }
    .mcheck { display: flex; width: var(--tap-min); height: var(--tap-min); flex-shrink: 0;
              align-items: center; justify-content: center; background: none; border: none;
              color: var(--text-dim); cursor: pointer; }
    .mcheck-gol { width: 18px; height: 18px; border: 2px solid var(--border); border-radius: 50%; }
    .mrow.done .mcheck { color: var(--success); }
    .mcheck { display: flex; }

    .gl-actiuni { display: flex; position: absolute; top: 0; right: 0; bottom: 0; z-index: 0; align-items: stretch; }
    .glb { width: 58px; display: flex; flex-direction: column; align-items: center; justify-content: center;
           gap: 3px; border: none; background: var(--bg-elevated); color: var(--text-secondary);
           font-size: var(--font-micro); cursor: pointer; }
    .glb span { line-height: 1; }
    .glb.datewrap { position: relative; }
    .glb.datewrap :global(.dp) { position: absolute; inset: 0; width: auto; }
    .glb.datewrap :global(.dp-trigger) { width: 100%; height: 100%; min-height: 0; padding: 0 0 14px;
      justify-content: center; background: none; border: none; box-shadow: none; color: inherit; }
    .glb.datewrap :global(.dp-value) { display: none; }
    .glb.datewrap > span { position: absolute; left: 0; right: 0; bottom: 11px; text-align: center; pointer-events: none; }
    .mrow:global(.gl-bifa) { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }

    .bl-head { min-height: var(--tap-min); }
    .bl-hint { display: none; }
    /* DOUA RANDURI, NU DOUA JUMATATI.
       Pe o linie, titlul si numele proiectului isi imparteau latimea si ieseau
       doua fragmente egale — „Backup paramet…" langa „Interventie avar…" — din
       care nu se intelege niciunul. Nu e o lista de taskuri de bifat (acolo un
       rand = o linie, vezi TodayBoard), e un sertar din care alegi ce planifici:
       aici numele intreg valoreaza mai mult decat inaltimea economisita.
       Titlul ia tot randul, proiectul sta dedesubt, manerul si data prind
       amandoua randurile. */
    .bl-chip { max-width: none; width: 100%; padding: 4px 6px 4px 4px;
               display: grid; grid-template-columns: auto minmax(0, 1fr) auto;
               column-gap: 6px; row-gap: 1px; align-items: center; }
    .bl-chip :global(.bl-grip) { grid-row: 1 / -1; }
    .bl-txt { max-width: none; grid-column: 2; }
    .bl-proj { grid-column: 2; justify-self: start; max-width: 100%; }
    .bl-date { grid-column: 3; grid-row: 1 / -1; width: var(--tap-min); }
    .bl-date :global(.dp-trigger) { width: var(--tap-min); min-height: var(--tap-min); }
  }

  /* ===== print (browser print-to-PDF) ===== */
  .print-title { display: none; }
  @media print {
    .page { padding: 0 !important; }
    .page-header, .controls, .hint, .mlist, .backlog, .drag-label, .pop, .pop-backdrop { display: none !important; }
    .print-title { display: block; font-family: var(--font-heading); font-size: 1.1rem; font-weight: var(--fw-bold); color: #1a1206; margin-bottom: 8px; }
    /* Force the swimlane on: A4 portrait (~794px) is under the 820px mobile
       breakpoint, which would otherwise hide .chart and blank the page. */
    .chart { display: block !important; overflow: visible !important; border: none !important; box-shadow: none !important; background: #fff !important; }
    .chart-scroll { overflow: visible !important; }
    .inner { min-width: 0 !important; width: 100% !important; }
    .lane.print-hide { display: none !important; }
    .bar { animation: none !important; box-shadow: none !important; }
  }
  :global(body.plan-pagebreak) .lane { break-after: page; }
  :global(body.plan-pagebreak) .lane:last-of-type { break-after: auto; }
</style>
