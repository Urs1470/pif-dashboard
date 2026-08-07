<script>
  import { Sun, Moon, Monitor } from '@lucide/svelte'
  import { ui } from '../../stores/ui.svelte.js'
  import { tema, cicleazaTema } from '../../lib/tema.svelte.js'

  // Spune si ce e acum, si ce urmeaza — cu trei stari, „ce urmeaza" singur nu se
  // deduce dintr-o iconita.
  const titluTema = $derived(
    tema.mod === 'auto'
      ? `Temă: automată (sistemul e ${tema.sistem === 'dark' ? 'închis' : 'deschis'}) — atinge pentru deschisă`
      : tema.mod === 'light'
        ? 'Temă: deschisă — atinge pentru închisă'
        : 'Temă: închisă — atinge pentru automată'
  )
</script>

<header class="header">
  <a href="/" class="brand" title="PIF Dashboard">
    <span class="brand-dot"></span>
    <span class="brand-name">PIF<span class="brand-sep">·</span>Dashboard</span>
  </a>

  {#if ui.pageHeader.title}
    <div class="header-context">
      <h1 class="hc-title">{ui.pageHeader.title}</h1>
      {#if ui.pageHeader.subtitle}<span class="hc-sep" aria-hidden="true">·</span><span class="hc-sub">{ui.pageHeader.subtitle}</span>{/if}
    </div>
  {/if}

  <span class="h-spacer"></span>

  <div class="header-actions">
    <!-- Iconita arata MODUL CURENT, nu pe cel urmator. Cu doua stari „arata unde
         ajungi" mergea; cu trei, un monitor care inseamna „urmatorul e auto" nu
         se poate ghici. Titlul spune si unde te duce atingerea. -->
    <button class="header-btn" onclick={cicleazaTema} title={titluTema}
            aria-label={titluTema}>
      {#if tema.mod === 'auto'}
        <Monitor size={18} />
      {:else if tema.mod === 'light'}
        <Sun size={18} />
      {:else}
        <Moon size={18} />
      {/if}
    </button>
  </div>
</header>

<style>
  .header {
    height: var(--header-height);
    background: color-mix(in srgb, var(--bg) 82%, transparent);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 var(--space-lg);
    position: sticky;
    top: 0;
    z-index: var(--z-sticky);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--font-heading);
    font-weight: var(--fw-semibold);
    font-size: var(--font-h3);
    letter-spacing: var(--tracking-tight);
    color: var(--text);
    white-space: nowrap;
  }
  .brand-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 14px var(--accent-ring);
    flex-shrink: 0;
  }
  .brand-sep { color: var(--text-faint); }

  /* Context de pagina (ex. salutul de pe Home) — CENTRAT in bara, separat de
     brand si actiuni prin spatiu. pointer-events:none ca sa nu blocheze clickuri. */
  .header-context {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: baseline;
    gap: 8px;
    max-width: 56%;
    pointer-events: none;
    white-space: nowrap;
  }
  .hc-title {
    font-family: var(--font-heading);
    font-weight: var(--fw-semibold);
    font-size: var(--font-h3);
    letter-spacing: var(--tracking-tight);
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .hc-sep { color: var(--text-faint); align-self: center; }
  .hc-sub {
    font-size: var(--font-small);
    color: var(--text-dim);
    text-transform: capitalize;
    flex-shrink: 0;
  }

  .h-spacer { flex: 1; }

  .header-actions {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .header-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    transition: var(--transition-colors);
  }
  .header-btn:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  @media (max-width: 768px) {
    /* Pe telefon salutul centrat se suprapunea peste brand (nu incape la 390px).
       Il ascundem complet — brandul + titlul propriu al paginii sunt de ajuns. */
    .header-context { display: none; }
    .header {
      flex-wrap: wrap;
      height: auto;
      min-height: var(--header-height);
      gap: var(--space-xs);
      /* Coboara sub notch/status-bar si respecta insets laterale. */
      padding-top: calc(var(--space-xs) + var(--safe-top));
      padding-bottom: var(--space-xs);
      padding-left: calc(var(--space-md) + var(--safe-left));
      padding-right: calc(var(--space-md) + var(--safe-right));
    }

    /* Cele doua tinte din bara — sigla (duce Acasa) si comutatorul de tema — erau
       de 25px si 36px. Casetele cresc la 44 fara ca semnele sa creasca: sigla isi
       pastreaza inaltimea textului, butonul isi pastreaza iconita de 18px. */
    .brand { min-height: var(--tap-min); }
    .header-btn { width: var(--tap-min); height: var(--tap-min); margin-right: -8px; }
  }
</style>
