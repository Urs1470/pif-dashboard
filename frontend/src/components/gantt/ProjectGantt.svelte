<script>
  import { onMount } from 'svelte'
  import { Plus, Diamond, Trash2, Flag, Milestone } from '@lucide/svelte'
  import { apiJson } from '../../lib/api.js'
  import { createTask, updateTask, deleteTask } from '../../stores/tasks.svelte.js'
  import { buildColumns, spanRect, dayDiff, addDays, isoDate, parseISO, localToday } from '../../lib/planDates.js'
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

  async function patch(id, body) {
    try { await updateTask(id, body); await load() }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') }
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
{:else if data.tasks.length === 0}
  <EmptyState icon={Milestone} title="Niciun task în Gantt" description="Adaugă taskuri cu date de start și termen ca să apară pe diagramă.">
    <button class="add-btn" onclick={addTask}><Plus size={15} /> Adaugă task</button>
  </EmptyState>
{:else}
  <div class="g-toolbar">
    <button class="add-btn" onclick={addTask} disabled={adding}><Plus size={15} /> Task nou</button>
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
        <span class="c-date">Start</span>
        <span class="c-date">Sfârșit</span>
        <span class="c-dur">Zile</span>
        <span class="c-prog">%</span>
        <span class="c-act"></span>
      </div>
      {#each data.tasks as t, i (t.id)}
        <div class="gt-row" class:done={statusClass(t) === 'done'}>
          <span class="c-idx">{i + 1}</span>
          <span class="c-name">
            {#if editId === t.id}
              <input class="rename" bind:value={editVal} onblur={commitRename} onkeydown={(e) => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') editId = null }} autofocus />
            {:else}
              <button class="name-btn" onclick={() => startRename(t)} title={t.titlu}>
                {#if t.is_milestone}<Diamond size={11} class="mini-ms" />{/if}{t.titlu}
              </button>
            {/if}
          </span>
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
            <button class="ic" class:on={t.is_milestone} onclick={() => toggleMilestone(t)} title="Comută milestone"><Flag size={13} /></button>
            <button class="ic danger" onclick={() => removeTask(t)} title="Șterge"><Trash2 size={13} /></button>
          </span>
        </div>
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
        <div class="g-body">
          <div class="overlay">
            {#each columns.cols as c (c.key)}
              <div class="col-line" style="left:{c.leftPct}%"></div>
              {#if unit === 'day' && c.isWeekend}<div class="col-we" style="left:{c.leftPct}%; width:{c.widthPct}%"></div>{/if}
            {/each}
            {#if todayIdx != null && todayIdx >= 0 && todayIdx < win.days}
              <div class="today-line" style="left:{(todayIdx / win.days) * 100}%"></div>
            {/if}
          </div>
          {#each data.tasks as t (t.id)}
            {@const r = rectFor(t)}
            <div class="gb-row">
              {#if t.is_milestone}
                {#if msPct(t) != null}<div class="ms" style="left:{msPct(t)}%" title="{t.titlu} · {formatDateShort(t.data_start)}"></div>{/if}
              {:else if r}
                <div class="bar {statusClass(t)}" style="left:{r.left}%; width:{r.width}%" title="{t.titlu} · {formatDateShort(t.data_start)} → {formatDateShort(t.data_scadenta)} · {t.progres}%">
                  <div class="fill" style="width:{t.progres}%"></div>
                  <span class="bl">{t.progres}%</span>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .gk { display: flex; flex-direction: column; gap: 6px; }
  .g-err { color: var(--danger); padding: var(--space-md); }

  .g-toolbar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); margin-bottom: var(--space-sm); flex-wrap: wrap; }
  .add-btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 13px; border-radius: var(--radius-md); background: var(--accent); border: none; color: var(--accent-text); font-size: var(--font-small); font-weight: var(--fw-semibold); cursor: pointer; }
  .add-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .g-legend { display: flex; gap: 12px; flex-wrap: wrap; }
  .lg { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-micro); color: var(--text-dim); font-family: var(--font-mono); }
  .sw { width: 18px; height: 10px; border-radius: 3px; }
  .sw.done { background: var(--success); } .sw.prog { background: var(--accent); }
  .sw.todo { background: var(--bg-elevated); border: 1px solid var(--border-strong); }
  .sw-ms { width: 10px; height: 10px; background: var(--accent); transform: rotate(45deg); }

  /* ===== two-pane gantt ===== */
  .gantt2 { --row-h: 34px; --head-h: 38px; display: flex; border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; background: var(--bg-panel); }

  .g-table { flex: none; width: 460px; border-right: 2px solid var(--border-strong); background: var(--bg-surface); }
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
  .overlay { position: absolute; inset: 0; pointer-events: none; z-index: 0; }
  .col-line { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--border-subtle); }
  .col-we { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--purple) 5%, transparent); }
  .today-line { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--danger); opacity: 0.7; z-index: 1; }

  .gb-row { position: relative; height: var(--row-h); border-bottom: 1px solid var(--border); }
  .gb-row:last-child { border-bottom: 0; }
  .bar { position: absolute; top: 50%; transform: translateY(-50%); height: 20px; border-radius: 6px; display: flex; align-items: center; overflow: hidden; z-index: 1; }
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
