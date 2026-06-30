<script>
  import { Calendar, ChevronLeft, ChevronRight, X } from '@lucide/svelte'

  let {
    value = $bindable(''),
    label = '',
    placeholder = 'Selecteaza data',
    disabled = false,
  } = $props()

  const MONTHS = ['Ianuarie', 'Februarie', 'Martie', 'Aprilie', 'Mai', 'Iunie',
    'Iulie', 'August', 'Septembrie', 'Octombrie', 'Noiembrie', 'Decembrie']
  const WEEKDAYS = ['Lu', 'Ma', 'Mi', 'Jo', 'Vi', 'Sâ', 'Du']

  let open = $state(false)
  let viewY = $state(0)
  let viewM = $state(0) // 0-indexed
  let triggerEl = $state(null)
  let popupEl = $state(null)
  let popupStyle = $state('')

  const pad = (n) => String(n).padStart(2, '0')
  const toISO = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`

  function parts(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
    if (!m) return null
    return { y: +m[1], mo: +m[2] - 1, d: +m[3] }
  }

  // Display label for the trigger (dd.mm.yyyy)
  const display = $derived.by(() => {
    const p = parts(value)
    return p ? `${pad(p.d)}.${pad(p.mo + 1)}.${p.y}` : ''
  })

  function today() {
    const t = new Date()
    return { y: t.getFullYear(), mo: t.getMonth(), d: t.getDate() }
  }

  function gridDays(y, m) {
    const first = (new Date(y, m, 1).getDay() + 6) % 7 // 0 = Monday
    const count = new Date(y, m + 1, 0).getDate()
    const cells = []
    for (let i = 0; i < first; i++) cells.push(null)
    for (let d = 1; d <= count; d++) cells.push(d)
    return cells
  }

  const days = $derived(gridDays(viewY, viewM))

  function positionPopup() {
    if (!triggerEl || !popupEl) return
    const r = triggerEl.getBoundingClientRect()
    const popupH = popupEl.offsetHeight || 320
    const popupW = popupEl.offsetWidth || 268
    // Target coordinates in viewport space.
    let top = r.bottom + 6
    if (top + popupH > window.innerHeight && r.top - popupH - 6 >= 0) top = r.top - popupH - 6
    let left = r.left
    if (left + popupW > window.innerWidth - 8) left = window.innerWidth - popupW - 8
    if (left < 8) left = 8
    // Modals use backdrop-filter/transform, which makes an ancestor the containing
    // block for our position:fixed popup. Subtract its offset so the fixed
    // coordinates land where we mean them to in the viewport.
    const cb = popupEl.offsetParent
    if (cb) {
      const cbr = cb.getBoundingClientRect()
      top -= cbr.top
      left -= cbr.left
    }
    popupStyle = `top:${Math.round(top)}px; left:${Math.round(left)}px;`
  }

  function openCal() {
    if (disabled) return
    const p = parts(value) || today()
    viewY = p.y
    viewM = p.mo
    open = true
  }

  // Position once Svelte has rendered the popup and bound popupEl.
  $effect(() => {
    if (open && popupEl) positionPopup()
  })

  function close() { open = false }

  function prevMonth() { if (viewM === 0) { viewM = 11; viewY-- } else viewM-- }
  function nextMonth() { if (viewM === 11) { viewM = 0; viewY++ } else viewM++ }

  function pick(d) {
    value = toISO(viewY, viewM, d)
    close()
  }
  function pickToday() {
    const t = today()
    value = toISO(t.y, t.mo, t.d)
    close()
  }
  function clear() { value = ''; close() }

  function isSelected(d) {
    const p = parts(value)
    return p && p.y === viewY && p.mo === viewM && p.d === d
  }
  function isToday(d) {
    const t = today()
    return t.y === viewY && t.mo === viewM && t.d === d
  }

  function onWindowClick(e) {
    if (!open) return
    if (triggerEl?.contains(e.target) || popupEl?.contains(e.target)) return
    close()
  }
  function onKey(e) { if (e.key === 'Escape') close() }
</script>

<svelte:window onclick={onWindowClick} onkeydown={onKey} onresize={() => open && positionPopup()} />

<div class="dp" class:has-label={label}>
  {#if label}<span class="dp-label">{label}</span>{/if}
  <button type="button" class="dp-trigger" class:placeholder={!display} {disabled}
    bind:this={triggerEl} onclick={() => open ? close() : openCal()}>
    <span class="dp-value">{display || placeholder}</span>
    <Calendar size={15} />
  </button>

  {#if open}
    <div class="dp-pop" bind:this={popupEl} style={popupStyle}>
      <div class="dp-head">
        <button type="button" class="dp-nav" onclick={prevMonth} aria-label="Luna anterioara"><ChevronLeft size={16} /></button>
        <span class="dp-title">{MONTHS[viewM]} {viewY}</span>
        <button type="button" class="dp-nav" onclick={nextMonth} aria-label="Luna urmatoare"><ChevronRight size={16} /></button>
      </div>
      <div class="dp-grid dp-wd">
        {#each WEEKDAYS as w}<span class="dp-wdname">{w}</span>{/each}
      </div>
      <div class="dp-grid">
        {#each days as d}
          {#if d === null}
            <span class="dp-empty"></span>
          {:else}
            <button type="button" class="dp-day" class:selected={isSelected(d)} class:today={isToday(d)} onclick={() => pick(d)}>{d}</button>
          {/if}
        {/each}
      </div>
      <div class="dp-foot">
        <button type="button" class="dp-foot-btn" onclick={pickToday}>Azi</button>
        {#if display}<button type="button" class="dp-foot-btn clear" onclick={clear}><X size={12} /> Sterge</button>{/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .dp { position: relative; display: inline-flex; flex-direction: column; gap: 4px; width: 100%; }
  .dp-label { font-size: var(--font-tiny); font-weight: 500; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; }

  .dp-trigger {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    min-height: 40px; padding: 8px 12px; width: 100%;
    background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md);
    color: var(--text); font-size: var(--font-body); font-family: inherit; cursor: pointer; text-align: left;
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .dp-trigger:hover:not(:disabled) { border-color: var(--text-dim); }
  .dp-trigger:focus-visible { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }
  .dp-trigger:disabled { opacity: 0.5; cursor: not-allowed; }
  .dp-trigger.placeholder .dp-value { color: var(--text-dim); }
  .dp-trigger :global(svg) { color: var(--text-dim); flex-shrink: 0; }
  .dp-value { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .dp-pop {
    position: fixed; z-index: var(--z-tooltip);
    width: 268px; padding: 12px;
    background: var(--bg-surface); border: 1px solid var(--border);
    border-radius: var(--radius-xl); box-shadow: var(--shadow-lg);
  }
  .dp-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
  .dp-title { font-size: var(--font-small); font-weight: 600; color: var(--text); }
  .dp-nav {
    width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
    border-radius: var(--radius-full); color: var(--text-secondary); cursor: pointer;
    transition: all var(--dur-fast) var(--ease);
  }
  .dp-nav:hover { background: var(--bg-hover); color: var(--text); }

  .dp-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
  .dp-wd { margin-bottom: 4px; }
  .dp-wdname { text-align: center; font-size: 10px; font-weight: 600; color: var(--text-dim); text-transform: uppercase; padding: 2px 0; }
  .dp-empty { aspect-ratio: 1; }
  .dp-day {
    aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
    border-radius: var(--radius-full); font-size: var(--font-small); color: var(--text-secondary);
    cursor: pointer; transition: all var(--dur-fast) var(--ease);
  }
  .dp-day:hover { background: var(--bg-hover); color: var(--text); }
  .dp-day.today { color: var(--accent); font-weight: 700; }
  .dp-day.selected { background: var(--accent); color: var(--accent-text); font-weight: 600; }
  .dp-day.selected:hover { background: var(--accent); color: var(--accent-text); }

  .dp-foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-subtle); }
  .dp-foot-btn {
    display: inline-flex; align-items: center; gap: 4px; padding: 5px 12px;
    border-radius: var(--radius-full); font-size: var(--font-tiny); font-weight: 600;
    color: var(--accent); background: var(--accent-subtle); cursor: pointer;
    transition: opacity var(--dur-fast) var(--ease);
  }
  .dp-foot-btn:hover { opacity: 0.8; }
  .dp-foot-btn.clear { color: var(--danger); background: transparent; }
</style>
