<script>
  export let params = {}
</script>

<div class="page">
  <h1>Proiect #{params.id}</h1>
  <p class="placeholder">Detalii proiect — taskuri, jurnal, echipamente, checklist, timer</p>
</div>

<style>
  .page { padding: var(--space-lg); }
  h1 { font-size: var(--font-h1); font-weight: 700; margin-bottom: var(--space-lg); }
  .placeholder { color: var(--text-dim); }
</style>
