<script>
  import { onMount } from 'svelte'
  import { Search } from '@lucide/svelte'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { router, link } from '../../lib/router.svelte.js'

  // Vizibilitate dock:
  //  - DESKTOP (autohide v4): ascuns by default; apare DOAR cat timp cursorul e
  //    impins in marginea de jos (unde sta dock-ul) si se ascunde cand iesi.
  //    Manerul "peek" ramane vizibil ca linie de prezenta.
  //  - MOBIL (cerinta Ion): dock FIX, mereu vizibil, FARA autohide. Se ascunde
  //    doar cat timp tastatura e deschisa (focus pe camp), ca sa nu pluteasca
  //    peste ea.
  let hidden = $state(true)
  let kbLocked = $state(false)
  let isMobile = $state(false)
  let peekTimer = 0

  // Nota (desktop): NU ascundem la schimbarea rutei — cursorul ramane jos dupa
  // click pe un tab, deci un hide pe ruta ar produce flicker.

  // mobil: dock-ul e deja fix; pe desktop, tap pe maner -> apare temporar ~4s
  function revealFromPeek() {
    if (kbLocked || isMobile) return
    hidden = false
    clearTimeout(peekTimer)
    peekTimer = setTimeout(() => { hidden = true }, 4000)
  }

  onMount(() => {
    let inZone = false
    // Desktop: cursorul in banda de jos -> apare. Prag ridicat de la 6px la 48px
    // (cerut de Ion): la 6px trebuia sa ajungi in taskbar-ul Windows si dadeai peste
    // el din inertie; la 48px dock-ul apare inainte sa atingi marginea sistemului.
    const REVEAL_EDGE = 48  // px de la marginea de jos -> apare
    const HIDE_ZONE = 150   // px: odata aparut, se ascunde cand treci peste atat

    const mq = window.matchMedia('(pointer: coarse)')
    const computeMobile = () => { isMobile = mq.matches || window.innerWidth <= 768 }
    computeMobile()

    const apply = () => {
      // Mobil: fix (vizibil), ascuns doar cu tastatura deschisa.
      // Desktop: cursor-driven.
      hidden = isMobile ? kbLocked : (kbLocked ? true : !inZone)
    }

    let mmTick = 0
    function onMove(e) {
      if (isMobile) return
      const now = performance.now()
      if (now - mmTick < 16) return
      mmTick = now
      const fromBottom = window.innerHeight - e.clientY
      if (inZone) {
        if (fromBottom > HIDE_ZONE) inZone = false
      } else if (fromBottom <= REVEAL_EDGE) {
        inZone = true
      }
      apply()
    }

    function onResize() { computeMobile(); apply() }

    // tastatura mobila: focus pe camp editabil -> dock blocat ascuns
    const isEditable = (el) => !!el && (el.matches?.('input, textarea, select') || el.closest?.('[contenteditable="true"]'))
    function onFocusIn(e) {
      if (!isMobile || !isEditable(e.target)) return
      kbLocked = true
      apply()
    }
    function onFocusOut() {
      if (!kbLocked) return
      setTimeout(() => {
        if (isEditable(document.activeElement)) return
        kbLocked = false
        apply()
      }, 120)
    }

    apply()  // stare initiala (pe mobil -> vizibil)

    mq.addEventListener?.('change', onResize)
    window.addEventListener('resize', onResize, { passive: true })
    window.addEventListener('mousemove', onMove, { passive: true })
    document.addEventListener('focusin', onFocusIn)
    document.addEventListener('focusout', onFocusOut)
    return () => {
      clearTimeout(peekTimer)
      mq.removeEventListener?.('change', onResize)
      window.removeEventListener('resize', onResize)
      window.removeEventListener('mousemove', onMove)
      document.removeEventListener('focusin', onFocusIn)
      document.removeEventListener('focusout', onFocusOut)
    }
  })

  const items = [
    { path: '/', label: 'Acasă', icon: 'home' },
    { path: '/projects', label: 'Proiecte', icon: 'projects' },
    { path: '/tasks', label: 'Taskuri', icon: 'tasks' },
    { path: '/plan', label: 'Planificator', icon: 'plan' },
    { path: '/calendar', label: 'Calendar', icon: 'calendar' },
    // Langa Calendar, nu la coada: dupa „unde sunt eu" urmeaza imediat „cine e unde".
    { path: '/departament', label: 'Departament', icon: 'departament' },
    { path: '/calculator', label: 'Calculator', icon: 'calculator' },
  ]

  function isActive(path) {
    if (path === '/') return router.path === '/'
    return router.path.startsWith(path)
  }

  function openSearch() {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true }))
  }
</script>

