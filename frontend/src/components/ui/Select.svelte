<script>
  // Dropdown custom pe tema Bento (meniul nativ de <select> e alb/OS si rupe
  // designul). API compatibil cu vechiul Select: label, value bindable,
  // options (stringuri sau {value,label}), placeholder, disabled, size, error,
  // onchange (primeste { target: { value } } ca un select nativ).
  import { fly } from 'svelte/transition'
  import { ChevronDown, Check } from '@lucide/svelte'
  import { motionDuration, DUR_FAST } from '../../lib/motion.svelte.js'

  let {
    label = '', value = $bindable(''), options = [], placeholder = '',
    error = '', disabled = false, size = 'md', onchange = null, ...rest
  } = $props()

  let open = $state(false)
  let rootEl = $state(null)
  let hi = $state(-1) // index evidentiat cu tastatura

  const items = $derived(options.map((o) => ({ value: o?.value ?? o, label: o?.label ?? o })))
  const selected = $derived(items.find((i) => String(i.value) === String(value)))
  const display = $derived(selected ? selected.label : (placeholder || 'Selectează...'))

  function toggle() {
    if (disabled) return
    open = !open
    if (open) hi = items.findIndex((i) => String(i.value) === String(value))
  }

  function pick(v) {
    open = false
    if (String(v) === String(value)) return
    value = v
    onchange?.({ target: { value: v } })
  }

  function onKey(e) {
    if (disabled) return
    if (!open && (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown')) {
      e.preventDefault(); toggle(); return
    }
    if (!open) return
    // `stopPropagation`, nu doar `preventDefault`: preventDefault NU opreste
    // urcarea, deci Escape ajungea si la backdrop-ul Modalului, care se inchidea
    // odata cu dropdown-ul. Escape inchide UN strat — cel mai de sus.
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); open = false }
    else if (e.key === 'ArrowDown') { e.preventDefault(); hi = Math.min(items.length - 1, hi + 1) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); hi = Math.max(0, hi - 1) }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (items[hi]) pick(items[hi].value) }
    else if (e.key === 'Tab') { open = false }
  }

  function onDocClick(e) {
    if (open && rootEl && !rootEl.contains(e.target)) open = false
  }
</script>

<svelte:document onclick={onDocClick} />

<div class="field" class:has-error={error} bind:this={rootEl}>
  {#if label}
    <span class="field-label" id={undefined}>{label}</span>
  {/if}
  <button
    type="button"
    class="field-select"
    class:sm={size === 'sm'}
    class:open
    class:ph={!selected}
    {disabled}
    aria-haspopup="listbox"
    aria-expanded={open}
    onclick={toggle}
    onkeydown={onKey}
    {...rest}
  >
    <span class="fs-text">{display}</span>
    <ChevronDown size={size === 'sm' ? 13 : 15} class="fs-chev" />
  </button>

  {#if open}
    <div class="menu" role="listbox" transition:fly={{ y: -4, duration: motionDuration(DUR_FAST) }}>
      {#if placeholder}
        <button type="button" class="opt" class:sel={!selected} role="option" aria-selected={!selected}
          onclick={() => pick('')}>
          <span class="opt-label ph">{placeholder}</span>
          {#if !selected}<Check size={13} />{/if}
        </button>
      {/if}
      {#each items as it, i (String(it.value))}
        <button type="button" class="opt" class:sel={selected && String(it.value) === String(value)} class:hi={i === hi}
          role="option" aria-selected={selected && String(it.value) === String(value)}
          onmouseenter={() => (hi = i)} onclick={() => pick(it.value)}>
          <span class="opt-label">{it.label}</span>
          {#if selected && String(it.value) === String(value)}<Check size={13} />{/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    position: relative;
    min-width: 0;
  }
  /* Treapta MICRO, ca la Input — aceeasi eticheta peste tot. */
  .field-label {
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
  }
  /* Aceeasi reteta ca `.field-input` (vezi nota din Input.svelte). */
  .field-select {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-sm);
    width: 100%;
    padding: 10px 12px;
    min-height: 46px;
    background: var(--bg-elevated);
    border: none;
    border-radius: var(--radius-sm);
    box-shadow: inset 0 0 0 1px var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: var(--font-body);
    text-align: left;
    transition: box-shadow var(--dur-fast) var(--ease);
    cursor: pointer;
  }
  .field-select.sm {
    min-height: 38px;
    padding: 6px 10px;
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
  }
  .fs-text { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .field-select.ph .fs-text { color: var(--text-dim); }
  .field-select :global(.fs-chev) { color: var(--text-dim); flex-shrink: 0; transition: transform var(--dur-fast) var(--ease); }
  .field-select.open :global(.fs-chev) { transform: rotate(180deg); }
  .field-select:hover:not(:disabled):not(:focus) { box-shadow: inset 0 0 0 1px var(--border-strong); }
  .field-select:focus, .field-select.open {
    outline: none;
    box-shadow: inset 0 0 0 1.5px var(--accent);
  }
  .field-select:disabled { opacity: 0.5; cursor: not-allowed; }
  .has-error .field-select { box-shadow: inset 0 0 0 1px var(--danger); }
  .has-error .field-select:focus { box-shadow: inset 0 0 0 1.5px var(--danger); }

  /* Meniul e o suprafata FLOTANTA: se desprinde prin umbra, nu prin chenar. */
  .menu {
    position: absolute;
    top: calc(100% + 5px);
    left: 0;
    min-width: 100%;
    width: max-content;
    max-width: 260px;
    z-index: var(--z-dropdown, 50);
    background: var(--bg-overlay);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-md);
    padding: 4px;
    max-height: 260px;
    overflow-y: auto;
    scrollbar-width: thin;
  }
  .opt {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-sm);
    width: 100%;
    padding: 8px 10px;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--font-small);
    text-align: left;
    cursor: pointer;
    background: transparent;
    border: none;
  }
  .opt.hi { background: var(--bg-hover); color: var(--text); }
  .opt.sel { color: var(--accent-on-subtle); background: var(--accent-subtle); }
  .opt-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .opt-label.ph { color: var(--text-dim); font-style: italic; }

  @media (max-width: 768px) {
    /* Optiunile aveau ~33px si stau LIPITE una de alta intr-o lista — cel mai usor
       loc din aplicatie in care alegi randul de deasupra celui pe care il voiai.
       Meniul se intinde si pe toata latimea declansatorului: la 260px ramanea
       ingust langa un camp de 343px si taia etichetele lungi. */
    /* In foaie, 48 — aceeasi regula ca la Input. */
    .field-select { min-height: var(--tap-sheet); }
    .field-select.sm { min-height: var(--tap-min); }
    .opt { min-height: var(--tap-min); font-size: var(--font-body); padding: 8px 12px; }
    .menu { max-width: none; max-height: 50dvh; overscroll-behavior: contain; }
  }
</style>
