<script module>
  // Comune tuturor instantelor de Modal (vezi blocarea derularii mai jos).
  let blocari = 0
  let yBlocat = 0
</script>

<script>
  import { tick } from 'svelte'
  import { X } from '@lucide/svelte'
  import { fade, scale } from 'svelte/transition'
  import { motionDuration, DUR_FAST, DUR_BASE, EASE } from '../../lib/motion.svelte.js'
  import { ecran } from '../../lib/ecran.svelte.js'

  // `onclose` se cheama DOAR cand utilizatorul inchide (X, fundal, Escape, tras in
  // jos) — nu cand parintele pune `open = false` singur. Exista fiindca un modal de
  // scriere (notita) pierdea tot ce ai tastat la un click pe fundal: `onBackdrop`
  // stingea `open` si atat, fara sa intrebe si fara sa salveze. Cine deschide un
  // editor decide ce inseamna „am inchis" (la notite: salveaza, cu „Anulează" in
  // toast); cine deschide un formular poate sa nu dea nimic si sa se comporte ca
  // pana acum.
  let { open = $bindable(false), title = '', size = 'md', children, footer, onclose } = $props()
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
      // DEBLOCAREA ASTEAPTA SFARSITUL IESIRII. Se elibera in acelasi tact cu
      // `open = false`, deci `window.scrollTo(0, yBlocat)` repozitiona pagina din
      // spate CAT TIMP foaia era inca pe ecran: fundalul sarea sub o foaie care
      // tocmai cobora. Nu se vede in demonstratie, dar pe telefon e primul lucru
      // pe care il observi. Se recontroleaza `blocari` la capat: intre timp poate
      // fi deschisa alta foaie, si atunci pagina trebuie sa ramana blocata.
      setTimeout(() => {
        if (blocari > 0) return
        b.style.position = ''
        b.style.top = ''
        b.style.width = ''
        window.scrollTo(0, yBlocat)
      }, motionDuration(DUR_BASE))
    }
  })

  // Sheet-ul urca de sub marginea ecranului, indiferent cat de inalt e — `fly` ar
  // avea nevoie de o distanta in px, iar aceeasi distanta arata „sarit de jos" pe
  // un sheet scund si „abia miscat" pe unul inalt. Procentul e din propria inaltime,
  // deci pornirea e mereu exact sub margine.
  // O CASETA SI VOALUL EI NU POT AVEA DOUA CEASURI.
  //
  // Voalul foloseste `EASE` (vezi `transition:fade` din markup), caseta ramasese
  // pe implicitul lui `scale` — `cubicOut`. Sunt curbe diferite, deci in prima
  // treime voalul se intuneca vizibil inaintea casetei pe care o tine, si
  // amandoua se opresc in acelasi moment: obiectul pare ca vine DUPA umbra lui.
  // E aceeasi scapare pe care tura 8 a reparat-o la `fade`/`sosire`/`plecare`
  // (`--ease` era respectata peste tot in CSS si de nicio tranzitie Svelte);
  // `scale` n-a fost pe lista atunci fiindca `fly` si `slide` — verificate —
  // aveau deja `cubicOut`, si a fost pus in aceeasi galeata fara sa fie deschis.
  function intra(node) {
    const duration = motionDuration(DUR_BASE)
    if (sheet) return { duration, easing: EASE, css: (t, u) => `transform: translateY(${u * 100}%)` }
    return scale(node, { start: 0.96, duration, easing: EASE })
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
    // `trasY` RAMANE unde l-ai lasat. Punandu-l pe 0 aici, doua miscari se
    // compuneau pe acelasi obiect, pe proprietati diferite si in sensuri opuse:
    // `translate` revenea de la 118px la 0 in --dur-slow CU ARC, in timp ce
    // tranzitia de iesire cobora foaia cu toata inaltimea ei. Prima jumatate a
    // iesirii se anula singura — foaia se misca in jos incet, apoi brusc, ceea ce
    // se citeste exact ca lag de atingere. Iar arcul, care are voie sa depaseasca
    // tinta, tragea IN SUS fix in intervalul in care obiectul trebuia sa
    // accelereze in jos. Acum gestul si iesirea merg in acelasi sens.
    if (trasY > PRAG_INCHIDE) { inchide(); return }
    if (trasY < -PRAG_INTINDE) intins = true
    trasY = 0
  }

  // La fiecare deschidere pornim din starea normala, nu din cea intinsa a
  // taskului dinainte.
  // `trasY` nu se mai zeroeaza la ridicarea degetului (vezi `trageSus`), deci se
  // zeroeaza aici: foaia urmatoare porneste din pozitia ei, nu din cea in care ai
  // lasat-o pe cea dinainte.
  $effect(() => { if (open) { intins = false; trasY = 0 } })

  /** Singurul drum de inchidere pornit de utilizator. */
  function inchide() {
    open = false
    onclose?.()
  }

  function onBackdrop(e) {
    if (e.target === e.currentTarget) inchide()
  }

  function onKey(e) {
    if (e.key === 'Escape') { inchide(); return }
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
  <!-- VOALUL PLEACA ODATA CU FOAIA, NU INAINTEA EI. Era stins in --dur-fast
       (120ms), cand foaia mai avea inca ~170px de coborat: ultimele doua treimi
       ale inchiderii se jucau peste o pagina deja limpede si nedimuita, ca si cum
       foaia nu mai apartinea nimanui. Voalul TINE obiectul, deci pleaca odata cu
       el sau dupa el — niciodata inainte. Acelasi ceas: --dur-base. -->
  <div class="backdrop" bind:this={backdropEl} onclick={onBackdrop} onkeydown={onKey} role="dialog" aria-modal="true" aria-label={title} tabindex="-1" transition:fade={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
    <div class="modal modal-{size}" class:sheet class:intins class:trage
         bind:this={sheetEl} style:--trasY="{trasY}px" transition:intra>
      {#if sheet}
        <span class="sheet-grip" aria-hidden="true"></span>
      {/if}
      <!-- Se trage de TOT ANTETUL, nu de bara de 4px. Ion: „pot sa ridic doar daca
           tin apasat bara aia de sus, nu este prea comod". Bara ramane semnul
           vizual; suprafata care raspunde e antetul intreg — titlu, spatiu gol si
           bara — adica vreo 80px inaltime in loc de 4. Butonul de inchidere isi
           opreste singur gestul (`onpointerdown|stopPropagation`), altfel apasarea
           pe `X` ar porni o tragere. -->
      <div class="modal-header"
           onpointerdown={trageJos} onpointermove={trageMisca}
           onpointerup={trageSus} onpointercancel={trageSus}>
        <h2 class="modal-title">{title}</h2>
        <button class="modal-close" onpointerdown={(e) => e.stopPropagation()} onclick={inchide} aria-label="Închide"><X size={18} /></button>
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
    border-radius: var(--radius-lg);
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
  .modal-doc { max-width: 1060px; height: 95dvh; max-height: 95dvh; }
  /* ANTETUL UNUI DOCUMENT E O LINIE DE CONTEXT, NU UN TITLU DE FEREASTRA.
     Pe telefon asta se decisese deja (vezi `.modal.sheet .modal-title` mai jos);
     pe desktop ramasese varianta tare: Space Grotesk bold la 18.4px, care pe
     „Notițe — Verifică parametrii Danfoss FC302 — stand 4" umple randul si se taie.
     Titlul repeta oricum taskul din care ai venit — deci e context, nu titlu, si
     cel mai bun lucru care i se poate intampla e sa nu-ti ia atentia de la pagina
     goala de dedesubt. */
  .modal-doc .modal-header { border-bottom: none; padding-bottom: var(--space-sm); }
  .modal-doc .modal-title {
    font-family: var(--font-sans);
    font-size: var(--font-label);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    font-weight: var(--fw-semibold);
    color: var(--text-faint);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
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
    letter-spacing: var(--tracking-tight);
    font-size: var(--font-h3);
    font-weight: var(--fw-semibold);
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
    /* Fara `font-size`: butonul poarta un `<X>` Lucide (SVG dimensionat prin
       `size`), deci treapta de font nu masura niciodata nimic aici. */
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
      border-radius: var(--radius-lg) var(--radius-lg) 0 0;
      border-bottom: none;
      /* Umbra urca, nu coboara: sheet-ul se ridica peste pagina. */
      box-shadow: 0 -14px 40px -12px rgba(0, 0, 0, 0.6);
    }
    .modal-sm, .modal-md, .modal-lg, .modal-xl, .modal-wide, .modal-zoom { max-width: 100%; }

    /* Antetul e suprafata de tragere. `touch-action: none` doar aici: gestul e
       al nostru, dar restul sheet-ului trebuie sa se poata DERULA normal. */
    .modal.sheet .modal-header {
      touch-action: none;
      cursor: grab;
      -webkit-user-select: none;
      user-select: none;
    }
    .modal.sheet.trage .modal-header { cursor: grabbing; }
    .sheet-grip {
      width: 36px;
      height: 4px;
      margin: 8px auto 2px;
      border-radius: var(--radius-full);
      background: var(--border-strong);
      transition: background var(--dur-fast) var(--ease), width var(--dur-fast) var(--ease);
    }
    .modal.trage .sheet-grip { background: var(--accent); width: 52px; }

    /* Deplasarea din deget, pe `translate` (vezi nota din <script>). Cat timp
       tragi NU exista tranzitie — altfel sheet-ul ramane in urma degetului si se
       simte ca lag. La ridicare revine animat spre 0.
       Revenirea foloseste ARCUL (--ease-spring): un obiect pe care l-ai tras si
       l-ai eliberat se aseaza cu o depasire mica, nu se opreste mecanic — de
       aceea si durata e --dur-slow, arcul are nevoie de loc sa se aseze.
       Prima linie e rezerva pentru browserele fara `linear()`. */
    .modal.sheet {
      translate: 0 var(--trasY, 0px);
      transition: translate var(--dur-base) var(--ease), max-height var(--dur-base) var(--ease);
      transition: translate var(--dur-slow) var(--ease-spring), max-height var(--dur-base) var(--ease);
      will-change: translate;
    }
    .modal.sheet.trage { transition: none; }

    /* Tras in sus = ecran plin. DOAR `max-height`, niciodata si `height`:
       prima varianta le seta pe amandoua, iar `height` fix face saltul pe care Ion
       l-a numit „se rupe modalul si dupa abia se extinde" — continutul se reaseza
       instantaneu, apoi tranzitia pornea de la o geometrie deja schimbata. */
    .modal.sheet.intins {
      max-height: calc(100dvh - var(--safe-top));
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
      font-size: var(--font-label);
      text-transform: uppercase;
      letter-spacing: var(--tracking-label);
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
