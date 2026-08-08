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
  /* Treapta MICRO, ca la Input — aceeasi eticheta peste tot. */
  .field-label {
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
  }
  /* Aceeasi reteta ca `.field-input` (vezi nota din Input.svelte): suprafata a
     doua, muchie interioara de 1px, raza de control, focus la 1,5px accent. */
  .field-textarea {
    padding: 10px 12px;
    background: var(--bg-elevated);
    border: none;
    border-radius: var(--radius-sm);
    box-shadow: inset 0 0 0 1px var(--border);
    color: var(--text);
    font-size: var(--font-body);
    font-family: inherit;
    resize: vertical;
    min-height: 72px;
    line-height: var(--lh-normal);
    transition: box-shadow var(--dur-fast) var(--ease);
  }
  .field-textarea:hover:not(:disabled):not(:focus) {
    box-shadow: inset 0 0 0 1px var(--border-strong);
  }
  .field-textarea:focus {
    outline: none;
    box-shadow: inset 0 0 0 1.5px var(--accent);
  }
  .field-textarea:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .field-textarea::placeholder {
    color: var(--text-dim);
  }
  .has-error .field-textarea {
    box-shadow: inset 0 0 0 1px var(--danger);
  }
  .has-error .field-textarea:focus {
    box-shadow: inset 0 0 0 1.5px var(--danger);
  }
</style>
