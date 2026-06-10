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
    font-size: var(--font-tiny);
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .field-input {
    padding: 8px 12px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text);
    font-size: var(--font-small);
    transition: border-color var(--dur-fast) var(--ease);
  }
  .field-input:focus {
    outline: none;
    border-color: var(--accent);
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
  .field-error {
    font-size: var(--font-tiny);
    color: var(--danger);
  }
</style>
