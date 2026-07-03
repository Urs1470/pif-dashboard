<script>
  import { fade } from 'svelte/transition'
  import Header from './components/layout/Header.svelte'
  import Dock from './components/layout/Dock.svelte'
  import Toast from './components/ui/Toast.svelte'
  import CommandPalette from './components/layout/CommandPalette.svelte'
  import { router, resolveRoute, viewTransitionsOn } from './lib/router.svelte.js'
  import { motionDuration, DUR_FAST } from './lib/motion.svelte.js'

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
    '/calculator': lazy(() => import('./pages/Calculator.svelte')),
    '/notes': lazy(() => import('./pages/Notes.svelte')),
    '/admin': lazy(() => import('./pages/Admin.svelte')),
  }

  const rawMatch = $derived(resolveRoute(routes))
  const routeKey = $derived(router.path)
  // When the browser drives the route change via the View Transitions API, let it
  // own the cross-fade; the Svelte fade only runs as a fallback (no VT support).
  // motionDuration() also zeroes this under reduced-motion regardless of VT support.
  const fadeDur = $derived(motionDuration(viewTransitionsOn() ? 0 : DUR_FAST))

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

<div class="app-layout">
  <div class="app-main">
    <Header />
    <main class="app-content" id="main-content">
      {#key routeKey}
        <div class="content-width" in:fade={{ duration: fadeDur }} out:fade={{ duration: fadeDur }}>
          {#if loadError}
            <div class="not-found"><p>Eroare: {loadError}</p></div>
          {:else if LoadedComponent}
            <LoadedComponent params={loadedParams}></LoadedComponent>
          {:else if rawMatch}
            <div class="page-loading"><Skeleton width="60%" height="24px" /><Skeleton width="100%" height="200px" /></div>
          {:else}
            <div class="not-found">
              <h2>404</h2>
              <p>Pagina nu a fost găsită.</p>
            </div>
          {/if}
        </div>
      {/key}
    </main>
  </div>

  <Dock />
  <CommandPalette />
  <Toast />
</div>

<style>
  .app-layout {
    min-height: 100dvh;
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
    /* Dock-ul pluteste peste continut la toate latimile — lasa loc dedesubt. */
    padding-bottom: calc(var(--dock-h) + var(--space-lg) + var(--safe-bottom));
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
    font-weight: var(--fw-bold);
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
    color: var(--accent-text);
    border-radius: var(--radius-sm);
    z-index: var(--z-tooltip);
    font-size: var(--font-small);
    font-weight: var(--fw-semibold);
    transition: top var(--dur-fast) var(--ease);
  }
  .skip-link:focus {
    top: var(--space-md);
  }

</style>
