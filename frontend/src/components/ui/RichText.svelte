<script>
  // Read-only display of user-entered rich text (HTML or legacy plain text) with
  // KaTeX math + tables. Reactive: re-renders when `value` changes.
  // collapsible: clamp tall content to `maxHeight` with a fade + "Arata tot" toggle.
  import { ChevronDown, ChevronUp } from '@lucide/svelte'
  import { renderStoredText } from '../../lib/storedText.js'
  import { renderMath } from '../../lib/math.js'

  // noToggle: doar clamp + fade, fara butonul "Arata tot" (parintele decide ce
  // se intampla la click — ex. campul de observatii deschide editorul).
  let { value = '', class: cls = '', collapsible = false, maxHeight = 220, noToggle = false } = $props()

  let inner = $state(null)
  let expanded = $state(false)
  let overflowing = $state(false)

  const clamped = $derived(collapsible && !expanded && overflowing)

  function measure() {
    if (!inner || !collapsible) { overflowing = false; return }
    overflowing = inner.scrollHeight > maxHeight + 8
  }

  $effect(() => {
    value // track
    if (!inner) return
    inner.innerHTML = renderStoredText(value)
    renderMath(inner)
    measure()
    // re-measure once layout/fonts settle
    requestAnimationFrame(measure)
  })

  $effect(() => {
    if (!collapsible) return
    const onResize = () => measure()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  })
</script>

{#if collapsible}
  <div class="rt-collapse">
    <div class="rt-clip" class:rt-clamped={clamped} style:max-height={clamped ? maxHeight + 'px' : null}>
      <div bind:this={inner} class="rich-content {cls}"></div>
      {#if clamped}<div class="rt-fade"></div>{/if}
    </div>
    {#if overflowing && !noToggle}
      <button class="rt-toggle" onclick={() => expanded = !expanded}>
        {#if expanded}<ChevronUp size={13} /> Restrange{:else}<ChevronDown size={13} /> Arata tot{/if}
      </button>
    {/if}
  </div>
{:else}
  <div bind:this={inner} class="rich-content {cls}"></div>
{/if}

<style>
  .rt-collapse { position: relative; }
  .rt-clip { position: relative; }
  .rt-clamped { overflow: hidden; }
  .rt-fade { position: absolute; left: 0; right: 0; bottom: 0; height: 44px; background: linear-gradient(transparent, var(--rt-fade, var(--bg))); pointer-events: none; }
  .rt-toggle { display: inline-flex; align-items: center; gap: 4px; margin-top: 6px; font-size: var(--font-tiny); font-weight: var(--fw-semibold); color: var(--accent); cursor: pointer; padding: 3px 8px; border-radius: var(--radius-xs); transition: background var(--dur-fast) var(--ease); }
  .rt-toggle:hover { background: var(--accent-subtle); }
</style>
