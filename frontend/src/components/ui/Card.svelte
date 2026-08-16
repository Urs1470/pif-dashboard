<script>
  let { padding = true, hover = false, onclick, children } = $props()
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
  class="card"
  class:padded={padding}
  class:hoverable={hover}
  class:clickable={onclick}
  role={onclick ? 'button' : undefined}
  tabindex={onclick ? '0' : undefined}
  onclick={onclick}
  onkeydown={onclick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onclick(e) } } : undefined}
>
  {@render children()}
</div>

<style>
  /* SUPRAFATA SE DESPRINDE PRIN UMBRA, NU PRIN CHENAR.
     Cardul avea si `border: 1px`, si `box-shadow` — deci fiecare card era
     conturat, exact aspectul de „cadre desenate din linii peste tot" pe care
     sistemul il scoate. Liniile de 1px raman doar ca separatoare INTRE randuri.
     Raza e 14 (suprafata), nu 20: 20 e treapta rezervata foii de jos. */
  .card {
    background: var(--bg-surface);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
    transition: box-shadow var(--dur-fast) var(--ease);
  }
  .padded {
    padding: var(--card-pad);
  }
  /* Fara chenar, hoverul se face tot din umbra: cardul se ridica un nivel. */
  .hoverable:hover {
    box-shadow: var(--shadow-md);
  }
  .clickable {
    cursor: pointer;
    transition: box-shadow var(--dur-fast) var(--ease), transform var(--dur-press) var(--ease);
  }
  .clickable:hover {
    box-shadow: var(--shadow-md);
  }
  .clickable:active {
    transform: scale(var(--press-scale));
  }
</style>
