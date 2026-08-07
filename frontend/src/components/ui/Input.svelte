<script>
  let { label = '', value = $bindable(''), type = 'text', placeholder = '', error = '', disabled = false, ...rest } = $props()
</script>

<label class="field" class:has-error={error}>
  {#if label}
    <span class="field-label">{label}</span>
  {/if}
  <input
    class="field-input"
    {type}
    {placeholder}
    {disabled}
    aria-invalid={error ? 'true' : undefined}
    bind:value
    {...rest}
  />
  {#if error}
    <span class="field-error">{error}</span>
  {/if}
</label>

<style>
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .field-label {
    font-size: var(--font-small);
    font-weight: var(--fw-medium);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
  }
  .field-input {
    padding: 10px 12px;
    min-height: 46px;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-size: var(--font-body);
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .field-input:hover:not(:disabled):not(:focus) {
    border-color: var(--text-dim);
  }
  .field-input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: var(--focus-ring);
  }
  .field-input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .field-input::placeholder {
    color: var(--text-dim);
  }
  .has-error .field-input {
    border-color: var(--danger);
  }
  .has-error .field-input:focus {
    box-shadow: 0 0 0 3px var(--danger-subtle);
  }
  .field-error {
    font-size: var(--font-small);
    color: var(--danger);
  }
</style>
