<script>
  import { onMount } from 'svelte'
  import { CalendarRange, ChevronRight, ArrowRight, X, CheckCircle2, Repeat, ExternalLink, Check, FileDown, Inbox, GripVertical } from '@lucide/svelte'
  import {
    plan, loadPlan, moveTaskDate, moveTaskTomorrow, toggleTaskDone,
    setTaskDates, setHorizon, toggleShowDone, toggleWeekends, scheduleBacklog,
  } from '../stores/plan.svelte.js'
  import { buildColumns, spanRect, dayDiff, addDays, clampNum } from '../lib/planDates.js'
  import { formatDate, formatDateShort } from '../lib/formatters.js'
  import { toast } from '../stores/ui.svelte.js'
  import { morphNavigate } from '../lib/focus.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import Modal from '../components/ui/Modal.svelte'

  // Distinct, CVD-legible lane hues on the warm-dark ground. Amber is reserved for
  // the app accent/active state, so lanes deliberately avoid it.
  const LANE_PALETTE = ['#3f9dc4', '#3fae74', '#8b6fe0', '#d1697f', '#b9a5ff', '#5f8fd0', '#c9a13a']
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
  const contentMin = $derived(200 + colMin * columns.cols.length) // lane-w(200) + cols
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

  const views = $derived(plan.lanes.map((lane) => {
    const color = laneColor(lane.id)
    const taskDates = lane.tasks.flatMap(t => [
      (t.data_planificata || '').slice(0, 10),
      (t.data_scadenta || '').slice(0, 10),
    ].filter(Boolean))
    const bandStart = lane.data_incepere || (taskDates.length ? taskDates.reduce((a, b) => a < b ? a : b) : '')
    const bandEnd = lane.deadline || (taskDates.length ? taskDates.reduce((a, b) => a > b ? a : b) : '')
    const band = lane.tip === 'proiect' ? spanRect(bandStart, bandEnd, plan.start, plan.days) : null
    let deadlinePct = null
    if (lane.deadline) {
      const di = dayDiff(plan.start, lane.deadline)
      if (di != null && di >= 0 && di < plan.days) deadlinePct = ((di + 0.5) / plan.days) * 100
    }
    const tasks = lane.tasks.map(t => ({
      ...t,
      rect: spanRect(t.data_planificata, effDue(t), plan.start, plan.days),
    }))
    return { ...lane, color, band, deadlinePct, tasks, packed: packRows(tasks) }
  }))

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
      await moveTaskDate(t.tip, t.id, v, { data_scadenta: t.data_scadenta })
      toast(`Mutat pe ${formatDate(v)}`, 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    closePop()
  }
  async function onTomorrow(t) {
    try { await moveTaskTomorrow(t.tip, t.id, { data_scadenta: t.data_scadenta }); toast('Mutat pe mâine', 'success') }
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

  function previewText(d) {
    const t = d.t, k = d.effDelta
    if (d.mode === 'move') {
      const s = t.data_planificata ? addDays(t.data_planificata.slice(0, 10), k) : ''
      const e = t.data_scadenta ? addDays(t.data_scadenta.slice(0, 10), k) : ''
      if (s && e) return `${formatDateShort(s)} → ${formatDateShort(e)}`
      return formatDateShort(s || e)
    }
    if (d.mode === 'resizeL') {
      const base = (t.data_planificata || t.data_scadenta || '').slice(0, 10)
      return `start ${formatDateShort(addDays(base, k))}`
    }
    const base = (t.data_scadenta || t.data_planificata || '').slice(0, 10)
    return `termen ${formatDateShort(addDays(base, k))}`
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
    } else if (drag.mode === 'resizeL') {
      const maxLeft = drag.origLeft + drag.origWidth - u
      const want = clampNum(drag.origLeft + dd * u, 0, maxLeft)
      el.style.left = want + '%'
      el.style.width = (drag.origLeft + drag.origWidth - want) + '%'
      drag.effDelta = Math.round((want - drag.origLeft) / u)
    } else {
      const want = clampNum(drag.origWidth + dd * u, u, 100 - drag.origLeft)
      el.style.width = want + '%'
      drag.effDelta = Math.round((want - drag.origWidth) / u)
    }
    dragLabel = { x: e.clientX, y: e.clientY, text: previewText(drag) }
  }

  function commitBody(d) {
    const t = d.t, k = d.effDelta, body = {}
    if (d.mode === 'move') {
      if (t.data_planificata) body.data_planificata = addDays(t.data_planificata.slice(0, 10), k)
      if (t.data_scadenta) body.data_scadenta = addDays(t.data_scadenta.slice(0, 10), k)
    } else if (d.mode === 'resizeL') {
      const base = (t.data_planificata || t.data_scadenta || '').slice(0, 10)
      body.data_planificata = addDays(base, k)
    } else {
      const base = (t.data_scadenta || t.data_planificata || '').slice(0, 10)
      body.data_scadenta = addDays(base, k)
    }
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
    const laneW = parseFloat(getComputedStyle(body).getPropertyValue('--lane-w')) || 200
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
        <FileDown size={14} /> Export PDF
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
                  {#if lane.band}
                    <div class="band" class:clipL={lane.band.clippedLeft} class:clipR={lane.band.clippedRight}
                         style="left:{lane.band.left}%; width:{lane.band.width}%"></div>
                  {/if}
                  {#if lane.deadlinePct != null}
                    <div class="band-ms" style="left:{lane.deadlinePct}%" title="Deadline proiect: {formatDate(lane.deadline)}"></div>
                  {/if}
                  <div class="rows">
                    {#each lane.packed as row, ri (ri)}
                      <div class="t-row">
                        {#each row as t (t.tip + ':' + t.id)}
                          <div
                            class="bar"
                            class:active={isActive(t.status)}
                            class:todo={!isActive(t.status) && !isDone(t.status)}
                            class:done={isDone(t.status)}
                            class:urgent={(t.prioritate || '').toLowerCase() === 'urgent'}
                            class:single={t.rect.single}
                            class:draggable={!isDone(t.status)}
                            style="left:{t.rect.left}%; width:{t.rect.width}%"
                            role="button"
                            tabindex="0"
                            onpointerdown={(e) => startDrag(e, t, 'move', lane.nume)}
                            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPopover(e.currentTarget, t, lane.nume) } }}
                            title="{t.titlu}{t.data_planificata ? ' · plan ' + formatDateShort(t.data_planificata) : ''}{t.data_scadenta ? ' → termen ' + formatDateShort(t.data_scadenta) : ''}"
                          >
                            {#if !isDone(t.status) && !t.rect.single}
                              <span class="rz rz-l" onpointerdown={(e) => startDrag(e, t, 'resizeL', lane.nume)} aria-hidden="true"></span>
                            {/if}
                            <span class="bar-txt">{t.titlu}</span>
                            {#if t.recurenta}<Repeat size={11} />{/if}
                            {#if !isDone(t.status) && !t.rect.single}
                              <span class="rz rz-r" onpointerdown={(e) => startDrag(e, t, 'resizeR', lane.nume)} aria-hidden="true"></span>
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
      <p class="hint">Trage o bară ca s-o muți · trage marginile ca să întinzi intervalul · click pentru acțiuni</p>
    </div>

    <!-- ===== Backlog (taskuri fără termen) ===== -->
    {#if plan.backlog.length > 0}
      <section class="backlog" class:open={backlogOpen}>
        <button class="bl-head" onclick={() => backlogOpen = !backlogOpen} aria-expanded={backlogOpen}>
          <Inbox size={16} />
          <h2>Fără termen</h2>
          <span class="bl-count">{plan.backlog.length}</span>
          <span class="bl-hint">trage pe o zi ca să planifici</span>
          <ChevronRight size={16} class="bl-chev" />
        </button>
        {#if backlogOpen}
          <div class="bl-items">
            {#each plan.backlog as t (t.tip + ':' + t.id)}
              <div class="bl-chip" class:urgent={(t.prioritate || '').toLowerCase() === 'urgent'}
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
      {#each views as lane (lane.tip + ':' + lane.id)}
        <section class="mgroup" style="--lane:{lane.color}">
          <header class="mg-head">
            <span class="lane-dot"></span>
            <h2>{lane.nume}</h2>
            {#if lane.tip_proiect}<span class="tip-chip" class:svc={lane.tip_proiect === 'Service'}>{lane.tip_proiect}</span>{/if}
            <span class="mg-count">{lane.tasks.length}</span>
          </header>
          {#each lane.tasks as t (t.tip + ':' + t.id)}
            <div class="mrow" class:urgent={(t.prioritate || '').toLowerCase() === 'urgent'} class:done={isDone(t.status)}>
              <button class="mrow-main" onclick={(e) => openTask(t, e.currentTarget)}>
                <span class="mrow-title">{t.titlu}</span>
                <span class="mrow-meta">
                  {#if t.data_planificata}<span class="chip">plan {formatDateShort(t.data_planificata)}</span>{/if}
                  {#if t.data_scadenta}<span class="chip due">termen {formatDateShort(t.data_scadenta)}</span>{/if}
                  {#if t.recurenta}<span class="chip"><Repeat size={10} /> {t.recurenta}</span>{/if}
                </span>
              </button>
              <div class="mrow-actions">
                <button class="mbtn" onclick={() => onTomorrow(t)} title="Mută pe mâine"><ArrowRight size={15} /></button>
                <span class="mrow-date"><DatePicker value={t.data_planificata} placeholder="Mută" onchange={(v) => onMove(t, v)} /></span>
                <button class="mbtn" onclick={() => onDone(t)} title="Bifează"><CheckCircle2 size={16} /></button>
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
      <DatePicker value={sel.data_planificata} placeholder="alege" onchange={(v) => onMove(sel, v)} />
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
  .chart { --lane-w: 200px; --day-min: 48px; --row-h: 28px;
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
  .lane-name { display: flex; align-items: center; gap: 7px; min-width: 0; color: var(--text); cursor: pointer; background: none; border: none; text-align: left; font-size: var(--font-small); font-weight: var(--fw-medium); }
  .lane-name.static { cursor: default; }
  .lane-name:not(.static):hover .lane-txt { color: var(--accent); }
  .lane-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--lane); flex-shrink: 0; box-shadow: 0 0 6px color-mix(in srgb, var(--lane) 55%, transparent); }
  .lane-txt { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .tip-chip { font-size: var(--font-micro); font-family: var(--font-mono); padding: 1px 6px; border-radius: var(--radius-chip); background: var(--accent-subtle); color: var(--accent); flex-shrink: 0; }
  .tip-chip.svc { background: color-mix(in srgb, var(--purple) 18%, transparent); color: var(--purple); }

  .lane-track { flex: 1; position: relative; min-width: 0; padding: 7px 0; }
  .band { position: absolute; top: 5px; bottom: 5px; border-radius: 8px;
    background: color-mix(in oklab, var(--lane) 13%, transparent);
    border: 1px solid color-mix(in oklab, var(--lane) 28%, transparent); z-index: 0; }
  .band.clipL { border-top-left-radius: 0; border-bottom-left-radius: 0; border-left: 0; }
  .band.clipR { border-top-right-radius: 0; border-bottom-right-radius: 0; border-right: 0; }
  .band-ms { position: absolute; top: 3px; width: 11px; height: 11px; background: var(--lane);
    border: 1.5px solid var(--bg-surface); transform: translateX(-50%) rotate(45deg);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--lane) 20%, transparent); z-index: 2; }

  .rows { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 4px; }
  .t-row { position: relative; height: var(--row-h); }
  .bar { position: absolute; top: 0; bottom: 0; display: flex; align-items: center; gap: 4px;
    padding: 0 8px; border-radius: 7px; font-size: var(--font-tiny); font-weight: var(--fw-semibold);
    white-space: nowrap; overflow: hidden; cursor: pointer; text-align: left; touch-action: none;
    transition: box-shadow var(--dur-fast) var(--ease);
    animation: barIn 0.4s var(--ease) both; }
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
  .bar.single { justify-content: center; padding: 0 4px; }
  .bar.single .bar-txt { display: none; }
  .bar.single::after { content: '◆'; font-size: 0.7rem; }
  .bar.urgent { box-shadow: inset 3px 0 0 0 var(--danger); }
  .bar-txt { overflow: hidden; text-overflow: ellipsis; pointer-events: none; }

  .rz { position: absolute; top: 0; bottom: 0; width: 8px; cursor: ew-resize; z-index: 6; }
  .rz-l { left: 0; } .rz-r { right: 0; }
  .bar:hover .rz::after { content: ''; position: absolute; top: 50%; transform: translateY(-50%); width: 2px; height: 12px; border-radius: 2px; background: color-mix(in srgb, currentColor 60%, transparent); }
  .rz-l::after { left: 2px; } .rz-r::after { right: 2px; }

  @media (prefers-reduced-motion: reduce) { .bar { animation: none; } }

  .hint { text-align: center; font-size: var(--font-micro); color: var(--text-faint); padding: 8px; border-top: 1px solid var(--border-subtle); }

  .drag-label { position: fixed; z-index: var(--z-tooltip); pointer-events: none; background: var(--bg-overlay);
    border: 1px solid var(--border-strong); border-radius: var(--radius-sm); padding: 3px 8px;
    font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text); box-shadow: var(--shadow-md); white-space: nowrap; }

  /* ===== mobile grouped list ===== */
  .mlist { display: none; flex-direction: column; gap: var(--space-md); }
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

  @media (max-width: 820px) {
    .chart { display: none; }
    .mlist { display: flex; }
  }

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
    .rz { display: none !important; }
  }
  :global(body.plan-pagebreak) .lane { break-after: page; }
  :global(body.plan-pagebreak) .lane:last-of-type { break-after: auto; }
</style>
