<script>
  import { Inbox } from '@lucide/svelte'
  let { icon: Icon = Inbox, title = 'Nimic de afisat', description = '', children } = $props()
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
  h3 {
    font-family: var(--font-heading);
    letter-spacing: -0.02em;
    font-size: var(--font-h3);
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
