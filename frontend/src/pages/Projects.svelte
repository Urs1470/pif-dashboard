<script>
  import { onMount } from 'svelte'
  import { FolderKanban, Search, Plus, ChevronDown, ChevronUp, Archive } from '@lucide/svelte'
  import { projects, loadProjects } from '../stores/projects.svelte.js'
  import { PROJECT_STATUS_LABELS, STATUS_COLORS, formatDate } from '../lib/formatters.js'
  import { navigate } from '../lib/router.svelte.js'
  import Badge from '../components/ui/Badge.svelte'
  import Button from '../components/ui/Button.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ProjectFormModal from '../components/projects/ProjectFormModal.svelte'

  const statusOptions = [
    { value: '', label: 'Toate' },
    { value: 'in_lucru', label: 'În Lucru' },
    { value: 'in_asteptare', label: 'În Așteptare' },
    { value: 'blocat', label: 'Blocat' },
    { value: 'finalizat', label: 'Finalizat' },
  ]

  const columns = [
    { key: 'nume', label: 'Nume' },
    { key: 'client', label: 'Client' },
    { key: 'producator', label: 'Producator' },
    { key: 'status', label: 'Status' },
    { key: 'deadline', label: 'Deadline' },
  ]

  let searchInput = $state('')
  let debounceTimer
  let showNewModal = $state(false)
  let showArchive = $state(false)
  let sort = $state({ key: 'nume', dir: 1 })

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

  function toggleSort(key) {
    if (sort.key === key) sort.dir = -sort.dir
    else sort = { key, dir: 1 }
  }

  function sortItems(items) {
    const { key, dir } = sort
    return [...items].sort((a, b) => {
      const av = (a[key] ?? '').toString().toLowerCase()
      const bv = (b[key] ?? '').toString().toLowerCase()
      if (av < bv) return -dir
      if (av > bv) return dir
      return 0
    })
  }

  function openProject(p) {
    try {
      const recents = JSON.parse(localStorage.getItem('recent_projects') || '[]')
      const fresh = [{ id: p.id, nume: p.nume, client: p.client, tip: p.tip },
        ...recents.filter(r => r.id !== p.id)].slice(0, 6)
      localStorage.setItem('recent_projects', JSON.stringify(fresh))
    } catch (_) {}
    navigate(`/projects/${p.id}`)
  }

  onMount(() => { loadProjects() })

  const activeItems = $derived(
    projects.filters.status
      ? sortItems(projects.items)
      : sortItems(projects.items.filter(p => p.status !== 'finalizat'))
  )
  const archivedItems = $derived(
    projects.filters.status ? [] : sortItems(projects.items.filter(p => p.status === 'finalizat'))
  )
</script>

<div class="page">
  <div class="page-header">
    <div class="page-title-row">
      <FolderKanban size={22} />
      <h1>Proiecte</h1>
      <span class="count">{projects.items.length}</span>
    </div>
    <Button size="sm" onclick={() => showNewModal = true}><Plus size={14} /> Proiect Nou</Button>
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
  {:else if activeItems.length === 0 && archivedItems.length === 0}
    <EmptyState icon={FolderKanban} title="Niciun proiect" description="Nu exista proiecte cu filtrele selectate." />
  {:else}
    <div class="data-table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            {#each columns as col}
              <th onclick={() => toggleSort(col.key)} class="sortable">
                <span class="th-inner">
                  {col.label}
                  {#if sort.key === col.key}
                    {#if sort.dir === 1}<ChevronUp size={12} />{:else}<ChevronDown size={12} />{/if}
                  {/if}
                </span>
              </th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each activeItems as p (p.id)}
            <tr class="clickable-row" onclick={() => openProject(p)}>
              <td class="name-cell">
                {#if p.tip}<span class="ptip" class:pif={p.tip === 'PIF'} class:service={p.tip === 'Service'}>{p.tip}</span>{/if}
                {p.nume || '—'}
              </td>
              <td class="dim">{p.client || '—'}</td>
              <td class="dim">{p.producator || '—'}</td>
              <td><Badge label={PROJECT_STATUS_LABELS[p.status] || p.status || '—'} color={STATUS_COLORS[p.status] || 'var(--text-dim)'} small /></td>
              <td class="dim">{p.deadline ? formatDate(p.deadline) : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if archivedItems.length > 0}
      <div class="archive">
        <button class="archive-toggle" onclick={() => showArchive = !showArchive}>
          <Archive size={14} />
          Arhiva (Finalizate)
          <span class="count">{archivedItems.length}</span>
          {#if showArchive}<ChevronUp size={14} />{:else}<ChevronDown size={14} />{/if}
        </button>
        {#if showArchive}
          <div class="data-table-wrap">
            <table class="data-table">
              <tbody>
                {#each archivedItems as p (p.id)}
                  <tr class="clickable-row archived" onclick={() => openProject(p)}>
                    <td class="name-cell">
                      {#if p.tip}<span class="ptip" class:pif={p.tip === 'PIF'} class:service={p.tip === 'Service'}>{p.tip}</span>{/if}
                      {p.nume || '—'}
                    </td>
                    <td class="dim">{p.client || '—'}</td>
                    <td class="dim">{p.producator || '—'}</td>
                    <td><Badge label="Finalizat" color="var(--success)" small /></td>
                    <td class="dim">{p.deadline ? formatDate(p.deadline) : '—'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<ProjectFormModal bind:open={showNewModal} onsaved={() => loadProjects()} />

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-h1); font-weight: 700; }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .toolbar { display: flex; gap: var(--space-md); align-items: center; margin-bottom: var(--space-md); flex-wrap: wrap; }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-dim); flex: 1; max-width: 320px; }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; box-shadow: none; }
  .search-box input:focus { box-shadow: none; border: none; }
  .search-box input::placeholder { color: var(--text-dim); }
  .search-box:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }

  .filters { display: flex; gap: 4px; flex-wrap: wrap; }
  .chip { padding: 4px 12px; font-size: var(--font-tiny); font-weight: 500; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid transparent; cursor: pointer; transition: all var(--dur-fast) var(--ease); min-height: 30px; }
  .chip:hover { background: var(--bg-hover); color: var(--text); }
  .chip.active { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }

  .sortable { cursor: pointer; user-select: none; }
  .sortable:hover { color: var(--text); }
  .th-inner { display: inline-flex; align-items: center; gap: 4px; }

  .name-cell { font-weight: 500; }
  .dim { color: var(--text-secondary); }
  .ptip { font-size: 10px; font-weight: 600; text-transform: uppercase; padding: 1px 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-secondary); margin-right: 6px; }
  .ptip.pif { background: var(--accent-subtle); color: var(--accent); }
  .ptip.service { background: var(--service-subtle); color: var(--service-accent); }

  .archive { margin-top: var(--space-lg); }
  .archive-toggle { display: flex; align-items: center; gap: var(--space-sm); font-size: var(--font-small); font-weight: 600; color: var(--text-secondary); cursor: pointer; padding: var(--space-sm) 0; margin-bottom: var(--space-sm); min-height: 44px; }
  .archive-toggle:hover { color: var(--text); }
  .archived { opacity: 0.7; }

  .row-skeleton { display: flex; flex-direction: column; gap: 6px; padding: var(--space-sm) var(--space-md); }
  .error-text { color: var(--danger); padding: var(--space-md); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .toolbar { flex-direction: column; align-items: stretch; }
    .search-box { max-width: none; }
  }
</style>
