<script>
  let { color = 'var(--text-dim)', label = '', small = false } = $props()
</script>

<span class="badge" class:small style="--badge-color: {color}">
  <span class="dot"></span>
  {label}
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: var(--radius-full);
    font-size: var(--font-tiny);
    font-weight: 500;
    color: var(--badge-color);
    background: color-mix(in srgb, var(--badge-color) 12%, transparent);
    white-space: nowrap;
  }
  .badge.small {
    padding: 2px 8px;
    font-size: 11px;
    gap: 4px;
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--badge-color);
    flex-shrink: 0;
  }
  .small .dot {
    width: 5px;
    height: 5px;
  }
</style>
