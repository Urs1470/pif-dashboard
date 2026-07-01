<script>
  let { padding = true, hover = false, onclick, children } = $props()
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
  class="card"
  class:padded={padding}
  class:hoverable={hover}
  class:clickable={onclick}
  role={onclick ? 'button' : undefined}
  tabindex={onclick ? '0' : undefined}
  onclick={onclick}
  onkeydown={onclick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onclick(e) } } : undefined}
>
  {@render children()}
</div>

<style>
  .card {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
    transition: border-color var(--dur-fast) var(--ease);
  }
  .padded {
    padding: var(--card-pad);
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
