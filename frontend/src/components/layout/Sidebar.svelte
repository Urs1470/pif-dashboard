<script>
  import {
    Home, FolderKanban, ListTodo, Cpu, StickyNote,
    Wallet, Settings, PanelLeftClose, PanelLeft
  } from '@lucide/svelte'
  import { router, link } from '../../lib/router.svelte.js'
  import { ui, toggleSidebar } from '../../stores/ui.svelte.js'

  const navItems = [
    { path: '/', label: 'Acasa', icon: Home },
    { path: '/projects', label: 'Proiecte', icon: FolderKanban },
    { path: '/tasks', label: 'Taskuri', icon: ListTodo },
    { path: '/params', label: 'Parametri', icon: Cpu },
    { path: '/notes', label: 'Notite', icon: StickyNote },
    { path: '/budget', label: 'Budget', icon: Wallet },
    { path: '/admin', label: 'Admin', icon: Settings },
  ]

  function isActive(itemPath) {
    if (itemPath === '/') return router.path === '/'
    return router.path.startsWith(itemPath)
  }
</script>

<aside class="sidebar" class:collapsed={ui.sidebarCollapsed}>
  <div class="sidebar-brand">
    {#if !ui.sidebarCollapsed}
      <span class="brand-text">PIF</span>
    {:else}
      <span class="brand-icon">P</span>
    {/if}
  </div>

  <nav class="sidebar-nav" aria-label="Navigatie principala">
    {#each navItems as item}
      <a
        href={item.path}
        use:link
        class="nav-item"
        class:active={isActive(item.path)}
        title={ui.sidebarCollapsed ? item.label : undefined}
      >
        <item.icon size={20} />
        {#if !ui.sidebarCollapsed}
          <span class="nav-label">{item.label}</span>
        {/if}
      </a>
    {/each}
  </nav>

  <button class="sidebar-toggle" onclick={toggleSidebar}>
    {#if ui.sidebarCollapsed}
      <PanelLeft size={18} />
    {:else}
      <PanelLeftClose size={18} />
    {/if}
  </button>
</aside>

<style>
  .sidebar {
    position: sticky;
    top: 0;
    height: 100dvh;
    width: var(--sidebar-width);
    background: var(--bg-surface);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    z-index: var(--z-sticky);
    transition: width var(--dur-base) var(--ease);
  }
  .sidebar.collapsed {
    width: var(--sidebar-collapsed);
  }

  .sidebar-brand {
    height: var(--header-height);
    display: flex;
    align-items: center;
    padding: 0 var(--space-md);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .brand-text {
    font-size: var(--font-h2);
    font-weight: 700;
    color: var(--accent);
    letter-spacing: 0.05em;
  }
  .brand-icon {
    font-size: var(--font-h2);
    font-weight: 700;
    color: var(--accent);
    width: 32px;
    text-align: center;
  }

  .sidebar-nav {
    flex: 1;
    padding: var(--space-sm);
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-sm) var(--space-sm);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    transition: all var(--dur-fast) var(--ease);
    white-space: nowrap;
    overflow: hidden;
  }
  .nav-item:hover {
    background: var(--bg-hover);
    color: var(--text);
  }
  .nav-item.active {
    background: var(--accent-subtle);
    color: var(--accent);
  }

  .nav-label {
    font-size: var(--font-small);
    font-weight: 500;
  }

  .sidebar-toggle {
    padding: var(--space-md);
    border-top: 1px solid var(--border);
    color: var(--text-dim);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: color var(--dur-fast) var(--ease);
    flex-shrink: 0;
  }
  .sidebar-toggle:hover {
    color: var(--text);
  }

  @media (max-width: 768px) {
    .sidebar {
      display: none;
    }
  }
</style>
