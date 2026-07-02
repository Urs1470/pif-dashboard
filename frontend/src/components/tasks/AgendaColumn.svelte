<script>
  import { priorityColor, priorityLabel } from '../../lib/formatters.js'

  let { tasks = [], onopen = () => {} } = $props()

  const DAY_SHORT = ['Dum', 'Lun', 'Mar', 'Mie', 'Joi', 'Vin', 'Sam']

  function sameDay(a, b) {
    return a.toDateString() === b.toDateString()
  }

  // Urmatoarele 7 zile, doar cele care au taskuri scadente (zilele goale se sar).
  const days = $derived.by(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const out = []
    for (let i = 0; i < 7; i++) {
      const d = new Date(today)
      d.setDate(today.getDate() + i)
      const dayTasks = tasks.filter(t => t.status !== 'done' && t.data_scadenta && sameDay(new Date(t.data_scadenta), d))
      if (!dayTasks.length) continue
      const dm = `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`
      out.push({
        key: `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`,
        isToday: i === 0,
        label: `${i === 0 ? 'Azi' : DAY_SHORT[d.getDay()]} · ${dm}`,
        tasks: dayTasks,
      })
    }
    return out
  })
</script>

<aside class="agenda cell-in">
  <div class="cell-label agenda-label"><span class="ico ico-vio">◔</span>Agenda — 7 zile</div>
  {#if days.length === 0}
    <div class="agenda-empty">Nicio scadenta in urmatoarele 7 zile.</div>
  {:else}
    {#each days as day (day.key)}
      <div class="day" class:today={day.isToday}>{day.label}</div>
      <div class="rowlist">
        {#each day.tasks as t (t.id)}
          <button class="row it" onclick={() => onopen(t)} title="Deschide taskul">
            <span class="it-title" class:it-today={day.isToday}>{t.titlu}</span>
            <span class="pr" style="color: {priorityColor(t.prioritate || 'normal')}; border-color: {priorityColor(t.prioritate || 'normal')}">{priorityLabel(t.prioritate || 'normal')}</span>
          </button>
        {/each}
      </div>
    {/each}
  {/if}
</aside>

<style>
  .agenda {
    position: sticky;
    top: 16px;
    display: flex;
    flex-direction: column;
    padding: var(--space-md);
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    min-width: 0;
  }
  .agenda-label { margin-bottom: var(--space-xs); }

  .day {
    font-size: var(--font-micro);
    font-weight: var(--fw-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-wide);
    color: var(--text-faint);
    padding: var(--space-sm) 2px 3px;
    margin-top: var(--space-xs);
    border-bottom: 1px solid var(--border-subtle);
  }
  .day.today { color: var(--accent); border-bottom-color: color-mix(in srgb, var(--accent) 35%, var(--border-subtle)); }

  .it {
    width: 100%;
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    padding: 7px 6px;
    text-align: left;
    cursor: pointer;
  }
  .it-title {
    flex: 1;
    min-width: 0;
    font-size: var(--font-tiny);
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .it:hover .it-title { color: var(--text); }
  .it-title.it-today { color: var(--text); font-weight: var(--fw-medium); }

  .pr {
    flex-shrink: 0;
    font-size: var(--font-micro);
    font-weight: var(--fw-semibold);
    padding: 0 6px;
    border: 1px solid;
    border-radius: var(--radius-full);
    white-space: nowrap;
  }

  .agenda-empty { font-size: var(--font-tiny); color: var(--text-dim); padding: var(--space-sm) 2px; }

  @media (max-width: 940px) {
    .agenda { position: static; }
  }
</style>
