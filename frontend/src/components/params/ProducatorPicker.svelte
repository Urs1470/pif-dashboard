<script>
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { PRODUCATOR_FAMILII } from '../../stores/params.svelte.js'

  let { families = [], onpick } = $props()

  function countFor(producator) {
    const fams = PRODUCATOR_FAMILII[producator] || []
    return families
      .filter(f => fams.includes(f.familie))
      .reduce((sum, f) => sum + (f.count || 0), 0)
  }

  const producatori = $derived(
    Object.keys(PRODUCATOR_FAMILII).map(p => ({
      nume: p,
      familii: PRODUCATOR_FAMILII[p].length,
      count: countFor(p),
    }))
  )
</script>

<div class="picker">
  {#each producatori as p (p.nume)}
    <button class="pcard" onclick={() => onpick?.(p.nume)}>
      <SolidIcon name="cpu" size={24} />
      <span class="pname">{p.nume}</span>
      <span class="pmeta">{p.familii} {p.familii === 1 ? 'familie' : 'familii'} · {p.count} parametri</span>
    </button>
  {/each}
</div>

<style>
  .picker { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: var(--space-md); }
  .pcard {
    display: flex; flex-direction: column; align-items: center; gap: var(--space-sm);
    padding: var(--space-lg); background: var(--bg-surface); border: 1px solid var(--border);
    border-radius: var(--radius-lg); color: var(--text-dim); cursor: pointer;
    transition: all var(--dur-fast) var(--ease);
  }
  .pcard:hover { border-color: var(--accent); color: var(--accent); transform: translateY(-2px); box-shadow: var(--shadow-md); }
  .pname { font-size: var(--font-h3); font-weight: var(--fw-bold); color: var(--text); }
  .pmeta { font-size: var(--font-tiny); color: var(--text-dim); }
</style>
