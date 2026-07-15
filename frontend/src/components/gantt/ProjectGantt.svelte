<script>
  import { onMount } from 'svelte'
  import { Diamond, Milestone, FileDown, Sheet, ChevronRight, MapPin, Building2, CheckCircle2 } from '@lucide/svelte'
  import ImplPeriodModal from '../projects/ImplPeriodModal.svelte'
  import { apiJson } from '../../lib/api.js'
  import { buildColumns, spanRect, dayDiff, addDays, localToday } from '../../lib/planDates.js'
  import { formatDateShort } from '../../lib/formatters.js'
  import Skeleton from '../ui/Skeleton.svelte'
  import EmptyState from '../ui/EmptyState.svelte'

  // Read-only Gantt: tasks are inherited from the Tasks tab (no editing here).
  // The only editable thing is the implementation period (Site / Sediu EGB).
  let { projectId, onOpenTask } = $props()

  let data = $state({ proiect: null, tasks: [], dependencies: [], implementari: [] })
  let loading = $state(true)
  let error = $state(null)

  async function load() {
    loading = true; error = null
    try {
      data = await apiJson(`/api/proiecte/${projectId}/gantt`)
    } catch (e) { error = e.message } finally { loading = false }
  }
  onMount(load)

  const today = localToday()

  // Auto-fit the window to the project's real span (tasks + project dates + periods), padded.
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
  const isDone = (t) => statusClass(t) === 'done'
  function rectFor(t) { return spanRect(t.data_start, t.data_scadenta, win.start, win.days) }
  function msPct(t) {
    const di = dayDiff(win.start, t.data_start || t.data_scadenta)
    if (di == null) return null
    return ((di + 0.5) / win.days) * 100
  }
  function implRect(im) { return spanRect(im.data_start, im.data_sfarsit, win.start, win.days) }
  function locLabel(l) { return l === 'sediu' ? 'Sediu EGB' : 'Site' }

  // Meta sub-line for a task row: phase (if any) + date range (or milestone date).
  function metaText(t) {
    const parts = []
    const f = (t.faza || '').trim()
    if (f) parts.push(f)
    if (t.is_milestone) { if (t.data_start) parts.push(formatDateShort(t.data_start)) }
    else if (t.data_start && t.data_scadenta) parts.push(`${formatDateShort(t.data_start)} → ${formatDateShort(t.data_scadenta)}`)
    else if (t.data_scadenta) parts.push(formatDateShort(t.data_scadenta))
    return parts.join(' · ') || '—'
  }
  // Due chip (only for open tasks): azi / mâine / depășit / date.
  function dueInfo(t) {
    if (isDone(t)) return null
    const d = t.data_scadenta ? t.data_scadenta.slice(0, 10) : ''
    if (!d) return null
    const k = dayDiff(today, d)
    if (k == null) return null
    if (k < 0) return { text: 'depășit', cls: 'hot' }
    if (k === 0) return { text: 'azi', cls: 'warm' }
    if (k === 1) return { text: 'mâine', cls: 'warm' }
    return { text: formatDateShort(d), cls: '' }
  }
  // Severity color for the index / accent.
  function sevColor(t) {
    if (isDone(t)) return 'var(--text-faint)'
    const d = t.data_scadenta ? t.data_scadenta.slice(0, 10) : ''
    const k = d ? dayDiff(today, d) : null
    if (k != null && k < 0) return 'var(--danger)'
    if (k != null && k <= 1) return 'var(--accent)'
    return 'var(--border-strong)'
  }

  // --- phases: group tasks under collapsible summary bars (view-only) ---
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

  function phaseSpanRect(ts) {
    const ds = ts.flatMap(t => [t.data_start, t.data_scadenta].filter(Boolean).map(x => x.slice(0, 10)))
    if (!ds.length) return null
    const lo = ds.reduce((a, b) => a < b ? a : b), hi = ds.reduce((a, b) => a > b ? a : b)
    return spanRect(lo, hi, win.start, win.days)
  }

  // implementation-period editor (the one editable thing here)
  let implOpen = $state(false)
  let implEditing = $state(null)
  function newImpl() { implEditing = null; implOpen = true }
  function editImpl(im) { implEditing = im; implOpen = true }

  function openTask(t) { onOpenTask?.(t.id) }
