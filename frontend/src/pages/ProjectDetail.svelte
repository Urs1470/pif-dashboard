<script>
  import { onMount } from 'svelte'
  import { ArrowLeft, Clock, Play, Square, Plus, CheckCircle2, Wrench, BookOpen, ListTodo, ClipboardList, Settings2 } from '@lucide/svelte'
  import { loadProjectDetail, loadProjectTasks, loadProjectJournal, loadProjectEquipment, loadProjectChecklist } from '../stores/projects.svelte.js'
  import { updateTask, createTask } from '../stores/tasks.svelte.js'
  import { timer, startProjectTimer, stopProjectTimer, startTaskTimer, stopTaskTimer, loadActiveTimer } from '../stores/timer.svelte.js'
  import { PROJECT_STATUS_LABELS, TASK_STATUS_LABELS, STATUS_COLORS, formatDate, formatDuration } from '../lib/formatters.js'
  import { navigate } from '../lib/router.svelte.js'
  import Badge from '../components/ui/Badge.svelte'
  import Card from '../components/ui/Card.svelte'
  import Button from '../components/ui/Button.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import Input from '../components/ui/Input.svelte'

  let { params } = $props()
  let project = $state(null)
  let tasks = $state([])
  let journal = $state([])
  let equipment = $state([])
  let checklist = $state([])
  let loading = $state(true)
  let error = $state(null)
  let activeTab = $state('tasks')
  let showNewTask = $state(false)
  let newTaskTitle = $state('')
  let creatingTask = $state(false)

  const tabs = [
    { key: 'tasks', label: 'Taskuri', icon: ListTodo },
    { key: 'journal', label: 'Jurnal', icon: BookOpen },
    { key: 'equipment', label: 'Echipamente', icon: Wrench },
    { key: 'checklist', label: 'Checklist', icon: ClipboardList },
    { key: 'info', label: 'Info', icon: Settings2 },
  ]

  async function load() {
    loading = true
    try {
      project = await loadProjectDetail(params.id)
      const [t, j, e, c] = await Promise.all([
        loadProjectTasks(params.id).catch(() => []),
        loadProjectJournal(params.id).catch(() => []),
        loadProjectEquipment(params.id).catch(() => []),
        loadProjectChecklist(params.id).catch(() => []),
      ])
      tasks = Array.isArray(t) ? t : t.tasks || []
      journal = Array.isArray(j) ? j : j.entries || []
      equipment = Array.isArray(e) ? e : e.echipamente || []
      checklist = Array.isArray(c) ? c : c.items || c.checklist || []
    } catch (err) {
      error = err.message
    } finally { loading = false }
  }

  async function toggleTaskStatus(task) {
    const next = task.status === 'done' ? 'to_do' : 'done'
    await updateTask(task.id, { status: next })
    tasks = tasks.map(t => t.id === task.id ? { ...t, status: next } : t)
  }

  async function handleProjectTimer() {
    if (timer.active?.proiect_id === params.id && !timer.active?.task_id) await stopProjectTimer(params.id)
    else await startProjectTimer(params.id)
    await loadActiveTimer()
  }

  async function handleTaskTimer(taskId) {
    if (timer.active?.task_id === taskId) await stopTaskTimer(taskId)
    else await startTaskTimer(taskId)
    await loadActiveTimer()
  }

  async function handleCreateTask() {
    if (!newTaskTitle.trim()) return
    creatingTask = true
    try {
      await createTask(params.id, { titlu: newTaskTitle.trim(), status: 'to_do' })
      newTaskTitle = ''
      showNewTask = false
      const t = await loadProjectTasks(params.id)
      tasks = Array.isArray(t) ? t : t.tasks || []
    } finally { creatingTask = false }
  }

  onMount(() => { load(); loadActiveTimer() })

  const tasksDone = $derived(tasks.filter(t => t.status === 'done' || t.status === 'finalizat').length)
  const projectTimerActive = $derived(timer.active?.proiect_id === params.id && !timer.active?.task_id)
</script>

