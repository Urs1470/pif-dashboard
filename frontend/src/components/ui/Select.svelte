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
    padding: 10px 12px;
    padding-right: 32px;
    min-height: 46px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-size: var(--font-body);
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23859289' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 10px center;
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
    cursor: pointer;
  }
  .field-select:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-subtle);
  }
  .field-select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