</script>

{#if loading}
  <div class="gk">{#each Array(5) as _}<Skeleton height="46px" />{/each}</div>
{:else if error}
  <p class="g-err">Eroare: {error}</p>
{:else if data.tasks.length === 0 && (data.implementari || []).length === 0}
  <EmptyState icon={Milestone} title="Nimic de arătat" description="Taskurile apar aici automat din tabul „Taskuri”. Adaugă o perioadă de implementare (Site / Sediu EGB) ca să apară pe diagramă.">
    <div class="es-actions">
      <button class="exp-btn" onclick={newImpl}><MapPin size={15} /> Perioadă</button>
    </div>
  </EmptyState>
{:else}
  <div class="g-toolbar">
    <div class="g-tl">
      <button class="exp-btn" onclick={newImpl} title="Adaugă perioadă de implementare (Site / Sediu EGB)"><MapPin size={14} /> Perioadă</button>
      <a class="exp-btn" href={`/api/proiecte/${projectId}/gantt.pdf`} target="_blank" rel="noopener" title="Export PDF (client)"><FileDown size={14} /> PDF</a>
      <a class="exp-btn" href={`/api/proiecte/${projectId}/gantt.xlsx`} title="Export Excel"><Sheet size={14} /> Excel</a>
    </div>
    <span class="g-legend">
      <span class="lg"><span class="sw done"></span>finalizat</span>
      <span class="lg"><span class="sw prog"></span>în lucru</span>
      <span class="lg"><span class="sw todo"></span>de făcut</span>
      <span class="lg"><span class="sw-ms"></span>milestone</span>
      <span class="lg"><span class="sw" style="background:#3f9dc4"></span>site</span>
      <span class="lg"><span class="sw" style="background:#c99a3a"></span>sediu</span>
    </span>
  </div>

  <div class="gantt2">
    <!-- left: read-only task list -->
    <div class="g-table">
      <div class="gh-row lhead"><span>Activități</span></div>
      {#each displayRows as row (row.kind === 'phase' ? 'p:' + row.phase : row.kind === 'impl' ? 'i:' + row.im.id : row.t.id)}
        {#if row.kind === 'impl'}
          <button class="impl-lrow loc-{row.im.locatie}" onclick={() => editImpl(row.im)} title="Editează perioada">
            {#if row.im.locatie === 'sediu'}<Building2 size={14} />{:else}<MapPin size={14} />{/if}
            <span class="impl-lname">{locLabel(row.im.locatie)}{row.im.eticheta ? ' · ' + row.im.eticheta : ''}</span>
          </button>
        {:else if row.kind === 'phase'}
          <div class="ph-row" onclick={() => togglePhase(row.phase)} role="button" tabindex="0">
            <ChevronRight size={14} class="ph-chev {collapsed.has(row.phase) ? '' : 'open'}" />
            <span class="ph-name">{row.phase}</span>
            <span class="ph-meta">{row.tasks.length} task{row.tasks.length === 1 ? '' : 'uri'}</span>
          </div>
        {:else}
          {@const t = row.t}
          {@const due = dueInfo(t)}
          <button class="tk-row" class:done={isDone(t)} style="--sev:{sevColor(t)}" onclick={() => openTask(t)} title="Deschide în tabul Taskuri">
            <span class="tix">
              {#if isDone(t)}<CheckCircle2 size={15} />{:else}{String(row.no).padStart(2, '0')}{/if}
            </span>
            <span class="row-content">
              <span class="row-title">{#if t.is_milestone}<Diamond size={11} class="mini-ms" />{/if}{t.titlu}</span>
              <span class="row-meta">{metaText(t)}</span>
            </span>
            {#if due}<span class="due-chip {due.cls}">{due.text}</span>{/if}
            <ChevronRight size={14} class="tk-chev" />
          </button>
        {/if}
      {/each}
    </div>

    <!-- right: read-only timeline -->
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
                {#if pr}<div class="phase-bar" style="left:{pr.left}%; width:{pr.width}%" title={row.phase}></div>{/if}
              </div>
            {:else}
              {@const t = row.t}
              {@const r = rectFor(t)}
              <div class="gb-row">
                {#if t.is_milestone}
                  {#if msPct(t) != null}<div class="ms" style="left:{msPct(t)}%" title="{t.titlu} · {formatDateShort(t.data_start)}"></div>{/if}
                {:else if r}
                  <div class="bar {statusClass(t)}" style="left:{r.left}%; width:{r.width}%" title="{t.titlu} · {formatDateShort(t.data_start)} → {formatDateShort(t.data_scadenta)}"></div>
                {/if}
              </div>
            {/if}
          {/each}
        </div>
      </div>
    </div>
  </div>
{/if}

<ImplPeriodModal bind:open={implOpen} projectId={projectId} period={implEditing} onsaved={load} />

<style>
  .gk { display: flex; flex-direction: column; gap: 6px; }
  .g-err { color: var(--danger); padding: var(--space-md); }
  .es-actions { display: flex; gap: var(--space-sm); flex-wrap: wrap; justify-content: center; }

  .g-toolbar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); margin-bottom: var(--space-sm); flex-wrap: wrap; }
  .g-tl { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }
  .exp-btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 12px; border-radius: var(--radius-md); background: var(--bg-panel); border: 1px solid var(--border); color: var(--text-secondary); font-size: var(--font-small); font-weight: var(--fw-medium); cursor: pointer; text-decoration: none; }
  .exp-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-subtle); }
  .g-legend { display: flex; gap: 12px; flex-wrap: wrap; }
  .lg { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-micro); color: var(--text-dim); font-family: var(--font-mono); }
  .sw { width: 18px; height: 10px; border-radius: 3px; }
  .sw.done { background: var(--success); } .sw.prog { background: var(--accent); }
  .sw.todo { background: var(--bg-elevated); border: 1px solid var(--border-strong); }
  .sw-ms { width: 10px; height: 10px; background: var(--accent); transform: rotate(45deg); }

  /* ===== two-pane gantt ===== */
  .gantt2 { --row-h: 46px; --head-h: 38px; display: flex; border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; background: var(--bg-panel); }

  .g-table { flex: none; width: 340px; border-right: 2px solid var(--border-strong); background: var(--bg-surface); }
  .gh-row { height: var(--head-h); display: flex; align-items: center; background: var(--bg-overlay); border-bottom: 1px solid var(--border-strong); font-family: var(--font-mono); font-size: var(--font-micro); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--text-dim); }
  .lhead { padding: 0 14px; }

  /* read-only task rows (island look, aligned to timeline) */
  .tk-row { height: var(--row-h); width: 100%; display: flex; align-items: center; gap: var(--space-sm); padding: 0 12px; border: none; border-bottom: 1px solid var(--border); background: none; text-align: left; cursor: pointer; color: var(--text-secondary); position: relative; transition: background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); }
  .tk-row::before { content: ''; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px; border-radius: 0 2px 2px 0; background: var(--sev, transparent); opacity: 0.7; }
  .tk-row:hover { background: var(--bg-hover); }
  .tk-row:last-child { border-bottom: 0; }
  .tk-row .tix { font-family: var(--font-mono); font-size: 0.95rem; font-weight: var(--fw-bold); letter-spacing: -0.04em; color: color-mix(in srgb, var(--sev, var(--border-strong)) 80%, transparent); min-width: 24px; flex-shrink: 0; font-variant-numeric: tabular-nums; display: inline-flex; align-items: center; }
  .row-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .row-title { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: inline-flex; align-items: center; gap: 5px; }
  .row-title :global(.mini-ms) { color: var(--accent); flex: none; }
  .row-meta { font-size: var(--font-tiny); color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tk-row.done .row-title { color: var(--text-dim); text-decoration: line-through; text-decoration-color: var(--text-faint); }
  .tk-row.done .tix { color: var(--success); }
  .due-chip { font-family: var(--font-mono); font-size: var(--font-micro); padding: 3px 9px; border-radius: var(--radius-full); background: var(--bg-hover); color: var(--text-dim); white-space: nowrap; flex-shrink: 0; }
  .due-chip.hot { background: var(--danger-subtle); color: var(--danger); }
  .due-chip.warm { background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .tk-row :global(.tk-chev) { color: var(--text-faint); flex: none; }

  /* phases */
  .ph-row { height: var(--row-h); display: flex; align-items: center; gap: 6px; padding: 0 10px; background: var(--bg-overlay); border-bottom: 1px solid var(--border); cursor: pointer; }
  .ph-row:hover { background: var(--bg-hover); }
  .ph-row :global(.ph-chev) { color: var(--text-dim); transition: transform var(--dur-fast) var(--ease); flex: none; }
  .ph-row :global(.ph-chev.open) { transform: rotate(90deg); }
  .ph-name { flex: 1; min-width: 0; color: var(--text); font-size: var(--font-small); font-weight: var(--fw-semibold); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ph-meta { font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text-dim); flex: none; }

  /* implementation periods (Site / Sediu EGB) — the editable rows */
  .impl-lrow { height: var(--row-h); width: 100%; display: flex; align-items: center; gap: 7px; padding: 0 12px; border: none; border-bottom: 1px solid var(--border); border-left: 3px solid var(--il); background: color-mix(in srgb, var(--il) 8%, transparent); color: var(--text); cursor: pointer; text-align: left; }
  .impl-lrow:hover { background: color-mix(in srgb, var(--il) 16%, transparent); }
  .impl-lname { font-size: var(--font-small); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .loc-site { --il: #3f9dc4; } .loc-sediu { --il: #b98a2e; }
  .impl-band { position: absolute; top: 50%; transform: translateY(-50%); height: 18px; border-radius: 5px; display: flex; align-items: center; padding: 0 8px; border: none; cursor: pointer; overflow: hidden; background: var(--il); color: #10130f; }
  .impl-band.loc-site { background: #3f9dc4; } .impl-band.loc-sediu { background: #c99a3a; }
  .ib-txt { font-size: 0.62rem; font-weight: var(--fw-bold); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ph-track { background: color-mix(in srgb, var(--accent) 4%, transparent); }
  .phase-bar { position: absolute; top: 50%; transform: translateY(-50%); height: 8px; border-radius: 3px; background: color-mix(in oklab, var(--text-dim) 34%, var(--bg-panel)); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--text-dim) 40%, transparent); }

  /* ===== timeline ===== */
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
  .bar { position: absolute; top: 50%; transform: translateY(-50%); height: 20px; border-radius: 6px; z-index: 1; }
  .bar.done { background: color-mix(in oklab, var(--success) 55%, var(--bg-panel)); }
  .bar.prog { background: color-mix(in oklab, var(--accent) 55%, var(--bg-panel)); }
  .bar.todo { background: var(--bg-elevated); border: 1px solid var(--border-strong); }
  .ms { position: absolute; top: 50%; width: 15px; height: 15px; background: var(--accent); border: 2px solid var(--bg-panel); transform: translate(-50%, -50%) rotate(45deg); box-shadow: 0 0 0 3px var(--accent-subtle); z-index: 2; }

  @media (max-width: 720px) {
    .g-table { width: 210px; }
  }
</style>
