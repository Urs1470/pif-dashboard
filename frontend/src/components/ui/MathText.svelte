<script>
  // Randeaza un text de proza in care marimile cu subscript/superscript apar profesional (KaTeX).
  // Recunoaste: $...$ (KaTeX explicit) si tokeni de forma X_y / X^y (baza latina, indice alnum).
  // Restul textului ramane neschimbat (inclusiv litere grecesti unicode, %, unitati etc.).
  import katex from 'katex'
  import 'katex/dist/katex.min.css'

  let { text = '' } = $props()

  function render(tex) {
    try { return katex.renderToString(tex, { throwOnError: false }) } catch (_) { return tex }
  }
  // Cache pe text: se recalculeaza doar cand textul se schimba (nu la fiecare re-render al cardului).
  const parts = $derived.by(() => {
    const s = String(text ?? '')
    if (!s) return []
    const re = /\$([^$]+)\$|([A-Za-z][A-Za-z0-9]*)([_^])([A-Za-z0-9]+)/g
    const out = []; let last = 0; let m
    while ((m = re.exec(s)) !== null) {
      if (m.index > last) out.push({ txt: s.slice(last, m.index) })
      if (m[1] != null) out.push({ html: render(m[1]) })
      else out.push({ html: render(`${m[2]}${m[3]}{${m[4]}}`) })
      last = re.lastIndex
    }
    if (last < s.length) out.push({ txt: s.slice(last) })
    return out
  })
</script>

{#each parts as p}{#if p.html}<span class="mt">{@html p.html}</span>{:else}{p.txt}{/if}{/each}

<style>
  /* simbolul inline preia fontul/culoarea textului din jur */
  .mt :global(.katex) { font-size: 1em; color: inherit; }
</style>
