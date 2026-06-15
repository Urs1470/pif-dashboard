<script>
  // Read-only display of user-entered rich text (stored as HTML or legacy plain
  // text) with KaTeX math typeset. Reactive: re-renders when `value` changes.
  import { renderStoredText } from '../../lib/storedText.js'
  import { renderMath } from '../../lib/math.js'

  let { value = '', class: cls = '' } = $props()
  let el = $state(null)

  $effect(() => {
    if (!el) return
    el.innerHTML = renderStoredText(value)
    renderMath(el)
  })
</script>

<div bind:this={el} class={cls}></div>
