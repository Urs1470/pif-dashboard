<script>
  // CEASUL: al doilea selector de timp al aplicatiei, pe ACEEASI carcasa ca primul.
  //
  // Ion, 2026-08-17: „in primul rand trebuie ora sa pot selecta cu un ceas, tot
  // omogen cu designul." Prima varianta punea un `<input type="time">` — merge, dar
  // deschide selectorul SISTEMULUI: alt fundal, alte colturi, alta tipografie, si pe
  // Android chiar un cadran analogic. Adica singurul loc din aplicatie in care
  // alegerea unei valori arata ca alt program.
  //
  // OMOGEN INSEAMNA ACELASI OBIECT, nu „ceva asemanator": carcasa e copiata la
  // structura din `DatePicker.svelte` — acelasi declansator (a patra retea de camp
  // a sistemului: suprafata 2, muchie interioara 1px, raza de control, 46px / 48 in
  // foaie), aceeasi regula de asezare (popover agatat de declansator pe desktop,
  // FOAIE lipita de baza pe telefon), acelasi voal, aceeasi intrare in stiva de
  // modale, aceleasi durate. Cine a invatat calendarul stie deja ceasul.
  //
  // DE CE DOUA GRILE SI NU UN CADRAN. Un cadran analogic ar fi singura forma
  // circulara mare din aplicatie (cercul e rezervat bifei), si cere doua gesturi
  // imprecise pe o suprafata mica. Calendarul rezolva deja „alege dintr-un set
  // finit" cu o grila de celule rotunde — deci ora foloseste acelasi limbaj: 24 de
  // ore intr-o grila de 6, apoi minutele in pas de 5, in aceeasi grila de 6.
  // La pas de 5 nu se pierde nimic real: un task nu se pune la 8:37.
  import { Clock, X } from '@lucide/svelte'
  import { ecran } from '../../lib/ecran.svelte.js'
  import { scale, fade } from 'svelte/transition'
  import { portal } from '../../lib/portal.js'
  import { motionDuration, DUR_FAST, DUR_BASE, DUR_SLOW, EASE } from '../../lib/motion.svelte.js'
  import { nivelNou, nivelInchis } from './Modal.svelte'

  let {
    /** 'HH:MM' sau '' */
    value = $bindable(''),
    label = '',
    placeholder = 'Fără oră',
    disabled = false,
    onchange = undefined,
    /** Text FIX pe declansator, cand el e un VERB si nu un camp — ca la DatePicker. */
    eticheta = '',
  } = $props()

  const ORE = Array.from({ length: 24 }, (_, i) => i)
  const MINUTE = Array.from({ length: 12 }, (_, i) => i * 5)

  let open = $state(false)
  let triggerEl = $state(null)
  let popupEl = $state(null)
  let popupStyle = $state('')

  // Ce s-a ales pana acum, in timpul deschiderii. Se pleaca de la valoarea primita;
  // fara ea, de la ora rotunda urmatoare — nu de la 00:00, care ar cere sa treci
  // prin toata grila ca sa ajungi la o ora de lucru.
  let h = $state(null)
  let m = $state(0)

  const p2 = (n) => String(n).padStart(2, '0')

  function despica(v) {
    const s = String(v || '').trim()
    const mm = /^(\d{1,2}):(\d{2})$/.exec(s)
    if (!mm) return null
    const H = +mm[1], M = +mm[2]
    if (H > 23 || M > 59) return null
    return { h: H, m: M }
  }

  const afisat = $derived(despica(value) ? value : '')

  function deschideCeasul() {
    if (disabled) return
    const p = despica(value)
    if (p) { h = p.h; m = p.m }
    else {
      const acum = new Date()
      h = acum.getHours()
      // La pas de 5, in SUS: ora propusa e una care n-a trecut inca.
      m = Math.ceil(acum.getMinutes() / 5) * 5
      if (m >= 60) { m = 0; h = (h + 1) % 24 }
    }
    open = true
  }

  /** Se scrie la FIECARE atingere, nu la un buton „Gata".
   *  Motivul e cel din `SelectorZi` si din calendar: o alegere dintr-un set finit e
   *  deja decizia — un pas de confirmare in plus n-ar apara nimic, fiindca valoarea
   *  se vede pe declansator si se poate schimba din aceeasi foaie. */
  function scrie() {
    if (h === null) return
    value = `${p2(h)}:${p2(m)}`
    onchange?.(value)
  }

  function alegeOra(x) { h = x; scrie() }
  // Minutul INCHIDE, ora nu: ordinea fireasca e ora apoi minutul, deci minutul e
  // ultimul gest. Cine vrea ora rotunda atinge „00" si a terminat tot in doua
  // atingeri — la fel de multe ca la un selector nativ.
  function alegeMinut(x) { m = x; scrie(); close() }

  function acum() {
    const a = new Date()
    h = a.getHours()
    m = Math.round(a.getMinutes() / 5) * 5 % 60
    scrie()
    close()
  }

  function scoate() {
    value = ''
    onchange?.('')
    close()
  }

  function close() { open = false }

  // Pe telefon ceasul e FOAIE, ca si calendarul: grila de 6 coloane pe latimea
  // intreaga da celule de ~52px, iar in popoverul de 268px ar da ~40 — sub pragul
  // la care nimeresti ora din prima.
  const sheet = $derived(ecran.telefon)

  function positionPopup() {
    if (sheet) { popupStyle = ''; return }
    if (!triggerEl || !popupEl) return
    const r = triggerEl.getBoundingClientRect()
    const popupH = popupEl.offsetHeight || 300
    const popupW = popupEl.offsetWidth || 268
    let top = r.bottom + 6
    if (top + popupH > window.innerHeight && r.top - popupH - 6 >= 0) top = r.top - popupH - 6
    let left = r.left
    if (left + popupW > window.innerWidth - 8) left = window.innerWidth - popupW - 8
    if (left < 8) left = 8
    // Acelasi corectiv ca in DatePicker: un stramos cu `transform` devine blocul de
    // referinta al unui `position: fixed`, deci coordonatele trebuie mutate cu el.
    const cb = popupEl.offsetParent
    if (cb) {
      const cbr = cb.getBoundingClientRect()
      top -= cbr.top
      left -= cbr.left
    }
    popupStyle = `top:${Math.round(top)}px; left:${Math.round(left)}px;`
  }

  $effect(() => { if (open && popupEl) positionPopup() })

  // Intra in stiva de modale DOAR ca foaie — exact regula din DatePicker: ca foaie
  // are voal si trebuie sa fie „varf"; ca popover n-are voal, si daca ar lua varful
  // ar stinge voalul panoului de sub el.
  $effect(() => {
    if (!open || !sheet) return
    nivelNou()
    return () => nivelInchis()
  })

  function deschide(node) {
    if (sheet) {
      return {
        duration: motionDuration(DUR_SLOW),
        easing: EASE,
        css: (t, u) => `transform: translateY(${u * 100}%)`,
      }
    }
    return scale(node, { start: 0.96, duration: motionDuration(DUR_BASE), easing: EASE })
  }
