<script>
  let { label = '', value = $bindable(''), options = [], placeholder = '', disabled = false, ...rest } = $props()
</script>

<label class="field">
  {#if label}
    <span class="field-label">{label}</span>
  {/if}
  <select class="field-select" bind:value {disabled} {...rest}>
    {#if placeholder}
      <option value="">{placeholder}</option>
    {/if}
    {#each options as opt}
      <option value={opt.value ?? opt}>{opt.label ?? opt}</option>
    {/each}
  </select>
</label>

<style>
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .field-label {
    font-size: var(--font-tiny);
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .field-select {
    padding: 8px 12px;
    padding-right: 32px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-size: var(--font-small);
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 10px center;
    transition: border-color var(--dur-fast) var(--ease);
    cursor: pointer;
  }
  .field-select:focus {
    outline: none;
    border-color: var(--accent);
  }
  .field-select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
