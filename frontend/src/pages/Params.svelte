<script>
  import { onMount } from 'svelte'
  import { Cpu, Search, ChevronLeft, ChevronRight, ArrowLeft } from '@lucide/svelte'
  import { params, loadParams, loadFamilies, loadParamDetail, faultCodes, loadFaultCodes, loadFaultFamilies, loadFaultDetail, PRODUCATOR_FAMILII, familieLabel } from '../stores/params.svelte.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import ProducatorPicker from '../components/params/ProducatorPicker.svelte'

  let activeTab = $state('params')
  let producator = $state('')
  let searchInput = $state('')
  let debounceTimer
  let detail = $state(null)
  let showDetail = $state(false)
  let detailLoading = $state(false)

  function pickProducator(p) {
    producator = p
    searchInput = ''
    const firstFam = PRODUCATOR_FAMILII[p]?.[0] || ''
    if (activeTab === 'params') {
      params.filters.producator = p
      params.filters.familie = firstFam
      params.filters.search = ''
      params.filters.page = 1
      loadParams()
    } else {
      faultCodes.filters.producator = p
      faultCodes.filters.familie = firstFam
      faultCodes.filters.search = ''
      faultCodes.filters.page = 1
      loadFaultCodes()
    }
  }

  function backToPicker() {
    producator = ''
    searchInput = ''
    params.filters.producator = ''
    params.filters.familie = ''
    faultCodes.filters.producator = ''
    faultCodes.filters.familie = ''
  }

  function selectFamily(f) {
    if (activeTab === 'params') {
      params.filters.familie = f
      params.filters.page = 1
      loadParams()
    } else {
      faultCodes.filters.familie = f
      faultCodes.filters.page = 1
      loadFaultCodes()
    }
  }

  function onSearch(e) {
    searchInput = e.target.value
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      if (activeTab === 'params') { params.filters.search = searchInput; params.filters.page = 1; loadParams() }
      else { faultCodes.filters.search = searchInput; faultCodes.filters.page = 1; loadFaultCodes() }
    }, 300)
  }

  function goPage(delta) {
    if (activeTab === 'params') { params.filters.page = Math.max(1, Math.min(params.totalPages, params.filters.page + delta)); loadParams() }
    else { faultCodes.filters.page = Math.max(1, Math.min(faultCodes.totalPages, faultCodes.filters.page + delta)); loadFaultCodes() }
  }

  function switchTab(t) {
    activeTab = t
    searchInput = ''
    if (producator) {
      const firstFam = PRODUCATOR_FAMILII[producator]?.[0] || ''
      if (t === 'params') {
        if (!params.filters.familie) { params.filters.producator = producator; params.filters.familie = firstFam }
        loadParams()
      } else {
        if (!faultCodes.filters.familie) { faultCodes.filters.producator = producator; faultCodes.filters.familie = firstFam }
        loadFaultCodes()
      }
    }
  }

  async function openDetail(item) {
    showDetail = true
    detailLoading = true
    detail = item
    try {
      detail = activeTab === 'params' ? await loadParamDetail(item.id) : await loadFaultDetail(item.id)
    } catch (_) {} finally { detailLoading = false }
  }

  async function jumpToParam(id) {
    detailLoading = true
    try { detail = await loadParamDetail(id) } catch (_) {} finally { detailLoading = false }
  }

  onMount(() => { loadFamilies(); loadFaultFamilies() })

  const curFamilies = $derived(producator ? (PRODUCATOR_FAMILII[producator] || []) : [])
  const curFilter = $derived(activeTab === 'params' ? params.filters.familie : faultCodes.filters.familie)
  const curItems = $derived(activeTab === 'params' ? params.items : faultCodes.items)
  const curLoading = $derived(activeTab === 'params' ? params.loading : faultCodes.loading)
  const curPage = $derived(activeTab === 'params' ? params.filters.page : faultCodes.filters.page)
  const curTotalPages = $derived(activeTab === 'params' ? params.totalPages : faultCodes.totalPages)
  const curTotal = $derived(activeTab === 'params' ? params.total : faultCodes.total)
  const famCount = $derived((fam) => params.families.find(f => f.familie === fam)?.count || 0)
</script>

