<script>
  let { label = '', value = $bindable(''), options = [], placeholder = '', error = '', disabled = false, size = 'md', ...rest } = $props()
</script>

<label class="field" class:has-error={error}>
  {#if label}
    <span class="field-label">{label}</span>
  {/if}
  <select class="field-select" class:sm={size === 'sm'} bind:value {disabled} aria-invalid={error ? 'true' : undefined} {...rest}>
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
    font-weight: var(--fw-medium);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
  }
  .field-select {
    padding: 10px 12px;
    padding-right: 32px;
    min-height: 46px;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-size: var(--font-body);
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23948a7d' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 10px center;
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
    cursor: pointer;
  }
  .field-select.sm {
    min-height: 38px;
    padding: 6px 10px;
    padding-right: 30px;
    font-size: var(--font-small);
  }
  .field-select:hover:not(:disabled):not(:focus) {
    border-color: var(--text-dim);
  }
  .field-select:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: var(--focus-ring);
  }
  .field-select:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .has-error .field-select {
    border-color: var(--danger);
  }
  .has-error .field-select:focus {
    box-shadow: 0 0 0 3px var(--danger-subtle);
  }
</style>
