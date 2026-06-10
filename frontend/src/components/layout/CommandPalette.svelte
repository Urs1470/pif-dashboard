<script>
  import { Search, Home, FolderKanban, ListTodo, Cpu, StickyNote, Wallet, Settings } from '@lucide/svelte'
  import { navigate, router } from '../../lib/router.svelte.js'

  let open = $state(false)
  let query = $state('')
  let selected = $state(0)
  let inputEl = $state(null)

  const commands = [
    { label: 'Acasa', path: '/', icon: Home, keywords: 'home dashboard' },
    { label: 'Proiecte', path: '/projects', icon: FolderKanban, keywords: 'projects lista' },
    { label: 'Taskuri', path: '/tasks', icon: ListTodo, keywords: 'tasks todo' },
    { label: 'Parametri', path: '/params', icon: Cpu, keywords: 'params drive fault' },
    { label: 'Notite', path: '/notes', icon: StickyNote, keywords: 'notes obsidian' },
    { label: 'Budget', path: '/budget', icon: Wallet, keywords: 'budget cheltuieli' },
    { label: 'Admin', path: '/admin', icon: Settings, keywords: 'admin stats export' },
  ]

  const filtered = $derived(
    query.trim()
      ? commands.filter(c =>
          (c.label + ' ' + c.keywords).toLowerCase().includes(query.toLowerCase())
        )
      : commands
  )

  $effect(() => { selected = 0 })

  function handleKey(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); selected = Math.min(selected + 1, filtered.length - 1) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); selected = Math.max(selected - 1, 0) }
    else if (e.key === 'Enter' && filtered[selected]) { go(filtered[selected]) }
    else if (e.key === 'Escape') { close() }
  }

  function go(cmd) {
    navigate(cmd.path)
    close()
  }

  function close() {
    open = false
    query = ''
  }

  function onGlobalKey(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault()
      open = !open
      if (open) requestAnimationFrame(() => inputEl?.focus())
    }
  }

  $effect(() => {
    window.addEventListener('keydown', onGlobalKey)
    return () => window.removeEventListener('keydown', onGlobalKey)
  })
</script>

{#if open}
  <div class="palette-backdrop" onclick={close} role="presentation">
    <div class="palette" onclick={(e) => e.stopPropagation()} onkeydown={handleKey} role="listbox" tabindex="-1">
      <div class="palette-search">
        <Search size={16} />
        <input
          bind:this={inputEl}
          type="text"
          bind:value={query}
          placeholder="Navigheaza..."
          autocomplete="off"
          spellcheck="false"
        />
        <kbd>Esc</kbd>
      </div>
      <div class="palette-list">
        {#each filtered as cmd, i (cmd.path)}
          <button
            class="palette-item"
            class:selected={i === selected}
            onclick={() => go(cmd)}
            onmouseenter={() => selected = i}
            role="option"
            aria-selected={i === selected}
          >
            <cmd.icon size={16} />
            <span>{cmd.label}</span>
            {#if router.path === cmd.path || (cmd.path !== '/' && router.path.startsWith(cmd.path))}
              <span class="current">curent</span>
            {/if}
          </button>
        {/each}
        {#if filtered.length === 0}
          <div class="palette-empty">Niciun rezultat</div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .palette-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: var(--z-modal);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 20vh;
    animation: fadeIn var(--dur-fast) var(--ease);
  }

  .palette {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 480px;
    box-shadow: var(--shadow-lg);
    overflow: hidden;
    animation: slideUp var(--dur-fast) var(--ease);
  }

  .palette-search {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-md) var(--space-lg);
    border-bottom: 1px solid var(--border);
    color: var(--text-dim);
  }
  .palette-search input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text);
    font-size: var(--font-body);
  }
  .palette-search input::placeholder { color: var(--text-dim); }
  .palette-search kbd {
    font-family: var(--font-mono);
    font-size: var(--font-tiny);
    padding: 2px 6px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-xs);
    color: var(--text-dim);
  }

  .palette-list {
    max-height: 320px;
    overflow-y: auto;
    padding: var(--space-xs);
  }

  .palette-item {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    width: 100%;
    padding: var(--space-sm) var(--space-md);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--font-small);
    text-align: left;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease);
  }
  .palette-item:hover,
  .palette-item.selected {
    background: var(--bg-hover);
    color: var(--text);
  }
  .current {
    margin-left: auto;
    font-size: var(--font-tiny);
    color: var(--accent);
    opacity: 0.7;
  }

  .palette-empty {
    padding: var(--space-lg);
    text-align: center;
    color: var(--text-dim);
    font-size: var(--font-small);
  }

  @keyframes fadeIn { from { opacity: 0; } }
  @keyframes slideUp { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }

  @media (max-width: 768px) {
    .palette-backdrop { padding-top: var(--space-lg); padding-left: var(--space-md); padding-right: var(--space-md); }
  }
</style>
