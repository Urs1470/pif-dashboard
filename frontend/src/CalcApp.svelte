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
  /* ACELASI SHELL, DOAR FARA DOCK SI FARA MARCA. Calculatorul public e aceeasi
     aplicatie vazuta din afara, nu alta — deci nici comutatorul de tema nu e un
     obiect propriu: e o suprafata flotanta ca oricare alta, adica umbra, nu
     chenar, si aceeasi raza de control. */
  .sa { min-height: 100dvh; background: var(--bg); color: var(--text); }
  .sa-theme {
    position: fixed; top: 12px; right: 14px; z-index: var(--z-dropdown);
    display: inline-flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: var(--radius-sm);
    border: none; color: var(--text-dim); background: var(--bg-surface);
    box-shadow: var(--shadow-sm); cursor: pointer;
    transition: var(--transition-pressable);
  }
  .sa-theme:hover { background: var(--bg-hover); color: var(--text); }
  .sa-theme:active { transform: scale(var(--press-scale)); }
  .sa-main { max-width: 1400px; margin: 0 auto; }
  .sa-foot { text-align: center; padding: var(--space-20); font-size: var(--font-small); color: var(--text-dim); border-top: 1px solid var(--border); }

  @media (max-width: 768px) {
    .sa-theme { width: var(--tap-min); height: var(--tap-min); }
  }
</style>
