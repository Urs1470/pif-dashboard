<script>
  import { onMount } from 'svelte'
  import { fade } from 'svelte/transition'
  import { Search } from '@lucide/svelte'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { router, link } from '../../lib/router.svelte.js'
  import { motionDuration, DUR_FAST } from '../../lib/motion.svelte.js'

  // Autohide v3: cand ai derulat pagina, dock-ul se ascunde si revine DOAR cand
  // duci cursorul in zona de jos (unde sta dock-ul) — reveal la hover pe margine.
  // Ramane vizibil cat esti in varful paginii sau la capatul ei si cat timp
  // cursorul e in zona de jos; iese cursorul din zona -> se ascunde la loc.
  // Scrollerul real e #main-content (.app-main are overflow:hidden), NU window.
  // Pe mobil (fara cursor) ramane manerul "peek": tap -> revine.
  // Cat timp tastatura mobila e deschisa (focus pe camp) dock + peek stau ascunse.
  let hidden = $state(false)
  let kbLocked = $state(false)

  // ruta noua -> dock vizibil
  $effect(() => {
    router.path
    if (!kbLocked) hidden = false
  })

  onMount(() => {
    // Scrollerul e fereastra (documentul creste liber; .app-content nu ajunge
    // sa deruleze intern). Citim din document.scrollingElement (== window.scrollY).
    const se = document.scrollingElement || document.documentElement
    const mc = document.getElementById('main-content')
    let inBottomZone = false
    let dragging = false
    const REVEAL = 120  // cursor mai aproape de jos de atat -> reveal
    const LEAVE = 180   // cursor mai departe de atat -> permite ascunderea

    // Foloseste #main-content DOAR daca chiar deruleaza intern; altfel fereastra.
    const mcScrolls = () => mc && mc.scrollHeight > mc.clientHeight + 5
    const scrollTop = () => (mcScrolls() ? mc.scrollTop : (window.scrollY || se.scrollTop || 0))
    const scrollBottomGap = () => mcScrolls()
      ? mc.scrollHeight - mc.scrollTop - mc.clientHeight
      : se.scrollHeight - (window.scrollY || se.scrollTop || 0) - window.innerHeight
    const atTop = () => scrollTop() < 80
    const atBottom = () => scrollBottomGap() <= 40

    function recompute() {
      if (kbLocked) { hidden = true; return }
      if (dragging) { hidden = false; return }
      hidden = !(atTop() || atBottom() || inBottomZone)
    }

    function onScroll() { recompute() }

    let mmTick = 0
    function onMove(e) {
      const now = performance.now()
      if (now - mmTick < 50) return
      mmTick = now
      const fromBottom = window.innerHeight - e.clientY
      if (fromBottom < REVEAL) inBottomZone = true
      else if (fromBottom > LEAVE) inBottomZone = false
      recompute()
    }

    // tastatura mobila: focus pe camp editabil -> dock blocat ascuns
    const isMobileLike = () => window.matchMedia('(pointer: coarse)').matches || window.innerWidth <= 768
    const isEditable = (el) => !!el && (el.matches?.('input, textarea, select') || el.closest?.('[contenteditable="true"]'))
    function onFocusIn(e) {
      if (!isMobileLike() || !isEditable(e.target)) return
      kbLocked = true
      hidden = true
    }
    function onFocusOut() {
      if (!kbLocked) return
      setTimeout(() => {
        if (isEditable(document.activeElement)) return
        kbLocked = false
        recompute()
      }, 120)
    }

    // in timpul drag&drop (reordonare Astazi) nu ascundem nimic
    const onDragStart = () => { dragging = true; recompute() }
    const onDragEnd = () => { dragging = false; recompute() }

    window.addEventListener('scroll', onScroll, { passive: true })
    mc?.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('mousemove', onMove, { passive: true })
    window.addEventListener('dragstart', onDragStart)
    window.addEventListener('dragend', onDragEnd)
    window.addEventListener('drop', onDragEnd)
    document.addEventListener('focusin', onFocusIn)
    document.addEventListener('focusout', onFocusOut)
    recompute()
    return () => {
      window.removeEventListener('scroll', onScroll)
      mc?.removeEventListener('scroll', onScroll)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('dragstart', onDragStart)
      window.removeEventListener('dragend', onDragEnd)
      window.removeEventListener('drop', onDragEnd)
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

{#if hidden && !kbLocked}
  <button
    class="dock-peek"
    transition:fade={{ duration: motionDuration(DUR_FAST) }}
    aria-label="Arată navigația"
    title="Arată navigația"
    onclick={() => (hidden = false)}
  ><span></span></button>
{/if}

<style>
  .dock {
    position: fixed;
    left: 50%;
    bottom: calc(14px + var(--safe-bottom));
    transform: translateX(-50%) translateY(var(--dock-shift, 0px));
    transition: transform 0.28s var(--ease);
    display: flex;
    gap: 4px;
    padding: 8px;
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

  .dock.hidden {
    --dock-shift: calc(100% + 22px + var(--safe-bottom));
  }

  .sep {
    width: 1px;
    background: var(--border-strong);
    margin: 10px 6px;
  }

  /* Manerul "peek" — ramane cand dock-ul e ascuns; tap/click il readuce */
  .dock-peek {
    position: fixed;
    left: 50%;
    transform: translateX(-50%);
    bottom: calc(4px + var(--safe-bottom));
    width: 64px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    cursor: pointer;
    z-index: var(--z-sticky);
  }
  .dock-peek span {
    width: 36px;
    height: 5px;
    border-radius: var(--radius-full);
    background: var(--border-strong);
    box-shadow: 0 1px 6px rgba(0, 0, 0, 0.45);
    transition: background var(--dur-fast) var(--ease), width var(--dur-fast) var(--ease);
  }
  .dock-peek:hover span,
  .dock-peek:focus-visible span {
    background: var(--accent);
    width: 46px;
  }

  @media (max-width: 560px) {
    .dock {
      gap: 2px;
      padding: 6px;
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
