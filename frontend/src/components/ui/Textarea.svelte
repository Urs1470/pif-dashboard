<script>
  let { label = '', value = $bindable(''), placeholder = '', rows = 3, error = '', disabled = false, ...rest } = $props()
</script>

<label class="field" class:has-error={error}>
  {#if label}
    <span class="field-label">{label}</span>
  {/if}
  <textarea
    class="field-textarea"
    {placeholder}
    {rows}
    {disabled}
    aria-invalid={error ? 'true' : undefined}
    bind:value
    {...rest}
  ></textarea>
  {#if error}
    <span class="field-error">{error}</span>
  {/if}
</label>

<style>
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }
  .field-label {
    font-size: var(--font-small);
    font-weight: var(--fw-medium);
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
  }
  .field-textarea {
    padding: 10px 12px;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    color: var(--text);
    font-size: var(--font-body);
    font-family: inherit;
    resize: vertical;
    min-height: 72px;
    line-height: var(--lh-normal);
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .field-textarea:hover:not(:disabled):not(:focus) {
    border-color: var(--text-dim);
  }
  .field-textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: var(--focus-ring);
  }
  .field-textarea:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .field-textarea::placeholder {
    color: var(--text-dim);
  }
  .has-error .field-textarea {
    border-color: var(--danger);
  }
  .has-error .field-textarea:focus {
    box-shadow: 0 0 0 3px var(--danger-subtle);
  }
</style>
