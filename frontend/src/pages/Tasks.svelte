<script>
  import { ListTodo } from '@lucide/svelte'
</script>

<div class="page">
  <div class="page-header">
    <ListTodo size={24} />
    <h1>Taskuri globale</h1>
  </div>
  <p class="placeholder">Taskuri zilnice — filtre, prioritati, categorii</p>
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
