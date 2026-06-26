<script>
  import {
    Home, FolderKanban, ListTodo, Cpu, StickyNote,
    Settings, PanelLeftClose, PanelLeft, Calculator
  } from '@lucide/svelte'
  import { router, link, navigate } from '../../lib/router.svelte.js'
  import { ui, toggleSidebar } from '../../stores/ui.svelte.js'

  const navItems = [
    { path: '/', label: 'Acasa', icon: Home },
    { path: '/projects', label: 'Proiecte', icon: FolderKanban },
    { path: '/tasks', label: 'Taskuri', icon: ListTodo },
    { path: '/params', label: 'Parametri', icon: Cpu },
    { path: '/calculator', label: 'Calculator', icon: Calculator },
    { path: '/notes', label: 'Notite', icon: StickyNote },
    { path: '/admin', label: 'Admin', icon: Settings },
  ]

  function isActive(itemPath) {
    if (itemPath === '/') return router.path === '/'
    return router.path.startsWith(itemPath)
  }
</script>

<aside class="sidebar" class:collapsed={ui.sidebarCollapsed}>
  <a href="/" use:link class="sidebar-brand" title="PIF Dashboard">
    <svg class="brand-logo" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
      <rect width="32" height="32" rx="7" fill="var(--accent)"/>
      <path d="M7 24 C13.5 24 15 20 16.5 15 S21 8 25 8 L25 24 Z" fill="var(--accent-text)" opacity="0.3"/>
      <path d="M7 24 C13.5 24 15 20 16.5 15 S21 8 25 8" fill="none" stroke="var(--accent-text)" stroke-width="2.75" stroke-linecap="round"/>
      <circle cx="25" cy="8" r="2.5" fill="var(--accent-text)"/>
    </svg>
    {#if !ui.sidebarCollapsed}
      <span class="brand-text">PIF Dashboard</span>
    {/if}
  </a>

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
    gap: var(--space-sm);
    padding: 0 var(--space-md);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    text-decoration: none;
    transition: opacity var(--dur-fast) var(--ease);
  }
  .sidebar-brand:hover { opacity: 0.85; }
  .brand-logo {
    width: 28px;
    height: 28px;
    flex-shrink: 0;
  }
  .brand-text {
    font-size: var(--font-small);
    font-weight: 700;
    color: var(--text);
    letter-spacing: 0.02em;
    white-space: nowrap;
    overflow: hidden;
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
