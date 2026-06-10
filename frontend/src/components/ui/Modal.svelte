<script>
  let { open = $bindable(false), title = '', size = 'md', children } = $props()

  function onBackdrop(e) {
    if (e.target === e.currentTarget) open = false
  }
  function onKey(e) {
    if (e.key === 'Escape') open = false
  }
</script>

{#if open}
  <div class="backdrop" onclick={onBackdrop} onkeydown={onKey} role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal modal-{size}">
      <div class="modal-header">
        <h2 class="modal-title">{title}</h2>
        <button class="modal-close" onclick={() => open = false} aria-label="Inchide">&times;</button>
      </div>
      <div class="modal-body">
        {@render children()}
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: var(--z-modal);
    padding: var(--space-md);
    animation: fadeIn var(--dur-fast) var(--ease);
  }
  .modal {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    width: 100%;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    animation: slideUp var(--dur-base) var(--ease);
  }
  .modal-sm { max-width: 400px; }
  .modal-md { max-width: 560px; }
  .modal-lg { max-width: 720px; }
  .modal-xl { max-width: 960px; }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-md) var(--space-lg);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .modal-title {
    font-size: var(--font-base);
    font-weight: 600;
    color: var(--text);
  }
  .modal-close {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--text-dim);
    font-size: 20px;
    transition: all var(--dur-fast) var(--ease);
  }
  .modal-close:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  .modal-body {
    padding: var(--space-lg);
    overflow-y: auto;
  }

  @keyframes fadeIn { from { opacity: 0; } }
  @keyframes slideUp { from { opacity: 0; transform: translateY(12px); } }

  @media (max-width: 768px) {
    .modal {
      max-width: 100%;
      max-height: 90vh;
    }
  }
</style>
