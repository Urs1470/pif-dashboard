<script>
  import Sidebar from './components/layout/Sidebar.svelte'
  import Header from './components/layout/Header.svelte'
  import BottomNav from './components/layout/BottomNav.svelte'
  import Toast from './components/ui/Toast.svelte'
  import { ui } from './stores/ui.svelte.js'
  import { resolveRoute } from './lib/router.svelte.js'

  import Home from './pages/Home.svelte'
  import Projects from './pages/Projects.svelte'
  import ProjectDetail from './pages/ProjectDetail.svelte'
  import Tasks from './pages/Tasks.svelte'
  import Params from './pages/Params.svelte'
  import Notes from './pages/Notes.svelte'
  import Budget from './pages/Budget.svelte'
  import Admin from './pages/Admin.svelte'
  import More from './pages/More.svelte'

  const routes = {
    '/': Home,
    '/projects': Projects,
    '/projects/:id': ProjectDetail,
    '/tasks': Tasks,
    '/params': Params,
    '/notes': Notes,
    '/budget': Budget,
    '/admin': Admin,
    '/more': More,
  }

  const match = $derived(resolveRoute(routes))
</script>

<div class="app-layout" class:sidebar-collapsed={ui.sidebarCollapsed}>
  <Sidebar />

  <div class="app-main">
    <Header />
    <main class="app-content">
      {#if match}
        <match.component params={match.params} />
      {:else}
        <div class="not-found">
          <h2>404</h2>
          <p>Pagina nu a fost gasita.</p>
        </div>
      {/if}
    </main>
  </div>

  <BottomNav />
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
