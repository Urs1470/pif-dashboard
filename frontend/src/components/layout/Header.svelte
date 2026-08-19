<script>
  import { Sun, Moon, Monitor, Check, Search } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import { ecran } from '../../lib/ecran.svelte.js'
  import { tema, setMod } from '../../lib/tema.svelte.js'
  import { motionDuration, DUR_BASE, EASE } from '../../lib/motion.svelte.js'

  let { deschideCautarea = () => {} } = $props()

  // CAT E DE INALT ANTETUL, ca fapt disponibil in CSS.
  //
  // Pe telefon nu e o constanta: regula are `height: auto`, `min-height` si
  // `flex-wrap: wrap`, deci bara se poate rupe pe doua randuri, iar decupajul
  // ecranului (`--safe-top`) intra si el in padding. Cine are nevoie de
  // marginea ei de JOS nu o poate calcula din tokenuri fara sa se insele.
  //
  // Are nevoie arcul de trage-sa-reincarci: el porneste ascuns exact sub
  // antet si iese de acolo odata cu degetul. Inainte pornea de la 6px si urca
  // PESTE titlu — un disc care traverseaza un text viu.
  //
  // Se scrie pe <html>, ca `--nav-sens` (App) si `--kb` (Modal): acelasi tipar,
  // un singur scriitor per variabila.
  let inaltime = $state(0)
  $effect(() => {
    document.documentElement.style.setProperty('--h-antet', inaltime + 'px')
  })

  // TREI STARI, TREI RANDURI — nu un buton care cicleaza.
  //
  // Cu doua stari, un comutator care „arata unde ajungi" mergea. Cu trei nu se
  // mai poate ghici: o iconita de monitor poate insemna si „acum e automat" si
  // „urmatorul e automat", iar ca sa afli care trebuie sa apesi si sa vezi ce se
  // intampla. Un meniu spune toate trei deodata si o bifeaza pe cea curenta.
  const MODURI = [
    { mod: 'auto', eticheta: 'Sistem', Ico: Monitor },
    { mod: 'light', eticheta: 'Deschis', Ico: Sun },
    { mod: 'dark', eticheta: 'Întunecat', Ico: Moon },
  ]
  const IcoCurenta = $derived(
    tema.mod === 'auto' ? Monitor : tema.mod === 'light' ? Sun : Moon
  )

  let meniuDeschis = $state(false)

  // FOAIA SE INCARCA LENES, SI NU DIN ELEGANTA.
  //
  // `Header` traieste in cadrul permanent al aplicatiei, deci tot ce importa el
  // STATIC ajunge in chunk-ul preincarcat la pornire. Cu `import Modal from …`
  // scris normal, Rollup a mutat foaia (~80kB) langa `api`, adica exact in ce se
  // descarca si se parseaza inainte de primul cadru.
  //
  // Masurat cu `scripts/audit_navigare.py`: pastila dockului nu mai apuca sa
  // plece din slotul vechi pana la 90ms — adica se rupea contractul „schimbarea
  // de tab ALUNECA, nu sare", pe o pagina care n-are nicio legatura cu meniul de
  // tema. Un contract nu se strica intotdeauna de acolo de unde ai scris.
  //
  // Meniul de tema se deschide rar, si pana atunci foaia e oricum in cache: orice
  // ruta cu un modal a incarcat-o deja.
  let FoaieMeniu = $state(null)
  $effect(() => {
    if (!meniuDeschis || !ecran.telefon || FoaieMeniu) return
    import('../ui/Modal.svelte').then((m) => { FoaieMeniu = m.default })
  })

  function alege(mod) {
    setMod(mod)
    meniuDeschis = false
  }

  function navMeniu(e) {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
    e.preventDefault()
    const items = [...e.currentTarget.querySelectorAll('[role="menuitemradio"]')]
    const cur = items.indexOf(document.activeElement)
    const next = e.key === 'ArrowDown'
      ? (cur + 1) % items.length
      : (cur - 1 + items.length) % items.length
    items[next]?.focus()
  }

  function inafara(nod) {
    // Pe telefon meniul e o FOAIE, cu voalul ei — inchiderea vine de acolo, iar
    // regula de aici ar inchide-o la orice atingere in ea: foaia se randeaza in
    // `body` (portal), deci e „in afara" declansatorului.
    const pe = (e) => { if (!ecran.telefon && !nod.contains(e.target)) meniuDeschis = false }
    const esc = (e) => { if (e.key === 'Escape') meniuDeschis = false }
    document.addEventListener('pointerdown', pe)
    document.addEventListener('keydown', esc)
    return {
      destroy() {
        document.removeEventListener('pointerdown', pe)
        document.removeEventListener('keydown', esc)
      },
    }
  }