<div class="page">
  <div class="page-header">
    <Cpu size={22} />
    <h1>Parametri</h1>
    {#if producator}<span class="count">{curTotal}</span>{/if}
  </div>

  <div class="tabs">
    <button class="tab" class:active={activeTab === 'params'} onclick={() => switchTab('params')}>Parametri</button>
    <button class="tab" class:active={activeTab === 'faults'} onclick={() => switchTab('faults')}>Fault Codes</button>
  </div>

  {#if !producator}
    <ProducatorPicker families={activeTab === 'params' ? params.families : faultCodes.families} onpick={pickProducator} />
  {:else}
    <button class="back" onclick={backToPicker}><ArrowLeft size={14} /> Producatori</button>

    <div class="prod-head">
      <span class="prod-name">{producator}</span>
      <div class="families">
        {#each curFamilies as f}
          <button class="chip" class:active={curFilter === f} onclick={() => selectFamily(f)}>{familieLabel(f)}</button>
        {/each}
      </div>
    </div>

    <div class="toolbar">
      <div class="search-box">
        <Search size={14} />
        <input type="text" placeholder="Cauta in {familieLabel(curFilter)}..." value={searchInput} oninput={onSearch} />
      </div>
    </div>

    {#if curLoading}
      {#each Array(8) as _}<div class="row-skel"><Skeleton width="40%" height="14px" /></div>{/each}
    {:else if curItems.length === 0}
      <EmptyState icon={Cpu} title="Niciun rezultat" description="Incearca alta familie sau alt termen." />
    {:else if activeTab === 'params'}
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>Param</th><th>Descriere</th><th>Acces</th><th>Tip</th><th>Default</th><th>Min</th><th>Max</th><th>Unitate</th>
          </tr></thead>
          <tbody>
            {#each curItems as item (item.id)}
              <tr class="clickable-row" onclick={() => openDetail(item)}>
                <td class="mono accent">{item.parametru || '—'}</td>
                <td class="desc-cell">{item.descriere_scurta || item.descriere || '—'}</td>
                <td class="dim">{item.acces || '—'}</td>
                <td class="dim">{item.tip_date || '—'}</td>
                <td class="mono">{item.valoare_default_str ?? item.valoare_default ?? '—'}</td>
                <td class="mono dim">{item.min ?? '—'}</td>
                <td class="mono dim">{item.max ?? '—'}</td>
                <td class="dim">{item.unitate || '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else}
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>Cod</th><th>Cod secundar</th><th>Tip</th><th>Nume</th><th>Pagina</th>
          </tr></thead>
          <tbody>
            {#each curItems as item (item.id)}
              <tr class="clickable-row" onclick={() => openDetail(item)}>
                <td class="mono accent">{item.cod || '—'}</td>
                <td class="mono dim">{item.cod_secundar || '—'}</td>
                <td class="dim">{item.tip || '—'}</td>
                <td>{item.nume || '—'}</td>
                <td class="dim">{item.pagina || '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    {#if curTotalPages > 1}
      <div class="pagination">
        <button class="pg-btn" disabled={curPage <= 1} onclick={() => goPage(-1)}><ChevronLeft size={14} /></button>
        <span class="pg-info">{curPage} / {curTotalPages}</span>
        <button class="pg-btn" disabled={curPage >= curTotalPages} onclick={() => goPage(1)}><ChevronRight size={14} /></button>
      </div>
    {/if}
  {/if}
</div>

<Modal bind:open={showDetail} title={detail?.parametru || detail?.cod || 'Detalii'} size="md">
  {#if detailLoading}
    <Skeleton width="100%" height="120px" />
  {:else if detail}
    <div class="detail">
      {#if activeTab === 'params'}
        <div class="dmeta">
          {#each [['Familie', familieLabel(detail.familie)], ['Acces', detail.acces], ['Tip date', detail.tip_date], ['Default', detail.valoare_default_str ?? detail.valoare_default], ['Min', detail.min], ['Max', detail.max], ['Unitate', detail.unitate], ['Pagina manual', detail.pagina]] as [label, val]}
            {#if val != null && val !== ''}<div class="drow"><span class="dlabel">{label}</span><span class="dval">{val}</span></div>{/if}
          {/each}
        </div>
        {#if detail.descriere_scurta}<div class="dsection"><h4 class="dsec-title">Descriere</h4><p>{detail.descriere_scurta}</p></div>{/if}
        {#if detail.descriere && detail.descriere !== detail.descriere_scurta}<div class="dsection"><h4 class="dsec-title">Detalii</h4><p>{detail.descriere}</p></div>{/if}
        {#if detail.explicatie}<div class="dsection accent"><h4 class="dsec-title">Explicatie</h4><p>{detail.explicatie}</p></div>{/if}
        {#if detail.influenteaza}
          <div class="dsection">
            <h4 class="dsec-title">Influenteaza</h4>
            {#if detail.influenteaza_tokens?.some(t => t.id)}
              <div class="dlinks">
                {#each detail.influenteaza_tokens as t}
                  {#if t.id}
                    <button class="dlink" onclick={() => jumpToParam(t.id)}>{t.text}</button>
                  {:else}
                    <span class="dtok">{t.text}</span>
                  {/if}
                {/each}
              </div>
            {:else}
              <p>{detail.influenteaza}</p>
            {/if}
          </div>
        {/if}
        {#if detail.influentat_de?.length > 0}
          <div class="dsection">
            <h4 class="dsec-title">Influentat de</h4>
            <div class="dlinks">
              {#each detail.influentat_de as inf}
                <button class="dlink" onclick={() => jumpToParam(inf.id)}>{inf.parametru}</button>
              {/each}
            </div>
          </div>
        {/if}
      {:else}
        <div class="dmeta">
          {#each [['Familie', familieLabel(detail.familie)], ['Cod', detail.cod], ['Cod secundar', detail.cod_secundar], ['Tip', detail.tip], ['Pagina manual', detail.pagina]] as [label, val]}
            {#if val != null && val !== ''}<div class="drow"><span class="dlabel">{label}</span><span class="dval">{val}</span></div>{/if}
          {/each}
        </div>
        {#if detail.nume}<div class="dsection"><h4 class="dsec-title">Nume</h4><p>{detail.nume}</p></div>{/if}
        {#if detail.cauza}<div class="dsection"><h4 class="dsec-title">Cauza</h4><p>{detail.cauza}</p></div>{/if}
        {#if detail.solutie}<div class="dsection accent"><h4 class="dsec-title">Solutie</h4><p>{detail.solutie}</p></div>{/if}
        {#if detail.extra && Object.keys(detail.extra).length > 0}
          {#each Object.entries(detail.extra) as [k, v]}
            <div class="dsection"><h4 class="dsec-title">{k}</h4><p>{v}</p></div>
          {/each}
        {/if}
      {/if}
    </div>
  {/if}
</Modal>

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); margin-bottom: var(--space-md); }
  .page-header h1 { font-size: var(--font-h1); font-weight: 700; }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .tabs { display: flex; border-bottom: 1px solid var(--border); margin-bottom: var(--space-md); }
  .tab { padding: var(--space-sm) var(--space-md); font-size: var(--font-small); font-weight: 500; color: var(--text-secondary); border-bottom: 2px solid transparent; cursor: pointer; min-height: 44px; }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }

  .back { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-small); color: var(--text-dim); margin-bottom: var(--space-sm); cursor: pointer; min-height: 36px; }
  .back:hover { color: var(--accent); }

  .prod-head { display: flex; align-items: center; gap: var(--space-md); margin-bottom: var(--space-sm); flex-wrap: wrap; }
  .prod-name { font-size: var(--font-h3); font-weight: 700; color: var(--text); }

  .toolbar { margin-bottom: var(--space-sm); }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-dim); max-width: 400px; }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; box-shadow: none; }
  .search-box input:focus { box-shadow: none; }
  .search-box:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }

  .families { display: flex; gap: 4px; flex-wrap: wrap; }
  .chip { display: flex; align-items: center; gap: 4px; padding: 4px 12px; font-size: var(--font-tiny); font-weight: 500; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid transparent; cursor: pointer; min-height: 30px; }
  .chip:hover { background: var(--bg-hover); }
  .chip.active { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }

  .mono { font-family: var(--font-mono); font-size: 12px; }
  .accent { color: var(--accent); font-weight: 500; }
  .dim { color: var(--text-secondary); }
  .desc-cell { max-width: 380px; }

  .pagination { display: flex; align-items: center; justify-content: center; gap: var(--space-sm); padding: var(--space-md) 0; }
  .pg-btn { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid var(--border); cursor: pointer; }
  .pg-btn:hover:not(:disabled) { background: var(--bg-hover); }
  .pg-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .pg-info { font-size: var(--font-tiny); color: var(--text-dim); }

  .row-skel { padding: var(--space-sm); }

  .detail { display: flex; flex-direction: column; gap: var(--space-md); }
  .dmeta { background: var(--bg-elevated); border-radius: var(--radius-md); padding: var(--space-sm) var(--space-md); display: flex; flex-direction: column; gap: 2px; border: 1px solid var(--border); }
  .drow { display: flex; justify-content: space-between; font-size: var(--font-small); gap: var(--space-md); padding: 3px 0; }
  .dlabel { color: var(--text-dim); flex-shrink: 0; }
  .dval { font-weight: 500; color: var(--text); text-align: right; }
  .dsection { padding: var(--space-sm) var(--space-md); border-radius: var(--radius-md); border: 1px solid var(--border); }
  .dsection.accent { background: var(--accent-subtle); border-color: var(--accent); border-color: color-mix(in srgb, var(--accent) 25%, transparent); }
  .dsec-title { font-size: var(--font-tiny); font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: .04em; margin: 0 0 6px 0; }
  .dsection p { font-size: var(--font-small); color: var(--text-secondary); line-height: 1.55; white-space: pre-wrap; margin: 0; }
  .dsection.accent p { color: var(--text); }
  .dlinks { display: flex; gap: 6px; flex-wrap: wrap; }
  .dlink { padding: 3px 12px; font-size: var(--font-tiny); font-family: var(--font-mono); border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent); border: 1px solid transparent; cursor: pointer; }
  .dlink:hover { border-color: var(--accent); }
  .dtok { padding: 3px 12px; font-size: var(--font-tiny); font-family: var(--font-mono); border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid var(--border); }

  @media (max-width: 768px) { .page { padding: var(--space-md); } .search-box { max-width: none; } }
</style>
