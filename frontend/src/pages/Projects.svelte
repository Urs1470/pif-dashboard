<script>
  import { onMount } from 'svelte'
  import { FolderKanban, Search, ChevronRight } from '@lucide/svelte'
  import { projects, loadProjects } from '../stores/projects.svelte.js'
  import { PROJECT_STATUS_LABELS, STATUS_COLORS, formatDate } from '../lib/formatters.js'
  import { navigate } from '../lib/router.svelte.js'
  import Badge from '../components/ui/Badge.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'

  const statusOptions = [
    { value: '', label: 'Toate' },
    { value: 'in_lucru', label: 'În Lucru' },
    { value: 'in_asteptare', label: 'În Așteptare' },
    { value: 'blocat', label: 'Blocat' },
    { value: 'finalizat', label: 'Finalizat' },
  ]

  let searchInput = $state('')
  let debounceTimer

  function onSearch(e) {
    searchInput = e.target.value
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      projects.filters.search = searchInput
      loadProjects()
    }, 300)
  }

  function setStatus(s) {
    projects.filters.status = s
    loadProjects()
  }

  function openProject(id) {
    const p = projects.items.find(x => x.id === id)
    if (p) {
      try {
        const recents = JSON.parse(localStorage.getItem('recent_projects') || '[]')
        const fresh = [{ id: p.id, nume: p.nume, client: p.client, tip: p.tip },
          ...recents.filter(r => r.id !== p.id)].slice(0, 6)
        localStorage.setItem('recent_projects', JSON.stringify(fresh))
      } catch (_) {}
    }
    navigate(`/projects/${id}`)
  }

  onMount(() => { loadProjects() })
</script>

<div class="page">
  <div class="page-header">
    <div class="page-title-row">
      <FolderKanban size={22} />
      <h1>Proiecte</h1>
      <span class="count">{projects.items.length}</span>
    </div>
  </div>

  <div class="toolbar">
    <div class="search-box">
      <Search size={14} />
      <input type="text" placeholder="Cauta proiecte..." value={searchInput} oninput={onSearch} />
    </div>
    <div class="filters">
      {#each statusOptions as opt}
        <button class="chip" class:active={projects.filters.status === opt.value} onclick={() => setStatus(opt.value)}>{opt.label}</button>
      {/each}
    </div>
  </div>

  {#if projects.loading}
    <div class="list">
      {#each Array(6) as _}
        <div class="row-skeleton"><Skeleton width="60%" height="16px" /><Skeleton width="30%" height="14px" /></div>
      {/each}
    </div>
  {:else if projects.error}
    <p class="error-text">Eroare: {projects.error}</p>
  {:else if projects.items.length === 0}
    <EmptyState icon={FolderKanban} title="Niciun proiect" description="Nu exista proiecte cu filtrele selectate." />
  {:else}
    <div class="list">
      {#each projects.items as p (p.id)}
        <button class="project-row" onclick={() => openProject(p.id)}>
          <div class="project-main">
            <div class="project-name">
              {#if p.tip}<span class="project-tip" class:pif={p.tip === 'PIF'}>{p.tip}</span>{/if}
              {p.nume || '—'}
            </div>
            <div class="project-meta">
              <span>{p.client || '—'}</span>
              {#if p.echipament_principal}<span>· {p.echipament_principal}</span>{/if}
              {#if p.cod_proiect}<span>· {p.cod_proiect}</span>{/if}
            </div>
          </div>
          <div class="project-right">
            <Badge label={PROJECT_STATUS_LABELS[p.status] || p.status || '—'} color={STATUS_COLORS[p.status] || 'var(--text-dim)'} small />
            {#if p.deadline}<span class="project-deadline">{formatDate(p.deadline)}</span>{/if}
          </div>
          <ChevronRight size={14} class="chevron" />
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page { padding: var(--space-lg); }
  .page-header { margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-h1); font-weight: 700; }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .toolbar { display: flex; gap: var(--space-md); align-items: center; margin-bottom: var(--space-md); flex-wrap: wrap; }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-dim); flex: 1; max-width: 320px; }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; }
  .search-box input::placeholder { color: var(--text-dim); }
  .search-box:focus-within { border-color: var(--accent); }

  .filters { display: flex; gap: 4px; flex-wrap: wrap; }
  .chip { padding: 4px 12px; font-size: var(--font-tiny); font-weight: 500; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid transparent; cursor: pointer; transition: all var(--dur-fast) var(--ease); }
  .chip:hover { background: var(--bg-hover); color: var(--text); }
  .chip.active { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }

  .list { display: flex; flex-direction: column; }
  .project-row { display: flex; align-items: center; gap: var(--space-md); padding: var(--space-sm) var(--space-md); text-align: left; cursor: pointer; transition: background var(--dur-fast) var(--ease); border-radius: var(--radius-sm); }
  .project-row:hover { background: var(--bg-surface); }
  .project-row + .project-row { border-top: 1px solid var(--border); }
  .project-main { flex: 1; min-width: 0; }
  .project-name { font-size: var(--font-small); font-weight: 500; color: var(--text); display: flex; align-items: center; gap: var(--space-xs); }
  .project-tip { font-size: 10px; font-weight: 600; text-transform: uppercase; padding: 1px 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-secondary); }
  .project-tip.pif { background: var(--accent-subtle); color: var(--accent); }
  .project-meta { font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .project-right { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; flex-shrink: 0; }
  .project-deadline { font-size: var(--font-tiny); color: var(--text-dim); }
  :global(.chevron) { color: var(--text-dim); flex-shrink: 0; }
  .row-skeleton { display: flex; flex-direction: column; gap: 6px; padding: var(--space-sm) var(--space-md); }
  .error-text { color: var(--danger); padding: var(--space-md); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .toolbar { flex-direction: column; align-items: stretch; }
    .search-box { max-width: none; }
  }
</style>
