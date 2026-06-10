<script>
  import { Home } from '@lucide/svelte'
</script>

<div class="page">
  <div class="page-header">
    <Home size={24} />
    <h1>Acasa</h1>
  </div>
  <p class="placeholder">Dashboard — statistici, taskuri de azi, proiecte recente</p>
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
  .page-header h1 {
    font-size: var(--font-h1);
    font-weight: 700;
  }
  .placeholder {
    color: var(--text-dim);
    font-size: var(--font-body);
  }
</style>
