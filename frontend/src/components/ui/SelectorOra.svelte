<script>
  // CEASUL, CU CADRAN. Ion, 2026-08-17: „vreau ora sa fie ca ceas, nu grila."
  //
  // Prima varianta punea doua grile de celule rotunde, cu argumentul c-ar fi
  // omogene cu calendarul (care e si el o grila) si c-un cadran ar fi singura forma
  // circulara mare din aplicatie. Argumentul era despre consecventa interna; cererea
  // e despre ce recunoaste mana. Un cadran nu e o abatere de la limbajul
  // sistemului, e obiectul pe care limbajul il descrie: 24 de ore nu sunt un set de
  // valori fara ordine (ca zilele unei luni, care se aliniaza pe saptamani), ele se
  // intorc — iar un cerc spune „se intoarce" fara sa citesti nimic.
  //
  // CE RAMANE DIN OMOGENITATE, si e partea care conteaza: carcasa. Declansatorul,
  // asezarea (popover agatat pe desktop, FOAIE lipita de baza pe telefon), voalul,
  // intrarea in stiva de modale, durata intrarii — toate copiate la valoare din
  // `DatePicker.svelte`. Ce se schimba e ce e INAUNTRU.
  //
  // DOUA INELE, nu doua ecrane. Romania scrie ora pe 24, deci un cadran de 12 ar
  // cere un comutator AM/PM — un al treilea lucru de atins pentru o informaţie pe
  // care ora scrisa o are deja. Inel exterior 1–12, interior 13–00: exact ce face
  // si ceasul de 24 de ore din Material, si singura asezare in care toate cele 24
  // de valori sunt pe ecran deodata.
  //
  // ORA APOI MINUTUL, pe acelasi cadran. Nu doua cadrane alaturi: pe 390px ar fi
  // doua cercuri de ~150px, adica numere de sub 20px. Se comuta singur dupa ce
  // alegi ora, si se poate comuta inapoi atingand ora din antet — antetul e si
  // afisaj si navigatie, ca in orice selector de timp.
  import { Clock, X } from '@lucide/svelte'
  import { ecran } from '../../lib/ecran.svelte.js'
  import { scale, fade } from 'svelte/transition'
  import { portal } from '../../lib/portal.js'
  import { motionDuration, DUR_FAST, DUR_BASE, DUR_NORMAL, EASE } from '../../lib/motion.svelte.js'
  import { nivelNou, nivelInchis } from './Modal.svelte'
  import { foaieTrage } from '../../lib/foaieTrage.js'

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

  let open = $state(false)
  let triggerEl = $state(null)
  let popupEl = $state(null)
  let popupStyle = $state('')

  let h = $state(null)
  let m = $state(0)
  /** 'ora' | 'minut' — ce alege cadranul acum. */
  let faza = $state('ora')

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

  // ===== CEASUL DESCHIS PESTE O FOAIE NU MAI STINGE PAGINA A DOUA OARA =====
  //
  // Ion, 2026-08-17: „selectorul ora e ok, dar cand il deschid parca pagina se
  // stinge si se aprinde, la fel si la inchidere."
  //
  // Exact asta se intampla, si se poate socoti: ceasul isi picta voalul lui
  // (`--scrim`, 0,6) PESTE voalul foii de sub el, care e tot 0,6. Doua straturi de
  // 0,6 nu dau 0,6, dau ~0,84 — deci fondul se INTUNECA. Apoi `nivelNou()` ii ia
  // foii de dedesubt titlul de „varf", ea isi stinge voalul pe `--dur-base`, si
  // fondul se LUMINEAZA inapoi la 0,6. Doua treceri de opacitate pe aceiasi pixeli,
  // in ordine inversa: exact „se stinge si se aprinde". La inchidere, invers.
  //
  // Reparatia nu e o durata mai mica, e sa nu existe a doua stingere. Cand ceasul
  // vine PESTE un strat care are deja voal, voalul lui doar SEPARA — si tokenul
  // pentru asta exista deja, cu motivul scris in `tokens.css`: „`--scrim-slab` e
  // pentru cazul in care peste val vine si un panou opac — atunci valul doar
  // separa, nu stinge."
  // Fara tranzitie in cazul asta: orice fade ar fi tot o trecere de opacitate peste
  // fondul deja stins, adica exact ce reparam.
  //
  // Se citeste din DOM, nu din stiva: `are-modal` e pusa de `Modal` si e deja
  // adevarata in clipa atingerii, INAINTE ca `nivelNou()` al nostru sa se cheme.
  // Un `$derived` pe stiva ar da 0 la primul cadru si ar picta voalul intreg
  // exact atunci — adica ar produce chiar palpaitul.
  let pesteFoaie = $state(false)

  function deschideCeasul() {
    if (disabled) return
    try { pesteFoaie = document.documentElement.classList.contains('are-modal') } catch (_) { pesteFoaie = false }
    const p = despica(value)
    if (p) { h = p.h; m = p.m }
    else {
      const acum = new Date()
      h = acum.getHours()
      // Pas de 5, in SUS: ora propusa e una care n-a trecut inca.
      m = Math.ceil(acum.getMinutes() / 5) * 5
      if (m >= 60) { m = 0; h = (h + 1) % 24 }
    }
    faza = 'ora'
    open = true
  }

  /** Se scrie la fiecare atingere — alegerea dintr-un set finit E decizia, iar
   *  valoarea se vede pe declansator si se poate schimba din aceeasi foaie. */
  function scrie() {
    if (h === null) return
    value = `${p2(h)}:${p2(m)}`
    onchange?.(value)
  }

  // ===== GEOMETRIA CADRANULUI =====
  //
  // Sistem de coordonate 0..240, scalat de `viewBox` — deci cadranul e la fel pe
  // popoverul de 244px si pe foaia de 390, si nicio valoare de aici nu e in px.
  const C = 120                 // centrul
  const R_EXT = 96              // inelul de afara (1–12, si minutele)
  const R_INT = 62              // inelul de dinauntru (13–00)
  const R_PASTILA = 17          // discul de sub un numar ales

  /** Unghiul unei valori pe un cadran cu `pasi` diviziuni, de la 12 in sus, in radiani. */
  const unghi = (i, pasi) => (i / pasi) * 2 * Math.PI
  const pozitie = (i, pasi, r) => ({
    x: C + r * Math.sin(unghi(i, pasi)),
    y: C - r * Math.cos(unghi(i, pasi)),
  })

  // Orele: 1..12 pe inelul exterior, 13..23 + 00 pe cel interior. Poziţia lui 12 si
  // a lui 00 e aceeasi (sus), pe inele diferite — adica exact ce spune un ceas.
  const ORE_EXT = $derived(Array.from({ length: 12 }, (_, k) => {
    const val = k + 1 === 12 ? 12 : k + 1
    return { val, ...pozitie(k + 1, 12, R_EXT) }
  }))
  const ORE_INT = $derived(Array.from({ length: 12 }, (_, k) => {
    const val = k + 13 === 24 ? 0 : k + 13
    return { val, ...pozitie(k + 1, 12, R_INT) }
  }))
  // Minutele: 12 etichete la pas de 5. Se pot alege si minutele intermediare, prin
  // tragere pe cadran (vezi `dinPunct`) — dar SCRISE sunt doar cele de 5, altfel
  // cadranul ar avea 60 de numere si niciunul citibil.
  const MINUTE = $derived(Array.from({ length: 12 }, (_, k) => ({
    val: k * 5, ...pozitie(k, 12, R_EXT),
  })))

  /** Unde sta capatul acului acum. */
  const ac = $derived.by(() => {
    if (faza === 'minut') return { ...pozitie(m / 5, 12, R_EXT), r: R_EXT }
    if (h === null) return { x: C, y: C - R_EXT, r: R_EXT }
    const interior = h === 0 || h > 12
    const idx = h === 0 ? 12 : (h > 12 ? h - 12 : h)
    const r = interior ? R_INT : R_EXT
    return { ...pozitie(idx, 12, r), r }
  })

  function alegeOra(v) {
    h = v
    scrie()
    // Comutarea la minute e ce face ceasul sa fie doua atingeri, nu doua ecrane.
    faza = 'minut'
  }
  function alegeMinut(v) {
    m = v
    scrie()
    close()
  }

  /** Valoarea de sub un punct de pe cadran — pentru tragere cu degetul.
   *  La minute da pas de 1: cine trage vrea 8:37, cine atinge un numar vrea 8:35. */
  function dinPunct(ev) {
    const svg = ev.currentTarget
    const r = svg.getBoundingClientRect()
    const x = ((ev.clientX - r.left) / r.width) * 240 - C
    const y = ((ev.clientY - r.top) / r.height) * 240 - C
    const raza = Math.hypot(x, y)
    // `atan2(x, -y)`: 0 in sus, crescator spre dreapta — ca pe un ceas.
    let a = Math.atan2(x, -y)
    if (a < 0) a += 2 * Math.PI
    if (faza === 'minut') {
      const v = Math.round((a / (2 * Math.PI)) * 60) % 60
      m = v
      scrie()
      return
    }
    const idx = Math.round((a / (2 * Math.PI)) * 12) || 12
    const interior = raza < (R_EXT + R_INT) / 2
    h = interior ? (idx === 12 ? 0 : idx + 12) : idx
    scrie()
  }

  let trage = $state(false)
  function jos(ev) {
    if (ev.pointerType === 'mouse' && ev.button !== 0) return
    trage = true
    ev.currentTarget.setPointerCapture?.(ev.pointerId)
    dinPunct(ev)
  }
  function misca(ev) { if (trage) dinPunct(ev) }
  function sus(ev) {
    if (!trage) return
    trage = false
    try { ev.currentTarget.releasePointerCapture?.(ev.pointerId) } catch (_) {}
    // Ridicarea degetului INCHEIE pasul: la ora trece la minute, la minute inchide.
    if (faza === 'ora') faza = 'minut'
    else close()
  }

  function acum() {
    const a = new Date()
    h = a.getHours()
    m = a.getMinutes()
    scrie()
    close()
  }

  function scoate() {
    value = ''
    onchange?.('')
    close()
  }

  function close() { open = false }

  const sheet = $derived(ecran.telefon)

  function positionPopup() {
    if (sheet) { popupStyle = ''; return }
    if (!triggerEl || !popupEl) return
    const r = triggerEl.getBoundingClientRect()
    const popupH = popupEl.offsetHeight || 360
    const popupW = popupEl.offsetWidth || 268
    let top = r.bottom + 6
    if (top + popupH > window.innerHeight && r.top - popupH - 6 >= 0) top = r.top - popupH - 6
    let left = r.left
    if (left + popupW > window.innerWidth - 8) left = window.innerWidth - popupW - 8
    if (left < 8) left = 8
    // Acelasi corectiv ca in DatePicker: un stramos cu `transform` devine blocul de
    // referinta al unui `position: fixed`.
    const cb = popupEl.offsetParent
    if (cb) {
      const cbr = cb.getBoundingClientRect()
      top -= cbr.top
      left -= cbr.left
    }
    popupStyle = `top:${Math.round(top)}px; left:${Math.round(left)}px;`
  }

  $effect(() => { if (open && popupEl) positionPopup() })

  // Intra in stiva de modale DOAR ca foaie — regula din DatePicker: ca foaie are
  // voal si trebuie sa fie „varf"; ca popover n-are voal si n-ar avea ce sa preia.
  $effect(() => {
    if (!open || !sheet) return
    nivelNou()
    return () => nivelInchis()
  })

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
</script>