<nav class="dock" class:hidden aria-label="Navigație principală">
  <button class="dock-grip" aria-label="Arată navigația" title="Navigație" onclick={revealFromPeek}></button>
  {#each items as item (item.path)}
    <a
      href={item.path}
      use:link
      onclick={(e) => e.currentTarget.blur()}
      class="dock-item"
      class:active={isActive(item.path)}
      aria-current={isActive(item.path) ? 'page' : undefined}
      aria-label={item.label}
      title={item.label}
    >
      <SolidIcon name={item.icon} size={20} />
    </a>
  {/each}
  <span class="sep" aria-hidden="true"></span>
  <button class="dock-item" onclick={openSearch} aria-label="Caută (Ctrl+K)" title="Caută (Ctrl+K)">
    <Search size={20} />
  </button>
</nav>

<style>
  .dock {
    position: fixed;
    left: 50%;
    bottom: calc(14px + var(--safe-bottom));
    transform: translateX(-50%) translateY(var(--dock-shift, 0px));
    transition: transform var(--dur-base) var(--ease);
    display: flex;
    gap: 4px;
    padding: 12px 8px 8px;
    border-radius: var(--radius-xl);
    z-index: var(--z-sticky);
    background: color-mix(in srgb, var(--bg-surface) 85%, transparent);
    border: 1px solid var(--border-strong);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    box-shadow: var(--shadow-lg);
  }

  .dock-item {
    width: 50px;
    height: 50px;
    border-radius: 16px;
    color: var(--text-faint);
    display: grid;
    place-items: center;
    cursor: pointer;
    background: transparent;
    border: none;
    transition: color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease),
      transform var(--dur-fast) var(--ease);
  }
  /* Ridicarea e un raspuns la cursor. Pe touch ramanea ridicata tableta atinsa
     ultima data, deci dock-ul arata mereu ca si cum ai fi peste un alt tab decat
     cel activ. */
  @media (hover: hover) {
    .dock-item:hover {
      color: var(--text);
      transform: translateY(-4px);
    }
  }
  .dock-item:active { color: var(--text); background: var(--bg-hover); }
  .dock-item.active:active { background: var(--accent); }
  .dock-item.active {
    color: var(--accent-text);
    background: var(--accent);
  }
  .dock-item.active:hover {
    transform: none;
  }

  /* Ascuns: dock-ul coboara pana ramane vizibil doar manerul-linie de sus.
     Manerul e copil al dock-ului, deci urca/coboara IMPREUNA cu el. */
  .dock.hidden {
    --dock-shift: calc(100% + 6px);
  }

  .sep {
    width: 1px;
    background: var(--border-strong);
    margin: 10px 6px;
  }

  /* Manerul-linie (prezenta dock-ului). Absolut pe dock -> se misca cu dock-ul. */
  .dock-grip {
    position: absolute;
    top: 3px;
    left: 50%;
    transform: translateX(-50%);
    width: 48px;
    height: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    background: none;
    border: none;
    cursor: pointer;
  }
  .dock-grip::before {
    content: '';
    width: 30px;
    height: 3px;
    border-radius: var(--radius-full);
    background: var(--border-strong);
    box-shadow: 0 1px 5px rgba(0, 0, 0, 0.4);
    transition: background var(--dur-fast) var(--ease), width var(--dur-fast) var(--ease);
  }
  .dock-grip:hover::before,
  .dock-grip:focus-visible::before {
    background: var(--accent);
    width: 38px;
  }

  /* Pe touch dock-ul e fix (mereu vizibil) -> manerul de "peek" nu mai are rost.
     Conditia de latime o dubleaza pe cea de pointer fiindca JS-ul de mai sus
     considera „mobil" si o fereastra ingusta cu mouse (`innerWidth <= 768`): fara
     ea, acolo dock-ul era fix dar manerul continua sa se ofere sa-l arate. */
  @media (pointer: coarse), (max-width: 768px) {
    .dock-grip { display: none; }
    .dock { padding-top: 8px; }
  }

  /* Opt tinte (7 tab-uri + cautare) intr-un ecran de 375px: 8 × 44 = 352px, iar cu
     `gap: 2px` + padding + separator nu incapeau si tabletele scadeau la 40×42.
     Spatiul dintre ele NU e ce face tinta mai sigura — marimea ei e. Deci scot
     spatiile si separatorul si dau fiecarui tab caseta intreaga de 44: lipite, dar
     fara zona moarta intre ele. Pastila ambar a tabului activ ramane inseta, deci
     vizual randul arata la fel de aerisit. */
  @media (max-width: 560px) {
    .dock {
      gap: 0;
      padding: 8px 2px;
      max-width: calc(100vw - 12px);
    }
    .dock-item {
      width: var(--tap-min);
      height: var(--tap-min);
      border-radius: 14px;
    }
    .sep { display: none; }
  }
</style>
