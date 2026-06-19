<script>
  import Calculator from './pages/Calculator.svelte'
  import { Sun, Moon } from '@lucide/svelte'

  let theme = $state(document.documentElement.getAttribute('data-theme') || 'dark')
  function toggleTheme() {
    theme = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', theme)
  }
</script>

<div class="sa">
  <header class="sa-bar">
    <span class="sa-brand">PIF · Calculator acționări electrice</span>
    <button class="sa-theme" onclick={toggleTheme} aria-label="Schimba tema">
      {#if theme === 'dark'}<Sun size={18} />{:else}<Moon size={18} />{/if}
    </button>
  </header>
  <div class="sa-main">
    <Calculator />
  </div>
  <footer class="sa-foot">Valori orientative — verifica intotdeauna catalogul / manualul. · Electroglobal PIF</footer>
</div>

<style>
  .sa { min-height: 100dvh; background: var(--bg); color: var(--text); }
  .sa-bar {
    position: sticky; top: 0; z-index: 30;
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 10px 18px;
    background: var(--bg-surface); border-bottom: 1px solid var(--border);
  }
  .sa-brand { font-weight: 700; color: var(--accent); }
  .sa-theme {
    display: inline-flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: var(--radius-sm);
    border: 1px solid var(--border); color: var(--text); background: var(--bg); cursor: pointer;
  }
  .sa-theme:hover { border-color: var(--accent); color: var(--accent); }
  .sa-main { max-width: 1400px; margin: 0 auto; }
  .sa-foot { text-align: center; padding: 18px; font-size: var(--font-tiny); color: var(--text-dim); border-top: 1px solid var(--border); }
</style>
