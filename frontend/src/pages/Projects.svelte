<script>
  import { onMount } from 'svelte'
  import { slide } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { FolderKanban, Search, Plus, ChevronDown, ChevronUp, Archive, CheckSquare, Square } from '@lucide/svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import { projects, loadProjects, updateProject, deleteProject } from '../stores/projects.svelte.js'
  import { PROJECT_STATUS_LABELS, STATUS_COLORS, formatDate } from '../lib/formatters.js'
  import { navigate } from '../lib/router.svelte.js'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../lib/motion.svelte.js'
  import { toast } from '../stores/ui.svelte.js'
  import Badge from '../components/ui/Badge.svelte'
  import Button from '../components/ui/Button.svelte'
  import Select from '../components/ui/Select.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  import ProjectFormModal from '../components/projects/ProjectFormModal.svelte'

  const statusOptions = [
    { value: '', label: 'Toate' },
    { value: 'in_lucru', label: 'În Lucru' },
    { value: 'in_asteptare', label: 'În Așteptare' },
    { value: 'blocat', label: 'Blocat' },
    { value: 'finalizat', label: 'Finalizat' },
  ]

  const sortOptions = [
    { value: 'nume', label: 'Nume' },
    { value: 'client', label: 'Client' },
    { value: 'tip', label: 'Tip' },
    { value: 'status', label: 'Status' },
    { value: 'deadline', label: 'Deadline' },
  ]

  const batchStatusOptions = [
    { value: 'in_lucru', label: 'In Lucru' },
    { value: 'in_asteptare', label: 'In Asteptare' },
    { value: 'blocat', label: 'Blocat' },
    { value: 'finalizat', label: 'Finalizat' },
  ]

  function daysUntil(deadline) {
    if (!deadline) return null
    const d = new Date(deadline)
    if (isNaN(d)) return null
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    d.setHours(0, 0, 0, 0)
    return Math.round((d - today) / 86400000)
  }

  function deadlineText(deadline) {
    const days = daysUntil(deadline)
    if (days === null) return formatDate(deadline)
    if (days < 0) return `${formatDate(deadline)} — depasit`
    if (days === 0) return `${formatDate(deadline)} — azi`
    return `${formatDate(deadline)} — ${days} ${days === 1 ? 'zi' : 'zile'}`
  }

  const STATUS_CYCLE = ['in_lucru', 'in_asteptare', 'blocat', 'finalizat']

  async function cycleProjectStatus(e, p) {
    e.stopPropagation()
    const cur = p.status || 'in_lucru'
    const next = STATUS_CYCLE[(STATUS_CYCLE.indexOf(cur) + 1) % STATUS_CYCLE.length]
    try {
      await updateProject(p.id, { status: next })
      toast(`Status: ${PROJECT_STATUS_LABELS[next] || next}`, 'success')
    } catch (err) { toast(`Eroare: ${err.message}`, 'error') }
  }

  let searchInput = $state('')
  let debounceTimer
  let showNewModal = $state(false)
  let showArchive = $state(false)
  let sort = $state({ key: 'nume', dir: 1 })

  let batchMode = $state(false)
  let selected = $state(new Set())
  let batchStatus = $state('')
  let showBatchDelete = $state(false)
  let batchBusy = $state(false)

  function toggleBatch() {
    batchMode = !batchMode
    if (!batchMode) selected = new Set()
  }

  function toggleSelect(id) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id); else next.add(id)
    selected = next
  }

  function toggleSelectAll() {
    if (selected.size === activeItems.length) {
      selected = new Set()
    } else {
      selected = new Set(activeItems.map(p => p.id))
    }
  }

  async function batchUpdateStatus() {
    if (!batchStatus || selected.size === 0) return
    batchBusy = true
    try {
      await Promise.all([...selected].map(id => updateProject(id, { status: batchStatus })))
      toast(`${selected.size} proiecte actualizate`, 'success')
      selected = new Set()
      batchStatus = ''
      await loadProjects()
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { batchBusy = false }
  }

  async function batchDeleteSelected() {
    if (selected.size === 0) return
    batchBusy = true
    try {
      for (const id of selected) await deleteProject(id)
      toast(`${selected.size} proiecte sterse`, 'success')
      selected = new Set()
      showBatchDelete = false
      await loadProjects()
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { batchBusy = false }
  }

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

  function setSortKey(e) {
    if (sort.key !== e.target.value) sort = { key: e.target.value, dir: 1 }
  }

  function cardKeydown(e, p) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      if (batchMode) toggleSelect(p.id)
      else openProject(p)
    }
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
    <div class="header-btns">
      <Button size="sm" variant={batchMode ? 'secondary' : 'ghost'} onclick={toggleBatch}><CheckSquare size={14} /> Selecteaza</Button>
      <Button size="sm" onclick={() => showNewModal = true}><Plus size={14} /> Proiect Nou</Button>
    </div>
  </div>

  {#if batchMode && selected.size > 0}
    <div class="batch-bar" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
      <span class="batch-count">{selected.size} selectate</span>
      <Select size="sm" bind:value={batchStatus} placeholder="Schimba status..." options={batchStatusOptions} aria-label="Schimba status" />
      <Button size="sm" disabled={!batchStatus || batchBusy} onclick={batchUpdateStatus}>Aplica</Button>
      <Button size="sm" variant="danger" disabled={batchBusy} onclick={() => showBatchDelete = true}><SolidIcon name="trash" size={12} /> Sterge</Button>
      <Button size="sm" variant="ghost" onclick={() => { selected = new Set() }}>Deselecteaza</Button>
    </div>
  {/if}

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
    <div class="sort-box">
      <span class="sort-label">Sortare</span>
      <Select size="sm" value={sort.key} options={sortOptions} onchange={setSortKey} aria-label="Sortare" />
      <button class="sort-dir" onclick={() => sort.dir = -sort.dir} title="Inverseaza ordinea">
        {#if sort.dir === 1}<ChevronUp size={14} />{:else}<ChevronDown size={14} />{/if}
      </button>
    </div>
    {#if batchMode}
      <button class="select-all" onclick={toggleSelectAll}>
        {#if selected.size === activeItems.length && activeItems.length > 0}<CheckSquare size={14} />{:else}<Square size={14} />{/if}
        Selecteaza toate
      </button>
    {/if}
  </div>

  {#if projects.loading}
    <div class="cards-grid">
      {#each Array(6) as _}
        <div class="pcard skeleton-card"><Skeleton width="40%" height="14px" /><Skeleton width="70%" height="18px" /><Skeleton width="50%" height="12px" /></div>
      {/each}
    </div>
  {:else if projects.error}
    <ErrorState message={projects.error} onretry={() => loadProjects()} />
  {:else if activeItems.length === 0 && archivedItems.length === 0}
    <EmptyState icon={FolderKanban} title="Niciun proiect" description="Nu exista proiecte cu filtrele selectate." />
  {:else}
    <div class="cards-grid">
      {#each activeItems as p (p.id)}
        <div class="pcard cell-in" class:batch-selected={batchMode && selected.has(p.id)} role="button" tabindex="0" animate:flip={{ duration: motionDuration(DUR_BASE) }} onclick={(e) => { if (batchMode) { e.stopPropagation(); toggleSelect(p.id) } else openProject(p) }} onkeydown={(e) => cardKeydown(e, p)}>
          <div class="card-top">
            {#if batchMode}
              <button class="batch-check card-check" onclick={(e) => { e.stopPropagation(); toggleSelect(p.id) }}>
                {#if selected.has(p.id)}<CheckSquare size={16} />{:else}<Square size={16} />{/if}
              </button>
            {/if}
            {#if p.tip}<span class="tip-chip" class:pif={p.tip === 'PIF'} class:service={p.tip === 'Service'}>{p.tip === 'PIF' ? '◳' : '⟳'}</span><span class="tip-label">{p.tip}</span>{:else}<span class="tip-label">—</span>{/if}
            <button class="status-pill" style="color: {STATUS_COLORS[p.status] || 'var(--text-dim)'}; border-color: {STATUS_COLORS[p.status] || 'var(--text-dim)'}" onclick={(e) => cycleProjectStatus(e, p)} title="Click pentru a schimba statusul">{PROJECT_STATUS_LABELS[p.status] || p.status || '—'}</button>
          </div>
          <div class="card-name">{p.nume || '—'}</div>
          <div class="card-client">{p.client || '—'}</div>
          <div class="card-foot">
            {#if p.deadline}
              <span class="deadline" class:urgent={daysUntil(p.deadline) !== null && daysUntil(p.deadline) <= 2}>deadline {deadlineText(p.deadline)}</span>
            {:else}
              <span class="deadline">fara deadline</span>
            {/if}
          </div>
        </div>
      {/each}
      {#if !batchMode}
        <button class="pcard new-card cell-in" onclick={() => showNewModal = true}>
          <span class="new-plus">+</span>
          <span class="new-label">Proiect nou</span>
        </button>
      {/if}
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
          <div class="arch-list" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
            {#each archivedItems as p (p.id)}
              <button class="arch-row archived" animate:flip={{ duration: motionDuration(DUR_BASE) }} onclick={() => openProject(p)}>
                <span class="arch-name">{p.nume || '—'}</span>
                <span class="dim arch-client">{p.client || '—'}</span>
                {#if p.tip}<span class="ptip" class:pif={p.tip === 'PIF'} class:service={p.tip === 'Service'}>{p.tip}</span>{/if}
                <span class="arch-tail">
                  <Badge label="Finalizat" color="var(--success)" small />
                  <span class="dim arch-deadline">{p.deadline ? formatDate(p.deadline) : '—'}</span>
                </span>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<ProjectFormModal bind:open={showNewModal} onsaved={() => loadProjects()} />
<ConfirmDialog bind:open={showBatchDelete} title="Sterge proiecte" message={`Stergi ${selected.size} proiecte selectate? Aceasta actiune este ireversibila.`} confirmLabel="Sterge" onconfirm={batchDeleteSelected} />

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-h1); font-weight: var(--fw-bold); }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .toolbar { display: flex; gap: var(--space-md); align-items: center; margin-bottom: var(--space-md); flex-wrap: wrap; }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 12px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-full); color: var(--text-dim); flex: 1; max-width: 320px; }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; box-shadow: none; }
  .search-box input:focus { box-shadow: none; border: none; }
  .search-box input::placeholder { color: var(--text-dim); }
  .search-box:focus-within { border-color: var(--accent); box-shadow: var(--focus-ring); }

  .filters { display: flex; gap: 4px; flex-wrap: wrap; }
  .chip { padding: 4px 12px; font-size: var(--font-tiny); font-weight: var(--fw-medium); border-radius: var(--radius-full); background: var(--bg-input); color: var(--text-secondary); border: 1px solid transparent; cursor: pointer; transition: all var(--dur-fast) var(--ease); min-height: 30px; }
  .chip:hover { background: var(--bg-hover); color: var(--text); }
  .chip.active { background: var(--accent-subtle); color: var(--accent-on-subtle); border-color: var(--accent); }
  .chip:active { transform: scale(0.97); }

  .sort-box { display: flex; align-items: center; gap: var(--space-xs); }
  .sort-label { font-size: var(--font-tiny); color: var(--text-dim); }
  .sort-dir { display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--bg-input); color: var(--text-dim); cursor: pointer; transition: all var(--dur-fast) var(--ease); }
  .sort-dir:hover { color: var(--text); border-color: var(--border-strong); }
  .select-all { display: inline-flex; align-items: center; gap: 6px; font-size: var(--font-tiny); font-weight: var(--fw-medium); color: var(--text-secondary); cursor: pointer; padding: 4px 10px; border-radius: var(--radius-sm); background: var(--bg-input); border: 1px solid var(--border); }
  .select-all:hover { color: var(--text); border-color: var(--border-strong); }

  .cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 14px; }
  .pcard { position: relative; display: flex; flex-direction: column; min-height: 132px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 18px 20px; cursor: pointer; text-align: left; transition: transform var(--dur-base) var(--ease), border-color var(--dur-base) var(--ease), box-shadow var(--dur-base) var(--ease); }
  .pcard:hover { transform: translateY(-4px); border-color: var(--border-strong); box-shadow: var(--shadow-lg); }
  .pcard:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .pcard.batch-selected { background: var(--accent-subtle); border-color: var(--accent); }
  .pcard.new-card { border-style: dashed; align-items: center; justify-content: center; gap: 6px; color: var(--text-faint); background: transparent; }
  .pcard.new-card:hover { color: var(--accent); border-color: var(--accent); box-shadow: none; }
  .new-plus { font-size: 1.5rem; line-height: 1; }
  .new-label { font-size: var(--font-small); font-weight: var(--fw-semibold); }
  .card-top { display: flex; align-items: center; gap: var(--space-xs); margin-bottom: 10px; }
  .card-top { display: flex; align-items: center; }
  .card-top .status-pill { margin-left: auto; }
  .card-check { width: auto; height: auto; }
  .card-name { font-family: var(--font-heading); font-size: 1.05rem; font-weight: var(--fw-bold); letter-spacing: -0.02em; color: var(--text); line-height: 1.25; overflow-wrap: anywhere; }
  .card-client { font-size: var(--font-tiny); color: var(--text-faint); margin-top: 2px; }
  .card-foot { margin-top: auto; padding-top: 14px; display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text-dim); }
  .deadline.urgent { color: var(--danger); font-weight: var(--fw-semibold); }
  .skeleton-card { gap: 8px; cursor: default; }

  .dim { color: var(--text-secondary); }
  .ptip { display: inline-block; font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; padding: 1px 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-secondary); }
  .ptip.pif { background: var(--accent-subtle); color: var(--accent); }
  .ptip.service { background: var(--service-subtle); color: var(--service-accent); }
  .tip-chip { width: 22px; height: 22px; border-radius: 7px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.72rem; background: var(--bg-elevated); color: var(--text-secondary); flex-shrink: 0; }
  .tip-chip.pif { background: var(--accent-subtle); color: var(--accent); }
  .tip-chip.service { background: var(--success-subtle); color: var(--success); }
  .tip-label { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-faint); margin-left: 8px; }

  .archive { margin-top: var(--space-lg); }
  .archive-toggle { display: flex; align-items: center; gap: var(--space-sm); font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary); cursor: pointer; padding: var(--space-sm) 0; margin-bottom: var(--space-sm); min-height: 44px; }
  .archive-toggle:hover { color: var(--text); }
  .archived { opacity: 0.7; }
  .arch-list { display: flex; flex-direction: column; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
  .arch-row { display: flex; align-items: center; gap: var(--space-sm); width: 100%; padding: 10px 16px; font-size: var(--font-small); color: var(--text); text-align: left; cursor: pointer; background: transparent; border: none; border-bottom: 1px solid var(--border); transition: background var(--dur-fast) var(--ease); }
  .arch-row:last-child { border-bottom: none; }
  .arch-row:hover { background: var(--bg-hover); opacity: 1; }
  .arch-name { font-weight: var(--fw-medium); }
  .arch-client { font-size: var(--font-tiny); }
  .arch-tail { margin-left: auto; display: inline-flex; align-items: center; gap: var(--space-sm); }
  .arch-deadline { font-size: var(--font-tiny); font-family: var(--font-mono); }

  .header-btns { display: flex; gap: var(--space-xs); }
  .batch-bar { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) var(--space-md); background: var(--accent-subtle); border: 1px solid color-mix(in srgb, var(--accent) 25%, transparent); border-radius: var(--radius-md); margin-bottom: var(--space-md); flex-wrap: wrap; }
  .batch-count { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--accent); }
  .batch-check { display: flex; align-items: center; justify-content: center; color: var(--text-dim); cursor: pointer; background: transparent; border: none; padding: 0; }
  .batch-check:hover { color: var(--accent); }
  .status-pill { font-size: var(--font-tiny); font-weight: var(--fw-semibold); padding: 2px 10px; min-height: 22px; border-radius: var(--radius-full); background: transparent; border: 1px solid; cursor: pointer; white-space: nowrap; transition: transform var(--dur-fast) var(--ease), opacity var(--dur-fast) var(--ease); }
  .status-pill:hover { opacity: .7; transform: scale(1.05); }
  .status-pill:active { transform: scale(0.92); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .toolbar { flex-direction: column; align-items: stretch; }
    .search-box { max-width: none; }
    .sort-box { justify-content: flex-start; }
    .batch-bar { flex-direction: column; align-items: stretch; }
  }

  @media (max-width: 560px) {
    .cards-grid { grid-template-columns: 1fr; }
  }
</style>
