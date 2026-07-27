<script>
  import { onMount } from 'svelte'
  import { slide, fade } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { ArrowLeft, Plus, CheckCircle2, ListTodo, Settings2, Paperclip, FileDown, ChevronDown, ChevronRight, AlertCircle, Upload, Copy, Repeat, BookOpen, CalendarRange } from '@lucide/svelte'
  import ProjectGantt from '../components/gantt/ProjectGantt.svelte'
  import ImplPeriods from '../components/projects/ImplPeriods.svelte'
  import { manualUrlForEquip, familieForEquip } from '../lib/manuals.js'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import {
    loadProjectDetail, loadProjectTasks, loadProjectEquipment,
    deleteProject, updateProject, deleteEquipment,
  } from '../stores/projects.svelte.js'
  import { apiJson } from '../lib/api.js'
  import { updateTask, createTask, deleteTask, loadSubtasks, createSubtask, updateSubtask, deleteSubtask, loadTaskAttachments, uploadTaskAttachment, deleteTaskAttachment } from '../stores/tasks.svelte.js'
  import { PROJECT_STATUS_LABELS, TASK_STATUS_LABELS, STATUS_COLORS, formatDate, priorityColor, priorityLabel, isFutureRecurrence } from '../lib/formatters.js'
  import { exportMarkdown } from '../lib/exportMd.js'
  import RichText from '../components/ui/RichText.svelte'
  import { navigate, router } from '../lib/router.svelte.js'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../lib/motion.svelte.js'
  import { focusOnLand, focusKey } from '../lib/focus.js'
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
  import EquipmentFormModal from '../components/projects/EquipmentFormModal.svelte'
  import AttachmentsTab from '../components/projects/AttachmentsTab.svelte'
  import MarkdownView from '../components/notes/MarkdownView.svelte'
  import RichTextEditor from '../components/ui/RichTextEditor.svelte'
  import AttachmentPreview from '../components/ui/AttachmentPreview.svelte'

  let { params } = $props()
  let project = $state(null)
  let tasks = $state([])
  let equipment = $state([])
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
  let taskFormPriority = $state('Normal')
  let taskFormDeadline = $state('')
  let taskFormRecurenta = $state('')
  let taskFormSaving = $state(false)
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

  let showEquipModal = $state(false)
  let editingEquipment = $state(null)
  let equipDeleteId = $state(null)
  let showEquipDelete = $state(false)

  // Subtask state
  let expandedTask = $state(null)
  let subtasksCache = $state({})
  let newSubtaskTitle = $state('')
  let subtaskLoading = $state(false)

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

  // Echipamente + Atasamente scoase din navigatie (2026-07-27, pregatire v24):
  // parametrii de drive stau in wiki (skill drive-backup), backup-urile brute in
  // raw/projects/<slug>/. Codul ramane pana la migratie.
  const tabs = [
    { key: 'tasks', label: 'Taskuri', icon: ListTodo },
    { key: 'gantt', label: 'Gantt', icon: CalendarRange },
    { key: 'wiki', label: 'Wiki', icon: BookOpen },
    { key: 'info', label: 'Info', icon: Settings2 },
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
      const [t, e] = await Promise.all([
        loadProjectTasks(params.id).catch(() => []),
        loadProjectEquipment(params.id).catch(() => []),
      ])
      tasks = Array.isArray(t) ? t : t.tasks || []
      equipment = Array.isArray(e) ? e : e.echipamente || []
    } catch (err) {
      error = err.message
    } finally { loading = false }
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
    const res = await updateTask(task.id, { status: next })
    if (res?.recurring_spawned) {
      toast(`Finalizat ✓ — următoarea apariție: ${formatDate(res.recurring_next)}`, 'success')
      await reloadTasks()
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

  function openTaskEditModal(t) {
    editingTask = t
    taskFormTitle = t.titlu || ''
    taskFormDesc = t.descriere || ''
    taskFormPriority = t.prioritate || 'Normal'
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
        prioritate: taskFormPriority,
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
  async function cycleTaskStatus(t) {
    const cur = t.status || 'to_do'
    const next = TASK_STATUS_CYCLE[(TASK_STATUS_CYCLE.indexOf(cur) + 1) % TASK_STATUS_CYCLE.length]
    tasks = tasks.map(x => x.id === t.id ? { ...x, status: next } : x)
    const res = await updateTask(t.id, { status: next })
    if (res?.recurring_spawned) {
      toast(`Finalizat ✓ — următoarea apariție: ${formatDate(res.recurring_next)}`, 'success')
    }
    await reloadTasks()
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
      toast(files.length === 1 ? 'Fișier atașat' : `${files.length} fișiere atașate`, 'success')
      await Promise.all([loadAtt(taskId, true), reloadTasks()])
    } catch (err) {
      toast(`Eroare: ${err.message}`, 'error')
    } finally { attUploading = false }
  }

  async function doDeleteAtt() {
    if (!attDeleteId) return
    try {
      await deleteTaskAttachment(attDeleteId)
      toast('Atașament șters', 'success')
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

  const PRIO_CYCLE = ['normal', 'urgent', 'minor'] // dupa Normal urmeaza Urgent (cerinta Ion)
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
    toast('Echipament șters', 'success')
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

  // B1: cod de parametru din echipament -> deschide detaliul din baza de parametri.
  // Rezolva codul -> id prin cautarea globala (ranking exact-pe-cod) si foloseste
  // deep-link-ul /params?open=<id>.
  let paramJumping = $state(false)
  async function openParamDetail(code) {
    const c = String(code || '').trim()
    if (!c || paramJumping) return
    paramJumping = true
    try {
      const r = await apiJson('/api/search?q=' + encodeURIComponent(c))
      const hits = (r.results || []).filter((x) => x.type === 'parametru')
      const hit = hits.find((x) => String(x.cod).toLowerCase() === c.toLowerCase()) || hits[0]
      if (hit) navigate('/params?open=' + hit.id)
      else toast(`Parametrul „${c}" nu e in baza de parametri`, 'error')
    } catch (_) {
      toast('Nu am putut deschide parametrul', 'error')
    } finally {
      paramJumping = false
    }
  }

  // B7: copiaza rapid "cod = valoare"
  function copyParam(k, v) {
    const text = `${k} = ${v}`
    if (!navigator.clipboard) { toast('Copierea nu e disponibila', 'error'); return }
    navigator.clipboard.writeText(text).then(
      () => toast(`Copiat: ${text}`, 'success'),
      () => toast('Nu am putut copia', 'error'),
    )
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

  const tasksDone = $derived(tasks.filter(t => t.status === 'done' || t.status === 'finalizat').length)
  // Hide a recurring task's next occurrence until its scadenta arrives (see Tasks.svelte).
  const activeTasks = $derived(tasks.filter(t => t.status !== 'done' && t.status !== 'finalizat' && !isFutureRecurrence(t)))
  const doneTasks = $derived(tasks.filter(t => t.status === 'done' || t.status === 'finalizat'))

  // Rail: progres taskuri + zile pana la deadline
  const taskPct = $derived(tasks.length ? Math.round((tasksDone / tasks.length) * 100) : 0)
  const deadlineDays = $derived.by(() => {
    if (!project?.deadline) return null
    return Math.round((new Date(String(project.deadline).slice(0, 10)) - new Date(new Date().toDateString())) / 86400000)
  })
  function deadlineLabel(d) {
    if (d === null) return ''
    if (d < 0) return `depășit cu ${-d} ${d === -1 ? 'zi' : 'zile'}`
    if (d === 0) return 'scadent astăzi'
    if (d === 1) return '1 zi rămasă'
    return `${d} zile rămase`
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
                <div class="trow" use:focusOnLand={focusKey('task', t.id)} style="--sev: {t.prioritate ? priorityColor(t.prioritate) : 'var(--border-strong)'}">
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
                      {#if t.atasamente_count}<span class="att-ind"><Paperclip size={10} /> {t.atasamente_count}</span>{/if}
                      {#if t.data_scadenta}
                        <span class="tdeadline" class:overdue={isOverdue(t.data_scadenta)} class:today={isToday(t.data_scadenta)} class:soon={isSoon(t.data_scadenta)}>{formatDate(t.data_scadenta)}</span>
                      {/if}
                    </div>
                  </button>
                  <div class="task-actions">
                    <button class="status-badge" style="color: {STATUS_COLORS[t.status] || 'var(--text-dim)'}; border-color: {STATUS_COLORS[t.status] || 'var(--text-dim)'}" onclick={() => cycleTaskStatus(t)} title="Click pentru a schimba statusul">{TASK_STATUS_LABELS[t.status] || t.status || 'To Do'}</button>
                    <button class="prio-badge" style="color: {priorityColor(t.prioritate || 'normal')}; border-color: {priorityColor(t.prioritate || 'normal')}" onclick={() => cycleTaskPriority(t)} title="Click pentru a schimba prioritatea">{priorityLabel(t.prioritate || 'normal')}</button>
                    <button class="task-edit" onclick={() => openTaskEditModal(t)} title="Editează task"><SolidIcon name="pencil" size={13} /></button>
                    <button class="task-del" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Șterge task"><SolidIcon name="trash" size={13} /></button>
                  </div>
                </div>
                {#if expandedTask === t.id}
                  {@const subs = subtasksCache[t.id] || []}
                  {@const atts = attCache[t.id] || []}
                  {@const doneCount = subs.filter(s => s.done).length}
                  <div class="subtask-body" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
                    {#if t.descriere}
                      <div class="note-block">
                        <RichText value={t.descriere} class="note-content" collapsible maxHeight={200} />
                        <button class="note-edit-btn" title="Editează notițe" onclick={() => openNoteModal(t)}><SolidIcon name="pencil" size={12} /> Editează</button>
                      </div>
                    {/if}

                    {#if atts.length}
                      <div class="att-row">
                        {#each atts as a (a.id)}
                          <span class="att-chip">
                            <button class="att-open" title="{a.nume_fisier} ({a.tip_fisier})" onclick={() => openAttPreview(a, t.id)}>
                              <Paperclip size={11} /><span class="att-fname">{a.nume_fisier}</span>
                            </button>
                            <button class="att-del" title="Șterge atașament" onclick={() => { attDeleteId = a.id; attDeleteTaskId = t.id; showAttDelete = true }}><SolidIcon name="trash" size={11} /></button>
                          </span>
                        {/each}
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
                  <div class="trow done" animate:flip={{ duration: motionDuration(DUR_BASE) }} use:focusOnLand={focusKey('task', t.id)} style="--sev: {t.prioritate ? priorityColor(t.prioritate) : 'var(--border-strong)'}">
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

      {:else if activeTab === 'equipment'}
        <div class="tab-header">
          <span class="tab-sub">{equipment.length} echipamente</span>
          <div class="equip-btns">
            <Button size="sm" variant="ghost" onclick={triggerImportStarter} disabled={importBusy}><Upload size={14} /> Import STARTER</Button>
            <Button size="sm" variant="ghost" onclick={triggerImportAbb} disabled={importBusy}><Upload size={14} /> Import ABB</Button>
            <Button size="sm" variant="ghost" onclick={openCopyModal}><Copy size={14} /> Copiază</Button>
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
                  <button class="att-btn" title="Editează" onclick={() => editEquip(e)}><SolidIcon name="pencil" size={14} /></button>
                  <button class="att-btn danger" title="Șterge" onclick={() => { equipDeleteId = e.id; showEquipDelete = true }}><SolidIcon name="trash" size={14} /></button>
                </div>
              </div>
              <div class="edetails">
                {#if e.model}<span>Model: {e.model}</span>{/if}
                {#if e.serial_number}<span>Serie: {e.serial_number}</span>{/if}
              </div>
              {@const eManual = manualUrlForEquip(e.producator, e.model)}
              {@const eFam = familieForEquip(e.producator, e.model)}
              {#if eManual || eFam}
                <div class="ecard-links">
                  {#if eManual}<a class="ecard-link" href={eManual} target="_blank" rel="noopener"><BookOpen size={13} /> Manual</a>{/if}
                  {#if eFam}<button class="ecard-link" onclick={() => navigate(`/params?tab=faults&familie=${encodeURIComponent(eFam)}`)}><AlertCircle size={13} /> Coduri erori</button>{/if}
                </div>
              {/if}
              {#if eparams.length > 0}
                {@const pq = (equipParamSearch[e.id] || '').toLowerCase()}
                {@const filteredParams = pq ? eparams.filter(([k, v]) => k.toLowerCase().includes(pq) || v.toLowerCase().includes(pq)) : eparams}
                <button class="eparam-toggle" onclick={() => toggleEquipExpand(e.id)}>
                  {#if isExpanded}<ChevronDown size={12} /> Ascunde parametri{:else}<ChevronRight size={12} /> {eparams.length} parametri{/if}
                </button>
                {#if isExpanded}
                  <div class="eparams-wrap" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
                    {#if eparams.length > 5}
                      <input type="text" class="eparam-search" placeholder="Filtrează parametri..." value={equipParamSearch[e.id] || ''} oninput={(ev) => { equipParamSearch = { ...equipParamSearch, [e.id]: ev.target.value } }} />
                    {/if}
                    <div class="eparams">
                      {#each filteredParams as [k, v]}
                        <div class="eparam">
                          <button class="eparam-key eparam-link" onclick={() => openParamDetail(k)} title="Deschide detaliul parametrului {k}">{k}</button>
                          <span class="eparam-right">
                            <span class="eparam-val">{v}</span>
                            <button class="eparam-copy" onclick={() => copyParam(k, v)} title="Copiază „{k} = {v}”" aria-label="Copiază parametrul"><Copy size={12} /></button>
                          </span>
                        </div>
                      {/each}
                      {#if pq && filteredParams.length === 0}
                        <div class="eparam-empty">Niciun parametru găsit</div>
                      {/if}
                    </div>
                  </div>
                {/if}
              {/if}
            </Card>
          {/each}</div>
        {/if}

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

      {:else if activeTab === 'attachments'}
        <AttachmentsTab projectId={params.id} />

      {:else if activeTab === 'info'}
        <div class="igrid">
          {#each [['Client', project.client], ['Locație', project.locatie], ['Echipament', project.echipament_principal], ['Producător', project.producator], ['Cod proiect', project.cod_proiect], ['PM', project.pm], ['Nr. comandă', project.nr_comanda], ['Nr. contract', project.nr_contract], ['Data începere', formatDate(project.data_incepere)], ['Deadline', formatDate(project.deadline)]] as [label, val]}
            <div class="irow"><span class="ilabel">{label}</span><span>{val || '—'}</span></div>
          {/each}
        </div>
        <div style="margin-top: var(--space-md)"><ImplPeriods projectId={params.id} /></div>
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

      <section class="rcell cell-in">
        <div class="cell-label"><span class="ico ico-red"><SolidIcon name="clock" size={12} /></span>Deadline</div>
        {#if project.deadline}
          <div class="rdate" class:urgent={deadlineDays !== null && deadlineDays <= 2}>{formatDate(project.deadline)}</div>
          <div class="rsub">{deadlineLabel(deadlineDays)}</div>
        {:else}
          <div class="rsub rsub-empty">Fără termen</div>
        {/if}
      </section>

    </aside>
    </div>
  {/if}
</div>

<ProjectFormModal bind:open={showEditModal} {project} onsaved={() => load()} />
<EquipmentFormModal bind:open={showEquipModal} projectId={params.id} equipment={editingEquipment} onsaved={() => reloadEquipment()} />

<Modal bind:open={showImportModal} title="Import Echipamente" size="lg">
  {#if importPreview}
    <div class="import-info">
      <span>{importPreview.drives?.length || 0} drive-uri detectate</span>
      {#if importPreview.skipped_default}<span class="dim">({importPreview.skipped_default} parametri la valoare default omiși)</span>{/if}
    </div>
    <div class="import-drives">
      {#each (importPreview.drives || []) as drv, i}
        <div class="import-drive" class:import-selected={importSelected.has(i)}>
          <label class="import-check">
            <input type="checkbox" checked={importSelected.has(i)} onchange={() => toggleImportDrive(i)} />
            <div class="import-drive-info">
              <strong>{drv.nume || `Drive ${i + 1}`}</strong>
              <span class="dim">{drv.producator} {drv.model}{drv.firmware ? ` (FW ${drv.firmware})` : ''}</span>
              <span class="dim">{Object.keys(drv.params || {}).length} parametri modificați</span>
            </div>
          </label>
        </div>
      {/each}
    </div>
  {/if}
  {#snippet footer()}
    {#if importPreview}
      <div class="modal-actions">
        <Button variant="secondary" onclick={() => { showImportModal = false; importPreview = null }}>Anulează</Button>
        <Button loading={importBusy} disabled={importSelected.size === 0} onclick={commitImport}>
          <Upload size={14} /> Importă {importSelected.size} echipamente
        </Button>
      </div>
    {/if}
  {/snippet}
</Modal>

<Modal bind:open={showCopyModal} title="Copiază echipamente din alt proiect" size="lg">
  <div class="copy-form">
    <Select label="Proiect sursă" bind:value={copyProjectId} onchange={loadCopyEquipment} placeholder="Selectează proiect..." options={copyProjects.map((p) => ({ value: p.id, label: `${p.nume}${p.client ? ` — ${p.client}` : ''}` }))} />
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
      <p class="empty">Niciun echipament în proiectul selectat.</p>
    {/if}
  </div>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showCopyModal = false}>Anulează</Button>
      <Button loading={copyBusy} disabled={copySelected.size === 0} onclick={commitCopy}>
        <Copy size={14} /> Copiază {copySelected.size} echipamente
      </Button>
    </div>
  {/snippet}
</Modal>
<ConfirmDialog bind:open={showDeleteConfirm} title="Șterge proiect" message={`Ștergi proiectul "${project?.nume}"? Toate datele (taskuri, atașamente, echipamente) vor fi șterse definitiv.`} confirmLabel="Șterge definitiv" onconfirm={handleDeleteProject} />
<ConfirmDialog bind:open={showEquipDelete} title="Șterge echipament" message="Ștergi acest echipament?" confirmLabel="Șterge" onconfirm={doDeleteEquip} />
<ConfirmDialog bind:open={showTaskDelete} title="Șterge task" message="Ștergi acest task? Toate subtaskurile asociate vor fi șterse." confirmLabel="Șterge" onconfirm={doDeleteTask} />
<ConfirmDialog bind:open={showAttDelete} title="Șterge atașament" message="Ștergi acest fișier atașat?" confirmLabel="Șterge" onconfirm={doDeleteAtt} />
<AttachmentPreview bind:open={attPreviewOpen} attachment={attPreviewAtt} ondelete={attPreviewDelete} />
<input type="file" multiple hidden bind:this={attInput} onchange={onAttFiles} />

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
        <Select label="Prioritate" bind:value={taskFormPriority} options={['Normal', 'Minor', 'Urgent']} />
      </div>
      <div class="mf-field">
        <span class="mf-label">Deadline</span>
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
  .meta { font-size: var(--font-small); color: var(--text-dim); margin-top: 4px; display: flex; gap: var(--space-xs); }
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
  .req-list { margin-top: 10px; display: flex; flex-direction: column; gap: 4px; }
  .req-name { font-size: var(--font-small); color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .req-more { font-size: var(--font-tiny); color: var(--text-faint); }

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
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .empty { color: var(--text-dim); font-size: var(--font-small); padding: var(--space-lg) 0; text-align: center; }

  /* Task list */
  .task-list { display: flex; flex-direction: column; }
  .trow-wrap { display: flex; flex-direction: column; }
  /* Insula (V3+V2): fara bara pe stanga — underline de severitate jos + index mono ghost */
  .trow { position: relative; display: flex; align-items: center; gap: var(--space-sm); padding: 8px var(--space-sm) 10px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: 6px; transition: transform var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease), opacity var(--dur-base) var(--ease); }
  .trow::after { content: ''; position: absolute; left: 12px; bottom: 0; height: 2px; width: 40px; border-radius: 2px 2px 0 0; background: var(--sev, var(--border-strong)); box-shadow: 0 0 8px color-mix(in srgb, var(--sev, transparent) 45%, transparent); }
  .trow:hover { transform: translateX(4px); border-color: var(--border-strong); }
  .tix { font-family: var(--font-mono); font-size: 1rem; font-weight: var(--fw-bold); letter-spacing: -0.04em; color: color-mix(in srgb, var(--sev, var(--border-strong)) 70%, transparent); min-width: 28px; flex-shrink: 0; font-variant-numeric: tabular-nums; }
  .done-list { display: flex; flex-direction: column; }
  .task-actions { display: flex; align-items: center; gap: var(--space-xs); flex-shrink: 0; }
  .trow.done { opacity: 0.5; }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; }
  .check:hover { color: var(--accent); }
  .trow.done .check { color: var(--success); }
  .check-empty { width: 16px; height: 16px; border: 2px solid var(--border); border-radius: 50%; }
  .tmain { flex: 1; min-width: 0; cursor: pointer; text-align: left; }
  .status-badge { font-size: var(--font-micro); font-weight: var(--fw-semibold); padding: 2px 10px; min-height: 22px; border-radius: var(--radius-full); background: transparent; border: 1px solid; cursor: pointer; white-space: nowrap; transition: all var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); display: inline-block; min-width: 62px; text-align: center; }
  .status-badge:hover { opacity: .7; }
  .status-badge:active { transform: scale(0.92); }
  .recur-badge { display: inline-flex; align-items: center; gap: 3px; padding: 0 6px; background: var(--accent-subtle); color: var(--accent); border-radius: var(--radius-xs); font-weight: var(--fw-medium); }
  .task-form { display: flex; flex-direction: column; gap: var(--space-md); }
  .mf-textarea { padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-body); font-family: inherit; resize: vertical; min-height: 60px; }
  .task-edit { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: all var(--dur-fast); }
  .trow:hover .task-edit { opacity: 1; }
  .task-edit:hover { color: var(--accent); background: var(--accent-subtle); }
  .ttitle-row { display: flex; align-items: center; gap: var(--space-xs); }
  .ttitle { font-size: var(--font-small); color: var(--text); font-weight: var(--fw-medium); }
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  .note-ind { display: inline-flex; align-items: center; color: var(--text-dim); }
  .tinfo { display: flex; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; align-items: center; }
  .prio-badge { font-size: var(--font-tiny); font-weight: var(--fw-semibold); padding: 2px 10px; min-height: 22px; border-radius: var(--radius-full); background: transparent; border: 1px solid; cursor: pointer; white-space: nowrap; transition: all var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); display: inline-block; min-width: 62px; text-align: center; }
  .prio-badge:hover { opacity: .8; }
  .prio-badge:active { transform: scale(0.92); }
  .tsub-chip { padding: 1px 6px; border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent); font-weight: var(--fw-semibold); font-size: var(--font-micro); }
  .tdeadline { font-size: var(--font-micro); }
  .tdeadline.overdue { color: var(--danger); font-weight: var(--fw-semibold); }
  .tdeadline.today { color: var(--accent); font-weight: var(--fw-semibold); }
  .tdeadline.soon { color: var(--warning); }
  .task-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: all var(--dur-fast); }
  .trow:hover .task-del { opacity: 1; }
  .task-del:hover { color: var(--danger); background: var(--danger-subtle); }

  /* Done separator */
  .done-sep { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-xs); font-size: var(--font-tiny); font-weight: var(--fw-semibold); color: var(--text-dim); cursor: pointer; margin-top: var(--space-sm); border-top: 1px solid var(--border-subtle); text-transform: uppercase; letter-spacing: var(--tracking-wide); }
  .done-sep:hover { color: var(--text-secondary); }

  /* Subtask expanded area */
  /* Corp expandat: panou inset (nu mai pluteste pe negru), continut grupat cu gap */
  .subtask-body { margin-left: 26px; margin-bottom: var(--space-sm); padding: var(--space-12); background: var(--bg-surface); border: 1px solid var(--border-subtle); border-left: 2px solid var(--accent-subtle); border-radius: var(--radius-md); display: flex; flex-direction: column; gap: var(--space-12); }
  .detail-actions { display: flex; flex-wrap: wrap; gap: var(--space-xs); }
  .detail-chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-full); color: var(--text-secondary); font-size: var(--font-tiny); cursor: pointer; transition: all var(--dur-fast) var(--ease); }
  .detail-chip:hover:not(:disabled) { color: var(--accent-on-subtle); border-color: var(--accent); background: var(--accent-subtle); }
  .detail-chip:active:not(:disabled) { transform: scale(0.97); }
  .detail-chip:disabled { opacity: 0.5; cursor: default; }
  .note-block { display: flex; flex-direction: column; gap: var(--space-xs); }
  .note-edit-btn { display: inline-flex; align-items: center; gap: 5px; align-self: flex-start; padding: 3px 8px; font-size: var(--font-tiny); color: var(--text-faint); cursor: pointer; border-radius: var(--radius-xs); transition: all var(--dur-fast) var(--ease); }
  .note-edit-btn:hover { color: var(--accent); background: var(--accent-subtle); }
  .sub-section { display: flex; flex-direction: column; gap: 2px; }
  .sub-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
  .sub-cap { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-wide); color: var(--text-faint); }
  .sub-prog { font-size: var(--font-tiny); color: var(--text-dim); font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
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
  .sub-add input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .sub-add-btn { width: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .sub-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
  .sub-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .sub-loading { font-size: var(--font-tiny); color: var(--text-dim); padding: var(--space-xs) 0; }

  /* Equipment */
  .elist { display: flex; flex-direction: column; gap: var(--space-sm); }
  .ecard-top { display: flex; align-items: center; justify-content: space-between; }
  .ecard-actions { display: flex; gap: 2px; }
  .ename { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); }
  .edetails { display: flex; gap: var(--space-md); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 4px; }
  .ecard-links { display: flex; flex-wrap: wrap; gap: var(--space-xs); margin-top: var(--space-sm); }
  .ecard-link { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-tiny); font-weight: var(--fw-medium); color: var(--accent); background: var(--accent-subtle); border: 1px solid color-mix(in srgb, var(--accent) 20%, transparent); border-radius: var(--radius-full); padding: 4px 11px; cursor: pointer; text-decoration: none; transition: background var(--dur-fast) var(--ease); }
  .ecard-link:hover { background: color-mix(in srgb, var(--accent) 20%, transparent); }
  .eparam-toggle { display: flex; align-items: center; gap: var(--space-xs); font-size: var(--font-tiny); color: var(--accent); cursor: pointer; margin-top: var(--space-sm); padding: 4px 0; font-weight: var(--fw-medium); }
  .eparam-toggle:hover { text-decoration: underline; }
  .eparams-wrap { margin-top: var(--space-xs); }
  .eparam-search { width: 100%; padding: 6px 10px; margin-bottom: var(--space-xs); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-small); }
  .eparam-search:focus { border-color: var(--accent); outline: none; }
  .eparam-empty { padding: var(--space-sm); text-align: center; color: var(--text-dim); font-size: var(--font-tiny); grid-column: 1 / -1; background: var(--bg); }
  .eparams { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1px; border-top: 1px solid var(--border-subtle); padding-top: var(--space-sm); background: var(--border-subtle); border-radius: var(--radius-sm); overflow: hidden; }
  .eparam { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); padding: 6px var(--space-sm); background: var(--bg); font-size: var(--font-small); }
  .eparam-key { color: var(--accent); font-family: var(--font-mono); font-size: var(--font-tiny); font-weight: var(--fw-medium); flex-shrink: 0; }
  .eparam-link { background: none; border: none; padding: 0; cursor: pointer; text-align: left; border-bottom: 1px dashed transparent; transition: border-color var(--dur-fast) var(--ease); }
  .eparam-link:hover { border-bottom-color: var(--accent); }
  .eparam-right { display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
  .eparam-val { color: var(--text); font-weight: var(--fw-medium); text-align: right; }
  .eparam-copy { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: var(--radius-xs); color: var(--text-dim); background: transparent; border: none; cursor: pointer; opacity: 0; transition: opacity var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease); flex-shrink: 0; }
  .eparam:hover .eparam-copy { opacity: 1; }
  .eparam-copy:hover { color: var(--accent); background: var(--accent-subtle); }
  @media (pointer: coarse) { .eparam-copy { opacity: 0.6; } }
  .att-btn { width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); }
  .att-btn:hover { background: var(--bg-hover); color: var(--text); }
  .att-btn.danger:hover { background: var(--danger-subtle); color: var(--danger); }

  /* Info tab */
  .igrid { display: flex; flex-direction: column; gap: var(--space-sm); }
  .irow { display: flex; justify-content: space-between; font-size: var(--font-small); padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
  .ilabel { color: var(--text-dim); font-weight: var(--fw-medium); }

  .mf-row { display: flex; gap: var(--space-md); }
  .mf-field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
  .mf-label { font-size: var(--font-tiny); font-weight: var(--fw-medium); color: var(--text-secondary); text-transform: uppercase; letter-spacing: var(--tracking-wide); }

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

  @media (max-width: 940px) {
    .rail-grid { grid-template-columns: 1fr; }
    .rail { position: static; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; order: -1; margin-bottom: var(--space-sm); }
  }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .header-top { flex-direction: column; }
    .edetails { flex-wrap: wrap; gap: var(--space-sm); }
    .trow { padding: var(--space-sm); flex-wrap: wrap; align-items: flex-start; row-gap: 6px; }
    .check { padding-top: 1px; }
    .task-actions { flex-basis: 100%; justify-content: flex-end; }
    .back { min-height: 44px; }
    .subtask-body { margin-left: var(--space-sm); }
    .sub-del, .task-del, .task-edit { opacity: 1; }
    .note-edit-btn { opacity: 1; }
    .quick-add input, .quick-add-btn { min-height: 44px; }
    .quick-add-btn { width: 44px; }
  }
</style>
