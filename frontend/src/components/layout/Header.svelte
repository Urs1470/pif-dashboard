<script>
  import { Sun, Moon, Monitor, Check, Search } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import { ui } from '../../stores/ui.svelte.js'
  import { ecran } from '../../lib/ecran.svelte.js'
  import { tema, setMod } from '../../lib/tema.svelte.js'
  import { motionDuration, DUR_BASE, EASE } from '../../lib/motion.svelte.js'

  let { deschideCautarea = () => {} } = $props()

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

  function alege(mod) {
    setMod(mod)
    meniuDeschis = false
  }

  function inafara(nod) {
    const pe = (e) => { if (!nod.contains(e.target)) meniuDeschis = false }
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

<header class="header">
  <a href="/" class="brand" title="PIF Dashboard">
    <!-- Marca: aceleasi coordonate ca `frontend/public/favicon.svg`. Tila ia
         accentul, cerneala ia `--accent-text` — deci urmeaza tema, spre deosebire
         de fisierul .svg, care e un asset si nu stie de ea. -->
    <svg class="brand-tile" width="26" height="26" viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="var(--accent)" />
      <path d="M14 48 C27 48 30 40 33 30 S42 16 50 16 L50 48 Z" fill="var(--accent-text)" opacity="0.3" />
      <path d="M14 48 C27 48 30 40 33 30 S42 16 50 16" fill="none" stroke="var(--accent-text)"
            stroke-width="5.5" stroke-linecap="round" />
      <circle cx="50" cy="16" r="5" fill="var(--accent-text)" />
    </svg>
    <span class="brand-name">PIF Dashboard</span>
  </a>

  {#if ui.pageHeader.title}
    <div class="header-context">
      <h1 class="hc-title">{ui.pageHeader.title}</h1>
      {#if ui.pageHeader.subtitle}<span class="hc-sub">{ui.pageHeader.subtitle}</span>{/if}
    </div>
  {/if}

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
      {#if meniuDeschis}
        <div class="tema-meniu" role="menu"
             transition:fly={{ y: -4, duration: motionDuration(DUR_BASE), easing: EASE }}>
          {#each MODURI as m (m.mod)}
            <button class="tema-rand" class:activ={tema.mod === m.mod} role="menuitemradio"
                    aria-checked={tema.mod === m.mod} onclick={() => alege(m.mod)}>
              <m.Ico size={16} strokeWidth={1.5} />
              {m.eticheta}
              {#if tema.mod === m.mod}<Check size={15} strokeWidth={1.5} class="tema-bifa" />{/if}
            </button>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</header>

<style>
  .header {
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
    letter-spacing: -0.015em;
    color: var(--text);
    white-space: nowrap;
  }
  .brand-tile { flex: none; display: block; }

  .header-context {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: baseline;
    gap: 10px;
    max-width: 56%;
    pointer-events: none;
    white-space: nowrap;
  }
  .hc-title {
    font-weight: var(--fw-semibold);
    font-size: var(--font-h3);
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .hc-sub {
    font-size: var(--font-small);
    color: var(--text-dim);
    text-transform: capitalize;
    flex-shrink: 0;
  }

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

  @media (max-width: 768px) {
    .header-context { display: none; }
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