<div class="page">
  <button class="back" onclick={() => navigate('/projects')}><ArrowLeft size={16} /> Proiecte</button>

  {#if loading}
    <Skeleton width="60%" height="24px" />
  {:else if error}
    <Card><p class="error-text">Eroare: {error}</p></Card>
  {:else if project}
    <div class="project-header">
      <div class="header-top">
        <div class="title-area">
          {#if project.tip}<span class="tip" class:pif={project.tip === 'PIF'}>{project.tip}</span>{/if}
          <h1>{project.nume || '—'}</h1>
          <Badge label={PROJECT_STATUS_LABELS[project.status] || project.status || '—'} color={STATUS_COLORS[project.status] || 'var(--text-dim)'} />
        </div>
        <Button variant={projectTimerActive ? 'danger' : 'secondary'} size="sm" onclick={handleProjectTimer}>
          {#if projectTimerActive}<Square size={14} /> Opreste{:else}<Play size={14} /> Timer{/if}
        </Button>
      </div>
      <div class="meta">
        {#if project.client}<span>{project.client}</span>{/if}
        {#if project.echipament_principal}<span>· {project.echipament_principal}</span>{/if}
        {#if project.cod_proiect}<span>· {project.cod_proiect}</span>{/if}
      </div>
      <div class="pstats">
        <div class="ps"><span class="ps-val">{tasks.length}</span><span class="ps-lbl">taskuri</span></div>
        <div class="ps"><span class="ps-val">{tasksDone}</span><span class="ps-lbl">finalizate</span></div>
        {#if project.deadline}<div class="ps"><span class="ps-val">{formatDate(project.deadline)}</span><span class="ps-lbl">deadline</span></div>{/if}
      </div>
    </div>

    <div class="tabs">
      {#each tabs as tab}
        <button class="tab" class:active={activeTab === tab.key} onclick={() => activeTab = tab.key}>
          <tab.icon size={14} />
          {tab.label}
          {#if tab.key === 'tasks'}<span class="tab-count">{tasks.length}</span>{/if}
        </button>
      {/each}
    </div>

    <div class="tab-content">
      {#if activeTab === 'tasks'}
        <div class="tab-header">
          <span class="tab-sub">{tasksDone}/{tasks.length} finalizate</span>
          <Button size="sm" variant="secondary" onclick={() => showNewTask = true}><Plus size={14} /> Task</Button>
        </div>
        {#if tasks.length === 0}<p class="empty">Niciun task.</p>
        {:else}
          <div class="task-list">
            {#each tasks as t (t.id)}
              <div class="trow" class:done={t.status === 'done' || t.status === 'finalizat'}>
                <button class="check" onclick={() => toggleTaskStatus(t)}>
                  {#if t.status === 'done' || t.status === 'finalizat'}<CheckCircle2 size={16} />{:else}<div class="check-empty"></div>{/if}
                </button>
                <div class="tmain">
                  <div class="ttitle">{t.titlu}</div>
                  <div class="tinfo">
                    <Badge label={TASK_STATUS_LABELS[t.status] || t.status} color={STATUS_COLORS[t.status] || 'var(--text-dim)'} small />
                    {#if t.timp_secunde}<span>{formatDuration(t.timp_secunde)}</span>{/if}
                    {#if t.subtask_total}<span>{t.subtask_done}/{t.subtask_total}</span>{/if}
                  </div>
                </div>
                <button class="timer-btn" class:active={timer.active?.task_id === t.id} onclick={() => handleTaskTimer(t.id)}><Clock size={14} /></button>
              </div>
            {/each}
          </div>
        {/if}

      {:else if activeTab === 'journal'}
        {#if journal.length === 0}<p class="empty">Nicio intrare.</p>
        {:else}
          <div class="jlist">{#each journal as j}
            <div class="jentry">
              <div class="jdate">{formatDate(j.created_at || j.data)}</div>
              <div class="jtext">{j.continut || j.content || '—'}</div>
              {#if j.ore}<div class="jhours"><Clock size={12} /> {j.ore}h</div>{/if}
            </div>
          {/each}</div>
        {/if}

      {:else if activeTab === 'equipment'}
        {#if equipment.length === 0}<p class="empty">Niciun echipament.</p>
        {:else}
          <div class="elist">{#each equipment as e}
            <Card>
              <div class="ename">{e.tip || '—'} — {e.producator || '—'}</div>
              <div class="edetails">
                {#if e.model}<span>Model: {e.model}</span>{/if}
                {#if e.serie}<span>Serie: {e.serie}</span>{/if}
                {#if e.putere}<span>Putere: {e.putere}</span>{/if}
              </div>
            </Card>
          {/each}</div>
        {/if}

      {:else if activeTab === 'checklist'}
        {#if checklist.length === 0}<p class="empty">Checklist gol.</p>
        {:else}
          {#each checklist as item}
            <div class="clrow" class:done={item.bifat || item.done}>
              <span class="clcheck">{(item.bifat || item.done) ? '✓' : '○'}</span>
              <div><div class="cllabel">{item.element || item.label || '—'}</div>{#if item.categorie}<div class="clcat">{item.categorie}</div>{/if}</div>
            </div>
          {/each}
        {/if}

      {:else if activeTab === 'info'}
        <div class="igrid">
          {#each [['Client', project.client], ['Locatie', project.locatie], ['Echipament', project.echipament_principal], ['Producator', project.producator], ['Cod proiect', project.cod_proiect], ['PM', project.pm], ['Nr. comanda', project.nr_comanda], ['Data incepere', formatDate(project.data_incepere)], ['Deadline', formatDate(project.deadline)]] as [label, val]}
            <div class="irow"><span class="ilabel">{label}</span><span>{val || '—'}</span></div>
          {/each}
          {#if project.observatii}<div class="ifull"><span class="ilabel">Observatii</span><p>{project.observatii}</p></div>{/if}
          {#if project.service_before}<div class="ifull"><span class="ilabel">Service Before</span><p>{project.service_before}</p></div>{/if}
          {#if project.service_after}<div class="ifull"><span class="ilabel">Service After</span><p>{project.service_after}</p></div>{/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

<Modal bind:open={showNewTask} title="Task Nou" size="sm">
  <form onsubmit={(e) => { e.preventDefault(); handleCreateTask() }}>
    <Input label="Titlu" bind:value={newTaskTitle} placeholder="Descrie taskul..." />
    <div class="modal-actions"><Button variant="secondary" onclick={() => showNewTask = false}>Anuleaza</Button><Button loading={creatingTask} disabled={!newTaskTitle.trim()} onclick={handleCreateTask}>Creeaza</Button></div>
  </form>
</Modal>

<style>
  .page { padding: var(--space-lg); }
  .back { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-small); color: var(--text-dim); margin-bottom: var(--space-md); cursor: pointer; }
  .back:hover { color: var(--accent); }

  .project-header { margin-bottom: var(--space-lg); }
  .header-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-md); }
  .title-area { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }
  .title-area h1 { font-size: var(--font-h1); font-weight: 700; color: var(--text); }
  .tip { font-size: 10px; font-weight: 600; text-transform: uppercase; padding: 2px 8px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-secondary); }
  .tip.pif { background: var(--accent-subtle); color: var(--accent); }
  .meta { font-size: var(--font-small); color: var(--text-dim); margin-top: 4px; display: flex; gap: var(--space-xs); }
  .pstats { display: flex; gap: var(--space-lg); margin-top: var(--space-md); padding: var(--space-md); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); }
  .ps { text-align: center; }
  .ps-val { display: block; font-size: var(--font-h2); font-weight: 700; color: var(--text); }
  .ps-lbl { font-size: var(--font-tiny); color: var(--text-dim); text-transform: uppercase; }

  .tabs { display: flex; border-bottom: 1px solid var(--border); margin-bottom: var(--space-md); overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
  .tabs::-webkit-scrollbar { display: none; }
  .tab { display: flex; align-items: center; gap: 4px; padding: var(--space-sm) var(--space-md); font-size: var(--font-small); font-weight: 500; color: var(--text-secondary); border-bottom: 2px solid transparent; cursor: pointer; white-space: nowrap; min-height: 44px; -webkit-tap-highlight-color: transparent; }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab-count { font-size: 10px; padding: 0 5px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .tab-content { min-height: 200px; }
  .tab-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-sm); }
  .tab-sub { font-size: var(--font-tiny); color: var(--text-dim); }
  .empty { color: var(--text-dim); font-size: var(--font-small); padding: var(--space-lg) 0; text-align: center; }
  .error-text { color: var(--danger); }

  .task-list { display: flex; flex-direction: column; }
  .trow { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
  .trow.done { opacity: 0.5; }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; }
  .check:hover { color: var(--accent); }
  .trow.done .check { color: var(--success); }
  .check-empty { width: 16px; height: 16px; border: 2px solid var(--border); border-radius: 50%; }
  .tmain { flex: 1; min-width: 0; }
  .ttitle { font-size: var(--font-small); color: var(--text); font-weight: 500; }
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  .tinfo { display: flex; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; align-items: center; }
  .timer-btn { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; -webkit-tap-highlight-color: transparent; flex-shrink: 0; }
  .timer-btn:hover { background: var(--bg-hover); color: var(--text); }
  .timer-btn.active { color: var(--accent); background: var(--accent-subtle); }

  .jlist { display: flex; flex-direction: column; gap: var(--space-sm); }
  .jentry { padding: var(--space-sm) var(--space-md); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-sm); }
  .jdate { font-size: var(--font-tiny); color: var(--text-dim); margin-bottom: 4px; }
  .jtext { font-size: var(--font-small); color: var(--text); line-height: 1.5; }
  .jhours { font-size: var(--font-tiny); color: var(--accent); margin-top: 4px; display: flex; align-items: center; gap: 4px; }

  .elist { display: flex; flex-direction: column; gap: var(--space-sm); }
  .ename { font-size: var(--font-small); font-weight: 500; color: var(--text); }
  .edetails { display: flex; gap: var(--space-md); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 4px; }

  .clrow { display: flex; gap: var(--space-sm); padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
  .clrow.done { opacity: 0.5; }
  .clcheck { color: var(--text-dim); width: 20px; flex-shrink: 0; }
  .clrow.done .clcheck { color: var(--success); }
  .cllabel { font-size: var(--font-small); color: var(--text); }
  .clcat { font-size: var(--font-tiny); color: var(--text-dim); }

  .igrid { display: flex; flex-direction: column; gap: var(--space-sm); }
  .irow { display: flex; justify-content: space-between; font-size: var(--font-small); padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
  .ilabel { color: var(--text-dim); font-weight: 500; }
  .ifull { display: flex; flex-direction: column; gap: 4px; padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
  .ifull p { font-size: var(--font-small); color: var(--text-secondary); line-height: 1.5; white-space: pre-wrap; }

  .modal-actions { display: flex; gap: var(--space-sm); justify-content: flex-end; margin-top: var(--space-lg); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .pstats { gap: var(--space-md); flex-wrap: wrap; }
    .header-top { flex-direction: column; }
    .edetails { flex-wrap: wrap; gap: var(--space-sm); }
    .trow { padding: var(--space-sm) 0; }
    .back { min-height: 44px; }
  }
</style>
