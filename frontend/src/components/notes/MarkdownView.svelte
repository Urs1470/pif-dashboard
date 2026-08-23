<script>
  import { renderMarkdown } from '../../lib/markdown.js'
  import { renderMath } from '../../lib/math.js'

  let { content = '', onwikilink } = $props()

  const html = $derived(renderMarkdown(content))
  let el = $state(null)

  // Typeset $…$ / $$…$$ dupa fiecare randare — altfel formulele Obsidian apar ca text brut.
  $effect(() => {
    html // track
    if (el) renderMath(el)
  })

  function onClick(e) {
    const link = e.target.closest('.md-wikilink')
    if (link) {
      const target = link.getAttribute('data-wikilink')
      if (target) onwikilink?.(target)
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="md-rendered" bind:this={el} onclick={onClick}>
  {@html html}
</div>

<style>
  /* Masura de citire ~72ch ca randurile sa nu ajunga la 140 caractere pe desktop */
  .md-rendered { font-size: var(--font-body); line-height: var(--lh-normal); color: var(--text); max-width: 72ch; }
  .md-rendered :global(.katex-display) { text-align: left; overflow-x: auto; overflow-y: hidden; }
  .md-rendered :global(h1), .md-rendered :global(h2), .md-rendered :global(h3) {
    margin: 1em 0 0.4em; font-weight: var(--fw-semibold); color: var(--text); letter-spacing: var(--tracking-tight);
  }
  .md-rendered :global(h1) { font-size: var(--font-h2); }
  .md-rendered :global(h2) { font-size: var(--font-h3); }
  .md-rendered :global(h3) { font-size: var(--font-h3); color: var(--text-secondary); }
  .md-rendered :global(p) { margin: 0.55em 0; }
  .md-rendered :global(ul), .md-rendered :global(ol) { margin: 0.5em 0; padding-left: 1.5em; }
  /* Marcatorii trebuie REAFIRMATI: `reset.css` sterge `list-style` de pe toate
     listele; fara asta, listele din notite apar ca paragrafe indentate.
     Aceeasi reafirmare in `.rich-content` (global.css) si `.rte-editor`. */
  .md-rendered :global(ul) { list-style: disc outside; }
  .md-rendered :global(ul ul) { list-style: circle outside; }
  .md-rendered :global(ol) { list-style: decimal outside; }
  .md-rendered :global(li) { margin: 0.2em 0; }
  .md-rendered :global(a) { color: var(--accent); text-decoration: none; }
  .md-rendered :global(a:hover) { text-decoration: underline; }
  /* Cod si valori: MONO 13 pe suprafata a doua — o treapta din scara, nu `0.85em`
     din marimea randului in care se nimeresc (care dadea 12,75 in corp si 17,85
     intr-un titlu, adica doua marimi diferite pentru acelasi fel de lucru). */
  .md-rendered :global(code) {
    background: var(--bg-elevated); padding: 1px var(--space-6); border-radius: var(--radius-xs);
    font-size: var(--font-small); font-family: var(--font-mono); color: var(--accent-deep);
  }
  .md-rendered :global(pre) {
    background: var(--bg-elevated); border-radius: var(--radius-sm);
    padding: var(--space-md); overflow-x: auto; margin: 0.7em 0;
  }
  .md-rendered :global(pre code) { background: none; padding: 0; color: var(--text); }
  /* Citatul PASTREAZA muchia de 3px, dar NEUTRA: intr-o notita e conventie
     tipografica, nu cod de culoare. Colorata, ar fi al doilea inteles pe aceeasi
     linie de 3px — vezi si caseta de mai jos, care si-a pierdut dunga tocmai ca
     sa nu se confunde cu ea. */
  .md-rendered :global(blockquote) {
    border-left: 3px solid var(--border); margin: 0.7em 0; padding: var(--space-2xs) 0 var(--space-2xs) var(--space-14);
    color: var(--text-secondary);
  }
  .md-rendered :global(hr) { border: none; border-top: 1px solid var(--border-subtle); margin: 1.2em 0; }
  /* TABEL CU DOAR LINII DE RAND. Grila completa (chenar pe fiecare celula) plus
     fond pe antet desena o cutie in mijlocul unui text care n-are nicio alta
     cutie: liniile orizontale ajung ca sa urmaresti un rand, iar cele verticale
     nu adaugau decat cerneala. Antetul se deosebeste prin TREAPTA (micro
     majuscula), nu prin fundal. */
  .md-rendered :global(table) { border-collapse: collapse; margin: 0.7em 0; width: 100%; }
  .md-rendered :global(th), .md-rendered :global(td) {
    border-bottom: 1px solid var(--border); padding: var(--space-sm) var(--space-2xs); text-align: left;
  }
  .md-rendered :global(td) { font-size: var(--font-body); }
  .md-rendered :global(th) {
    font-size: var(--font-label); font-weight: var(--fw-semibold);
    text-transform: uppercase; letter-spacing: var(--tracking-label);
    color: var(--text-dim); padding-bottom: 7px;
  }
  .md-rendered :global(tr:last-child td) { border-bottom: none; }
  .md-rendered :global(img) { max-width: 100%; border-radius: var(--radius-xs); }
  .md-rendered :global(mark) { background: var(--accent-subtle); color: var(--accent-deep); border-radius: 2px; padding: 0 var(--space-2xs); }
  .md-rendered :global(input[type="checkbox"]) { margin-right: var(--space-xs); accent-color: var(--accent); }

  .md-rendered :global(.md-wikilink) {
    color: var(--accent-deep); cursor: pointer; border-bottom: 1px dashed var(--accent);
    border-radius: 2px; padding: 0 1px; transition: background-color var(--dur-fast) var(--ease);
  }
  .md-rendered :global(.md-wikilink:hover) { background: var(--accent-subtle); }
  .md-rendered :global(.md-tag) {
    color: var(--accent-deep); background: var(--accent-subtle); border-radius: var(--radius-full);
    padding: 0 7px; font-size: 0.82em;
  }

  /* Suprafata in tenta, FARA dunga: „bara de accent pe stanga" e interdictie
     explicita, iar aici era chiar figura ei — tenta plus muchie colorata. */
  .md-rendered :global(.md-callout) {
    background: var(--accent-subtle);
    border-radius: var(--radius-xs); padding: var(--space-10) var(--space-14); margin: 0.7em 0;
  }
  .md-rendered :global(.md-callout-title) { font-weight: var(--fw-semibold); font-size: var(--font-body); color: var(--accent-on-subtle); }
  .md-rendered :global(.md-callout-body) { margin-top: var(--space-xs); }
  .md-rendered :global(.md-callout-body > *:first-child) { margin-top: 0; }
  .md-rendered :global(.md-callout-body > *:last-child) { margin-bottom: 0; }
  /* CELE OPT VARIANTE: `border-left-color` fara `border-left` — declaratii moarte
     de cand baza si-a pierdut dunga (B4). Se sterg, altfel prima persoana care
     pune inapoi o muchie pe `.md-callout` reinvie opt dungi colorate fara sa-si
     dea seama de unde vin.
     Si cerneala: era la valoarea PLINA peste propria tenta (E3). Text pe tenta ia
     intotdeauna varianta ADANCA — de aceea exista `-deep`. */
  .md-rendered :global(.md-callout-note) { background: var(--accent-subtle); }
  .md-rendered :global(.md-callout-note .md-callout-title) { color: var(--accent-deep); }
  .md-rendered :global(.md-callout-tip) { background: var(--success-subtle); }
  .md-rendered :global(.md-callout-tip .md-callout-title) { color: var(--success-deep); }
  .md-rendered :global(.md-callout-success) { background: var(--success-subtle); }
  .md-rendered :global(.md-callout-success .md-callout-title) { color: var(--success-deep); }
  .md-rendered :global(.md-callout-question) { background: var(--accent-subtle); }
  .md-rendered :global(.md-callout-question .md-callout-title) { color: var(--accent-deep); }
  .md-rendered :global(.md-callout-warning) { background: var(--danger-subtle); }
  .md-rendered :global(.md-callout-warning .md-callout-title) { color: var(--danger-deep); }
  .md-rendered :global(.md-callout-danger) { background: var(--danger-subtle); }
  .md-rendered :global(.md-callout-danger .md-callout-title) { color: var(--danger-deep); }
  .md-rendered :global(.md-callout-example) { background: var(--accent-subtle); }
  .md-rendered :global(.md-callout-example .md-callout-title) { color: var(--accent-deep); }
  .md-rendered :global(.md-callout-quote) { background: var(--bg-elevated); }
  .md-rendered :global(.md-callout-quote .md-callout-title) { color: var(--text-secondary); }

  @media (max-width: 768px) {
    /* Un tabel din wiki are des mai multe coloane decat incap in 360px si nu poate
       cobori sub latimea lui minima. Cu `width: 100%` iesea pur si simplu din
       pagina, iar `.app-main` (overflow-x: clip) il TAIA: ultima coloana —
       „Sursă", „Ce s-a extras" — nu se mai vedea si nu exista nicio cale spre ea.
       `display: block` + `overflow-x: auto` ii da tabelului propriul derulaj, iar
       `max-content` cu plafon 100% il lasa sa se stranga cand chiar incape.
       Doar pe telefon: pe desktop coloana e destul de lata, iar acolo tabelele
       sunt latime-plina prin `width: 100%` si asa trebuie sa rămână. */
    .md-rendered :global(table) {
      display: block;
      width: max-content;
      max-width: 100%;
      overflow-x: auto;
      overscroll-behavior-x: contain;
    }
  }
</style>
