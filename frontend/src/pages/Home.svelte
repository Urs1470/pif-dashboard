<script>
  import { onMount } from 'svelte'
  import { fly } from 'svelte/transition'
  import {
    Home as HomeIcon, FolderKanban, AlertTriangle,
    CalendarClock, ChevronRight, RotateCcw
  } from '@lucide/svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import { apiJson } from '../lib/api.js'
  import { formatDuration, formatDate, formatElapsed } from '../lib/formatters.js'
  import { navigate } from '../lib/router.svelte.js'
  import { morphNavigate } from '../lib/focus.js'
  import { timer, loadActiveTimer, stopActiveTimer } from '../stores/timer.svelte.js'
  import Card from '../components/ui/Card.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import TodayBoard from '../components/TodayBoard.svelte'
  import { motion, motionDuration, DUR_BASE } from '../lib/motion.svelte.js'

  const kindLabels = { project: 'Proiect', task: 'Task', global_task: 'Task global' }

  function goToActiveTimer() {
    if (timer.active?.project_id) navigate(`/projects/${timer.active.project_id}`)
  }
  async function stopActive(e) {
    e.stopPropagation()
    await stopActiveTimer()
  }

  // Click a task anywhere on Home -> jump to it (its page scrolls it to center +
  // flashes a highlight via the focusOnLand action on the destination row).
  function goToTask(e, t) {
    const src = e?.currentTarget
    if (t.proiect_id) morphNavigate(src, `/projects/${t.proiect_id}`, 'task', t.id)
    else morphNavigate(src, '/tasks', 'global', t.id)
  }

  let dashboard = $state(null)
  let loading = $state(true)
  let error = $state(null)
  let recents = $state([])

  // Count-up: numbers ease 0 -> value once the data lands (respects reduced-motion)
  let animVals = $state({ active: 0, urgent: 0, hours: 0, deadline: 0 })
  let _animStarted = false

  function fmtHours(cur) {
    const target = dashboard?.stats?.weekly_hours ?? 0
    return Number.isInteger(target) ? String(Math.round(cur)) : cur.toFixed(1)
  }

  $effect(() => {
    if (!dashboard || _animStarted) return
    _animStarted = true
    const s = dashboard.stats || {}
    const targets = {
      active: s.active_projects || 0,
      urgent: s.urgent_count || 0,
      hours: s.weekly_hours || 0,
      deadline: s.deadline_count || 0,
    }
    // No animation when motion is reduced or the tab is hidden (rAF is paused
    // there, which would otherwise leave the numbers stuck at 0).
    if (motion.reduced || document.hidden) {
      animVals = targets
      return
    }
    let raf = 0
    const t0 = performance.now()
    const dur = 650
    function frame(now) {
      const p = Math.min((now - t0) / dur, 1)
      const e = 1 - Math.pow(1 - p, 3)
      animVals = {
        active: targets.active * e,
        urgent: targets.urgent * e,
        hours: targets.hours * e,
        deadline: targets.deadline * e,
      }
      if (p < 1) raf = requestAnimationFrame(frame)
      else animVals = targets
    }
    raf = requestAnimationFrame(frame)
    // Safety net: if rAF gets throttled (tab loses focus mid-run), still settle.
    const safety = setTimeout(() => { animVals = targets }, dur + 400)
    return () => { cancelAnimationFrame(raf); clearTimeout(safety) }
  })

  function greeting() {
    const h = new Date().getHours()
    if (h < 12) return 'Buna dimineata'
    if (h < 18) return 'Buna ziua'
    return 'Buna seara'
  }

  function todayRO() {
    return new Date().toLocaleDateString('ro-RO', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
    })
  }

  async function loadDashboard() {
    loading = true
    error = null
    try {
      dashboard = await apiJson('/api/dashboard/home')
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  onMount(async () => {
    try {
      recents = JSON.parse(localStorage.getItem('recent_projects') || '[]').slice(0, 5)
    } catch (_) {}
    await loadDashboard()
    loadActiveTimer()
  })
</script>

<div class="page">
  <div class="page-head">
    <div class="greet-left">
      <h1 class="greeting">{greeting()}, Ion</h1>
      <p class="today">{todayRO()}</p>
    </div>
    {#if timer.active}
      <div class="timer-card" role="button" tabindex="0"
        transition:fly={{ y: -8, duration: motionDuration(DUR_BASE) }}
        onclick={goToActiveTimer} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goToActiveTimer() } }}>
        <span class="tc-dot"></span>
        <div class="tc-main">
          <span class="tc-eyebrow">Cronometru activ · {kindLabels[timer.active.kind] || 'Timer'}</span>
          <span class="tc-name">{timer.active.label || '—'}</span>
        </div>
        <span class="tc-elapsed">{formatElapsed(timer.elapsed)}</span>
        <button class="tc-stop" title="Opreste cronometrul" onclick={stopActive}><SolidIcon name="stop" size={15} /></button>
      </div>
    {/if}
  </div>

  {#if loading}
    <div class="kpi-skeleton"><Skeleton height="72px" /></div>
  {:else if error}
    <ErrorState message={error} onretry={loadDashboard} />
  {:else if dashboard}
    {@const s = dashboard.stats || {}}
    {@const spark = s.weekly_spark || []}
    {@const sparkMax = Math.max(...spark, 0.1)}
    {@const projPct = s.total_projects ? Math.min(100, (animVals.active / s.total_projects) * 100) : 0}
    <div class="kpi-bar">
      <button class="kpi cell-in" onclick={() => navigate('/projects')} title="Vezi proiectele">
        <div class="kpi-head"><span class="kpi-chip accent"><FolderKanban size={16} /></span><span class="kpi-label">Proiecte Active</span></div>
        <div class="kpi-val accent">{Math.round(animVals.active)}<span class="of">/ {s.total_projects ?? 0}</span></div>
        <div class="kpi-track"><span style="width: {projPct}%"></span></div>
      </button>
      <button class="kpi cell-in" onclick={() => navigate('/tasks')} title="Vezi taskurile urgente">
        <div class="kpi-head"><span class="kpi-chip warn"><AlertTriangle size={16} /></span><span class="kpi-label">Urgente</span></div>
        <div class="kpi-val warn">{#if (s.urgent_count || 0) > 0}<span class="kpi-pulse"></span>{/if}{Math.round(animVals.urgent)}</div>
        <div class="kpi-sub">{(s.urgent_count || 0) > 0 ? 'scadenta apropiata' : 'fara urgente'}</div>
      </button>
      <button class="kpi cell-in" onclick={() => navigate('/admin')} title="Vezi statistici">
        <div class="kpi-head"><span class="kpi-chip success"><SolidIcon name="clock" size={16} /></span><span class="kpi-label">Ore Saptamana</span></div>
        <div class="kpi-val success">{fmtHours(animVals.hours)}<span class="unit">h</span>{#if (s.weekly_delta || 0) !== 0}<span class="kpi-delta {(s.weekly_delta || 0) > 0 ? 'up' : 'down'}">{(s.weekly_delta || 0) > 0 ? '+' : ''}{s.weekly_delta}h</span>{/if}</div>
        {#if spark.length}
          <div class="kpi-spark">{#each spark as v}<span style="height: {Math.max(8, (v / sparkMax) * 100)}%"></span>{/each}</div>
        {:else}
          <div class="kpi-sub">vs. sapt. trecuta</div>
        {/if}
      </button>
      <button class="kpi cell-in" onclick={() => navigate('/projects')} title="Vezi deadline-urile">
        <div class="kpi-head"><span class="kpi-chip neutral"><CalendarClock size={16} /></span><span class="kpi-label">Deadline-uri</span></div>
        <div class="kpi-val">{Math.round(animVals.deadline)}</div>
        <div class="kpi-sub">in urmatoarele 7 zile</div>
      </button>
    </div>

    <TodayBoard />

    {#if recents.length > 0}
      <section class="section">
        <div class="section-head"><RotateCcw size={14} /><span>Continua</span></div>
        <div class="recent-strip">
          {#each recents as p}
            <button class="recent-card" onclick={() => navigate(`/projects/${p.id}`)}>
              {#if p.tip}<span class="recent-tip" class:pif={p.tip === 'PIF'}>{p.tip}</span>{/if}
              <div class="recent-name">{p.nume || '—'}</div>
              <div class="recent-client">{p.client || '—'}</div>
            </button>
          {/each}
        </div>
      </section>
    {/if}

    <div class="cards-grid">
      {#if dashboard.urgent_tasks?.length}
        <Card padding={false}>
          <div class="card-head danger"><AlertTriangle size={16} /><span>Task-uri Urgente</span><span class="card-count">{dashboard.urgent_tasks.length}</span></div>
          <div class="card-list scroll">
            {#each dashboard.urgent_tasks as t}
              <button class="list-row" onclick={(e) => goToTask(e, t)}>
                <div class="row-dot urgent"></div>
                <div class="row-content">
                  <div class="row-title">{t.titlu}</div>
                  <div class="row-meta">{t.proiect_nume || 'Task global'}{t.data_scadenta ? ` · ${formatDate(t.data_scadenta)}` : ''}</div>
                </div>
                <ChevronRight size={14} />
              </button>
            {/each}
          </div>
        </Card>
      {/if}

      {#if dashboard.upcoming_deadlines?.length}
        <Card padding={false}>
          <div class="card-head"><CalendarClock size={16} /><span>Deadline-uri</span><span class="card-count">{dashboard.upcoming_deadlines.length}</span></div>
          <div class="card-list">
            {#each dashboard.upcoming_deadlines.slice(0, 5) as p}
              <button class="list-row" onclick={() => navigate(`/projects/${p.id}`)}>
                <div class="row-dot due"></div>
                <div class="row-content">
                  <div class="row-title">{p.nume}</div>
                  <div class="row-meta">{p.client || '—'} · {formatDate(p.deadline)}</div>
                </div>
                <ChevronRight size={14} />
              </button>
            {/each}
          </div>
        </Card>
      {/if}

    </div>
  {/if}
</div>

<style>
  .page { padding: var(--space-lg); }
  .page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-md); margin-bottom: var(--space-lg); flex-wrap: wrap; }
  .greeting { font-family: var(--font-heading); font-size: var(--font-h1); font-weight: var(--fw-bold); letter-spacing: -0.03em; color: var(--text); white-space: nowrap; }
  .today { font-size: var(--font-small); color: var(--text-dim); margin-top: 2px; text-transform: capitalize; }

  .timer-card { display: flex; align-items: center; gap: 13px; padding: 12px 16px; border-radius: var(--radius-md); background: linear-gradient(150deg, color-mix(in srgb, var(--accent) 9%, var(--bg-surface)) 0%, var(--bg-surface) 60%); border: 1px solid var(--accent-ring); cursor: pointer; transition: border-color var(--dur-fast) var(--ease); }
  .timer-card:hover { border-color: var(--accent); }
  .tc-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--accent); animation: tcpulse 1.5s ease-in-out infinite; flex-shrink: 0; }
  @keyframes tcpulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
  .tc-main { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
  .tc-eyebrow { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--accent); }
  .tc-name { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px; }
  .tc-elapsed { font-family: var(--font-mono); font-size: var(--font-h3); font-weight: var(--fw-bold); color: var(--accent); letter-spacing: var(--tracking-wide); }
  .tc-stop { width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--danger); cursor: pointer; transition: all var(--dur-fast) var(--ease); flex-shrink: 0; }
  .tc-stop:hover { background: var(--danger); color: var(--bg); }

  .kpi-skeleton { margin-bottom: var(--space-lg); }
  .kpi-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-md); margin-bottom: var(--space-lg); }
  .kpi { text-align: left; font-family: inherit; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 18px 20px; cursor: pointer; display: flex; flex-direction: column; transition: transform var(--dur-base) var(--ease), border-color var(--dur-base) var(--ease), box-shadow var(--dur-base) var(--ease); }
  .kpi:hover { transform: translateY(-4px); border-color: var(--border-strong); box-shadow: var(--shadow-lg); }
  .kpi-head { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; }
  .kpi-chip { width: 30px; height: 30px; border-radius: 9px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .kpi-chip.accent { background: var(--accent-subtle); color: var(--accent); }
  .kpi-chip.warn { background: var(--warning-subtle); color: var(--warning); }
  .kpi-chip.success { background: var(--success-subtle); color: var(--success); }
  .kpi-chip.neutral { background: var(--bg-elevated); color: var(--text-secondary); }
  .kpi-label { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--text-dim); }
  .kpi-val { font-family: var(--font-heading); font-size: 2.3rem; font-weight: var(--fw-bold); letter-spacing: -0.04em; color: var(--text); line-height: 1; display: flex; align-items: baseline; gap: 6px; font-variant-numeric: tabular-nums; }
  .kpi-val.accent { color: var(--accent); }
  .kpi-val.warn { color: var(--warning); }
  .kpi-val.success { color: var(--success); }
  .kpi-val .of { font-size: var(--font-small); color: var(--text-dim); font-weight: var(--fw-semibold); }
  .kpi-pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--warning); align-self: center; animation: kpipulse 1.5s ease-in-out infinite; }
  @keyframes kpipulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
  .kpi-delta { font-family: var(--font-mono); font-size: var(--font-tiny); font-weight: var(--fw-semibold); padding: 2px 7px; border-radius: var(--radius-full); align-self: center; }
  .kpi-delta.up { background: var(--success-subtle); color: var(--success); }
  .kpi-delta.down { background: var(--danger-subtle); color: var(--danger); }
  .unit { font-size: var(--font-small); color: var(--text-dim); font-weight: var(--fw-semibold); }
  .kpi-sub { font-size: var(--font-tiny); color: var(--text-dim); margin-top: 6px; }
  .kpi-track { height: 4px; background: var(--bg-hover); border-radius: var(--radius-full); margin-top: 11px; overflow: hidden; }
  .kpi-track span { display: block; height: 100%; background: var(--accent); border-radius: var(--radius-full); }
  .kpi-spark { display: flex; align-items: flex-end; gap: 3px; height: 22px; margin-top: 9px; }
  .kpi-spark span { flex: 1; background: var(--success); border-radius: 3px 3px 0 0; opacity: 0.35; min-height: 2px; }
  .kpi-spark span:nth-last-child(-n+3) { opacity: 1; }

  .section { margin-bottom: var(--space-lg); }
  .section-head { display: flex; align-items: center; gap: 6px; font-size: var(--font-tiny); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--text-dim); margin-bottom: var(--space-sm); }

  .recent-strip { display: flex; gap: var(--space-sm); overflow-x: auto; padding-bottom: 4px; }
  .recent-card { flex: 0 0 160px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-sm) var(--space-md); text-align: left; cursor: pointer; transition: border-color var(--dur-fast) var(--ease); }
  .recent-card:hover { border-color: var(--accent); }
  .recent-tip { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--accent); display: block; margin-bottom: 4px; }
  .recent-tip.pif { color: var(--accent); }
  .recent-name { font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .recent-client { font-size: var(--font-tiny); color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .cards-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: var(--space-md); align-items: start; }
  .card-head { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-md); border-bottom: 1px solid var(--border); font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); }
  .card-head.danger { color: var(--danger); }
  .card-count { margin-left: auto; font-size: var(--font-tiny); padding: 1px 8px; border-radius: var(--radius-full); background: var(--bg-hover); color: var(--text-secondary); }

  .card-list { display: flex; flex-direction: column; }
  .card-list.scroll { max-height: 248px; overflow-y: auto; scrollbar-width: thin; }
  .list-row { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) var(--space-md); text-align: left; cursor: pointer; transition: background var(--dur-fast) var(--ease); color: var(--text-secondary); }
  .list-row:hover { background: var(--bg-hover); }
  .list-row + .list-row { border-top: 1px dashed var(--border); }
  .row-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-dim); flex-shrink: 0; }
  .row-dot.urgent { background: var(--danger); }
  .row-dot.due { background: var(--warning); }
  .row-content { flex: 1; min-width: 0; }
  .row-title { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .row-meta { font-size: var(--font-tiny); color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .kpi-bar { grid-template-columns: repeat(2, 1fr); gap: var(--space-sm); }
    .cards-grid { grid-template-columns: 1fr; }
    .greeting { font-size: var(--font-h2); white-space: normal; }
    .timer-card { flex: 1; }
  }
</style>
