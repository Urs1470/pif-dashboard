<script>
  import { onMount } from 'svelte'
  import { slide } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { motionDuration, DUR_BASE } from '../lib/motion.svelte.js'
  import { ListTodo, Plus, CheckCircle2, ChevronDown, ChevronRight, Repeat, Search, Paperclip } from '@lucide/svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import { globalTasks, loadGlobalTasks, updateGlobalTask, createGlobalTask, deleteGlobalTask, loadSubtasks, createSubtask, updateSubtask, deleteSubtask, loadTaskAttachments, uploadTaskAttachment, deleteTaskAttachment } from '../stores/tasks.svelte.js'
  import { TASK_STATUS_LABELS, STATUS_COLORS, formatDate, priorityColor, priorityLabel, isFutureRecurrence } from '../lib/formatters.js'
  import { toast } from '../stores/ui.svelte.js'
  import { router } from '../lib/router.svelte.js'
  import { focusOnLand, focusKey } from '../lib/focus.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import Button from '../components/ui/Button.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import Input from '../components/ui/Input.svelte'
  import Textarea from '../components/ui/Textarea.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import Select from '../components/ui/Select.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  import RichTextEditor from '../components/ui/RichTextEditor.svelte'
  import AttachmentPreview from '../components/ui/AttachmentPreview.svelte'
  import RichText from '../components/ui/RichText.svelte'
  import AgendaColumn from '../components/tasks/AgendaColumn.svelte'

  let showArchive = $state(false)
  let taskDeleteId = $state(null)
  let showTaskDelete = $state(false)
  let showNewModal = $state(false)
  let creating = $state(false)

  let formTitle = $state('')
  let formDesc = $state('')
  let formPriority = $state('Normal')
  let formCategory = $state('General')
  let formDeadline = $state('')
  let formRecurenta = $state('')
  let editingTask = $state(null)
  let showEditModal = $state(false)

  let expandedTask = $state(null)
  let subtasksCache = $state({})
  let newSubtaskTitle = $state('')
  let subtaskLoading = $state(false)

  let showDoneTasks = $state(false)
  let taskSearch = $state('')
  let statusFilter = $state('')
  let quickTitle = $state('')
  let quickAdding = $state(false)
  let showNoteModal = $state(false)
  let noteTask = $state(null)
  let noteDraft = $state('')
  let noteSaving = $state(false)

  let attCache = $state({})
  let attInput = $state(null)
  let attUploadTaskId = null
  let attUploading = $state(false)
  let attDeleteId = $state(null)
  let attDeleteTaskId = $state(null)
  let showAttDelete = $state(false)
  let attPreviewOpen = $state(false)
  let attPreviewAtt = $state(null)
  let attPreviewTaskId = null

  const STATUS_CYCLE = ['to_do', 'in_lucru', 'done']
  const STATUS_FILTER_OPTIONS = [
    { value: '', label: 'Toate' },
    { value: 'to_do', label: 'To Do' },
    { value: 'in_lucru', label: 'In Lucru' },
  ]

  function matchesSearch(t) {
    if (!taskSearch) return true
    const q = taskSearch.toLowerCase()
    return (t.titlu || '').toLowerCase().includes(q) ||
           (t.descriere || '').toLowerCase().includes(q) ||
           (t.categorie || '').toLowerCase().includes(q)
  }

  const filteredTasks = $derived(
    globalTasks.items.filter(t => {
      if (statusFilter && t.status !== statusFilter) return false
      return matchesSearch(t)
    })
  )
  // Hide a recurring task's next occurrence until its scadenta arrives, so finalizing
  // today's instance doesn't look like an identical unchecked copy reappearing.
  const activeTasks = $derived(filteredTasks.filter(t => t.status !== 'done' && !isFutureRecurrence(t)))
  const doneTasks = $derived(filteredTasks.filter(t => t.status === 'done'))

  // Deep-link to a finalized task: auto-open the (collapsed-by-default) done section
  // so its row mounts and focusOnLand can scroll/flash it instead of silently no-op'ing.
  $effect(() => {
    const f = router.query.focus
    if (!f || !f.startsWith('global:')) return
    const id = f.slice('global:'.length)
    if (doneTasks.some(t => String(t.id) === id)) showDoneTasks = true
  })

  async function toggleStatus(task) {
    const next = task.status === 'done' ? 'to_do' : 'done'
    const res = await updateGlobalTask(task.id, { status: next })
    await loadGlobalTasks({ arhiva: showArchive })
    if (res?.recurring_spawned) {
      toast(`Finalizat ✓ — următoarea apariție: ${formatDate(res.recurring_next)}`, 'success')
    }
  }

  function resetForm() {
    formTitle = ''; formDesc = ''; formPriority = 'Normal'
    formCategory = 'General'; formDeadline = ''; formRecurenta = ''
  }

  function openNewModal() {
    resetForm()
    showNewModal = true
  }

  function openEditModal(t) {
    editingTask = t
    formTitle = t.titlu || ''
    formDesc = t.descriere || ''
    formPriority = t.prioritate || 'Normal'
    formCategory = t.categorie || 'General'
    formDeadline = t.data_scadenta || ''
    formRecurenta = t.recurenta || ''
    showEditModal = true
  }

  async function handleCreate() {
    if (!formTitle.trim()) return
    creating = true
    try {
      await createGlobalTask({
        titlu: formTitle.trim(),
        descriere: formDesc.trim() || undefined,
        prioritate: formPriority,
        categorie: formCategory,
        data_scadenta: formDeadline || undefined,
        recurenta: formRecurenta || undefined,
        status: 'to_do',
      })
      resetForm()
      showNewModal = false
    } finally { creating = false }
  }

  async function quickAdd() {
    if (!quickTitle.trim() || quickAdding) return
    quickAdding = true
    try {
      await createGlobalTask({ titlu: quickTitle.trim(), status: 'to_do' })
      quickTitle = ''
    } finally { quickAdding = false }
  }

  async function loadAtt(taskId, force = false) {
    if (force || !attCache[taskId]) {
      attCache = { ...attCache, [taskId]: await loadTaskAttachments(taskId, true).catch(() => attCache[taskId] || []) }
    }
  }

  function triggerAttUpload(taskId) {
    attUploadTaskId = taskId
    attInput?.click()
  }

  function openAttPreview(att, taskId) {
    attPreviewAtt = att
    attPreviewTaskId = taskId
    attPreviewOpen = true
  }

  function attPreviewDelete(att) {
    attDeleteId = att.id
    attDeleteTaskId = attPreviewTaskId
    showAttDelete = true
  }

  async function onAttFiles(e) {
    const files = Array.from(e.target.files || [])
    e.target.value = ''
    if (!files.length || !attUploadTaskId) return
    const taskId = attUploadTaskId
    attUploading = true
    try {
      for (const f of files) await uploadTaskAttachment(taskId, f, true)
      toast(files.length === 1 ? 'Fisier atasat' : `${files.length} fisiere atasate`, 'success')
      await Promise.all([loadAtt(taskId, true), loadGlobalTasks({ arhiva: showArchive })])
    } catch (err) {
      toast(`Eroare: ${err.message}`, 'error')
    } finally { attUploading = false }
  }

  async function doDeleteAtt() {
    if (!attDeleteId) return
    try {
      await deleteTaskAttachment(attDeleteId)
      toast('Atasament sters', 'success')
      const taskId = attDeleteTaskId
      attDeleteId = null
      attDeleteTaskId = null
      if (taskId) await Promise.all([loadAtt(taskId, true), loadGlobalTasks({ arhiva: showArchive })])
    } catch (err) {
      toast(`Eroare: ${err.message}`, 'error')
    }
  }

  function openNoteModal(t) {
    noteTask = t
    noteDraft = t.descriere || ''
    showNoteModal = true
  }

  async function saveNote() {
    if (noteSaving || !noteTask) return
    noteSaving = true
    try {
      await updateGlobalTask(noteTask.id, { descriere: noteDraft })
      showNoteModal = false
      await loadGlobalTasks({ arhiva: showArchive })
      toast('Salvat', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { noteSaving = false }
  }

  async function handleEdit() {
    if (!editingTask || !formTitle.trim()) return
    creating = true
    try {
      await updateGlobalTask(editingTask.id, {
        titlu: formTitle.trim(),
        descriere: formDesc.trim(),
        prioritate: formPriority,
        categorie: formCategory,
        data_scadenta: formDeadline,
        recurenta: formRecurenta || null,
      })
      showEditModal = false
      editingTask = null
      await loadGlobalTasks({ arhiva: showArchive })
    } finally { creating = false }
  }

  async function toggleTaskExpand(taskId) {
    if (expandedTask === taskId) {
      expandedTask = null
      return
    }
    expandedTask = taskId
    loadAtt(taskId)
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

  async function doDeleteTask() {
    if (!taskDeleteId) return
    await deleteGlobalTask(taskDeleteId)
    taskDeleteId = null
    await loadGlobalTasks({ arhiva: showArchive })
    toast('Task sters', 'success')
  }

  const PRIO_CYCLE = ['normal', 'minor', 'urgent']
  async function cycleTaskPriority(t) {
    const cur = (t.prioritate || 'normal').toLowerCase()
    const next = PRIO_CYCLE[(PRIO_CYCLE.indexOf(cur) + 1) % PRIO_CYCLE.length]
    await updateGlobalTask(t.id, { prioritate: next })
    await loadGlobalTasks({ arhiva: showArchive })
  }

  async function cycleTaskStatus(t) {
    const cur = t.status || 'to_do'
    const next = STATUS_CYCLE[(STATUS_CYCLE.indexOf(cur) + 1) % STATUS_CYCLE.length]
    await updateGlobalTask(t.id, { status: next })
    await loadGlobalTasks({ arhiva: showArchive })
  }

  function isOverdue(d) {
    if (!d) return false
    return new Date(d) < new Date(new Date().toDateString())
  }
  function isToday(d) {
    if (!d) return false
    return new Date(d).toDateString() === new Date().toDateString()
  }
  function isSoon(d) {
    if (!d) return false
    const diff = (new Date(d) - new Date(new Date().toDateString())) / 86400000
    return diff > 0 && diff <= 7
  }

  // Banda hero V3: taskuri urgente si/sau scadente azi / intarziate (max 4), din itemele deja incarcate.
  const urgentHero = $derived(
    activeTasks
      .filter(t => (t.prioritate || '').toLowerCase() === 'urgent' || isOverdue(t.data_scadenta) || isToday(t.data_scadenta))
      .slice(0, 4)
  )

  function heroLabel(t) {
    const urgent = (t.prioritate || '').toLowerCase() === 'urgent'
    if (isOverdue(t.data_scadenta)) return urgent ? 'Urgent · intarziat' : 'Intarziat'
    if (isToday(t.data_scadenta)) return urgent ? 'Urgent · azi' : 'Scadent azi'
    return 'Urgent'
  }

  // Bordura stanga a randului, dupa prioritate (danger=urgent, accent=normal, discret=minor).
  function rowBorderColor(p) {
    const key = (p || '').toLowerCase()
    if (key === 'urgent') return 'var(--danger)'
    if (key === 'normal') return 'var(--accent)'
    if (key === 'minor') return 'var(--border-strong)'
    return 'var(--border)'
  }

  onMount(() => { loadGlobalTasks() })
</script>

{#snippet taskDetail(t)}
  {@const subs = subtasksCache[t.id] || []}
  {@const atts = attCache[t.id] || []}
  {@const doneCount = subs.filter(s => s.done).length}

  {#if t.descriere}
    <div class="note-block">
      <RichText value={t.descriere} class="note-content" collapsible maxHeight={200} />
      <button class="note-edit-btn" title="Editeaza notite" onclick={() => openNoteModal(t)}><SolidIcon name="pencil" size={12} /> Editeaza</button>
    </div>
  {/if}

  {#if atts.length}
    <div class="att-row">
      {#each atts as a (a.id)}
        <span class="att-chip">
          <button class="att-open" title="{a.nume_fisier} ({a.tip_fisier})" onclick={() => openAttPreview(a, t.id)}>
            <Paperclip size={11} /><span class="att-fname">{a.nume_fisier}</span>
          </button>
          <button class="att-del" title="Sterge atasament" onclick={() => { attDeleteId = a.id; attDeleteTaskId = t.id; showAttDelete = true }}><SolidIcon name="trash" size={11} /></button>
        </span>
      {/each}
    </div>
  {/if}

  <div class="detail-actions">
    {#if !t.descriere}
      <button class="detail-chip" onclick={() => openNoteModal(t)}><SolidIcon name="notes" size={13} /> Descriere</button>
    {/if}
    <button class="detail-chip" onclick={() => triggerAttUpload(t.id)} disabled={attUploading}><Paperclip size={13} /> {attUploading ? 'Se incarca…' : 'Fisier'}</button>
  </div>

  <div class="sub-section">
    <div class="sub-head">
      <span class="sub-cap">Subtaskuri</span>
      {#if subs.length}<span class="sub-prog">{doneCount}/{subs.length}</span>{/if}
    </div>
    {#if subtaskLoading && !subtasksCache[t.id]}
      <div class="sub-loading">Se incarca...</div>
    {:else}
      {#each subs as sub (sub.id)}
        <div class="sub-row" class:sub-done={sub.done} animate:flip={{ duration: motionDuration(DUR_BASE) }} transition:slide|local={{ duration: motionDuration(DUR_BASE) }}>
          <button class="check" onclick={() => toggleSubtaskDone(sub)}>
            {#if sub.done}<CheckCircle2 size={14} />{:else}<div class="check-empty small"></div>{/if}
          </button>
          <span class="sub-title">{sub.titlu}</span>
          <button class="sub-del" onclick={() => removeSubtask(sub)}><SolidIcon name="trash" size={12} /></button>
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
{/snippet}

<div class="page">
  <div class="page-header">
    <div class="page-title-row">
      <ListTodo size={22} />
      <h1>Taskuri</h1>
      <span class="count">{globalTasks.items.length}</span>
    </div>
    <Button size="sm" onclick={openNewModal}><Plus size={14} /> Nou</Button>
  </div>

  <div class="toolbar">
    <div class="search-box">
      <Search size={14} />
      <input type="text" placeholder="Cauta taskuri..." bind:value={taskSearch} />
    </div>
    <div class="filters">
      {#each STATUS_FILTER_OPTIONS as opt}
        <button class="chip" class:active={statusFilter === opt.value} onclick={() => statusFilter = opt.value}>{opt.label}</button>
      {/each}
      <span class="filter-sep"></span>
      <button class="chip" class:active={!showArchive} onclick={() => { showArchive = false; loadGlobalTasks() }}>Active</button>
      <button class="chip" class:active={showArchive} onclick={() => { showArchive = true; loadGlobalTasks({ arhiva: true }) }}>Arhiva</button>
    </div>
  </div>

  {#if !showArchive && !globalTasks.loading && urgentHero.length > 0}
    <div class="urgent-band">
      {#each urgentHero as t (t.id)}
        <section class="ucard cell-in">
          <div class="cell-label"><span class="ico ico-red">!</span>{heroLabel(t)}</div>
          <button class="ucard-title" onclick={() => toggleTaskExpand(t.id)} title="Deschide detalii">{t.titlu}</button>
          <div class="ucard-sub">
            <span>{t.categorie || 'General'}</span>
            {#if t.data_scadenta}<span class="ucard-dot">·</span><span>{formatDate(t.data_scadenta)}</span>{/if}
            {#if t.subtask_total}<span class="ucard-dot">·</span><span>{t.subtask_done || 0}/{t.subtask_total} subtaskuri</span>{/if}
          </div>
          <div class="ucard-actions">
            <button class="ucard-btn" onclick={() => toggleStatus(t)}>✓ Bifeaza</button>
          </div>
        </section>
      {/each}
    </div>
  {/if}

  <div class="v3grid">
  <div class="list-cell cell-in">
  <div class="cell-label list-label"><span class="ico ico-amber">≔</span>{showArchive ? 'Taskuri arhivate' : 'Lista taskuri'}<span class="tail">{showArchive ? globalTasks.items.length : activeTasks.length}</span></div>
  {#if !showArchive}
    <form class="quick-add" onsubmit={(e) => { e.preventDefault(); quickAdd() }}>
      <input type="text" placeholder="Task rapid... Enter pentru a adauga" bind:value={quickTitle} disabled={quickAdding} />
      <button type="submit" class="quick-add-btn" disabled={!quickTitle.trim() || quickAdding} title="Adauga task"><Plus size={16} /></button>
    </form>
  {/if}

  {#if globalTasks.loading}
    <div class="list">{#each Array(5) as _}<div class="task-skeleton"><Skeleton width="70%" height="16px" /></div>{/each}</div>
  {:else if globalTasks.items.length === 0}
    <EmptyState icon={ListTodo} title="Niciun task" description={showArchive ? 'Arhiva e goala.' : 'Adauga un task nou.'} />
  {:else}
    <div class="task-list">
      {#each (showArchive ? globalTasks.items : activeTasks) as t (t.id)}
        <div class="trow-wrap" animate:flip={{ duration: motionDuration(DUR_BASE) }}>
          <div class="trow" class:done={t.status === 'done'} use:focusOnLand={focusKey('global', t.id)} style="border-left-color: {rowBorderColor(t.prioritate)}">
            <button class="check" onclick={() => toggleStatus(t)}>
              {#if t.status === 'done'}<CheckCircle2 size={18} />{:else}<div class="check-empty"></div>{/if}
            </button>
            <button class="tmain" onclick={() => toggleTaskExpand(t.id)}>
              <div class="ttitle-row">
                {#if expandedTask === t.id}<ChevronDown size={14} />{:else}<ChevronRight size={14} />{/if}
                <span class="ttitle">{t.titlu}</span>
              </div>
              <div class="tinfo">
                {#if t.categorie}<span class="task-cat">{t.categorie}</span>{/if}
                {#if t.recurenta}<span class="recur-badge" title="Recurent: {t.recurenta}"><Repeat size={10} /> {t.recurenta}</span>{/if}
                {#if t.subtask_total}
                  <span class="tsub-chip">{t.subtask_done || 0}/{t.subtask_total}</span>
                {/if}
                {#if t.descriere}<span class="note-ind" title="Are notiță"><SolidIcon name="notes" size={10} /></span>{/if}
                {#if t.atasamente_count}<span class="att-ind"><Paperclip size={10} /> {t.atasamente_count}</span>{/if}
                {#if t.data_scadenta}<span class="tdeadline" class:overdue={isOverdue(t.data_scadenta)} class:today={isToday(t.data_scadenta)} class:soon={isSoon(t.data_scadenta)}>{formatDate(t.data_scadenta)}</span>{/if}
              </div>
            </button>
            <div class="task-actions">
              <button class="status-badge" style="color: {STATUS_COLORS[t.status] || 'var(--text-dim)'}; border-color: {STATUS_COLORS[t.status] || 'var(--text-dim)'}" onclick={() => cycleTaskStatus(t)} title="Click pentru a schimba statusul">{TASK_STATUS_LABELS[t.status] || t.status || 'To Do'}</button>
              <button class="prio-badge" style="color: {priorityColor(t.prioritate || 'normal')}; border-color: {priorityColor(t.prioritate || 'normal')}" onclick={() => cycleTaskPriority(t)} title="Click pentru a schimba prioritatea">{priorityLabel(t.prioritate || 'normal')}</button>
              <button class="task-edit" onclick={() => openEditModal(t)} title="Editeaza task"><SolidIcon name="pencil" size={12} /></button>
              <button class="task-del" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Sterge task"><SolidIcon name="trash" size={13} /></button>
            </div>
          </div>
          {#if expandedTask === t.id}
            <div class="subtask-body" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
              {@render taskDetail(t)}
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
          <div class="done-list" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
          {#each doneTasks as t (t.id)}
            <div class="trow-wrap" animate:flip={{ duration: motionDuration(DUR_BASE) }}>
              <div class="trow done" use:focusOnLand={focusKey('global', t.id)} style="border-left-color: {rowBorderColor(t.prioritate)}">
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
                  </div>
                </button>
                <div class="task-actions">
                  <button class="prio-badge" style="color: {priorityColor(t.prioritate || 'normal')}; border-color: {priorityColor(t.prioritate || 'normal')}" onclick={() => cycleTaskPriority(t)} title="Click pentru a schimba prioritatea">{priorityLabel(t.prioritate || 'normal')}</button>
                  <button class="task-del" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Sterge task"><SolidIcon name="trash" size={13} /></button>
                </div>
              </div>
              {#if expandedTask === t.id}
                <div class="subtask-body" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
                  {@render taskDetail(t)}
                </div>
              {/if}
            </div>
          {/each}
          </div>
        {/if}
      {/if}
    </div>
  {/if}
  </div>

  <AgendaColumn tasks={showArchive ? globalTasks.items : activeTasks} onopen={(t) => toggleTaskExpand(t.id)} />
  </div>
</div>

<Modal bind:open={showNewModal} title="Task Nou" size="md">
  <form class="task-form" onsubmit={(e) => { e.preventDefault(); handleCreate() }}>
    <Input label="Titlu" bind:value={formTitle} placeholder="Ce ai de facut?" />
    <Textarea label="Descriere" bind:value={formDesc} placeholder="Detalii (optional)" rows={3} />
    <div class="form-row-3">
      <Select label="Prioritate" size="sm" bind:value={formPriority} options={['Normal', 'Minor', 'Urgent']} />
      <label class="mf-field">
        <span class="mf-label">Categorie</span>
        <input type="text" class="mf-input" bind:value={formCategory} placeholder="General" />
      </label>
      <div class="mf-field">
        <span class="mf-label">Deadline</span>
        <DatePicker bind:value={formDeadline} />
      </div>
    </div>
    <Select label="Recurenta" size="sm" bind:value={formRecurenta} options={[{ value: '', label: 'Fara' }, { value: 'zilnic', label: 'Zilnic' }, { value: 'saptamanal', label: 'Saptamanal' }, { value: 'lunar', label: 'Lunar' }]} />
  </form>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showNewModal = false}>Anuleaza</Button>
      <Button loading={creating} disabled={!formTitle.trim()} onclick={handleCreate}>Creeaza</Button>
    </div>
  {/snippet}
</Modal>

<Modal bind:open={showEditModal} title="Editeaza Task" size="md">
  <form class="task-form" onsubmit={(e) => { e.preventDefault(); handleEdit() }}>
    <Input label="Titlu" bind:value={formTitle} placeholder="Titlu task" />
    <Textarea label="Descriere" bind:value={formDesc} placeholder="Detalii (optional)" rows={3} />
    <div class="form-row-3">
      <Select label="Prioritate" size="sm" bind:value={formPriority} options={['Normal', 'Minor', 'Urgent']} />
      <label class="mf-field">
        <span class="mf-label">Categorie</span>
        <input type="text" class="mf-input" bind:value={formCategory} placeholder="General" />
      </label>
      <div class="mf-field">
        <span class="mf-label">Deadline</span>
        <DatePicker bind:value={formDeadline} />
      </div>
    </div>
    <Select label="Recurenta" size="sm" bind:value={formRecurenta} options={[{ value: '', label: 'Fara' }, { value: 'zilnic', label: 'Zilnic' }, { value: 'saptamanal', label: 'Saptamanal' }, { value: 'lunar', label: 'Lunar' }]} />
  </form>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showEditModal = false}>Anuleaza</Button>
      <Button loading={creating} disabled={!formTitle.trim()} onclick={handleEdit}>Salveaza</Button>
    </div>
  {/snippet}
</Modal>

<ConfirmDialog bind:open={showTaskDelete} title="Sterge task" message="Stergi acest task? Toate subtaskurile asociate vor fi sterse." confirmLabel="Sterge" onconfirm={doDeleteTask} />
<ConfirmDialog bind:open={showAttDelete} title="Sterge atasament" message="Stergi acest fisier atasat?" confirmLabel="Sterge" onconfirm={doDeleteAtt} />
<AttachmentPreview bind:open={attPreviewOpen} attachment={attPreviewAtt} ondelete={attPreviewDelete} />
<input type="file" multiple hidden bind:this={attInput} onchange={onAttFiles} />

<Modal bind:open={showNoteModal} title={noteTask ? `Notite — ${noteTask.titlu}` : 'Notite task'} size="wide">
  <div class="note-modal">
    {#if showNoteModal}
      <RichTextEditor bind:value={noteDraft} placeholder="Scrie notite pentru acest task..." />
    {/if}
  </div>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showNoteModal = false}>Anuleaza</Button>
      <Button loading={noteSaving} onclick={saveNote}>Salveaza</Button>
    </div>
  {/snippet}
</Modal>

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-h1); font-weight: var(--fw-bold); }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .toolbar { display: flex; gap: var(--space-md); align-items: center; margin-bottom: var(--space-md); flex-wrap: wrap; }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 12px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-full); color: var(--text-dim); flex: 1; max-width: 280px; }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; box-shadow: none; }
  .search-box input::placeholder { color: var(--text-dim); }
  .search-box:focus-within { border-color: var(--accent); box-shadow: var(--focus-ring); }
  .quick-add { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); }
  .quick-add input { flex: 1; min-height: 40px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); }
  .quick-add input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .filters { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
  .filter-sep { width: 1px; height: 16px; background: var(--border); margin: 0 4px; }
  .chip { padding: 4px 12px; font-size: var(--font-tiny); font-weight: var(--fw-medium); border-radius: var(--radius-full); background: var(--bg-input); color: var(--text-secondary); border: 1px solid transparent; cursor: pointer; transition: all var(--dur-fast) var(--ease); min-height: 30px; }
  .chip:hover { background: var(--bg-hover); color: var(--text); }
  .chip.active { background: var(--accent-subtle); color: var(--accent-on-subtle); border-color: var(--accent); }
  .chip:active { transform: scale(0.97); }
  .status-badge { font-size: var(--font-micro); font-weight: var(--fw-semibold); padding: 2px 10px; min-height: 22px; border-radius: var(--radius-full); background: transparent; border: 1px solid; cursor: pointer; white-space: nowrap; transition: opacity var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); display: inline-block; min-width: 62px; text-align: center; }
  .status-badge:hover { opacity: .7; }
  .status-badge:active { transform: scale(0.92); }

  .task-list { display: flex; flex-direction: column; }
  .trow-wrap { display: flex; flex-direction: column; }
  .trow { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-xs) var(--space-sm); border-left: 3px solid var(--border); border-radius: var(--radius-xs); margin-bottom: 2px; transition: background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease), opacity var(--dur-base) var(--ease); }
  .trow:hover { background: var(--bg-hover); transform: translateX(2px); }
  .trow.done { opacity: 0.5; }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; }
  .check:hover { color: var(--accent); }
  .trow.done .check { color: var(--success); }
  .check-empty { width: 18px; height: 18px; border: 2px solid var(--border); border-radius: 50%; }
  .check-empty.small { width: 14px; height: 14px; }
  .check:hover .check-empty { border-color: var(--accent); }
  .tmain { flex: 1; min-width: 0; cursor: pointer; text-align: left; }
  .ttitle-row { display: flex; align-items: center; gap: var(--space-xs); min-width: 0; }
  .ttitle { font-size: var(--font-small); color: var(--text); font-weight: var(--fw-medium); flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  .note-ind { display: inline-flex; align-items: center; color: var(--text-dim); }
  .tinfo { display: flex; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; align-items: center; }
  .task-cat { padding: 1px 8px; background: var(--purple-subtle); color: var(--purple); border-radius: var(--radius-full); font-weight: var(--fw-semibold); }
  .tsub-chip { padding: 1px 6px; border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent); font-weight: var(--fw-semibold); font-size: var(--font-micro); }
  .task-actions { display: flex; align-items: center; gap: var(--space-xs); flex-shrink: 0; }
  .prio-badge { font-size: var(--font-tiny); font-weight: var(--fw-semibold); padding: 2px 10px; min-height: 22px; border-radius: var(--radius-full); background: transparent; border: 1px solid; cursor: pointer; white-space: nowrap; transition: opacity var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); display: inline-block; min-width: 62px; text-align: center; }
  .prio-badge:hover { opacity: .8; }
  .prio-badge:active { transform: scale(0.92); }
  .task-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast); }
  .task-del:hover { color: var(--danger); background: var(--danger-subtle); }

  .done-sep { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-xs); font-size: var(--font-tiny); font-weight: var(--fw-semibold); color: var(--text-dim); cursor: pointer; margin-top: var(--space-sm); border-top: 1px solid var(--border-subtle); text-transform: uppercase; letter-spacing: var(--tracking-wide); }
  .done-sep:hover { color: var(--text-secondary); }

  /* Corp expandat: panou inset (nu mai pluteste pe negru), continut grupat cu gap */
  .subtask-body { margin-left: 26px; margin-bottom: var(--space-sm); padding: var(--space-12); background: var(--bg-surface); border: 1px solid var(--border-subtle); border-left: 2px solid var(--accent-subtle); border-radius: var(--radius-md); display: flex; flex-direction: column; gap: var(--space-12); }

  /* Actiuni discrete: chip-uri "+ Descriere / + Fisier" in loc de link-uri italic plutinde */
  .detail-actions { display: flex; flex-wrap: wrap; gap: var(--space-xs); }
  .detail-chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-full); color: var(--text-secondary); font-size: var(--font-tiny); cursor: pointer; transition: all var(--dur-fast) var(--ease); }
  .detail-chip:hover:not(:disabled) { color: var(--accent-on-subtle); border-color: var(--accent); background: var(--accent-subtle); }
  .detail-chip:active:not(:disabled) { transform: scale(0.97); }
  .detail-chip:disabled { opacity: 0.5; cursor: default; }

  .note-block { display: flex; flex-direction: column; gap: var(--space-xs); }

  /* Sectiunea de subtaskuri: eticheta micro + progres X/Y */
  .sub-section { display: flex; flex-direction: column; gap: 2px; }
  .sub-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
  .sub-cap { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--text-faint); }
  .sub-prog { font-size: var(--font-tiny); color: var(--text-dim); font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .note-edit-btn { display: inline-flex; align-items: center; gap: 5px; margin-top: 4px; padding: 3px 8px; font-size: var(--font-tiny); color: var(--text-faint); cursor: pointer; border-radius: var(--radius-sm); transition: all var(--dur-fast) var(--ease); }
  .note-edit-btn:hover { color: var(--accent); background: var(--accent-subtle); }
  .note-modal { display: flex; flex-direction: column; gap: var(--space-sm); }
  .att-row { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-xs); }
  .att-chip { display: inline-flex; align-items: center; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); overflow: hidden; }
  .att-open { display: inline-flex; align-items: center; gap: 5px; padding: 4px 8px; font-size: var(--font-tiny); color: var(--text-secondary); cursor: pointer; max-width: 220px; }
  .att-open:hover { color: var(--accent); background: var(--bg-hover); }
  .att-fname { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .att-del { display: inline-flex; align-items: center; justify-content: center; width: 24px; align-self: stretch; color: var(--text-faint); cursor: pointer; border-left: 1px solid var(--border); }
  .att-del:hover { color: var(--danger); background: var(--danger-subtle); }
  .att-ind { display: inline-flex; align-items: center; gap: 3px; color: var(--text-dim); }
  .sub-row { display: flex; align-items: center; gap: var(--space-sm); padding: 3px 0; }
  .sub-row.sub-done .sub-title { text-decoration: line-through; color: var(--text-dim); }
  .sub-title { flex: 1; font-size: var(--font-small); color: var(--text); min-width: 0; }
  .sub-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: opacity var(--dur-fast); }
  .sub-row:hover .sub-del { opacity: 1; }
  .sub-del:hover { color: var(--danger); background: var(--danger-subtle); }
  .sub-add { display: flex; gap: var(--space-xs); margin-top: var(--space-xs); }
  .sub-add input { flex: 1; padding: 6px 10px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-small); }
  .sub-add-btn { width: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .sub-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
  .sub-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .sub-loading { font-size: var(--font-tiny); color: var(--text-dim); padding: var(--space-xs) 0; }

  .mf-field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
  .mf-label { font-size: var(--font-tiny); font-weight: var(--fw-medium); color: var(--text-secondary); text-transform: uppercase; letter-spacing: var(--tracking-wide); }
  .mf-input { padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-body); font-family: inherit; min-height: 40px; }
  .mf-input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }

  .task-edit { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast); }
  .task-edit:hover { color: var(--accent); background: var(--accent-subtle); }
  .recur-badge { display: inline-flex; align-items: center; gap: 3px; padding: 0 6px; background: var(--accent-subtle); color: var(--accent); border-radius: var(--radius-xs); font-weight: var(--fw-medium); }
  .tdeadline { font-size: var(--font-micro); }
  .tdeadline.overdue { color: var(--danger); font-weight: var(--fw-semibold); }
  .tdeadline.today { color: var(--accent); font-weight: var(--fw-semibold); }
  .tdeadline.soon { color: var(--warning); }

  .task-form { display: flex; flex-direction: column; gap: var(--space-md); }
  .form-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-md); }

  .task-skeleton { padding: var(--space-sm) var(--space-md); }

  /* ===== V3: banda hero urgente ===== */
  .urgent-band { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; margin-bottom: 14px; }
  .ucard {
    display: flex; flex-direction: column; gap: 6px; min-width: 0;
    padding: var(--space-md);
    background: linear-gradient(150deg, color-mix(in srgb, var(--danger) 7%, var(--bg-surface)) 0%, var(--bg-surface) 60%);
    border: 1px solid color-mix(in srgb, var(--danger) 30%, var(--border));
    border-radius: var(--radius-lg);
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
  }
  .ucard:hover { border-color: color-mix(in srgb, var(--danger) 45%, var(--border-strong)); box-shadow: var(--shadow-lg); }
  .ucard-title { font-family: var(--font-heading); font-size: var(--font-h3); font-weight: var(--fw-bold); line-height: 1.25; color: var(--text); text-align: left; cursor: pointer; padding: 0; }
  .ucard-title:hover { color: var(--accent); }
  .ucard-sub { display: flex; align-items: center; gap: 6px; font-size: var(--font-tiny); color: var(--text-dim); flex-wrap: wrap; }
  .ucard-dot { color: var(--text-faint); }
  .ucard-actions { display: flex; gap: var(--space-sm); margin-top: auto; padding-top: var(--space-sm); }
  .ucard-btn {
    display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; min-height: 30px;
    font-size: var(--font-tiny); font-weight: var(--fw-semibold);
    background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-full);
    color: var(--text-secondary); cursor: pointer; white-space: nowrap;
    transition: all var(--dur-fast) var(--ease);
  }
  .ucard-btn:hover { border-color: var(--accent); color: var(--accent-on-subtle); background: var(--accent-subtle); }
  .ucard-btn:active { transform: scale(0.97); }

  /* ===== V3: grid lista + agenda 7 zile ===== */
  .v3grid { display: grid; grid-template-columns: 1fr 300px; gap: 14px; align-items: start; }
  .list-cell { min-width: 0; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-md); }
  .list-label { margin-bottom: var(--space-12); }

  @media (max-width: 940px) {
    /* Agenda coboara sub lista (o singura coloana) */
    .v3grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 640px) {
    .urgent-band { grid-template-columns: 1fr; }
  }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .toolbar { flex-direction: column; align-items: stretch; }
    .search-box { max-width: none; }
    .quick-add input, .quick-add-btn { min-height: 44px; }
    .quick-add-btn { width: 44px; }
    .task-del, .task-edit, .note-edit-btn { opacity: 1; }
    .form-row-3 { grid-template-columns: 1fr; }
    /* Title gets the full width; the action bar wraps to its own line below
       so a long title no longer squeezes into a tall narrow column. */
    .trow { flex-wrap: wrap; align-items: flex-start; row-gap: 6px; padding: var(--space-sm); }
    .check { padding-top: 1px; }
    .task-actions { flex-basis: 100%; justify-content: flex-end; gap: var(--space-xs); }
    /* Tinte de atingere >=44px pe actiunile de rand */
    .task-actions button, .check { min-width: var(--tap-min); min-height: var(--tap-min); }
  }
</style>
