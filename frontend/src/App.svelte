<script>
  import { fade } from 'svelte/transition'
  import Sidebar from './components/layout/Sidebar.svelte'
  import Header from './components/layout/Header.svelte'
  import BottomNav from './components/layout/BottomNav.svelte'
  import Toast from './components/ui/Toast.svelte'
  import CommandPalette from './components/layout/CommandPalette.svelte'
  import { ui } from './stores/ui.svelte.js'
  import { router, resolveRoute } from './lib/router.svelte.js'

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
    /* Lasa loc pentru bottom-nav + home-indicator, ca ultimul rand de continut
       sa nu fie ascuns sub bara de navigatie. */
    .app-content {
      padding-bottom: calc(var(--bottom-nav-height) + var(--safe-bottom) + var(--space-sm));
    }
  }
</style>
