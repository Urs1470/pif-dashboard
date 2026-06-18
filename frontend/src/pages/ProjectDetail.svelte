<script>
  import { onMount } from 'svelte'
  import { slide } from 'svelte/transition'
  import { ArrowLeft, Clock, Play, Square, Plus, CheckCircle2, Wrench, BookOpen, ListTodo, Settings2, Paperclip, Pencil, Trash2, FileDown, FileText, StickyNote, ChevronDown, ChevronRight, AlertCircle, Upload, Copy } from '@lucide/svelte'
  import {
    loadProjectDetail, loadProjectTasks, loadProjectJournal, loadProjectEquipment,
    deleteProject, updateProject,
    createJournalEntry, deleteJournalEntry, deleteEquipment, loadProjectTimerSessions,
  } from '../stores/projects.svelte.js'
  import { apiJson } from '../lib/api.js'
  import { updateTask, createTask, deleteTask, loadSubtasks, createSubtask, updateSubtask, deleteSubtask, loadTaskAttachments, uploadTaskAttachment, deleteTaskAttachment } from '../stores/tasks.svelte.js'
  import { timer, startProjectTimer, stopProjectTimer, stopProjectTimerWithNote, startTaskTimer, stopTaskTimer, startSubtaskTimer, stopSubtaskTimer, addManualTime, deleteTimerSession, loadActiveTimer, loadTaskTimer, loadSubtaskTimer } from '../stores/timer.svelte.js'
  import { PROJECT_STATUS_LABELS, TASK_STATUS_LABELS, STATUS_COLORS, formatDate, formatDuration, priorityColor, priorityLabel } from '../lib/formatters.js'
  import { exportMarkdown } from '../lib/exportMd.js'
  import RichText from '../components/ui/RichText.svelte'
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
  import RichTextEditor from '../components/ui/RichTextEditor.svelte'
  import AttachmentPreview from '../components/ui/AttachmentPreview.svelte'

  let { params } = $props()
  let project = $state(null)
  let tasks = $state([])
  let journal = $state([])
  let equipment = $state([])
  let taskDeleteId = $state(null)
  let showTaskDelete = $state(false)
  let timerSessions = $state({ sessions: [], total_secunde: 0 })
  let loading = $state(true)
  let error = $state(null)
  let activeTab = $state('tasks')

  let newTaskTitle = $state('')
  let creatingTask = $state(false)
  let editTaskId = $state(null)
  let editTaskTitle = $state('')
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
  let journalDeleteSessionId = $state(null)
  let showJournalDelete = $state(false)

  let showEquipModal = $state(false)
  let editingEquipment = $state(null)
  let equipDeleteId = $state(null)
  let showEquipDelete = $state(false)

  // Subtask state
  let expandedTask = $state(null)
  let subtasksCache = $state({})
  let newSubtaskTitle = $state('')
  let subtaskLoading = $state(false)

  // Task/subtask session state
  let taskSessionsCache = $state({})
  let subSessionsCache = $state({})
  let expandedSubSess = $state(null)

  // Equipment collapse state
  let expandedEquip = $state(new Set())
  let equipParamSearch = $state({})

  // Done tasks collapse
  let showDoneTasks = $state(false)

  // Field edit modal (observatii, service_before, service_after)
  let showFieldEdit = $state(false)
  let editField = $state(null)
  let editValue = $state('')
  let editLabel = $state('')
  let editSaving = $state(false)


  // Manual time entry modal
  let showManualTime = $state(false)
  let manualKind = $state('project')
  let manualId = $state(null)
  let manualDate = $state('')
  let manualHours = $state(1)
  let manualMinutes = $state(0)
  let manualSaving = $state(false)

  const tabs = [
    { key: 'tasks', label: 'Taskuri', icon: ListTodo },
    { key: 'journal', label: 'Jurnal', icon: BookOpen },
    { key: 'equipment', label: 'Echipamente', icon: Wrench },
    { key: 'attachments', label: 'Atasamente', icon: Paperclip },
    { key: 'info', label: 'Info', icon: Settings2 },
  ]

  async function load() {
    loading = true
    try {
      project = await loadProjectDetail(params.id)
      const [t, j, e, ts] = await Promise.all([
        loadProjectTasks(params.id).catch(() => []),
        loadProjectJournal(params.id).catch(() => []),
        loadProjectEquipment(params.id).catch(() => []),
        loadProjectTimerSessions(params.id).catch(() => ({ sessions: [], total_secunde: 0 })),
      ])
      tasks = Array.isArray(t) ? t : t.tasks || []
      journal = Array.isArray(j) ? j : j.entries || []
      equipment = Array.isArray(e) ? e : e.echipamente || []
      timerSessions = ts
    } catch (err) {
      error = err.message
    } finally { loading = false }
  }

  async function reloadJournal() {
    const j = await loadProjectJournal(params.id).catch(() => [])
    journal = Array.isArray(j) ? j : j.entries || []
  }

  async function reloadEquipment() {
    const e = await loadProjectEquipment(params.id).catch(() => [])
    equipment = Array.isArray(e) ? e : e.echipamente || []
  }

  async function reloadTasks() {
    const t = await loadProjectTasks(params.id).catch(() => [])
    tasks = Array.isArray(t) ? t : t.tasks || []
  }

  async function toggleTaskStatus(task) {
    const next = task.status === 'done' ? 'to_do' : 'done'
    tasks = tasks.map(t => t.id === task.id ? { ...t, status: next } : t)
    await updateTask(task.id, { status: next })
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
    const wasActive = timer.active?.kind === 'task' && timer.active?.task_id === taskId
    if (wasActive) await stopTaskTimer(taskId)
    else await startTaskTimer(taskId)
    await loadActiveTimer()
    if (wasActive) {
      await reloadTasks()
      taskSessionsCache = { ...taskSessionsCache, [taskId]: await loadTaskTimer(taskId).catch(() => taskSessionsCache[taskId] || { sessions: [], total_secunde: 0 }) }
    }
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

  function startRename(t) {
    editTaskId = t.id
    editTaskTitle = t.titlu || ''
  }

  function focusSelect(node) {
    node.focus()
    node.select()
  }

  async function saveRename(t) {
    if (editTaskId !== t.id) return
    const newTitle = editTaskTitle.trim()
    editTaskId = null
    if (!newTitle || newTitle === t.titlu) return
    try {
      await updateTask(t.id, { titlu: newTitle })
      await reloadTasks()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  async function loadAtt(taskId, force = false) {
    if (force || !attCache[taskId]) {
      attCache = { ...attCache, [taskId]: await loadTaskAttachments(taskId).catch(() => attCache[taskId] || []) }
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
      for (const f of files) await uploadTaskAttachment(taskId, f)
      toast(files.length === 1 ? 'Fisier atasat' : `${files.length} fisiere atasate`, 'success')
      await Promise.all([loadAtt(taskId, true), reloadTasks()])
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
      if (taskId) await Promise.all([loadAtt(taskId, true), reloadTasks()])
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
    if (journalDeleteSessionId) {
      await deleteTimerSession(journalDeleteSessionId).catch(() => {})
      timerSessions = await loadProjectTimerSessions(params.id).catch(() => timerSessions)
    }
    journalDeleteId = null
    journalDeleteSessionId = null
    await reloadJournal()
    toast('Intrare stearsa', 'success')
  }

  async function doDeleteTask() {
    if (!taskDeleteId) return
    await deleteTask(taskDeleteId)
    taskDeleteId = null
    await reloadTasks()
    toast('Task sters', 'success')
  }

  const PRIO_CYCLE = ['normal', 'minor', 'urgent']
  async function cycleTaskPriority(t) {
    const cur = (t.prioritate || 'normal').toLowerCase()
    const next = PRIO_CYCLE[(PRIO_CYCLE.indexOf(cur) + 1) % PRIO_CYCLE.length]
    await updateTask(t.id, { prioritate: next })
    await reloadTasks()
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

  // Equipment import state
  let importFileInput = $state(null)
  let importAbbInput = $state(null)
  let importType = $state('')
  let importPreview = $state(null)
  let showImportModal = $state(false)
  let importBusy = $state(false)
  let importSelected = $state(new Set())

  // Equipment copy state
  let showCopyModal = $state(false)
  let copyProjects = $state([])
  let copyProjectId = $state('')
  let copyEquipment = $state([])
  let copySelected = $state(new Set())
  let copyBusy = $state(false)

  function triggerImportStarter() {
    importType = 'starter'
    importFileInput?.click()
  }

  function triggerImportAbb() {
    importType = 'abb'
    importAbbInput?.click()
  }

  async function onImportFile(e) {
    const files = e.target.files
    if (!files?.length) return
    importBusy = true
    try {
      const fd = new FormData()
      if (importType === 'abb') {
        for (const f of files) fd.append('files', f)
        const res = await apiJson('/api/import-abb-multi/preview', { method: 'POST', body: fd })
        importPreview = res
      } else {
        fd.append('file', files[0])
        const res = await apiJson('/api/import-archive/preview', { method: 'POST', body: fd })
        importPreview = res
      }
      importSelected = new Set((importPreview.drives || []).map((_, i) => i))
      showImportModal = true
    } catch (err) { toast(`Eroare import: ${err.message}`, 'error') }
    finally { importBusy = false; e.target.value = '' }
  }

  async function commitImport() {
    if (!importPreview?.drives || importSelected.size === 0) return
    importBusy = true
    try {
      const drives = importPreview.drives.filter((_, i) => importSelected.has(i))
      await apiJson(`/api/proiecte/${params.id}/echipamente/import-archive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ drives }),
      })
      toast(`${drives.length} echipamente importate`, 'success')
      showImportModal = false
      importPreview = null
      await reloadEquipment()
    } catch (err) { toast(`Eroare: ${err.message}`, 'error') }
    finally { importBusy = false }
  }

  function toggleImportDrive(i) {
    const next = new Set(importSelected)
    if (next.has(i)) next.delete(i); else next.add(i)
    importSelected = next
  }

  async function openCopyModal() {
    showCopyModal = true
    copyBusy = true
    try {
      const data = await apiJson('/api/proiecte')
      const all = Array.isArray(data) ? data : data.projects || []
      copyProjects = all.filter(p => p.id !== params.id)
    } catch (err) { toast(`Eroare: ${err.message}`, 'error') }
    finally { copyBusy = false }
  }

  async function loadCopyEquipment() {
    if (!copyProjectId) { copyEquipment = []; return }
    copyBusy = true
    try {
      const e = await apiJson(`/api/proiecte/${copyProjectId}/echipamente`)
      copyEquipment = Array.isArray(e) ? e : e.echipamente || []
      copySelected = new Set(copyEquipment.map((_, i) => i))
    } catch (_) { copyEquipment = [] }
    finally { copyBusy = false }
  }

  async function commitCopy() {
    if (copySelected.size === 0) return
    copyBusy = true
    try {
      const drives = copyEquipment.filter((_, i) => copySelected.has(i)).map(e => ({
        nume: e.nume, producator: e.producator, model: e.model,
        serial_number: e.serial_number, firmware: e.firmware,
        params: typeof e.params_json === 'string' ? JSON.parse(e.params_json || '{}') : (e.params_json || {}),
        descrieri: typeof e.descrieri_json === 'string' ? JSON.parse(e.descrieri_json || '{}') : (e.descrieri_json || {}),
      }))
      await apiJson(`/api/proiecte/${params.id}/echipamente/import-archive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ drives }),
      })
      toast(`${drives.length} echipamente copiate`, 'success')
      showCopyModal = false
      copyEquipment = []
      copyProjectId = ''
      await reloadEquipment()
    } catch (err) { toast(`Eroare: ${err.message}`, 'error') }
    finally { copyBusy = false }
  }

  function parseEquipParams(e) {
    try {
      return Object.entries(typeof e.params_json === 'string' ? JSON.parse(e.params_json || '{}') : (e.params_json || {}))
    } catch (_) { return [] }
  }

  function toggleEquipExpand(id) {
    const next = new Set(expandedEquip)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    expandedEquip = next
  }

  // Subtask functions
  async function toggleTaskExpand(taskId) {
    if (expandedTask === taskId) {
      expandedTask = null
      return
    }
    expandedTask = taskId
    expandedSubSess = null
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
    if (!taskSessionsCache[taskId]) {
      taskSessionsCache = { ...taskSessionsCache, [taskId]: await loadTaskTimer(taskId).catch(() => ({ sessions: [], total_secunde: 0 })) }
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

  async function removeSubtask(subId, taskId) {
    subtasksCache = { ...subtasksCache, [taskId]: subtasksCache[taskId].filter(s => s.id !== subId) }
    try {
      await deleteSubtask(subId)
      await reloadTasks()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
      const subs = await loadSubtasks(taskId)
      subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
    }
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

  function openManualTime(kind, id, date) {
    manualKind = kind
    manualId = id
    manualDate = date || new Date().toISOString().slice(0, 10)
    manualHours = 1
    manualMinutes = 0
    showManualTime = true
  }

  async function saveManualTime() {
    const sec = manualHours * 3600 + manualMinutes * 60
    if (sec <= 0) { toast('Durata trebuie sa fie > 0', 'error'); return }
    manualSaving = true
    try {
      await addManualTime(manualKind, manualId, sec, manualDate || undefined)
      showManualTime = false
      toast('Timp adaugat', 'success')
      timerSessions = await loadProjectTimerSessions(params.id).catch(() => timerSessions)
      await reloadTasks()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { manualSaving = false }
  }

  async function handleDeleteSession(sessionId) {
    try {
      await deleteTimerSession(sessionId)
      timerSessions = await loadProjectTimerSessions(params.id).catch(() => timerSessions)
      toast('Sesiune stearsa', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  async function handleDeleteTaskSession(taskId, sessionId) {
    try {
      await deleteTimerSession(sessionId)
      taskSessionsCache = { ...taskSessionsCache, [taskId]: await loadTaskTimer(taskId).catch(() => ({ sessions: [], total_secunde: 0 })) }
      await reloadTasks()
      toast('Sesiune stearsa', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function toggleSubSessions(subId) {
    if (expandedSubSess === subId) { expandedSubSess = null; return }
    expandedSubSess = subId
    if (!subSessionsCache[subId]) {
      subSessionsCache = { ...subSessionsCache, [subId]: await loadSubtaskTimer(subId).catch(() => ({ sessions: [], total_secunde: 0 })) }
    }
  }

  async function handleDeleteSubSession(subId, sessionId) {
    try {
      await deleteTimerSession(sessionId)
      subSessionsCache = { ...subSessionsCache, [subId]: await loadSubtaskTimer(subId).catch(() => ({ sessions: [], total_secunde: 0 })) }
      const taskId = expandedTask
      subtasksCache = { ...subtasksCache, [taskId]: await loadSubtasks(taskId) }
      await reloadTasks()
      toast('Sesiune stearsa', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function handleSubtaskTimer(sub) {
    const wasActive = timer.active?.kind === 'subtask' && timer.active?.subtask_id === sub.id
    if (wasActive) {
      await stopSubtaskTimer(sub.id)
    } else {
      await startSubtaskTimer(sub.id)
    }
    await loadActiveTimer()
    if (wasActive) {
      const taskId = sub.task_id || expandedTask
      subSessionsCache = { ...subSessionsCache, [sub.id]: await loadSubtaskTimer(sub.id).catch(() => subSessionsCache[sub.id] || { sessions: [], total_secunde: 0 }) }
      if (taskId) {
        const subs = await loadSubtasks(taskId).catch(() => null)
        if (subs) subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
      }
      await reloadTimerSessions()
    }
  }

  async function reloadTimerSessions() {
    timerSessions = await loadProjectTimerSessions(params.id).catch(() => timerSessions)
  }

  onMount(() => { load(); loadActiveTimer() })

  const tasksDone = $derived(tasks.filter(t => t.status === 'done' || t.status === 'finalizat').length)
  const activeTasks = $derived(tasks.filter(t => t.status !== 'done' && t.status !== 'finalizat'))
  const doneTasks = $derived(tasks.filter(t => t.status === 'done' || t.status === 'finalizat'))
  const projectTimerActive = $derived(timer.active?.kind === 'project' && timer.active?.project_id === params.id)

  const mergedTimeline = $derived.by(() => {
    const sessions = timerSessions.sessions || []
    const matched = new Set()
    const items = []
    const toDay = iso => (iso || '').slice(0, 10)
    for (const j of journal) {
      const jTime = new Date(j.data || j.created_at || 0).getTime()
      const jDay = toDay(j.data || j.created_at)
      const found = sessions.find(s => {
        if (matched.has(s.id)) return false
        const stopIso = s.stop_time || s.end_time
        if (!stopIso) return false
        const diff = Math.abs(jTime - new Date(stopIso).getTime())
        if (diff < 2 * 60 * 1000) return true
        return toDay(stopIso) === jDay
      })
      if (found) {
        matched.add(found.id)
        items.push({ kind: 'journal', ...j, _duration: found.durata_secunde, _sessionId: found.id })
      } else {
        items.push({ kind: 'journal', ...j })
      }
    }
    for (const s of sessions) {
      if (!matched.has(s.id)) {
        items.push({ kind: 'timer', id: s.id, data: s.stop_time || s.start_time, durata: s.durata_secunde, sessionId: s.id })
      }
    }
    items.sort((a, b) => new Date(b.data || 0).getTime() - new Date(a.data || 0).getTime())
    return items
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
          <Button variant="secondary" size="sm" onclick={() => openManualTime('project', params.id)}><Clock size={14} /> Manual</Button>
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

      <div class="field-section">
        <div class="field-header">
          <FileText size={14} />
          <span class="field-label">Observatii Tehnice</span>
          <button class="field-edit" onclick={() => openFieldEdit('observatii', 'Observatii Tehnice')} title="Editeaza"><Pencil size={13} /></button>
        </div>
        {#if project.observatii}
          <div class="field-body">
            <RichText value={project.observatii} collapsible maxHeight={240} />
          </div>
        {:else}
          <button class="field-empty" onclick={() => openFieldEdit('observatii', 'Observatii Tehnice')}>Click pentru a adauga...</button>
        {/if}
      </div>

      {#if project.tip === 'Service'}
        <div class="field-section">
          <div class="field-header">
            <AlertCircle size={14} />
            <span class="field-label">Constatari inainte de interventie</span>
            <button class="field-edit" onclick={() => openFieldEdit('service_before', 'Constatari inainte de interventie')} title="Editeaza"><Pencil size={13} /></button>
          </div>
          {#if project.service_before}
            <div class="field-body">
              <RichText value={project.service_before} collapsible maxHeight={240} />
            </div>
          {:else}
            <button class="field-empty" onclick={() => openFieldEdit('service_before', 'Constatari inainte de interventie')}>Click pentru a adauga...</button>
          {/if}
        </div>

        <div class="field-section">
          <div class="field-header">
            <CheckCircle2 size={14} />
            <span class="field-label">Actiuni si rezultat</span>
            <button class="field-edit" onclick={() => openFieldEdit('service_after', 'Actiuni si rezultat')} title="Editeaza"><Pencil size={13} /></button>
          </div>
          {#if project.service_after}
            <div class="field-body">
              <RichText value={project.service_after} collapsible maxHeight={240} />
            </div>
          {:else}
            <button class="field-empty" onclick={() => openFieldEdit('service_after', 'Actiuni si rezultat')}>Click pentru a adauga...</button>
          {/if}
        </div>
      {/if}
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
        </div>
        <form class="quick-add" onsubmit={(e) => { e.preventDefault(); handleCreateTask() }}>
          <input type="text" placeholder="Task rapid... Enter pentru a adauga" bind:value={newTaskTitle} disabled={creatingTask} />
          <button type="submit" class="quick-add-btn" disabled={!newTaskTitle.trim() || creatingTask} title="Adauga task"><Plus size={16} /></button>
        </form>
        {#if tasks.length === 0}<p class="empty">Niciun task.</p>
        {:else}
          <div class="task-list">
            {#each activeTasks as t (t.id)}
              <div class="trow-wrap">
                <div class="trow" style="border-left-color: {t.prioritate ? priorityColor(t.prioritate) : 'var(--border)'}">
                  <button class="check" onclick={() => toggleTaskStatus(t)}>
                    <div class="check-empty"></div>
                  </button>
                  {#if editTaskId === t.id}
                    <input class="trename" bind:value={editTaskTitle} use:focusSelect
                      onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveRename(t) } else if (e.key === 'Escape') { editTaskId = null } }}
                      onblur={() => saveRename(t)} />
                  {:else}
                    <button class="tmain" onclick={() => toggleTaskExpand(t.id)}>
                      <div class="ttitle-row">
                        <span class="ttitle">{t.titlu}</span>
                        {#if t.descriere}<span class="tdesc-icon" title="Are notiță"><StickyNote size={12} /></span>{/if}
                      </div>
                      <div class="tinfo">
                        {#if t.timp_secunde}<span class="tmono">{formatDuration(t.timp_secunde)}</span>{/if}
                        {#if t.subtask_total}
                          <span class="tsub-chip">{t.subtask_done || 0}/{t.subtask_total}</span>
                        {/if}
                        {#if t.atasamente_count}<span class="att-ind"><Paperclip size={10} /> {t.atasamente_count}</span>{/if}
                        {#if t.deadline}
                          <span class="tdeadline" class:overdue={isOverdue(t.deadline)} class:today={isToday(t.deadline)} class:soon={isSoon(t.deadline)}>{formatDate(t.deadline)}</span>
                        {/if}
                      </div>
                    </button>
                  {/if}
                  <div class="task-actions">
                    <button class="prio-badge" style="color: {priorityColor(t.prioritate || 'normal')}; border-color: {priorityColor(t.prioritate || 'normal')}" onclick={() => cycleTaskPriority(t)} title="Click pentru a schimba prioritatea">{priorityLabel(t.prioritate || 'normal')}</button>
                    <button class="task-edit" onclick={() => startRename(t)} title="Editeaza numele"><Pencil size={13} /></button>
                    <button class="timer-btn" class:active={timer.active?.kind === 'task' && timer.active?.task_id === t.id} onclick={() => handleTaskTimer(t.id)}><Clock size={14} /></button>
                    <button class="task-del" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Sterge task"><Trash2 size={13} /></button>
                  </div>
                </div>
                {#if expandedTask === t.id}
                  <div class="subtask-body" transition:slide={{ duration: 150 }}>
                    {#if t.descriere}
                      <div class="note-block">
                        <RichText value={t.descriere} class="note-content" collapsible maxHeight={200} />
                        <button class="note-edit-btn" title="Editeaza notite" onclick={() => openNoteModal(t)}><Pencil size={12} /> Editeaza</button>
                      </div>
                    {:else}
                      <button class="note-add" onclick={() => openNoteModal(t)}><StickyNote size={12} /> Adauga notite...</button>
                    {/if}
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
                    {#if subtaskLoading && !subtasksCache[t.id]}
                      <div class="sub-loading">Se incarca...</div>
                    {:else}
                      {#each (subtasksCache[t.id] || []) as sub (sub.id)}
                        <div class="sub-row" class:sub-done={sub.done}>
                          <input type="checkbox" class="cbx" checked={!!sub.done} onchange={() => toggleSubtaskDone(sub)} />
                          <span class="sub-title">{sub.titlu}</span>
                          {#if sub.timp_secunde}<button class="sub-time" onclick={() => toggleSubSessions(sub.id)} title="Vezi sesiuni">{formatDuration(sub.timp_secunde)}</button>{/if}
                          <button class="sub-timer" class:active={timer.active?.kind === 'subtask' && timer.active?.subtask_id === sub.id} onclick={() => handleSubtaskTimer(sub)} title="Timer subtask"><Clock size={12} /></button>
                          <button class="sub-del" onclick={() => removeSubtask(sub.id, t.id)}><Trash2 size={12} /></button>
                        </div>
                        {#if expandedSubSess === sub.id && subSessionsCache[sub.id]?.sessions?.length > 0}
                          <div class="sub-sess" transition:slide={{ duration: 150 }}>
                            {#each subSessionsCache[sub.id].sessions as s (s.id)}
                              <div class="sess mini">
                                <span>{s.start_time ? formatDate(s.start_time) : '—'}</span>
                                <span class="sess-dur">{formatDuration(s.durata_secunde)}</span>
                                <button class="sess-del" title="Sterge" onclick={() => handleDeleteSubSession(sub.id, s.id)}><Trash2 size={10} /></button>
                              </div>
                            {/each}
                          </div>
                        {/if}
                      {/each}
                      <form class="sub-add" onsubmit={(e) => { e.preventDefault(); addSubtask(t.id) }}>
                        <input type="text" placeholder="Adauga subtask..." bind:value={newSubtaskTitle} />
                        <button type="submit" class="sub-add-btn" disabled={!newSubtaskTitle.trim()}><Plus size={14} /></button>
                      </form>
                    {/if}
                    {#if taskSessionsCache[t.id]?.sessions?.length > 0}
                      <div class="tsess-section">
                        <span class="tsess-label">Sesiuni ({taskSessionsCache[t.id].sessions.length}) — {formatDuration(taskSessionsCache[t.id].total_secunde)}</span>
                        {#each taskSessionsCache[t.id].sessions as s (s.id)}
                          <div class="sess">
                            <span>{s.start_time ? formatDate(s.start_time) : '—'}</span>
                            <span class="sess-dur">{formatDuration(s.durata_secunde)}</span>
                            <button class="sess-del" title="Sterge" onclick={() => handleDeleteTaskSession(t.id, s.id)}><Trash2 size={11} /></button>
                          </div>
                        {/each}
                      </div>
                    {/if}
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
                {#each doneTasks as t (t.id)}
                  <div class="trow done" style="border-left-color: {t.prioritate ? priorityColor(t.prioritate) : 'var(--border)'}">
                    <button class="check" onclick={() => toggleTaskStatus(t)}>
                      <CheckCircle2 size={16} />
                    </button>
                    <div class="tmain">
                      <div class="ttitle">{t.titlu}</div>
                      <div class="tinfo">
                        {#if t.timp_secunde}<span class="tmono">{formatDuration(t.timp_secunde)}</span>{/if}
                      </div>
                    </div>
                  </div>
                {/each}
              {/if}
            {/if}
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
        {#if mergedTimeline.length === 0}<p class="empty">Nicio intrare.</p>
        {:else}
          <div class="jlist">{#each mergedTimeline as item (item.id)}
            {#if item.kind === 'journal'}
              <div class="jentry">
                <div class="jentry-top">
                  <div class="jentry-meta">
                    <div class="jdate">{formatDate(item.data || item.created_at)}</div>
                    {#if item._duration}<span class="jdur"><Clock size={12} /> {formatDuration(item._duration)}</span>{/if}
                  </div>
                  <div class="jentry-actions">
                    <button class="jtime-btn" title="Adauga timp manual" onclick={() => openManualTime('project', params.id, (item.data || item.created_at || '').slice(0, 10))}><Clock size={13} /></button>
                    <button class="jdel" title="Sterge" onclick={() => { journalDeleteId = item.id; journalDeleteSessionId = item._sessionId || null; showJournalDelete = true }}><Trash2 size={13} /></button>
                  </div>
                </div>
                <div class="jtext">{item.continut || '—'}</div>
              </div>
            {:else}
              <div class="jentry jentry-timer">
                <div class="jentry-top">
                  <div class="jentry-meta">
                    <div class="jdate">{formatDate(item.data)}</div>
                    <span class="jdur"><Clock size={12} /> {formatDuration(item.durata)}</span>
                  </div>
                  <button class="jdel" title="Sterge sesiunea" onclick={() => handleDeleteSession(item.sessionId)}><Trash2 size={13} /></button>
                </div>
                <div class="jtext jtext-timer">Timer fara nota</div>
              </div>
            {/if}
          {/each}</div>
        {/if}

      {:else if activeTab === 'equipment'}
        <div class="tab-header">
          <span class="tab-sub">{equipment.length} echipamente</span>
          <div class="equip-btns">
            <Button size="sm" variant="ghost" onclick={triggerImportStarter} disabled={importBusy}><Upload size={14} /> Import STARTER</Button>
            <Button size="sm" variant="ghost" onclick={triggerImportAbb} disabled={importBusy}><Upload size={14} /> Import ABB</Button>
            <Button size="sm" variant="ghost" onclick={openCopyModal}><Copy size={14} /> Copiaza</Button>
            <Button size="sm" variant="secondary" onclick={newEquip}><Plus size={14} /> Echipament</Button>
          </div>
        </div>
        <input type="file" accept=".zip,.s7p" hidden bind:this={importFileInput} onchange={onImportFile} />
        <input type="file" accept=".dcparamsbak" multiple hidden bind:this={importAbbInput} onchange={onImportFile} />
        {#if equipment.length === 0}<p class="empty">Niciun echipament.</p>
        {:else}
          <div class="elist">{#each equipment as e (e.id)}
            {@const eparams = parseEquipParams(e)}
            {@const isExpanded = expandedEquip.has(e.id)}
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
                {@const pq = (equipParamSearch[e.id] || '').toLowerCase()}
                {@const filteredParams = pq ? eparams.filter(([k, v]) => k.toLowerCase().includes(pq) || v.toLowerCase().includes(pq)) : eparams}
                <button class="eparam-toggle" onclick={() => toggleEquipExpand(e.id)}>
                  {#if isExpanded}<ChevronDown size={12} /> Ascunde parametri{:else}<ChevronRight size={12} /> {eparams.length} parametri{/if}
                </button>
                {#if isExpanded}
                  <div class="eparams-wrap" transition:slide={{ duration: 150 }}>
                    {#if eparams.length > 5}
                      <input type="text" class="eparam-search" placeholder="Filtreaza parametri..." value={equipParamSearch[e.id] || ''} oninput={(ev) => { equipParamSearch = { ...equipParamSearch, [e.id]: ev.target.value } }} />
                    {/if}
                    <div class="eparams">
                      {#each filteredParams as [k, v]}
                        <div class="eparam">
                          <span class="eparam-key">{k}</span>
                          <span class="eparam-val">{v}</span>
                        </div>
                      {/each}
                      {#if pq && filteredParams.length === 0}
                        <div class="eparam-empty">Niciun parametru gasit</div>
                      {/if}
                    </div>
                  </div>
                {/if}
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
          {#if timerSessions.sessions?.length > 0}
            <div class="ifull">
              <div class="sess-header">
                <span class="ilabel">Sesiuni timer ({timerSessions.sessions.length}) — Total: {formatDuration(timerSessions.total_secunde)}</span>
              </div>
              <div class="sess-list">
                {#each timerSessions.sessions as s (s.id)}
                  <div class="sess">
                    <span>{s.start_time ? formatDate(s.start_time) : '—'}</span>
                    <span class="sess-dur">{formatDuration(s.durata_secunde)}</span>
                    <button class="sess-del" title="Sterge sesiunea" onclick={() => handleDeleteSession(s.id)}><Trash2 size={12} /></button>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

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

<Modal bind:open={showImportModal} title="Import Echipamente" size="lg">
  {#if importPreview}
    <div class="import-info">
      <span>{importPreview.drives?.length || 0} drive-uri detectate</span>
      {#if importPreview.skipped_default}<span class="dim">({importPreview.skipped_default} parametri la valoare default omisi)</span>{/if}
    </div>
    <div class="import-drives">
      {#each (importPreview.drives || []) as drv, i}
        <div class="import-drive" class:import-selected={importSelected.has(i)}>
          <label class="import-check">
            <input type="checkbox" checked={importSelected.has(i)} onchange={() => toggleImportDrive(i)} />
            <div class="import-drive-info">
              <strong>{drv.nume || `Drive ${i + 1}`}</strong>
              <span class="dim">{drv.producator} {drv.model}{drv.firmware ? ` (FW ${drv.firmware})` : ''}</span>
              <span class="dim">{Object.keys(drv.params || {}).length} parametri modificati</span>
            </div>
          </label>
        </div>
      {/each}
    </div>
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => { showImportModal = false; importPreview = null }}>Anuleaza</Button>
      <Button loading={importBusy} disabled={importSelected.size === 0} onclick={commitImport}>
        <Upload size={14} /> Importa {importSelected.size} echipamente
      </Button>
    </div>
  {/if}
</Modal>

<Modal bind:open={showCopyModal} title="Copiaza echipamente din alt proiect" size="lg">
  <div class="copy-form">
    <label class="mf-field">
      <span class="mf-label">Proiect sursa</span>
      <select class="mf-input" bind:value={copyProjectId} onchange={loadCopyEquipment}>
        <option value="">Selecteaza proiect...</option>
        {#each copyProjects as p}
          <option value={p.id}>{p.nume}{p.client ? ` — ${p.client}` : ''}</option>
        {/each}
      </select>
    </label>
    {#if copyEquipment.length > 0}
      <div class="import-drives">
        {#each copyEquipment as eq, i}
          <div class="import-drive" class:import-selected={copySelected.has(i)}>
            <label class="import-check">
              <input type="checkbox" checked={copySelected.has(i)} onchange={() => { const n = new Set(copySelected); if (n.has(i)) n.delete(i); else n.add(i); copySelected = n }} />
              <div class="import-drive-info">
                <strong>{eq.nume || '—'}</strong>
                <span class="dim">{eq.producator} {eq.model || ''}</span>
              </div>
            </label>
          </div>
        {/each}
      </div>
    {:else if copyProjectId}
      <p class="empty">Niciun echipament in proiectul selectat.</p>
    {/if}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showCopyModal = false}>Anuleaza</Button>
      <Button loading={copyBusy} disabled={copySelected.size === 0} onclick={commitCopy}>
        <Copy size={14} /> Copiaza {copySelected.size} echipamente
      </Button>
    </div>
  </div>
</Modal>
<ConfirmDialog bind:open={showDeleteConfirm} title="Sterge proiect" message={`Stergi proiectul "${project?.nume}"? Toate datele (taskuri, jurnal, atasamente, echipamente) vor fi sterse definitiv.`} confirmLabel="Sterge definitiv" onconfirm={handleDeleteProject} />
<ConfirmDialog bind:open={showJournalDelete} title="Sterge intrare" message="Stergi aceasta intrare din jurnal?" confirmLabel="Sterge" onconfirm={doDeleteJournal} />
<ConfirmDialog bind:open={showEquipDelete} title="Sterge echipament" message="Stergi acest echipament?" confirmLabel="Sterge" onconfirm={doDeleteEquip} />
<ConfirmDialog bind:open={showTaskDelete} title="Sterge task" message="Stergi acest task? Toate subtaskurile si sesiunile timer asociate vor fi sterse." confirmLabel="Sterge" onconfirm={doDeleteTask} />
<ConfirmDialog bind:open={showAttDelete} title="Sterge atasament" message="Stergi acest fisier atasat?" confirmLabel="Sterge" onconfirm={doDeleteAtt} />
<AttachmentPreview bind:open={attPreviewOpen} attachment={attPreviewAtt} ondelete={attPreviewDelete} />
<input type="file" multiple hidden bind:this={attInput} onchange={onAttFiles} />

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

<Modal bind:open={showFieldEdit} title={editLabel} size="wide">
  <div class="field-edit-modal">
    {#if showFieldEdit}
      <RichTextEditor bind:value={editValue} placeholder="Scrie aici..." />
    {/if}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showFieldEdit = false}>Anuleaza</Button>
      <Button loading={editSaving} onclick={saveFieldEdit}>Salveaza</Button>
    </div>
  </div>
</Modal>

<Modal bind:open={showNoteModal} title={noteTask ? `Notite — ${noteTask.titlu}` : 'Notite task'} size="wide">
  <div class="field-edit-modal">
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

  /* Field sections under header (observatii, service) */
  .field-section { margin-top: var(--space-sm); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; }
  .field-header { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-md); font-size: var(--font-small); color: var(--text-secondary); }
  .field-label { flex: 1; font-weight: 600; }
  .field-edit { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast); }
  .field-edit:hover { color: var(--accent); background: var(--accent-subtle); }
  .field-body { font-size: var(--font-small); color: var(--text); line-height: 1.6; padding: 0 var(--space-md) var(--space-sm); overflow-x: auto; --rt-fade: var(--bg-surface); }
  .field-empty { padding: var(--space-xs) var(--space-md) var(--space-sm); font-size: var(--font-small); color: var(--text-faint); font-style: italic; cursor: pointer; width: 100%; text-align: left; }
  .field-empty:hover { color: var(--accent); }
  .field-edit-modal { display: flex; flex-direction: column; gap: var(--space-sm); }

  .tabs { display: flex; border-bottom: 1px solid var(--border); margin-bottom: var(--space-md); overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
  .tabs::-webkit-scrollbar { display: none; }
  .tab { display: flex; align-items: center; gap: 4px; padding: var(--space-sm) var(--space-md); font-size: var(--font-small); font-weight: 500; color: var(--text-secondary); border-bottom: 2px solid transparent; cursor: pointer; white-space: nowrap; min-height: 44px; -webkit-tap-highlight-color: transparent; }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab-count { font-size: 10px; padding: 0 5px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }

  .tab-content { min-height: 200px; }
  .tab-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-sm); }
  .tab-sub { font-size: var(--font-tiny); color: var(--text-dim); }
  .quick-add { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); }
  .quick-add input { flex: 1; min-height: 40px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); }
  .quick-add input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); outline: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .empty { color: var(--text-dim); font-size: var(--font-small); padding: var(--space-lg) 0; text-align: center; }
  .error-text { color: var(--danger); }

  /* Task list */
  .task-list { display: flex; flex-direction: column; }
  .trow-wrap { display: flex; flex-direction: column; }
  .trow { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-xs) var(--space-sm); border-left: 2px solid var(--border); border-radius: var(--radius-xs); margin-bottom: 2px; transition: background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); }
  .trow:hover { background: var(--bg-surface); transform: translateX(2px); }
  .task-actions { display: flex; align-items: center; gap: var(--space-xs); flex-shrink: 0; }
  .trow.done { opacity: 0.5; }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; }
  .check:hover { color: var(--accent); }
  .trow.done .check { color: var(--success); }
  .check-empty { width: 16px; height: 16px; border: 2px solid var(--border); border-radius: 50%; }
  .tmain { flex: 1; min-width: 0; cursor: pointer; text-align: left; }
  .trename { flex: 1; min-width: 0; font-size: var(--font-small); font-weight: 500; padding: 5px 8px; background: var(--bg-elevated); border: 1px solid var(--accent); border-radius: var(--radius-sm); color: var(--text); outline: none; box-shadow: 0 0 0 3px var(--accent-subtle); }
  .task-edit { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: all var(--dur-fast); }
  .trow:hover .task-edit { opacity: 1; }
  .task-edit:hover { color: var(--accent); background: var(--accent-subtle); }
  .ttitle-row { display: flex; align-items: center; gap: var(--space-xs); }
  .ttitle { font-size: var(--font-small); color: var(--text); font-weight: 500; }
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  :global(.tdesc-icon) { display: inline-flex; align-items: center; color: var(--text-faint); flex-shrink: 0; }
  .tinfo { display: flex; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; align-items: center; }
  .tmono { font-family: var(--font-mono); }
  .prio-badge { font-size: var(--font-tiny); font-weight: 600; padding: 1px 8px; border-radius: var(--radius-full); background: transparent; border: 1px solid; cursor: pointer; white-space: nowrap; transition: all var(--dur-fast); display: inline-block; min-width: 62px; text-align: center; }
  .prio-badge:hover { opacity: .8; }
  .tsub-chip { padding: 1px 6px; border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent); font-weight: 600; font-size: 10px; }
  .tdeadline { font-size: 10px; }
  .tdeadline.overdue { color: var(--danger); font-weight: 600; }
  .tdeadline.today { color: var(--accent); font-weight: 600; }
  .tdeadline.soon { color: var(--warning); }
  .timer-btn { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; -webkit-tap-highlight-color: transparent; flex-shrink: 0; }
  .timer-btn:hover { background: var(--bg-hover); color: var(--text); }
  .timer-btn.active { color: var(--accent); background: var(--accent-subtle); }
  .task-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: all var(--dur-fast); }
  .trow:hover .task-del { opacity: 1; }
  .task-del:hover { color: var(--danger); background: var(--danger-subtle); }

  /* Done separator */
  .done-sep { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-xs); font-size: var(--font-tiny); font-weight: 600; color: var(--text-dim); cursor: pointer; margin-top: var(--space-sm); border-top: 1px solid var(--border-subtle); text-transform: uppercase; letter-spacing: 0.05em; }
  .done-sep:hover { color: var(--text-secondary); }

  /* Subtask expanded area */
  .subtask-body { margin-left: 26px; padding: var(--space-sm) var(--space-sm) var(--space-sm) var(--space-md); border-left: 2px solid var(--accent-subtle); margin-bottom: var(--space-sm); }
  .note-add { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-tiny); color: var(--text-faint); cursor: pointer; padding: 4px 6px; margin-bottom: var(--space-xs); border-radius: var(--radius-xs); font-style: italic; transition: all var(--dur-fast) var(--ease); }
  .note-add:hover { color: var(--accent); background: var(--accent-subtle); }
  .note-block { margin-bottom: var(--space-sm); }
  .note-edit-btn { display: inline-flex; align-items: center; gap: 5px; margin-top: 4px; padding: 3px 8px; font-size: var(--font-tiny); color: var(--text-faint); cursor: pointer; border-radius: var(--radius-xs); transition: all var(--dur-fast) var(--ease); }
  .note-edit-btn:hover { color: var(--accent); background: var(--accent-subtle); }
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
  .sub-time { font-size: var(--font-tiny); font-family: var(--font-mono); color: var(--accent); flex-shrink: 0; background: none; border: none; cursor: pointer; padding: 0; }
  .sub-time:hover { text-decoration: underline; }
  .sub-timer { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: all var(--dur-fast); }
  .sub-timer.active { opacity: 1; color: var(--accent); background: var(--accent-subtle); }
  .sub-row:hover .sub-timer { opacity: 1; }
  .sub-timer:hover { color: var(--accent); background: var(--accent-subtle); }
  .sub-del { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: opacity var(--dur-fast); }
  .sub-row:hover .sub-del { opacity: 1; }
  .sub-del:hover { color: var(--danger); background: var(--danger-subtle); }
  .sub-add { display: flex; gap: var(--space-xs); margin-top: var(--space-xs); }
  .sub-add input { flex: 1; padding: 6px 10px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-small); }
  .sub-add-btn { width: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .sub-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
  .sub-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .sub-loading { font-size: var(--font-tiny); color: var(--text-dim); padding: var(--space-xs) 0; }

  /* Journal */
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
  .jentry-actions { display: flex; align-items: center; gap: 2px; }
  .jtime-btn { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); opacity: 0; }
  .jentry:hover .jtime-btn { opacity: 1; }
  .jtime-btn:hover { background: var(--accent-subtle); color: var(--accent); }
  .jentry-meta { display: flex; align-items: center; gap: var(--space-sm); }
  .jdur { display: inline-flex; align-items: center; gap: 3px; font-size: var(--font-tiny); font-family: var(--font-mono); color: var(--accent); background: var(--accent-subtle); padding: 2px 7px; border-radius: var(--radius-xs); }
  .jentry-timer { opacity: 0.7; }
  .jtext-timer { font-style: italic; color: var(--text-dim); }
  .jtext { font-size: var(--font-small); color: var(--text); line-height: 1.55; white-space: pre-wrap; }

  /* Equipment */
  .elist { display: flex; flex-direction: column; gap: var(--space-sm); }
  .ecard-top { display: flex; align-items: center; justify-content: space-between; }
  .ecard-actions { display: flex; gap: 2px; }
  .ename { font-size: var(--font-small); font-weight: 600; color: var(--text); }
  .edetails { display: flex; gap: var(--space-md); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 4px; }
  .eparam-toggle { display: flex; align-items: center; gap: var(--space-xs); font-size: var(--font-tiny); color: var(--accent); cursor: pointer; margin-top: var(--space-sm); padding: 4px 0; font-weight: 500; }
  .eparam-toggle:hover { text-decoration: underline; }
  .eparams-wrap { margin-top: var(--space-xs); }
  .eparam-search { width: 100%; padding: 6px 10px; margin-bottom: var(--space-xs); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-small); }
  .eparam-search:focus { border-color: var(--accent); outline: none; }
  .eparam-empty { padding: var(--space-sm); text-align: center; color: var(--text-dim); font-size: var(--font-tiny); grid-column: 1 / -1; background: var(--bg); }
  .eparams { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1px; border-top: 1px solid var(--border-subtle); padding-top: var(--space-sm); background: var(--border-subtle); border-radius: var(--radius-sm); overflow: hidden; }
  .eparam { display: flex; justify-content: space-between; gap: var(--space-sm); padding: 6px var(--space-sm); background: var(--bg); font-size: var(--font-small); }
  .eparam-key { color: var(--accent); font-family: var(--font-mono); font-size: var(--font-tiny); font-weight: 500; flex-shrink: 0; }
  .eparam-val { color: var(--text); font-weight: 500; text-align: right; }
  .att-btn { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); }
  .att-btn:hover { background: var(--bg-hover); color: var(--text); }
  .att-btn.danger:hover { background: var(--danger-subtle); color: var(--danger); }

  /* Info tab */
  .igrid { display: flex; flex-direction: column; gap: var(--space-sm); }
  .irow { display: flex; justify-content: space-between; font-size: var(--font-small); padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
  .ilabel { color: var(--text-dim); font-weight: 500; }
  .ifull { display: flex; flex-direction: column; gap: 4px; padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
  .sess-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
  .sess-list { display: flex; flex-direction: column; gap: 2px; }
  .sess { display: flex; align-items: center; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-secondary); padding: 2px 0; }
  .sess-dur { font-family: var(--font-mono); color: var(--accent); margin-left: auto; }
  .sess-del { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-xs); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: all var(--dur-fast); }
  .sess:hover .sess-del { opacity: 1; }
  .sess-del:hover { color: var(--danger); background: var(--danger-subtle); }

  .tsess-section { margin-top: var(--space-sm); border-top: 1px solid var(--border); padding-top: var(--space-sm); }
  .tsess-label { font-size: var(--font-tiny); color: var(--text-dim); }
  .sub-sess { margin-left: 1.5rem; margin-bottom: var(--space-xs); }
  .sess.mini { font-size: 0.68rem; }

  .stopnote { display: flex; flex-direction: column; gap: var(--space-md); }
  .ta-field { display: flex; flex-direction: column; gap: 4px; }
  .ta-label { font-size: var(--font-tiny); font-weight: 500; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; }
  .ta-field textarea { padding: 10px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-body); font-family: inherit; resize: vertical; }

  .manual-form { display: flex; flex-direction: column; gap: var(--space-md); }
  .mf-row { display: flex; gap: var(--space-md); }
  .mf-field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
  .mf-label { font-size: var(--font-tiny); font-weight: 500; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em; }
  .mf-input { padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-body); font-family: inherit; min-height: 38px; }

  .modal-actions { display: flex; gap: var(--space-sm); justify-content: flex-end; margin-top: var(--space-lg); }

  /* Equipment import/copy */
  .equip-btns { display: flex; gap: var(--space-xs); flex-wrap: wrap; }
  .import-info { font-size: var(--font-small); color: var(--text-secondary); margin-bottom: var(--space-md); display: flex; gap: var(--space-sm); align-items: center; }
  .import-drives { display: flex; flex-direction: column; gap: var(--space-xs); max-height: 400px; overflow-y: auto; }
  .import-drive { padding: var(--space-sm); border: 1px solid var(--border); border-radius: var(--radius-md); transition: all var(--dur-fast); }
  .import-drive.import-selected { border-color: var(--accent); background: var(--accent-subtle); }
  .import-check { display: flex; align-items: flex-start; gap: var(--space-sm); cursor: pointer; }
  .import-check input[type="checkbox"] { margin-top: 3px; accent-color: var(--accent); }
  .import-drive-info { display: flex; flex-direction: column; gap: 2px; }
  .import-drive-info strong { font-size: var(--font-small); color: var(--text); }
  .copy-form { display: flex; flex-direction: column; gap: var(--space-md); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .pstats { gap: var(--space-md); flex-wrap: wrap; }
    .header-top { flex-direction: column; }
    .edetails { flex-wrap: wrap; gap: var(--space-sm); }
    .trow { padding: var(--space-sm); flex-wrap: wrap; align-items: flex-start; row-gap: 6px; }
    .check { padding-top: 1px; }
    .task-actions { flex-basis: 100%; justify-content: flex-end; }
    .back { min-height: 44px; }
    .subtask-body { margin-left: var(--space-sm); }
    .sub-del, .sub-timer, .task-del, .jtime-btn, .task-edit { opacity: 1; }
    .sess-del, .note-edit-btn { opacity: 1; }
    .quick-add input, .quick-add-btn { min-height: 44px; }
    .quick-add-btn { width: 44px; }
  }
</style>
