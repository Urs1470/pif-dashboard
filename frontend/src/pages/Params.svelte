<script>
  import { onMount } from 'svelte'
  import { Cpu, Search, ChevronLeft, ChevronRight } from '@lucide/svelte'
  import { params, loadParams, loadFamilies, faultCodes, loadFaultCodes, loadFaultFamilies } from '../stores/params.svelte.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import Modal from '../components/ui/Modal.svelte'

  let activeTab = $state('params')
  let searchInput = $state('')
  let debounceTimer
  let selectedParam = $state(null)
  let showDetail = $state(false)

  function onSearch(e) {
    searchInput = e.target.value
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      if (activeTab === 'params') { params.filters.search = searchInput; params.filters.page = 1; loadParams() }
      else { faultCodes.filters.search = searchInput; faultCodes.filters.page = 1; loadFaultCodes() }
    }, 300)
  }

  function selectFamily(f) {
    if (activeTab === 'params') { params.filters.familie = params.filters.familie === f ? '' : f; params.filters.page = 1; loadParams() }
    else { faultCodes.filters.familie = faultCodes.filters.familie === f ? '' : f; faultCodes.filters.page = 1; loadFaultCodes() }
  }

  function goPage(delta) {
    if (activeTab === 'params') { params.filters.page = Math.max(1, Math.min(params.totalPages, params.filters.page + delta)); loadParams() }
    else { faultCodes.filters.page = Math.max(1, Math.min(faultCodes.totalPages, faultCodes.filters.page + delta)); loadFaultCodes() }
  }

  function switchTab(t) { activeTab = t; searchInput = ''; if (t === 'params') loadParams(); else loadFaultCodes() }

  onMount(() => { loadFamilies(); loadParams(); loadFaultFamilies() })

  const curFamilies = $derived(activeTab === 'params' ? params.families : faultCodes.families)
  const curFilter = $derived(activeTab === 'params' ? params.filters.familie : faultCodes.filters.familie)
  const curItems = $derived(activeTab === 'params' ? params.items : faultCodes.items)
  const curLoading = $derived(activeTab === 'params' ? params.loading : faultCodes.loading)
  const curPage = $derived(activeTab === 'params' ? params.filters.page : faultCodes.filters.page)
  const curTotalPages = $derived(activeTab === 'params' ? params.totalPages : faultCodes.totalPages)
  const curTotal = $derived(activeTab === 'params' ? params.total : faultCodes.total)
</script>

