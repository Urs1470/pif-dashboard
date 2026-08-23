<script>
  // Butonul „Urmă" — vizibil doar cand jurnalul de pe aparat e pornit (`#/?urma=1`).
  // O atingere copiaza ultima inregistrare in clipboard. Vezi `lib/urma.js`.
  import { router } from '../lib/router.svelte.js'
  import { urmaActiva, porneste, ultimaUrma } from '../lib/urma.js'
  import { toast } from '../stores/ui.svelte.js'

  let activ = $state(urmaActiva())
  // Comutatorul de pe marca (Header) anunta printr-un eveniment.
  $effect(() => {
    const f = () => { activ = urmaActiva() }
    window.addEventListener('pif-urma', f)
    return () => window.removeEventListener('pif-urma', f)
  })

  // `?urma=1` / `?urma=0` in adresa comuta starea si ramane in localStorage.
  $effect(() => {
    const v = router.query.urma
    if (v === '1') { porneste(true); activ = true }
    else if (v === '0') { porneste(false); activ = false }
  })

  async function copiaza() {
    const u = ultimaUrma()
    if (!u) { toast('Nicio urmă încă — deschide întâi o foaie', 'error'); return }
    try {
      await navigator.clipboard.writeText(u)
      toast(`Urmă copiată (${Math.round(u.length / 1024)} kB)`, 'success')
    } catch (_) {
      // Fara clipboard (WebView vechi): un `<textarea>` selectat ramane drumul.
      const ta = document.createElement('textarea')
      ta.value = u
      document.body.appendChild(ta)
      ta.select()
      try { document.execCommand('copy'); toast('Urmă copiată', 'success') }
      catch (__) { toast('Nu s-a putut copia', 'error') }
      ta.remove()
    }
  }
</script>

{#if activ}
  <button class="urma" onclick={copiaza} aria-label="Copiază urma ultimei foi">Urmă</button>
{/if}

<style>
  /* Deasupra a tot, sub deget, dar mic: e o unealta de masurat, nu un control
     al aplicatiei. Sta pe stanga, ca sa nu se bata cu butonul plutitor. */
  .urma {
    position: fixed;
    /* DUPA BARA LATERALA, nu peste ea. Butonul sta la `--z-toast + 1` = 2001,
       adica peste orice altceva din aplicatie — bara e la `--z-sticky` = 200 —
       deci la `left: 16px` s-ar picta fix peste randurile de navigatie, si
       tocmai un obiect care se aprinde rar ar acoperi ceva ce e mereu acolo.
       Pe telefon `--sidebar-w` e 0 si termenul dispare, deci pozitia de acolo
       ramane exact cea de dinainte. */
    left: calc(var(--sidebar-w) + var(--space-md));
    bottom: calc(var(--dock-h) + 14px + var(--safe-bottom) + var(--space-12) + var(--kb, 0px));
    z-index: calc(var(--z-toast) + 1);
    min-height: var(--tap-min);
    padding: 0 var(--space-md);
    border-radius: var(--radius-full);
    background: var(--danger);
    color: var(--accent-text);
    font-size: var(--font-small);
    font-weight: var(--fw-semibold);
    box-shadow: var(--shadow-lg);
    cursor: pointer;
  }
  .urma:active { transform: scale(var(--press-scale)); }
</style>
