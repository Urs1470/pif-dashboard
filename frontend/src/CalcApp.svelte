<script>
  import Calculator from './pages/Calculator.svelte'
  import { Sun, Moon, Monitor } from '@lucide/svelte'
  import { tema, cicleazaTema } from './lib/tema.svelte.js'

  // Aceeasi sursa ca in dashboard: /calc e alt bundle, dar acelasi browser si
  // aceeasi preferinta. Inainte avea comutatorul lui, care nu retinea nimic si
  // nu stia de sistem.
</script>

<div class="sa">
  <button class="sa-theme" onclick={cicleazaTema} aria-label="Schimbă tema"
          title={tema.mod === 'auto' ? 'Temă: automată (după sistem)'
                 : tema.mod === 'light' ? 'Temă: deschisă' : 'Temă: închisă'}>
    {#if tema.mod === 'auto'}<Monitor size={18} />
    {:else if tema.mod === 'light'}<Sun size={18} />
    {:else}<Moon size={18} />{/if}
  </button>
  <div class="sa-main">
    <Calculator standalone={true} />
  </div>
  <footer class="sa-foot">Valori orientative — verifică întotdeauna catalogul / manualul. · Electroglobal PIF</footer>
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