</script>

<header class="header" bind:clientHeight={inaltime}>
  <a href="/" class="brand" title="TORQA">
    <!-- Marca „Unda" — semnal dreptunghiular (PWM). Aceleasi coordonate ca
         `frontend/public/favicon.svg`, dar aici tila ia `--accent` si cerneala
         `--accent-text`, deci marca URMEAZA TEMA; fisierul .svg e un asset si
         nu stie de tokenuri, deci acolo hexul e scris. Grosimea e 6.4 la 26px
         randati (fata de 5.6 pe tile-ul de asset si 7 pe favicon): traseul se
         ingroasa pe masura ce marca se micsoreaza, altfel se stinge. -->
    <svg class="brand-tile" width="26" height="26" viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="var(--accent)" />
      <path d="M10 42 H21.5 V22 H32 V42 H42.5 V22 H54" fill="none" stroke="var(--accent-text)"
            stroke-width="6.4" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
    <span class="brand-name">TORQA</span>
  </a>

  <!-- `.header-context` (titlul paginii in bara) A PLECAT: era singurul titlu
       care nu statea in pagina — „sus pe mijloc", la alta inaltime decat restul,
       si invizibil pe telefon. Acum FIECARE ruta isi scrie h1-ul in continut,
       in aceeasi pozitie; bara tine doar marca si actiunile globale. -->
  <span class="h-spacer"></span>

  <div class="header-actions">
    <!-- CAUTAREA TRAIESTE INTR-UN SINGUR LOC: in dock.
         Pe telefon dock-ul nu o are (cele patru sloturi plus „Mai mult" sunt
         pline), deci acolo — si numai acolo — ramane in cap. -->
    {#if ecran.telefon}
      <button class="h-btn" onclick={deschideCautarea} aria-label="Caută" title="Caută">
        <Search size={17} strokeWidth={1.5} />
      </button>
    {/if}

    <div class="tema-wrap" use:inafara>
      <button class="h-btn" class:deschis={meniuDeschis}
              onclick={() => (meniuDeschis = !meniuDeschis)}
              aria-haspopup="menu" aria-expanded={meniuDeschis} aria-label="Temă" title="Temă">
        <IcoCurenta size={17} strokeWidth={1.5} />
      </button>
      <!-- PE TELEFON MENIUL E O FOAIE, NU UN DROPDOWN. Randuri de 38px agatate
           de coltul din dreapta sus, sub degetul care le acopera — vezi foaia
           de mai jos, si aceeasi schimbare la sortarea din Proiecte. -->
      {#if meniuDeschis && !ecran.telefon}
        <div class="tema-meniu" role="menu" tabindex="-1" onkeydown={navMeniu}
             transition:fly={{ y: -4, duration: motionDuration(DUR_BASE), easing: EASE }}>
          {@render moduriTema()}
        </div>
      {/if}
    </div>
  </div>
</header>

{#snippet moduriTema()}
  {#each MODURI as m (m.mod)}
    <button class="tema-rand" class:activ={tema.mod === m.mod} role="menuitemradio"
            aria-checked={tema.mod === m.mod} onclick={() => alege(m.mod)}>
      <m.Ico size={16} strokeWidth={1.5} />
      {m.eticheta}
      {#if tema.mod === m.mod}<Check size={15} strokeWidth={1.5} class="tema-bifa" />{/if}
    </button>
  {/each}
{/snippet}

{#if ecran.telefon && FoaieMeniu}
  <FoaieMeniu bind:open={meniuDeschis} title="Temă" iesireGest>
    <div class="tema-foaie" role="menu" tabindex="-1" onkeydown={navMeniu}>{@render moduriTema()}</div>
  </FoaieMeniu>
{/if}

<style>
  .header {
    /* CADRUL NU CLIPESTE CAND SE SCHIMBA CONTINUTUL.
       Fara nume propriu, bara intra in instantaneul `root` al tranzitiei de
       ruta — deci se stingea si se reaprindea la fiecare schimbare de tab, si
       lua si cei ±10px de alunecare, desi e identica inainte si dupa. Cu nume,
       browserul o trateaza ca element persistent: ramane pe loc, iar
       cross-fadeul e doar pe ce se schimba efectiv, adica pagina.
       Pe iOS bara de navigatie nu se misca niciodata cand schimbi tabul; asta
       e perechea ei pe web. */
    view-transition-name: cadru-antet;
    height: var(--header-height);
    /* FARA BLUR. Bara statea pe `backdrop-filter: blur(14px)` peste un fond
       semi-transparent, deci continutul care trecea pe sub ea se vedea ca o pata
       care se misca — pe o pagina cu carduri albe, exact acolo unde te uiti
       intai. Suprafata e opaca; separarea o face linia de jos. */
    background: var(--bg);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-lg);
    position: sticky;
    top: 0;
    z-index: var(--z-sticky);
  }

  /* Marca: un singur font, o greutate, fara separator. 18px e singura treapta
     din afara scarii de text — e logotip, nu continut. */
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: var(--fw-semibold);
    font-size: var(--font-brand);
    letter-spacing: var(--tracking-tight);
    color: var(--text);
    white-space: nowrap;
  }
  .brand-tile { flex: none; display: block; }

  .h-spacer { flex: 1; }

  .header-actions {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .h-btn {
    width: 36px;
    height: 36px;
    display: grid;
    place-items: center;
    border-radius: var(--radius-sm);
    background: var(--bg-surface);
    box-shadow: var(--shadow-sm);
    color: var(--text-secondary);
    transition: var(--transition-pressable);
  }
  .h-btn:hover { color: var(--text); }
  .h-btn:active { transform: scale(var(--press-scale)); }
  /* Deschis = tenta de accent cu cerneala ADANCA, niciodata accentul plin peste
     tenta lui (ar fi acelasi ton pe acelasi ton). */
  .h-btn.deschis { background: var(--accent-subtle); color: var(--accent-deep); box-shadow: none; }

  .tema-wrap { position: relative; display: inline-flex; }
  .tema-meniu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    width: 190px;
    padding: 6px;
    border-radius: var(--radius-md);
    background: var(--bg-overlay);
    box-shadow: var(--shadow-md);
    display: flex;
    flex-direction: column;
    gap: 2px;
    z-index: var(--z-dropdown);
  }
  .tema-rand {
    display: flex;
    align-items: center;
    gap: 10px;
    height: 38px;
    padding: 0 10px;
    border-radius: var(--radius-sm);
    font-size: var(--font-body);
    font-weight: var(--fw-medium);
    color: var(--text-secondary);
    text-align: left;
    transition: var(--transition-colors);
  }
  .tema-rand:hover { background: var(--bg-hover); color: var(--text); }
  .tema-rand.activ {
    background: var(--accent-subtle);
    color: var(--accent-deep);
    font-weight: var(--fw-semibold);
  }
  .tema-rand :global(.tema-bifa) { margin-left: auto; }

  /* Aceleasi trei randuri, pe foaie: 38px -> `--tap-sheet`, si de la o margine la
     alta (marginile negative anuleaza padding-ul lateral al foii). O tinta care
     se opreste la 16px de marginea ecranului rateaza degetul mare. */
  .tema-foaie { display: flex; flex-direction: column; gap: 2px; margin: 0 calc(var(--space-md) * -1 + 4px); }
  .tema-foaie .tema-rand { height: var(--tap-sheet); padding: 0 var(--space-12); }
  .tema-foaie .tema-rand:active { background: var(--bg-active); }

  @media (max-width: 768px) {
    .header {
      flex-wrap: wrap;
      height: auto;
      min-height: var(--header-height);
      gap: var(--space-xs);
      padding-top: calc(var(--space-xs) + var(--safe-top));
      padding-bottom: var(--space-xs);
      padding-left: calc(var(--space-md) + var(--safe-left));
      padding-right: calc(var(--space-md) + var(--safe-right));
    }
    .brand { min-height: var(--tap-min); }
    .h-btn { width: var(--tap-min); height: var(--tap-min); }
    .tema-rand { height: var(--tap-sheet); }
  }
</style>
