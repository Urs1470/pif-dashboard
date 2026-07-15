<script>
  import { onMount } from 'svelte'
  import { Plus, Diamond, Trash2, Flag, Milestone, Link2, X, FileDown, Sheet, Wand2, ChevronRight, MapPin, Building2 } from '@lucide/svelte'
  import ImplPeriodModal from '../projects/ImplPeriodModal.svelte'
  import { apiJson } from '../../lib/api.js'
  import { createTask, updateTask, deleteTask } from '../../stores/tasks.svelte.js'
  import { buildColumns, spanRect, dayDiff, addDays, isoDate, parseISO, localToday, clampNum } from '../../lib/planDates.js'
  import { formatDateShort } from '../../lib/formatters.js'
  import { toast } from '../../stores/ui.svelte.js'
  import DatePicker from '../ui/DatePicker.svelte'
  import Skeleton from '../ui/Skeleton.svelte'
  import EmptyState from '../ui/EmptyState.svelte'

  let { projectId } = $props()

  let data = $state({ proiect: null, tasks: [], dependencies: [] })
  let loading = $state(true)
  let error = $state(null)
  let adding = $state(false)

  async function load() {
    loading = true; error = null
    try {
      data = await apiJson(`/api/proiecte/${projectId}/gantt`)
    } catch (e) { error = e.message } finally { loading = false }
  }
  onMount(load)

  const today = localToday()

  // Auto-fit the window to the project's real span (tasks + project dates), padded.
  const win = $derived.by(() => {
    const ds = []
    for (const t of data.tasks) {
      if (t.data_start) ds.push(t.data_start.slice(0, 10))
      if (t.data_scadenta) ds.push(t.data_scadenta.slice(0, 10))
    }
    if (data.proiect?.data_incepere) ds.push(data.proiect.data_incepere.slice(0, 10))
    if (data.proiect?.deadline) ds.push(data.proiect.deadline.slice(0, 10))
    for (const im of (data.implementari || [])) {
      if (im.data_start) ds.push(im.data_start.slice(0, 10))
      if (im.data_sfarsit) ds.push(im.data_sfarsit.slice(0, 10))
    }
    ds.push(today)
    const lo = ds.reduce((a, b) => a < b ? a : b)
    const hi = ds.reduce((a, b) => a > b ? a : b)
    const start = addDays(lo, -2)
    let days = (dayDiff(start, hi) || 0) + 4
    days = Math.max(14, days)
    return { start, days }
  })

  const columns = $derived(buildColumns(win.start, win.days))
  const unit = $derived(columns.unit)
  const todayIdx = $derived(dayDiff(win.start, today))
  const colMin = $derived(unit === 'day' ? (win.days <= 21 ? 40 : 30) : unit === 'week' ? 60 : 90)
  const contentMin = $derived(colMin * columns.cols.length)

  function statusClass(t) {
    if (t.status === 'done' || t.status === 'finalizat') return 'done'
    if (t.status === 'in_progress' || t.status === 'in_lucru') return 'prog'
    return 'todo'
  }
  function duration(t) {
    const d = dayDiff(t.data_start, t.data_scadenta)
    return d == null ? 1 : d + 1
  }
  function rectFor(t) {
    return spanRect(t.data_start, t.data_scadenta, win.start, win.days)
  }
  function msPct(t) {
    const di = dayDiff(win.start, t.data_start || t.data_scadenta)
    if (di == null) return null
    return ((di + 0.5) / win.days) * 100
  }

  let autoReschedule = $state((() => { try { return localStorage.getItem('pif-gantt-auto') === '1' } catch { return false } })())
  function toggleAuto() {
    autoReschedule = !autoReschedule
    try { localStorage.setItem('pif-gantt-auto', autoReschedule ? '1' : '0') } catch {}
  }
  // --- critical path (CPM on durations + dependency DAG) ---
  let showCritical = $state((() => { try { return localStorage.getItem('pif-gantt-crit') === '1' } catch { return false } })())
  function toggleCritical() {
    showCritical = !showCritical
    try { localStorage.setItem('pif-gantt-crit', showCritical ? '1' : '0') } catch {}
  }
  const criticalSet = $derived.by(() => {
    const T = data.tasks
    if (!T.length) return new Set()
    const id2 = new Map(T.map(t => [t.id, t]))
    const dur = (t) => t.is_milestone ? 0 : Math.max((dayDiff(t.data_start, t.data_scadenta) || 0) + 1, 1)
    const preds = new Map(T.map(t => [t.id, []]))
    const succs = new Map(T.map(t => [t.id, []]))
    for (const d of data.dependencies) {
      if (id2.has(d.predecessor_id) && id2.has(d.successor_id)) {
        preds.get(d.successor_id).push(d.predecessor_id)
        succs.get(d.predecessor_id).push(d.successor_id)
      }
    }
    const indeg = new Map(T.map(t => [t.id, preds.get(t.id).length]))
    const q = T.filter(t => indeg.get(t.id) === 0).map(t => t.id)
    const order = []
    while (q.length) {
      const n = q.shift(); order.push(n)
      for (const s of succs.get(n)) { indeg.set(s, indeg.get(s) - 1); if (indeg.get(s) === 0) q.push(s) }
    }
    if (order.length < T.length) return new Set() // cycle guard
    const EF = new Map(), ES = new Map()
    for (const id of order) {
      const d = dur(id2.get(id))
      let es = 0
      for (const p of preds.get(id)) es = Math.max(es, EF.get(p))
      ES.set(id, es); EF.set(id, es + d)
    }
    const projEnd = Math.max(...EF.values())
    const LS = new Map()
    for (let i = order.length - 1; i >= 0; i--) {
      const id = order[i]; const d = dur(id2.get(id))
      let lf = projEnd
      if (succs.get(id).length) lf = Math.min(...succs.get(id).map(s => LS.get(s)))
      LS.set(id, lf - d)
    }
    const crit = new Set()
    for (const id of order) if (Math.abs(LS.get(id) - ES.get(id)) < 0.5) crit.add(id)
    return crit
  })

  async function patch(id, body) {
    try {
      await updateTask(id, body)
      if (autoReschedule) {
        const res = await apiJson(`/api/proiecte/${projectId}/reschedule`, { method: 'POST' })
        if (res?.changed) toast(`Reprogramat ${res.changed} task${res.changed > 1 ? '-uri' : ''} dependent${res.changed > 1 ? 'e' : ''}`, 'success')
      }
      await load()
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }
  async function rescheduleNow() {
    try {
      const res = await apiJson(`/api/proiecte/${projectId}/reschedule`, { method: 'POST' })
      toast(res?.changed ? `Reprogramat ${res.changed} task-uri` : 'Nimic de reprogramat', 'success')
      await load()
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }
  function setStart(t, v) { if (v) patch(t.id, { data_start: v }) }
  function setEnd(t, v) { if (v) patch(t.id, { data_scadenta: v }) }
  function setProgress(t, e) {
    let v = parseInt(e.target.value, 10)
    if (isNaN(v)) return
    v = Math.max(0, Math.min(100, v))
    patch(t.id, { progres: v })
  }
  function toggleMilestone(t) { patch(t.id, { is_milestone: t.is_milestone ? 0 : 1 }) }
  function setFaza(t, e) { const v = e.target.value.trim(); if (v !== (t.faza || '')) patch(t.id, { faza: v }) }

  async function addTask() {
    if (adding) return
    adding = true
    try {
      const start = today
      await createTask(projectId, { titlu: 'Task nou', status: 'to_do', data_start: start, data_scadenta: addDays(start, 2) })
      await load()
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { adding = false }
  }
  async function removeTask(t) {
    if (!confirm(`Ștergi „${t.titlu}"?`)) return
    try { await deleteTask(t.id); await load() }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  // --- dependencies (arrows) ---
  const ROW_H = 34 // keep in sync with --row-h
  let bodyW = $state(0)
  let linkFrom = $state(null)
  // --- phases (Plane-style cycles): group tasks under collapsible summary bars ---
  let collapsed = $state(new Set())
  function togglePhase(p) { const s = new Set(collapsed); if (s.has(p)) s.delete(p); else s.add(p); collapsed = s }

  const displayRows = $derived.by(() => {
    const byPhase = new Map(), noPhase = []
    for (const t of data.tasks) {
      const f = (t.faza || '').trim()
      if (f) { if (!byPhase.has(f)) byPhase.set(f, []); byPhase.get(f).push(t) }
      else noPhase.push(t)
    }
    const rows = []; let n = 0
    for (const im of (data.implementari || [])) rows.push({ kind: 'impl', im })
    const pushTask = (t) => rows.push({ kind: 'task', t, no: ++n })
    for (const [phase, ts] of byPhase) {
      rows.push({ kind: 'phase', phase, tasks: ts })
      if (!collapsed.has(phase)) ts.forEach(pushTask)
    }
    noPhase.forEach(pushTask)
    return rows
  })
  function implRect(im) { return spanRect(im.data_start, im.data_sfarsit, win.start, win.days) }
  function locLabel(l) { return l === 'sediu' ? 'Sediu EGB' : 'Site' }

  // implementation-period editor
  let implOpen = $state(false)
  let implEditing = $state(null)
  function newImpl() { implEditing = null; implOpen = true }
  function editImpl(im) { implEditing = im; implOpen = true }
  const hasPhases = $derived(data.tasks.some(t => (t.faza || '').trim()))

  function phaseSpanRect(ts) {
    const ds = ts.flatMap(t => [t.data_start, t.data_scadenta].filter(Boolean).map(x => x.slice(0, 10)))
    if (!ds.length) return null
    const lo = ds.reduce((a, b) => a < b ? a : b), hi = ds.reduce((a, b) => a > b ? a : b)
    return spanRect(lo, hi, win.start, win.days)
  }
  function phaseProgress(ts) {
    let w = 0, p = 0
    for (const t of ts) { const d = Math.max((dayDiff(t.data_start, t.data_scadenta) || 0) + 1, 1); w += d; p += d * t.progres }
    return w ? Math.round(p / w) : 0
  }

  const idxMap = $derived.by(() => { const m = new Map(); displayRows.forEach((r, i) => { if (r.kind === 'task') m.set(r.t.id, i) }); return m })
  const nRows = $derived(displayRows.length)

  function edgesFor(t) {
    const i = idxMap.get(t.id)
    if (i == null || !bodyW) return null
    const y = i * ROW_H + ROW_H / 2
    if (t.is_milestone) {
      const p = msPct(t)
      if (p == null) return null
      const x = (p / 100) * bodyW
      return { s: x, e: x, y }
    }
    const r = rectFor(t)
    if (!r) return null
    return { s: (r.left / 100) * bodyW, e: ((r.left + r.width) / 100) * bodyW, y }
  }
  function arrowPath(dep) {
    const p = data.tasks.find(x => x.id === dep.predecessor_id)
    const s = data.tasks.find(x => x.id === dep.successor_id)
    if (!p || !s) return null
    const pe = edgesFor(p), se = edgesFor(s)
    if (!pe || !se) return null
    const x1 = pe.e, y1 = pe.y, x2 = se.s, y2 = se.y
    const g = 10
    if (x2 >= x1 + g) return `M ${x1} ${y1} H ${x1 + g} V ${y2} H ${x2 - 2}`
    const ym = (y1 + y2) / 2
    return `M ${x1} ${y1} H ${x1 + g} V ${ym} H ${x2 - g} V ${y2} H ${x2 - 2}`
  }
  async function createDep(pred, succ) {
    try { await apiJson(`/api/proiecte/${projectId}/dependencies`, { method: 'POST', body: { predecessor_id: pred, successor_id: succ } }); await load() }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }
  async function deleteDep(id) {
    try { await apiJson(`/api/dependencies/${id}`, { method: 'DELETE' }); await load() }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }
  function onLinkClick(t) {
    if (!linkFrom) { linkFrom = t.id; toast('Alege succesorul — task-ul care depinde de acesta', 'success') }
    else if (linkFrom === t.id) { linkFrom = null }
    else { const p = linkFrom; linkFrom = null; createDep(p, t.id) }
  }

  // --- drag / resize bars directly on the timeline ---
  let drag = null
  let dragLabel = $state(null)

  function startBarDrag(e, t, mode) {
    if (e.button != null && e.button !== 0) return
    const barEl = e.currentTarget.closest('.bar, .ms')
    if (!barEl || !bodyW) return
    drag = {
      t, mode, barEl, startX: e.clientX,
      dayW: bodyW / win.days,
      unit: 100 / win.days,
      isMs: barEl.classList.contains('ms'),
      origLeft: parseFloat(barEl.style.left) || 0,
      origWidth: parseFloat(barEl.style.width) || 0,
      effDelta: 0, moved: false,
    }
    document.body.classList.add('plan-dragging')
    window.addEventListener('pointermove', onBarMove)
    window.addEventListener('pointerup', onBarUp)
    e.preventDefault(); e.stopPropagation()
  }
  function onBarMove(e) {
    if (!drag) return
    const dx = e.clientX - drag.startX
    if (Math.abs(dx) > 3) drag.moved = true
    const dd = Math.round(dx / drag.dayW)
    const u = drag.unit, el = drag.barEl
    if (drag.mode === 'move') {
      const maxL = drag.isMs ? 100 : 100 - drag.origWidth
      const want = clampNum(drag.origLeft + dd * u, 0, maxL)
      el.style.left = want + '%'
      drag.effDelta = Math.round((want - drag.origLeft) / u)
    } else if (drag.mode === 'resizeL') {
      const want = clampNum(drag.origLeft + dd * u, 0, drag.origLeft + drag.origWidth - u)
      el.style.left = want + '%'
      el.style.width = (drag.origLeft + drag.origWidth - want) + '%'
      drag.effDelta = Math.round((want - drag.origLeft) / u)
    } else {
      const want = clampNum(drag.origWidth + dd * u, u, 100 - drag.origLeft)
      el.style.width = want + '%'
      drag.effDelta = Math.round((want - drag.origWidth) / u)
    }
    const t = drag.t, k = drag.effDelta
    if (drag.mode === 'move') dragLabel = { x: e.clientX, y: e.clientY, text: `${formatDateShort(addDays(t.data_start, k))} → ${formatDateShort(addDays(t.data_scadenta, k))}` }
    else if (drag.mode === 'resizeL') dragLabel = { x: e.clientX, y: e.clientY, text: `start ${formatDateShort(addDays(t.data_start, k))}` }
    else dragLabel = { x: e.clientX, y: e.clientY, text: `sfârșit ${formatDateShort(addDays(t.data_scadenta, k))}` }
  }
  async function onBarUp() {
    window.removeEventListener('pointermove', onBarMove)
    window.removeEventListener('pointerup', onBarUp)
    document.body.classList.remove('plan-dragging')
    const d = drag; drag = null; dragLabel = null
    if (!d || !d.moved || d.effDelta === 0) {
      if (d) { d.barEl.style.left = d.origLeft + '%'; if (!d.isMs) d.barEl.style.width = d.origWidth + '%' }
      return
    }
    const t = d.t, k = d.effDelta, body = {}
    if (d.mode === 'move') { body.data_start = addDays(t.data_start, k); body.data_scadenta = addDays(t.data_scadenta, k) }
    else if (d.mode === 'resizeL') body.data_start = addDays(t.data_start, k)
    else body.data_scadenta = addDays(t.data_scadenta, k)
    await patch(t.id, body)
  }

  // rename inline
  let editId = $state(null)
  let editVal = $state('')
  function startRename(t) { editId = t.id; editVal = t.titlu }
  async function commitRename() {
    if (editId) {
      const t = data.tasks.find(x => x.id === editId)
      if (t && editVal.trim() && editVal !== t.titlu) await patch(editId, { titlu: editVal.trim() })
    }
    editId = null
  }
</script>

{#if loading}
  <div class="gk">{#each Array(5) as _}<Skeleton height="34px" />{/each}</div>
{:else if error}
  <p class="g-err">Eroare: {error}</p>
{:else if data.tasks.length === 0 && (data.implementari || []).length === 0}
  <EmptyState icon={Milestone} title="Niciun task în Gantt" description="Adaugă taskuri (cu start și termen) sau o perioadă de implementare ca să apară pe diagramă.">
    <div class="es-actions">
      <button class="add-btn" onclick={addTask}><Plus size={15} /> Adaugă task</button>
      <button class="exp-btn" onclick={newImpl}><MapPin size={15} /> Perioadă</button>
    </div>
  </EmptyState>
{:else}
  {#if linkFrom}
    <div class="link-bar">
      <Link2 size={14} /> Legare dependență: apasă <Link2 size={12} /> pe task-ul care <b>depinde</b> de „{data.tasks.find(t => t.id === linkFrom)?.titlu}".
      <button class="link-cancel" onclick={() => linkFrom = null}><X size={13} /> Anulează</button>
    </div>
  {/if}
  <div class="g-toolbar">
    <div class="g-tl">
      <button class="add-btn" onclick={addTask} disabled={adding}><Plus size={15} /> Task nou</button>
      <button class="exp-btn" onclick={newImpl} title="Adaugă perioadă de implementare (Site / Sediu EGB)"><MapPin size={14} /> Perioadă</button>
      <button class="exp-btn" onclick={rescheduleNow} title="Împinge succesorii ca să respecte dependențele"><Wand2 size={14} /> Reprogramează</button>
      <button class="exp-btn" class:on-tg={autoReschedule} onclick={toggleAuto} title="Reprogramare automată a succesorilor la fiecare mutare">Auto {autoReschedule ? '●' : '○'}</button>
      <button class="exp-btn" class:on-tg={showCritical} onclick={toggleCritical} title="Evidențiază drumul critic">Drum critic {showCritical ? '●' : '○'}</button>
      <a class="exp-btn" href={`/api/proiecte/${projectId}/gantt.pdf`} target="_blank" rel="noopener" title="Export PDF (client)"><FileDown size={14} /> PDF</a>
      <a class="exp-btn" href={`/api/proiecte/${projectId}/gantt.xlsx`} title="Export Excel"><Sheet size={14} /> Excel</a>
    </div>
    <span class="g-legend">
      <span class="lg"><span class="sw done"></span>finalizat</span>
      <span class="lg"><span class="sw prog"></span>în lucru</span>
      <span class="lg"><span class="sw todo"></span>de făcut</span>
      <span class="lg"><span class="sw-ms"></span>milestone</span>
    </span>
  </div>

  <div class="gantt2">
    <!-- left: task table -->
    <div class="g-table">
      <div class="gh-row">
        <span class="c-idx">#</span>
        <span class="c-name">Task</span>
        <span class="c-faza">Fază</span>
        <span class="c-date">Start</span>
        <span class="c-date">Sfârșit</span>
        <span class="c-dur">Zile</span>
        <span class="c-prog">%</span>
        <span class="c-act"></span>
      </div>
      {#each displayRows as row (row.kind === 'phase' ? 'p:' + row.phase : row.kind === 'impl' ? 'i:' + row.im.id : row.t.id)}
        {#if row.kind === 'impl'}
          <button class="impl-lrow loc-{row.im.locatie}" onclick={() => editImpl(row.im)} title="Editează perioada">
            {#if row.im.locatie === 'sediu'}<Building2 size={13} />{:else}<MapPin size={13} />{/if}
            <span class="impl-lname">{locLabel(row.im.locatie)}{row.im.eticheta ? ' · ' + row.im.eticheta : ''}</span>
          </button>
        {:else if row.kind === 'phase'}
          <div class="ph-row" onclick={() => togglePhase(row.phase)} role="button" tabindex="0">
            <ChevronRight size={14} class="ph-chev {collapsed.has(row.phase) ? '' : 'open'}" />
            <span class="ph-name">{row.phase}</span>
            <span class="ph-meta">{row.tasks.length} · {phaseProgress(row.tasks)}%</span>
          </div>
        {:else}
          {@const t = row.t}
          <div class="gt-row" class:done={statusClass(t) === 'done'} class:child={(t.faza || '').trim()}>
            <span class="c-idx">{row.no}</span>
            <span class="c-name">
              {#if editId === t.id}
                <input class="rename" bind:value={editVal} onblur={commitRename} onkeydown={(e) => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') editId = null }} autofocus />
              {:else}
                <button class="name-btn" onclick={() => startRename(t)} title={t.titlu}>
                  {#if t.is_milestone}<Diamond size={11} class="mini-ms" />{/if}{t.titlu}
                </button>
              {/if}
            </span>
            <span class="c-faza"><input class="faza-in" value={t.faza || ''} placeholder="—" onchange={(e) => setFaza(t, e)} onkeydown={(e) => { if (e.key === 'Enter') e.target.blur() }} /></span>
            <span class="c-date"><DatePicker value={t.data_start} placeholder="—" onchange={(v) => setStart(t, v)} /></span>
            <span class="c-date"><DatePicker value={t.data_scadenta} placeholder="—" onchange={(v) => setEnd(t, v)} /></span>
            <span class="c-dur">{t.is_milestone ? '◆' : duration(t)}</span>
            <span class="c-prog">
              {#if t.subtask_total > 0}
                <span class="prog-auto" title="Din subtaskuri: {t.subtask_done}/{t.subtask_total}">{t.progres}%</span>
              {:else}
                <input class="prog-in" type="number" min="0" max="100" value={t.progres} onchange={(e) => setProgress(t, e)} onkeydown={(e) => { if (e.key === 'Enter') e.target.blur() }} />
              {/if}
            </span>
            <span class="c-act">
              <button class="ic" class:on={linkFrom === t.id} onclick={() => onLinkClick(t)} title={linkFrom ? 'Leagă aici (succesor)' : 'Leagă dependență'}><Link2 size={13} /></button>
              <button class="ic" class:on={t.is_milestone} onclick={() => toggleMilestone(t)} title="Comută milestone"><Flag size={13} /></button>
              <button class="ic danger" onclick={() => removeTask(t)} title="Șterge"><Trash2 size={13} /></button>
            </span>
          </div>
        {/if}
      {/each}
    </div>

    <!-- right: timeline -->
    <div class="g-time">
      <div class="g-time-inner" style="min-width:{contentMin}px">
        <div class="gh-row time-head">
          {#each columns.cols as c (c.key)}
            <div class="col-h" class:we={unit === 'day' && c.isWeekend} class:today={c.iso && c.iso === today} style="left:{c.leftPct}%; width:{c.widthPct}%">
              <span class="ch-sub">{c.sub}</span><span class="ch-main">{c.main}</span>
            </div>
          {/each}
        </div>
        <div class="g-body" bind:clientWidth={bodyW}>
          {#if data.dependencies.length && bodyW}
            <svg class="dep-svg" width={bodyW} height={nRows * ROW_H} viewBox="0 0 {bodyW} {nRows * ROW_H}">
              <defs>
                <marker id="gdep-arw" markerWidth="7" markerHeight="7" refX="5.5" refY="3" orient="auto">
                  <path d="M0 0 L6 3 L0 6 z" fill="currentColor" />
                </marker>
              </defs>
              {#each data.dependencies as dep (dep.id)}
                {@const d = arrowPath(dep)}
                {#if d}<path {d} class="dep-path" class:crit={showCritical && criticalSet.has(dep.predecessor_id) && criticalSet.has(dep.successor_id)} fill="none" marker-end="url(#gdep-arw)" onclick={() => deleteDep(dep.id)}><title>Șterge dependența</title></path>{/if}
              {/each}
            </svg>
          {/if}
          <div class="overlay">
            {#each columns.cols as c (c.key)}
              <div class="col-line" style="left:{c.leftPct}%"></div>
              {#if unit === 'day' && c.isWeekend}<div class="col-we" style="left:{c.leftPct}%; width:{c.widthPct}%"></div>{/if}
            {/each}
            {#if todayIdx != null && todayIdx >= 0 && todayIdx < win.days}
              <div class="today-line" style="left:{(todayIdx / win.days) * 100}%"></div>
            {/if}
          </div>
          {#each displayRows as row (row.kind === 'phase' ? 'p:' + row.phase : row.kind === 'impl' ? 'i:' + row.im.id : row.t.id)}
            {#if row.kind === 'impl'}
              {@const ir = implRect(row.im)}
              <div class="gb-row impl-track">
                {#if ir}
                  <button class="impl-band loc-{row.im.locatie}" style="left:{ir.left}%; width:{ir.width}%" onclick={() => editImpl(row.im)} title="{locLabel(row.im.locatie)} · {formatDateShort(row.im.data_start)} → {formatDateShort(row.im.data_sfarsit)}">
                    <span class="ib-txt">{locLabel(row.im.locatie)}{row.im.eticheta ? ' · ' + row.im.eticheta : ''}</span>
                  </button>
                {/if}
              </div>
            {:else if row.kind === 'phase'}
              {@const pr = phaseSpanRect(row.tasks)}
              <div class="gb-row ph-track">
                {#if pr}
                  <div class="phase-bar" style="left:{pr.left}%; width:{pr.width}%" title="{row.phase} · {phaseProgress(row.tasks)}%">
                    <div class="pfill" style="width:{phaseProgress(row.tasks)}%"></div>
                  </div>
                {/if}
              </div>
            {:else}
              {@const t = row.t}
              {@const r = rectFor(t)}
              <div class="gb-row">
                {#if t.is_milestone}
                  {#if msPct(t) != null}<div class="ms" class:crit={showCritical && criticalSet.has(t.id)} style="left:{msPct(t)}%" title="{t.titlu} · {formatDateShort(t.data_start)}" onpointerdown={(e) => startBarDrag(e, t, 'move')} role="button" tabindex="-1"></div>{/if}
                {:else if r}
                  <div class="bar {statusClass(t)}" class:crit={showCritical && criticalSet.has(t.id)} style="left:{r.left}%; width:{r.width}%" title="{t.titlu} · {formatDateShort(t.data_start)} → {formatDateShort(t.data_scadenta)} · {t.progres}%" onpointerdown={(e) => startBarDrag(e, t, 'move')} role="button" tabindex="-1">
                    <span class="rz rz-l" onpointerdown={(e) => startBarDrag(e, t, 'resizeL')} aria-hidden="true"></span>
                    <div class="fill" style="width:{t.progres}%"></div>
                    <span class="bl">{t.progres}%</span>
                    <span class="rz rz-r" onpointerdown={(e) => startBarDrag(e, t, 'resizeR')} aria-hidden="true"></span>
                  </div>
                {/if}
              </div>
            {/if}
          {/each}
        </div>
      </div>
    </div>
  </div>
{/if}

{#if dragLabel}
  <div class="drag-label" style="left:{dragLabel.x + 14}px; top:{dragLabel.y - 34}px">{dragLabel.text}</div>
{/if}

<ImplPeriodModal bind:open={implOpen} projectId={projectId} period={implEditing} onsaved={load} />

<style>
  .gk { display: flex; flex-direction: column; gap: 6px; }
  .g-err { color: var(--danger); padding: var(--space-md); }
  .es-actions { display: flex; gap: var(--space-sm); flex-wrap: wrap; justify-content: center; }

  .link-bar { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 8px 12px; margin-bottom: var(--space-sm); background: var(--accent-subtle); border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent); border-radius: var(--radius-md); font-size: var(--font-small); color: var(--text); }
  .link-cancel { margin-left: auto; display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; border-radius: var(--radius-sm); background: none; border: 1px solid var(--border-strong); color: var(--text-secondary); cursor: pointer; font-size: var(--font-tiny); }
  .link-cancel:hover { color: var(--text); border-color: var(--text-dim); }
  .g-toolbar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); margin-bottom: var(--space-sm); flex-wrap: wrap; }
  .add-btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 13px; border-radius: var(--radius-md); background: var(--accent); border: none; color: var(--accent-text); font-size: var(--font-small); font-weight: var(--fw-semibold); cursor: pointer; }
  .add-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .g-tl { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }
  .exp-btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 12px; border-radius: var(--radius-md); background: var(--bg-panel); border: 1px solid var(--border); color: var(--text-secondary); font-size: var(--font-small); font-weight: var(--fw-medium); cursor: pointer; text-decoration: none; }
  .exp-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-subtle); }
  .exp-btn.on-tg { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 45%, transparent); background: var(--accent-subtle); }
  .g-legend { display: flex; gap: 12px; flex-wrap: wrap; }
  .lg { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-micro); color: var(--text-dim); font-family: var(--font-mono); }
  .sw { width: 18px; height: 10px; border-radius: 3px; }
  .sw.done { background: var(--success); } .sw.prog { background: var(--accent); }
  .sw.todo { background: var(--bg-elevated); border: 1px solid var(--border-strong); }
  .sw-ms { width: 10px; height: 10px; background: var(--accent); transform: rotate(45deg); }

  /* ===== two-pane gantt ===== */
  .gantt2 { --row-h: 34px; --head-h: 38px; display: flex; border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; background: var(--bg-panel); }

  .g-table { flex: none; width: 560px; border-right: 2px solid var(--border-strong); background: var(--bg-surface); }
  .c-faza { width: 84px; flex: none; }
  .faza-in { width: 78px; font-size: var(--font-tiny); background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text-secondary); padding: 2px 5px; }
  .faza-in:focus { border-color: var(--accent); outline: none; color: var(--text); }
  .gt-row.child .c-name { padding-left: 12px; }
  .ph-row { height: var(--row-h); display: flex; align-items: center; gap: 6px; padding: 0 10px; background: var(--bg-overlay); border-bottom: 1px solid var(--border); cursor: pointer; }
  .ph-row:hover { background: var(--bg-hover); }
  .ph-row :global(.ph-chev) { color: var(--text-dim); transition: transform var(--dur-fast) var(--ease); flex: none; }
  .ph-row :global(.ph-chev.open) { transform: rotate(90deg); }
  .ph-name { flex: 1; min-width: 0; color: var(--text); font-size: var(--font-small); font-weight: var(--fw-semibold); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ph-meta { font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text-dim); flex: none; }
  /* implementation periods (Site / Sediu EGB) — distinct from tasks */
  .impl-lrow { height: var(--row-h); width: 100%; display: flex; align-items: center; gap: 7px; padding: 0 10px; border: none; border-bottom: 1px solid var(--border); border-left: 3px solid var(--il); background: color-mix(in srgb, var(--il) 8%, transparent); color: var(--text); cursor: pointer; text-align: left; }
  .impl-lrow:hover { background: color-mix(in srgb, var(--il) 16%, transparent); }
  .impl-lname { font-size: var(--font-small); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .loc-site { --il: #3f9dc4; } .loc-sediu { --il: #b98a2e; }
  .impl-track { background: color-mix(in srgb, var(--il-track, transparent) 0%, transparent); }
  .impl-band { position: absolute; top: 50%; transform: translateY(-50%); height: 16px; border-radius: 4px; display: flex; align-items: center; padding: 0 8px; border: none; cursor: pointer; overflow: hidden; background: var(--il); color: #10130f; }
  .impl-band.loc-site { background: #3f9dc4; } .impl-band.loc-sediu { background: #c99a3a; }
  .ib-txt { font-size: 0.62rem; font-weight: var(--fw-bold); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ph-track { background: color-mix(in srgb, var(--accent) 4%, transparent); }
  .phase-bar { position: absolute; top: 50%; transform: translateY(-50%); height: 11px; border-radius: 3px; background: color-mix(in oklab, var(--text-dim) 34%, var(--bg-panel)); overflow: hidden; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--text-dim) 40%, transparent); }
  .phase-bar .pfill { height: 100%; background: var(--text-dim); }
  .gh-row { height: var(--head-h); display: flex; align-items: center; background: var(--bg-overlay); border-bottom: 1px solid var(--border-strong); font-family: var(--font-mono); font-size: var(--font-micro); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--text-dim); }
  .gt-row { height: var(--row-h); display: flex; align-items: center; border-bottom: 1px solid var(--border); }
  .gt-row:last-child { border-bottom: 0; }
  .gt-row.done .c-name { color: var(--text-dim); }
  .c-idx { width: 30px; text-align: center; flex: none; font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text-faint); }
  .c-name { flex: 1; min-width: 0; padding-right: 4px; }
  .name-btn { width: 100%; text-align: left; background: none; border: none; color: var(--text); font-size: var(--font-small); cursor: text; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: inline-flex; align-items: center; gap: 5px; }
  .name-btn:hover { color: var(--accent); }
  .name-btn :global(.mini-ms) { color: var(--accent); flex: none; }
  .rename { width: 100%; font-size: var(--font-small); background: var(--bg-input); border: 1px solid var(--accent); border-radius: var(--radius-xs); color: var(--text); padding: 3px 6px; }
  .c-date { width: 92px; flex: none; }
  .c-date :global(.dp-trigger) { min-height: 28px; padding: 2px 6px; background: transparent; border: none; box-shadow: none; font-size: var(--font-micro); color: var(--text-secondary); }
  .c-date :global(.dp-trigger:hover) { background: var(--bg-hover); color: var(--text); }
  .c-dur { width: 40px; flex: none; text-align: center; font-family: var(--font-mono); font-size: var(--font-tiny); color: var(--text-dim); }
  .c-prog { width: 50px; flex: none; text-align: center; }
  .prog-auto { font-family: var(--font-mono); font-size: var(--font-tiny); color: var(--accent); }
  .prog-in { width: 44px; font-size: var(--font-tiny); font-family: var(--font-mono); text-align: center; background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text); padding: 2px; }
  .c-act { width: 56px; flex: none; display: flex; gap: 2px; justify-content: center; }
  .ic { width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); background: none; border: none; cursor: pointer; }
  .ic:hover { background: var(--bg-hover); color: var(--text); }
  .ic.on { color: var(--accent); }
  .ic.danger:hover { color: var(--danger); background: var(--danger-subtle); }

  .g-time { flex: 1; overflow-x: auto; min-width: 0; }
  .g-time-inner { position: relative; }
  .time-head { position: relative; }
  .col-h { position: absolute; top: 0; bottom: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px; border-left: 1px solid var(--border); overflow: hidden; }
  .col-h.we { background: color-mix(in srgb, var(--purple) 6%, transparent); }
  .col-h.today { background: var(--accent-subtle); }
  .ch-sub { font-size: 0.55rem; color: var(--text-faint); text-transform: uppercase; white-space: nowrap; }
  .ch-main { font-family: var(--font-mono); font-size: var(--font-tiny); font-weight: var(--fw-semibold); color: var(--text-secondary); white-space: nowrap; }
  .col-h.today .ch-main, .col-h.today .ch-sub { color: var(--accent); }

  .g-body { position: relative; }
  .dep-svg { position: absolute; top: 0; left: 0; z-index: 3; pointer-events: none; overflow: visible; color: var(--text-dim); }
  .dep-path { stroke: currentColor; stroke-width: 1.5; pointer-events: stroke; cursor: pointer; transition: stroke var(--dur-fast) var(--ease); }
  .dep-path:hover { color: var(--danger); stroke-width: 2.2; }
  .dep-path.crit { color: #e0433a; stroke-width: 2; }
  .bar.crit { outline: 2px solid #e0433a; outline-offset: 1px; }
  .ms.crit { box-shadow: 0 0 0 2px #e0433a; }
  .overlay { position: absolute; inset: 0; pointer-events: none; z-index: 0; }
  .col-line { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--border-subtle); }
  .col-we { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--purple) 5%, transparent); }
  .today-line { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--danger); opacity: 0.7; z-index: 1; }

  .gb-row { position: relative; height: var(--row-h); border-bottom: 1px solid var(--border); }
  .gb-row:last-child { border-bottom: 0; }
  .bar { position: absolute; top: 50%; transform: translateY(-50%); height: 20px; border-radius: 6px; display: flex; align-items: center; overflow: hidden; z-index: 1; cursor: grab; touch-action: none; }
  .bar:active { cursor: grabbing; }
  .rz { position: absolute; top: 0; bottom: 0; width: 7px; cursor: ew-resize; z-index: 4; }
  .rz-l { left: 0; } .rz-r { right: 0; }
  .ms { cursor: grab; touch-action: none; }
  .drag-label { position: fixed; z-index: var(--z-tooltip); pointer-events: none; background: var(--bg-overlay); border: 1px solid var(--border-strong); border-radius: var(--radius-sm); padding: 3px 8px; font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text); box-shadow: var(--shadow-md); white-space: nowrap; }
  :global(body.plan-dragging) { user-select: none; cursor: grabbing; }
  .bar .fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 6px 0 0 6px; opacity: 0.9; }
  .bar .bl { position: relative; z-index: 2; font-size: 0.6rem; font-weight: var(--fw-bold); font-family: var(--font-mono); padding: 0 6px; }
  .bar.done { background: color-mix(in oklab, var(--success) 22%, var(--bg-panel)); }
  .bar.done .fill { background: var(--success); } .bar.done .bl { color: #0d2a19; }
  .bar.prog { background: color-mix(in oklab, var(--accent) 22%, var(--bg-panel)); }
  .bar.prog .fill { background: var(--accent); } .bar.prog .bl { color: var(--text); }
  .bar.todo { background: var(--bg-elevated); border: 1px solid var(--border-strong); }
  .bar.todo .fill { background: color-mix(in oklab, var(--accent) 55%, var(--bg-panel)); } .bar.todo .bl { color: var(--text-secondary); }
  .ms { position: absolute; top: 50%; width: 15px; height: 15px; background: var(--accent); border: 2px solid var(--bg-panel); transform: translate(-50%, -50%) rotate(45deg); box-shadow: 0 0 0 3px var(--accent-subtle); z-index: 2; }

  @media (max-width: 720px) {
    .g-table { width: 240px; }
    .c-date { width: 70px; } .c-dur { display: none; }
  }
</style>
