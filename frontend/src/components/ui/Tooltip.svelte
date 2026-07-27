<script>
  // Tooltip la nivel de aplicatie — o singura instanta, montata in App.
  //
  // DE CE ASA: sursa ramane atributul `title` (127 in 18 fisiere). Un sistem cu
  // `use:tip={...}` ar fi cerut rescrierea tuturor si ar fi ratat orice `title`
  // adaugat de-acum inainte. Aici, pe hover, mutam textul intr-o variabila si
  // STERGEM atributul — altfel bula nativa a sistemului ar aparea peste a noastra
  // — apoi il punem la loc cand pleaca cursorul.
  //
  // Accesibilitate: cat timp e sters, elementul si-ar pierde numele accesibil,
  // asa ca il repunem imediat la iesire, iar butoanele-doar-icoana au oricum
  // `aria-label` propriu. Tooltipul in sine e aria-hidden: nu adauga nimic la
  // arborele de accesibilitate.
  import { motion } from '../../lib/motion.svelte.js'

  const INTARZIERE = 380     // ca la sistem: nu sare la fiecare trecere peste
  const MARGINE = 8          // distanta fata de element si fata de marginea ferestrei

  let linii = $state([])
  let x = $state(0)
  let y = $state(0)
  let dedesubt = $state(false)
  let vizibil = $state(false)

  let tinta = null           // elementul al carui `title` l-am imprumutat (de restaurat)
  let nodCurent = null       // elementul deasupra caruia suntem, oricare ar fi sursa
  let textImprumutat = ''
  let cronometru = 0
  let el = $state(null)      // nodul tooltipului, ca sa-i masuram dimensiunea

  function restaurare() {
    if (tinta && textImprumutat && tinta.isConnected && !tinta.getAttribute('title')) {
      try { tinta.setAttribute('title', textImprumutat) } catch (_) {}
    }
    tinta = null
    nodCurent = null
    textImprumutat = ''
  }

  function ascunde() {
    clearTimeout(cronometru)
    vizibil = false
    linii = []
    restaurare()
  }

  async function aseaza() {
    // Masuram dupa ce s-a randat continutul, altfel latimea e a tooltipului gol.
    await Promise.resolve()
    if (!el || !nodCurent || !nodCurent.isConnected) return
    const r = nodCurent.getBoundingClientRect()
    const t = el.getBoundingClientRect()
    const sus = r.top - t.height - MARGINE
    dedesubt = sus < MARGINE
    y = dedesubt ? Math.min(r.bottom + MARGINE, window.innerHeight - t.height - MARGINE) : sus
    x = Math.max(MARGINE, Math.min(
      r.left + r.width / 2 - t.width / 2,
      window.innerWidth - t.width - MARGINE,
    ))
    vizibil = true
  }

  const CONTROALE = 'button, a, [role="button"], summary'

  /** Textul tooltipului si daca trebuie imprumutat (doar `title` produce bula
   *  nativa, deci doar el se sterge; `aria-label` e numele accesibil si ramane). */
  function sursa(nod) {
    const t = (nod.getAttribute('title') || '').trim()
    if (t) return { text: t, imprumut: true }
    // Cadere pe `aria-label`, dar NUMAI pe un control fara text vizibil: acolo
    // eticheta chiar E numele butonului. Altfel am pune tooltipuri pe containere
    // (`<nav aria-label="Navigație principală">`), ceea ce ar fi zgomot.
    const a = (nod.getAttribute('aria-label') || '').trim()
    if (a && nod.matches(CONTROALE) && !nod.textContent.trim()) {
      return { text: a, imprumut: false }
    }
    return null
  }

  function porneste(nod, imediat = false) {
    const s = sursa(nod)
    if (!s) return
    ascunde()
    tinta = s.imprumut ? nod : null
    textImprumutat = s.imprumut ? s.text : ''
    if (s.imprumut) nod.removeAttribute('title')
    nodCurent = nod
    const text = s.text
    // Svelte NU decodeaza entitatile HTML in atributele compilate cu expresie:
    // `title="a&#10;b"` ajunge in DOM cu `&#10;` LITERAL. (Se vedea si in bula
    // nativa, dinainte — doar ca nimeni nu se uita la ea.) Un `\n` scris in
    // atribut n-ar ajuta: acolo e text, nu sir JS. Deci decodam aici.
    linii = text
      .replace(/&#(?:10|13|x0?a);/gi, '\n')
      .split('\n')
      .map(l => l.trim())
      .filter(Boolean)
    const porni = () => aseaza()
    if (imediat || motion.reduced) porni()
    else cronometru = setTimeout(porni, INTARZIERE)
  }

  function peste(e) {
    // Doar cu mouse-ul. Pe atingere, un tooltip care apare la tap ar acoperi exact
    // lucrul pe care l-ai atins.
    if (e.pointerType && e.pointerType !== 'mouse') return
    const nod = e.target?.closest?.('[title], [aria-label]')
    if (!nod) { if (nodCurent) ascunde(); return }
    if (nod === nodCurent) return
    porneste(nod)
  }

  function iese(e) {
    if (!nodCurent) return
    const spre = e.relatedTarget
    if (spre && nodCurent.contains?.(spre)) return
    ascunde()
  }

  function focus(e) {
    const nod = e.target?.closest?.('[title], [aria-label]')
    if (nod) porneste(nod, true)
  }

  function tasta(e) { if (e.key === 'Escape') ascunde() }
</script>

<svelte:window
  onpointerover={peste}
  onpointerout={iese}
  onpointerdown={ascunde}
  onfocusin={focus}
  onfocusout={ascunde}
  onkeydown={tasta}
  onscroll={ascunde}
  onresize={ascunde}
/>

{#if linii.length}
  <div bind:this={el} class="tip" class:vaz={vizibil} class:jos={dedesubt}
       style="left:{x}px; top:{y}px" aria-hidden="true">
    {#each linii as l, i (i)}
      <span class="l" class:prima={i === 0}>{l}</span>
    {/each}
  </div>
{/if}

<style>
  .tip {
    position: fixed;
    z-index: var(--z-tooltip, 900);
    max-width: min(340px, calc(100vw - 24px));
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 7px 10px;
    border-radius: var(--radius-md);
    background: var(--bg-overlay);
    border: 1px solid var(--border-strong);
    box-shadow: var(--shadow-lg);
    color: var(--text-secondary);
    font-size: var(--font-micro);
    line-height: 1.45;
    pointer-events: none;
    opacity: 0;
    transform: translateY(3px);
    transition: opacity var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease);
  }
  .tip.jos { transform: translateY(-3px); }
  .tip.vaz { opacity: 1; transform: translateY(0); }

  /* Prima linie e subiectul, restul e detaliu — asa arata bine si tooltipurile
     multi-linie din Calendar („Deplasare · Continental" + lista lucrarilor). */
  .l { white-space: pre-wrap; overflow-wrap: anywhere; }
  .l.prima { color: var(--text); font-weight: var(--fw-medium); }

  @media (prefers-reduced-motion: reduce) {
    .tip { transition: none; }
  }
</style>
