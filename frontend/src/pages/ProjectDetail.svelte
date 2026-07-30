<script>
  import { onMount } from 'svelte'
  import { slide, fade } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { ArrowLeft, Plus, CheckCircle2, AlertCircle, ListTodo, Settings2, FileDown, ChevronDown, ChevronRight, Repeat, BookOpen, CalendarRange, CalendarPlus, ArrowRight } from '@lucide/svelte'
  import ProjectGantt from '../components/gantt/ProjectGantt.svelte'
  import ImplPeriods from '../components/projects/ImplPeriods.svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import {
    loadProjectDetail, loadProjectTasks, deleteProject, updateProject,
  } from '../stores/projects.svelte.js'
  import { apiJson } from '../lib/api.js'
  import { updateTask, createTask, deleteTask, loadSubtasks, createSubtask, updateSubtask, deleteSubtask } from '../stores/tasks.svelte.js'
  import { PROJECT_STATUS_LABELS, STATUS_COLORS, formatDate, dueColor, isFutureRecurrence } from '../lib/formatters.js'
  import { etichetaTermen } from '../lib/grupare.js'
  import { ecran } from '../lib/ecran.svelte.js'
  import { exportMarkdown } from '../lib/exportMd.js'
  import RichText from '../components/ui/RichText.svelte'
  import { navigate, router } from '../lib/router.svelte.js'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../lib/motion.svelte.js'
  import { focusOnLand, focusKey } from '../lib/focus.js'
  import { glisare } from '../lib/glisare.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import Badge from '../components/ui/Badge.svelte'
  import Card from '../components/ui/Card.svelte'
  import Button from '../components/ui/Button.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import Input from '../components/ui/Input.svelte'
  import Select from '../components/ui/Select.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  import ProjectFormModal from '../components/projects/ProjectFormModal.svelte'
  import MarkdownView from '../components/notes/MarkdownView.svelte'
  import RichTextEditor from '../components/ui/RichTextEditor.svelte'

  let { params } = $props()
  let project = $state(null)
  let tasks = $state([])
  let taskDeleteId = $state(null)
  let showTaskDelete = $state(false)
  let loading = $state(true)
  let error = $state(null)
  let activeTab = $state('tasks')

  // Jump from the read-only Gantt to a task in the Tasks tab (scroll + flash).
  function openTaskFromGantt(taskId) {
    router.query = { ...router.query, focus: focusKey('task', taskId) }
    activeTab = 'tasks'
  }

  let newTaskTitle = $state('')
  let creatingTask = $state(false)
  let showTaskEditModal = $state(false)
  let editingTask = $state(null)
  let taskFormTitle = $state('')
  let taskFormDesc = $state('')
  let taskFormDeadline = $state('')
  let taskFormRecurenta = $state('')
  let taskFormSaving = $state(false)
  let showNoteModal = $state(false)
  let noteTask = $state(null)
  let noteDraft = $state('')
  let noteSaving = $state(false)

  let showEditModal = $state(false)
  let showDeleteConfirm = $state(false)

  // Subtask state
  let expandedTask = $state(null)
  let subtasksCache = $state({})
  let newSubtaskTitle = $state('')
  let subtaskLoading = $state(false)

  // Done tasks collapse
  let showDoneTasks = $state(false)

  // Field edit modal (observatii, service_before, service_after)
  let showFieldEdit = $state(false)
  let editField = $state(null)
  let editValue = $state('')
  let editLabel = $state('')
  let editSaving = $state(false)

  // Echipamente + Atasamente scoase din navigatie (2026-07-27, pregatire v28):
  // parametrii de drive stau in wiki (skill drive-backup), backup-urile brute in
  // raw/projects/<slug>/. Codul ramane pana la migratie.
  // Tabul „Info" a fost scos (2026-07-27): repeta antetul README-ului din wiki
  // (Client, Locație, Cod proiect, Nr. comandă), iar 4 din 10 campuri erau
  // aproape mereu goale. Datele au trecut in bara laterala, iar editorul de
  // perioade — singurul lucru nedublat de acolo — a trecut la Gantt.
  const tabs = [
    { key: 'tasks', label: 'Taskuri', icon: ListTodo },
    { key: 'gantt', label: 'Gantt', icon: CalendarRange },
    { key: 'wiki', label: 'Wiki', icon: BookOpen },
  ]

  // Wiki tab — notele proiectului din vault-ul Obsidian (read-only, lazy load)
  let wikiInfo = $state(null)
  let wikiNote = $state(null)
  let wikiContent = $state('')
  let wikiListLoading = $state(false)
  let wikiNoteLoading = $state(false)

  async function loadWiki() {
    wikiListLoading = true
    try {
      wikiInfo = await apiJson(`/api/proiecte/${params.id}/wiki`)
      if (wikiInfo.notes?.length && !wikiNote) openWikiNote(wikiInfo.notes[0])
    } catch (e) {
      wikiInfo = { error: e.message, notes: [] }
    } finally { wikiListLoading = false }
  }

  let wikiEditing = $state(false)
  let wikiDraft = $state('')
  let wikiSaving = $state(false)

  function startWikiEdit() {
    wikiDraft = wikiContent
    wikiEditing = true
  }

  async function saveWikiEdit() {
    wikiSaving = true
    try {
      await apiJson('/api/obsidian/note', { method: 'PUT', body: { path: wikiNote.path, content: wikiDraft } })
      wikiContent = wikiDraft
      wikiEditing = false
      toast('Notă salvată și împinsă în repo (git push)', 'success')
    } catch (e) {
      toast(`Eroare la salvare: ${e.message}`, 'error')
    } finally { wikiSaving = false }
  }

  async function openWikiNote(note) {
    wikiEditing = false
    wikiNote = note
    wikiNoteLoading = true
    try {
      const data = await apiJson(`/api/obsidian/note?path=${encodeURIComponent(note.path)}`)
      wikiContent = data.content || ''
    } catch (e) {
      wikiContent = ''
      toast(`Eroare la încărcarea notei: ${e.message}`, 'error')
    } finally { wikiNoteLoading = false }
  }

  function handleProjectWikilink(target) {
    const t = target.toLowerCase()
    const list = wikiInfo?.notes || []
    const found = list.find(n => (n.title || '').toLowerCase() === t)
      || list.find(n => (n.path || '').toLowerCase().endsWith(t + '.md'))
      || list.find(n => (n.title || '').toLowerCase().includes(t))
    if (found) openWikiNote(found)
    else toast(`Nota "${target}" nu e în folderul proiectului`, 'error')
  }

  $effect(() => {
    if (activeTab === 'wiki' && !wikiInfo && !wikiListLoading) loadWiki()
  })

  async function load() {
    loading = true
    try {
      project = await loadProjectDetail(params.id)
      const t = await loadProjectTasks(params.id).catch(() => [])
      tasks = Array.isArray(t) ? t : t.tasks || []
    } catch (err) {
      error = err.message
    } finally { loading = false }
  }

  async function reloadTasks() {
    const t = await loadProjectTasks(params.id).catch(() => [])
    tasks = Array.isArray(t) ? t : t.tasks || []
  }

  async function toggleTaskStatus(task) {
    const next = task.status === 'done' ? 'to_do' : 'done'
    tasks = tasks.map(t => t.id === task.id ? { ...t, status: next } : t)
    const res = await updateTask(task.id, { status: next })
    if (res?.recurring_spawned) {
      toast(`Finalizat ✓ — următoarea apariție: ${formatDate(res.recurring_next)}`, 'success')
      await reloadTasks()
      return
    }
    // „Anulează", ca la taskurile globale: pe telefon bifatul vine si din glisare,
    // deci vine si din greseala, iar randul pleaca din lista activa.
    if (next === 'done') {
      toastUndo(`Făcut: ${task.titlu.slice(0, 34)}${task.titlu.length > 34 ? '…' : ''}`, {
        onUndo: async () => {
          tasks = tasks.map(t => t.id === task.id ? { ...t, status: 'to_do' } : t)
          await updateTask(task.id, { status: 'to_do' })
          await reloadTasks()
        },
      })
    }
  }

  /** Muta termenul unui task de proiect. Ca la /tasks: se poate intoarce. */
  async function setTermenTask(t, zile) {
    const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + zile)
    await aplicaTermen(t, d.toISOString().slice(0, 10))
  }
  async function setTermenTaskData(t, v) { await aplicaTermen(t, v || '') }

  async function aplicaTermen(t, v) {
    const vechi = t.data_scadenta || ''
    try {
      await updateTask(t.id, { data_scadenta: v })
      await reloadTasks()
      toastUndo(v ? `Mutat pe ${etichetaTermen(v)}` : 'Termen scos', {
        onUndo: async () => { await updateTask(t.id, { data_scadenta: vechi }); await reloadTasks() },
      })
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function handleCreateTask() {
    if (!newTaskTitle.trim() || creatingTask) return
    creatingTask = true
    try {
      await createTask(params.id, { titlu: newTaskTitle.trim(), status: 'to_do' })
      newTaskTitle = ''
      await reloadTasks()
    } finally { creatingTask = false }
  }

  function openTaskEditModal(t) {
    editingTask = t
    taskFormTitle = t.titlu || ''
    taskFormDesc = t.descriere || ''
    taskFormDeadline = (t.data_scadenta || '').slice(0, 10)
    taskFormRecurenta = t.recurenta || ''
    showTaskEditModal = true
  }

  async function handleTaskEdit() {
    if (!editingTask || !taskFormTitle.trim() || taskFormSaving) return
    taskFormSaving = true
    try {
      await updateTask(editingTask.id, {
        titlu: taskFormTitle.trim(),
        descriere: taskFormDesc.trim(),
        data_scadenta: taskFormDeadline,
        recurenta: taskFormRecurenta || null,
      })
      showTaskEditModal = false
      editingTask = null
      await reloadTasks()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { taskFormSaving = false }
  }

  const TASK_STATUS_CYCLE = ['to_do', 'in_lucru', 'done']

  function openNoteModal(t) {
    noteTask = t
    noteDraft = t.descriere || ''
    showNoteModal = true
  }

  async function saveNote() {
    if (noteSaving || !noteTask) return
    noteSaving = true
    try {
      await updateTask(noteTask.id, { descriere: noteDraft })
      showNoteModal = false
      await reloadTasks()
      toast('Salvat', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { noteSaving = false }
  }

  async function handleDeleteProject() {
    await deleteProject(params.id)
    toast('Proiect șters', 'success')
    navigate('/projects')
  }

  async function doDeleteTask() {
    if (!taskDeleteId) return
    await deleteTask(taskDeleteId)
    taskDeleteId = null
    await reloadTasks()
    toast('Task șters', 'success')
  }


  // Subtask functions
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
    const next = sub.done ? 0 : 1
    const taskId = expandedTask
    subtasksCache = { ...subtasksCache, [taskId]: subtasksCache[taskId].map(s => s.id === sub.id ? { ...s, done: next } : s) }
    try {
      await updateSubtask(sub.id, { done: next })
    } catch (_) {
      subtasksCache = { ...subtasksCache, [taskId]: subtasksCache[taskId].map(s => s.id === sub.id ? { ...s, done: sub.done } : s) }
    }
    await reloadTasks()
  }

  async function addSubtask(taskId) {
    if (!newSubtaskTitle.trim()) return
    try {
      await createSubtask(taskId, newSubtaskTitle.trim())
      newSubtaskTitle = ''
      const subs = await loadSubtasks(taskId)
      subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
      await reloadTasks()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  function removeSubtask(subId, taskId) {
    // Stergere reversibila: scoatem optimist din UI + toast „Anulează" ~6s.
    // Stergerea reala pe server abia la expirare/inchidere (onCommit); undo o repune.
    const list = subtasksCache[taskId] || []
    const idx = list.findIndex(s => s.id === subId)
    if (idx === -1) return
    const removed = list[idx]
    subtasksCache = { ...subtasksCache, [taskId]: list.filter(s => s.id !== subId) }
    toastUndo('Subtask șters', {
      onUndo: () => {
        const cur = [...(subtasksCache[taskId] || [])]
        cur.splice(Math.min(idx, cur.length), 0, removed)
        subtasksCache = { ...subtasksCache, [taskId]: cur }
      },
      onCommit: async () => {
        try {
          await deleteSubtask(subId)
          await reloadTasks()
        } catch (e) {
          toast(`Eroare: ${e.message}`, 'error')
          const subs = await loadSubtasks(taskId)
          subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
        }
      },
    })
  }

  function exportPdf() {
    window.open(`/api/export/pdf?project_id=${params.id}`, '_blank')
  }

  async function exportMd() {
    try {
      await exportMarkdown(params.id)
      toast('Export Markdown descărcat', 'success')
    } catch (e) {
      toast(`Eroare la export: ${e.message}`, 'error')
    }
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

  function openFieldEdit(field, label) {
    editField = field
    editValue = project[field] || ''
    editLabel = label
    showFieldEdit = true
  }

  async function saveFieldEdit() {
    editSaving = true
    try {
      await updateProject(params.id, { [editField]: editValue })
      project = { ...project, [editField]: editValue }
      showFieldEdit = false
      toast('Salvat', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { editSaving = false }
  }

  onMount(() => { load() })

  // Datele de identificare, mutate in bara laterala din fostul tab „Info"
  // (2026-07-27): tabul repeta antetul README-ului din wiki, iar 4 din 10 campuri
  // erau aproape mereu goale. Randurile fara valoare nu se deseneaza deloc.
  const detalii = $derived(([
    ['Locație', project?.locatie],
    ['Producător', project?.producator],
    ['Cod proiect', project?.cod_proiect],
    ['Nr. comandă', project?.nr_comanda],
    // „Nr. contract" (1/18), „PM" (4/18) si „Început" (5/18) au plecat in v36.
    // Începutul se citeste din perioade — Ganttul de mai jos il arata.
  ]).filter(([, v]) => String(v ?? '').trim()))

  const tasksDone = $derived(tasks.filter(t => t.status === 'done' || t.status === 'finalizat').length)
  // Hide a recurring task's next occurrence until its scadenta arrives (see Tasks.svelte).
  const activeTasks = $derived(tasks.filter(t => t.status !== 'done' && t.status !== 'finalizat' && !isFutureRecurrence(t)))
  const doneTasks = $derived(tasks.filter(t => t.status === 'done' || t.status === 'finalizat'))

  // Rail: progres taskuri + urmatoarea perioada. Deadline-ul a plecat in v30 —
  // Ion nu se lua dupa el niciodata; ce stie cu adevarat sunt perioadele.
  const taskPct = $derived(tasks.length ? Math.round((tasksDone / tasks.length) * 100) : 0)
  const FAZA_LABEL = { pregatire: 'Pregătire', implementare: 'Implementare' }
  const urmDays = $derived.by(() => {
    if (!project?.urmatoarea) return null
    return Math.round((new Date(String(project.urmatoarea).slice(0, 10)) - new Date(new Date().toDateString())) / 86400000)
  })
  function urmLabel(d) {
    if (d === null) return ''
    if (d <= 0) return 'în desfășurare'
    if (d === 1) return 'mâine'
    return `peste ${d} zile`
  }

  // Ziua închiderii se numără în urmă, nu înainte — „în desfășurare" ar fi absurd
  // pentru un proiect închis, iar ea decide până unde ține Calendarul perioadele.
  const zileDeLaFinal = $derived.by(() => {
    if (!project?.data_finalizare) return null
    return Math.round((new Date(new Date().toDateString()) - new Date(String(project.data_finalizare).slice(0, 10))) / 86400000)
  })
  function finalLabel(d) {
    if (d === null) return ''
    if (d <= 0) return 'astăzi'
    if (d === 1) return 'ieri'
    if (d < 30) return `acum ${d} zile`
    return ''
  }
</script>

<div class="page">
  <button class="back" onclick={() => navigate('/projects')}><ArrowLeft size={16} /> Proiecte</button>

  {#if loading}
    <Skeleton width="60%" height="24px" />
  {:else if error}
    <ErrorState message={error} onretry={load} />
  {:else if project}
    <div class="project-header">
      <div class="header-top">
        <div class="title-area">
          {#if project.tip}<span class="tip" class:pif={project.tip === 'PIF'} class:service={project.tip === 'Service'}>{project.tip}</span>{/if}
          <h1>{project.nume || '—'}</h1>
          <Badge label={PROJECT_STATUS_LABELS[project.status] || project.status || '—'} color={STATUS_COLORS[project.status] || 'var(--text-dim)'} />
        </div>
        <div class="header-actions">
          <Button variant="secondary" size="sm" onclick={() => showEditModal = true}><SolidIcon name="pencil" size={14} /> Edit</Button>
          <Button variant="secondary" size="sm" onclick={exportPdf}><FileDown size={14} /> PDF</Button>
          <Button variant="secondary" size="sm" onclick={exportMd}><SolidIcon name="file" size={14} /> MD</Button>
          <Button variant="ghost" size="sm" onclick={() => showDeleteConfirm = true}><SolidIcon name="trash" size={14} /></Button>
        </div>
      </div>
      <div class="meta">
        {#if project.client}<span>{project.client}</span>{/if}
        {#if project.echipament_principal}<span>· {project.echipament_principal}</span>{/if}
        {#if project.cod_proiect}<span>· {project.cod_proiect}</span>{/if}
      </div>
    </div>

    <!-- Layout V3: continut principal + rail persistent -->
    <div class="rail-grid">
    <div class="rail-main">

      <div class="field-section" role="button" tabindex="0" title="Click pentru a edita"
        onclick={() => openFieldEdit('observatii', 'Observații Tehnice')}
        onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openFieldEdit('observatii', 'Observații Tehnice') } }}>
        <div class="field-header">
          <span class="f-ico"><SolidIcon name="file" size={13} /></span>
          <span class="field-label">Observații Tehnice</span>
          {#if project.updated_at}<span class="f-meta">actualizat {formatDate(project.updated_at)}</span>{/if}
        </div>
        {#if project.observatii}
          <div class="field-body">
            <RichText value={project.observatii} collapsible noToggle maxHeight={240} />
          </div>
        {:else}
          <div class="field-empty">Click pentru a adăuga...</div>
        {/if}
      </div>

      {#if project.tip === 'Service'}
        <div class="field-section" role="button" tabindex="0" title="Click pentru a edita"
          onclick={() => openFieldEdit('service_before', 'Constatări înainte de intervenție')}
          onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openFieldEdit('service_before', 'Constatări înainte de intervenție') } }}>
          <div class="field-header">
            <span class="f-ico f-red"><AlertCircle size={13} /></span>
            <span class="field-label">Constatări înainte de intervenție</span>
            {#if project.updated_at}<span class="f-meta">actualizat {formatDate(project.updated_at)}</span>{/if}
          </div>
          {#if project.service_before}
            <div class="field-body">
              <RichText value={project.service_before} collapsible noToggle maxHeight={240} />
            </div>
          {:else}
            <div class="field-empty">Click pentru a adăuga...</div>
          {/if}
        </div>

        <div class="field-section" role="button" tabindex="0" title="Click pentru a edita"
          onclick={() => openFieldEdit('service_after', 'Acțiuni și rezultat')}
          onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openFieldEdit('service_after', 'Acțiuni și rezultat') } }}>
          <div class="field-header">
            <span class="f-ico f-green"><CheckCircle2 size={13} /></span>
            <span class="field-label">Acțiuni și rezultat</span>
            {#if project.updated_at}<span class="f-meta">actualizat {formatDate(project.updated_at)}</span>{/if}
          </div>
          {#if project.service_after}
            <div class="field-body">
              <RichText value={project.service_after} collapsible noToggle maxHeight={240} />
            </div>
          {:else}
            <div class="field-empty">Click pentru a adăuga...</div>
          {/if}
        </div>
      {/if}

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
      {#key activeTab}
      <div class="tab-pane" in:fade={{ duration: motionDuration(DUR_FAST) }}>
      {#if activeTab === 'tasks'}
        <div class="tab-header">
          <span class="tab-sub">{tasksDone}/{tasks.length} finalizate</span>
        </div>
        <form class="quick-add" onsubmit={(e) => { e.preventDefault(); handleCreateTask() }}>
          <input type="text" placeholder="Task rapid... Enter pentru a adăuga" bind:value={newTaskTitle} disabled={creatingTask} />
          <button type="submit" class="quick-add-btn" disabled={!newTaskTitle.trim() || creatingTask} title="Adaugă task"><Plus size={16} /></button>
        </form>
        {#if tasks.length === 0}<p class="empty">Niciun task.</p>
        {:else}
          <div class="task-list">
            {#each activeTasks as t, i (t.id)}
              <div class="trow-wrap" animate:flip={{ duration: motionDuration(DUR_BASE) }}>
                <div class="trow" use:focusOnLand={focusKey('task', t.id)} style="--sev: {dueColor(t.data_scadenta)}"
                     use:glisare={{ latime: 232, activ: ecran.telefon, onBifa: () => toggleTaskStatus(t) }}>
                  <!-- Editarea si stergerea stau in panoul de sub rand (glisare
                       spre stanga); glisarea spre dreapta bifeaza. La fel ca in
                       Taskuri si pe „Astazi". -->
                  <!-- Aceeasi gramatica de gest ca la /tasks: planificarea intai
                       (e ce faci des cu un task), apoi intretinerea. Doua liste de
                       taskuri cu acelasi rand nu au voie sa raspunda diferit la
                       acelasi gest — altfel gestul nu se invata niciodata. -->
                  <div class="gl-actiuni">
                    <button class="glb" onclick={() => setTermenTask(t, 0)} title="Termen azi">
                      <CalendarPlus size={16} /><span>Azi</span>
                    </button>
                    <button class="glb" onclick={() => setTermenTask(t, 1)} title="Termen mâine">
                      <ArrowRight size={16} /><span>Mâine</span>
                    </button>
                    <span class="glb datewrap" title="Alege ziua">
                      <DatePicker value={t.data_scadenta} placeholder="Dată" onchange={(v) => setTermenTaskData(t, v)} />
                      <span>Dată</span>
                    </span>
                    <button class="glb danger" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Șterge task">
                      <SolidIcon name="trash" size={16} /><span>Șterge</span>
                    </button>
                  </div>
                  <div class="gl-fata">
                  <span class="tix">{String(i + 1).padStart(2, '0')}</span>
                  <button class="check" onclick={() => toggleTaskStatus(t)}>
                    <div class="check-empty"></div>
                  </button>
                  <button class="tmain" onclick={() => toggleTaskExpand(t.id)}>
                    <div class="ttitle-row">
                      {#if expandedTask === t.id}<ChevronDown size={14} />{:else}<ChevronRight size={14} />{/if}
                      <span class="ttitle">{t.titlu}</span>
                    </div>
                    <div class="tinfo">
                      {#if t.recurenta}<span class="recur-badge" title="Recurent: {t.recurenta}"><Repeat size={10} /> {t.recurenta}</span>{/if}
                      {#if t.subtask_total}
                        <span class="tsub-chip">{t.subtask_done || 0}/{t.subtask_total}</span>
                      {/if}
                      {#if t.descriere}<span class="note-ind" title="Are notiță"><SolidIcon name="notes" size={10} /></span>{/if}
                      {#if t.data_scadenta}
                        <!-- „azi" / „acum 2 zile" / „vineri", ca in Taskuri. O data plina te pune
                             sa numeri in cap la fiecare rand, iar aici randurile sunt
                             tocmai lucrurile pe care le iei in ordine. -->
                        <span class="tdeadline" class:overdue={isOverdue(t.data_scadenta)} class:today={isToday(t.data_scadenta)} class:soon={isSoon(t.data_scadenta)}>{etichetaTermen(t.data_scadenta)}</span>
                      {/if}
                    </div>
                  </button>
                  <div class="task-actions">
                    <button class="task-edit" onclick={() => openTaskEditModal(t)} title="Editează task"><SolidIcon name="pencil" size={13} /></button>
                    <button class="task-del" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Șterge task"><SolidIcon name="trash" size={13} /></button>
                  </div>
                  </div>
                </div>
                {#if expandedTask === t.id}
                  {@const subs = subtasksCache[t.id] || []}
                  {@const doneCount = subs.filter(s => s.done).length}
                  <div class="subtask-body" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
                    {#if t.descriere}
                      <div class="note-block">
                        <RichText value={t.descriere} class="note-content" collapsible maxHeight={200} />
                        <button class="note-edit-btn" title="Editează notițe" onclick={() => openNoteModal(t)}><SolidIcon name="pencil" size={12} /> Editează</button>
                      </div>
                    {/if}

                    <div class="detail-actions">
                      {#if !t.descriere}
                        <button class="detail-chip" onclick={() => openNoteModal(t)}><SolidIcon name="notes" size={13} /> Descriere</button>
                      {/if}
                    </div>

                    <div class="sub-section">
                      <div class="sub-head">
                        <span class="sub-cap">Subtaskuri</span>
                        {#if subs.length}<span class="sub-prog">{doneCount}/{subs.length}</span>{/if}
                      </div>
                      {#if subtaskLoading && !subtasksCache[t.id]}
                        <div class="sub-loading">Se încarcă...</div>
                      {:else}
                        {#each subs as sub (sub.id)}
                          <div class="sub-row" class:sub-done={sub.done}>
                            <input type="checkbox" class="cbx" checked={!!sub.done} onchange={() => toggleSubtaskDone(sub)} />
                            <span class="sub-title">{sub.titlu}</span>
                            <button class="sub-del" onclick={() => removeSubtask(sub.id, t.id)}><SolidIcon name="trash" size={12} /></button>
                          </div>
                        {/each}
                        <form class="sub-add" onsubmit={(e) => { e.preventDefault(); addSubtask(t.id) }}>
                          <input type="text" placeholder="Adaugă subtask..." bind:value={newSubtaskTitle} />
                          <button type="submit" class="sub-add-btn" disabled={!newSubtaskTitle.trim()}><Plus size={14} /></button>
                        </form>
                      {/if}
                    </div>
                  </div>
                {/if}
              </div>
            {/each}

            {#if doneTasks.length > 0}
              <button class="done-sep" onclick={() => showDoneTasks = !showDoneTasks}>
                {#if showDoneTasks}<ChevronDown size={14} />{:else}<ChevronRight size={14} />{/if}
                <span>Finalizate ({doneTasks.length})</span>
              </button>
              {#if showDoneTasks}
                <div class="done-list" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
                {#each doneTasks as t, i (t.id)}
                  <div class="trow done" animate:flip={{ duration: motionDuration(DUR_BASE) }} use:focusOnLand={focusKey('task', t.id)} style="--sev: {dueColor(t.data_scadenta)}">
                    <span class="tix">{String(i + 1).padStart(2, '0')}</span>
                    <button class="check" onclick={() => toggleTaskStatus(t)}>
                      <CheckCircle2 size={16} />
                    </button>
                    <div class="tmain">
                      <div class="ttitle">{t.titlu}</div>
                    </div>
                  </div>
                {/each}
                </div>
              {/if}
            {/if}
          </div>
        {/if}

      {:else if activeTab === 'gantt'}
        <ProjectGantt projectId={params.id} onOpenTask={openTaskFromGantt} />
        <!-- Perioadele de implementare stateau in fostul tab „Info", langa datele
             de identificare — n-aveau ce cauta acolo. Locul lor e aici: sunt
             unitatea reala de planificare a proiectului, iar Ganttul e vederea
             lui in timp. -->
        <div style="margin-top: var(--space-md)"><ImplPeriods projectId={params.id} /></div>

      {:else if activeTab === 'wiki'}
        {#if wikiListLoading}
          <Skeleton height="120px" />
        {:else if !wikiInfo?.folder}
          <div class="wiki-empty">
            <BookOpen size={20} />
            <p>Proiectul nu e legat de un folder din vault.</p>
            <p class="wiki-hint">Setează câmpul <code>vault_folder</code> (ex. <code>wiki/job/projects/&lt;slug&gt;</code>) prin editare proiect sau API.</p>
          </div>
        {:else if !wikiInfo.configured}
          <div class="wiki-empty">
            <BookOpen size={20} />
            <p>Vault-ul Obsidian nu e configurat pe server.</p>
            <p class="wiki-hint">Administrativ → Obsidian → calea vault-ului.</p>
          </div>
        {:else if !wikiInfo.valid || !wikiInfo.notes.length}
          <div class="wiki-empty">
            <BookOpen size={20} />
            <p>Folderul <code>{wikiInfo.folder}</code> nu există (sau e gol) în copia vault de pe server.</p>
          </div>
        {:else}
          <div class="wiki-chips">
            {#each wikiInfo.notes as note (note.path)}
              <button class="wiki-chip" class:active={wikiNote?.path === note.path} onclick={() => openWikiNote(note)}>
                {note.path.slice((wikiInfo.folder + '/').length, -3)}
              </button>
            {/each}
          </div>
          {#if wikiNoteLoading}
            <Skeleton height="240px" />
          {:else if wikiEditing}
            <textarea class="wiki-editor" bind:value={wikiDraft} spellcheck="false"></textarea>
            <div class="wiki-edit-actions">
              <Button variant="secondary" onclick={() => wikiEditing = false}>Anulează</Button>
              <Button loading={wikiSaving} onclick={saveWikiEdit}>Salvează + push</Button>
            </div>
          {:else}
            <div class="wiki-body">
              <MarkdownView content={wikiContent} onwikilink={handleProjectWikilink} />
            </div>
            <div class="wiki-edit-actions">
              <Button variant="secondary" onclick={startWikiEdit}>Editează</Button>
            </div>
          {/if}
        {/if}

      {/if}
      </div>
      {/key}
    </div>

    </div>

    <aside class="rail">
      <section class="rcell cell-in">
        <div class="cell-label"><span class="ico ico-amber"><ListTodo size={12} /></span>Progres taskuri</div>
        <div class="rprog">
          <span class="rprog-num">{tasksDone}/{tasks.length}</span>
          <div class="rbar"><i style="width: {taskPct}%"></i></div>
        </div>
        <div class="rsub">{taskPct}% finalizate</div>
      </section>

      <!-- Un proiect închis nu mai are „următoarea perioadă" — celula ar rămâne
           „Neplanificat". În locul ei arătăm ziua închiderii, care e reperul la
           care Calendarul îi taie perioadele (v35): dacă e greșită, se vede aici
           și se corectează din Edit. -->
      <section class="rcell cell-in">
        {#if project.status === 'finalizat'}
          <div class="cell-label"><span class="ico ico-green"><SolidIcon name="check" size={12} /></span>Finalizat</div>
          {#if project.data_finalizare}
            <div class="rdate">{formatDate(project.data_finalizare)}</div>
            <div class="rsub">{finalLabel(zileDeLaFinal)}</div>
          {:else}
            <div class="rsub rsub-empty">Fără dată de închidere</div>
          {/if}
        {:else}
          <div class="cell-label"><span class="ico ico-red"><SolidIcon name="clock" size={12} /></span>Următoarea perioadă</div>
          {#if project.urmatoarea}
          <div class="rdate" class:urgent={urmDays !== null && urmDays <= 2}>{formatDate(project.urmatoarea)}{#if project.urmatoarea_sfarsit && project.urmatoarea_sfarsit !== project.urmatoarea}<span class="rdate-pana"> – {formatDate(project.urmatoarea_sfarsit)}</span>{/if}</div>
          <div class="rsub">{FAZA_LABEL[project.urmatoarea_faza] || ''}{project.urmatoarea_faza ? ' · ' : ''}{urmLabel(urmDays)}</div>
          {:else}
            <div class="rsub rsub-empty">Neplanificat</div>
          {/if}
        {/if}
      </section>

      <!-- Datele de identificare, mutate aici din fostul tab „Info" (2026-07-27).
           Tabul repeta antetul README-ului din wiki si avea 4 din 10 campuri
           aproape mereu goale (PM 4/20, contract 1/20, incepere 5/20).
           Randurile goale nu se mai deseneaza, deci celula ramane mica atunci
           cand proiectul are putine date completate. -->
      {#if detalii.length}
        <section class="rcell cell-in">
          <div class="cell-label"><span class="ico"><Settings2 size={12} /></span>Detalii</div>
          <dl class="rdet">
            {#each detalii as [eticheta, valoare]}
              <dt>{eticheta}</dt><dd>{valoare}</dd>
            {/each}
          </dl>
        </section>
      {/if}

    </aside>
    </div>
  {/if}
</div>

<ProjectFormModal bind:open={showEditModal} {project} onsaved={() => load()} />

<ConfirmDialog bind:open={showDeleteConfirm} title="Șterge proiect" message={`Ștergi proiectul "${project?.nume}"? Toate taskurile asociate vor fi șterse definitiv.`} confirmLabel="Șterge definitiv" onconfirm={handleDeleteProject} />
<ConfirmDialog bind:open={showTaskDelete} title="Șterge task" message="Ștergi acest task? Toate subtaskurile asociate vor fi șterse." confirmLabel="Șterge" onconfirm={doDeleteTask} />

<Modal bind:open={showFieldEdit} title={editLabel} size="doc">
  <div class="field-edit-modal">
    {#if showFieldEdit}
      <RichTextEditor bind:value={editValue} variant="doc" placeholder="Scrie aici..." onsave={saveFieldEdit} />
    {/if}
  </div>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showFieldEdit = false}>Anulează</Button>
      <Button loading={editSaving} onclick={saveFieldEdit}>Salvează</Button>
    </div>
  {/snippet}
</Modal>

<Modal bind:open={showTaskEditModal} title="Editează Task" size="md">
  <form class="task-form" onsubmit={(e) => { e.preventDefault(); handleTaskEdit() }}>
    <Input label="Titlu" bind:value={taskFormTitle} placeholder="Titlu task" />
    <label class="mf-field">
      <span class="mf-label">Descriere</span>
      <textarea class="mf-textarea" bind:value={taskFormDesc} placeholder="Detalii (opțional)" rows="3"></textarea>
    </label>
    <div class="mf-row">
      <div class="mf-field">
      </div>
      <div class="mf-field">
        <span class="mf-label">Termen</span>
        <DatePicker bind:value={taskFormDeadline} />
      </div>
    </div>
    <Select label="Recurență" bind:value={taskFormRecurenta} options={[{ value: '', label: 'Fără' }, { value: 'zilnic', label: 'Zilnic' }, { value: 'saptamanal', label: 'Săptămânal' }, { value: 'lunar', label: 'Lunar' }]} />
  </form>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showTaskEditModal = false}>Anulează</Button>
      <Button loading={taskFormSaving} disabled={!taskFormTitle.trim()} onclick={handleTaskEdit}>Salvează</Button>
    </div>
  {/snippet}
</Modal>

<Modal bind:open={showNoteModal} title={noteTask ? `Notițe — ${noteTask.titlu}` : 'Notițe task'} size="doc">
  <div class="field-edit-modal">
    {#if showNoteModal}
      <RichTextEditor bind:value={noteDraft} variant="doc" placeholder="Scrie notițe pentru acest task..." onsave={saveNote} />
    {/if}
  </div>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showNoteModal = false}>Anulează</Button>
      <Button loading={noteSaving} onclick={saveNote}>Salvează</Button>
    </div>
  {/snippet}
</Modal>

<style>
  .page { padding: var(--space-lg); }
  .back { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-small); color: var(--text-dim); margin-bottom: var(--space-md); cursor: pointer; }
  .back:hover { color: var(--accent); }

  .project-header { margin-bottom: var(--space-lg); }
  .header-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-md); }
  .title-area { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }
  .title-area h1 { font-size: var(--font-h1); font-weight: var(--fw-bold); color: var(--text); }
  .header-actions { display: flex; gap: var(--space-xs); flex-wrap: wrap; flex-shrink: 0; }
  .tip { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; padding: 2px 8px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-secondary); }
  .tip.pif { background: var(--accent-subtle); color: var(--accent); }
  .tip.service { background: var(--service-subtle); color: var(--service-accent); }
  /* `flex-wrap` + `min-width: 0`: fara ele cele trei fapte (client, echipament, cod)
     imparteau latimea in trei coloane egale si fiecare se rupea inauntru —
     „ACS880-07-" pe un rand, „0640A-3" pe urmatorul, langa „P-2026-" / „001".
     Un cod de echipament taiat in doua nu mai e un cod. Acum randul curge normal
     si trece pe randul urmator INTRE fapte, nu prin mijlocul lor. */
  .meta { font-size: var(--font-small); color: var(--text-dim); margin-top: 4px; display: flex; flex-wrap: wrap; gap: var(--space-xs); }
  .meta span { min-width: 0; }
  /* Layout V3: continut principal + rail persistent */
  .rail-grid { display: grid; grid-template-columns: 1fr 300px; gap: 14px; align-items: start; }
  .rail-main { min-width: 0; }
  .rail { display: flex; flex-direction: column; gap: 12px; position: sticky; top: calc(var(--header-height) + 16px); }
  .rcell { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 16px 18px; }
  .rprog { display: flex; align-items: baseline; gap: 10px; margin-top: 10px; }
  .rprog-num { font-family: var(--font-mono); font-size: 1.4rem; font-weight: var(--fw-bold); color: var(--text); line-height: 1; font-variant-numeric: tabular-nums; }
  .rbar { flex: 1; height: 6px; border-radius: var(--radius-full); background: var(--bg-panel); overflow: hidden; }
  .rbar i { display: block; height: 100%; background: var(--accent); border-radius: var(--radius-full); transition: width var(--dur-base) var(--ease); }
  .rdate { font-family: var(--font-mono); font-size: 1.15rem; font-weight: var(--fw-bold); color: var(--text); margin-top: 10px; font-variant-numeric: tabular-nums; }
  .rdate.urgent { color: var(--danger); }
  .rsub { font-size: var(--font-tiny); color: var(--text-dim); margin-top: 6px; }
  .rsub-empty { font-style: italic; margin-top: 10px; }

  /* Field sections in coloana stanga (observatii, service) */
  /* "Coala de document" (V1): gradient cald, umbra, antet cu chip + meta */
  .field-section { margin-bottom: var(--space-sm); background: linear-gradient(170deg, color-mix(in srgb, var(--accent) 5%, var(--bg-surface)) 0%, var(--bg-surface) 55%); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-md); transition: border-color var(--dur-fast) var(--ease); cursor: pointer; text-align: left; }
  .field-section:hover { border-color: var(--accent-ring); }
  .field-section:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .field-header { display: flex; align-items: center; gap: var(--space-sm); padding: 11px var(--space-md); font-size: var(--font-small); color: var(--text-secondary); border-bottom: 1px dashed var(--border); }
  .f-ico { width: 24px; height: 24px; border-radius: 8px; background: var(--accent-subtle); color: var(--accent); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .f-ico.f-red { background: var(--danger-subtle); color: var(--danger); }
  .f-ico.f-green { background: var(--success-subtle); color: var(--success); }
  .f-meta { font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text-faint); white-space: nowrap; flex-shrink: 0; }
  .field-label { flex: 1; font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-faint); }
  .field-body { font-size: var(--font-small); color: var(--text); line-height: 1.65; padding: var(--space-sm) var(--space-lg) var(--space-sm); overflow-x: auto; --rt-fade: var(--bg-surface); }
  .field-empty { padding: var(--space-sm) var(--space-lg) var(--space-md); font-size: var(--font-small); color: var(--text-faint); font-style: italic; cursor: pointer; width: 100%; text-align: left; }
  .field-empty:hover { color: var(--accent); }
  .field-edit-modal { display: flex; flex-direction: column; gap: var(--space-sm); }

  .tab-count { display: inline-flex; align-items: center; justify-content: center; min-width: 17px; height: 17px; padding: 0 4px; font-family: var(--font-mono); font-size: var(--font-micro); font-weight: var(--fw-semibold); line-height: 1; font-variant-numeric: tabular-nums; border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent-on-subtle); border: 1px solid var(--accent-ring); }

  .tab-content { min-height: 200px; }

  /* Wiki tab */
  .wiki-empty { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 32px 16px; color: var(--text-secondary); text-align: center; }
  .wiki-empty p { margin: 0; }
  .wiki-hint { font-size: var(--font-small, 0.82rem); color: var(--text-tertiary, var(--text-secondary)); }
  .wiki-empty code { font-family: var(--font-mono); font-size: 0.85em; background: var(--bg-elevated); padding: 1px 5px; border-radius: var(--radius-sm); }
  .wiki-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
  .wiki-chip { font-family: var(--font-mono); font-size: 0.78rem; padding: 4px 10px; border-radius: var(--radius-full); border: 1px solid var(--border); background: transparent; color: var(--text-secondary); cursor: pointer; }
  .wiki-chip:hover { background: var(--bg-hover); color: var(--text); }
  .wiki-chip.active { background: var(--accent-subtle); color: var(--accent-on-subtle); border-color: var(--accent-ring); }
  .wiki-body { padding: 4px 2px; }
  .wiki-editor { width: 100%; min-height: 360px; resize: vertical; font-family: var(--font-mono); font-size: 0.83rem; line-height: 1.5; color: var(--text); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 10px 12px; }
  .wiki-editor:focus { outline: none; border-color: var(--accent-ring); }
  .wiki-edit-actions { display: flex; gap: 8px; margin-top: 10px; }
  .tab-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-sm); }
  .tab-sub { font-size: var(--font-tiny); color: var(--text-dim); }
  .quick-add { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); }
  .quick-add input { flex: 1; min-height: 40px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); }
  .quick-add input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .empty { color: var(--text-dim); font-size: var(--font-small); padding: var(--space-lg) 0; text-align: center; }

  /* Task list */
  .task-list { display: flex; flex-direction: column; }
  .trow-wrap { display: flex; flex-direction: column; }
  /* Insula (V3+V2): fara bara pe stanga — underline de severitate jos + index mono ghost */
  .trow { position: relative; display: flex; align-items: center; gap: var(--space-sm); padding: 8px var(--space-sm) 10px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: 6px; transition: transform var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease), opacity var(--dur-base) var(--ease); }
  .trow::after { content: ''; position: absolute; left: 12px; bottom: 0; height: 2px; width: 40px; border-radius: 2px 2px 0 0; background: var(--sev, var(--border-strong)); box-shadow: 0 0 8px color-mix(in srgb, var(--sev, transparent) 45%, transparent); }
  /* Doar unde exista cursor — pe touch :hover ramane lipit dupa atingere. */
  @media (hover: hover) {
    .trow:hover { transform: translateX(4px); border-color: var(--border-strong); }
  }
  .trow:active { border-color: var(--border-strong); }
  /* ===== O SINGURA AXA DE CULOARE PE RAND =====
     Randul avea TREI sisteme de culoare care se bateau: severitatea (bordura din
     stanga + indexul), mov (categoria) si amber (subtaskuri, recurenta, numele
     proiectului). Masurat pe desktop, ierarhia iesea exact pe dos fata de cat
     conteaza lucrurile:
        index „01"   16px / 700 / colorat   <- cel mai tare text din rand
        categoria    11.2px / 600 / mov
        TITLUL       12.8px / 500           <- continutul propriu-zis
        termenul     10.4px / 600
     Un numar de ordine decorativ nu are ce cauta deasupra titlului.
     Regula, de-acum: CULOAREA E REZERVATA SEVERITATII (termen si bordura). Restul
     metadatelor sunt gri — se citesc cand le cauti, nu striga cand nu le cauti.
     Titlul creste la `--font-body`, indexul devine ce spunea documentatia ca e:
     o fantoma. */
  .tix { font-family: var(--font-mono); font-size: 0.8rem; font-weight: var(--fw-medium); letter-spacing: -0.02em; color: color-mix(in srgb, var(--sev, var(--border-strong)) 38%, transparent); min-width: 28px; flex-shrink: 0; font-variant-numeric: tabular-nums; }
  .done-list { display: flex; flex-direction: column; }
  .task-actions { display: flex; align-items: center; gap: var(--space-xs); flex-shrink: 0; }
  /* Pe desktop invelisul de glisare nu exista pentru layout. */
  .gl-fata { display: contents; }
  .gl-actiuni { display: none; }
  .trow.done { opacity: 0.5; }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; }
  .check:hover { color: var(--accent); }
  .trow.done .check { color: var(--success); }
  .check-empty { width: 16px; height: 16px; border: 2px solid var(--border); border-radius: 50%; }
  .tmain { flex: 1; min-width: 0; cursor: pointer; text-align: left; }
  /* Chipurile de status si prioritate au plecat in v34: taskul e facut sau nu,
     iar severitatea se citeste din bordura din stanga, dupa termen. */
  .recur-badge { display: inline-flex; align-items: center; gap: 3px; padding: 0 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-dim); font-weight: var(--fw-medium); }
  .task-form { display: flex; flex-direction: column; gap: var(--space-md); }
  .mf-textarea { padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-body); font-family: inherit; resize: vertical; min-height: 60px; }
  /* LA VEDERE, PALIDE — nu ascunse pana la hover.
     Aici erau `opacity: 0` pana la `.trow:hover`, in timp ce aceleasi butoane din
     /tasks stau mereu la vedere (decizia din 2026-06-18). Doua liste de taskuri cu
     acelasi rand si doua comportamente diferite — inveti unul si te inseala celalalt.
     Si mai rau: `opacity: 0` + `:hover` inseamna INEXISTENT pe orice ecran care se
     atinge, iar sub 768px scapau doar fiindca acolo intra alta regula. Un laptop cu
     ecran tactil sau o tableta in peisaj cadeau exact intre ele. */
  .task-edit { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease); }
  .task-edit:hover { color: var(--accent); background: var(--accent-subtle); }
  .ttitle-row { display: flex; align-items: center; gap: var(--space-xs); }
  .ttitle { font-size: var(--font-body); color: var(--text); font-weight: var(--fw-medium); }
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  .note-ind { display: inline-flex; align-items: center; color: var(--text-dim); }
  .tinfo { display: flex; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; align-items: center; }
  .tsub-chip { padding: 1px 6px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); font-weight: var(--fw-medium); font-size: var(--font-micro); }
  .tdeadline { font-size: var(--font-tiny); }
  .tdeadline.overdue { color: var(--danger); font-weight: var(--fw-semibold); }
  .tdeadline.today { color: var(--accent); font-weight: var(--fw-semibold); }
  .tdeadline.soon { color: var(--warning); }
  .task-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease); }
  .task-del:hover { color: var(--danger); background: var(--danger-subtle); }

  /* Done separator */
  .done-sep { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-xs); font-size: var(--font-tiny); font-weight: var(--fw-semibold); color: var(--text-dim); cursor: pointer; margin-top: var(--space-sm); border-top: 1px solid var(--border-subtle); text-transform: uppercase; letter-spacing: var(--tracking-wide); }
  .done-sep:hover { color: var(--text-secondary); }

  /* Subtask expanded area */
  /* Corp expandat: panou inset (nu mai pluteste pe negru), continut grupat cu gap */
  .subtask-body { margin-left: 26px; margin-bottom: var(--space-sm); padding: var(--space-12); background: var(--bg-surface); border: 1px solid var(--border-subtle); border-left: 2px solid var(--accent-subtle); border-radius: var(--radius-md); display: flex; flex-direction: column; gap: var(--space-12); }
  .detail-actions { display: flex; flex-wrap: wrap; gap: var(--space-xs); }
  .detail-chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-full); color: var(--text-secondary); font-size: var(--font-tiny); cursor: pointer; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .detail-chip:hover:not(:disabled) { color: var(--accent-on-subtle); border-color: var(--accent); background: var(--accent-subtle); }
  .detail-chip:active:not(:disabled) { transform: scale(0.97); }
  .detail-chip:disabled { opacity: 0.5; cursor: default; }
  .note-block { display: flex; flex-direction: column; gap: var(--space-xs); }
  .note-edit-btn { display: inline-flex; align-items: center; gap: 5px; align-self: flex-start; padding: 3px 8px; font-size: var(--font-tiny); color: var(--text-faint); cursor: pointer; border-radius: var(--radius-xs); transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .note-edit-btn:hover { color: var(--accent); background: var(--accent-subtle); }
  .sub-section { display: flex; flex-direction: column; gap: 2px; }
  .sub-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
  .sub-cap { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--text-faint); }
  .sub-prog { font-size: var(--font-tiny); color: var(--text-dim); font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .sub-row { display: flex; align-items: center; gap: var(--space-sm); padding: 3px 0; }
  .sub-row.sub-done .sub-title { text-decoration: line-through; color: var(--text-dim); }
  .sub-title { flex: 1; font-size: var(--font-small); color: var(--text); min-width: 0; }
  .sub-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: opacity var(--dur-fast); }
  .sub-row:hover .sub-del { opacity: 1; }
  .sub-del:hover { color: var(--danger); background: var(--danger-subtle); }
  .sub-add { display: flex; gap: var(--space-xs); margin-top: var(--space-xs); }
  .sub-add input { flex: 1; padding: 6px 10px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-small); }
  .sub-add input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .sub-add-btn { width: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .sub-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
  .sub-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .sub-loading { font-size: var(--font-tiny); color: var(--text-dim); padding: var(--space-xs) 0; }

  /* Detalii proiect (bara laterala) */
  /* Detalii in bara laterala (fostul tab Info) — grila de doua coloane, fara
     randuri goale: campurile necompletate nici nu ajung in lista. */
  .rdet { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 10px; margin: 6px 0 0; }
  .rdet dt { font-size: var(--font-micro); color: var(--text-faint); white-space: nowrap; }
  .rdet dd { margin: 0; font-size: var(--font-tiny); color: var(--text-secondary); overflow-wrap: anywhere; }

  .mf-row { display: flex; gap: var(--space-md); }
  .mf-field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
  .mf-label { font-size: var(--font-tiny); font-weight: var(--fw-medium); color: var(--text-secondary); text-transform: uppercase; letter-spacing: var(--tracking-wide); }

  /* Equipment import/copy */

  @media (max-width: 940px) {
    .rail-grid { grid-template-columns: 1fr; }
    .rail { position: static; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; order: -1; margin-bottom: var(--space-sm); }
    /* „Detalii" TREBUIE sa prinda ambele coloane. Celelalte celule au o cifra si
       o eticheta (1/3, o data) si stau bine pe jumatate de rand; asta are perechi
       eticheta-valoare, iar pe jumatate de rand valoarea primea 55px si se rupea
       inauntru: „P-2026-" pe un rand, „001" pe urmatorul. Un cod de proiect taiat
       in doua nu mai e un cod, e o greseala de tipar. */
    .rail > :global(.rcell:has(.rdet)) { grid-column: 1 / -1; }
  }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .header-top { flex-direction: column; }
    /* O LINIE, cu actiunile in panoul de sub rand (vezi Taskuri / „Astazi").
       Randul avea titlul sus si actiunile pe o linie proprie dedesubt. */
    .trow { padding: 0; flex-wrap: nowrap; align-items: center; overflow: hidden;
            position: relative; touch-action: pan-y; }
    .gl-fata { display: flex; align-items: center; gap: var(--space-sm); width: 100%;
               padding: 6px var(--space-sm); background: var(--bg-panel); position: relative;
               z-index: 1; border-radius: var(--radius-md); will-change: transform; }
    /* `:global(...)` pe clasa pusa din JS, NU pe intreg selectorul.
       Svelte NU se multumeste sa avertizeze „Unused CSS selector": TAIE regula din
       build. Iar `gl-tras`/`gl-bifa` sunt puse la RULARE de `lib/glisare.js`, deci
       nu apar in markup si compilatorul le crede moarte. Efectul, verificat in CSS-ul
       livrat: din toate regulile de gest ale aplicatiei supravietuise UNA. Adica
       glisai spre dreapta si nu vedeai verdele care spune „ai trecut pragul" —
       exact semnalul fara de care gestul e o loterie.
       Ancora (`.arow`/`.trow`/`.mrow`) ramane scoped, deci regula nu scapa in alte
       componente. */
    .trow:global(.gl-tras) .gl-fata { box-shadow: -6px 0 12px -8px rgba(0,0,0,0.55); }
    .task-actions { display: none; }
    .tix { display: none; }
    .ttitle { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .tinfo { flex-wrap: nowrap; overflow: hidden; }
    .tinfo > * { flex-shrink: 0; }

    .gl-actiuni { display: flex; position: absolute; top: 0; right: 0; bottom: 0; z-index: 0; align-items: stretch; }
    .glb { width: 58px; display: flex; flex-direction: column; align-items: center; justify-content: center;
           gap: 3px; border: none; background: var(--bg-elevated); color: var(--text-secondary);
           font-size: var(--font-micro); cursor: pointer; }
    .glb span { line-height: 1; }
    .glb.danger { background: var(--danger-subtle); color: var(--danger); }
    /* Calendarul din panou trebuie sa arate ca vecinii lui: o iconita cu eticheta,
       nu un camp. Aceeasi reteta ca in TodayBoard si Tasks. */
    .glb.datewrap { position: relative; }
    .glb.datewrap :global(.dp) { position: absolute; inset: 0; width: auto; }
    .glb.datewrap :global(.dp-trigger) { width: 100%; height: 100%; min-height: 0;
      padding: 0 0 14px; justify-content: center; background: none; border: none;
      box-shadow: none; color: inherit; }
    .glb.datewrap :global(.dp-value) { display: none; }
    .glb.datewrap > span { position: absolute; left: 0; right: 0; bottom: 11px;
      text-align: center; pointer-events: none; }
    .trow:global(.gl-bifa) { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }
    .back { min-height: 44px; }
    .subtask-body { margin-left: var(--space-sm); }
    .note-edit-btn { opacity: 1; }
    .quick-add input, .quick-add-btn { min-height: var(--tap-min); }
    .quick-add-btn { width: var(--tap-min); }
    /* Aceeasi reteta ca in Taskuri si Astăzi: 44px de atins, 30px de latime.
       Cercul de 18px intr-o caseta de 44 impingea titlul cu un sfert de ecran. */
    .check { position: relative; min-width: 30px; width: 30px; min-height: var(--tap-min);
      align-items: center; justify-content: center; padding: 0; }
    .check::after { content: ''; position: absolute; inset: -7px; }
    .sub-del, .sub-add-btn { min-width: var(--tap-min); min-height: var(--tap-min); }
    .sub-add input { min-height: var(--tap-min); }
    /* Filtrele de fisier din tabul Wiki — 29px. */
    .wiki-chip { min-height: var(--tap-min); padding: 4px 14px; }
    .wiki-chips { gap: var(--space-xs); }
    /* Bara de sus a paginii: „Edit", „PDF", „MD" si meniul. */
    .header-actions :global(.btn) { min-width: var(--tap-min); }
  }
</style>
