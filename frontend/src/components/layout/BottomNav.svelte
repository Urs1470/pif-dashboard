<script>
  import { Home, FolderKanban, ListTodo, Cpu, Menu } from '@lucide/svelte'
  import { router, link } from '../../lib/router.svelte.js'

  const tabs = [
    { path: '/', label: 'Acasa', icon: Home },
    { path: '/projects', label: 'Proiecte', icon: FolderKanban },
    { path: '/tasks', label: 'Taskuri', icon: ListTodo },
    { path: '/params', label: 'Parametri', icon: Cpu },
    { path: '/more', label: 'Mai mult', icon: Menu },
  ]

  function isActive(itemPath) {
    if (itemPath === '/') return router.path === '/'
    if (itemPath === '/more') {
      return ['/notes', '/admin'].some(p => router.path.startsWith(p))
    }
    return router.path.startsWith(itemPath)
  }
</script>

<nav class="bottom-nav" aria-label="Navigatie mobila">
  {#each tabs as tab}
    <a
      href={tab.path}
      use:link
      class="bottom-tab"
      class:active={isActive(tab.path)}
    >
      <tab.icon size={20} />
      <span>{tab.label}</span>
    </a>
  {/each}
</nav>

<style>
  .bottom-nav {
    display: none;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 64px;
    background: var(--bg-surface);
    border-top: 1px solid var(--border);
    z-index: var(--z-sticky);
    padding-bottom: env(safe-area-inset-bottom, 0);
  }

  @media (max-width: 768px) {
    .bottom-nav {
      display: flex;
      align-items: center;
      justify-content: space-around;
    }
  }

  .bottom-tab {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    padding: var(--space-xs);
    color: var(--text-dim);
    font-size: 0.65rem;
    font-weight: 500;
    transition: color var(--dur-fast) var(--ease);
    min-width: 56px;
    min-height: 48px;
    -webkit-tap-highlight-color: transparent;
  }
  .bottom-tab.active {
    color: var(--accent);
  }
</style>
