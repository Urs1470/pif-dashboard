<script>
  // COMUTATORUL DE TEMA, INTR-UN SINGUR LOC.
  //
  // Traia in `Header.svelte`. De cand pe desktop antetul nu mai exista — marca,
  // tema si starea retelei au urcat in bara laterala — ar fi trebuit scris a
  // doua oara acolo. Doua copii ale aceluiasi meniu inseamna ca a treia stare
  // („Sistem") se poate adauga intr-una si uita in cealalta, iar nimic nu
  // semnaleaza. Deci componenta, nu copie.
  //
  // Ce NU s-a schimbat la mutare: trei stari, trei randuri — nu un buton care
  // cicleaza. Cu doua stari un comutator care „arata unde ajungi" mergea; cu
  // trei nu se mai poate ghici, fiindca o iconita de monitor poate insemna si
  // „acum e automat" si „urmatorul e automat". Un meniu spune toate trei
  // deodata si o bifeaza pe cea curenta.
  import { Sun, Moon, Monitor, Check } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import { ecran } from '../../lib/ecran.svelte.js'
  import { tema, setMod } from '../../lib/tema.svelte.js'
  import { motionDuration, DUR_BASE, EASE } from '../../lib/motion.svelte.js'

  // `varianta` schimba DOAR declansatorul, nu meniul:
  //  - 'buton' — patratul din antetul de telefon;
  //  - 'rand'  — randul de latimea barei laterale, in rand cu rutele de deasupra.
  // `sens` spune incotro se deschide meniul de desktop: din bara laterala, care
  // sta jos, in sus; de sub un buton de antet, in jos.
  let { varianta = 'buton', sens = 'jos' } = $props()

  const MODURI = [
    { mod: 'auto', eticheta: 'Sistem', Ico: Monitor },
    { mod: 'light', eticheta: 'Deschis', Ico: Sun },
    { mod: 'dark', eticheta: 'Întunecat', Ico: Moon },
  ]
  const IcoCurenta = $derived(
    tema.mod === 'auto' ? Monitor : tema.mod === 'light' ? Sun : Moon
  )
  const eticheta = $derived(MODURI.find((m) => m.mod === tema.mod)?.eticheta ?? 'Temă')

  let meniuDeschis = $state(false)

  // FOAIA SE INCARCA LENES, SI NU DIN ELEGANTA.
  //
  // Componenta traieste in cadrul permanent al aplicatiei, deci tot ce importa
  // ea STATIC ajunge in chunk-ul preincarcat la pornire. Cu `import Modal from
  // …` scris normal, Rollup a mutat foaia (~80kB) langa `api`, adica exact in ce
  // se descarca si se parseaza inainte de primul cadru.
  //
  // Masurat cu `scripts/audit_navigare.py`: pastila navigatiei nu mai apuca sa
  // plece din slotul vechi pana la 90ms — adica se rupea contractul „schimbarea
  // de tab ALUNECA, nu sare", pe o pagina care n-are nicio legatura cu meniul de
  // tema. Un contract nu se strica intotdeauna de acolo de unde ai scris.
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

<div class="tema-wrap" class:rand={varianta === 'rand'} use:inafara>
  {#if varianta === 'rand'}
    <button class="tema-trig-rand" class:deschis={meniuDeschis}
            onclick={() => (meniuDeschis = !meniuDeschis)}
            aria-haspopup="menu" aria-expanded={meniuDeschis}>
      <IcoCurenta size={18} strokeWidth={1.5} />
      <span class="tt-et">{eticheta}</span>
    </button>
  {:else}
    <button class="h-btn" class:deschis={meniuDeschis}
            onclick={() => (meniuDeschis = !meniuDeschis)}
            aria-haspopup="menu" aria-expanded={meniuDeschis} aria-label="Temă" title="Temă">
      <IcoCurenta size={17} strokeWidth={1.5} />
    </button>
  {/if}

  <!-- PE TELEFON MENIUL E O FOAIE, NU UN DROPDOWN. Randuri de 38px agatate de
       coltul din dreapta sus, sub degetul care le acopera — vezi foaia de mai
       jos, si aceeasi schimbare la sortarea din Proiecte. -->
  {#if meniuDeschis && !ecran.telefon}
    <div class="tema-meniu" class:sus={sens === 'sus'} role="menu" tabindex="-1" onkeydown={navMeniu}
         transition:fly={{ y: sens === 'sus' ? 4 : -4, duration: motionDuration(DUR_BASE), easing: EASE }}>
      {@render moduriTema()}
    </div>
  {/if}
</div>

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
  .tema-wrap { position: relative; display: inline-flex; }
  .tema-wrap.rand { display: block; }

  /* Declansatorul din ANTET: patratul de 38px (`--ctrl-md`), ca celelalte actiuni globale. */
  .h-btn {
    width: var(--ctrl-md);
    height: var(--ctrl-md);
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

  /* Declansatorul din BARA LATERALA: acelasi rand ca rutele de deasupra —
     aceeasi inaltime, acelasi gol intre iconita si text, aceeasi raza. Altfel
     piciorul barei ar arata ca alta componenta lipita dedesubt. */
  .tema-trig-rand {
    display: flex;
    align-items: center;
    gap: var(--space-10);
    width: 100%;
    height: var(--ctrl-md);
    padding: 0 var(--space-10);
    border-radius: var(--radius-sm);
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: var(--font-small);
    font-weight: var(--fw-medium);
    text-align: left;
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .tema-trig-rand:hover { background: var(--bg-hover); color: var(--text); }
  .tema-trig-rand.deschis { background: var(--accent-subtle); color: var(--accent-deep); }
  .tt-et { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .tema-meniu {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    width: 190px;
    padding: var(--space-6);
    border-radius: var(--radius-md);
    background: var(--bg-overlay);
    box-shadow: var(--shadow-md);
    display: flex;
    flex-direction: column;
    gap: var(--space-2xs);
    z-index: var(--z-dropdown);
  }
  /* Din piciorul barei laterale meniul iese IN SUS si aliniat la STANGA: in jos
     n-are unde, iar la dreapta ar iesi din bara peste continut. */
  .tema-meniu.sus {
    top: auto;
    bottom: calc(100% + 8px);
    right: auto;
    left: 0;
    width: 100%;
    min-width: 176px;
  }
  .tema-rand {
    display: flex;
    align-items: center;
    gap: var(--space-10);
    height: var(--ctrl-md);
    padding: 0 var(--space-10);
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
  .tema-foaie { display: flex; flex-direction: column; gap: var(--space-2xs); margin: 0 calc(var(--space-md) * -1 + var(--space-xs)); }
  .tema-foaie .tema-rand { height: var(--tap-sheet); padding: 0 var(--space-12); }
  .tema-foaie .tema-rand:active { background: var(--bg-active); }

  @media (max-width: 768px) {
    .h-btn { width: var(--tap-min); height: var(--tap-min); }
    .tema-rand { height: var(--tap-sheet); }
  }
</style>