<div class="so">
  {#if label}<span class="so-label">{label}</span>{/if}

  <button type="button" class="so-trigger" class:deschis={open} class:placeholder={!eticheta && !afisat} {disabled}
          bind:this={triggerEl} onclick={deschideCeasul}>
    <span class="so-value">{eticheta || afisat || placeholder}</span>
    <Clock size={16} strokeWidth={1.5} />
  </button>

  {#if open && sheet}
    <!-- Peste o foaie: voal SLAB si fara fade (vezi nota de la `pesteFoaie`).
         Singur pe pagina: voalul intreg, cu fade, ca la calendar. -->
    <div class="so-voal" class:slab={pesteFoaie} use:portal onclick={close} role="presentation"
         transition:fade={{ duration: motionDuration(pesteFoaie ? 0 : DUR_FAST), easing: EASE }}></div>
  {/if}

  {#if open}
    <div class="so-pop" class:sheet use:portal bind:this={popupEl} style={popupStyle} transition:deschide
         use:foaieTrage={{ activ: sheet, laInchidere: () => { open = false } }}>
      {#if sheet}<span class="so-grip" aria-hidden="true"></span>{/if}

      <!-- ANTETUL E SI AFISAJ SI NAVIGATIE: cifra activa spune ce alege cadranul, iar
           cealalta e butonul cu care te intorci. Doua puncte fixe intre ele — nu
           clipesc, ceasul nu e un cronometru. -->
      <div class="so-head">
        <button type="button" class="so-h" class:activ={faza === 'ora'} onclick={() => faza = 'ora'}>
          {h === null ? '--' : p2(h)}
        </button>
        <span class="so-doua">:</span>
        <button type="button" class="so-h" class:activ={faza === 'minut'} onclick={() => faza = 'minut'}>
          {p2(m)}
        </button>
      </div>

      <!-- CADRANUL. `touch-action: none` pe el, ca tragerea sa nu deruleze foaia. -->
      <svg class="so-cadran" viewBox="0 0 240 240" role="application"
           aria-label={faza === 'ora' ? 'Alege ora' : 'Alege minutul'}
           onpointerdown={jos} onpointermove={misca} onpointerup={sus} onpointercancel={sus}>
        <circle class="so-fata" cx={C} cy={C} r="112" />

        <!-- Acul: linia din centru plus discul de la capat. Discul e DESENAT INAINTE
             de numere, ca cifra aleasa sa stea PESTE el si sa se citeasca in cerneala
             de pe fill — nu sub un disc opac. -->
        <line class="so-ac" x1={C} y1={C} x2={ac.x} y2={ac.y} />
        <circle class="so-pivot" cx={C} cy={C} r="3.5" />
        <circle class="so-pastila" cx={ac.x} cy={ac.y} r={R_PASTILA} />

        <!-- CADRANUL E UN INSTRUMENT DE DEGET, si numerele sunt tinte pe
             aceeasi suprafata pe care se trage acul. Nu au drum de tastatura
             si nu li se poate face unul cinstit: 24 de numere in ordinea de
             tabulare ar ingropa butoanele reale de sub cadran. Cine scrie ora
             de la tastatura o face din campul foii, nu de aici. -->
        {#if faza === 'ora'}
          {#each ORE_EXT as o (o.val)}
            <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
            <text class="so-nr" class:sel={h === o.val} x={o.x} y={o.y}
                  onclick={() => alegeOra(o.val)}>{o.val}</text>
          {/each}
          {#each ORE_INT as o (o.val)}
            <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
            <text class="so-nr mic" class:sel={h === o.val} x={o.x} y={o.y}
                  onclick={() => alegeOra(o.val)}>{p2(o.val)}</text>
          {/each}
        {:else}
          {#each MINUTE as o (o.val)}
            <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
            <text class="so-nr" class:sel={m === o.val} x={o.x} y={o.y}
                  onclick={() => alegeMinut(o.val)}>{p2(o.val)}</text>
          {/each}
        {/if}
      </svg>

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
  .so { position: relative; display: flex; flex-direction: column; gap: var(--space-6); width: 100%; }
  .so-label {
    font-size: var(--font-label); font-weight: var(--fw-semibold); color: var(--text-dim);
    text-transform: uppercase; letter-spacing: var(--tracking-label);
  }

  /* A PATRA RETETA DE CAMP A SISTEMULUI, copiata la valoare din `.dp-trigger`.
     Cine o gazduieste intr-un rand de foaie o dezbraca, exact ca la `DatePicker`
     (vezi `.ft-ora` in `FoaieTask.svelte`). */
  .so-trigger {
    display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm);
    min-height: var(--ctrl-lg); padding: var(--space-10) var(--space-12); width: 100%;
    background: var(--bg-elevated); border: none; border-radius: var(--radius-sm);
    box-shadow: inset 0 0 0 1px var(--border);
    color: var(--text); font-size: var(--font-body); font-family: inherit;
    cursor: pointer; text-align: left;
    transition: box-shadow var(--dur-fast) var(--ease);
  }
  .so-trigger:hover:not(:disabled) { box-shadow: inset 0 0 0 1px var(--border-strong); }
  /* SI CAND E DESCHIS, nu doar la focus de tastatura. Declansatorul e un `<button>`,
     iar pe butoane `:focus-visible` NU se aprinde la clic de mouse — deci deschideai
     popoverul si campul ramanea stins, desi el e chiar obiectul deschis. La cinci
     controale care se declara in comentariile lor „acelasi camp al sistemului",
     asta era singura deosebire pe care o vedeai cu ochiul.
     Reteta nu e inventata aici: `Select.svelte:196` o are deja — `:focus, .open`.
     (`Input` si `Textarea` raman pe `:focus` cu buna stiinta: sunt campuri de text,
     unde `:focus-visible` se potriveste oricum la clic, iar `:focus` are un plus —
     aprinde muchia si cand focalizam din cod, cum face foaia de adaugare.) */
  .so-trigger:focus-visible,
  .so-trigger.deschis { outline: none; box-shadow: inset 0 0 0 1.5px var(--accent); }
  .so-trigger:disabled { opacity: .5; cursor: not-allowed; }
  .so-trigger.placeholder .so-value { color: var(--text-dim); }
  .so-trigger :global(svg) { color: var(--text-dim); flex-shrink: 0; }
  .so-value { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .so-trigger:not(.placeholder) .so-value { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

  /* Aceeasi pereche ca la calendar (`.dp-voal` / `.dp-pop`): voalul cu o treapta
     sub popup. Era scrisa de mana ca `--z-modal + 40/41`, adica o a doua scara
     pentru acelasi lucru — si una care se prabusea la al cincilea strat de modal,
     unde `--z-modal + (nivel-1)*10` ajunge tot la 1040. */
  .so-voal { position: fixed; inset: 0; background: var(--scrim); z-index: calc(var(--z-tooltip) - 1); }
  /* Peste o foaie care are deja voal: doar separa. Vezi `--scrim-slab` in tokens.css
     si nota de la `pesteFoaie` in <script>. */
  .so-voal.slab { background: var(--scrim-slab); }

  /* Acelasi motiv ca la `.dp-pop`: stratul pleaca in `<body>` prin `use:portal`,
     deci se compara cu backdropul Modalului (`--z-modal`), nu cu continutul din
     jurul declansatorului. `--z-dropdown` (100) il ingropa sub orice foaie sau
     panou din care e deschis — iar aici era si mai vizibil, fiindca voalul lui
     statea DEASUPRA modalului si popupul dedesubt. */
  .so-pop {
    position: fixed; z-index: var(--z-tooltip);
    width: 268px; padding: var(--space-12);
    background: var(--bg-overlay);
    border-radius: var(--radius-md); box-shadow: var(--shadow-md);
  }

  /* Antetul: treapta de PANOU (21), fiindca cifrele astea sunt titlul foii — ce ai
     ales. Mono si tabular: doua cifre care se schimba sub deget n-au voie sa mute
     doua puncte. */
  .so-head { display: flex; align-items: baseline; justify-content: center; gap: var(--space-2xs); padding: var(--space-2xs) 0 var(--space-10); }
  .so-h {
    font-family: var(--font-mono); font-size: var(--font-h2); font-weight: var(--fw-semibold);
    font-variant-numeric: tabular-nums;
    color: var(--text-dim); background: none; border: none; cursor: pointer;
    padding: var(--space-2xs) var(--space-6); border-radius: var(--radius-xs);
    transition: var(--transition-colors);
  }
  .so-h:hover { color: var(--text-secondary); }
  /* Cifra ACTIVA e cea pe care o alege cadranul. Tenta, nu fill: un fill saturat pe
     o cifra de 21 ar striga mai tare decat cadranul de dedesubt. */
  .so-h.activ { color: var(--accent-deep); background: var(--accent-subtle); }
  .so-doua {
    font-family: var(--font-mono); font-size: var(--font-h2); font-weight: var(--fw-semibold);
    color: var(--text-dim);
  }

  /* CADRANUL. `aspect-ratio: 1` pe latimea disponibila — deci 244px in popover si
     ~358 pe foaie, fara nicio valoare in px aici. */
  .so-cadran {
    display: block; width: 100%; aspect-ratio: 1;
    touch-action: none;             /* tragerea alege ora, nu deruleaza foaia */
    -webkit-user-select: none; user-select: none;
  }
  /* Fata ceasului e suprafata 2 — acelasi ton ca orice camp. Fara chenar: cercul
     insusi e forma, iar o muchie in plus ar fi al doilea contur langa numere. */
  .so-fata { fill: var(--bg-elevated); }
  .so-ac { stroke: var(--accent); stroke-width: 2; }
  .so-pivot { fill: var(--accent); }
  .so-pastila { fill: var(--accent); }

  .so-nr {
    font-family: var(--font-mono);
    font-size: 15px;
    font-weight: var(--fw-medium);
    fill: var(--text-secondary);
    text-anchor: middle;
    dominant-baseline: central;
    cursor: pointer;
  }
  /* Inelul interior (13–00) e mai mic: doua inele de aceeasi greutate s-ar citi ca
     un singur camp de numere, si n-ai mai vedea ca sunt doua scari. */
  .so-nr.mic { font-size: var(--font-small); fill: var(--text-dim); }
  /* Numarul ALES sta peste discul de accent, deci ia cerneala de pe fill. */
  .so-nr.sel { fill: var(--accent-text); font-weight: var(--fw-semibold); }

  .so-foot {
    display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm);
    margin-top: var(--space-10); padding-top: var(--space-10); border-top: 1px solid var(--border);
  }
  .so-foot-btn {
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
  .so-foot-btn:hover { background: color-mix(in oklab, var(--accent) 22%, var(--bg-surface)); }
  .so-foot-btn.clear { color: var(--danger); background: transparent; }
  .so-foot-btn.clear:hover { color: var(--danger-deep); background: var(--danger-subtle); }

  /* ===== Telefon: ceasul e foaie, cu un cadran cat latimea ecranului ===== */
  .so-pop.sheet {
    position: fixed; left: 0; right: 0; bottom: 0; top: auto;
    width: auto; max-height: 92dvh; overflow-y: auto;
    padding: var(--space-6) var(--space-lg) calc(var(--space-md) + var(--safe-bottom));
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    box-shadow: var(--shadow-foaie);
    background: var(--bg-surface);
    /* z-indexul vine din `.so-pop`: e acelasi strat, doar alta forma. */
  }
  /* Manerul: acelasi obiect ca al foii din `Modal` — 38×4, `--border-strong`. */
  /* Manerul e SEMN, nu tinta: gestul asculta pe toata banda de sus a foii (vezi
     `lib/foaieTrage.js`). Aceeasi lectie ca la Modal — Ion: „de TOT ANTETUL, nu de
     bara de 4px". */
  .so-grip {
    pointer-events: none;
    display: block; width: 38px; height: 4px; margin: var(--space-sm) auto var(--space-2xs);
    border-radius: var(--radius-full); background: var(--border-strong);
  }
  @media (max-width: 768px) {
    .so-trigger { min-height: var(--tap-sheet); }
    /* SUBSOLUL SE INGROASA CA IN CALENDAR. Antetul componentei spune ca toata
       carcasa e „copiata la valoare din `DatePicker.svelte`" — subsolul era singura
       piesa la care copierea s-a oprit: intr-o FOAIE de telefon, „Acum" si „Scoate
       ora" ramaneau la ~26px, sub `--tap-min`. Perechea din calendar e
       `DatePicker.svelte:347`. `:only-child` fiindca „Scoate ora" dispare cand n-ai
       ora pusa, exact ca „Sterge". */
    .so-pop.sheet .so-foot-btn {
      flex: 1; justify-content: center; min-height: var(--tap-min);
      font-size: var(--font-small); border-radius: var(--radius-md);
    }
    .so-pop.sheet .so-foot-btn:only-child { flex: 0 1 160px; }
    /* Pe un cadran de ~358px numerele cresc odata cu el: la 15px pe SVG scalat ar
       iesi ~22px reali pe inelul de afara. Nu se mai ating, deci nu mai e nevoie de
       nimic in plus — dar acul se ingroasa, ca sa rămână in proporţie. */
    .so-ac { stroke-width: 2.5; }
  }
</style>
