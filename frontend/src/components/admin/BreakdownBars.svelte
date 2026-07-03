<script>
  let { items = [], color = 'var(--accent)', labelMap = {} } = $props()

  const max = $derived(Math.max(1, ...items.map(i => i.count || 0)))
</script>

<div class="bars">
  {#each items as item}
    <div class="bar-row">
      <span class="bar-label">{labelMap[item.label] || item.label || '—'}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width: {Math.round(((item.count || 0) / max) * 100)}%; background: {color}"></div>
      </div>
      <span class="bar-count">{item.count || 0}</span>
    </div>
  {/each}
  {#if items.length === 0}
    <p class="bars-empty">Fără date.</p>
  {/if}
</div>

<style>
  .bars { display: flex; flex-direction: column; gap: var(--space-xs); }
  .bar-row { display: grid; grid-template-columns: 110px 1fr 36px; align-items: center; gap: var(--space-sm); }
  .bar-label { font-size: var(--font-tiny); color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bar-track { height: 8px; background: var(--bg-elevated); border-radius: var(--radius-full); overflow: hidden; }
  .bar-fill { height: 100%; border-radius: var(--radius-full); transition: width var(--dur-slow) var(--ease); }
  .bar-count { font-size: var(--font-tiny); color: var(--text); font-weight: var(--fw-semibold); text-align: right; font-feature-settings: "tnum"; }
  .bars-empty { font-size: var(--font-tiny); color: var(--text-dim); }
</style>
