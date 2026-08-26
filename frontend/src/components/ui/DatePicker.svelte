<script>
  import { Calendar, ChevronLeft, ChevronRight, X } from '@lucide/svelte'
  import { ecran } from '../../lib/ecran.svelte.js'
  import { scale, fly, fade } from 'svelte/transition'
  import { portal } from '../../lib/portal.js'
  import { motionDuration, DUR_FAST, DUR_BASE, DUR_NORMAL, EASE } from '../../lib/motion.svelte.js'
  import { nivelNou, nivelInchis } from './Modal.svelte'
  import { foaieTrage } from '../../lib/foaieTrage.js'

  let {
    value = $bindable(''),
    label = '',
    placeholder = 'Selectează data',
    disabled = false,
    onchange = undefined,
    // Textul FIX al declansatorului, cand el e un VERB, nu un camp.
    // Pe randul de task, „Planifică" e o actiune asezata langa termenul deja
    // scris in coloana lui: daca butonul ar arata tot data, acelasi lucru s-ar
    // scrie de doua ori pe 46px distanta, si niciunul n-ar spune ce face
    // atingerea. Gol => se poarta ca un camp (arata valoarea sau placeholderul).
    eticheta = '',
  } = $props()

  const MONTHS = ['Ianuarie', 'Februarie', 'Martie', 'Aprilie', 'Mai', 'Iunie',
    'Iulie', 'August', 'Septembrie', 'Octombrie', 'Noiembrie', 'Decembrie']
  const WEEKDAYS = ['Lu', 'Ma', 'Mi', 'Jo', 'Vi', 'Sâ', 'Du']

  let open = $state(false)
  let viewY = $state(0)
  let viewM = $state(0) // 0-indexed
  let direction = $state(1) // for the month-grid slide: +1 next, -1 prev
  let triggerEl = $state(null)
  let popupEl = $state(null)
  let popupStyle = $state('')

  const pad = (n) => String(n).padStart(2, '0')
  const toISO = (y, m, d) => `${y}-${pad(m + 1)}-${pad(d)}`

  function parts(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
    if (!m) return null
    return { y: +m[1], mo: +m[2] - 1, d: +m[3] }
  }

  // Display label for the trigger (dd.mm.yyyy)
  const display = $derived.by(() => {
    const p = parts(value)
    return p ? `${pad(p.d)}.${pad(p.mo + 1)}.${p.y}` : ''
  })

  function today() {
    const t = new Date()
    return { y: t.getFullYear(), mo: t.getMonth(), d: t.getDate() }
  }

  function gridDays(y, m) {
    const first = (new Date(y, m, 1).getDay() + 6) % 7 // 0 = Monday
    const count = new Date(y, m + 1, 0).getDate()
    const cells = []
    for (let i = 0; i < first; i++) cells.push(null)
    for (let d = 1; d <= count; d++) cells.push(d)
    return cells
  }

  const days = $derived(gridDays(viewY, viewM))

  // Pe telefon calendarul nu se mai agata de declansator: devine sheet pe toata
  // latimea, lipit de marginea de jos. Doua motive, amandoua verificate pe ecranul
  // real: (1) popup-ul de 268px imparte 7 coloane, deci o zi are ~34px — sub pragul
  // la care nimeresti din prima; (2) declansatorul poate fi oriunde pe verticala,
  // deci calendarul aparea uneori sus, unde degetul mare nu ajunge.
  const sheet = $derived(ecran.telefon)

  function positionPopup() {
    if (sheet) { popupStyle = ''; return }
    if (!triggerEl || !popupEl) return
    const r = triggerEl.getBoundingClientRect()
    const popupH = popupEl.offsetHeight || 320
    const popupW = popupEl.offsetWidth || 268
    // Target coordinates in viewport space.
    let top = r.bottom + 6
    if (top + popupH > window.innerHeight && r.top - popupH - 6 >= 0) top = r.top - popupH - 6
    let left = r.left
    if (left + popupW > window.innerWidth - 8) left = window.innerWidth - popupW - 8
    if (left < 8) left = 8
    // Modals use backdrop-filter/transform, which makes an ancestor the containing
    // block for our position:fixed popup. Subtract its offset so the fixed
    // coordinates land where we mean them to in the viewport.
    const cb = popupEl.offsetParent
    if (cb) {
      const cbr = cb.getBoundingClientRect()
      top -= cbr.top
      left -= cbr.left
    }
    popupStyle = `top:${Math.round(top)}px; left:${Math.round(left)}px;`
  }

  function openCal() {
    if (disabled) return
    const p = parts(value) || today()
    viewY = p.y
    viewM = p.mo
    open = true
  }

  // DESCHIDEREA DIN AFARA. Pe boardul „Astăzi" glisarea spre stanga duce direct la
  // alegerea zilei, iar acolo declansatorul nu e pe ecran (`.arow-actions` lipseste
  // pe telefon). Aceeasi functie ca la clic — altfel calendarul s-ar deschide pe
  // luna la care ramasese, nu pe cea a taskului. Numele e lung ca sa nu se
  // ciocneasca de tranzitia `deschide` de mai jos.
  export function deschideCalendarul() { openCal() }

  // Position once Svelte has rendered the popup and bound popupEl.
  $effect(() => {
    if (open && popupEl) positionPopup()
  })

  // CALENDARUL INTRA IN ACEEASI STIVA CA MODALELE (regula din T1a) — DAR NUMAI
  // CA FOAIE, adica doar pe telefon.
  //
  // Ca foaie el ARE voal (`.dp-voal`, 0,5) si sta peste tot: fara sa se anunte,
  // foaia de sub el ramanea „varf" si isi picta voalul de 0,65, iar cele doua se
  // inmulteau (~0,83) — exact fondul negru pe care regula il interzice.
  //
  // Ca popover (desktop) NU are voal: se agata de declansator si nu intuneca
  // nimic. Daca s-ar anunta si acolo, ar lua varful de la panoul de sub el si
  // acela si-ar stinge voalul — deci un calendar deschis peste panou ar lasa
  // pagina complet nedimuita. „Voalul se picteaza doar pe varf" presupune ca
  // varful CHIAR are voal; un strat fara voal nu are ce sa preia.
  $effect(() => {
    if (!open || !sheet) return
    nivelNou()
    return () => nivelInchis()
  })

  function close() { open = false }

  // Sheet-ul urca de sub margine; popup-ul de desktop creste din punctul lui.
  // Foaia e SUPRAFATA (280ms), popoverul e ELEMENT (220ms) — doua marimi, doua
  // trepte din scara. Amandoua pe `--ease`: `cubicOut` era a doua curba, si se
  // vedea exact ca la modal (voalul pornea vizibil inaintea casetei).
  function deschide(node) {
    if (sheet) {
      return {
        duration: motionDuration(DUR_NORMAL),
        easing: EASE,
        css: (t, u) => `transform: translateY(${u * 100}%)`,
      }
    }
    return scale(node, { start: 0.96, duration: motionDuration(DUR_BASE), easing: EASE })
  }

  function prevMonth() { direction = -1; if (viewM === 0) { viewM = 11; viewY-- } else viewM-- }
  function nextMonth() { direction = 1; if (viewM === 11) { viewM = 0; viewY++ } else viewM++ }

  function pick(d) {
    value = toISO(viewY, viewM, d)
    onchange?.(value)
    close()
  }
  function pickToday() {
    const t = today()
    value = toISO(t.y, t.mo, t.d)
    onchange?.(value)
    close()
  }
  function clear() { value = ''; onchange?.(''); close() }

  function isSelected(d) {
    const p = parts(value)
    return p && p.y === viewY && p.mo === viewM && p.d === d
  }
  function isToday(d) {
    const t = today()
    return t.y === viewY && t.mo === viewM && t.d === d
  }

  function onWindowClick(e) {
    if (!open) return
    if (triggerEl?.contains(e.target) || popupEl?.contains(e.target)) return
    close()
  }
  // Pe faza de CAPTURA, nu de bubbling: ascultatorul de window pe bubbling ar
  // rula DUPA backdrop-ul Modalului (care sta pe drumul de urcare al focusului
  // din declansator), deci Escape inchidea si calendarul, si tot modalul.
  // In captura, fereastra e prima — inchidem calendarul si oprim propagarea,
  // iar modalul ramane deschis. Escape inchide UN strat.
  function onKey(e) {
    if (e.key !== 'Escape' || !open) return
    e.stopPropagation()
    close()
  }

  // Ridica pop-up-ul la <body> ca sa scape din orice stacking-context al unui
  // stramos (transform-ul tranzitiei de pagina, backdrop-filter-ul cardurilor,
  // .arow:hover) — altfel un card-frate ulterior in DOM il acopera desi are
  // z-index mare. position:fixed + getBoundingClientRect => coordonatele raman
  // corecte in spatiul viewport-ului.
  // Mutat in `lib/portal.js` cand `Modal` a avut nevoie de acelasi lucru.