<div class="page">
  <div class="page-header">
    <Cpu size={22} />
    <h1>Parametri</h1>
    <span class="count">{curTotal}</span>
  </div>

  <div class="tabs">
    <button class="tab" class:active={activeTab === 'params'} onclick={() => switchTab('params')}>Parametri</button>
    <button class="tab" class:active={activeTab === 'faults'} onclick={() => switchTab('faults')}>Fault Codes</button>
  </div>

  <div class="toolbar">
    <div class="search-box">
      <Search size={14} />
      <input type="text" placeholder="Cauta..." value={searchInput} oninput={onSearch} />
    </div>
  </div>

  {#if curFamilies.length > 0}
    <div class="families">
      {#each curFamilies as f}
        <button class="chip" class:active={curFilter === f.familie} onclick={() => selectFamily(f.familie)}>
          {f.familie} <span class="chip-count">{f.count}</span>
        </button>
      {/each}
    </div>
  {/if}

  {#if curLoading}
    {#each Array(8) as _}<div class="row-skel"><Skeleton width="40%" height="14px" /></div>{/each}
  {:else if curItems.length === 0}
    <EmptyState icon={Cpu} title="Niciun rezultat" description="Incearca alte filtre." />
  {:else}
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Nume</th><th>Familie</th>
          {#if activeTab === 'params'}<th>Categorie</th><th>Valoare</th>{:else}<th>Cod</th><th>Descriere</th>{/if}
        </tr></thead>
        <tbody>
          {#each curItems as item}
            <tr class="clickable" onclick={() => { selectedParam = item; showDetail = true }}>
              <td class="name-cell">{item.nume || item.name || '—'}</td>
              <td><span class="fam-badge">{item.familie || '—'}</span></td>
              {#if activeTab === 'params'}
                <td class="dim">{item.categorie || '—'}</td>
                <td class="dim">{item.valoare_implicita || item.default_value || '—'}</td>
              {:else}
                <td class="mono">{item.cod || item.code || '—'}</td>
                <td class="dim">{item.descriere || item.description || '—'}</td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if curTotalPages > 1}
      <div class="pagination">
        <button class="pg-btn" disabled={curPage <= 1} onclick={() => goPage(-1)}><ChevronLeft size={14} /></button>
        <span class="pg-info">{curPage} / {curTotalPages}</span>
        <button class="pg-btn" disabled={curPage >= curTotalPages} onclick={() => goPage(1)}><ChevronRight size={14} /></button>
      </div>
    {/if}
  {/if}
</div>

<Modal bind:open={showDetail} title={selectedParam?.nume || selectedParam?.name || 'Detalii'} size="md">
  {#if selectedParam}
    <div class="detail">
      {#each [['Nume', selectedParam.nume || selectedParam.name], ['Familie', selectedParam.familie], ['Categorie', selectedParam.categorie], ['Valoare implicita', selectedParam.valoare_implicita || selectedParam.default_value], ['Unitate', selectedParam.unitate]] as [label, val]}
        {#if val}<div class="drow"><span class="dlabel">{label}</span><span>{val}</span></div>{/if}
      {/each}
      {#if selectedParam.explicatie}<div class="dfull"><span class="dlabel">Explicatie</span><p>{selectedParam.explicatie}</p></div>{/if}
    </div>
  {/if}
</Modal>

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); margin-bottom: var(--space-md); }
  .page-header h1 { font-size: var(--font-h1); font-weight: 700; }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .tabs { display: flex; border-bottom: 1px solid var(--border); margin-bottom: var(--space-md); }
  .tab { padding: var(--space-sm) var(--space-md); font-size: var(--font-small); font-weight: 500; color: var(--text-secondary); border-bottom: 2px solid transparent; cursor: pointer; }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }

  .toolbar { margin-bottom: var(--space-sm); }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-dim); max-width: 400px; }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; }
  .search-box:focus-within { border-color: var(--accent); }

  .families { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: var(--space-md); }
  .chip { display: flex; align-items: center; gap: 4px; padding: 3px 10px; font-size: var(--font-tiny); font-weight: 500; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid transparent; cursor: pointer; }
  .chip:hover { background: var(--bg-hover); }
  .chip.active { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }
  .chip-count { font-size: 10px; color: var(--text-dim); }

  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; }
  thead th { text-align: left; font-size: var(--font-tiny); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-dim); padding: var(--space-sm); border-bottom: 1px solid var(--border); }
  tbody tr.clickable { cursor: pointer; }
  tbody tr:hover { background: var(--bg-surface); }
  td { padding: var(--space-sm); font-size: var(--font-small); color: var(--text); border-bottom: 1px solid var(--border); }
  .name-cell { font-weight: 500; }
  .dim { color: var(--text-secondary); }
  .mono { font-family: var(--font-mono); font-size: var(--font-tiny); }
  .fam-badge { font-size: 10px; font-weight: 600; text-transform: uppercase; padding: 1px 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-secondary); }

  .pagination { display: flex; align-items: center; justify-content: center; gap: var(--space-sm); padding: var(--space-md) 0; }
  .pg-btn { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid var(--border); cursor: pointer; }
  .pg-btn:hover:not(:disabled) { background: var(--bg-hover); }
  .pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .pg-info { font-size: var(--font-tiny); color: var(--text-dim); }

  .row-skel { padding: var(--space-sm); }

  .detail { display: flex; flex-direction: column; gap: var(--space-sm); }
  .drow { display: flex; justify-content: space-between; font-size: var(--font-small); }
  .dlabel { color: var(--text-dim); font-weight: 500; }
  .dfull { display: flex; flex-direction: column; gap: 4px; }
  .dfull p { font-size: var(--font-small); color: var(--text-secondary); line-height: 1.5; }

  @media (max-width: 768px) { .page { padding: var(--space-md); } .search-box { max-width: none; } }
</style>
