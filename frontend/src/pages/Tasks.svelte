<script>
  import { onMount } from 'svelte'
  import { ListTodo, Plus, Clock, CheckCircle2 } from '@lucide/svelte'
  import { globalTasks, loadGlobalTasks, updateGlobalTask, createGlobalTask } from '../stores/tasks.svelte.js'
  import { timer, startGlobalTaskTimer, stopGlobalTaskTimer, loadActiveTimer } from '../stores/timer.svelte.js'
  import { TASK_STATUS_LABELS, STATUS_COLORS, formatDuration, formatDate } from '../lib/formatters.js'
  import Badge from '../components/ui/Badge.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import Button from '../components/ui/Button.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import Input from '../components/ui/Input.svelte'

  let showArchive = $state(false)
  let showNewModal = $state(false)
  let newTitle = $state('')
  let creating = $state(false)

  async function toggleStatus(task) {
    const next = task.status === 'done' ? 'to_do' : 'done'
    await updateGlobalTask(task.id, { status: next })
    await loadGlobalTasks({ arhiva: showArchive })
  }

  async function toggleTimer(task) {
    if (timer.active?.global_task_id === task.id) {
      await stopGlobalTaskTimer(task.id)
    } else {
      await startGlobalTaskTimer(task.id)
    }
    await loadActiveTimer()
  }

  async function handleCreate() {
    if (!newTitle.trim()) return
    creating = true
    try {
      await createGlobalTask({ titlu: newTitle.trim(), status: 'to_do' })
      newTitle = ''
      showNewModal = false
    } finally { creating = false }
  }

  onMount(() => { loadGlobalTasks(); loadActiveTimer() })
</script>

<div class="page">
  <div class="page-header">
    <div class="page-title-row">
      <ListTodo size={22} />
      <h1>Taskuri</h1>
      <span class="count">{globalTasks.items.length}</span>
    </div>
    <Button size="sm" onclick={() => showNewModal = true}><Plus size={14} /> Nou</Button>
  </div>

  <div class="toolbar">
    <button class="chip" class:active={!showArchive} onclick={() => { showArchive = false; loadGlobalTasks() }}>Active</button>
    <button class="chip" class:active={showArchive} onclick={() => { showArchive = true; loadGlobalTasks({ arhiva: true }) }}>Arhiva</button>
  </div>

  {#if globalTasks.loading}
    <div class="list">{#each Array(5) as _}<div class="task-skeleton"><Skeleton width="70%" height="16px" /></div>{/each}</div>
  {:else if globalTasks.items.length === 0}
    <EmptyState icon={ListTodo} title="Niciun task" description={showArchive ? 'Arhiva e goala.' : 'Adauga un task nou.'} />
  {:else}
    <div class="list">
      {#each globalTasks.items as t (t.id)}
        <div class="task-row" class:done={t.status === 'done'}>
          <button class="check" onclick={() => toggleStatus(t)}>
            {#if t.status === 'done'}<CheckCircle2 size={18} />{:else}<div class="check-empty"></div>{/if}
          </button>
          <div class="task-main">
            <div class="task-title">{t.titlu}</div>
            <div class="task-meta">
              {#if t.categorie}<span class="task-cat">{t.categorie}</span>{/if}
              {#if t.timp_secunde}<span>{formatDuration(t.timp_secunde)}</span>{/if}
              {#if t.data_scadenta}<span>{formatDate(t.data_scadenta)}</span>{/if}
            </div>
          </div>
          <div class="task-actions">
            <Badge label={TASK_STATUS_LABELS[t.status] || t.status} color={STATUS_COLORS[t.status] || 'var(--text-dim)'} small />
            <button class="timer-btn" class:active={timer.active?.global_task_id === t.id} onclick={() => toggleTimer(t)}>
              <Clock size={14} />
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<Modal bind:open={showNewModal} title="Task Nou" size="sm">
  <form onsubmit={(e) => { e.preventDefault(); handleCreate() }}>
    <Input label="Titlu" bind:value={newTitle} placeholder="Ce ai de facut?" />
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showNewModal = false}>Anuleaza</Button>
      <Button loading={creating} disabled={!newTitle.trim()} onclick={handleCreate}>Creeaza</Button>
    </div>
  </form>
</Modal>

<style>
  .page { padding: var(--space-lg); max-width: 900px; }
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-h1); font-weight: 700; }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .toolbar { display: flex; gap: 4px; margin-bottom: var(--space-md); }
  .chip { padding: 4px 12px; font-size: var(--font-tiny); font-weight: 500; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid transparent; cursor: pointer; transition: all var(--dur-fast) var(--ease); }
  .chip:hover { background: var(--bg-hover); }
  .chip.active { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }

  .list { display: flex; flex-direction: column; }
  .task-row { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) var(--space-md); border-radius: var(--radius-sm); transition: background var(--dur-fast) var(--ease); }
  .task-row:hover { background: var(--bg-surface); }
  .task-row + .task-row { border-top: 1px solid var(--border); }
  .task-row.done { opacity: 0.6; }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; }
  .check:hover { color: var(--accent); }
  .task-row.done .check { color: var(--success); }
  .check-empty { width: 18px; height: 18px; border: 2px solid var(--border); border-radius: 50%; }
  .check:hover .check-empty { border-color: var(--accent); }
  .task-main { flex: 1; min-width: 0; }
  .task-title { font-size: var(--font-small); color: var(--text); font-weight: 500; }
  .task-row.done .task-title { text-decoration: line-through; color: var(--text-dim); }
  .task-meta { display: flex; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; }
  .task-cat { padding: 0 6px; background: var(--bg-elevated); border-radius: var(--radius-xs); }
  .task-actions { display: flex; align-items: center; gap: var(--space-xs); flex-shrink: 0; }
  .timer-btn { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; transition: all var(--dur-fast) var(--ease); -webkit-tap-highlight-color: transparent; flex-shrink: 0; }
  .timer-btn:hover { background: var(--bg-hover); color: var(--text); }
  .timer-btn.active { color: var(--accent); background: var(--accent-subtle); }
  .task-skeleton { padding: var(--space-sm) var(--space-md); }
  .modal-actions { display: flex; gap: var(--space-sm); justify-content: flex-end; margin-top: var(--space-lg); }

  @media (max-width: 768px) { .page { padding: var(--space-md); } }
</style>
