<script>
  import { Inbox } from '@lucide/svelte'
  let { icon: Icon = Inbox, title = 'Nimic de afișat', description = '', children } = $props()
</script>

<div class="empty">
  <!-- ACEEASI FORMA CA EROAREA, cu o singura diferenta: PATRATUL E NEUTRU.
       Absenta nu e o eroare si n-are voie sa imprumute tenta de restant — daca
       „Niciun task" arata ca „n-a mers ceva", inveti sa te uiti dupa o
       problema exact cand nu exista niciuna. -->
  <span class="patrat"><Icon size={22} strokeWidth={1.5} /></span>
  <h3>{title}</h3>
  {#if description}
    <p>{description}</p>
  {/if}
  {#if children}
    <div class="empty-actions">
      {@render children()}
    </div>
  {/if}
</div>

<style>
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-2xl) var(--space-lg);
    color: var(--text-dim);
    text-align: center;
  }
  .patrat {
    display: grid;
    place-items: center;
    width: 48px;
    height: 48px;
    border-radius: var(--radius-md);
    background: var(--bg-elevated);
    color: var(--text-dim);
    margin-bottom: var(--space-xs);
  }
  /* Titlul unei stari goale e o PROPOZITIE („Niciun task fără termen"), nu
     numele unui lucru — deci treapta de corp, la 600, nu una de titlu. */
  h3 {
    font-size: var(--font-body);
    font-weight: var(--fw-semibold);
    color: var(--text);
  }
  p {
    font-size: var(--font-small);
    max-width: 320px;
    color: var(--text-dim);
  }
  .empty-actions {
    margin-top: var(--space-sm);
  }
</style>
