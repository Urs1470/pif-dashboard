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
    gap: 5px;
    padding: 2px 9px;
    border-radius: var(--radius-full);
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    color: var(--badge-color);
    background: color-mix(in srgb, var(--badge-color) 12%, transparent);
    white-space: nowrap;
    transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease);
  }
  /* Fara `font-size`: scria exact aceeasi treapta ca `.badge`, deci nu micsora
     niciodata nimic — „small" inseamna doar mai stramt (padding si gap). */
  .badge.small {
    padding: 2px 8px;
    gap: 4px;
  }
  .dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--badge-color);
    opacity: 0.9;
    flex-shrink: 0;
    transition: background-color var(--dur-fast) var(--ease);
  }
  .small .dot {
    width: 4px;
    height: 4px;
  }
</style>
