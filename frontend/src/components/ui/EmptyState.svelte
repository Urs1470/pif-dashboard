<script>
  import { Inbox } from '@lucide/svelte'
  let { icon: Icon = Inbox, title = 'Nimic de afișat', description = '', children } = $props()
</script>

<div class="empty">
  <Icon size={40} />
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
    color: var(--text-faint);
    text-align: center;
  }
  /* Inter, nu Space Grotesk: titlul unei stari goale e o PROPOZITIE („Niciun
     task fara termen"), nu numele unui lucru. Fontul de titlu spune „asta se
     numeste asa"; aici nu se numeste nimic, doar se constata. */
  h3 {
    font-size: var(--font-body);
    font-weight: var(--fw-semibold);
    color: var(--text-secondary);
  }
  p {
    font-size: var(--font-small);
    max-width: 320px;
  }
  .empty-actions {
    margin-top: var(--space-sm);
  }
</style>
