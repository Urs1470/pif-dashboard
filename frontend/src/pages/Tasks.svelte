<script>
  import { onMount } from 'svelte'
  import { slide } from 'svelte/transition'
  import { ListTodo, Plus, Clock, CheckCircle2, ChevronDown, ChevronRight, Trash2, Pencil, Repeat, Search, StickyNote, Paperclip } from '@lucide/svelte'
  import { globalTasks, loadGlobalTasks, updateGlobalTask, createGlobalTask, deleteGlobalTask, loadSubtasks, createSubtask, updateSubtask, deleteSubtask, loadTaskAttachments, uploadTaskAttachment, deleteTaskAttachment } from '../stores/tasks.svelte.js'
  import { timer, startGlobalTaskTimer, stopGlobalTaskTimer, loadActiveTimer, addManualTime, deleteGlobalTimerSession, loadGlobalTaskTimer } from '../stores/timer.svelte.js'
  import { TASK_STATUS_LABELS, STATUS_COLORS, formatDuration, formatDate, priorityColor, priorityLabel } from '../lib/formatters.js'
  import { toast } from '../stores/ui.svelte.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import Button from '../components/ui/Button.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import Input from '../components/ui/Input.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  import RichTextEditor from '../components/ui/RichTextEditor.svelte'
  import AttachmentPreview from '../components/ui/AttachmentPreview.svelte'
  import RichText from '../components/ui/RichText.svelte'

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

  let showManualTime = $state(false)
  let manualId = $state(null)
  let manualDate = $state('')
  let manualHours = $state(1)
  let manualMinutes = $state(0)
  let manualSaving = $state(false)

  let taskSessions = $state({})

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
  const activeTasks = $derived(filteredTasks.filter(t => t.status !== 'done'))
  const doneTasks = $derived(filteredTasks.filter(t => t.status === 'done'))

  async function toggleStatus(task) {
    const next = task.status === 'done' ? 'to_do' : 'done'
    await updateGlobalTask(task.id, { status: next })
    await loadGlobalTasks({ arhiva: showArchive })
  }

  async function toggleTimer(task) {
    const wasActive = timer.active?.global_task_id === task.id
    if (wasActive) {
      await stopGlobalTaskTimer(task.id)
    } else {
      await startGlobalTaskTimer(task.id)
    }
    await loadActiveTimer()
    if (wasActive) {
      await loadGlobalTasks({ arhiva: showArchive })
      taskSessions = { ...taskSessions, [task.id]: await loadGlobalTaskTimer(task.id).catch(() => taskSessions[task.id] || { sessions: [], total_secunde: 0 }) }
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
    loadTaskSessions(taskId)
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

  function openManualTime(taskId) {
    manualId = taskId
    manualDate = new Date().toISOString().slice(0, 10)
    manualHours = 1
    manualMinutes = 0
    showManualTime = true
  }

  async function saveManualTime() {
    const sec = manualHours * 3600 + manualMinutes * 60
    if (sec <= 0) { toast('Durata trebuie sa fie > 0', 'error'); return }
    manualSaving = true
    try {
      await addManualTime('global_task', manualId, sec, manualDate || undefined)
      showManualTime = false
      toast('Timp adaugat', 'success')
      await loadGlobalTasks({ arhiva: showArchive })
      if (taskSessions[manualId]) {
        taskSessions = { ...taskSessions, [manualId]: await loadGlobalTaskTimer(manualId).catch(() => taskSessions[manualId]) }
      }
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { manualSaving = false }
  }

  async function handleDeleteSession(taskId, sessionId) {
    try {
      await deleteGlobalTimerSession(sessionId)
      toast('Sesiune stearsa', 'success')
      await loadGlobalTasks({ arhiva: showArchive })
      taskSessions = { ...taskSessions, [taskId]: await loadGlobalTaskTimer(taskId).catch(() => taskSessions[taskId]) }
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function loadTaskSessions(taskId) {
    if (!taskSessions[taskId]) {
      taskSessions = { ...taskSessions, [taskId]: await loadGlobalTaskTimer(taskId).catch(() => ({ sessions: [], total_secunde: 0 })) }
    }
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

  onMount(() => { loadGlobalTasks(); loadActiveTimer() })
</script>

{#snippet taskNotes(t)}
  {#if t.descriere}
    <div class="note-block">
      <RichText value={t.descriere} class="note-content" collapsible maxHeight={200} />
      <button class="note-edit-btn" title="Editeaza notite" onclick={() => openNoteModal(t)}><Pencil size={12} /> Editeaza</button>
    </div>
  {:else}
    <button class="note-add" onclick={() => openNoteModal(t)}><StickyNote size={12} /> Adauga notite...</button>
  {/if}
{/snippet}

{#snippet taskAttachments(t)}
  <div class="att-row">
    {#each (attCache[t.id] || []) as a (a.id)}
      <span class="att-chip">
        <button class="att-open" title="{a.nume_fisier} ({a.tip_fisier})" onclick={() => openAttPreview(a, t.id)}>
          <Paperclip size={11} /><span class="att-fname">{a.nume_fisier}</span>
        </button>
        <button class="att-del" title="Sterge atasament" onclick={() => { attDeleteId = a.id; attDeleteTaskId = t.id; showAttDelete = true }}><Trash2 size={11} /></button>
      </span>
    {/each}
    <button class="note-add" onclick={() => triggerAttUpload(t.id)} disabled={attUploading}><Paperclip size={12} /> {attUploading ? 'Se incarca...' : 'Ataseaza fisier...'}</button>
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
        <div class="trow-wrap">
          <div class="trow" class:done={t.status === 'done'} style="border-left-color: {t.prioritate ? priorityColor(t.prioritate) : 'var(--border)'}">
            <button class="check" onclick={() => toggleStatus(t)}>
              {#if t.status === 'done'}<CheckCircle2 size={18} />{:else}<div class="check-empty"></div>{/if}
            </button>
            <button class="tmain" onclick={() => toggleTaskExpand(t.id)}>
              <div class="ttitle-row">
                {#if expandedTask === t.id}<ChevronDown size={14} />{:else}<ChevronRight size={14} />{/if}
                <span class="ttitle">{t.titlu}</span>
                {#if t.descriere}<span class="tdesc-icon" title="Are notiță"><StickyNote size={12} /></span>{/if}
              </div>
              <div class="tinfo">
                {#if t.categorie}<span class="task-cat">{t.categorie}</span>{/if}
                {#if t.recurenta}<span class="recur-badge" title="Recurent: {t.recurenta}"><Repeat size={10} /> {t.recurenta}</span>{/if}
                {#if t.timp_secunde}<span class="tmono">{formatDuration(t.timp_secunde)}</span>{/if}
                {#if t.subtask_total}
                  <span class="tsub-chip">{t.subtask_done || 0}/{t.subtask_total}</span>
                {/if}
                {#if t.atasamente_count}<span class="att-ind"><Paperclip size={10} /> {t.atasamente_count}</span>{/if}
                {#if t.data_scadenta}<span>{formatDate(t.data_scadenta)}</span>{/if}
              </div>
            </button>
            <div class="task-actions">
              <button class="status-badge" style="color: {STATUS_COLORS[t.status] || 'var(--text-dim)'}; border-color: {STATUS_COLORS[t.status] || 'var(--text-dim)'}" onclick={() => cycleTaskStatus(t)} title="Click pentru a schimba statusul">{TASK_STATUS_LABELS[t.status] || t.status || 'To Do'}</button>
              <button class="prio-badge" style="color: {priorityColor(t.prioritate || 'normal')}; border-color: {priorityColor(t.prioritate || 'normal')}" onclick={() => cycleTaskPriority(t)} title="Click pentru a schimba prioritatea">{priorityLabel(t.prioritate || 'normal')}</button>
              <button class="task-edit" onclick={() => openEditModal(t)} title="Editeaza task"><Pencil size={12} /></button>
              <button class="timer-btn manual" title="Adauga timp manual" onclick={() => openManualTime(t.id)}><Plus size={12} /></button>
              <button class="timer-btn" class:active={timer.active?.global_task_id === t.id} onclick={() => toggleTimer(t)}>
                <Clock size={14} />
              </button>
              <button class="task-del" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Sterge task"><Trash2 size={13} /></button>
            </div>
          </div>
          {#if expandedTask === t.id}
            <div class="subtask-body" transition:slide={{ duration: 150 }}>
              {@render taskNotes(t)}
              {@render taskAttachments(t)}
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
              {#if taskSessions[t.id]?.sessions?.length > 0}
                <div class="sess-section">
                  <span class="sess-label">Sesiuni ({taskSessions[t.id].sessions.length}) — {formatDuration(taskSessions[t.id].total_secunde)}</span>
                  {#each taskSessions[t.id].sessions as s (s.id)}
                    <div class="sess">
                      <span>{s.start_time ? formatDate(s.start_time) : '—'}</span>
                      <span class="sess-dur">{formatDuration(s.durata_secunde)}</span>
                      <button class="sess-del" title="Sterge" onclick={() => handleDeleteSession(t.id, s.id)}><Trash2 size={11} /></button>
                    </div>
                  {/each}
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
          <div class="done-list" transition:slide={{ duration: 150 }}>
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
                  <button class="prio-badge" style="color: {priorityColor(t.prioritate || 'normal')}; border-color: {priorityColor(t.prioritate || 'normal')}" onclick={() => cycleTaskPriority(t)} title="Click pentru a schimba prioritatea">{priorityLabel(t.prioritate || 'normal')}</button>
                  <button class="timer-btn" class:active={timer.active?.global_task_id === t.id} onclick={() => toggleTimer(t)}>
                    <Clock size={14} />
                  </button>
                  <button class="task-del" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Sterge task"><Trash2 size={13} /></button>
                </div>
              </div>
              {#if expandedTask === t.id}
                <div class="subtask-body" transition:slide={{ duration: 150 }}>
                  {@render taskNotes(t)}
                  {@render taskAttachments(t)}
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
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<Modal bind:open={showNewModal} title="Task Nou" size="md">
  <form class="task-form" onsubmit={(e) => { e.preventDefault(); handleCreate() }}>
    <Input label="Titlu" bind:value={formTitle} placeholder="Ce ai de facut?" />
    <label class="mf-field">
      <span class="mf-label">Descriere</span>
      <textarea class="mf-textarea" bind:value={formDesc} placeholder="Detalii (optional)" rows="3"></textarea>
    </label>
    <div class="form-row-3">
      <label class="mf-field">
        <span class="mf-label">Prioritate</span>
        <select class="mf-input" bind:value={formPriority}>
          <option value="Normal">Normal</option>
          <option value="Minor">Minor</option>
          <option value="Urgent">Urgent</option>
        </select>
      </label>
      <label class="mf-field">
        <span class="mf-label">Categorie</span>
        <input type="text" class="mf-input" bind:value={formCategory} placeholder="General" />
      </label>
      <label class="mf-field">
        <span class="mf-label">Deadline</span>
        <input type="date" class="mf-input" bind:value={formDeadline} />
      </label>
    </div>
    <label class="mf-field">
      <span class="mf-label">Recurenta</span>
      <select class="mf-input" bind:value={formRecurenta}>
        <option value="">Fara</option>
        <option value="zilnic">Zilnic</option>
        <option value="saptamanal">Saptamanal</option>
        <option value="lunar">Lunar</option>
      </select>
    </label>
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showNewModal = false}>Anuleaza</Button>
      <Button loading={creating} disabled={!formTitle.trim()} onclick={handleCreate}>Creeaza</Button>
    </div>
  </form>
</Modal>

<Modal bind:open={showEditModal} title="Editeaza Task" size="md">
  <form class="task-form" onsubmit={(e) => { e.preventDefault(); handleEdit() }}>
    <Input label="Titlu" bind:value={formTitle} placeholder="Titlu task" />
    <label class="mf-field">
      <span class="mf-label">Descriere</span>
      <textarea class="mf-textarea" bind:value={formDesc} placeholder="Detalii (optional)" rows="3"></textarea>
    </label>
    <div class="form-row-3">
      <label class="mf-field">
        <span class="mf-label">Prioritate</span>
        <select class="mf-input" bind:value={formPriority}>
          <option value="Normal">Normal</option>
          <option value="Minor">Minor</option>
          <option value="Urgent">Urgent</option>
        </select>
      </label>
      <label class="mf-field">
        <span class="mf-label">Categorie</span>
        <input type="text" class="mf-input" bind:value={formCategory} placeholder="General" />
      </label>
      <label class="mf-field">
        <span class="mf-label">Deadline</span>
        <input type="date" class="mf-input" bind:value={formDeadline} />
      </label>
    </div>
    <label class="mf-field">
      <span class="mf-label">Recurenta</span>
      <select class="mf-input" bind:value={formRecurenta}>
        <option value="">Fara</option>
        <option value="zilnic">Zilnic</option>
        <option value="saptamanal">Saptamanal</option>
        <option value="lunar">Lunar</option>
      </select>
    </label>
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showEditModal = false}>Anuleaza</Button>
      <Button loading={creating} disabled={!formTitle.trim()} onclick={handleEdit}>Salveaza</Button>
    </div>
  </form>
</Modal>

<Modal bind:open={showManualTime} title="Adauga timp manual" size="sm">
  <div class="manual-form">
    <label class="mf-field">
      <span class="mf-label">Data</span>
      <input type="date" bind:value={manualDate} class="mf-input" />
    </label>
    <div class="mf-row">
      <label class="mf-field">
        <span class="mf-label">Ore</span>
        <input type="number" min="0" max="24" bind:value={manualHours} class="mf-input" />
      </label>
      <label class="mf-field">
        <span class="mf-label">Minute</span>
        <input type="number" min="0" max="59" step="5" bind:value={manualMinutes} class="mf-input" />
      </label>
    </div>
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showManualTime = false}>Anuleaza</Button>
      <Button loading={manualSaving} onclick={saveManualTime}>Adauga</Button>
    </div>
  </div>
</Modal>

<ConfirmDialog bind:open={showTaskDelete} title="Sterge task" message="Stergi acest task? Toate subtaskurile si sesiunile timer asociate vor fi sterse." confirmLabel="Sterge" onconfirm={doDeleteTask} />
<ConfirmDialog bind:open={showAttDelete} title="Sterge atasament" message="Stergi acest fisier atasat?" confirmLabel="Sterge" onconfirm={doDeleteAtt} />
<AttachmentPreview bind:open={attPreviewOpen} attachment={attPreviewAtt} ondelete={attPreviewDelete} />
<input type="file" multiple hidden bind:this={attInput} onchange={onAttFiles} />

<Modal bind:open={showNoteModal} title={noteTask ? `Notite — ${noteTask.titlu}` : 'Notite task'} size="wide">
  <div class="note-modal">
    {#if showNoteModal}
      <RichTextEditor bind:value={noteDraft} placeholder="Scrie notite pentru acest task..." />
    {/if}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showNoteModal = false}>Anuleaza</Button>
      <Button loading={noteSaving} onclick={saveNote}>Salveaza</Button>
    </div>
  </div>
</Modal>

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-h1); font-weight: 700; }
  .count { font-size: var(--font-tiny); padding: 2px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .toolbar { display: flex; gap: var(--space-md); align-items: center; margin-bottom: var(--space-md); flex-wrap: wrap; }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-dim); flex: 1; max-width: 280px; }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; box-shadow: none; }
  .search-box input::placeholder { color: var(--text-dim); }
  .search-box:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }
  .quick-add { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); }
  .quick-add input { flex: 1; min-height: 40px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); }
  .quick-add input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); outline: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .filters { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
  .filter-sep { width: 1px; height: 16px; background: var(--border); margin: 0 4px; }
  .chip { padding: 4px 12px; font-size: var(--font-tiny); font-weight: 500; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid transparent; cursor: pointer; transition: all var(--dur-fast) var(--ease); }
  .chip:hover { background: var(--bg-hover); }
  .chip.active { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent); }
  .status-badge { font-size: 10px; font-weight: 600; padding: 1px 8px; border-radius: var(--radius-full); background: transparent; border: 1px solid; cursor: pointer; white-space: nowrap; transition: all var(--dur-fast); display: inline-block; min-width: 62px; text-align: center; }
  .status-badge:hover { opacity: .7; }

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
  .ttitle-row { display: flex; align-items: center; gap: var(--space-xs); min-width: 0; }
  .ttitle { font-size: var(--font-small); color: var(--text); font-weight: 500; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  :global(.tdesc-icon) { display: inline-flex; align-items: center; color: var(--text-faint); flex-shrink: 0; }
  .tinfo { display: flex; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; align-items: center; }
  .tmono { font-family: var(--font-mono); }
  .task-cat { padding: 0 6px; background: var(--bg-elevated); border-radius: var(--radius-xs); }
  .tsub-chip { padding: 1px 6px; border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent); font-weight: 600; font-size: 10px; }
  .task-actions { display: flex; align-items: center; gap: var(--space-xs); flex-shrink: 0; }
  .timer-btn { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; transition: all var(--dur-fast) var(--ease); -webkit-tap-highlight-color: transparent; flex-shrink: 0; }
  .timer-btn:hover { background: var(--bg-hover); color: var(--text); }
  .timer-btn.active { color: var(--accent); background: var(--accent-subtle); }
  .prio-badge { font-size: var(--font-tiny); font-weight: 600; padding: 1px 8px; border-radius: var(--radius-full); background: transparent; border: 1px solid; cursor: pointer; white-space: nowrap; transition: all var(--dur-fast); display: inline-block; min-width: 62px; text-align: center; }
  .prio-badge:hover { opacity: .8; }
  .task-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast); }
  .task-del:hover { color: var(--danger); background: var(--danger-subtle); }

  .done-sep { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-xs); font-size: var(--font-tiny); font-weight: 600; color: var(--text-dim); cursor: pointer; margin-top: var(--space-sm); border-top: 1px solid var(--border-subtle); text-transform: uppercase; letter-spacing: 0.05em; }
  .done-sep:hover { color: var(--text-secondary); }

  .subtask-body { margin-left: 26px; padding: var(--space-sm) var(--space-sm) var(--space-sm) var(--space-md); border-left: 2px solid var(--accent-subtle); margin-bottom: var(--space-sm); }
  .note-add { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-tiny); color: var(--text-faint); cursor: pointer; padding: 4px 6px; margin-bottom: var(--space-xs); border-radius: var(--radius-xs); font-style: italic; transition: all var(--dur-fast) var(--ease); }
  .note-add:hover { color: var(--accent); background: var(--accent-subtle); }
  .note-block { margin-bottom: var(--space-sm); }
  .note-edit-btn { display: inline-flex; align-items: center; gap: 5px; margin-top: 4px; padding: 3px 8px; font-size: var(--font-tiny); color: var(--text-faint); cursor: pointer; border-radius: var(--radius-xs); transition: all var(--dur-fast) var(--ease); }
  .note-edit-btn:hover { color: var(--accent); background: var(--accent-subtle); }
  .note-modal { display: flex; flex-direction: column; gap: var(--space-sm); }
  .att-row { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-xs); margin-bottom: var(--space-sm); }
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
  .sub-del { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: opacity var(--dur-fast); }
  .sub-row:hover .sub-del { opacity: 1; }
  .sub-del:hover { color: var(--danger); background: var(--danger-subtle); }
  .sub-add { display: flex; gap: var(--space-xs); margin-top: var(--space-xs); }
  .sub-add input { flex: 1; padding: 6px 10px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-small); }
  .sub-add-btn { width: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .sub-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
  .sub-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .sub-loading { font-size: var(--font-tiny); color: var(--text-dim); padding: var(--space-xs) 0; }

  .timer-btn.manual { width: 28px; height: 28px; color: var(--text-faint); }
  .timer-btn.manual:hover { color: var(--accent); }

  .sess-section { margin-top: var(--space-sm); padding-top: var(--space-sm); border-top: 1px solid var(--border-subtle); }
  .sess-label { font-size: var(--font-tiny); font-weight: 500; color: var(--text-dim); margin-bottom: 4px; display: block; }
  .sess { display: flex; align-items: center; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-secondary); padding: 2px 0; }
  .sess-dur { font-family: var(--font-mono); color: var(--accent); margin-left: auto; }
  .sess-del { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: all var(--dur-fast); }
  .sess:hover .sess-del { opacity: 1; }
  .sess-del:hover { color: var(--danger); background: var(--danger-subtle); }

  .manual-form { display: flex; flex-direction: column; gap: var(--space-md); }
  .mf-row { display: flex; gap: var(--space-md); }
  .mf-field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
  .mf-label { font-size: var(--font-tiny); font-weight: 500; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; }
  .mf-input { padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-body); font-family: inherit; min-height: 38px; }

  .task-edit { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast); }
  .task-edit:hover { color: var(--accent); background: var(--accent-subtle); }
  .recur-badge { display: inline-flex; align-items: center; gap: 3px; padding: 0 6px; background: var(--accent-subtle); color: var(--accent); border-radius: var(--radius-xs); font-weight: 500; }

  .task-form { display: flex; flex-direction: column; gap: var(--space-md); }
  .form-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-md); }
  .mf-textarea { padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-body); font-family: inherit; resize: vertical; min-height: 60px; }

  .task-skeleton { padding: var(--space-sm) var(--space-md); }
  .modal-actions { display: flex; gap: var(--space-sm); justify-content: flex-end; margin-top: var(--space-lg); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .toolbar { flex-direction: column; align-items: stretch; }
    .search-box { max-width: none; }
    .quick-add input, .quick-add-btn { min-height: 44px; }
    .quick-add-btn { width: 44px; }
    .sess-del, .task-del, .task-edit, .note-edit-btn { opacity: 1; }
    .form-row-3 { grid-template-columns: 1fr; }
    /* Title gets the full width; the action bar wraps to its own line below
       so a long title no longer squeezes into a tall narrow column. */
    .trow { flex-wrap: wrap; align-items: flex-start; row-gap: 6px; padding: var(--space-sm); }
    .check { padding-top: 1px; }
    .task-actions { flex-basis: 100%; justify-content: flex-end; }
  }
</style>
