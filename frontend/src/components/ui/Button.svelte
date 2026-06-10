<script>
  let { variant = 'primary', size = 'md', disabled = false, loading = false, onclick, children, ...rest } = $props()
</script>

<button
  class="btn btn-{variant} btn-{size}"
  disabled={disabled || loading}
  {onclick}
  {...rest}
>
  {#if loading}
    <span class="spinner"></span>
  {/if}
  {@render children()}
</button>

<style>
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-xs);
    font-weight: 500;
    border-radius: var(--radius-sm);
    transition: all var(--dur-fast) var(--ease);
    white-space: nowrap;
    cursor: pointer;
    position: relative;
  }
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-sm { padding: 6px 12px; font-size: var(--font-tiny); }
  .btn-md { padding: 8px 16px; font-size: var(--font-small); }
  .btn-lg { padding: 10px 20px; font-size: var(--font-base); }

  .btn-primary {
    background: var(--accent);
    color: var(--bg);
  }
  .btn-primary:hover:not(:disabled) {
    background: var(--accent-hover);
  }

  .btn-secondary {
    background: var(--bg-elevated);
    color: var(--text);
    border: 1px solid var(--border);
  }
  .btn-secondary:hover:not(:disabled) {
    background: var(--bg-hover);
    border-color: var(--text-dim);
  }

  .btn-ghost {
    background: transparent;
    color: var(--text-secondary);
  }
  .btn-ghost:hover:not(:disabled) {
    background: var(--bg-hover);
    color: var(--text);
  }

  .btn-danger {
    background: var(--danger);
    color: white;
  }
  .btn-danger:hover:not(:disabled) {
    opacity: 0.85;
  }

  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