</script>

<svelte:window onclick={onWindowClick} onkeydowncapture={onKey} onresize={() => open && positionPopup()} />

<div class="dp" class:has-label={label}>
  {#if label}<span class="dp-label">{label}</span>{/if}
  <button type="button" class="dp-trigger" class:deschis={open} class:placeholder={!eticheta && !display} {disabled}
    bind:this={triggerEl} onclick={() => open ? close() : openCal()}>
    <span class="dp-value">{eticheta || display || placeholder}</span>
    <Calendar size={15} strokeWidth={1.5} />
  </button>

  {#if open && sheet}
    <!-- Voalul e al sheet-ului, nu al paginii: pe telefon calendarul acopera
         continutul, deci trebuie sa se vada ca restul e inactiv, iar atingerea
         alaturi trebuie sa inchida. -->
    <div class="dp-voal" use:portal onclick={close} role="presentation" transition:fade={{ duration: motionDuration(DUR_FAST), easing: EASE }}></div>
  {/if}

  {#if open}
    <div class="dp-pop" class:sheet use:portal bind:this={popupEl} style={popupStyle} transition:deschide
         use:foaieTrage={{ activ: sheet, laInchidere: () => { open = false } }}>
      {#if sheet}<span class="dp-grip" aria-hidden="true"></span>{/if}
      <div class="dp-head">
        <button type="button" class="dp-nav" onclick={prevMonth} aria-label="Luna anterioară"><ChevronLeft size={16} /></button>
        <span class="dp-title">{MONTHS[viewM]} {viewY}</span>
        <button type="button" class="dp-nav" onclick={nextMonth} aria-label="Luna următoare"><ChevronRight size={16} /></button>
      </div>
      <div class="dp-grid dp-wd">
        {#each WEEKDAYS as w}<span class="dp-wdname">{w}</span>{/each}
      </div>
      {#key `${viewY}-${viewM}`}
        <div class="dp-grid" in:fly={{ x: direction * 12, duration: motionDuration(DUR_FAST), easing: EASE }}>
          {#each days as d}
            {#if d === null}
              <span class="dp-empty"></span>
            {:else}
              <button type="button" class="dp-day" class:selected={isSelected(d)} class:today={isToday(d)} onclick={() => pick(d)}>{d}</button>
            {/if}
          {/each}
        </div>
      {/key}
      <div class="dp-foot">
        <button type="button" class="dp-foot-btn" onclick={pickToday}>Azi</button>
        {#if display}<button type="button" class="dp-foot-btn clear" onclick={clear}><X size={12} /> Șterge</button>{/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .dp { position: relative; display: inline-flex; flex-direction: column; gap: var(--space-xs); width: 100%; }
  .dp-label { font-size: var(--font-label); font-weight: var(--fw-semibold); color: var(--text-dim); text-transform: uppercase; letter-spacing: var(--tracking-label); }

  /* Al patrulea camp al sistemului: aceeasi reteta ca `.field-input` din
     Input.svelte (suprafata a doua · muchie interioara 1px · raza de control ·
     46px, 48 in foaie · focus la 1,5px accent). Era 40px si raza 14 — adica
     singurul camp cu alta inaltime si alt colt decat celelalte trei. */
  .dp-trigger {
    display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm);
    min-height: var(--ctrl-lg); padding: var(--space-10) var(--space-12); width: 100%;
    background: var(--bg-elevated); border: none; border-radius: var(--radius-sm);
    box-shadow: inset 0 0 0 1px var(--border);
    color: var(--text); font-size: var(--font-body); font-family: inherit; cursor: pointer; text-align: left;
    transition: box-shadow var(--dur-fast) var(--ease);
  }
  .dp-trigger:hover:not(:disabled) { box-shadow: inset 0 0 0 1px var(--border-strong); }
  /* SI CAND E DESCHIS, nu doar la focus de tastatura. Declansatorul e un `<button>`,
     iar pe butoane `:focus-visible` NU se aprinde la clic de mouse — deci deschideai
     popoverul si campul ramanea stins, desi el e chiar obiectul deschis. La cinci
     controale care se declara in comentariile lor „acelasi camp al sistemului",
     asta era singura deosebire pe care o vedeai cu ochiul.
     Reteta nu e inventata aici: `Select.svelte:196` o are deja — `:focus, .open`.
     (`Input` si `Textarea` raman pe `:focus` cu buna stiinta: sunt campuri de text,
     unde `:focus-visible` se potriveste oricum la clic, iar `:focus` are un plus —
     aprinde muchia si cand focalizam din cod, cum face foaia de adaugare.) */
  .dp-trigger:focus-visible,
  .dp-trigger.deschis { outline: none; box-shadow: inset 0 0 0 1.5px var(--accent); }
  .dp-trigger:disabled { opacity: 0.5; cursor: not-allowed; }
  .dp-trigger.placeholder .dp-value { color: var(--text-dim); }
  .dp-trigger :global(svg) { color: var(--text-dim); flex-shrink: 0; }
  .dp-value { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* Suprafata flotanta: se desprinde prin UMBRA, nu si prin chenar.

     Z-INDEXUL E AL UNUI STRAT PORTAT, NU AL UNUI DROPDOWN DIN PAGINA.
     `--z-dropdown` (100) descrie un meniu care sta in fluxul paginii si trebuie
     doar sa treaca peste continutul din jurul lui. Popoverul asta pleaca in
     `<body>` prin `use:portal`, deci ajunge FRATE cu backdropul Modalului — iar
     acela e la `--z-modal` (1000) sau mai sus. Masurat pe panoul „Perioadă de
     implementare": declansatorul se aprindea (`.deschis`), calendarul se randa
     la z 100 sub panoul de 1000, iar `elementFromPoint` pe ziua 15 intorcea
     formularul de deasupra — deci nu era doar invizibil, era si de neatins.
     `--z-tooltip` e treapta pe care o folosesc deja celelalte doua straturi
     portate: meniul din `Select.svelte` si varianta-foaie de mai jos. */
  .dp-pop {
    position: fixed; z-index: var(--z-tooltip);
    width: 268px; padding: var(--space-12);
    background: var(--bg-overlay);
    border-radius: var(--radius-md); box-shadow: var(--shadow-md);
  }
  .dp-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-10); }
  .dp-title { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); }
  .dp-nav {
    width: var(--ctrl-sm); height: var(--ctrl-sm); display: flex; align-items: center; justify-content: center;
    border-radius: var(--radius-full); color: var(--text-secondary); cursor: pointer;
    transition: var(--transition-colors);
  }
  .dp-nav:hover { background: var(--bg-hover); color: var(--text); }

  .dp-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: var(--space-2xs); }
  .dp-wd { margin-bottom: var(--space-xs); }
  .dp-wdname { text-align: center; font-size: var(--font-label); font-weight: var(--fw-semibold); color: var(--text-dim); text-transform: uppercase; padding: var(--space-2xs) 0; }
  .dp-empty { aspect-ratio: 1; }
  .dp-day {
    aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
    border-radius: var(--radius-full); font-size: var(--font-small); color: var(--text-secondary);
    cursor: pointer; transition: var(--transition-colors);
  }
  .dp-day:hover { background: var(--bg-hover); color: var(--text); }
  .dp-day.today { color: var(--accent); font-weight: var(--fw-semibold); }
  .dp-day.selected { background: var(--accent); color: var(--accent-text); font-weight: var(--fw-semibold); }
  .dp-day.selected:hover { background: var(--accent); color: var(--accent-text); }

  .dp-foot { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); margin-top: var(--space-10); padding-top: var(--space-10); border-top: 1px solid var(--border); }
  .dp-foot-btn {
    display: inline-flex; align-items: center; gap: var(--space-xs); padding: 5px var(--space-12);
    border-radius: var(--radius-full); font-size: var(--font-small); font-weight: var(--fw-semibold);
    color: var(--accent-on-subtle); background: var(--accent-subtle); cursor: pointer;
    transition: var(--transition-colors);
  }
  /* CERNEALA PE TENTA IA VARIANTA ADANCA, si hoverul APASA TENTA, nu stinge textul.
     Erau amandoua gresite in acelasi loc: `--accent` peste `--accent-subtle` (4,81
     pe tema deschisa, cand `--accent-deep` da 7,11), plus un hover pe opacitate —
     care se inmulteste peste cerneala si o duce sub prag. Regula e scrisa in
     `Button.svelte:121`: „hoverul merge spre varianta ADANCA, nu pe opacitate".
     `--accent-on-subtle` e literal `--accent-deep`; il folosesc pe el fiindca
     numeste ROLUL, si asa se repara singur daca perechea se schimba vreodata. */
  .dp-foot-btn:hover { background: color-mix(in oklab, var(--accent) 22%, var(--bg-surface)); }
  .dp-foot-btn.clear { color: var(--danger); background: transparent; }
  .dp-foot-btn.clear:hover { color: var(--danger-deep); background: var(--danger-subtle); }

  /* ===== Telefon: calendarul e sheet, cu zile pe care se poate nimeri =====
     Latimea intreaga imparte 7 coloane la ~50px in loc de ~34px, iar `aspect-ratio: 1`
     le face si inalte. Sub 44px greseala nu e „ai atins alaturi" — e „ai mutat taskul
     pe alta zi si nu ai vazut". */
  @media (max-width: 768px) {
    /* Declansatorul in forma lui normala (camp de formular) avea 40px. Variantele
       comprimate — iconita din randul de task — isi impun singure 44 in
       componentele lor. */
    .dp-trigger { min-height: var(--tap-sheet); }
  }

  /* Fara blur, ca la voalul modalului: sticla a iesit din sistem. */
  .dp-voal {
    position: fixed; inset: 0; z-index: calc(var(--z-tooltip) - 1);
    background: var(--scrim);
  }
  .dp-pop.sheet {
    top: auto; bottom: 0; left: 0; right: 0;
    width: auto; max-width: 100%;
    /* z-indexul vine din `.dp-pop`: e acelasi strat, doar alta forma. */
    padding: 0 var(--space-md) calc(var(--space-md) + var(--safe-bottom));
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    border-bottom: none;
    box-shadow: var(--shadow-foaie);
  }
  /* Manerul e SEMN, nu tinta: gestul asculta pe toata banda de sus a foii (vezi
     `lib/foaieTrage.js`). Aceeasi lectie ca la Modal — Ion: „de TOT ANTETUL, nu de
     bara de 4px". */
  .dp-grip {
    pointer-events: none;
    display: block; width: 36px; height: 4px; margin: var(--space-sm) auto var(--space-2xs);
    border-radius: var(--radius-full); background: var(--border-strong);
  }
  .dp-pop.sheet .dp-head { margin-bottom: var(--space-12); }
  .dp-pop.sheet .dp-title { font-size: var(--font-body); }
  .dp-pop.sheet .dp-nav { width: var(--tap-min); height: var(--tap-min); }
  .dp-pop.sheet .dp-grid { gap: var(--space-xs); }
  .dp-pop.sheet .dp-day { font-size: var(--font-body); min-height: var(--tap-min); border-radius: var(--radius-md); }
  .dp-pop.sheet .dp-wdname { font-size: var(--font-small); padding-bottom: var(--space-xs); }
  .dp-pop.sheet .dp-foot { margin-top: var(--space-12); padding-top: var(--space-12); gap: var(--space-sm); }
  .dp-pop.sheet .dp-foot-btn {
    flex: 1; justify-content: center; min-height: var(--tap-min);
    font-size: var(--font-small); border-radius: var(--radius-md);
  }
  /* Fara „Șterge" in sheet, „Azi" ar rămâne singur si intins pe toata latimea, ca un
     buton principal — nu e. */
  .dp-pop.sheet .dp-foot-btn:only-child { flex: 0 1 160px; }
</style>
