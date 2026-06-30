<script>
  import { onMount } from 'svelte'
  import {
    Home as HomeIcon, FolderKanban, AlertTriangle,
    CalendarClock, ChevronRight, RotateCcw
  } from '@lucide/svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import { apiJson } from '../lib/api.js'
  import { formatDuration, formatDate, formatElapsed } from '../lib/formatters.js'
  import { navigate } from '../lib/router.svelte.js'
  import { timer, loadActiveTimer, stopActiveTimer } from '../stores/timer.svelte.js'
  import Card from '../components/ui/Card.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import TodayBoard from '../components/TodayBoard.svelte'

  const kindLabels = { project: 'Proiect', task: 'Task', global_task: 'Task global' }

  function goToActiveTimer() {
    if (timer.active?.project_id) navigate(`/projects/${timer.active.project_id}`)
  }
  async function stopActive(e) {
    e.stopPropagation()
    await stopActiveTimer()
  }

  let dashboard = $state(null)
  let loading = $state(true)
  let error = $state(null)
  let recents = $state([])

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

  onMount(async () => {
    try {
      recents = JSON.parse(localStorage.getItem('recent_projects') || '[]').slice(0, 5)
    } catch (_) {}
    try {
      dashboard = await apiJson('/api/dashboard/home')
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
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
    <Card><p class="error-msg">Eroare: {error}</p></Card>
  {:else if dashboard}
    {@const s = dashboard.stats || {}}
    <div class="kpi-bar">
      <div class="kpi">
        <div class="kpi-top"><span class="kpi-label">Proiecte Active</span><FolderKanban size={15} /></div>
        <div class="kpi-val accent">{s.active_projects ?? 0}</div>
        <div class="kpi-sub">din {s.total_projects ?? 0} total</div>
      </div>
      <div class="kpi">
        <div class="kpi-top"><span class="kpi-label">Urgente</span><AlertTriangle size={15} /></div>
        <div class="kpi-val warn">{s.urgent_count ?? 0}</div>
        <div class="kpi-sub">{(s.urgent_count || 0) > 0 ? 'scadenta apropiata' : 'fara urgente'}</div>
      </div>
      <div class="kpi">
        <div class="kpi-top"><span class="kpi-label">Ore Saptamana</span><SolidIcon name="clock" size={15} /></div>
        <div class="kpi-val success">{s.weekly_hours ?? 0}<span class="unit">h</span></div>
        <div class="kpi-sub">
          {#if (s.weekly_delta || 0) > 0}<span class="up">+{s.weekly_delta}h</span> vs. sapt. trecuta
          {:else if (s.weekly_delta || 0) < 0}<span class="down">{s.weekly_delta}h</span> vs. sapt. trecuta
          {:else}la fel ca sapt. trecuta{/if}
        </div>
      </div>
      <div class="kpi">
        <div class="kpi-top"><span class="kpi-label">Deadline-uri</span><CalendarClock size={15} /></div>
        <div class="kpi-val">{s.deadline_count ?? 0}</div>
        <div class="kpi-sub">in urmatoarele 7 zile</div>
      </div>
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
        <div class="card-full">
          <Card padding={false}>
            <div class="card-head danger"><AlertTriangle size={16} /><span>Task-uri Urgente</span><span class="card-count">{dashboard.urgent_tasks.length}</span></div>
            <div class="card-list scroll">
              {#each dashboard.urgent_tasks as t}
                <button class="list-row" onclick={() => t.proiect_id ? navigate(`/projects/${t.proiect_id}`) : navigate('/tasks')}>
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
        </div>
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
  .greeting { font-size: var(--font-h1); font-weight: 700; color: var(--text); white-space: nowrap; }
  .today { font-size: var(--font-small); color: var(--text-dim); margin-top: 2px; text-transform: capitalize; }

  .timer-card { display: flex; align-items: center; gap: 13px; padding: 12px 16px; border-radius: 14px; background: var(--bg-surface); border: 1px solid var(--accent-ring); cursor: pointer; transition: border-color var(--dur-fast) var(--ease); }
  .timer-card:hover { border-color: var(--accent); }
  .tc-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--accent); animation: tcpulse 1.5s ease-in-out infinite; flex-shrink: 0; }
  @keyframes tcpulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
  .tc-main { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
  .tc-eyebrow { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--accent); }
  .tc-name { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px; }
  .tc-elapsed { font-family: var(--font-mono); font-size: 19px; font-weight: 700; color: var(--accent); letter-spacing: 0.04em; }
  .tc-stop { width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--danger); cursor: pointer; transition: all var(--dur-fast) var(--ease); flex-shrink: 0; }
  .tc-stop:hover { background: var(--danger); color: white; }

  .kpi-skeleton { margin-bottom: var(--space-lg); }
  .kpi-bar { background: var(--bg-surface); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); overflow: hidden; display: grid; grid-template-columns: repeat(4, 1fr); margin-bottom: var(--space-lg); }
  .kpi { padding: 16px 18px; border-right: 1px solid var(--border-subtle); }
  .kpi:last-child { border-right: none; }
  .kpi-top { display: flex; justify-content: space-between; align-items: center; color: var(--text-dim); margin-bottom: var(--space-sm); }
  .kpi-label { font-size: 10.5px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; }
  .kpi-val { font-family: var(--font-mono); font-size: 30px; font-weight: 700; color: var(--text); line-height: 1; }
  .kpi-val.accent { color: var(--accent); }
  .kpi-val.warn { color: var(--warning); }
  .kpi-val.success { color: var(--success); }
  .unit { font-size: 14px; color: var(--text-dim); }
  .kpi-sub { font-size: 11px; color: var(--text-dim); margin-top: 4px; }
  .kpi-sub .up { color: var(--success); font-weight: 600; }
  .kpi-sub .down { color: var(--danger); font-weight: 600; }

  .section { margin-bottom: var(--space-lg); }
  .section-head { display: flex; align-items: center; gap: 6px; font-size: var(--font-tiny); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-dim); margin-bottom: var(--space-sm); }

  .recent-strip { display: flex; gap: var(--space-sm); overflow-x: auto; padding-bottom: 4px; }
  .recent-card { flex: 0 0 160px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-sm) var(--space-md); text-align: left; cursor: pointer; transition: border-color var(--dur-fast) var(--ease); }
  .recent-card:hover { border-color: var(--accent); }
  .recent-tip { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--accent); display: block; margin-bottom: 4px; }
  .recent-tip.pif { color: var(--accent); }
  .recent-name { font-size: var(--font-small); font-weight: 500; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .recent-client { font-size: var(--font-tiny); color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .cards-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-md); }
  .card-full { grid-column: 1 / -1; }
  .card-head { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-md); border-bottom: 1px solid var(--border); font-size: var(--font-small); font-weight: 600; color: var(--text); }
  .card-head.danger { color: var(--danger); }
  .card-head.success { color: var(--success); }
  .card-count { margin-left: auto; font-size: var(--font-tiny); padding: 1px 8px; border-radius: var(--radius-full); background: var(--bg-hover); color: var(--text-secondary); }

  .card-list { display: flex; flex-direction: column; }
  .card-list.scroll { max-height: 248px; overflow-y: auto; scrollbar-width: thin; }
  .list-row { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) var(--space-md); text-align: left; cursor: pointer; transition: background var(--dur-fast) var(--ease); color: var(--text-secondary); }
  .list-row:hover { background: var(--bg-hover); }
  .list-row + .list-row { border-top: 1px solid var(--border); }
  .row-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-dim); flex-shrink: 0; }
  .row-dot.urgent { background: var(--danger); }
  .row-dot.due { background: var(--warning); }
  .row-dot.done { background: var(--success); }
  .row-content { flex: 1; min-width: 0; }
  .row-title { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .row-title.line-through { text-decoration: line-through; color: var(--text-dim); }
  .row-meta { font-size: var(--font-tiny); color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .error-msg { color: var(--danger); padding: var(--space-md); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .kpi-bar { grid-template-columns: repeat(2, 1fr); }
    .kpi:nth-child(2n) { border-right: none; }
    .kpi:nth-child(n+3) { border-top: 1px solid var(--border-subtle); }
    .cards-grid { grid-template-columns: 1fr; }
    .greeting { font-size: var(--font-h2); white-space: normal; }
    .timer-card { flex: 1; }
  }
</style>
