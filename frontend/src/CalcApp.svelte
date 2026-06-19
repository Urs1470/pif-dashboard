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
  <button class="sa-theme" onclick={toggleTheme} aria-label="Schimba tema" title="Schimba tema (light/dark)">
    {#if theme === 'dark'}<Sun size={18} />{:else}<Moon size={18} />{/if}
  </button>
  <div class="sa-main">
    <Calculator />
  </div>
  <footer class="sa-foot">Valori orientative — verifica intotdeauna catalogul / manualul. · Electroglobal PIF</footer>
</div>

<style>
  .sa { min-height: 100dvh; background: var(--bg); color: var(--text); }
  /* fara header — doar un buton mic flotant pentru tema */
  .sa-theme {
    position: fixed; top: 12px; right: 14px; z-index: 50;
    display: inline-flex; align-items: center; justify-content: center;
    width: 34px; height: 34px; border-radius: var(--radius-sm);
    border: 1px solid var(--border); color: var(--text-dim); background: var(--bg-surface); cursor: pointer;
  }
  .sa-theme:hover { border-color: var(--accent); color: var(--accent); }
  .sa-main { max-width: 1400px; margin: 0 auto; }
  .sa-foot { text-align: center; padding: 18px; font-size: var(--font-tiny); color: var(--text-dim); border-top: 1px solid var(--border); }
</style>
