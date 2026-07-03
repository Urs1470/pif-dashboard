<script>
  import { onMount } from 'svelte'
  import { CalendarRange, ChevronRight, ArrowRight, X, CheckCircle2, Repeat, ExternalLink } from '@lucide/svelte'
  import { plan, loadPlan, moveTaskDate, moveTaskTomorrow, toggleTaskDone } from '../stores/plan.svelte.js'
  import { buildDays, spanRect, dayDiff } from '../lib/planDates.js'
  import { formatDate, formatDateShort } from '../lib/formatters.js'
  import { toast } from '../stores/ui.svelte.js'
  import { morphNavigate } from '../lib/focus.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'

  // Distinct, CVD-legible lane hues on the warm-dark ground. Amber is reserved for
  // the app accent/active state, so lanes deliberately avoid it.
  const LANE_PALETTE = ['#3f9dc4', '#3fae74', '#8b6fe0', '#d1697f', '#b9a5ff', '#5f8fd0', '#c9a13a']
  const GLOBAL_COLOR = '#948a7d'

  function laneColor(id) {
    if (id === '__global__') return GLOBAL_COLOR
    let h = 0
    for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0
    return LANE_PALETTE[h % LANE_PALETTE.length]
  }

  const days = $derived(buildDays(plan.start, plan.days))
  const todayIdx = $derived(plan.start && plan.today ? dayDiff(plan.start, plan.today) : null)

  function isActive(s) { return s === 'in_progress' || s === 'in_lucru' }

  // Build the render model per lane: color, project band, deadline marker, and
  // each task's clamped rectangle.
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
      rect: spanRect(t.data_planificata, t.data_scadenta, plan.start, plan.days),
    }))
    return { ...lane, color, band, deadlinePct, tasks }
  }))

  // --- action popover (desktop) ---
  let sel = $state(null)
  let anchorEl = null
  let popX = $state(0)
  let popY = $state(0)

  function openBar(e, task, laneNume) {
    anchorEl = e.currentTarget
    const r = anchorEl.getBoundingClientRect()
    popX = Math.max(8, Math.min(r.left, window.innerWidth - 268))
    popY = Math.min(r.bottom + 6, window.innerHeight - 220)
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
      else toast('Finalizat ✓', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    closePop()
  }

  function onKey(e) { if (e.key === 'Escape') closePop() }

  onMount(() => {
    loadPlan()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })
</script>

<div class="page">
  <div class="page-header">
    <div class="page-title-row">
      <CalendarRange size={22} />
      <h1>Planificator</h1>
      <span class="count">14 zile</span>
    </div>
  </div>

  {#if plan.loading && plan.lanes.length === 0}
    <div class="skel">{#each Array(4) as _}<Skeleton height="72px" />{/each}</div>
  {:else if plan.error}
    <ErrorState message={plan.error} onretry={loadPlan} />
  {:else if views.length === 0}
    <EmptyState icon={CalendarRange} title="Nimic în următoarele 2 săptămâni" description="Planifică taskuri (din Astăzi sau din proiecte) ca să apară aici pe zile." />
  {:else}
    <!-- ===== Desktop swimlane ===== -->
    <div class="chart" style="--days:{plan.days}">
      <div class="chart-scroll">
        <div class="inner" style="min-width: calc(var(--lane-w) + var(--day-min) * {plan.days})">
          <!-- header -->
          <div class="p-head">
            <div class="lane-label head">Proiect</div>
            <div class="days">
              {#each days as d}
                <div class="day" class:we={d.isWeekend} class:today={d.iso === plan.today}>
                  <span class="d-wd">{d.wd}</span>
                  <span class="d-num">{d.dayNum}</span>
                  {#if d.isMonthStart}<span class="d-mo">{d.month}</span>{/if}
                </div>
              {/each}
            </div>
          </div>

          <!-- body -->
          <div class="p-body">
            <div class="overlay">
              {#each days as d}
                <div class="col-line" style="left:{(d.i / plan.days) * 100}%"></div>
                {#if d.isWeekend}<div class="col-we" style="left:{(d.i / plan.days) * 100}%; width:{100 / plan.days}%"></div>{/if}
                {#if d.iso === plan.today}<div class="col-today" style="left:{(d.i / plan.days) * 100}%; width:{100 / plan.days}%"></div>{/if}
              {/each}
              {#if todayIdx != null && todayIdx >= 0 && todayIdx < plan.days}
                <div class="today-line" style="left:{(todayIdx / plan.days) * 100}%"></div>
              {/if}
            </div>

            {#each views as lane (lane.tip + ':' + lane.id)}
              <div class="lane" style="--lane:{lane.color}">
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
                    {#each lane.tasks as t (t.tip + ':' + t.id)}
                      <div class="t-row">
                        {#if t.rect}
                          <button
                            class="bar"
                            class:active={isActive(t.status)}
                            class:todo={!isActive(t.status)}
                            class:urgent={(t.prioritate || '').toLowerCase() === 'urgent'}
                            class:single={t.rect.single}
                            style="left:{t.rect.left}%; width:{t.rect.width}%"
                            onclick={(e) => openBar(e, t, lane.nume)}
                            title="{t.titlu} · {t.data_planificata ? 'plan ' + formatDateShort(t.data_planificata) : ''}{t.data_scadenta ? ' → termen ' + formatDateShort(t.data_scadenta) : ''}"
                          >
                            <span class="bar-txt">{t.titlu}</span>
                            {#if t.recurenta}<Repeat size={11} />{/if}
                          </button>
                        {/if}
                      </div>
                    {/each}
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      </div>
    </div>

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
            <div class="mrow" class:urgent={(t.prioritate || '').toLowerCase() === 'urgent'}>
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
    <button class="pop-act" onclick={() => onDone(sel)}><CheckCircle2 size={15} /> Bifează</button>
    <button class="pop-close" onclick={closePop} aria-label="Închide"><X size={14} /></button>
  </div>
{/if}

<style>
  .page { padding-bottom: 96px; }
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-h1); font-weight: var(--fw-bold); font-family: var(--font-heading); letter-spacing: -0.02em; }
  .count { font-size: var(--font-tiny); padding: 2px 10px; border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent); font-family: var(--font-mono); }
  .skel { display: flex; flex-direction: column; gap: var(--space-sm); }

  /* ===== chart shell ===== */
  .chart { --lane-w: 200px; --day-min: 48px; --row-h: 30px;
    background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
  .chart-scroll { overflow-x: auto; }
  .inner { position: relative; }

  .p-head { display: flex; border-bottom: 1px solid var(--border-strong); background: var(--bg-overlay); position: sticky; top: 0; z-index: 3; }
  .lane-label { width: var(--lane-w); flex-shrink: 0; box-sizing: border-box; }
  .lane-label.head { padding: 8px 12px; font-family: var(--font-mono); font-size: var(--font-micro); letter-spacing: var(--tracking-wide); text-transform: uppercase; color: var(--text-dim); display: flex; align-items: center; }
  .days { flex: 1; display: flex; min-width: 0; }
  .day { flex: 1; min-width: var(--day-min); padding: 6px 2px 7px; display: flex; flex-direction: column; align-items: center; gap: 1px; border-left: 1px solid var(--border); position: relative; }
  .day.we { background: color-mix(in srgb, var(--purple) 6%, transparent); }
  .day.today { background: var(--accent-subtle); }
  .d-wd { font-size: var(--font-micro); color: var(--text-faint); text-transform: uppercase; letter-spacing: 0.03em; }
  .day.today .d-wd { color: var(--accent); }
  .d-num { font-family: var(--font-mono); font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary); font-variant-numeric: tabular-nums; }
  .day.today .d-num { color: var(--accent); }
  .d-mo { position: absolute; top: -1px; left: 3px; font-size: 0.55rem; font-family: var(--font-mono); color: var(--text-faint); text-transform: uppercase; }

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
    white-space: nowrap; overflow: hidden; cursor: pointer; text-align: left;
    transition: transform var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
    animation: barIn 0.4s var(--ease) both; }
  @keyframes barIn { from { opacity: 0; transform: scaleX(0.4); transform-origin: left; } }
  .bar:hover { transform: translateY(-1px); box-shadow: var(--shadow-md); z-index: 5; }
  .bar.active { background: var(--lane); color: #14100a; }
  .bar.todo { background: color-mix(in oklab, var(--lane) 20%, var(--bg-panel));
    border: 1px solid color-mix(in oklab, var(--lane) 45%, var(--bg-panel));
    color: color-mix(in oklab, var(--lane) 70%, var(--text)); }
  .bar.single { justify-content: center; padding: 0 4px; }
  .bar.single .bar-txt { display: none; }
  .bar.single::after { content: '◆'; font-size: 0.7rem; }
  .bar.urgent::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--danger); border-radius: 7px 0 0 7px; }
  .bar-txt { overflow: hidden; text-overflow: ellipsis; }

  @media (prefers-reduced-motion: reduce) { .bar { animation: none; } }

  /* ===== mobile grouped list ===== */
  .mlist { display: none; flex-direction: column; gap: var(--space-md); }
  .mgroup { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-sm) var(--space-sm) var(--space-xs); }
  .mg-head { display: flex; align-items: center; gap: 7px; padding: 4px 6px 8px; }
  .mg-head h2 { font-size: var(--font-body); font-weight: var(--fw-semibold); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .mg-count { margin-left: auto; font-size: var(--font-tiny); font-family: var(--font-mono); color: var(--text-dim); background: var(--bg-elevated); padding: 1px 8px; border-radius: var(--radius-full); }
  .mrow { position: relative; display: flex; align-items: center; gap: var(--space-xs); padding: 8px; background: var(--bg-panel); border: 1px solid var(--border); border-left: 3px solid var(--lane); border-radius: var(--radius-md); margin-bottom: 6px; }
  .mrow.urgent { border-left-color: var(--danger); }
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
</style>
