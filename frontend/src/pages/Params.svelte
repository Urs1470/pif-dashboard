<script>
  import { Cpu } from '@lucide/svelte'
</script>

<div class="page">
  <div class="page-header">
    <Cpu size={24} />
    <h1>Parametri</h1>
  </div>
  <p class="placeholder">Parametri drive — familii, cautare, coduri eroare</p>
</div>

<style>
  .page { padding: var(--space-lg); }
  .page-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    margin-bottom: var(--space-lg);
    color: var(--text);
  }
  .page-header h1 { font-size: var(--font-h1); font-weight: 700; }
  .placeholder { color: var(--text-dim); }
</style>