</script>

<div class="so">
  {#if label}<span class="so-label">{label}</span>{/if}

  <button type="button" class="so-trigger" class:placeholder={!eticheta && !afisat} {disabled}
          bind:this={triggerEl} onclick={deschideCeasul}>
    <span class="so-value">{eticheta || afisat || placeholder}</span>
    <Clock size={16} strokeWidth={1.5} />
  </button>

  {#if open && sheet}
    <!-- Voalul e al foii, nu al paginii — ca la calendar. -->
    <div class="so-voal" use:portal onclick={close} role="presentation"
         transition:fade={{ duration: motionDuration(DUR_FAST), easing: EASE }}></div>
  {/if}

  {#if open}
    <div class="so-pop" class:sheet use:portal bind:this={popupEl} style={popupStyle} transition:deschide>
      {#if sheet}<span class="so-grip" aria-hidden="true"></span>{/if}
      <div class="so-head">
        <span class="so-title">Ora</span>
        <!-- Ce ai ales pana acum, in mono: se citeste ca o valoare, nu ca un titlu,
             si se schimba sub ochi la fiecare atingere. -->
        <span class="so-cit">{h === null ? '--:--' : `${p2(h)}:${p2(m)}`}</span>
      </div>

      <span class="so-sec">Ora</span>
      <div class="so-grid">
        {#each ORE as x}
          <button type="button" class="so-cel" class:selected={h === x} onclick={() => alegeOra(x)}>{p2(x)}</button>
        {/each}
      </div>

      <span class="so-sec">Minute</span>
      <div class="so-grid">
        {#each MINUTE as x}
          <button type="button" class="so-cel" class:selected={m === x} onclick={() => alegeMinut(x)}>{p2(x)}</button>
        {/each}
      </div>

      <div class="so-foot">
        <button type="button" class="so-foot-btn" onclick={acum}>Acum</button>
        {#if afisat}
          <button type="button" class="so-foot-btn clear" onclick={scoate}><X size={13} /> Scoate ora</button>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .so { position: relative; display: flex; flex-direction: column; gap: 6px; width: 100%; }
  .so-label {
    font-size: var(--font-label); font-weight: var(--fw-semibold); color: var(--text-dim);
    text-transform: uppercase; letter-spacing: var(--tracking-label);
  }

  /* A PATRA RETETA DE CAMP A SISTEMULUI, copiata la valoare din `.dp-trigger`:
     suprafata 2 · muchie interioara 1px · raza de control · 46px (48 in foaie) ·
     focus la 1,5px accent. Nu „asemanatoare" — identica, altfel ora si data ar fi
     doua feluri de camp una langa alta, in aceeasi foaie. */
  .so-trigger {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    min-height: 46px; padding: 10px 12px; width: 100%;
    background: var(--bg-elevated); border: none; border-radius: var(--radius-sm);
    box-shadow: inset 0 0 0 1px var(--border);
    color: var(--text); font-size: var(--font-body); font-family: inherit;
    cursor: pointer; text-align: left;
    transition: box-shadow var(--dur-fast) var(--ease);
  }
  .so-trigger:hover:not(:disabled) { box-shadow: inset 0 0 0 1px var(--border-strong); }
  .so-trigger:focus-visible { outline: none; box-shadow: inset 0 0 0 1.5px var(--accent); }
  .so-trigger:disabled { opacity: .5; cursor: not-allowed; }
  .so-trigger.placeholder .so-value { color: var(--text-dim); }
  .so-trigger :global(svg) { color: var(--text-dim); flex-shrink: 0; }
  /* Valoarea e o CIFRA, deci mono — se compara pe verticala cu termenele si cu
     celelalte ore din liste. */
  .so-value { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-variant-numeric: tabular-nums; }
  .so-trigger:not(.placeholder) .so-value { font-family: var(--font-mono); }

  .so-voal {
    position: fixed; inset: 0; background: var(--scrim);
    z-index: calc(var(--z-modal) + 40);
  }

  /* Suprafata flotanta: se desprinde prin UMBRA, nu prin chenar. */
  .so-pop {
    position: fixed; z-index: var(--z-dropdown);
    width: 268px; padding: 12px;
    background: var(--bg-overlay);
    border-radius: var(--radius-md); box-shadow: var(--shadow-md);
  }
  .so-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 10px; }
  .so-title { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); }
  .so-cit {
    font-family: var(--font-mono); font-size: var(--font-small);
    color: var(--accent-deep); font-variant-numeric: tabular-nums;
  }

  .so-sec {
    display: block;
    font-size: var(--font-label); font-weight: var(--fw-semibold); color: var(--text-dim);
    text-transform: uppercase; letter-spacing: var(--tracking-label);
    padding: 6px 0 4px;
  }

  /* SASE COLOANE, celule rotunde — acelasi limbaj ca grila de zile din calendar
     (`.dp-grid` / `.dp-day`). 24 de ore intra in patru randuri, 12 minute in doua. */
  .so-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 2px; }
  .so-cel {
    aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
    border-radius: var(--radius-full);
    font-family: var(--font-mono); font-size: var(--font-small);
    font-variant-numeric: tabular-nums;
    color: var(--text-secondary); cursor: pointer;
    transition: var(--transition-colors);
  }
  .so-cel:hover { background: var(--bg-hover); color: var(--text); }
  .so-cel.selected { background: var(--accent); color: var(--accent-text); font-weight: var(--fw-semibold); }
  .so-cel.selected:hover { background: var(--accent); color: var(--accent-text); }

  .so-foot {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-subtle);
  }
  .so-foot-btn {
    display: inline-flex; align-items: center; gap: 4px; padding: 5px 12px;
    border-radius: var(--radius-full); font-size: var(--font-small); font-weight: var(--fw-semibold);
    color: var(--accent); background: var(--accent-subtle); cursor: pointer;
    transition: opacity var(--dur-fast) var(--ease);
  }
  .so-foot-btn:hover { opacity: .8; }
  .so-foot-btn.clear { color: var(--danger); background: transparent; }

  /* ===== Telefon: ceasul e foaie, cu celule pe care se poate nimeri =====
     Latimea intreaga imparte 6 coloane la ~52px in loc de ~40. Sub 44 greseala nu e
     „ai atins alaturi", e „ai pus taskul la alta ora si n-ai vazut". */
  .so-pop.sheet {
    position: fixed; left: 0; right: 0; bottom: 0; top: auto;
    width: auto; max-height: 88dvh; overflow-y: auto;
    padding: 6px var(--space-md) calc(var(--space-md) + var(--safe-bottom));
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    box-shadow: var(--shadow-foaie);
    background: var(--bg-surface);
    z-index: calc(var(--z-modal) + 41);
  }
  /* Manerul: acelasi obiect ca al foii din `Modal` — 38×4, `--border-strong`. */
  .so-grip {
    display: block; width: 38px; height: 4px; margin: 8px auto 2px;
    border-radius: var(--radius-full); background: var(--border-strong);
  }
  @media (max-width: 768px) {
    .so-trigger { min-height: var(--tap-sheet); }
    /* Celula nu mai e patrata pe foaie: la 6 coloane pe 390px ar iesi 52 inalta,
       si cele sase randuri (4 de ore + 2 de minute) n-ar incapea fara derulare.
       48 = `--tap-sheet`, adica exact pragul de atingere din foaie. */
    .so-cel { aspect-ratio: auto; min-height: var(--tap-sheet); }
  }
</style>
