<script>
  import { AlertTriangle, RotateCcw } from '@lucide/svelte'
  import Button from './Button.svelte'
  let { title = 'Ceva n-a mers', message = '', onretry = undefined, children } = $props()
</script>

<div class="err" role="alert">
  <AlertTriangle size={40} />
  <h3>{title}</h3>
  {#if message}
    <p>{message}</p>
  {/if}
  {#if onretry || children}
    <div class="err-actions">
      {#if onretry}
        <Button size="sm" variant="secondary" onclick={onretry}><RotateCcw size={14} /> Reîncearcă</Button>
      {/if}
      {#if children}{@render children()}{/if}
    </div>
  {/if}
</div>

<style>
  .err {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-2xl) var(--space-lg);
    color: var(--text-dim);
    text-align: center;
  }
  .err :global(svg) { color: var(--danger); }
  /* Inter, ca la EmptyState: „Ieșirile nu s-au putut încărca" e o propozitie,
     nu numele unui lucru. */
  h3 {
    font-size: var(--font-body);
    font-weight: var(--fw-semibold);
    color: var(--text-secondary);
  }
  p {
    font-size: var(--font-small);
    max-width: 360px;
    color: var(--text-dim);
  }
  .err-actions {
    margin-top: var(--space-sm);
    display: flex;
    gap: var(--space-sm);
  }
</style>
