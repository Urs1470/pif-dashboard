<script>
  import { onMount } from 'svelte'
  import {
    FolderKanban, AlertTriangle,
    CalendarClock, ChevronRight
  } from '@lucide/svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import { apiJson } from '../lib/api.js'
  import { formatDate } from '../lib/formatters.js'
  import { navigate } from '../lib/router.svelte.js'
  import { morphNavigate } from '../lib/focus.js'
  import Card from '../components/ui/Card.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import TodayBoard from '../components/TodayBoard.svelte'
  import { motion } from '../lib/motion.svelte.js'

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

  // Count-up: numbers ease 0 -> value once the data lands (respects reduced-motion)
  let animVals = $state({ active: 0, urgent: 0, done: 0, deadline: 0 })
  let _animStarted = false

  $effect(() => {
    if (!dashboard || _animStarted) return
    _animStarted = true
    const s = dashboard.stats || {}
    const targets = {
      active: s.active_projects || 0,
      urgent: s.urgent_count || 0,
      done: s.weekly_done || 0,
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
        done: targets.done * e,
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
    if (h < 12) return 'Bună dimineața'
    if (h < 18) return 'Bună ziua'
    return 'Bună seara'
  }

  function daysUntil(d) {
    if (!d) return 99
    return Math.ceil((new Date(d) - new Date().setHours(0, 0, 0, 0)) / 86400000)
  }

  // Severitate pentru insulele din liste: hot = depasit, warm = azi/maine, cool = restul
  function sev(d) {
    const n = daysUntil(d)
    if (n < 0) return 'var(--danger)'
    if (n <= 1) return 'var(--accent-hover)'
    return 'var(--border-strong)'
  }
  function dueChip(d) {
    if (!d) return ''
    const n = daysUntil(d)
    if (n < 0) return `depășit \u00b7 ${formatDate(d)}`
    if (n === 0) return 'azi'
    if (n === 1) return 'mâine'
    return formatDate(d)
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

  onMount(loadDashboard)
</script>

<div class="page">
  <div class="page-head">
    <div class="greet-left">
      <h1 class="greeting">{greeting()}, Ion</h1>
      <p class="today">{todayRO()}</p>
    </div>
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
        <div class="kpi-sub">{(s.urgent_count || 0) > 0 ? 'scadență apropiată' : 'fără urgente'}</div>
      </button>
      <button class="kpi cell-in" onclick={() => navigate('/tasks')} title="Vezi taskurile">
        <div class="kpi-head"><span class="kpi-chip success"><SolidIcon name="check" size={16} /></span><span class="kpi-label">Finalizate — 7 zile</span></div>
        <div class="kpi-val success">{Math.round(animVals.done)}{#if (s.weekly_done_delta || 0) !== 0}<span class="kpi-delta {(s.weekly_done_delta || 0) > 0 ? 'up' : 'down'}">{(s.weekly_done_delta || 0) > 0 ? '+' : ''}{s.weekly_done_delta}</span>{/if}</div>
        {#if spark.some(v => v > 0)}
          <div class="kpi-spark">{#each spark as v}<span style="height: {Math.max(8, (v / sparkMax) * 100)}%"></span>{/each}</div>
        {:else}
          <div class="kpi-sub">taskuri bifate</div>
        {/if}
      </button>
      <button class="kpi cell-in" onclick={() => navigate('/projects')} title="Vezi deadline-urile">
        <div class="kpi-head"><span class="kpi-chip neutral"><CalendarClock size={16} /></span><span class="kpi-label">Deadline-uri</span></div>
        <div class="kpi-val">{Math.round(animVals.deadline)}</div>
        <div class="kpi-sub">în următoarele 7 zile</div>
      </button>
    </div>

    <TodayBoard />

    <div class="cards-grid">
      {#if dashboard.urgent_tasks?.length}
        <Card padding={false}>
          <div class="card-head"><span class="ch-ico ico-red"><AlertTriangle size={13} /></span><span class="ch-label">Task-uri urgente</span><span class="card-count">{dashboard.urgent_tasks.length}</span></div>
          <div class="card-list scroll">
            {#each dashboard.urgent_tasks as t, i}
              <button class="isl" style="--sev: {t.data_scadenta ? sev(t.data_scadenta) : 'var(--danger)'}" onclick={(e) => goToTask(e, t)}>
                <span class="tix">{String(i + 1).padStart(2, '0')}</span>
                <div class="row-content">
                  <div class="row-title">{t.titlu}</div>
                  <div class="row-meta">{t.proiect_nume || 'Task global'}</div>
                </div>
                {#if t.data_scadenta}<span class="due-chip" class:hot={daysUntil(t.data_scadenta) < 0} class:warm={daysUntil(t.data_scadenta) >= 0 && daysUntil(t.data_scadenta) <= 1}>{dueChip(t.data_scadenta)}</span>{/if}
                <ChevronRight size={14} />
              </button>
            {/each}
          </div>
        </Card>
      {/if}

      {#if dashboard.upcoming_deadlines?.length}
        <Card padding={false}>
          <div class="card-head"><span class="ch-ico ico-vio"><CalendarClock size={13} /></span><span class="ch-label">Deadline-uri</span><span class="card-count">{dashboard.upcoming_deadlines.length}</span></div>
          <div class="card-list">
            {#each dashboard.upcoming_deadlines.slice(0, 5) as p, i}
              <button class="isl" style="--sev: {sev(p.deadline)}" onclick={() => navigate(`/projects/${p.id}`)}>
                <span class="tix">{String(i + 1).padStart(2, '0')}</span>
                <div class="row-content">
                  <div class="row-title">{p.nume}</div>
                  <div class="row-meta">{p.client || '—'}</div>
                </div>
                <span class="due-chip" class:hot={daysUntil(p.deadline) < 0} class:warm={daysUntil(p.deadline) >= 0 && daysUntil(p.deadline) <= 1}>{dueChip(p.deadline)}</span>
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

  .kpi-skeleton { margin-bottom: var(--space-lg); }
  .kpi-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-md); margin-bottom: var(--space-lg); }
  .kpi { text-align: left; font-family: inherit; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 18px 20px; cursor: pointer; display: flex; flex-direction: column; transition: transform var(--dur-base) var(--ease), border-color var(--dur-base) var(--ease), box-shadow var(--dur-base) var(--ease); }
  .kpi:hover { transform: translateY(-4px); border-color: var(--border-strong); box-shadow: var(--shadow-lg); }
  .kpi-head { display: flex; align-items: center; gap: 9px; margin-bottom: 12px; }
  .kpi-chip { width: 30px; height: 30px; border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
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
  .kpi-sub { font-size: var(--font-tiny); color: var(--text-dim); margin-top: 6px; }
  .kpi-track { height: 4px; background: var(--bg-hover); border-radius: var(--radius-full); margin-top: 11px; overflow: hidden; }
  .kpi-track span { display: block; height: 100%; background: var(--accent); border-radius: var(--radius-full); }
  .kpi-spark { display: flex; align-items: flex-end; gap: 5px; height: 30px; margin-top: 10px; }
  .kpi-spark span { flex: 1; background: var(--success); border-radius: 3px 3px 0 0; opacity: 0.35; min-height: 2px; }
  .kpi-spark span:nth-last-child(-n+3) { opacity: 1; }

  .cards-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: var(--space-md); align-items: start; }
  .card-head { display: flex; align-items: center; gap: 9px; padding: 12px var(--space-md); border-bottom: 1px solid var(--border); }
  .ch-ico { width: 22px; height: 22px; border-radius: 7px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .ch-ico.ico-red { background: var(--danger-subtle); color: var(--danger); }
  .ch-ico.ico-vio { background: var(--purple-subtle); color: var(--purple); }
  .ch-label { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-faint); }
  .card-count { margin-left: auto; font-size: var(--font-tiny); padding: 1px 8px; border-radius: var(--radius-full); background: var(--bg-hover); color: var(--text-secondary); }

  .card-list { display: flex; flex-direction: column; gap: 6px; padding: var(--space-sm); }
  .card-list.scroll { max-height: 268px; overflow-y: auto; scrollbar-width: thin; }
  /* Insula (V3+V2): rand plutitor cu index mono ghost si underline de
     severitate pe muchia de jos (—sev vine inline pe rand). */
  .isl { position: relative; display: flex; align-items: center; gap: var(--space-sm); padding: 9px 12px 11px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-md); text-align: left; cursor: pointer; color: var(--text-secondary); overflow: hidden; transition: transform var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .isl::after { content: ''; position: absolute; left: 12px; bottom: 0; height: 2px; width: 40px; border-radius: 2px 2px 0 0; background: var(--sev, var(--border-strong)); box-shadow: 0 0 8px color-mix(in srgb, var(--sev, transparent) 45%, transparent); }
  .isl:hover { transform: translateX(4px); border-color: var(--border-strong); }
  .tix { font-family: var(--font-mono); font-size: 1.05rem; font-weight: var(--fw-bold); letter-spacing: -0.04em; color: color-mix(in srgb, var(--sev, var(--border-strong)) 75%, transparent); min-width: 30px; flex-shrink: 0; font-variant-numeric: tabular-nums; }
  .row-content { flex: 1; min-width: 0; }
  .row-title { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .row-meta { font-size: var(--font-tiny); color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .due-chip { font-family: var(--font-mono); font-size: var(--font-micro); padding: 3px 9px; border-radius: var(--radius-full); background: var(--bg-hover); color: var(--text-dim); white-space: nowrap; flex-shrink: 0; }
  .due-chip.hot { background: var(--danger-subtle); color: var(--danger); }
  .due-chip.warm { background: var(--accent-subtle); color: var(--accent-on-subtle); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .kpi-bar { grid-template-columns: repeat(2, 1fr); gap: var(--space-sm); }
    .cards-grid { grid-template-columns: 1fr; }
    .greeting { font-size: var(--font-h2); white-space: normal; }
  }
</style>
