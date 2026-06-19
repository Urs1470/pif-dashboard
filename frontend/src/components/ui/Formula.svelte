<script>
  // Randeaza un string LaTeX cu KaTeX (server-side string -> {@html}).
  // KaTeX e deja dependinta proiectului (folosit si in RichText / observatii).
  import katex from 'katex'
  import 'katex/dist/katex.min.css'

  let { tex = '', display = false, inline = false } = $props()

  const html = $derived.by(() => {
    try {
      return katex.renderToString(tex, { throwOnError: false, displayMode: display })
    } catch (_) {
      return tex
    }
  })
</script>

<span class="formula" class:block={display} class:inline={inline}>{@html html}</span>

<style>
  .formula {
    display: block;
    max-width: 100%;
    color: var(--text-secondary);
    font-size: 0.85em;
    line-height: 1.35;
  }
  .formula.block {
    display: block;
  }
  /* simbol inline in eticheta (acelasi font/culoare ca textul din jur) */
  .formula.inline {
    display: inline;
    max-width: none;
    font-size: 1em;
    color: inherit;
  }
</style>
