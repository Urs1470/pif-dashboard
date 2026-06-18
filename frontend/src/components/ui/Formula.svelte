<script>
  // Randeaza un string LaTeX cu KaTeX (server-side string -> {@html}).
  // KaTeX e deja dependinta proiectului (folosit si in RichText / observatii).
  import katex from 'katex'
  import 'katex/dist/katex.min.css'

  let { tex = '', display = false } = $props()

  const html = $derived.by(() => {
    try {
      return katex.renderToString(tex, { throwOnError: false, displayMode: display })
    } catch (_) {
      return tex
    }
  })
</script>

<span class="formula" class:block={display}>{@html html}</span>

<style>
  .formula {
    display: block;
    max-width: 100%;
    overflow-x: auto;
    color: var(--text-secondary);
    font-size: 0.9em;
    line-height: 1.4;
  }
  .formula.block {
    display: block;
  }
</style>
