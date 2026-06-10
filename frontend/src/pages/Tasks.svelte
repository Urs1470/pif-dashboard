<script>
  import { onMount } from 'svelte'
  import { ListTodo, Plus, Clock, CheckCircle2, ChevronDown, ChevronRight, Trash2, FileText } from '@lucide/svelte'
  import { globalTasks, loadGlobalTasks, updateGlobalTask, createGlobalTask, loadSubtasks, createSubtask, updateSubtask, deleteSubtask } from '../stores/tasks.svelte.js'
  import { timer, startGlobalTaskTimer, stopGlobalTaskTimer, loadActiveTimer } from '../stores/timer.svelte.js'
  import { TASK_STATUS_LABELS, STATUS_COLORS, formatDuration, formatDate, priorityColor } from '../lib/formatters.js'
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

  let expandedTask = $state(null)
  let subtasksCache = $state({})
  let newSubtaskTitle = $state('')
  let subtaskLoading = $state(false)

  let showDoneTasks = $state(false)

  const activeTasks = $derived(globalTasks.items.filter(t => t.status !== 'done'))
  const doneTasks = $derived(globalTasks.items.filter(t => t.status === 'done'))

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

  async function toggleTaskExpand(taskId) {
    if (expandedTask === taskId) {
      expandedTask = null
      return
    }
    expandedTask = taskId
    if (!subtasksCache[taskId]) {
      subtaskLoading = true
      try {
        const subs = await loadSubtasks(taskId)
        subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
      } catch (_) {
        subtasksCache = { ...subtasksCache, [taskId]: [] }
      } finally { subtaskLoading = false }
    }
  }

  async function toggleSubtaskDone(sub) {
    await updateSubtask(sub.id, { done: sub.done ? 0 : 1 })
    subtasksCache = {
      ...subtasksCache,
      [sub.task_id]: subtasksCache[sub.task_id].map(s => s.id === sub.id ? { ...s, done: s.done ? 0 : 1 } : s)
    }
  }

  async function addSubtask(taskId) {
    if (!newSubtaskTitle.trim()) return
    await createSubtask(taskId, newSubtaskTitle.trim())
    newSubtaskTitle = ''
    const subs = await loadSubtasks(taskId)
    subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
    await loadGlobalTasks({ arhiva: showArchive })
  }

  async function removeSubtask(sub) {
    await deleteSubtask(sub.id)
    subtasksCache = {
      ...subtasksCache,
      [sub.task_id]: (subtasksCache[sub.task_id] || []).filter(s => s.id !== sub.id)
    }
    await loadGlobalTasks({ arhiva: showArchive })
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
    <div class="task-list">
      {#each (showArchive ? globalTasks.items : activeTasks) as t (t.id)}
        <div class="trow-wrap">
          <div class="trow" class:done={t.status === 'done'} style="border-left-color: {t.prioritate ? priorityColor(t.prioritate) : 'var(--border)'}">
            <button class="check" onclick={() => toggleStatus(t)}>
              {#if t.status === 'done'}<CheckCircle2 size={18} />{:else}<div class="check-empty"></div>{/if}
            </button>
            <button class="tmain" onclick={() => toggleTaskExpand(t.id)}>
              <div class="ttitle-row">
                {#if expandedTask === t.id}<ChevronDown size={14} />{:else}<ChevronRight size={14} />{/if}
                <span class="ttitle">{t.titlu}</span>
                {#if t.descriere}<FileText size={12} class="tdesc-icon" />{/if}
              </div>
              <div class="tinfo">
                {#if t.categorie}<span class="task-cat">{t.categorie}</span>{/if}
                {#if t.timp_secunde}<span class="tmono">{formatDuration(t.timp_secunde)}</span>{/if}
                {#if t.subtask_total}
                  <span class="tsub-chip">{t.subtask_done || 0}/{t.subtask_total}</span>
                {/if}
                {#if t.data_scadenta}<span>{formatDate(t.data_scadenta)}</span>{/if}
              </div>
            </button>
            <div class="task-actions">
              <Badge label={TASK_STATUS_LABELS[t.status] || t.status} color={STATUS_COLORS[t.status] || 'var(--text-dim)'} small />
              <button class="timer-btn" class:active={timer.active?.global_task_id === t.id} onclick={() => toggleTimer(t)}>
                <Clock size={14} />
              </button>
            </div>
          </div>
          {#if expandedTask === t.id}
            <div class="subtask-body">
              {#if t.descriere}
                <div class="task-desc">{t.descriere}</div>
              {/if}
              {#if subtaskLoading && !subtasksCache[t.id]}
                <div class="sub-loading">Se incarca...</div>
              {:else}
                {#each (subtasksCache[t.id] || []) as sub (sub.id)}
                  <div class="sub-row" class:sub-done={sub.done}>
                    <button class="check" onclick={() => toggleSubtaskDone(sub)}>
                      {#if sub.done}<CheckCircle2 size={14} />{:else}<div class="check-empty small"></div>{/if}
                    </button>
                    <span class="sub-title">{sub.titlu}</span>
                    <button class="sub-del" onclick={() => removeSubtask(sub)}><Trash2 size={12} /></button>
                  </div>
                {/each}
                <div class="sub-add">
                  <input
                    type="text"
                    placeholder="Adauga subtask..."
                    bind:value={newSubtaskTitle}
                    onkeydown={(e) => { if (e.key === 'Enter') addSubtask(t.id) }}
                  />
                  <button class="sub-add-btn" disabled={!newSubtaskTitle.trim()} onclick={() => addSubtask(t.id)}>
                    <Plus size={14} />
                  </button>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}

      {#if !showArchive && doneTasks.length > 0}
        <button class="done-sep" onclick={() => showDoneTasks = !showDoneTasks}>
          {#if showDoneTasks}<ChevronDown size={14} />{:else}<ChevronRight size={14} />{/if}
          {doneTasks.length} finalizate
        </button>
        {#if showDoneTasks}
          {#each doneTasks as t (t.id)}
            <div class="trow-wrap">
              <div class="trow done" style="border-left-color: {t.prioritate ? priorityColor(t.prioritate) : 'var(--border)'}">
                <button class="check" onclick={() => toggleStatus(t)}>
                  <CheckCircle2 size={18} />
                </button>
                <button class="tmain" onclick={() => toggleTaskExpand(t.id)}>
                  <div class="ttitle-row">
                    {#if expandedTask === t.id}<ChevronDown size={14} />{:else}<ChevronRight size={14} />{/if}
                    <span class="ttitle">{t.titlu}</span>
                  </div>
                  <div class="tinfo">
                    {#if t.categorie}<span class="task-cat">{t.categorie}</span>{/if}
                    {#if t.timp_secunde}<span class="tmono">{formatDuration(t.timp_secunde)}</span>{/if}
                  </div>
                </button>
                <div class="task-actions">
                  <Badge label={TASK_STATUS_LABELS[t.status] || t.status} color={STATUS_COLORS[t.status] || 'var(--text-dim)'} small />
                  <button class="timer-btn" class:active={timer.active?.global_task_id === t.id} onclick={() => toggleTimer(t)}>
                    <Clock size={14} />
                  </button>
                </div>
              </div>
              {#if expandedTask === t.id}
                <div class="subtask-body">
                  {#if t.descriere}<div class="task-desc">{t.descriere}</div>{/if}
                  {#if subtaskLoading && !subtasksCache[t.id]}
                    <div class="sub-loading">Se incarca...</div>
                  {:else}
                    {#each (subtasksCache[t.id] || []) as sub (sub.id)}
                      <div class="sub-row" class:sub-done={sub.done}>
                        <button class="check" onclick={() => toggleSubtaskDone(sub)}>
                          {#if sub.done}<CheckCircle2 size={14} />{:else}<div class="check-empty small"></div>{/if}
                        </button>
                        <span class="sub-title">{sub.titlu}</span>
                        <button class="sub-del" onclick={() => removeSubtask(sub)}><Trash2 size={12} /></button>
                      </div>
                    {/each}
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        {/if}
      {/if}
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
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-h1); font-weight: 700; }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .toolbar { display: flex; gap: 4px; margin-bottom: var(--space-md); }
  .chip { padding: 4px 12px; font-size: var(--font-tiny); font-weight: 500; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid transparent; cursor: pointer; transition: all var(--dur-fast) var(--ease); }
  .chip:hover { background: var(--bg-hover); }
  .chip.active { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }

  .task-list { display: flex; flex-direction: column; }
  .trow-wrap { display: flex; flex-direction: column; }
  .trow { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-xs) var(--space-sm); border-left: 2px solid var(--border); border-radius: var(--radius-xs); margin-bottom: 2px; transition: background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); }
  .trow:hover { background: var(--bg-surface); transform: translateX(2px); }
  .trow.done { opacity: 0.5; }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; }
  .check:hover { color: var(--accent); }
  .trow.done .check { color: var(--success); }
  .check-empty { width: 18px; height: 18px; border: 2px solid var(--border); border-radius: 50%; }
  .check-empty.small { width: 14px; height: 14px; }
  .check:hover .check-empty { border-color: var(--accent); }
  .tmain { flex: 1; min-width: 0; cursor: pointer; text-align: left; }
  .ttitle-row { display: flex; align-items: center; gap: var(--space-xs); }
  .ttitle { font-size: var(--font-small); color: var(--text); font-weight: 500; }
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  :global(.tdesc-icon) { color: var(--text-faint); flex-shrink: 0; }
  .tinfo { display: flex; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; align-items: center; }
  .tmono { font-family: var(--font-mono); }
  .task-cat { padding: 0 6px; background: var(--bg-elevated); border-radius: var(--radius-xs); }
  .tsub-chip { padding: 1px 6px; border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent); font-weight: 600; font-size: 10px; }
  .task-actions { display: flex; align-items: center; gap: var(--space-xs); flex-shrink: 0; }
  .timer-btn { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; transition: all var(--dur-fast) var(--ease); -webkit-tap-highlight-color: transparent; flex-shrink: 0; }
  .timer-btn:hover { background: var(--bg-hover); color: var(--text); }
  .timer-btn.active { color: var(--accent); background: var(--accent-subtle); }

  .done-sep { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-xs); font-size: var(--font-tiny); font-weight: 600; color: var(--text-dim); cursor: pointer; margin-top: var(--space-sm); border-top: 1px solid var(--border-subtle); text-transform: uppercase; letter-spacing: 0.05em; }
  .done-sep:hover { color: var(--text-secondary); }

  .subtask-body { margin-left: 26px; padding: var(--space-sm) var(--space-sm) var(--space-sm) var(--space-md); border-left: 2px solid var(--accent-subtle); margin-bottom: var(--space-sm); }
  .task-desc { font-size: var(--font-small); color: var(--text-secondary); white-space: pre-wrap; line-height: 1.55; margin-bottom: var(--space-sm); padding-bottom: var(--space-sm); border-bottom: 1px solid var(--border-subtle); }
  .sub-row { display: flex; align-items: center; gap: var(--space-sm); padding: 3px 0; }
  .sub-row.sub-done .sub-title { text-decoration: line-through; color: var(--text-dim); }
  .sub-title { flex: 1; font-size: var(--font-small); color: var(--text); min-width: 0; }
  .sub-del { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: opacity var(--dur-fast); }
  .sub-row:hover .sub-del { opacity: 1; }
  .sub-del:hover { color: var(--danger); background: var(--danger-subtle); }
  .sub-add { display: flex; gap: var(--space-xs); margin-top: var(--space-xs); }
  .sub-add input { flex: 1; padding: 6px 10px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-small); }
  .sub-add-btn { width: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .sub-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
  .sub-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .sub-loading { font-size: var(--font-tiny); color: var(--text-dim); padding: var(--space-xs) 0; }

  .task-skeleton { padding: var(--space-sm) var(--space-md); }
  .modal-actions { display: flex; gap: var(--space-sm); justify-content: flex-end; margin-top: var(--space-lg); }

  @media (max-width: 768px) { .page { padding: var(--space-md); } }
</style>
