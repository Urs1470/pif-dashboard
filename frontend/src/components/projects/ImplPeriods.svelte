<script>
  import { onMount } from 'svelte'
  import { MapPin, Building2, Plus, CalendarRange, Pencil, Check } from '@lucide/svelte'
  import { apiJson } from '../../lib/api.js'
  import { formatDate } from '../../lib/formatters.js'
  import ImplPeriodModal from './ImplPeriodModal.svelte'

  let { projectId } = $props()

  let periods = $state([])
  let loading = $state(true)
  let open = $state(false)
  let editing = $state(null)

  async function load() {
    loading = true
    try { periods = await apiJson(`/api/proiecte/${projectId}/implementari`) }
    catch { periods = [] } finally { loading = false }
  }
  onMount(load)

  function locLabel(l) { return l === 'sediu' ? 'Sediu EGB' : 'Site (șantier)' }
  function days(p) {
    if (!p.data_start || !p.data_sfarsit) return ''
    const a = new Date(p.data_start), b = new Date(p.data_sfarsit)
    return Math.round((b - a) / 86400000) + 1
  }
  function add() { editing = null; open = true }
  function edit(p) { editing = p; open = true }
</script>

<section class="ip-sec">
  <div class="ip-head">
    <div class="ip-title"><CalendarRange size={16} /> <h3>Perioade de implementare</h3></div>
    <button class="ip-add" onclick={add}><Plus size={14} /> Adaugă</button>
  </div>

  {#if loading}
    <p class="ip-muted">Se încarcă…</p>
  {:else if periods.length === 0}
    <p class="ip-muted">Nicio perioadă. Adaugă una (Site sau Sediu EGB).</p>
  {:else}
    <div class="ip-list">
      {#each periods as p (p.id)}
        <button class="ip-item loc-{p.locatie}" onclick={() => edit(p)}>
          <span class="ip-loc">
            {#if p.locatie === 'sediu'}<Building2 size={14} />{:else}<MapPin size={14} />{/if}
            {locLabel(p.locatie)}
          </span>
          <span class="ip-range">{formatDate(p.data_start)} – {formatDate(p.data_sfarsit)}{#if days(p)}<span class="ip-days">{days(p)} zile</span>{/if}</span>
          {#if p.eticheta}<span class="ip-tag">{p.eticheta}</span>{/if}
          <!-- Doar semnul, nu si comutatorul: bifa se pune si se scoate din
               Calendar, pe ziua respectiva, unde te si intreaba. Aici ar fi un al
               doilea loc din care se schimba acelasi lucru. -->
          {#if p.confirmata}<span class="ip-fac"><Check size={12} /> Făcut</span>{/if}
          <Pencil size={13} class="ip-edit" />
        </button>
      {/each}
    </div>
  {/if}
</section>

<ImplPeriodModal bind:open {projectId} period={editing} onsaved={load} />

<style>
  .ip-sec { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--card-pad, 16px); }
  .ip-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-sm); }
  .ip-title { display: flex; align-items: center; gap: 8px; color: var(--text); }
  .ip-title h3 { font-size: var(--font-body); font-weight: var(--fw-semibold); }
  .ip-add { display: inline-flex; align-items: center; gap: 5px; padding: 6px 12px; border-radius: var(--radius-md); background: var(--accent); border: none; color: var(--accent-text); font-size: var(--font-small); font-weight: var(--fw-semibold); cursor: pointer; }
  .ip-muted { color: var(--text-dim); font-size: var(--font-small); padding: 6px 2px; }
  .ip-list { display: flex; flex-direction: column; gap: 6px; }
  .ip-item { display: flex; align-items: center; gap: 12px; padding: 9px 12px; border-radius: var(--radius-md); background: var(--bg-panel); border: 1px solid var(--border); border-left: 3px solid var(--il); color: var(--text); cursor: pointer; text-align: left; }
  .ip-item:hover { border-color: var(--border-strong); }
  .loc-site { --il: var(--loc-site); } .loc-sediu { --il: var(--loc-sediu); }
  .ip-loc { display: inline-flex; align-items: center; gap: 6px; font-weight: var(--fw-medium); font-size: var(--font-small); color: color-mix(in oklab, var(--il) 55%, var(--text)); min-width: 130px; }
  .ip-range { font-family: var(--font-mono); font-size: var(--font-small); color: var(--text-secondary); display: inline-flex; align-items: center; gap: 8px; }
  .ip-days { font-size: var(--font-micro); color: var(--text-dim); }
  .ip-tag { font-size: var(--font-micro); background: var(--bg-elevated); color: var(--text-dim); padding: 1px 7px; border-radius: var(--radius-xs); }
  /* Acelasi semn ca in panoul zilei din Calendar: verde conturat, nu plin. */
  .ip-fac { display: inline-flex; align-items: center; gap: 3px; font-size: var(--font-micro); color: var(--success);
            padding: 1px 7px; border-radius: var(--radius-full); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--success) 40%, transparent); }
  .ip-item :global(.ip-edit) { margin-left: auto; color: var(--text-faint); flex-shrink: 0; }
  .ip-item:hover :global(.ip-edit) { color: var(--accent); }

  @media (max-width: 768px) {
    .ip-add { min-height: var(--tap-min); padding: 6px 16px; }
    /* Randul perioadei se rupea urat la 375px: locatia are 130px rezervati, iar
       intervalul + eticheta nu mai incapeau langa. Doua randuri, fara min-width. */
    .ip-item { flex-wrap: wrap; row-gap: 4px; min-height: var(--tap-min); }
    .ip-loc { min-width: 0; }
    .ip-item :global(.ip-edit) { align-self: center; }
  }
</style>
