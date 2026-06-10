<script>
  import { onMount } from 'svelte'
  import { Settings, Download, Database, BarChart3 } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import Card from '../components/ui/Card.svelte'
  import Button from '../components/ui/Button.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'

  let stats = $state(null)
  let loading = $state(true)

  onMount(async () => {
    try { stats = await apiJson('/api/stats') } catch (_) {}
    loading = false
  })
</script>

<div class="page">
  <div class="page-header"><Settings size={22} /><h1>Admin</h1></div>

  {#if loading}
    <div class="grid">{#each Array(6) as _}<Skeleton height="80px" />{/each}</div>
  {:else if stats}
    <h2 class="sec-title"><BarChart3 size={16} /> Statistici</h2>
    <div class="grid">
      {#each Object.entries(stats) as [key, val]}
        <Card>
          <div class="stat-label">{key.replace(/_/g, ' ')}</div>
          <div class="stat-value">{typeof val === 'number' ? val.toLocaleString() : val}</div>
        </Card>
      {/each}
    </div>
  {:else}
    <Card><p class="dim">Nu s-au putut incarca statisticile.</p></Card>
  {/if}

  <h2 class="sec-title"><Download size={16} /> Export</h2>
  <div class="actions">
    <Button variant="secondary" onclick={() => window.open('/api/export/excel', '_blank')}><Download size={14} /> Excel</Button>
    <Button variant="secondary" onclick={() => window.open('/api/export/pdf', '_blank')}><Download size={14} /> PDF</Button>
  </div>

  <h2 class="sec-title"><Database size={16} /> Baza de Date</h2>
  <Card><p class="dim">Backup-urile sunt gestionate automat pe server.</p></Card>
</div>

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); margin-bottom: var(--space-lg); }
  .page-header h1 { font-size: var(--font-h1); font-weight: 700; }
  .sec-title { display: flex; align-items: center; gap: var(--space-xs); font-size: var(--font-base); font-weight: 600; color: var(--text); margin-top: var(--space-lg); margin-bottom: var(--space-sm); }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--space-sm); }
  .stat-label { font-size: var(--font-tiny); font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-dim); margin-bottom: 4px; }
  .stat-value { font-size: var(--font-h2); font-weight: 700; color: var(--text); }
  .actions { display: flex; gap: var(--space-sm); }
  .dim { color: var(--text-dim); font-size: var(--font-small); }

  @media (max-width: 768px) { .page { padding: var(--space-md); } .grid { grid-template-columns: repeat(2, 1fr); } }
</style>
