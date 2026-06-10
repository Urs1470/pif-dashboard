<script>
  import { fade } from 'svelte/transition'
  import { Square } from '@lucide/svelte'
  import Sidebar from './components/layout/Sidebar.svelte'
  import Header from './components/layout/Header.svelte'
  import BottomNav from './components/layout/BottomNav.svelte'
  import Toast from './components/ui/Toast.svelte'
  import CommandPalette from './components/layout/CommandPalette.svelte'
  import { ui } from './stores/ui.svelte.js'
  import { router, resolveRoute } from './lib/router.svelte.js'
  import { timer, stopProjectTimer, stopTaskTimer, stopGlobalTaskTimer, loadActiveTimer } from './stores/timer.svelte.js'

  const kindLabels = { project: 'Proiect', task: 'Task', global_task: 'Task global' }

  function formatElapsed(sec) {
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = sec % 60
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  async function stopActive() {
    const a = timer.active
    if (!a) return
    if (a.kind === 'project' && a.project_id) await stopProjectTimer(a.project_id)
    else if (a.kind === 'task' && a.task_id) await stopTaskTimer(a.task_id)
    else if (a.kind === 'global_task' && a.global_task_id) await stopGlobalTaskTimer(a.global_task_id)
    await loadActiveTimer()
  }

  import Home from './pages/Home.svelte'
  import Skeleton from './components/ui/Skeleton.svelte'

  const lazyCache = {}
  function lazy(loader) {
    return { _lazy: true, loader }
  }

  const routes = {
    '/': Home,
    '/projects': lazy(() => import('./pages/Projects.svelte')),
    '/projects/:id': lazy(() => import('./pages/ProjectDetail.svelte')),
    '/tasks': lazy(() => import('./pages/Tasks.svelte')),
    '/params': lazy(() => import('./pages/Params.svelte')),
    '/notes': lazy(() => import('./pages/Notes.svelte')),
    '/budget': lazy(() => import('./pages/Budget.svelte')),
    '/admin': lazy(() => import('./pages/Admin.svelte')),
    '/more': lazy(() => import('./pages/More.svelte')),
  }

  const rawMatch = $derived(resolveRoute(routes))
  const routeKey = $derived(router.path)

  let LoadedComponent = $state(null)
  let loadedParams = $state({})
  let loadError = $state(null)

  $effect(() => {
    const m = rawMatch
    if (!m) { LoadedComponent = null; return }

    if (m.component._lazy) {
      // Cheia e PATTERN-ul rutei, nu prefixul caii — altfel /projects si
      // /projects/:id ar imparti aceeasi intrare in cache.
      const key = m.pattern
      if (lazyCache[key]) {
        LoadedComponent = lazyCache[key]
        loadedParams = m.params
      } else {
        LoadedComponent = null
        loadError = null
        m.component.loader().then(mod => {
          lazyCache[key] = mod.default
          LoadedComponent = mod.default
          loadedParams = m.params
        }).catch(e => { loadError = e.message })
      }
    } else {
      LoadedComponent = m.component
      loadedParams = m.params
    }
  })
</script>

<a class="skip-link" href="#main-content">Sari la continut</a>

<div class="app-layout" class:sidebar-collapsed={ui.sidebarCollapsed}>
  <Sidebar />

  <div class="app-main">
    <Header />
    {#if timer.active}
      <div class="gtb">
        <div class="gtb-dot"></div>
        <div class="gtb-main">
          <span class="gtb-label">{timer.active.label || '—'}</span>
          <span class="gtb-kind">{kindLabels[timer.active.kind] || 'Timer'}</span>
        </div>
        <span class="gtb-elapsed">{formatElapsed(timer.elapsed)}</span>
        <button class="gtb-stop" title="Opreste timerul" onclick={stopActive}><Square size={14} /></button>
      </div>
    {/if}
    <main class="app-content" id="main-content">
      {#key routeKey}
        <div class="content-width" in:fade={{ duration: 120 }}>
          {#if loadError}
            <div class="not-found"><p>Eroare: {loadError}</p></div>
          {:else if LoadedComponent}
            <LoadedComponent params={loadedParams}></LoadedComponent>
          {:else if rawMatch}
            <div class="page-loading"><Skeleton width="60%" height="24px" /><Skeleton width="100%" height="200px" /></div>
          {:else}
            <div class="not-found">
              <h2>404</h2>
              <p>Pagina nu a fost gasita.</p>
            </div>
          {/if}
        </div>
      {/key}
    </main>
  </div>

  <BottomNav />
  <CommandPalette />
  <Toast />
</div>

<style>
  .app-layout {
    display: grid;
    grid-template-columns: var(--sidebar-width) 1fr;
    min-height: 100dvh;
    transition: grid-template-columns var(--dur-base) var(--ease);
  }
  .app-layout.sidebar-collapsed {
    grid-template-columns: var(--sidebar-collapsed) 1fr;
  }

  .app-main {
    display: flex;
    flex-direction: column;
    min-height: 100dvh;
    overflow: hidden;
  }

  .app-content {
    flex: 1;
    overflow-y: auto;
  }

  .gtb {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: 10px var(--space-lg);
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
  }
  .gtb-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    animation: pulse 1.5s ease-in-out infinite;
    flex-shrink: 0;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  .gtb-main {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }
  .gtb-label {
    font-size: var(--font-small);
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .gtb-kind {
    font-size: var(--font-tiny);
    color: var(--accent);
    font-weight: 500;
  }
  .gtb-elapsed {
    font-family: var(--font-mono);
    font-size: var(--font-small);
    font-weight: 600;
    color: var(--accent);
    letter-spacing: 0.04em;
    margin-left: auto;
    flex-shrink: 0;
  }
  .gtb-stop {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--danger);
    cursor: pointer;
    transition: all var(--dur-fast) var(--ease);
    flex-shrink: 0;
  }
  .gtb-stop:hover {
    background: var(--danger);
    color: white;
  }

  .not-found {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-2xl);
    color: var(--text-dim);
  }
  .not-found h2 {
    font-size: 3rem;
    font-weight: 700;
    color: var(--text-secondary);
  }

  .page-loading {
    padding: var(--space-lg);
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
    max-width: 600px;
  }

  .skip-link {
    position: fixed;
    top: -100px;
    left: var(--space-md);
    padding: var(--space-sm) var(--space-md);
    background: var(--accent);
    color: var(--bg);
    border-radius: var(--radius-sm);
    z-index: var(--z-tooltip);
    font-size: var(--font-small);
    font-weight: 600;
    transition: top var(--dur-fast) var(--ease);
  }
  .skip-link:focus {
    top: var(--space-md);
  }

  @media (max-width: 768px) {
    .app-layout,
    .app-layout.sidebar-collapsed {
      grid-template-columns: 1fr;
    }
    .app-content {
      padding-bottom: 72px;
    }
  }
</style>
