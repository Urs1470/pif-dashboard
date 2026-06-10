<script>
  import { Wallet } from '@lucide/svelte'
</script>

<div class="page">
  <div class="page-header"><Wallet size={22} /><h1>Budget</h1></div>
  <p class="placeholder">Budget tracker — va fi portat din aplicatia standalone in faza urmatoare.</p>
</div>

<style>
  .page { padding: var(--space-lg); max-width: 900px; }
  .page-header { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); margin-bottom: var(--space-lg); }
  .page-header h1 { font-size: var(--font-h1); font-weight: 700; }
  .placeholder { color: var(--text-dim); font-size: var(--font-small); }
</style>
