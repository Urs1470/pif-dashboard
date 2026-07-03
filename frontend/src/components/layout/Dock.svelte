<script>
  import { onMount } from 'svelte'
  import { fade } from 'svelte/transition'
  import { Search } from '@lucide/svelte'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { router, link } from '../../lib/router.svelte.js'
  import { motionDuration, DUR_FAST } from '../../lib/motion.svelte.js'

  // Autohide v2: dispare doar la scroll RAPID in jos; revine la scroll in sus,
  // la top, la capatul paginii, dupa ~1s fara scroll (idle), la schimbarea
  // rutei, la pointer langa marginea de jos sau la tap pe manerul "peek".
  // Cat timp tastatura mobila e deschisa (focus pe un camp), dock + peek stau
  // ascunse ca sa nu pluteasca peste tastatura.
  let hidden = $state(false)
  let kbLocked = $state(false)

  // ruta noua -> dock vizibil
  $effect(() => {
    router.path
    if (!kbLocked) hidden = false
  })

  onMount(() => {
    // Scrollerul real e documentul: .app-content are min-height si creste
    // liber, deci overflow-ul ajunge pe <html>, nu pe #main-content.
    let lastY = window.scrollY
    let lastT = performance.now()
    let acc = 0
    let idleTimer = 0
    let dragging = false

    const show = () => { if (!kbLocked) hidden = false }

    function onScroll() {
      const now = performance.now()
      const y = window.scrollY
      const delta = y - lastY
      const dt = Math.max(1, now - lastT)
      lastY = y
      lastT = now

      // idle: sta ascuns doar CAT derulezi — dupa 1s fara scroll revine
      clearTimeout(idleTimer)
      idleTimer = setTimeout(show, 1000)

      // la top sau la capatul de jos (nu mai ai unde derula) — vizibil
      const atBottom = y + window.innerHeight >= document.documentElement.scrollHeight - 40
      if (y < 80 || atBottom) { show(); acc = 0; return }
      if (dragging) return

      // acumuleaza directia ca sa nu tremure la scroll fin
      acc = Math.sign(delta) === Math.sign(acc) ? acc + delta : delta
      // se ascunde doar la scroll intentionat (viteza > ~0.5px/ms), nu la citit
      const speed = Math.abs(delta) / dt
      if (acc > 24 && speed > 0.5 && !kbLocked) hidden = true
      else if (acc < -24) show()
    }

    let mmTick = 0
    function onMove(e) {
      const now = performance.now()
      if (now - mmTick < 120) return
      mmTick = now
      if (window.innerHeight - e.clientY < 90) show()
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
        hidden = false
      }, 120)
    }

    // in timpul drag&drop (reordonare Astazi) nu ascundem nimic
    const onDragStart = () => { dragging = true }
    const onDragEnd = () => { dragging = false }

    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('mousemove', onMove, { passive: true })
    window.addEventListener('dragstart', onDragStart)
    window.addEventListener('dragend', onDragEnd)
    window.addEventListener('drop', onDragEnd)
    document.addEventListener('focusin', onFocusIn)
    document.addEventListener('focusout', onFocusOut)
    return () => {
      clearTimeout(idleTimer)
      window.removeEventListener('scroll', onScroll)
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
  .dock.hidden:focus-within {
    --dock-shift: 0px;
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
