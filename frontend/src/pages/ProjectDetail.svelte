<script module>
  import { urlProiect as _urlP, urlTaskuriProiect as _urlT } from '../stores/projects.svelte.js'
  import { preia as _preia, dinCache as _dinCache, uita as _uita } from '../lib/cache.js'

  /** Preincarcarea rutei: cardul de proiect din /projects cheama asta la hover,
   *  deci pana apesi, pagina are si proiectul, si taskurile lui.
   *  Taskurile au `catch`: daca pica doar ele, pagina TOT trebuie sa se
   *  deschida — aceeasi regula ca in `load`, unde esecul lor da o lista goala,
   *  nu o pagina de eroare. */
  export function pregateste(params) {
    const id = params?.id
    if (!id) return
    return Promise.all([
      _preia(_urlP(id), { proaspat: 5000 }),
      _preia(_urlT(id), { proaspat: 5000 }).catch(() => null),
    ])
  }
</script>

<script>
  import { onMount } from 'svelte'
  import { slide, fade } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { ArrowLeft, Plus, CheckCircle2, CalendarDays, ListChecks, AlertCircle, ListTodo, Settings2, FileDown, ChevronDown, ChevronRight, Repeat, BookOpen, CalendarRange, Check, Text } from '@lucide/svelte'
  import ImplPeriods, { urlPerioade } from '../components/projects/ImplPeriods.svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import {
    loadProjectDetail, loadProjectTasks, deleteProject, updateProject,
  } from '../stores/projects.svelte.js'
  import { apiJson } from '../lib/api.js'
  import { updateTask, createTask, deleteTask, loadSubtasks, createSubtask, updateSubtask, deleteSubtask } from '../stores/tasks.svelte.js'
  import { PROJECT_STATUS_LABELS, STATUS_COLORS, formatDate, dueRing, isFutureRecurrence, esteDepasit as isOverdue, esteAzi as isToday } from '../lib/formatters.js'
  import { etichetaTermen, etichetaTermenScurt, grupeazaDupaTermen, ORDINE_GRUPE } from '../lib/grupare.js'
  import { ecran } from '../lib/ecran.svelte.js'
  import { exportMarkdown } from '../lib/exportMd.js'
  import RichText from '../components/ui/RichText.svelte'
  import { navigate, router } from '../lib/router.svelte.js'
  import { motionDuration, DUR_FAST, DUR_BASE, plecare, sosire, desfacere, alunecare, EASE } from '../lib/motion.svelte.js'
  import { focusOnLand, focusKey } from '../lib/focus.js'
  import { glisare } from '../lib/glisare.js'
  import { apasareLunga } from '../lib/apasareLunga.js'
  import FoaieTask from '../components/FoaieTask.svelte'
  import FoaieAdauga from '../components/FoaieAdauga.svelte'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import Badge from '../components/ui/Badge.svelte'
  import Card from '../components/ui/Card.svelte'
  import Button from '../components/ui/Button.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ContorPasi from '../components/ui/ContorPasi.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import Input from '../components/ui/Input.svelte'
  import Textarea from '../components/ui/Textarea.svelte'
  import Select from '../components/ui/Select.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  import ProjectFormModal from '../components/projects/ProjectFormModal.svelte'
  import MarkdownView from '../components/notes/MarkdownView.svelte'
  import EditorLung from '../components/ui/EditorLung.svelte'
  import { todayISO, addDays, diffDays } from '../lib/calendarDates.js'

  let azi = $state(todayISO())

  let { params } = $props()
  let project = $state(null)
  let tasks = $state([])
  let taskDeleteId = $state(null)
  let showTaskDelete = $state(false)
  let loading = $state(true)
  let error = $state(null)
  let activeTab = $state('tasks')

  // ===== COMUTAREA TABURILOR (2026-08-15) =====
  //
  // Ion: „cum se deschid taburile de proiecte, acum e cu ramasite si schelet,
  // nu se deschide fluent."
  //
  // Continutul se estompa deja (`in:fade`), dar FARA directie — singurul loc din
  // aplicatie ramas asa, dupa ce ruta, luna din Calendar si sfera din Taskuri au
  // primit toate o alunecare care spune incotro ai mers. Un fondu pur intre doua
  // liste diferite nu spune nimic despre relatia lor.
  //
  // Sensul vine din ORDINEA taburilor, ca la doc: mergi spre dreapta ->
  // continutul soseste din dreapta.
  let tabSens = $state(0)
  function alegeTab(cheie) {
    if (cheie === activeTab) return
    const a = tabs.findIndex((t) => t.key === activeTab)
    const z = tabs.findIndex((t) => t.key === cheie)
    tabSens = a >= 0 && z >= 0 ? (z > a ? 1 : -1) : 0
    activeTab = cheie
  }

  // Sublinierea se MASOARA din tabul activ, nu se calculeaza din indici: cele
  // trei etichete au latimi diferite, iar o socoteala paralela s-ar desparti de
  // desen la prima schimbare de text sau de font.
  let tabsEl = $state(null)
  let linie = $state({ x: 0, w: 0, gata: false })
  let linieAsezata = $state(false)
  let linieMasurata = false        // NEreactiv: citit in efectul care scrie `linie`

  function masoaraLinia() {
    const el = tabsEl?.querySelector('.tab.active')
    if (!el) { linie.gata = false; return false }
    linie.x = el.offsetLeft
    linie.w = el.offsetWidth
    linie.gata = true
    return true
  }

  $effect(() => {
    activeTab; tabs
    if (!tabsEl) return
    if (masoaraLinia() && !linieMasurata) {
      linieMasurata = true
      // Un cadru fara tranzitie, ca prima asezare sa nu alunece din stanga.
      requestAnimationFrame(() => { linieAsezata = true })
    }
  })

  /** Incalzeste datele unui tab INAINTE sa fie deschis — la hover pe desktop, la
   *  apasare pe telefon. Masurat cu 150ms dus-intors: prima vizita pe „Perioade"
   *  si pe „Wiki" trecea printr-un cadru de schelet si trei stari vizuale; a doua
   *  era deja curata, fiindca memoria le avea. Deci nu lipsea cache-ul, lipsea
   *  momentul in care sa fie umplut.
   *  Taskurile nu apar aici: vin odata cu proiectul, in `load()`. */
  function pregatesteTab(cheie) {
    try {
      if (cheie === 'perioade') _preia(urlPerioade(params.id), { proaspat: 5000 })
      else if (cheie === 'wiki') _preia(urlWiki(params.id), { proaspat: 5000 })
    } catch (_) { /* incalzirea e tacuta prin definitie */ }
  }

  let newTaskTitle = $state('')
  let newTaskData = $state('')   // termenul ales din „Alege data", la compozitor
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
  let noteSalveaza = $state(null)

  let showEditModal = $state(false)
  let showDeleteConfirm = $state(false)
  // Cate perioade dispar odata cu proiectul. Nu vin cu `project` (nici lista, nici
  // detaliul nu le numara), iar `ImplPeriods` si le incarca singur — deci se cer
  // exact in clipa in care intrebarea se pune, nu la fiecare deschidere de pagina.
  // `null` = inca nu stim; propozitia NU inventeaza atunci o cifra.
  let nrPerioade = $state(null)

  async function ceriStergereaProiectului() {
    nrPerioade = null
    showDeleteConfirm = true
    try {
      const p = await apiJson(`/api/proiecte/${params.id}/implementari`)
      nrPerioade = Array.isArray(p) ? p.length : 0
    } catch (_) { nrPerioade = null }
  }

  /** „7 taskuri și 2 perioade" — enumerare care sare peste ce e zero. Un „0
   *  perioade" ar cere sa fie citit ca sa afli ca nu inseamna nimic. */
  const ceDispare = $derived.by(() => {
    const p = []
    if (tasks.length) p.push(`${tasks.length} ${tasks.length === 1 ? 'task' : 'taskuri'}`)
    if (nrPerioade) p.push(`${nrPerioade} ${nrPerioade === 1 ? 'perioadă' : 'perioade'}`)
    if (!p.length) return 'Nu se poate anula.'
    return `Dispar odată cu el ${p.join(' și ')}. Nu se poate anula.`
  })

  const subDeSters = $derived(taskDeleteId ? (subtasksCache[taskDeleteId] || null) : null)
  const taskDeSters = $derived(tasks.find((t) => t.id === taskDeleteId) || null)

  // Subtask state
  let expandedTask = $state(null)
  let subtasksCache = $state({})

  /** Contorul de pasi de pe rand („2/5"), sau `null` cand taskul n-are subtaskuri.
   *  Aceeasi regula ca in /tasks: cea mai proaspata sursa castiga. Aici lista se
   *  reincarca dupa fiecare scriere de subtask (`reloadTasks`), dar reincarcarea
   *  are un dus-intors — cache-ul e deja corect in clipa atingerii. Un `[]` in
   *  cache inseamna „am intrebat, n-are niciunul", deci scoate contorul. */
  function pasi(t) {
    const subs = subtasksCache[t.id]
    const total = subs ? subs.length : (t.subtask_total || 0)
    if (!total) return { total: 0, gata: 0 }
    return { total, gata: subs ? subs.filter(s => s.done).length : (t.subtask_done || 0) }
  }
  let newSubtaskTitle = $state('')
  let adaugSubLa = $state('')   // id-ul taskului al carui compozitor de subtask e deschis

  // Deschide direct in scriere, cu textul selectat — ca in /tasks.
  function focalizeaza(node) { node.focus(); node.select() }

  // Done tasks collapse
  let showDoneTasks = $state(false)

  // Campurile lungi (observatii, service_before, service_after) — acelasi
  // `EditorLung` ca nota unui task.
  let showFieldEdit = $state(false)
  let editValue = $state('')
  let editLabel = $state('')
  let editSalveaza = $state(null)

  // Echipamente + Atasamente scoase din navigatie (2026-07-27, pregatire v28):
  // parametrii de drive stau in wiki (skill drive-backup), backup-urile brute in
  // raw/projects/<slug>/. Codul ramane pana la migratie.
  // Tabul „Info" a fost scos (2026-07-27): repeta antetul README-ului din wiki
  // (Client, Locație, Cod proiect, Nr. comandă), iar 4 din 10 campuri erau
  // aproape mereu goale. Datele au trecut in bara laterala, iar editorul de
  // perioade — singurul lucru nedublat de acolo — a trecut la Gantt.
  /** Coloana pironita din dreapta randului de task. Un task recurent isi spune
   *  cadenta: pentru el „când" nu e o zi, e un ritm. */
  function termenScurtTask(t) {
    if (t.recurenta && !t.data_scadenta) return t.recurenta
    return etichetaTermenScurt(t.data_scadenta)
  }

  const tabs = [
    { key: 'tasks', label: 'Taskuri', icon: ListTodo },
    { key: 'perioade', label: 'Perioade', icon: CalendarRange },
    { key: 'wiki', label: 'Wiki', icon: BookOpen },
  ]

  // Wiki tab — notele proiectului din vault-ul Obsidian (read-only, lazy load)
  let wikiInfo = $state(null)
  let wikiNote = $state(null)
  let wikiContent = $state('')
  let wikiListLoading = $state(false)
  let wikiNoteLoading = $state(false)

  // TABURILE DIN PAGINA DE PROIECT TREC SI ELE PRIN MEMORIE.
  //
  // Ion: „taburile din proiecte nu prea le-ai atins, se incarca tot cu schelete
  // de fiecare data." Corect: reparasem intrarea PE pagina, nu si taburile din
  // ea. `wikiInfo` si `wikiContent` sunt stare de componenta, iar componenta
  // moare la fiecare navigare — deci fiecare revenire pe tabul Wiki cerea din
  // nou lista de note SI continutul primei note, cu doua schelete unul dupa
  // altul.
  //
  // Notele din vault sunt cel mai bun candidat din aplicatie: se schimba de
  // cateva ori pe luna, iar cand le schimbi TU, o face `saveWikiEdit`, care
  // uita ce stia memoria.
  const urlWiki = (id) => `/api/proiecte/${id}/wiki`
  const urlNota = (cale) => `/api/obsidian/note?path=${encodeURIComponent(cale)}`

  async function loadWiki() {
    const url = urlWiki(params.id)
    const gata = _dinCache(url)
    if (gata !== undefined) wikiInfo = gata
    else wikiListLoading = true
    try {
      wikiInfo = await _preia(url)
    } catch (e) {
      if (gata === undefined) wikiInfo = { error: e.message, notes: [] }
    } finally { wikiListLoading = false }
    if (wikiInfo?.notes?.length && !wikiNote) openWikiNote(wikiInfo.notes[0])
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
      // Ce stia memoria despre nota asta e acum vechi, iar `openWikiNote` nu se
      // mai cheama — starea locala e deja corecta. Fara asta, urmatoarea intrare
      // pe tab ar deschide nota cu TEXTUL DE DINAINTE de salvare.
      _uita(urlNota(wikiNote.path))
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
    const url = urlNota(note.path)
    const gata = _dinCache(url)
    // Si aici seedul e sincron: trecerea de la o nota la alta e o apasare, iar
    // o nota deja citita trebuie sa se intoarca fara sa clipeasca.
    if (gata !== undefined) { wikiContent = gata.content || ''; wikiNoteLoading = false }
    else { wikiContent = ''; wikiNoteLoading = true }
    try {
      const data = await _preia(url)
      wikiContent = data.content || ''
    } catch (e) {
      if (gata === undefined) {
        wikiContent = ''
        toast(`Eroare la încărcarea notei: ${e.message}`, 'error')
      }
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

  // Doar prima citire ia din cache; vezi comentariul din `load`.
  let primaCitire = true

  async function load() {
    // SE DESCHIDE CU CE STIM, SE CORECTEAZA CU CE VINE.
    //
    // Pagina isi tinea starea in componenta, iar routerul o distruge la fiecare
    // navigare: reveneai pe acelasi proiect si primeai iar schelet, desi nimic
    // nu se schimbase. Cache-ul e cheiat pe URL, deci merge si aici, unde
    // raspunsul depinde de id.
    //
    // Seedul e DOAR la montare. `load()` se cheama si dupa fiecare scriere, iar
    // acolo cache-ul e starea de dinainte: ar clipi inapoi la vechi exact in
    // clipa in care astepti confirmarea.
    const uP = _urlP(params.id)
    const uT = _urlT(params.id)
    let dinMemorie = false
    if (primaCitire) {
      primaCitire = false
      const p = _dinCache(uP)
      if (p !== undefined) {
        project = p
        const t = _dinCache(uT)
        if (t !== undefined) tasks = Array.isArray(t) ? t : t.tasks || []
        loading = false
        dinMemorie = true
      }
    } else {
      _uita(uP)   // prefix: acopera si `/tasks` de sub el
    }
    if (!dinMemorie) loading = true
    try {
      // IN PARALEL, nu unul dupa altul. Erau doua dus-intors inlantuite pentru
      // doua cereri care nu depind una de alta, deci pagina astepta suma lor.
      const [p, t] = await Promise.all([
        loadProjectDetail(params.id),
        loadProjectTasks(params.id).catch(() => []),
      ])
      project = p
      tasks = Array.isArray(t) ? t : t.tasks || []
    } catch (err) {
      // Cu ecranul deja plin din cache, o improspatare picata nu-l inlocuieste
      // cu o eroare: ai in fata date bune, doar putin vechi.
      if (!dinMemorie) error = err.message
    } finally { loading = false }
  }

  async function reloadTasks() {
    const t = await loadProjectTasks(params.id).catch(() => [])
    tasks = Array.isArray(t) ? t : t.tasks || []
  }

  async function toggleTaskStatus(task) {
    const prev = task.status
    const next = prev === 'done' ? 'to_do' : 'done'
    tasks = tasks.map(t => t.id === task.id ? { ...t, status: next } : t)
    let res
    try {
      res = await updateTask(task.id, { status: next })
    } catch (e) {
      tasks = tasks.map(t => t.id === task.id ? { ...t, status: prev } : t)
      toast(`Eroare: ${e.message}`, 'error')
      return
    }
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
    // Local, nu UTC — vezi nota din pages/Tasks.svelte: „Azi" scria ieri.
    await aplicaTermen(t, addDays(todayISO(), zile))
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

  // `zile` vine de la chipurile de sub camp; `newTaskData` de la „Alege data".
  // `addDays(todayISO(), n)`, NU `new Date().toISOString()` — a doua converteste
  // in UTC si „Azi" ar scrie ieri in fusul Romaniei.
  async function handleCreateTask(zile) {
    if (!newTaskTitle.trim() || creatingTask) return
    creatingTask = true
    let termen = newTaskData
    if (zile !== undefined && zile !== null) termen = addDays(todayISO(), zile)
    try {
      await createTask(params.id, {
        titlu: newTaskTitle.trim(), status: 'to_do',
        data_scadenta: termen || undefined,
      })
      newTaskTitle = ''
      newTaskData = ''
      await reloadTasks()
    } catch (e) {
      toast(`Eroare la creare: ${e.message}`, 'error')
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
    noteSalveaza = async (text) => {
      await updateTask(t.id, { descriere: text })
      await reloadTasks()
    }
    showNoteModal = true
  }

  async function handleDeleteProject() {
    try {
      await deleteProject(params.id)
      toast('Proiect șters', 'success')
      navigate('/projects')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  async function doDeleteTask() {
    if (!taskDeleteId) return
    try {
      await deleteTask(taskDeleteId)
      taskDeleteId = null
      await reloadTasks()
      toast('Task șters', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  // ===== FOAIA RANDULUI DE PE TELEFON =====
  //
  // Aceeasi foaie ca in Planificator (`components/FoaieTask.svelte`): glisarea la
  // stanga o deschide pe „Planifică", apasarea lunga pe actiuni.
  //
  // Glisarea la stanga deschidea pana acum FORMULARUL DE EDITARE — cu Titlu,
  // Descriere, Categorie si Termen — desi pista de sub deget scria „Planifică".
  // Comentariul de la gest o si recunostea („aici nu exista foaie, deci deschide
  // modalul de editare, care are campul Termen"). Acum exista foaie. Formularul
  // rămâne, dar la „Deschide" — adica exact acolo unde ceri mai mult decat o zi.
  let foaieTask = $state(null)
  let foaieMod = $state('actiuni')
  let foaieDeschisa = $state(false)
  let showAdauga = $state(false)
  let taskEditat = $state(null)

  function deschideFoaia(t, mod) {
    foaieTask = t
    foaieMod = mod
    foaieDeschisa = true
  }

  // Stergere reversibila, aceeasi mecanica ca la subtaskuri mai jos: randul pleaca
  // din lista pe loc, scrierea pe server abia la expirarea toastului.
  function stergeTaskDinLista(t) {
    const idx = tasks.findIndex(x => x.id === t.id)
    if (idx === -1) return
    const scos = tasks[idx]
    tasks = tasks.filter(x => x.id !== t.id)
    toastUndo('Task șters', {
      onUndo: () => {
        const cur = [...tasks]
        cur.splice(Math.min(idx, cur.length), 0, scos)
        tasks = cur
      },
      onCommit: async () => {
        try { await deleteTask(t.id); await reloadTasks() }
        catch (e) { toast(`Eroare: ${e.message}`, 'error'); await reloadTasks() }
      },
    })
  }


  // Subtask functions
  //
  // INTAI DATELE, APOI DESCHIDEREA — la fel ca in /tasks. Invers, panoul se
  // randa cu „Se încarcă…", `slide` masura acea inaltime scurta si animeaza
  // spre ea, iar sectiunea de subtaskuri sosita dupa aceea aparea taiata peste
  // un panou deja terminat de animat.
  async function toggleTaskExpand(taskId) {
    if (expandedTask === taskId) {
      expandedTask = null
      return
    }
    // Aici statea `loadAtt(taskId)` — fosila de la atasamente (sterse in v28).
    // Functia NU mai exista, deci apelul arunca ReferenceError in mijlocul
    // functiei async: extinderea se vedea (era setata mai sus), dar incarcarea
    // subtaskurilor de sub apel NU se mai executa niciodata. Chipul spunea
    // „0/1", lista era mereu goala, si nicio eroare nu ajungea in consola —
    // respingerea promisiunii ramanea neascultata.
    await incarcaSubtaskuri(taskId)
    expandedTask = taskId
  }

  // Cererile in zbor: cu preincarcarea pe hover, plimbatul mouse-ului peste
  // lista ar trimite cate o cerere de fiecare data cand intri pe acelasi rand,
  // iar in productie limita e 60 pe minut per IP (vezi app.py). Asa, un task
  // cere O SINGURA data.
  const inZbor = new Map()

  function incarcaSubtaskuri(taskId) {
    if (subtasksCache[taskId]) return Promise.resolve()
    if (inZbor.has(taskId)) return inZbor.get(taskId)
    const p = (async () => {
      try {
        const subs = await loadSubtasks(taskId)
        subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
      } catch (e) {
        subtasksCache = { ...subtasksCache, [taskId]: [] }
        toast(`Subtaskuri: ${e.message}`, 'error')
      } finally {
        inZbor.delete(taskId)
      }
    })()
    inZbor.set(taskId, p)
    return p
  }

  // Pe desktop mouse-ul trece pe rand inainte sa apese, deci asteptarea de mai
  // sus se plateste de obicei deloc: la clic subtaskurile sunt deja in cache.
  function preincarca(taskId) {
    if (!ecran.telefon) incarcaSubtaskuri(taskId)
  }

  async function toggleSubtaskDone(sub) {
    const next = sub.done ? 0 : 1
    const taskId = expandedTask
    subtasksCache = { ...subtasksCache, [taskId]: subtasksCache[taskId].map(s => s.id === sub.id ? { ...s, done: next } : s) }
    try {
      await updateSubtask(sub.id, { done: next })
    } catch (e) {
      subtasksCache = { ...subtasksCache, [taskId]: subtasksCache[taskId].map(s => s.id === sub.id ? { ...s, done: sub.done } : s) }
      toast(`Eroare: ${e.message}`, 'error')
    }
    await reloadTasks()
  }

  async function addSubtask(taskId) {
    if (!newSubtaskTitle.trim()) return
    try {
      await createSubtask(taskId, newSubtaskTitle.trim())
      // Compozitorul RAMANE deschis, gol si focalizat: subtaskurile se scriu in
      // rafala, nu unul singur. Aceeasi regula ca in /tasks.
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

  // isOverdue/isToday vin din formatters.js — aceeasi axa si aceleasi
  // praguri ca dueRing(), o singura definitie pentru toate listele.

  // Observatii tehnice, Constatari, Actiuni si rezultat: acelasi shell ca nota
  // unui task (`EditorLung`), deci si aceeasi regula — inchiderea COMITE, cu drum
  // inapoi prin toast. Inainte campurile de proiect aveau „Anulează" si „Salvează",
  // dar X / fundal / Escape aruncau in tacere tot ce scrisesei; nota, in aceeasi
  // pagina, salva. Acelasi gest, doua intelesuri opuse.
  //
  // Functia de scriere se construieste AICI, cu campul inchis in ea: „Anulează"
  // din toast ruleaza pana la 4 secunde mai tarziu, cand `editField` poate fi deja
  // alt camp.
  function openFieldEdit(field, label) {
    editValue = project[field] || ''
    editLabel = label
    editSalveaza = async (text) => {
      await updateProject(params.id, { [field]: text })
      project = { ...project, [field]: text }
    }
    showFieldEdit = true
  }

  function improspateazaZiua() {
    const nou = todayISO()
    if (nou !== azi) azi = nou
  }

  onMount(() => {
    load()
    const onVis = () => { if (document.visibilityState === 'visible') improspateazaZiua() }
    document.addEventListener('visibilitychange', onVis)
    const laMiezulNoptii = () => {
      const acum = new Date()
      const maine = new Date(acum.getFullYear(), acum.getMonth(), acum.getDate() + 1)
      return setTimeout(() => { improspateazaZiua(); idTimer = laMiezulNoptii() }, maine - acum + 500)
    }
    let idTimer = laMiezulNoptii()
    return () => { clearTimeout(idTimer); document.removeEventListener('visibilitychange', onVis) }
  })

  // TABURILE SE INCALZESC LA DESCHIDEREA PAGINII, nu la hover.
  //
  // Hoverul e prea tarziu, si se poate masura: intre `pointerenter` si click
  // trec ~150ms pe desktop si ~100 pe telefon, adica exact cat un dus-intors
  // prin tunel — deci prima vizita pe „Perioade" sau pe „Wiki" tot trecea
  // printr-un cadru de schelet si trei stari vizuale. Preincarcarea de la hover
  // ramane (nu strica, si acopera cazul in care cererea de aici a picat), dar
  // ea singura nu ajungea.
  //
  // Pe rand liber, nu imediat: pagina are deja doua cereri proprii la montare
  // (proiectul si taskurile lui), iar taburile n-au voie sa concureze cu ele.
  // Pana apesi un tab au trecut oricum secunde.
  $effect(() => {
    const cere = () => { pregatesteTab('perioade'); pregatesteTab('wiki') }
    if (typeof requestIdleCallback === 'function') {
      const id = requestIdleCallback(cere, { timeout: 2000 })
      return () => cancelIdleCallback(id)
    }
    const t = setTimeout(cere, 900)
    return () => clearTimeout(t)
  })

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

  // GRUPAREA DUPA TERMEN, ca in /tasks, „Astăzi" si Planificator. Era singura
  // lista de taskuri din aplicatie care NU grupa: lista vine `ORDER BY created_at
  // DESC` de la server si ramanea asa, iar in proiect nu exista nici reordonare
  // manuala — deci ordinea nu spunea nimic si un restant putea sta al patrulea.
  // `grupeazaDupaTermen` e deja generica; se itereaza `ORDINE_GRUPE` (chei
  // CONSTANTE — vezi comentariul din grupare.js despre tranzitiile de iesire).
  const grupe = $derived(grupeazaDupaTermen(activeTasks))

  // Rail: progres taskuri + urmatoarea perioada. Deadline-ul a plecat in v30 —
  // Ion nu se lua dupa el niciodata; ce stie cu adevarat sunt perioadele.
  const taskPct = $derived(tasks.length ? Math.round((tasksDone / tasks.length) * 100) : 0)
  const FAZA_LABEL = { pregatire: 'Pregătire', implementare: 'Implementare' }
  const urmDays = $derived.by(() => {
    if (!project?.urmatoarea) return null
    return diffDays(azi, String(project.urmatoarea).slice(0, 10))
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
    return diffDays(String(project.data_finalizare).slice(0, 10), azi)
  })
  function finalLabel(d) {
    if (d === null) return ''
    if (d <= 0) return 'astăzi'
    if (d === 1) return 'ieri'
    if (d < 30) return `acum ${d} zile`
    return ''
  }
</script>

<!-- `ruta-in`: ecranul SOSESTE, nu apare intre doua cadre. Aveau
     animatia doar Calendar, Planificator si Taskuri, deci jumatate din
     taburi se deschideau taiat si jumatate lin — raportat de Ion („nu
     toate taburile au animatii de deschidere"). Regula traieste in
     global.css, deci aici nu se adauga niciun CSS. -->
<div class="page ruta-in">
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
          <!-- „Edit" era singurul cuvant englezesc din interfata, si statea la doi
               centimetri de „Editează" de pe randurile de task de dedesubt. PDF si
               MD raman: sunt NUMELE unor formate, nu verbe traductibile.
               Pubela era singurul buton din toata aplicatia fara nume accesibil —
               fara text, fara `title`, fara `aria-label` — si e chiar cel care
               sterge proiectul cu tot cu taskurile lui. -->
          <Button variant="secondary" size="sm" onclick={() => showEditModal = true}><SolidIcon name="pencil" size={14} /> Editează</Button>
          <Button variant="secondary" size="sm" onclick={exportPdf}><FileDown size={14} /> PDF</Button>
          <Button variant="secondary" size="sm" onclick={exportMd}><SolidIcon name="file" size={14} /> MD</Button>
          <Button variant="ghost" size="sm" title="Șterge proiectul" aria-label="Șterge proiectul" onclick={ceriStergereaProiectului}><SolidIcon name="trash" size={14} /></Button>
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

      <!-- PE TELEFON, RAILUL COBOARA SUB CONTINUT (vezi `.rail { order: 0 }`).
           Cu `order: -1` deschideai un proiect si primeai butonul „Proiecte",
           antetul cu patru butoane, meta, celulele de progres, sectiunile „coala
           de document" si bara de taburi — abia apoi taskurile, sub doua ecrane.
           Deschizi un proiect ca sa vezi ce ai de facut, nu cat ai facut.
           Sus ramane o SINGURA linie: procentul si urmatoarea perioada. -->
      <div class="rail-mini" aria-hidden="true">
        <span class="rm-pct">{taskPct}%</span>
        <div class="rm-bar"><i style="width: {taskPct}%"></i></div>
        {#if project.status === 'finalizat'}
          <span class="rm-cand">{project.data_finalizare ? `Finalizat · ${formatDate(project.data_finalizare)}` : 'Finalizat'}</span>
        {:else if project.urmatoarea}
          <span class="rm-cand" class:urgent={urmDays !== null && urmDays <= 2}>{formatDate(project.urmatoarea)} · {urmLabel(urmDays)}</span>
        {:else}
          <span class="rm-cand rm-gol">Neplanificat</span>
        {/if}
      </div>

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

    <div class="tabs" bind:this={tabsEl}>
      <!-- Sublinierea e UN obiect care se muta, nu o bordura care se aprinde in
           alta parte — aceeasi gramatica cu pastila din doc si cursorul de sfera.
           Latimea difera de la un tab la altul, deci se scaleaza pe X in loc sa
           se anime `width`: scalarea se compune pe GPU, latimea cere layout. -->
      <span class="tab-linie" class:gata={linie.gata} class:asezata={linieAsezata}
            style="--lx:{linie.x}px; --lw:{linie.w / 100}" aria-hidden="true"></span>
      {#each tabs as tab}
        <button class="tab" class:active={activeTab === tab.key}
                data-tab={tab.key}
                onclick={() => alegeTab(tab.key)}
                onpointerenter={() => pregatesteTab(tab.key)}
                onpointerdown={() => pregatesteTab(tab.key)}>
          <tab.icon size={16} />
          {tab.label}
        </button>
      {/each}
    </div>

    <div class="tab-content">
      {#key activeTab}
      <!-- 220 (element), nu 120 (vopsea): schimbarea tabului aduce CONTINUT
           nou, e o sosire — aceeasi treapta ca lista si ca foaia de ruta. -->
      <div class="tab-pane" in:alunecare={{ sens: tabSens }}>
      {#if activeTab === 'tasks'}
        <!-- „N/M finalizate" a plecat: railul din dreapta arata bara de progres SI
             cifra mare, in acelasi ecran, la 300px distanta. Aceeasi informatie,
             o data ca text mic si o data ca grafic. -->
        <!-- CHIPURILE DE ZI, ca in /tasks. Fara ele, Enter si gata insemna ca
             taskul cade in „fara termen" — iar consecinta nu e estetica: un task
             fara termen NU apare in „Astăzi", nu apare in Planificator si nu
             ajunge in Google Calendar. Taskurile de proiect se nasteau invizibile. -->
        <!-- LINIA RAPIDA A RAMAS DOAR PE DESKTOP. Pe telefon era a treia gramatica
             de adaugare din aplicatie (dupa cautarea din „Astăzi" si formularul din
             /tasks), si singura care cerea sa alegi ziua din CHIPURI. Acolo adaugarea
             vine acum din butonul plutitor, care deschide aceeasi foaie ca celelalte
             doua ecrane, cu proiectul deja pus. Pe desktop linia rămâne: acolo n-ai
             buton plutitor, ai un camp la vedere, si e mai rapid decat o foaie. -->
        <form class="quick-add" onsubmit={(e) => { e.preventDefault(); handleCreateTask() }}>
          <div class="qa-rand">
            <input type="text" placeholder="Task rapid... Enter pentru a adăuga" bind:value={newTaskTitle} disabled={creatingTask} />
            <button type="submit" class="quick-add-btn" disabled={!newTaskTitle.trim() || creatingTask} title="Adaugă task"><Plus size={16} /></button>
          </div>
          {#if newTaskTitle.trim()}
            <div class="qa-cand" transition:slide={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
              <button type="button" class="qa-chip" onclick={() => handleCreateTask(0)}>Azi</button>
              <button type="button" class="qa-chip" onclick={() => handleCreateTask(1)}>Mâine</button>
              <span class="qa-dp">
                <DatePicker bind:value={newTaskData} placeholder="Alege data" onchange={(v) => { newTaskData = v; if (v) handleCreateTask() }} />
              </span>
              <span class="qa-hint">Enter = fără termen</span>
            </div>
          {/if}
        </form>
        {#if tasks.length === 0}<p class="empty">Niciun task.</p>
        {:else}
          <!-- UN SINGUR RAND, doua liste. „Finalizate" avea un rand PROPRIU, cu
               bifa si titlu si atat: taskul isi pierdea jumatate din identitate
               (termen, subtaskuri, nota) exact cand vrei sa verifici CE ai facut
               si cand. Acum e acelasi rand, doar stins si cu titlul taiat —
               `.trow.done` face deja asta. -->
          <!-- Snippetul tine DOAR interiorul randului: `animate:` cere ca elementul
               sa fie unicul copil al unui `{#each}` cheiat, iar Svelte nu poate
               verifica asta printr-un `{@render}`. Deci invelisul (cu `--ring` si
               tranzitiile) sta in fiecare lista, continutul o singura data. -->
          {#snippet randTask(t)}
            {@const gata = t.status === 'done' || t.status === 'finalizat'}
                <div class="trow" class:done={gata} use:focusOnLand={focusKey('task', t.id)}
                     use:glisare={{ activ: ecran.telefon, onBifa: gata ? null : () => toggleTaskStatus(t), onAmana: () => deschideFoaia(t, 'plan') }}
                     use:apasareLunga={{ activ: ecran.telefon, actiune: () => deschideFoaia(t, 'actiuni') }}>
                  <!-- UN GEST = UN VERB, IN AMBELE SENSURI — exact ca in /tasks.
                       Doua liste de taskuri cu acelasi rand nu au voie sa raspunda
                       diferit la acelasi gest; aici era acelasi panou de patru
                       actiuni × 58px = 232px din 390, care acoperea taskul pe care
                       actionai si punea „Șterge" exact unde ajunge o glisare rapida.
                       Stanga = „Planifică", dreapta = „Făcut". Stanga deschidea
                       FORMULARUL de editare, fiindca „aici nu exista foaie" — acum
                       exista (`components/FoaieTask.svelte`), deci gestul da exact
                       ce scrie pe pista: zilele. Formularul a ramas la „Deschide",
                       in foaia de la apasare lunga. -->

                  <div class="gl-pista" aria-hidden="true"><span class="gl-ico"><Check size={17} strokeWidth={3} /></span><span class="gl-et">Făcut</span></div>
                  <div class="gl-pista-s" aria-hidden="true"><span class="gl-et-s">Planifică</span><span class="gl-ico-s"><CalendarDays size={17} strokeWidth={2.4} /></span></div>
                  <div class="gl-fata">
                  <button class="check" onclick={() => toggleTaskStatus(t)}
                          title={gata ? 'Redeschide taskul' : 'Bifează taskul'}>
                    {#if gata}<CheckCircle2 size={16} />{:else}<div class="check-empty"></div>{/if}
                  </button>
                  <!-- ACELASI RAND CA IN /tasks si pe boardul „Astăzi": titlul,
                       apoi cati pasi (doar daca are), actiunile cu text la hover,
                       si termenul pironit intr-o coloana de 46px. -->
                  <button class="tmain" onclick={() => toggleTaskExpand(t.id)}>
                    <span class="ttitle">{t.titlu}</span>
                    <!-- CONTORUL DE PASI, la fel ca in /tasks si pe „Astăzi"
                         (cerinta Ion, 2026-08-15). Randul purta pana acum doua
                         lucruri — ce e de facut si cand — iar progresul se citea
                         doar din randul desfacut; interdictia s-a ridicat, dar tot
                         intr-un singur fel pe toate suprafetele: aceeasi
                         componenta, inel plus cifre, fara nicio culoare. -->
                    <ContorPasi {...pasi(t)} />
                  </button>
                  <div class="task-actions">
                    <span class="ta-dp" title="Planifică — alege ziua">
                      <DatePicker value={t.data_scadenta} eticheta="Planifică" onchange={(v) => setTermenTaskData(t, v)} />
                    </span>
                    <button class="ta-chip" onclick={() => openTaskEditModal(t)}><SolidIcon name="pencil" size={13} />Editează</button>
                    <button class="ta-chip ta-sterge" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }}><SolidIcon name="trash" size={13} />Șterge</button>
                  </div>
                  <span class="ttermen" class:sev={isOverdue(t.data_scadenta)}
                        class:acum={isToday(t.data_scadenta)}>{termenScurtTask(t)}</span>
                  </div>
                </div>
                {#if expandedTask === t.id}
                  {@const subs = subtasksCache[t.id] || []}
                  {@const doneCount = subs.filter(s => s.done).length}
                  <div class="subtask-body" transition:desfacere={{ duration: motionDuration(DUR_BASE) }}>
                    <!-- CONTINUTUL INAINTEA BUTOANELOR (ca in /tasks): nota, apoi
                         pasii. Butonul de editare a notei si chipul „Descriere" —
                         doua haine pentru aceeasi actiune, dupa cum era completata
                         nota — au fost inlocuite de UN singur link, jos. -->
                    {#if t.descriere}
                      <div class="td-nota"><RichText value={t.descriere} collapsible maxHeight={200} noToggle /></div>
                    {/if}

                    <div class="sub-section">
                      <!-- ACELASI ANTET CA IN /tasks: titlu + bara + „1/4" pe un
                           singur rand. Inainte numarul aparea de DOUA ori (o data
                           in cap, o data langa bara de pe randul urmator) — aceeasi
                           informatie, spusa de doua ori la 20px distanta. -->
                      <div class="sub-head">
                        <span class="sub-cap">Subtaskuri</span>
                        {#if subs.length}
                          <div class="sub-bara" role="img"
                               aria-label="{doneCount} din {subs.length} subtaskuri făcute">
                            <span style="width: {(doneCount / subs.length) * 100}%"></span>
                          </div>
                          <span class="sub-num">{doneCount}/{subs.length}</span>
                        {/if}
                      </div>
                      <!-- Fara stare de asteptare: panoul se randeaza DOAR cu
                           subtaskurile deja in cache (vezi `toggleTaskExpand`). -->
                      {#each subs as sub (sub.id)}
                        <!-- ACELASI RAND DE SUBTASK CA IN /tasks, si pe telefon
                             acelasi gest: stanga = „Șterge", cu „Anulează" in
                             toast. Pubela permanenta de 44px de pe fiecare rand
                             a plecat — era singura actiune distructiva din panou
                             si statea fix unde se odihneste degetul mare. -->
                        <div class="sub-row" class:sub-done={sub.done} class:gl-sub={ecran.telefon}
                             use:glisare={{ activ: ecran.telefon, onAmana: () => removeSubtask(sub.id, t.id) }}>
                          <div class="gl-pista-s" aria-hidden="true"><span class="gl-et-s">Șterge</span><span class="gl-ico-s"><SolidIcon name="trash" size={15} /></span></div>
                          <div class="gl-fata">
                          <!-- Bifa ROTUNDA, ca subtaskurile din /tasks si din
                               foaie: acelasi obiect, acelasi semn peste tot.
                               Patratul amber (cbx) e al selectiilor de lista
                               (batch pe /projects), nu al lui „făcut". -->
                          <button class="check" onclick={() => toggleSubtaskDone(sub)} title={sub.done ? 'Redeschide subtaskul' : 'Bifează subtaskul'}>
                            {#if sub.done}<CheckCircle2 size={16} />{:else}<div class="check-empty small"></div>{/if}
                          </button>
                          <!-- Zona mare face lucrul cel mai des: bifeaza. Aici nu
                               exista redenumire, deci nici apasare lunga. -->
                          <button class="sub-title" onclick={() => toggleSubtaskDone(sub)}>{sub.titlu}</button>
                          <button class="sub-del" onclick={() => removeSubtask(sub.id, t.id)} aria-label="Șterge subtaskul"><SolidIcon name="trash" size={12} /></button>
                          </div>
                        </div>
                      {/each}
                      <!-- Campul se deschide la atingere, ca in /tasks: pana atunci
                           randul e o INVITATIE, nu un formular care sta gol pe ecran. -->
                      {#if adaugSubLa === t.id}
                        <div class="sub-add">
                          <input type="text" placeholder="Ce pas urmează?" bind:value={newSubtaskTitle} use:focalizeaza
                                 onkeydown={(e) => {
                                   if (e.key === 'Enter') addSubtask(t.id)
                                   else if (e.key === 'Escape') { e.stopPropagation(); adaugSubLa = ''; newSubtaskTitle = '' }
                                 }} />
                          <button class="sub-add-btn" disabled={!newSubtaskTitle.trim()} onclick={() => addSubtask(t.id)}><Plus size={16} /></button>
                        </div>
                      {:else}
                        <button class="sub-nou" onclick={() => { adaugSubLa = t.id; newSubtaskTitle = '' }}>
                          <span class="sub-nou-p"><Plus size={14} /></span> Adaugă subtask
                        </button>
                      {/if}
                    </div>

                    <!-- Actiunile rare, sub o linie — ca in /tasks. -->
                    <div class="td-jos">
                      <button class="td-link" class:areNota={!!t.descriere} onclick={() => openNoteModal(t)}>
                        <Text size={12} strokeWidth={2} /> {t.descriere ? 'Editează nota' : 'Adaugă notă'}
                      </button>
                      <span class="td-link td-dp">
                        <DatePicker value={t.data_scadenta} placeholder="Schimbă termenul" onchange={(v) => setTermenTaskData(t, v)} />
                      </span>
                    </div>
                  </div>
                {/if}
          {/snippet}

          <div class="task-list">
            <!-- TOATE grupele, inclusiv cele goale, si chei CONSTANTE: un `{#if}`
                 care se stinge cand grupa ramane fara randuri ar distruge blocul
                 in care tocmai pleaca ultimul rand, iar Svelte nu i-ar mai juca
                 iesirea. Capul gol se ascunde; un cap n-are nevoie de tranzitie. -->
            {#each ORDINE_GRUPE as gid (gid)}
              {#if grupe[gid].titlu && grupe[gid].items.length}
                <!-- PE TELEFON, NUMARUL DOAR LA „RESTANTE" — ca in /tasks, unde
                     regula scrisa e ca un numar apare doar daca DECIDE o actiune.
                     Aici aparea pe toate grupele, deci „Mai tarziu 3" cerea o
                     citire pentru un fapt care nu cere nimic. Pe desktop ramane
                     cum era: acolo lista sta langa restul paginii, nu singura pe
                     ecran, si numarul e reperul care spune cat de lunga e grupa. -->
                <div class="grup-cap ton-{grupe[gid].ton}"><span class="grup-t">{grupe[gid].titlu}</span>{#if !ecran.telefon || grupe[gid].ton === 'danger'}<span class="grup-n">{grupe[gid].items.length}</span>{/if}</div>
              {/if}
              {#each grupe[gid].items as t (t.id)}
                <div class="trow-wrap" style="--ring: {dueRing(t.data_scadenta)}"
                     animate:flip={{ duration: motionDuration(DUR_BASE) }}
                     onpointerenter={() => preincarca(t.id)}
                     in:sosire|local out:plecare>
                  {@render randTask(t)}
                </div>
              {/each}
            {/each}

            {#if doneTasks.length > 0}
              <button class="done-sep" onclick={() => showDoneTasks = !showDoneTasks}>
                {#if showDoneTasks}<ChevronDown size={14} />{:else}<ChevronRight size={14} />{/if}
                <span>Finalizate</span><span class="grup-n">{doneTasks.length}</span>
              </button>
              {#if showDoneTasks}
                <div class="done-list" transition:slide={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
                {#each doneTasks as t (t.id)}
                  <div class="trow-wrap" style="--ring: {dueRing(t.data_scadenta)}"
                       animate:flip={{ duration: motionDuration(DUR_BASE) }}
                       onpointerenter={() => preincarca(t.id)}
                       in:sosire|local out:plecare>
                    {@render randTask(t)}
                  </div>
                {/each}
                </div>
              {/if}
            {/if}
          </div>
        {/if}

      {:else if activeTab === 'perioade'}
        <!-- GANTTUL DIN PAGINA DE PROIECT A PLECAT (cerut de Ion, 2026-08-15):
             „vom sterge gantt in interiorul proiectului, trebuie sa ramana doar
             optiunea de adaugare perioade de implementare."
             Perioadele sunt oricum unitatea reala de planificare — Ganttul era
             doar o a doua vedere peste ele, iar planificarea pe zile traieste in
             Calendar si in Planificator, unde o si editezi.

             EXPORTURILE AU PLECAT SI ELE (Ion, in aceeasi trecere: „sterge si
             alea"). Erau butoane INAUNTRUL Ganttului si tipareau exact vederea
             lui in timp; fara Gantt n-aveau ce reprezenta. Odata cu ele au plecat
             de pe server si cele trei rute care le serveau — `/gantt`,
             `/gantt.pdf` si `/gantt.xlsx` — plus cele 705 linii de asamblare a
             lor din `blueprints/tasks.py`, care n-ar mai fi avut niciun cititor.
             Perioadele raman singurul lucru din tab, adica exact ce s-a cerut. -->
        <ImplPeriods projectId={params.id} />

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
      <section class="rcell cell-in" style="--celula: 0">
        <div class="cell-label"><span class="ico ico-accent"><ListTodo size={12} /></span>Progres taskuri</div>
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
      <section class="rcell cell-in" style="--celula: 1">
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
        <section class="rcell cell-in" style="--celula: 2">
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

<!-- BUTONUL POARTA VERBUL SI OBIECTUL, INTREBAREA SPUNE CE DISPARE.
     „Șterge proiect" / „Șterge definitiv" erau o eticheta si un adverb: niciunul
     nu spunea CE pleaca. Aici e cea mai ireversibila actiune din aplicatie, si e
     citita in doua secunde. Vezi `ConfirmDialog`. -->
<ConfirmDialog bind:open={showDeleteConfirm}
               title={project ? `Ștergi proiectul „${project.nume}”?` : 'Ștergi proiectul?'}
               message={ceDispare}
               confirmLabel="Șterge proiectul" onconfirm={handleDeleteProject} />
<ConfirmDialog bind:open={showTaskDelete}
               title={taskDeSters ? `Ștergi „${taskDeSters.titlu}”?` : 'Ștergi taskul?'}
               message={subDeSters?.length
                 ? `Dispar odată cu el ${subDeSters.length} ${subDeSters.length === 1 ? 'subtask' : 'subtaskuri'}. Nu se poate anula.`
                 : 'Nu se poate anula.'}
               confirmLabel="Șterge taskul" onconfirm={doDeleteTask} />

<EditorLung bind:open={showFieldEdit} titlu={editLabel} valoare={editValue} salveaza={editSalveaza} />

<!-- `panou`, nu `md`: acelasi obiect (un task) trebuie sa se deschida in
     aceeasi gazda ca in /tasks. O caseta centrata iti pune editorul peste
     lista din care ai venit; panoul lateral o lasa la vedere. -->
<!-- BUTONUL MARE CU PLUS, ca in /tasks — aceeasi geometrie si aceeasi poziţie
     (58px, rază 20, peste dock, la dreapta), fiindca e acelasi obiect: singura cale
     de adaugare de pe telefon. Doar in tabul Taskuri: in celelalte taburi n-ar avea
     ce sa adauge. Proiectul intra precompletat din pagina curenta. -->
{#if ecran.telefon && activeTab === 'tasks' && project}
  <button class="fab" onclick={() => { taskEditat = null; showAdauga = true }} aria-label="Task nou în proiect">
    <Plus size={25} strokeWidth={1.5} />
  </button>
{/if}

<!-- ACEEASI foaie de adaugare ca in /tasks si pe „Astăzi". -->
<FoaieAdauga bind:open={showAdauga} proiect={project} onSchimbare={reloadTasks}
             editeaza={taskEditat}
             onSalveaza={async (d) => { await updateTask(taskEditat.id, d) }} />

<!-- Foaia randului de pe telefon. „Deschide" e formularul de editare: aici el E
     detaliul taskului, nu exista alta pagina in care sa-l duci. -->
<FoaieTask bind:open={foaieDeschisa} task={foaieTask} mod={foaieMod}
           onZi={(v) => setTermenTaskData(foaieTask, v)}
           onMaine={() => setTermenTask(foaieTask, 1)}
           onEditeaza={() => { taskEditat = foaieTask; showAdauga = true }}
           onSterge={() => stergeTaskDinLista(foaieTask)} />

<Modal bind:open={showTaskEditModal} title="Editează Task" size="panou">
  <form class="task-form" onsubmit={(e) => { e.preventDefault(); handleTaskEdit() }}>
    <Input label="Titlu" bind:value={taskFormTitle} placeholder="Titlu task" />
    <!-- Componentele librariei, ca in modalul din /tasks — acelasi formular,
         acelasi desen. Aici mai statea si un `mf-field` GOL: perechea campului
         de prioritate, plecat in v34, care impingea Termenul in dreapta ca sa
         faca loc unui nimic. -->
    <Textarea label="Descriere" bind:value={taskFormDesc} placeholder="Detalii (opțional)" rows={3} />
    <DatePicker label="Termen" bind:value={taskFormDeadline} />
    <Select label="Recurență" bind:value={taskFormRecurenta} options={[{ value: '', label: 'Fără' }, { value: 'zilnic', label: 'Zilnic' }, { value: 'saptamanal', label: 'Săptămânal' }, { value: 'lunar', label: 'Lunar' }]} />
  </form>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showTaskEditModal = false}>Anulează</Button>
      <Button loading={taskFormSaving} disabled={!taskFormTitle.trim()} onclick={handleTaskEdit}>Salvează</Button>
    </div>
  {/snippet}
</Modal>

<!-- Nota de task: ACELASI shell ca observatiile de mai sus — se schimba doar
     titlul (taskul) si bara de unelte (`nota` = sapte, nu treisprezece). -->
<EditorLung bind:open={showNoteModal} titlu={noteTask ? noteTask.titlu : 'Notiță'}
            valoare={noteDraft} tools="nota" salveaza={noteSalveaza}
            placeholder="Scrie notițe pentru acest task…" />

<style>
  .page { padding: var(--space-lg); }
  .back { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-small); color: var(--text-dim); margin-bottom: var(--space-md); cursor: pointer; }
  .back:hover { color: var(--accent); }

  .project-header { margin-bottom: var(--space-lg); }
  .header-top { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-md); }
  .title-area { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }
  .title-area h1 { font-size: var(--font-title); font-weight: var(--fw-semibold); color: var(--text); }
  .header-actions { display: flex; gap: var(--space-xs); flex-wrap: wrap; flex-shrink: 0; }
  .tip { font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; padding: 2px 8px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-secondary); }
  .tip.pif { background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .tip.service { background: var(--accent-subtle); color: var(--accent-deep); }
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
  .rail { display: flex; flex-direction: column; gap: 12px; position: sticky; top: calc(var(--header-height) + 16px); max-height: calc(100vh - var(--header-height) - var(--space-lg)); overflow-y: auto; }
  .rcell { background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); padding: var(--space-md) var(--space-20); }
  .rprog { display: flex; align-items: baseline; gap: 10px; margin-top: 10px; }
  .rprog-num { font-family: var(--font-mono); font-size: var(--font-title); font-weight: var(--fw-semibold); color: var(--text); line-height: 1; font-variant-numeric: tabular-nums; }
  .rbar { flex: 1; height: 6px; border-radius: var(--radius-full); background: var(--bg-panel); overflow: hidden; }
  .rbar i { display: block; height: 100%; background: var(--accent); border-radius: var(--radius-full); transition: width var(--dur-base) var(--ease); }
  .rdate { font-family: var(--font-mono); font-size: var(--font-h3); font-weight: var(--fw-semibold); color: var(--text); margin-top: 10px; font-variant-numeric: tabular-nums; }
  .rdate.urgent { color: var(--danger); }
  .rsub { font-size: var(--font-small); color: var(--text-dim); margin-top: 6px; }
  .rsub-empty { font-style: italic; margin-top: 10px; }

  /* Field sections in coloana stanga (observatii, service) */
  /* "Coala de document" (V1): gradient cald, umbra, antet cu chip + meta */
  /* HAINA NEUTRA PE TOATE TREI SECTIUNILE. Aveau un degrade dinspre accent —
     deci rubrica isi lua o culoare, desi culoarea e rezervata STARII. Un fond
     plat le face egale, cum au fost desenate. */
  .field-section { margin-bottom: var(--space-sm); background: var(--bg-surface); border-radius: var(--radius-md); overflow: clip; box-shadow: var(--shadow-sm); transition: box-shadow var(--dur-fast) var(--ease); cursor: pointer; text-align: left; }
  /* `:hover { border-color }` a plecat: sectiunea n-are chenar din B2, deci
     declaratia nu putea colora nimic. Daca hoverul se vrea inapoi, e pe umbra
     (`--shadow-md`) — tranzitia lui e deja scrisa mai sus. */
  .field-section:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .field-header { display: flex; align-items: center; gap: var(--space-sm); padding: 11px var(--space-md); font-size: var(--font-small); color: var(--text-secondary); border-bottom: 1px dashed var(--border); }
  /* Aceeasi familie cu `.ico-*` din global.css, deci aceeasi regula: cerneala pe
     tenta ia varianta adanca. Erau doua patratele identice ca forma, unul pe
     `--accent` si unul pe `--accent-on-subtle`, in aceeasi pagina. */
  .f-ico { width: 24px; height: 24px; border-radius: 8px; background: var(--accent-subtle); color: var(--accent-on-subtle); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .f-ico.f-red { background: var(--danger-subtle); color: var(--danger); }
  .f-ico.f-green { background: var(--success-subtle); color: var(--success); }
  .f-meta { font-family: var(--font-mono); font-size: var(--font-small); color: var(--text-dim); white-space: nowrap; flex-shrink: 0; }
  .field-label { flex: 1; font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); }
  .field-body { font-size: var(--font-small); color: var(--text); line-height: var(--lh-relaxed); padding: var(--space-sm) var(--space-lg) var(--space-sm); overflow-x: auto; --rt-fade: var(--bg-surface); }
  .field-empty { padding: var(--space-sm) var(--space-lg) var(--space-md); font-size: var(--font-small); color: var(--text-dim); font-style: italic; cursor: pointer; width: 100%; text-align: left; }
  .field-empty:hover { color: var(--accent); }

  /* `.tab-count` a plecat — e `.count accent` din global.css. */

  .tab-content { min-height: 200px; }

  /* Sublinierea taburilor. `.tabs` are `overflow-x: auto`, deci e deja un
     container de derulare — dar NU e pozitionat, iar un copil absolut s-ar
     raporta la pagina. `position: relative` il face reperul, si atunci
     `offsetLeft` al tabului si `left: 0` al liniei masoara din acelasi punct.
     Latimea de referinta e 100px, scalata pe X: asa nu se anima `width`. */
  .tabs { position: relative; }
  .tab-linie {
    position: absolute;
    left: 0;
    bottom: -1px;              /* peste linia de 1px a lui `.tabs` */
    width: 100px;
    height: 2px;
    background: var(--accent);
    transform-origin: left;
    transform: translateX(var(--lx, 0)) scaleX(var(--lw, 0));
    opacity: 0;
    pointer-events: none;
  }
  .tab-linie.gata { opacity: 1; }
  .tab-linie.asezata {
    transition: transform var(--dur-arc-elan) var(--ease-arc-elan), opacity var(--dur-fast) var(--ease);
  }
  /* Bordura proprie a tabului pleaca: sublinierea e acum un singur obiect care
     se muta. Lasata, s-ar aprinde in acelasi timp la destinatie — doua semne
     pentru acelasi lucru, exact ce s-a demontat la tenta din doc. */
  :global(.tabs) .tab.active { border-bottom-color: transparent; }

  /* Wiki tab */
  .wiki-empty { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 32px 16px; color: var(--text-secondary); text-align: center; }
  .wiki-empty p { margin: 0; }
  .wiki-hint { font-size: var(--font-small, 0.82rem); color: var(--text-dim); }
  .wiki-empty code { font-family: var(--font-mono); font-size: 0.85em; background: var(--bg-elevated); padding: 1px 5px; border-radius: var(--radius-sm); }

  .wiki-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
  /* Fara mono: chipul poarta NUMELE unei sectiuni de wiki — un cuvant care se
     citeste, nu o cifra care se compara pe verticala. */
  .wiki-chip { font-size: var(--font-small); padding: 4px 10px; border-radius: var(--radius-full); border: 1px solid var(--border); background: transparent; color: var(--text-secondary); cursor: pointer; }
  .wiki-chip:hover { background: var(--bg-hover); color: var(--text); }
  .wiki-chip.active { background: var(--accent-subtle); color: var(--accent-on-subtle); border-color: var(--accent-ring); }
  .wiki-body { padding: 4px 2px; }
  .wiki-editor { width: 100%; min-height: 360px; resize: vertical; font-family: var(--font-mono); font-size: var(--font-small); line-height: var(--lh-normal); color: var(--text); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 10px 12px; }
  .wiki-editor:focus { outline: none; border-color: var(--accent-ring); }
  .wiki-edit-actions { display: flex; gap: 8px; margin-top: 10px; }
  .tab-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-sm); }
  .tab-sub { font-size: var(--font-small); color: var(--text-dim); }
  .quick-add { display: flex; flex-direction: column; margin-bottom: var(--space-md); }
  .qa-rand { display: flex; gap: var(--space-sm); }
  /* Chipurile de zi, identice cu cele din /tasks: adaugarea si planificarea sunt
     un singur gest. Enter ramane „fara termen" — indiciul o spune. */
  .qa-cand { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 8px 2px 0; }
  .qa-chip { padding: 5px 14px; border-radius: var(--radius-full);
    background: var(--bg-elevated); border: 1px solid var(--border);
    color: var(--text-secondary); font-size: var(--font-small);
    font-weight: var(--fw-medium); cursor: pointer;
    transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .qa-chip:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-subtle); }
  .qa-dp :global(.dp-trigger) { min-height: 30px; padding: 4px 12px;
    border-radius: var(--radius-full); font-size: var(--font-small); }
  .qa-hint { font-size: var(--font-small); color: var(--text-dim); margin-left: auto; }

  .quick-add input { flex: 1; min-height: 40px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); }
  .quick-add input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .empty { color: var(--text-dim); font-size: var(--font-small); padding: var(--space-lg) 0; text-align: center; }

  /* Task list */
  .task-list { display: flex; flex-direction: column; }

  /* CAPUL DE GRUPA — acelasi obiect ca in /tasks, aceleasi tonuri: nu inveti doua
     coduri de culoare pentru acelasi fapt. Nu e `sticky` aici: lista traieste
     intr-un tab cu bara proprie deasupra, iar un al doilea rand lipit s-ar aseza
     peste ea. */
  .grup-cap { display: flex; align-items: center; gap: var(--space-xs);
    padding: 10px 2px 5px; margin-top: var(--space-xs);
    font-family: var(--font-mono); font-size: var(--font-label);
    font-weight: var(--fw-semibold); text-transform: uppercase;
    letter-spacing: var(--tracking-label); color: var(--text-dim); }
  .grup-cap:first-child { margin-top: 0; }
  .grup-n { display: inline-flex; align-items: center; justify-content: center;
    min-width: 17px; height: 17px; padding: 0 5px; border-radius: var(--radius-full);
    background: var(--bg-elevated); color: var(--text-dim);
    font-family: var(--font-mono); font-size: var(--font-small);
    line-height: 1; font-variant-numeric: tabular-nums; }
  .grup-cap.ton-danger { color: var(--danger); }
  .grup-cap.ton-danger .grup-n { background: var(--danger-subtle); color: var(--danger); }
  .grup-cap.ton-accent { color: var(--accent); }
  .grup-cap.ton-accent .grup-n { background: var(--accent-subtle); color: var(--accent-on-subtle); }

  /* ===== PE TELEFON, ACELASI CAP DE GRUPA CA IN /tasks =====
     Randul era DEJA acelasi obiect — masurat rand cu rand: aceeasi inaltime
     (52px), aceleasi stiluri calculate, aceeasi structura, acelasi gest de
     glisare. Capul de grupa nu era: aceeasi clasa `.grup-cap`, dar doua definitii
     scrise separat, care au divergat. Aici: text mono rosu, numarul intr-o
     pastila, fara banda. In /tasks: punct colorat + eticheta NEUTRA pe o banda
     lipita de ecran, si numarul singur poarta urgenta.
     Doua coduri de citire pentru acelasi fapt, la doua atingeri distanta.
     Se aliniaza pe cel din /tasks fiindca acolo e lista citita cel mai des, si
     fiindca regula lui e cea argumentata: un rand intreg de text rosu peste o
     lista de randuri rosii nu mai selecteaza nimic.
     `--header-height`, nu `--h-antet`: aceeasi valoare ca in /tasks, ca cele
     doua sa se lipeasca la fel. Daca se schimba, se schimba in amandoua.
     Doar pe telefon (cerut): pe desktop lista sta langa restul paginii, tabul
     are alta geometrie, si un al doilea rand lipit s-ar aseza peste bara lui. */
  @media (max-width: 768px) {
    .grup-cap { position: sticky; top: var(--header-height); z-index: 2;
      gap: var(--space-sm); padding: 20px 12px 8px; margin-top: 0;
      /* `--bg`, nu `--bg-surface`: degradeul exista ca sa stinga randurile care
         trec pe sub banda, deci trebuie sa fie culoarea DIN SPATELE listei.
         Masurat, amandoua listele stau pe `--bg` (rgb(244,245,247) pe tema
         deschisa) — cu `--bg-surface` banda iesea alba pe gri. Regula de telefon
         din /tasks foloseste tot `--bg`, din acelasi motiv. */
      background: linear-gradient(var(--bg) 72%, transparent);
      font-family: var(--font-sans); color: var(--text-secondary); }
    /* Punctul poarta tonul; eticheta ramane neutra in toate grupele. */
    .grup-cap::before { content: ''; width: 7px; height: 7px; border-radius: 50%;
      background: var(--border-strong); flex: none; }
    .grup-cap:first-child { padding-top: 4px; }
    .grup-cap.ton-danger, .grup-cap.ton-accent { color: var(--text-secondary); }
    .grup-cap.ton-danger::before { background: var(--danger); }
    .grup-cap.ton-accent::before { background: var(--accent); }
    /* „Fara termen" e INEL, nu punct plin — absenta termenului se spune prin
       absenta fillului, ca in /tasks. */
    .grup-cap.ton-sters::before { background: none;
      box-shadow: inset 0 0 0 1.5px var(--border-strong); }
    /* Pastila dispare: numarul e cifra, nu insigna. */
    .grup-n { display: inline; min-width: 0; height: auto; padding: 0;
      border-radius: 0; background: none; line-height: inherit;
      font-family: var(--font-mono); font-size: var(--font-label);
      color: var(--danger); text-transform: none;
      letter-spacing: var(--tracking-normal); }
    .grup-cap.ton-danger .grup-n { background: none; color: var(--danger); }
  }
  /* UN SINGUR OBIECT: rama, fundalul si colturile stau pe WRAPPER, iar randul si
     extinderea sunt continutul lui. Aici extinderea era un card SEPARAT (fundal
     propriu, rama proprie, indentat 26px), deci un task deschis se citea ca doua
     cutii lipite — in /tasks aceeasi problema fusese deja rezolvata invers. */
  /* MUCHIA DE SEVERITATE A PLECAT — severitatea e pe inelul bifei (`--ring`) si
     pe textul termenului. Aici muchia era in plus si ambigua: un rand de task si
     unul de implementare stateau unul sub altul cu aceeasi dunga de 3px, una
     spunand „urgent", cealalta „proiectul X". Cei 2px pierduti de la bordura se
     intorc in padding, ca lista sa nu se decaleze fata de antetul ei. */
  /* Lista, nu doisprezece cutii — ca in /tasks. */
  .trow-wrap { display: flex; flex-direction: column; background: none;
    border: 0; border-radius: var(--radius-sm); overflow: hidden; }
  .trow-wrap + .trow-wrap { border-top: 1px solid var(--border); }
  .trow-wrap.deschis, .trow-wrap.deschis + .trow-wrap { border-top-color: transparent; }
  .trow-wrap.deschis { background: var(--bg-elevated); }
  /* Ion: „poti face putin mai inguste pe desktop taskurile, pe inaltime?"
     8px sus / 10px jos -> 5/7: randul scade de la ~62 la ~56px, fara sa se
     atinga fontul sau meta-randul. Doar desktop — pe telefon padding-ul
     vertical e al lui `.gl-fata` si ramane cum e. */
  /* ACELASI RAND CA IN /tasks si pe boardul „Astăzi": 46px, gap 12, coloana de
     termen pironita la 46px, actiunile cu text la stanga ei. Comentariile
     detaliate stau in Tasks.svelte — acolo e sursa formei, aici e copia care
     trebuie sa nu se abata. */
  .trow { position: relative; display: flex; align-items: center; gap: var(--space-12);
    min-height: 46px; padding: 0 var(--space-12); background: none; border: 0;
    transition: background-color var(--dur-base) var(--ease), opacity var(--dur-base) var(--ease); }
  @media (hover: hover) {
    .trow:hover { background: var(--bg-elevated); }
  }
  .done-list { display: flex; flex-direction: column; }
  /* Pe desktop invelisul de glisare nu exista pentru layout. */
  .gl-fata { display: contents; }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; display: inline-flex; }
  .check:hover { color: var(--accent); }
  .trow.done .check { color: var(--success); }
  /* `.check-empty` traieste in global.css, o singura data pentru toate listele. */
  /* O LINIE, ca in `Tasks.svelte` — randul e UN SINGUR obiect in toate listele.
     Era o COLOANA, ramasa de pe vremea celei de-a doua linii (`.tinfo`), care nu
     mai are niciun consumator in markup de la E1 incoace: cu ea, contorul de pasi
     ar fi aterizat SUB titlu aici si langa el in celelalte trei liste. */
  .tmain { flex: 1; min-width: 0; cursor: pointer; text-align: left; align-self: stretch;
    display: flex; align-items: center; gap: var(--space-sm); }
  /* --font-rand, nu --font-body: randul de lista ramane 15 si pe telefon.
     Era singurul din cele patru liste ramas pe `--font-body`, care pe telefon
     urca la 16 — deci acelasi rand avea 56px aici si 52 in /tasks si pe
     „Astăzi”, desi contractul spune ca e UN SINGUR obiect. Pe desktop
     amandoua sunt 15, deci diferenta se vedea doar pe telefon. */
  .ttitle { font-size: var(--font-rand); color: var(--text); font-weight: var(--fw-medium);
    min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* Fara `opacity` pe randul bifat: se inmulteste peste tokenuri deja la limita
     de contrast. Ce e facut o spun taietura si culoarea bifei. */
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  /* `.tinfo` (a doua linie a randului) a plecat: n-avea niciun consumator in
     markup de la E1 incoace, iar `.tmain` ramasese coloana degeaba din cauza ei.
     Fractia de pasi s-a intors pe rand — `.tpasi`, langa titlu, reteta unica din
     global.css (cerinta Ion, 2026-08-15). Railul din dreapta („Progres taskuri
     7/12") ramane: acela numara TASKURI din proiect, nu pasii unui task. */

  .task-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
  /* ACEEASI RETETA CA IN `Tasks.svelte` — copiata literal, nu reinterpretata.
     Aici actiunile doar se stingeau, pe 120ms; acolo INTRA 8px dinspre dreapta,
     pe 220. Puse una langa alta la aceeasi latime, cele doua liste raspundeau
     diferit la acelasi gest. */
  @media (hover: hover) {
    .task-actions { opacity: 0; pointer-events: none; transform: translateX(8px);
      transition: opacity var(--dur-base) var(--ease), transform var(--dur-base) var(--ease); }
    .trow:hover .task-actions,
    .task-actions:focus-within { opacity: 1; pointer-events: auto; transform: none; }
  }
  .ta-chip, .ta-dp :global(.dp-trigger) {
    display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 11px;
    border-radius: var(--radius-xs); background: var(--bg-surface); box-shadow: var(--shadow-sm);
    border: none; color: var(--text-secondary); font-family: inherit;
    font-size: var(--font-control); font-weight: var(--fw-semibold);
    white-space: nowrap; cursor: pointer; transition: var(--transition-pressable); }
  .ta-chip:hover, .ta-dp :global(.dp-trigger:hover) { color: var(--text); background: var(--bg-hover); }
  .ta-chip:active { transform: scale(var(--press-scale)); }
  .ta-sterge:hover { color: var(--danger-deep); background: var(--danger-subtle); }
  .ta-dp { flex-shrink: 0; }
  .ta-dp :global(.dp) { width: auto; }
  .ta-dp :global(.dp-trigger) { min-height: 0; flex-direction: row-reverse; }

  .ttermen { flex: none; width: 46px; text-align: right;
    font-family: var(--font-mono); font-size: var(--font-label);
    color: var(--text-dim); font-variant-numeric: tabular-nums;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ttermen.sev { color: var(--danger); }
  .ttermen.acum { color: var(--accent-deep); font-weight: var(--fw-medium); }

  .task-form { display: flex; flex-direction: column; gap: var(--space-md); }
  /* LA VEDERE, PALIDE — nu ascunse pana la hover.
     Aici erau `opacity: 0` pana la `.trow:hover`, in timp ce aceleasi butoane din
     /tasks stau mereu la vedere (decizia din 2026-06-18). Doua liste de taskuri cu
     acelasi rand si doua comportamente diferite — inveti unul si te inseala celalalt.
     Si mai rau: `opacity: 0` + `:hover` inseamna INEXISTENT pe orice ecran care se
     atinge, iar sub 768px scapau doar fiindca acolo intra alta regula. Un laptop cu
     ecran tactil sau o tableta in peisaj cadeau exact intre ele. */

  /* Done separator */
  .done-sep { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-sm) var(--space-xs); font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-dim); cursor: pointer; margin-top: var(--space-sm); border-top: 1px solid var(--border-subtle); text-transform: uppercase; letter-spacing: var(--tracking-label); }
  .done-sep:hover { color: var(--text-secondary); }
  /* Contorul in capul sectiunii, ca la grupe — nu in paranteza in text. */
  .done-sep .grup-n { background: var(--success-subtle); color: var(--success); }

  /* Subtask expanded area */
  /* Corp expandat: panou inset (nu mai pluteste pe negru), continut grupat cu gap */
  /* Extinderea e CONTINUAREA randului, separata doar de o linie subtire — aceeasi
     reteta ca in /tasks, la aceleasi valori. */
  .subtask-body { margin: 0; padding: 6px var(--space-12) var(--space-12) 34px;
    border-top: 1px solid var(--border-subtle);
    display: flex; flex-direction: column; gap: 4px; }
  .td-nota { margin-bottom: var(--space-sm); font-size: var(--font-small); color: var(--text-secondary); }
  .td-jos { display: flex; align-items: center; gap: var(--space-md);
    margin-top: var(--space-sm); padding-top: var(--space-sm);
    border-top: 1px dashed var(--border-subtle); }
  .td-link { display: inline-flex; align-items: center; gap: 6px; padding: 0;
    background: none; border: none; color: var(--text-dim);
    font-size: var(--font-small); cursor: pointer; transition: var(--transition-colors); }
  .td-link:hover { color: var(--accent); }
  .td-link.areNota { color: var(--text-dim); }
  .td-dp :global(.dp) { width: auto; }
  .td-dp :global(.dp-trigger) { min-height: 0; padding: 0; gap: 6px;
    background: none; border: none; box-shadow: none; border-radius: 0;
    color: var(--text-dim); font-size: var(--font-small); }
  .td-dp :global(.dp-trigger:hover) { color: var(--accent); background: none; }
  .sub-section { display: flex; flex-direction: column; gap: 2px; }
  /* Antetul sectiunii de subtaskuri — aceeasi reteta ca in /tasks (titlu + bara
     + numar pe un rand); .sub-bara/.sub-num vin din global.css. */
  .sub-head { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: 4px; }
  .sub-cap { font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); flex: none; }
  .sub-row { display: flex; align-items: center; gap: 9px; min-height: 32px;
    padding: 0 6px; border-radius: var(--radius-xs); }
  .sub-row:hover { background: var(--bg-hover); }
  /* Ultimul RAND al listei, nu un formular care sta gol pe ecran. */
  .sub-nou { display: flex; align-items: center; gap: 9px; width: 100%;
    min-height: 32px; padding: 0 6px; border: none; border-radius: var(--radius-xs);
    background: none; color: var(--text-dim); font-size: var(--font-small);
    cursor: pointer; transition: var(--transition-colors); }
  .sub-nou:hover { background: var(--accent-subtle); color: var(--accent); }
  .sub-nou-p { display: flex; align-items: center; justify-content: center;
    width: 18px; flex: none; }
  .sub-row.sub-done .sub-title { text-decoration: line-through; color: var(--text-dim); }
  /* Titlul e BUTON (atingerea bifeaza), dar trebuie sa arate ca text: fara
     fundal, fara rama, aliniat la stanga, pe toata latimea ramasa. Aceleasi
     declaratii ca in /tasks — un `<button>` fara ele isi aduce haina lui. */
  .sub-title { flex: 1; font-size: var(--font-small); color: var(--text); min-width: 0;
    background: none; border: none; padding: 0; text-align: left; cursor: pointer;
    overflow-wrap: anywhere; }
  .sub-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; flex-shrink: 0; opacity: 0; transition: opacity var(--dur-fast); }
  .sub-row:hover .sub-del { opacity: 1; }
  .sub-del:hover { color: var(--danger); background: var(--danger-subtle); }
  .sub-add { display: flex; gap: var(--space-xs); margin-top: 0; }
  .sub-add input { flex: 1; padding: 6px 10px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-small); }
  .sub-add input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .sub-add-btn { width: 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .sub-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
  .sub-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* Detalii proiect (bara laterala) */
  /* Detalii in bara laterala (fostul tab Info) — grila de doua coloane, fara
     randuri goale: campurile necompletate nici nu ajung in lista. */
  .rdet { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 10px; margin: 6px 0 0; }
  .rdet dt { font-size: var(--font-small); color: var(--text-dim); white-space: nowrap; }
  .rdet dd { margin: 0; font-size: var(--font-small); color: var(--text-secondary); overflow-wrap: anywhere; }


  /* Equipment import/copy */

  /* Rezumatul de o linie exista DOAR sub 940px, unde railul a coborat. Pe desktop
     railul e langa continut si il spune mai bine. */
  .rail-mini { display: none; }

  @media (max-width: 940px) {
    .rail-grid { grid-template-columns: 1fr; }
    .rail { position: static; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; order: 0; margin-top: var(--space-md); }

    .rail-mini { display: flex; align-items: center; gap: var(--space-sm);
      margin-bottom: var(--space-sm); padding: 0 2px; }
    .rm-pct { font-family: var(--font-mono); font-size: var(--font-small);
      font-weight: var(--fw-semibold); color: var(--text-secondary);
      font-variant-numeric: tabular-nums; }
    .rm-bar { flex: 1; max-width: 90px; height: 3px; border-radius: var(--radius-full);
      background: var(--bg-input); overflow: hidden; }
    .rm-bar i { display: block; height: 100%; background: var(--accent); }
    .rm-cand { margin-left: auto; font-family: var(--font-mono);
      font-size: var(--font-small); color: var(--text-dim);
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .rm-cand.urgent { color: var(--danger); font-weight: var(--fw-semibold); }
    .rm-cand.rm-gol { color: var(--text-dim); }
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

    /* LINIA RAPIDA pleaca de pe telefon: adaugarea vine din butonul plutitor, prin
       aceeasi foaie ca in celelalte doua ecrane. Aici ea era a treia gramatica de
       adaugare din aplicatie. */
    .quick-add { display: none; }
    /* Loc pentru butonul plutitor, ca ultimul rand din lista sa nu stea sub el.
       Aceeasi rezerva ca in /tasks: inaltimea butonului plus distanta lui. */
    .tab-pane { padding-bottom: calc(58px + var(--space-md)); }

    /* BUTONUL MARE CU PLUS — copiat la valoare din /tasks, nu aproximat: e acelasi
       obiect pe alt ecran, deci orice diferenta de pozitie s-ar citi ca doua
       butoane diferite cand treci de la o pagina la alta. */
    .fab { --fab-size: 58px;
      position: fixed; right: calc(var(--space-md) + var(--safe-right));
      bottom: calc(var(--dock-h) + 4px + 24px + var(--safe-bottom));
      width: var(--fab-size); height: var(--fab-size); display: grid; place-items: center;
      border-radius: var(--radius-lg); border: none;
      background: var(--accent); color: var(--accent-text);
      box-shadow: var(--shadow-md); z-index: calc(var(--z-sticky) - 1);
      cursor: pointer; transition: var(--transition-pressable); }
    .fab:active { transform: scale(var(--press-scale)); }
    /* O LINIE, cu actiunile in panoul de sub rand (vezi Taskuri / „Astazi").
       Randul avea titlul sus si actiunile pe o linie proprie dedesubt. */
    /* ACEEASI GEOMETRIE CA IN /tasks SI PE „Astăzi" — pana la pixel.
       Randul de aici ramasese CARD: `padding: 6px`, gap 8, fond de panou si
       raza de control. Din cele 6px de padding iesea un rand de 56px, in timp
       ce celelalte doua liste au 52 — iar contractul spune ca e UN SINGUR
       obiect in trei liste. Un rand nu mai e un card: e o linie din lista, iar
       ce-l desparte de vecin e separatorul de pe wrapper.
       Fondul ramane OPAC: pista de bifare sta sub el si trebuie acoperita pana
       cand degetul o descopera. */
    .trow { flex-wrap: nowrap; align-items: center; min-height: var(--row-h-mobile);
            padding: 0; overflow: hidden; position: relative; touch-action: pan-y; }
    .gl-fata { display: flex; align-items: center; gap: var(--space-12); width: 100%;
               min-height: var(--row-h-mobile); padding: 0 var(--space-12);
               background: var(--bg-surface); position: relative;
               z-index: 1; border-radius: 0; will-change: transform; }
    .trow-wrap.deschis .gl-fata { background: var(--bg-elevated); }
    /* `:global(...)` pe clasa pusa din JS, NU pe intreg selectorul.
       Svelte NU se multumeste sa avertizeze „Unused CSS selector": TAIE regula din
       build. Iar `gl-tras`/`gl-bifa` sunt puse la RULARE de `lib/glisare.js`, deci
       nu apar in markup si compilatorul le crede moarte. Efectul, verificat in CSS-ul
       livrat: din toate regulile de gest ale aplicatiei supravietuise UNA. Adica
       glisai spre dreapta si nu vedeai verdele care spune „ai trecut pragul" —
       exact semnalul fara de care gestul e o loterie.
       Ancora (`.arow`/`.trow`/`.mrow`) ramane scoped, deci regula nu scapa in alte
       componente. */
    .trow:global(.gl-tras) .gl-fata { box-shadow: var(--shadow-glisare); }
    .task-actions { display: none; }
    /* Ca in /tasks: pe telefon titlul se rupe pe doua randuri in loc sa fie
       taiat cu „…”. Un titlu de task trunchiat la 30 de caractere pe un
       ecran de 390px ascunde tocmai ce s-a schimbat intre doua taskuri
       care incep la fel („Verifica schema de forta…” / „Verifica stocul…”). */
    .ttitle { white-space: normal; display: -webkit-box; -webkit-line-clamp: 2;
      line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
      text-overflow: initial; line-height: var(--lh-snug); }

    .trow:global(.gl-bifa) { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }
    .back { min-height: 44px; }
    .subtask-body { padding-left: var(--space-12); }
    .td-link { min-height: var(--tap-min); font-size: var(--font-small); }
    .td-dp :global(.dp-trigger) { min-height: var(--tap-min); font-size: var(--font-small); }
    .td-jos { gap: var(--space-lg); }
    .quick-add input, .quick-add-btn { min-height: var(--tap-min); }
    .quick-add-btn { width: var(--tap-min); }
    .qa-chip { min-height: var(--tap-sheet); }
    .qa-dp :global(.dp-trigger) { min-height: var(--tap-min); }
    /* Aceeasi reteta ca in Taskuri si Astăzi: 44px de atins, 30px de latime.
       Cercul de 18px intr-o caseta de 44 impingea titlul cu un sfert de ecran. */
    .check { position: relative; min-width: 30px; width: 30px; min-height: var(--tap-min);
      align-items: center; justify-content: center; padding: 0; }
    .check::after { content: ''; position: absolute; inset: -7px; }
    /* PUBELA PLEACA DE PE RAND — stergerea vine din glisare spre stanga, ca in
       /tasks si ca la taskul parinte, cu „Anulează" in toast. Regula veche
       („e mereu acolo", 44px) rezolva absenta hover-ului punand singura actiune
       distructiva a panoului exact sub degetul mare. */
    .sub-del { display: none; }
    .sub-add-btn { min-width: var(--tap-min); min-height: var(--tap-min); }
    .sub-add input { min-height: var(--tap-min); }
    /* Randul devine pista, cu metricile subtaskului. */
    .sub-row { min-height: var(--tap-min); position: relative; overflow: hidden;
      touch-action: pan-y; padding: 0; }
    .sub-row .gl-fata { padding: 0 6px; gap: 9px; min-height: var(--tap-min);
      background: var(--bg-surface); border-radius: var(--radius-xs); }
    .sub-row:global(.gl-tras) .gl-fata { box-shadow: var(--shadow-glisare); }
    .sub-title { text-align: left; cursor: pointer; }
    .sub-nou { min-height: var(--tap-min); font-size: var(--font-small); }
    .sub-nou-p { width: 26px; }
    /* Filtrele de fisier din tabul Wiki — 29px. */
    .wiki-chip { min-height: var(--tap-min); padding: 4px 14px; }
    .wiki-chips { gap: var(--space-xs); }
    /* Bara de sus a paginii: „Edit", „PDF", „MD" si meniul. */
    .header-actions :global(.btn) { min-width: var(--tap-min); }
  }
</style>
