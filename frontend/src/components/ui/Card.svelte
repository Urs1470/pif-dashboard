<script>
  let { padding = true, hover = false, onclick, children } = $props()
</script>

<div
  class="card"
  class:padded={padding}
  class:hoverable={hover}
  class:clickable={onclick}
  role={onclick ? 'button' : undefined}
  tabindex={onclick ? '0' : undefined}
  onclick={onclick}
  onkeydown={onclick ? (e) => e.key === 'Enter' && onclick(e) : undefined}
>
  {@render children()}
</div>

<style>
  .card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    overflow: hidden;
  }
  .padded {
    padding: var(--space-md);
  }
  .hoverable {
    transition: border-color var(--dur-fast) var(--ease);
  }
  .hoverable:hover {
    border-color: var(--text-dim);
  }
  .clickable {
    cursor: pointer;
  }
  .clickable:hover {
    border-color: var(--accent);
  }
</style>
