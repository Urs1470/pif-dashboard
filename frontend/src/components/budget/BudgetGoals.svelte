<script>
  import { Target, Plus } from '@lucide/svelte'
  import { budget, markDirty, getNextBudgetId } from '../../stores/budget.svelte.js'
  import { formatRON, parseRON, round2, todayIso, daysBetween } from '../../lib/budget-calc.js'

  const d = $derived(budget.data)
  const goals = $derived(d?.goals || [])

  function addGoal() {
    d.goals.push({ id: getNextBudgetId(d.goals), label: 'Obiectiv nou', sumaTarget: 0, contribuit: 0, dataTarget: '', nota: '' })
    markDirty()
  }

  function removeGoal(id) {
    d.goals = d.goals.filter(g => g.id !== id)
    markDirty()
  }

  function contribute(goal, amount) {
    goal.contribuit = round2((goal.contribuit || 0) + (parseRON(amount) || 0))
    markDirty()
  }

  function goalProgress(g) {
    const target = parseRON(g.sumaTarget) || 1
    return Math.min(100, Math.round(((g.contribuit || 0) / target) * 100))
  }

  function monthlyNeeded(g) {
    const remaining = (parseRON(g.sumaTarget) || 0) - (g.contribuit || 0)
    if (remaining <= 0) return 0
    if (!g.dataTarget) return 0
    const days = daysBetween(todayIso(), g.dataTarget)
    if (days <= 0) return remaining
    return round2(remaining / (days / 30))
  }
</script>

{#if d}
  <div class="header">
    <Target size={18} />
    <h3>Obiective de economisire</h3>
    <button class="btn-add" onclick={addGoal}><Plus size={14} /> Adauga</button>
  </div>

  {#if goals.length === 0}
    <p class="empty">Niciun obiectiv definit. Adauga unul pentru a incepe sa urmaresti progresul.</p>
  {:else}
    <div class="goals-grid">
      {#each goals as g (g.id)}
        {@const pct = goalProgress(g)}
        {@const monthly = monthlyNeeded(g)}
        {@const done = pct >= 100}
        <div class="goal-card" class:done>
          <div class="goal-header">
            <input type="text" bind:value={g.label} onchange={markDirty} class="goal-name" />
            <button class="btn-del" onclick={() => removeGoal(g.id)}>x</button>
          </div>

          <div class="progress-bar">
            <div class="progress-fill" style="width: {pct}%"></div>
          </div>
          <div class="progress-label">{pct}% — {formatRON(g.contribuit || 0)} / {formatRON(g.sumaTarget)} RON</div>

          <div class="goal-fields">
            <label>Target<input type="number" bind:value={g.sumaTarget} onchange={markDirty} step="0.01" /></label>
            <label>Data target<input type="date" bind:value={g.dataTarget} onchange={markDirty} /></label>
          </div>

          {#if monthly > 0 && !done}
            <p class="monthly-hint">Trebuie ~{formatRON(monthly)} RON/luna</p>
          {/if}

          {#if !done}
            <div class="contribute-row">
              <input type="number" id="contrib-{g.id}" placeholder="Suma" step="0.01" />
              <button class="btn-contrib" onclick={() => {
                const input = document.getElementById('contrib-' + g.id)
                contribute(g, input.value)
                input.value = ''
              }}>+ Contribuie</button>
            </div>
          {:else}
            <p class="done-label">Obiectiv atins!</p>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
{/if}

<style>
  .header { display: flex; align-items: center; gap: var(--space-xs); margin-bottom: var(--space-md); color: var(--text); }
  .header h3 { font-size: var(--font-base); font-weight: 600; }
  .btn-add { margin-left: auto; display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; font-size: var(--font-tiny); color: var(--accent); }
  .btn-del { font-size: var(--font-tiny); color: var(--danger); opacity: 0.5; }
  .btn-del:hover { opacity: 1; }
  .empty { color: var(--text-dim); font-size: var(--font-small); }

  .goals-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--space-md); }

  .goal-card {
    padding: var(--space-md);
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
  }
  .goal-card.done { border-color: var(--success); }

  .goal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-xs); }
  .goal-name { font-size: var(--font-small); font-weight: 500; color: var(--text); background: transparent; border: none; border-bottom: 1px solid var(--border); padding: 2px 0; flex: 1; }

  .progress-bar { height: 8px; background: var(--bg-elevated); border-radius: var(--radius-full); overflow: hidden; margin-bottom: 4px; }
  .progress-fill { height: 100%; background: var(--accent); border-radius: var(--radius-full); transition: width var(--dur-base) var(--ease); }
  .goal-card.done .progress-fill { background: var(--success); }
  .progress-label { font-size: var(--font-tiny); color: var(--text-dim); margin-bottom: var(--space-xs); }

  .goal-fields { display: flex; gap: var(--space-sm); margin-bottom: var(--space-xs); }
  .goal-fields label { font-size: var(--font-tiny); color: var(--text-dim); display: flex; flex-direction: column; gap: 2px; flex: 1; }
  .goal-fields input { padding: 4px 6px; font-size: var(--font-tiny); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text); }

  .monthly-hint { font-size: var(--font-tiny); color: var(--warning); margin-bottom: var(--space-xs); }
  .done-label { font-size: var(--font-tiny); color: var(--success); font-weight: 500; }

  .contribute-row { display: flex; gap: 6px; }
  .contribute-row input { flex: 1; padding: 4px 6px; font-size: var(--font-tiny); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-xs); color: var(--text); }
  .btn-contrib { padding: 4px 10px; font-size: var(--font-tiny); color: var(--accent); white-space: nowrap; }
</style>
