<script>
  // `ref` e legabil fiindca `bind:this` nu se poate trece printr-un spread:
  // cine deschide un formular trebuie sa poata pune focusul pe campul care
  // conteaza, nu pe primul element focalizabil din modal.
  let { label = '', value = $bindable(''), ref = $bindable(null), type = 'text', placeholder = '', error = '', disabled = false, ...rest } = $props()
</script>

<label class="field" class:has-error={error}>
  {#if label}
    <span class="field-label">{label}</span>
  {/if}
  <input
    class="field-input"
    bind:this={ref}
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
    gap: var(--space-xs);
  }
  /* Eticheta e treapta MICRO: 12/600 majuscule cu .05em. Era la 13/500 — adica
     aceeasi marime ca metadatele din randuri, dar in majuscule, deci concura cu
     ele fara sa fie de acelasi fel. */
  .field-label {
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
  }

  /* CAMPUL, SCRIS O SINGURA DATA (vezi si Textarea, Select, DatePicker):
     suprafata a doua · muchie INTERIOARA de 1px · raza de control (10) · 46px
     (48 in foaie) · focus = muchie de accent 1,5px.

     Muchia e `inset box-shadow`, nu `border`: cu border, trecerea de la 1px la
     1,5px la focus ar schimba cutia si tot randul ar tresari cu jumatate de
     pixel. Interioara, muchia se ingroasa peste desen, nu peste geometrie.
     Pe telefon textul e la 16px din `--font-body`, deci Safari nu mai mareste
     pagina la focus — nu e nevoie de o a doua valoare scrisa de mana. */
  .field-input {
    padding: var(--space-10) var(--space-12);
    min-height: var(--ctrl-lg);
    background: var(--bg-elevated);
    border: none;
    border-radius: var(--radius-sm);
    box-shadow: inset 0 0 0 1px var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: var(--font-body);
    transition: box-shadow var(--dur-fast) var(--ease);
  }
  .field-input:hover:not(:disabled):not(:focus) {
    box-shadow: inset 0 0 0 1px var(--border-strong);
  }
  .field-input:focus {
    outline: none;
    box-shadow: inset 0 0 0 1.5px var(--accent);
  }
  .field-input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .field-input::placeholder {
    color: var(--text-dim);
  }
  .has-error .field-input {
    box-shadow: inset 0 0 0 1px var(--danger);
  }
  .has-error .field-input:focus {
    box-shadow: inset 0 0 0 1.5px var(--danger);
  }
  .field-error {
    font-size: var(--font-small);
    color: var(--danger);
  }

  @media (max-width: 768px) {
    /* In foaie, 48. Modalele sunt foi pe telefon, iar acolo se scrie cu
       telefonul in mana. */
    .field-input { min-height: var(--tap-sheet); }
  }
</style>
