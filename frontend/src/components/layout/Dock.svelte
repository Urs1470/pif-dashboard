<script>
  import { onMount } from 'svelte'
  import { Search } from '@lucide/svelte'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { router, link } from '../../lib/router.svelte.js'

  // Autohide v4 (cerinta Ion): dock-ul e ASCUNS by default tot timpul; apare
  // DOAR cat timp cursorul e in zona de jos (unde sta dock-ul) si se ascunde
  // imediat ce iesi cu cursorul. Nu depinde de scroll deloc. Pe mobil (fara
  // cursor) manerul "peek" il aduce temporar (tap -> apare ~4s).
  // Cat timp tastatura mobila e deschisa (focus pe camp) dock + peek stau ascunse.
  let hidden = $state(true)
  let kbLocked = $state(false)
  let peekTimer = 0

  // ruta noua -> revine la "ascuns" (cursorul il re-arata daca e jos)
  $effect(() => {
    router.path
    if (!kbLocked) hidden = true
  })

  // mobil: tap pe maner -> apare temporar, apoi se ascunde singur
  function revealFromPeek() {
    if (kbLocked) return
    hidden = false
    clearTimeout(peekTimer)
    peekTimer = setTimeout(() => { hidden = true }, 4000)
  }

  onMount(() => {
    let inZone = false
    // Nu se ridica la orice atingere: trebuie sa IMPINGI cursorul pana la
    // marginea de jos (un mic "push"). Histereza: odata aparut, ramane cat
    // esti in zona lui si se ascunde doar cand pleci sus peste HIDE_ZONE.
    const REVEAL_EDGE = 6   // px de la marginea de jos -> apare (push pe margine)
    const HIDE_ZONE = 110   // px: odata aparut, se ascunde cand treci peste atat

    const apply = () => { hidden = kbLocked ? true : !inZone }

    let mmTick = 0
    function onMove(e) {
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

    // tastatura mobila: focus pe camp editabil -> dock blocat ascuns
    const isMobileLike = () => window.matchMedia('(pointer: coarse)').matches || window.innerWidth <= 768
    const isEditable = (el) => !!el && (el.matches?.('input, textarea, select') || el.closest?.('[contenteditable="true"]'))
    function onFocusIn(e) {
      if (!isMobileLike() || !isEditable(e.target)) return
      kbLocked = true
      inZone = false
      hidden = true
    }
    function onFocusOut() {
      if (!kbLocked) return
      setTimeout(() => {
        if (isEditable(document.activeElement)) return
        kbLocked = false
      }, 120)
    }

    window.addEventListener('mousemove', onMove, { passive: true })
    document.addEventListener('focusin', onFocusIn)
    document.addEventListener('focusout', onFocusOut)
    return () => {
      clearTimeout(peekTimer)
      window.removeEventListener('mousemove', onMove)
      document.removeEventListener('focusin', onFocusIn)
      document.removeEventListener('focusout', onFocusOut)
    }
  })

  const items = [
    { path: '/', label: 'Acasă', icon: 'home' },
    { path: '/projects', label: 'Proiecte', icon: 'projects' },
    { path: '/tasks', label: 'Taskuri', icon: 'tasks' },
    { path: '/params', label: 'Parametri', icon: 'params' },
    { path: '/calculator', label: 'Calculator', icon: 'calculator' },
    { path: '/notes', label: 'Notițe', icon: 'notes' },
    { path: '/admin', label: 'Admin', icon: 'admin' },
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
    transition: transform 0.28s var(--ease);
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
  .dock-item:hover {
    color: var(--text);
    transform: translateY(-4px);
  }
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

  @media (max-width: 560px) {
    .dock {
      gap: 2px;
      padding: 11px 6px 6px;
      max-width: calc(100vw - 16px);
    }
    .dock-item {
      width: 42px;
      height: 42px;
      border-radius: 13px;
    }
    .sep { margin: 8px 3px; }
  }
</style>
