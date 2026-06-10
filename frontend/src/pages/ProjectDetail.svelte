<script>
  import { onMount } from 'svelte'
  import { ArrowLeft, Clock, Play, Square, Plus, CheckCircle2, Wrench, BookOpen, ListTodo, ClipboardList, Settings2, Paperclip, Pencil, Trash2, FileDown, FileText, StickyNote } from '@lucide/svelte'
  import {
    loadProjectDetail, loadProjectTasks, loadProjectJournal, loadProjectEquipment,
    loadProjectChecklist, loadChecklistCategories, deleteProject,
    createChecklistItem, updateChecklistItem, deleteChecklistItem,
    createJournalEntry, deleteJournalEntry, deleteEquipment, loadProjectTimerSessions,
  } from '../stores/projects.svelte.js'
  import { updateTask, createTask } from '../stores/tasks.svelte.js'
  import { timer, startProjectTimer, stopProjectTimer, stopProjectTimerWithNote, startTaskTimer, stopTaskTimer, loadActiveTimer } from '../stores/timer.svelte.js'
  import { PROJECT_STATUS_LABELS, TASK_STATUS_LABELS, STATUS_COLORS, formatDate, formatDuration, priorityColor } from '../lib/formatters.js'
  import { exportMarkdown } from '../lib/exportMd.js'
  import { navigate } from '../lib/router.svelte.js'
  import { toast } from '../stores/ui.svelte.js'
  import Badge from '../components/ui/Badge.svelte'
  import Card from '../components/ui/Card.svelte'
  import Button from '../components/ui/Button.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import Input from '../components/ui/Input.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  import ProjectFormModal from '../components/projects/ProjectFormModal.svelte'
  import EquipmentFormModal from '../components/projects/EquipmentFormModal.svelte'
  import AttachmentsTab from '../components/projects/AttachmentsTab.svelte'

  let { params } = $props()
  let project = $state(null)
  let tasks = $state([])
  let journal = $state([])
  let equipment = $state([])
  let checklist = $state([])
  let checklistCats = $state([])
  let timerSessions = $state({ sessions: [], total_secunde: 0 })
  let loading = $state(true)
  let error = $state(null)
  let activeTab = $state('tasks')

  let showNewTask = $state(false)
  let newTaskTitle = $state('')
  let creatingTask = $state(false)

  let showEditModal = $state(false)
  let showDeleteConfirm = $state(false)

  let showStopNote = $state(false)
  let stopNoteTitle = $state('')
  let stopNoteText = $state('')
  let stoppingWithNote = $state(false)

  let journalText = $state('')
  let journalDate = $state('')
  let addingJournal = $state(false)
  let journalDeleteId = $state(null)
  let showJournalDelete = $state(false)

  let newItemTitles = $state({})

  let showEquipModal = $state(false)
  let editingEquipment = $state(null)
  let equipDeleteId = $state(null)
  let showEquipDelete = $state(false)

  const tabs = [
    { key: 'tasks', label: 'Taskuri', icon: ListTodo },
    { key: 'journal', label: 'Jurnal', icon: BookOpen },
    { key: 'checklist', label: 'Checklist', icon: ClipboardList },
    { key: 'equipment', label: 'Echipamente', icon: Wrench },
    { key: 'attachments', label: 'Atasamente', icon: Paperclip },
    { key: 'info', label: 'Info', icon: Settings2 },
  ]

  async function load() {
    loading = true
    try {
      project = await loadProjectDetail(params.id)
      const [t, j, e, c, cc, ts] = await Promise.all([
        loadProjectTasks(params.id).catch(() => []),
        loadProjectJournal(params.id).catch(() => []),
        loadProjectEquipment(params.id).catch(() => []),
        loadProjectChecklist(params.id).catch(() => []),
        loadChecklistCategories(params.id).catch(() => []),
        loadProjectTimerSessions(params.id).catch(() => ({ sessions: [], total_secunde: 0 })),
      ])
      tasks = Array.isArray(t) ? t : t.tasks || []
      journal = Array.isArray(j) ? j : j.entries || []
      equipment = Array.isArray(e) ? e : e.echipamente || []
      checklist = Array.isArray(c) ? c : c.items || c.checklist || []
      checklistCats = Array.isArray(cc) ? cc : cc.categorii || []
      timerSessions = ts
    } catch (err) {
      error = err.message
    } finally { loading = false }
  }

  async function reloadJournal() {
    const j = await loadProjectJournal(params.id).catch(() => [])
    journal = Array.isArray(j) ? j : j.entries || []
  }

  async function reloadChecklist() {
    const c = await loadProjectChecklist(params.id).catch(() => [])
    checklist = Array.isArray(c) ? c : c.items || c.checklist || []
  }

  async function reloadEquipment() {
    const e = await loadProjectEquipment(params.id).catch(() => [])
    equipment = Array.isArray(e) ? e : e.echipamente || []
  }

  async function toggleTaskStatus(task) {
    const next = task.status === 'done' ? 'to_do' : 'done'
    await updateTask(task.id, { status: next })
    tasks = tasks.map(t => t.id === task.id ? { ...t, status: next } : t)
  }

  async function handleProjectTimer() {
    if (projectTimerActive) {
      showStopNote = true
      stopNoteTitle = ''
      stopNoteText = ''
    } else {
      await startProjectTimer(params.id)
      await loadActiveTimer()
    }
  }

  async function stopSimple() {
    stoppingWithNote = true
    try {
      await stopProjectTimer(params.id)
      showStopNote = false
      timerSessions = await loadProjectTimerSessions(params.id).catch(() => timerSessions)
    } finally { stoppingWithNote = false }
  }

  async function stopWithNote() {
    stoppingWithNote = true
    try {
      await stopProjectTimerWithNote(params.id, { titlu: stopNoteTitle.trim(), note: stopNoteText.trim() })
      showStopNote = false
      toast('Timer oprit, nota salvata in jurnal', 'success')
      await Promise.all([reloadJournal(), loadProjectTimerSessions(params.id).then(ts => timerSessions = ts).catch(() => {})])
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { stoppingWithNote = false }
  }

  async function handleTaskTimer(taskId) {
    if (timer.active?.kind === 'task' && timer.active?.task_id === taskId) await stopTaskTimer(taskId)
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

  async function handleDeleteProject() {
    await deleteProject(params.id)
    toast('Proiect sters', 'success')
    navigate('/projects')
  }

  async function addJournal() {
    if (!journalText.trim()) return
    addingJournal = true
    try {
      const body = { continut: journalText.trim() }
      if (journalDate) body.data = journalDate
      await createJournalEntry(params.id, body)
      journalText = ''
      journalDate = ''
      await reloadJournal()
      toast('Intrare adaugata', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { addingJournal = false }
  }

  async function doDeleteJournal() {
    if (!journalDeleteId) return
    await deleteJournalEntry(journalDeleteId)
    journalDeleteId = null
    await reloadJournal()
    toast('Intrare stearsa', 'success')
  }

  async function toggleChecklistItem(item) {
    const next = item.completed ? 0 : 1
    checklist = checklist.map(c => c.id === item.id ? { ...c, completed: next } : c)
    try {
      await updateChecklistItem(item.id, { completed: next })
    } catch (e) {
      checklist = checklist.map(c => c.id === item.id ? { ...c, completed: item.completed } : c)
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  async function addChecklistItem(catId) {
    const key = catId ?? '0'
    const title = (newItemTitles[key] || '').trim()
    if (!title) return
    try {
      const body = { titlu: title }
      if (catId != null) body.categorie_id = catId
      await createChecklistItem(params.id, body)
      newItemTitles[key] = ''
      await reloadChecklist()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  async function removeChecklistItem(itemId) {
    await deleteChecklistItem(itemId)
    await reloadChecklist()
  }

  function editEquip(e) {
    editingEquipment = e
    showEquipModal = true
  }

  function newEquip() {
    editingEquipment = null
    showEquipModal = true
  }

  async function doDeleteEquip() {
    if (!equipDeleteId) return
    await deleteEquipment(equipDeleteId)
    equipDeleteId = null
    await reloadEquipment()
    toast('Echipament sters', 'success')
  }

  function parseEquipParams(e) {
    try {
      return Object.entries(typeof e.params_json === 'string' ? JSON.parse(e.params_json || '{}') : (e.params_json || {}))
    } catch (_) { return [] }
  }

  function exportPdf() {
    window.open(`/api/export/pdf?project_id=${params.id}`, '_blank')
  }

  async function exportMd() {
    try {
      await exportMarkdown(params.id)
      toast('Export Markdown descarcat', 'success')
    } catch (e) {
      toast(`Eroare la export: ${e.message}`, 'error')
    }
  }

  onMount(() => { load(); loadActiveTimer() })

  const tasksDone = $derived(tasks.filter(t => t.status === 'done' || t.status === 'finalizat').length)
  const projectTimerActive = $derived(timer.active?.kind === 'project' && timer.active?.project_id === params.id)
  const checklistGroups = $derived.by(() => {
    const groups = []
    const byCat = new Map()
    for (const item of checklist) {
      const key = item.categorie_id != null ? String(item.categorie_id) : '0'
      if (!byCat.has(key)) byCat.set(key, [])
      byCat.get(key).push(item)
    }
    const ordered = [...checklistCats].sort((a, b) => (a.ordine ?? 0) - (b.ordine ?? 0))
    for (const cat of ordered) {
      groups.push({ id: cat.id, nume: cat.nume, items: byCat.get(String(cat.id)) || [] })
    }
    const uncat = byCat.get('0') || []
    if (uncat.length || groups.length === 0) {
      groups.push({ id: null, nume: groups.length === 0 ? null : 'Fara categorie', items: uncat })
    }
    return groups
  })
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
          {#if project.tip}<span class="tip" class:pif={project.tip === 'PIF'} class:service={project.tip === 'Service'}>{project.tip}</span>{/if}
          <h1>{project.nume || '—'}</h1>
          <Badge label={PROJECT_STATUS_LABELS[project.status] || project.status || '—'} color={STATUS_COLORS[project.status] || 'var(--text-dim)'} />
        </div>
        <div class="header-actions">
          <Button variant={projectTimerActive ? 'danger' : 'secondary'} size="sm" onclick={handleProjectTimer}>
            {#if projectTimerActive}<span class="timer-dot"></span> {formatDuration(timer.elapsed)} · Stop{:else}<Play size={14} /> Timer{/if}
          </Button>
          <Button variant="secondary" size="sm" onclick={() => showEditModal = true}><Pencil size={14} /> Edit</Button>
          <Button variant="secondary" size="sm" onclick={exportPdf}><FileDown size={14} /> PDF</Button>
          <Button variant="secondary" size="sm" onclick={exportMd}><FileText size={14} /> MD</Button>
          <Button variant="ghost" size="sm" onclick={() => showDeleteConfirm = true}><Trash2 size={14} /></Button>
        </div>
      </div>
      <div class="meta">
        {#if project.client}<span>{project.client}</span>{/if}
        {#if project.echipament_principal}<span>· {project.echipament_principal}</span>{/if}
        {#if project.cod_proiect}<span>· {project.cod_proiect}</span>{/if}
      </div>
      <div class="pstats">
        <div class="ps"><span class="ps-val">{tasks.length}</span><span class="ps-lbl">taskuri</span></div>
        <div class="ps"><span class="ps-val">{tasksDone}</span><span class="ps-lbl">finalizate</span></div>
        <div class="ps"><span class="ps-val">{formatDuration(timerSessions.total_secunde)}</span><span class="ps-lbl">ore lucrate</span></div>
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
              <div class="trow" class:done={t.status === 'done' || t.status === 'finalizat'} style="border-left-color: {t.prioritate ? priorityColor(t.prioritate) : 'var(--border)'}">
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
                <button class="timer-btn" class:active={timer.active?.kind === 'task' && timer.active?.task_id === t.id} onclick={() => handleTaskTimer(t.id)}><Clock size={14} /></button>
              </div>
            {/each}
          </div>
        {/if}

      {:else if activeTab === 'journal'}
        <div class="jform">
          <textarea rows="3" bind:value={journalText} placeholder="Ce ai lucrat azi?"></textarea>
          <div class="jform-row">
            <input type="date" bind:value={journalDate} class="jdate-input" title="Data (optional, implicit azi)" />
            <Button size="sm" loading={addingJournal} disabled={!journalText.trim()} onclick={addJournal}><Plus size={14} /> Adauga</Button>
          </div>
        </div>
        {#if journal.length === 0}<p class="empty">Nicio intrare.</p>
        {:else}
          <div class="jlist">{#each journal as j (j.id)}
            <div class="jentry">
              <div class="jentry-top">
                <div class="jdate">{formatDate(j.data || j.created_at)}</div>
                <button class="jdel" title="Sterge" onclick={() => { journalDeleteId = j.id; showJournalDelete = true }}><Trash2 size={13} /></button>
              </div>
              <div class="jtext">{j.continut || '—'}</div>
            </div>
          {/each}</div>
        {/if}

      {:else if activeTab === 'checklist'}
        {#each checklistGroups as group (group.id ?? 'uncat')}
          {@const done = group.items.filter(i => i.completed).length}
          <div class="clgroup">
            {#if group.nume}
              <div class="clgroup-head">
                <span class="section-title">{group.nume}</span>
                <span class="clgroup-count">{done}/{group.items.length}</span>
              </div>
            {/if}
            {#each group.items as item (item.id)}
              <div class="clrow" class:done={item.completed}>
                <input type="checkbox" class="cbx" checked={!!item.completed} onchange={() => toggleChecklistItem(item)} />
                <div class="clmain">
                  <div class="cllabel">{item.titlu || '—'}</div>
                  {#if item.note}<div class="clcat">{item.note}</div>{/if}
                </div>
                <button class="jdel" title="Sterge" onclick={() => removeChecklistItem(item.id)}><Trash2 size={13} /></button>
              </div>
            {/each}
            <form class="cladd" onsubmit={(e) => { e.preventDefault(); addChecklistItem(group.id) }}>
              <input type="text" placeholder="Adauga element..." bind:value={newItemTitles[group.id ?? '0']} />
              <button type="submit" class="cladd-btn" disabled={!(newItemTitles[group.id ?? '0'] || '').trim()}><Plus size={14} /></button>
            </form>
          </div>
        {/each}

      {:else if activeTab === 'equipment'}
        <div class="tab-header">
          <span class="tab-sub">{equipment.length} echipamente</span>
          <Button size="sm" variant="secondary" onclick={newEquip}><Plus size={14} /> Echipament</Button>
        </div>
        {#if equipment.length === 0}<p class="empty">Niciun echipament.</p>
        {:else}
          <div class="elist">{#each equipment as e (e.id)}
            {@const eparams = parseEquipParams(e)}
            <Card>
              <div class="ecard-top">
                <div class="ename">{e.nume || '—'}{#if e.producator} — {e.producator}{/if}</div>
                <div class="ecard-actions">
                  <button class="att-btn" title="Editeaza" onclick={() => editEquip(e)}><Pencil size={14} /></button>
                  <button class="att-btn danger" title="Sterge" onclick={() => { equipDeleteId = e.id; showEquipDelete = true }}><Trash2 size={14} /></button>
                </div>
              </div>
              <div class="edetails">
                {#if e.model}<span>Model: {e.model}</span>{/if}
                {#if e.serial_number}<span>Serie: {e.serial_number}</span>{/if}
              </div>
              {#if eparams.length > 0}
                <div class="eparams">
                  {#each eparams as [k, v]}
                    <div class="eparam"><code>{k}</code><span>{v}</span></div>
                  {/each}
                </div>
              {/if}
            </Card>
          {/each}</div>
        {/if}

      {:else if activeTab === 'attachments'}
        <AttachmentsTab projectId={params.id} />

      {:else if activeTab === 'info'}
        <div class="igrid">
          {#each [['Client', project.client], ['Locatie', project.locatie], ['Echipament', project.echipament_principal], ['Producator', project.producator], ['Cod proiect', project.cod_proiect], ['PM', project.pm], ['Nr. comanda', project.nr_comanda], ['Nr. contract', project.nr_contract], ['Data incepere', formatDate(project.data_incepere)], ['Deadline', formatDate(project.deadline)]] as [label, val]}
            <div class="irow"><span class="ilabel">{label}</span><span>{val || '—'}</span></div>
          {/each}
          {#if project.observatii}<div class="ifull"><span class="ilabel">Observatii</span><p>{project.observatii}</p></div>{/if}
          {#if project.service_before}<div class="ifull"><span class="ilabel">Service Before</span><p>{project.service_before}</p></div>{/if}
          {#if project.service_after}<div class="ifull"><span class="ilabel">Service After</span><p>{project.service_after}</p></div>{/if}
          {#if timerSessions.sessions?.length > 0}
            <div class="ifull">
              <span class="ilabel">Sesiuni timer ({timerSessions.sessions.length})</span>
              <div class="sess-list">
                {#each timerSessions.sessions.slice(0, 10) as s}
                  <div class="sess"><span>{s.start_time ? formatDate(s.start_time) : '—'}</span><span class="sess-dur">{formatDuration(s.durata_secunde)}</span></div>
                {/each}
              </div>
            </div>
          {/if}
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

<Modal bind:open={showStopNote} title="Opreste timer" size="sm">
  <div class="stopnote">
    <Input label="Titlu (optional)" bind:value={stopNoteTitle} placeholder="Ex: Configurare parametri" />
    <label class="ta-field">
      <span class="ta-label">Nota jurnal (optional)</span>
      <textarea rows="3" bind:value={stopNoteText} placeholder="Ce ai lucrat in aceasta sesiune?"></textarea>
    </label>
    <div class="modal-actions">
      <Button variant="secondary" loading={stoppingWithNote} onclick={stopSimple}>Stop fara nota</Button>
      <Button loading={stoppingWithNote} disabled={!stopNoteTitle.trim() && !stopNoteText.trim()} onclick={stopWithNote}><StickyNote size={14} /> Stop cu nota</Button>
    </div>
  </div>
</Modal>

<ProjectFormModal bind:open={showEditModal} {project} onsaved={() => load()} />
<EquipmentFormModal bind:open={showEquipModal} projectId={params.id} equipment={editingEquipment} onsaved={() => reloadEquipment()} />
<ConfirmDialog bind:open={showDeleteConfirm} title="Sterge proiect" message={`Stergi proiectul "${project?.nume}"? Toate datele (taskuri, jurnal, atasamente, echipamente) vor fi sterse definitiv.`} confirmLabel="Sterge definitiv" onconfirm={handleDeleteProject} />
<ConfirmDialog bind:open={showJournalDelete} title="Sterge intrare" message="Stergi aceasta intrare din jurnal?" confirmLabel="Sterge" onconfirm={doDeleteJournal} />
<ConfirmDialog bind:open={showEquipDelete} title="Sterge echipament" message="Stergi acest echipament?" confirmLabel="Sterge" onconfirm={doDeleteEquip} />

<style>
  .page { padding: var(--space-lg); }
  .back { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-small); color: var(--text-dim); margin-bottom: var(--space-md); cursor: pointer; }
  .back:hover { color: var(--accent); }

  .project-header { margin-bottom: var(--space-lg); }
  .header-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-md); }
  .title-area { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }
  .title-area h1 { font-size: var(--font-h1); font-weight: 700; color: var(--text); }
  .header-actions { display: flex; gap: var(--space-xs); flex-wrap: wrap; flex-shrink: 0; }
  .tip { font-size: 10px; font-weight: 600; text-transform: uppercase; padding: 2px 8px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-secondary); }
  .tip.pif { background: var(--accent-subtle); color: var(--accent); }
  .tip.service { background: var(--service-subtle); color: var(--service-accent); }
  .meta { font-size: var(--font-small); color: var(--text-dim); margin-top: 4px; display: flex; gap: var(--space-xs); }
  .pstats { display: flex; gap: var(--space-lg); margin-top: var(--space-md); padding: var(--space-md); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); }
  .ps { text-align: center; }
  .ps-val { display: block; font-size: var(--font-h2); font-weight: 600; color: var(--text); font-feature-settings: "tnum"; }
  .ps-lbl { font-size: var(--font-tiny); color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; }

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
  .trow { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-xs) var(--space-sm); border-left: 2px solid var(--border); border-radius: var(--radius-xs); margin-bottom: 2px; transition: background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); }
  .trow:hover { background: var(--bg-surface); transform: translateX(2px); }
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

  .jform { margin-bottom: var(--space-md); display: flex; flex-direction: column; gap: var(--space-sm); }
  .jform textarea { width: 100%; padding: 10px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-body); font-family: inherit; resize: vertical; }
  .jform-row { display: flex; gap: var(--space-sm); justify-content: flex-end; align-items: center; }
  .jdate-input { padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); min-height: 38px; }
  .jlist { display: flex; flex-direction: column; gap: var(--space-sm); }
  .jentry { padding: var(--space-sm) var(--space-md); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-sm); }
  .jentry-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
  .jdate { font-size: var(--font-tiny); color: var(--text-dim); }
  .jdel { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); }
  .jdel:hover { background: var(--danger-subtle); color: var(--danger); }
  .jtext { font-size: var(--font-small); color: var(--text); line-height: 1.55; white-space: pre-wrap; }

  .clgroup { margin-bottom: var(--space-lg); }
  .clgroup-head { display: flex; align-items: center; justify-content: space-between; padding-bottom: var(--space-xs); margin-bottom: var(--space-xs); border-bottom: 1px solid var(--border); }
  .clgroup-count { font-size: var(--font-tiny); color: var(--text-dim); }
  .clrow { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-xs) var(--space-xs); border-radius: var(--radius-xs); }
  .clrow:hover { background: var(--bg-surface); }
  .clrow.done .cllabel { text-decoration: line-through; color: var(--text-dim); }
  .clmain { flex: 1; min-width: 0; }
  .cllabel { font-size: var(--font-small); color: var(--text); }
  .clcat { font-size: var(--font-tiny); color: var(--text-dim); }
  .cladd { display: flex; gap: var(--space-xs); margin-top: var(--space-xs); }
  .cladd input { flex: 1; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-small); }
  .cladd-btn { width: 38px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .cladd-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
  .cladd-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .elist { display: flex; flex-direction: column; gap: var(--space-sm); }
  .ecard-top { display: flex; align-items: center; justify-content: space-between; }
  .ecard-actions { display: flex; gap: 2px; }
  .ename { font-size: var(--font-small); font-weight: 600; color: var(--text); }
  .edetails { display: flex; gap: var(--space-md); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 4px; }
  .eparams { margin-top: var(--space-sm); display: flex; flex-direction: column; gap: 2px; border-top: 1px solid var(--border-subtle); padding-top: var(--space-sm); }
  .eparam { display: flex; justify-content: space-between; font-size: var(--font-tiny); }
  .eparam code { color: var(--accent); font-family: var(--font-mono); }
  .eparam span { color: var(--text-secondary); }
  .att-btn { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); }
  .att-btn:hover { background: var(--bg-hover); color: var(--text); }
  .att-btn.danger:hover { background: var(--danger-subtle); color: var(--danger); }

  .igrid { display: flex; flex-direction: column; gap: var(--space-sm); }
  .irow { display: flex; justify-content: space-between; font-size: var(--font-small); padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
  .ilabel { color: var(--text-dim); font-weight: 500; }
  .ifull { display: flex; flex-direction: column; gap: 4px; padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
  .ifull p { font-size: var(--font-small); color: var(--text-secondary); line-height: 1.55; white-space: pre-wrap; }
  .sess-list { display: flex; flex-direction: column; gap: 2px; }
  .sess { display: flex; justify-content: space-between; font-size: var(--font-tiny); color: var(--text-secondary); padding: 2px 0; }
  .sess-dur { font-family: var(--font-mono); color: var(--accent); }

  .stopnote { display: flex; flex-direction: column; gap: var(--space-md); }
  .ta-field { display: flex; flex-direction: column; gap: 4px; }
  .ta-label { font-size: var(--font-tiny); font-weight: 500; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; }
  .ta-field textarea { padding: 10px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-body); font-family: inherit; resize: vertical; }

  .modal-actions { display: flex; gap: var(--space-sm); justify-content: flex-end; margin-top: var(--space-lg); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .pstats { gap: var(--space-md); flex-wrap: wrap; }
    .header-top { flex-direction: column; }
    .edetails { flex-wrap: wrap; gap: var(--space-sm); }
    .trow { padding: var(--space-sm); }
    .back { min-height: 44px; }
  }
</style>
