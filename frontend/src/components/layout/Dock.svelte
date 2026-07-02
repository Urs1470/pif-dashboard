<script>
  import { onMount } from 'svelte'
  import { Search } from '@lucide/svelte'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { router, link } from '../../lib/router.svelte.js'

  // Autohide: dispare la scroll in jos, reapare la scroll in sus / la top /
  // cand pointerul se apropie de marginea de jos / la focus in dock.
  let hidden = $state(false)

  onMount(() => {
    // Scrollerul real e documentul: .app-content are min-height si creste
    // liber, deci overflow-ul ajunge pe <html>, nu pe #main-content.
    let lastY = window.scrollY
    let acc = 0
    function onScroll() {
      const y = window.scrollY
      const delta = y - lastY
      lastY = y
      if (y < 80) { hidden = false; acc = 0; return }
      // acumuleaza directia ca sa nu tremure la scroll fin
      acc = Math.sign(delta) === Math.sign(acc) ? acc + delta : delta
      if (acc > 24) hidden = true
      else if (acc < -24) hidden = false
    }
    let mmTick = 0
    function onMove(e) {
      const now = performance.now()
      if (now - mmTick < 120) return
      mmTick = now
      if (window.innerHeight - e.clientY < 90) hidden = false
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('mousemove', onMove, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('mousemove', onMove)
    }
  })

  const items = [
    { path: '/', label: 'Acasa', icon: 'home' },
    { path: '/projects', label: 'Proiecte', icon: 'projects' },
    { path: '/tasks', label: 'Taskuri', icon: 'tasks' },
    { path: '/params', label: 'Parametri', icon: 'params' },
    { path: '/calculator', label: 'Calculator', icon: 'calculator' },
    { path: '/notes', label: 'Notite', icon: 'notes' },
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

<nav class="dock" class:hidden aria-label="Navigatie principala">
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
  <button class="dock-item" onclick={openSearch} aria-label="Cauta (Ctrl+K)" title="Cauta (Ctrl+K)">
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
