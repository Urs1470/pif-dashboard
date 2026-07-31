<script module>
  // Comune tuturor instantelor de Modal (vezi blocarea derularii mai jos).
  let blocari = 0
  let yBlocat = 0
</script>

<script>
  import { tick } from 'svelte'
  import { X } from '@lucide/svelte'
  import { fade, scale } from 'svelte/transition'
  import { cubicOut } from 'svelte/easing'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../../lib/motion.svelte.js'
  import { ecran } from '../../lib/ecran.svelte.js'

  let { open = $bindable(false), title = '', size = 'md', children, footer } = $props()
  let backdropEl = $state(null)
  let previousFocus = $state(null)

  // Pe telefon modalul e un SHEET lipit de marginea de jos, nu o caseta centrata:
  // acolo ajunge degetul mare fara sa muti mana, si acolo se asteapta gestul de
  // inchidere. Deci si intrarea trebuie sa vina de jos — un `scale` din centru
  // spune „fereastra", nu „sertar".
  const sheet = $derived(ecran.telefon)

  // Cat timp sheet-ul e deschis, pagina de dedesubt nu se mai misca. Fara asta,
  // derularea continua in pagina din spate cand ajungi la capatul continutului din
  // sheet — iesi din modal si ai pierdut si locul din lista.
  //
  // Doar pe telefon: pe desktop pagina din spate se derula dintotdeauna si nimic
  // nu se pierde, iar `position: fixed` pe body langa `scrollbar-gutter: stable`
  // introduce un salt lateral pe care n-are rost sa-l platim.
  //
  // Contorul e pentru cazul in care doua sheet-uri sunt deschise in acelasi timp:
  // al doilea ar citi `scrollY` deja blocat (0) si, la inchidere, ar „restaura"
  // pagina la inceput. Blocheaza primul, deblocheaza ultimul.
  $effect(() => {
    if (!open || !sheet) return
    const b = document.body
    if (blocari === 0) {
      yBlocat = window.scrollY
      b.style.position = 'fixed'
      b.style.top = `-${yBlocat}px`
      b.style.width = '100%'
    }
    blocari++
    return () => {
      blocari--
      if (blocari > 0) return
      b.style.position = ''
      b.style.top = ''
      b.style.width = ''
      window.scrollTo(0, yBlocat)
    }
  })

  // Sheet-ul urca de sub marginea ecranului, indiferent cat de inalt e — `fly` ar
  // avea nevoie de o distanta in px, iar aceeasi distanta arata „sarit de jos" pe
  // un sheet scund si „abia miscat" pe unul inalt. Procentul e din propria inaltime,
  // deci pornirea e mereu exact sub margine.
  function intra(node) {
    const duration = motionDuration(DUR_BASE)
    if (sheet) return { duration, easing: cubicOut, css: (t, u) => `transform: translateY(${u * 100}%)` }
    return scale(node, { start: 0.96, duration })
  }

  // ===== TRAGEREA SHEET-ULUI (telefon) =====
  // Ion: „nu poate fi tras pe tot ecranul, nu poti sa-l tragi inapoi, doar prin x".
  // Manerul era pana acum DECOR: un dreptunghi care arata a maner si nu facea
  // nimic. Pe telefon asta e mai rau decat sa nu-l ai — promite un gest care nu
  // exista, deci incerci, nu se intampla nimic, si cauti `X`-ul.
  //
  // Deplasarea merge pe proprietatea `translate`, NU pe `transform`: tranzitiile
  // Svelte de intrare/iesire scriu `transform` inline pe acelasi nod, iar doua
  // surse pe aceeasi proprietate s-ar suprascrie. `translate` e o proprietate
  // separata, deci cele doua se compun in loc sa se bata.
  let trasY = $state(0)
  let trage = $state(false)
  let intins = $state(false)   // tras in sus pana la ecran plin
  let sheetEl = $state(null)
  let y0 = 0
  let idPointer = null

  const PRAG_INCHIDE = 110   // px in jos de la care ridicarea degetului inchide
  const PRAG_INTINDE = 40    // px in sus de la care sheet-ul se face ecran plin

  function trageJos(e) {
    if (!sheet || e.pointerType === 'mouse') return
    idPointer = e.pointerId
    y0 = e.clientY
    trasY = 0
    trage = true
    try { e.currentTarget.setPointerCapture?.(e.pointerId) } catch (_) {}
  }

  function trageMisca(e) {
    if (!trage || e.pointerId !== idPointer) return
    const dy = e.clientY - y0
    // In jos e liber (te duci spre inchidere). In sus se opreste scurt daca e deja
    // intins — altfel sheet-ul ar putea fi tras dincolo de marginea de sus.
    trasY = intins ? Math.max(0, dy) : (dy < 0 ? Math.max(dy, -90) : dy)
  }

  function trageSus(e) {
    if (!trage || e.pointerId !== idPointer) return
    trage = false
    idPointer = null
    if (trasY > PRAG_INCHIDE) { trasY = 0; open = false; return }
    if (trasY < -PRAG_INTINDE) intins = true
    trasY = 0
  }

  // La fiecare deschidere pornim din starea normala, nu din cea intinsa a
  // taskului dinainte.
  $effect(() => { if (open) intins = false })

  function onBackdrop(e) {
    if (e.target === e.currentTarget) open = false
  }

  function onKey(e) {
    if (e.key === 'Escape') { open = false; return }
    if (e.key === 'Tab' && backdropEl) {
      const focusable = backdropEl.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
  }

  $effect(() => {
    if (open) {
      previousFocus = document.activeElement
      tick().then(() => {
        const first = backdropEl?.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
        if (first) first.focus()
        else backdropEl?.focus()
      })
    } else if (previousFocus) {
      previousFocus.focus()
      previousFocus = null
    }
  })
</script>

{#if open}
  <div class="backdrop" bind:this={backdropEl} onclick={onBackdrop} onkeydown={onKey} role="dialog" aria-modal="true" aria-label={title} tabindex="-1" transition:fade={{ duration: motionDuration(DUR_FAST) }}>
    <div class="modal modal-{size}" class:sheet class:intins class:trage
         bind:this={sheetEl} style:--trasY="{trasY}px" transition:intra>
      {#if sheet}
        <!-- Zona de apucat, nu doar linia: 36px de bara intr-o banda de 28px
             inaltime, ca degetul sa nu trebuiasca sa nimereasca 4 pixeli. -->
        <div class="sheet-apuca" onpointerdown={trageJos} onpointermove={trageMisca}
             onpointerup={trageSus} onpointercancel={trageSus}
             role="button" tabindex="-1" aria-label="Trage ca să închizi sau să mărești">
          <span class="sheet-grip" aria-hidden="true"></span>
        </div>
      {/if}
      <div class="modal-header">
        <h2 class="modal-title">{title}</h2>
        <button class="modal-close" onclick={() => open = false} aria-label="Închide"><X size={18} /></button>
      </div>
      <div class="modal-body">
        {@render children()}
      </div>
      {#if footer}
        <div class="modal-footer">
          {@render footer()}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    backdrop-filter: blur(7px);
    -webkit-backdrop-filter: blur(7px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: var(--z-modal);
    padding: calc(var(--space-md) + var(--safe-top)) calc(var(--space-md) + var(--safe-right)) calc(var(--space-md) + var(--safe-bottom)) calc(var(--space-md) + var(--safe-left));
  }
  .modal {
    background: var(--bg-overlay);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    width: 100%;
    max-height: 85dvh;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-lg);
  }
  .modal-sm { max-width: 400px; }
  .modal-md { max-width: 560px; }
  .modal-lg { max-width: 720px; }
  .modal-xl { max-width: 960px; }
  .modal-wide { max-width: 80%; }
  .modal-zoom { max-width: 70%; }

  /* "doc" — document aproape fullscreen (editor observatii/notite).
     Body-ul nu deruleaza si nu are padding: pagina interioara (RichTextEditor
     variant="doc") isi gestioneaza singura scroll-ul si coloana de text. */
  .modal-doc { max-width: 900px; height: 92dvh; max-height: 92dvh; }
  .modal-doc .modal-body { padding: 0; overflow: hidden; display: flex; flex-direction: column; }
  .modal-doc .modal-body > :global(*) { flex: 1; min-height: 0; display: flex; flex-direction: column; }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-md) var(--space-lg);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .modal-title {
    font-family: var(--font-heading);
    letter-spacing: -0.02em;
    font-size: var(--font-h3);
    font-weight: var(--fw-bold);
    color: var(--text);
  }
  .modal-close {
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--text-dim);
    font-size: 20px;
    transition: var(--transition-colors);
  }
  .modal-close:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  .modal-body {
    padding: var(--space-lg);
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .modal-footer {
    padding: var(--space-md) var(--space-lg);
    border-top: 1px solid var(--border);
    flex-shrink: 0;
  }
  /* Randul de actiuni din footer — o singura reteta partajata (global, ca sa fie
     folosita din snippet-urile footer ale tuturor modalelor). :global fiindca e
     randat in slot-ul de footer al altui component. */
  :global(.modal-footer .modal-actions) {
    display: flex;
    gap: var(--space-sm);
    justify-content: flex-end;
    align-items: center;
    flex-wrap: wrap;
  }

  /* ===== Telefon: SHEET, nu caseta centrata =====
     O caseta centrata pe un ecran de 812px iti pune butoanele la mijloc, unde
     degetul mare nu ajunge fara sa muti mana, iar cand se deschide tastatura
     casetei ii ramane jumatate de ecran si sare in sus. Sheet-ul e lipit de
     marginea de jos: acolo ajunge degetul, acolo se opreste tastatura si de acolo
     vine gestul de inchidere.
     Manerul de sus nu e decor — spune „asta se trage/inchide de aici" si da o zona
     de apucat care nu e nici titlu, nici buton. */
  @media (max-width: 768px) {
    .backdrop {
      align-items: flex-end;
      padding: 0;
    }
    .modal {
      max-width: 100%;
      /* dvh urmareste bara de adresa; sheet-ul nu trebuie sa depaseasca ecranul
         nici cat timp bara se retrage. */
      max-height: min(92dvh, 100dvh - var(--safe-top) - 24px);
      border-radius: var(--radius-xl) var(--radius-xl) 0 0;
      border-bottom: none;
      /* Umbra urca, nu coboara: sheet-ul se ridica peste pagina. */
      box-shadow: 0 -14px 40px -12px rgba(0, 0, 0, 0.6);
    }
    .modal-sm, .modal-md, .modal-lg, .modal-xl, .modal-wide, .modal-zoom { max-width: 100%; }

    /* Banda de apucat: bara are 4px, dar degetul are nevoie de o zona. */
    .sheet-apuca {
      flex-shrink: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 28px;
      cursor: grab;
      touch-action: none;   /* gestul e al nostru, nu al derularii paginii */
    }
    .sheet-apuca:active { cursor: grabbing; }
    .sheet-grip {
      width: 36px;
      height: 4px;
      border-radius: var(--radius-full);
      background: var(--border-strong);
      transition: background var(--dur-fast) var(--ease), width var(--dur-fast) var(--ease);
    }
    .modal.trage .sheet-grip { background: var(--accent); width: 48px; }

    /* Deplasarea din deget. Cat timp tragi NU e tranzitie — altfel sheet-ul ar
       ramane in urma degetului; la ridicare revine animat spre 0. */
    .modal.sheet {
      translate: 0 var(--trasY, 0px);
      transition: translate var(--dur-base) var(--ease), max-height var(--dur-base) var(--ease);
    }
    .modal.sheet.trage { transition: max-height var(--dur-base) var(--ease); }

    /* Tras in sus = ecran plin. Ramane sub notch. */
    .modal.sheet.intins {
      max-height: calc(100dvh - var(--safe-top));
      height: calc(100dvh - var(--safe-top));
      border-radius: var(--radius-xl) var(--radius-xl) 0 0;
    }
    /* Antetul sheet-ului e o LINIE DE CONTEXT, nu un titlu de fereastra — ca
       „📥 Inbox >" la Todoist. Inainte lua ~90px pe verticala pentru un singur
       cuvant („birou"), fix acolo unde continutul ar trebui sa inceapa. */
    .modal.sheet .modal-header {
      padding: 2px var(--space-md) 0;
      border-bottom: none;
      min-height: 0;
    }
    .modal.sheet .modal-title {
      font-size: var(--font-micro);
      text-transform: uppercase;
      letter-spacing: var(--tracking-wide);
      font-weight: var(--fw-semibold);
      color: var(--text-faint);
    }
    .modal.sheet .modal-close { width: 40px; height: 40px; margin-right: -6px; }
    /* 32px e o tinta de cursor. Degetul are nevoie de 44, iar `X`-ul e singura
       iesire cand tastatura acopera restul sheet-ului. Marginea negativa il tine
       aliniat optic cu titlul, desi caseta lui a crescut. */
    .modal-close { width: var(--tap-min); height: var(--tap-min); margin-right: -10px; }

    .modal-header { padding-left: var(--space-md); padding-right: var(--space-md); }
    .modal-body {
      padding: var(--space-md);
      /* Ultimul rand din corp nu trebuie sa cada sub bara de gesturi. Cand exista
         footer, el poarta insetul si aici nu se mai adauga. */
      padding-bottom: calc(var(--space-md) + var(--safe-bottom));
      -webkit-overflow-scrolling: touch;
    }
    .modal:has(.modal-footer) .modal-body { padding-bottom: var(--space-md); }
    .modal-footer {
      padding: var(--space-12) var(--space-md) calc(var(--space-12) + var(--safe-bottom));
    }
    /* Actiunile ocupa latimea si stau la indemana: pe telefon un buton de 100px
       intr-un colt e o tinta mai mica decat trebuie, iar ordinea inversata pune
       actiunea principala sub degetul mare, la dreapta. */
    :global(.modal-footer .modal-actions) {
      gap: var(--space-sm);
    }
    :global(.modal-footer .modal-actions > *) {
      flex: 1 1 0;
      min-height: var(--tap-min);
      justify-content: center;
    }

    /* doc = sheet pe tot ecranul pe mobil */
    .backdrop:has(.modal-doc) { padding: 0; }
    .modal-doc {
      height: 100dvh; max-height: 100dvh;
      border-radius: 0; border: none;
      box-shadow: none;
    }
    .modal-doc .modal-header { padding-top: calc(var(--space-md) + var(--safe-top)); }
    .modal-doc .modal-footer { padding-bottom: calc(var(--space-md) + var(--safe-bottom)); }
  }
</style>
