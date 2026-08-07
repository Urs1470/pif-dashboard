<script>
  import { ecran } from '../lib/ecran.svelte.js'
  import { slide } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { motionDuration, DUR_BASE, plecare, sosire, desfacere, DUR_FAST } from '../lib/motion.svelte.js'
  import { ListTodo, Plus, CheckCircle2, CalendarDays, ListChecks, ChevronDown, ChevronRight, Repeat, Search, CalendarPlus, X, Check, Archive, Briefcase, User, Text, Bell } from '@lucide/svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import { globalTasks, loadGlobalTasks, updateGlobalTask, createGlobalTask, deleteGlobalTask, loadSubtasks, createSubtask, updateSubtask, deleteSubtask } from '../stores/tasks.svelte.js'
  import { formatDate, dueRing, isFutureRecurrence, esteDepasit as isOverdue, esteAzi as isToday } from '../lib/formatters.js'
  import { grupeazaDupaTermen, etichetaTermen, ORDINE_GRUPE } from '../lib/grupare.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import { router, navigate } from '../lib/router.svelte.js'
  import { focusOnLand, focusKey } from '../lib/focus.js'
  import { glisare } from '../lib/glisare.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import Button from '../components/ui/Button.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import Input from '../components/ui/Input.svelte'
  import Textarea from '../components/ui/Textarea.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import Select from '../components/ui/Select.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  import RichTextEditor from '../components/ui/RichTextEditor.svelte'
  import RichText from '../components/ui/RichText.svelte'
  import { todayISO, addDays } from '../lib/calendarDates.js'
  import { apiJson } from '../lib/api.js'
  import { suportaPush, esteIosNeinstalat, stareAbonament, aboneaza, dezaboneaza } from '../lib/push.js'
  import { esteNativ, probeaza, reprogrameaza } from '../lib/notificari.js'

  // Sfera vine din URL (#/tasks?sfera=personal), nu din state local: vederea e
  // adresabila — un link din paleta, din cautare sau de pe Acasa aterizeaza
  // direct in ea. Orice altceva decat 'personal' inseamna munca (fail-closed,
  // ca pe server).
  const sferaActiva = $derived(router.query.sfera === 'personal' ? 'personal' : 'munca')

  let showArchive = $state(false)
  let taskDeleteId = $state(null)
  let showTaskDelete = $state(false)
  let showNewModal = $state(false)
  let creating = $state(false)

  let formTitle = $state('')
  let formDesc = $state('')
  let formCategory = $state('General')
  let formDeadline = $state('')
  let formRecurenta = $state('')
  let editingTask = $state(null)
  let showEditModal = $state(false)

  let expandedTask = $state(null)
  let subtasksCache = $state({})
  let newSubtaskTitle = $state('')
  let adaugSubLa = $state('')   // id-ul taskului al carui compozitor de subtask e deschis

  let taskSearch = $state('')
  let quickTitle = $state('')
  let quickAdding = $state(false)
  let showNoteModal = $state(false)
  let noteTask = $state(null)
  let noteDraft = $state('')
  let noteOriginal = ''      // ca sa stim dac-ai schimbat ceva si ce se intoarce la „Anulează"
  let noteSaving = $state(false)



  /** Reincarcarea listei, mereu cu AMBELE filtre ale vederii curente. Un singur
   *  drum: fara el, un call-site uitat cu `loadGlobalTasks()` gol ar repicta
   *  vederea Personal cu lista de munca. */
  const reload = () => loadGlobalTasks({ arhiva: showArchive, sfera: sferaActiva })

  function matchesSearch(t) {
    if (!taskSearch) return true
    const q = taskSearch.toLowerCase()
    return (t.titlu || '').toLowerCase().includes(q) ||
           (t.descriere || '').toLowerCase().includes(q) ||
           (t.categorie || '').toLowerCase().includes(q)
  }

  const filteredTasks = $derived(
    globalTasks.items.filter(t => matchesSearch(t))
  )
  // Hide a recurring task's next occurrence until its scadenta arrives, so finalizing
  // today's instance doesn't look like an identical unchecked copy reappearing.
  const activeTasks = $derived(filteredTasks.filter(t => t.status !== 'done' && !isFutureRecurrence(t)))
  // NU exista `doneTasks` in vederea activa: `/api/global-tasks` adauga
  // `AND status != 'done'` cand nu ceri arhiva, deci lista nu contine niciodata
  // taskuri bifate. Aici traia o sectiune „N finalizate" pliabila, cu randuri
  // proprii si stil propriu — gardata pe `!showArchive && doneTasks.length > 0`,
  // adica pe o conditie care nu putea fi adevarata. Cod viu si corect, care nu
  // s-a randat niciodata. Ce ai terminat se vede in „Arhivă".

  // Lista se citeste de sus in jos ca o zi de lucru: restante, azi, mâine, restul.
  // In arhiva gruparea n-ar spune nimic (toate sunt facute), deci ramane o grupa
  // fara cap — acelasi drum de randare, zero markup duplicat.
  const grupe = $derived(showArchive
    ? { arhiva: { id: 'arhiva', titlu: null, ton: 'sters', items: globalTasks.items, start: 0 } }
    : grupeazaDupaTermen(activeTasks))
  // Arhiva e o grupa fara cap, pusa la coada ordinii — acelasi drum de randare.
  const ordine = [...ORDINE_GRUPE, 'arhiva']

  /** Ce scrie chipul de termen pe rand. In „Azi"/„Mâine"/„Fără termen" capul de
   *  grupa a spus-o deja — repetat pe fiecare rand ar fi zgomot. */
  function chipTermen(t, grupId) {
    if (grupId === 'azi' || grupId === 'maine' || grupId === 'fara') return ''
    return etichetaTermen(t.data_scadenta)
  }

  async function toggleStatus(task) {
    const next = task.status === 'done' ? 'to_do' : 'done'
    // OPTIMIST, ca randul sa plece IN CLIPA in care il atingi.
    // Fara asta, intre atingere si disparitie sta un dus-intors cu serverul
    // (~200ms de nimic), iar animatia de iesire nu se mai citeste ca raspuns la
    // gestul tau, ci ca ceva ce se intampla singur, mai tarziu. La eroare,
    // reincarcarea din `catch` pune lista la loc — deci minciuna dureaza cel
    // mult cat cererea.
    globalTasks.items = globalTasks.items.map(t => t.id === task.id ? { ...t, status: next } : t)
    let res
    try {
      res = await updateGlobalTask(task.id, { status: next })
    } catch (e) {
      await reload()
      toast(`Eroare: ${e.message}`, 'error')
      return
    }
    await reload()
    if (res?.recurring_spawned) {
      toast(`Finalizat ✓ — următoarea apariție: ${formatDate(res.recurring_next)}`, 'success')
      return
    }
    // ANULEAZA la bifare. Pe telefon bifatul se face si din glisare, deci se face
    // si din greseala — iar un task bifat DISPARE din lista (trece in „finalizate",
    // sectiune inchisa). Fara drumul inapoi ramai cu un task pierdut si convingerea
    // ca l-ai facut. Nu e o stergere, deci nu amanam nimic: actiunea s-a intamplat
    // deja, butonul doar o intoarce.
    if (next === 'done') {
      toastUndo(`Făcut: ${task.titlu.slice(0, 34)}${task.titlu.length > 34 ? '…' : ''}`, {
        onUndo: async () => {
          await updateGlobalTask(task.id, { status: 'to_do' })
          await reload()
        },
      })
    }
  }

  /** Muta termenul unui task. `null` il sterge (taskul se intoarce in „Fără termen"). */
  async function setTermen(t, zile) {
    // `addDays(todayISO(), n)`, NU `new Date().toISOString()`: a doua varianta
    // converteste la UTC, iar miezul noptii LOCAL intr-un fus de la est de
    // Greenwich (Romania e +2/+3) cade in ziua PRECEDENTA. Nu era un caz de
    // margine la ore mici — `setHours(0,0,0,0)` il facea sigur, deci „Azi"
    // scria ieri la orice ora. Vezi lib/calendarDates.js, care lucreaza pe
    // campurile locale ale datei.
    const v = zile === null ? '' : addDays(todayISO(), zile)
    const vechi = t.data_scadenta || ''
    try {
      await updateGlobalTask(t.id, { data_scadenta: v })
      await reload()
      toastUndo(v ? `Mutat pe ${etichetaTermen(v)}` : 'Termen scos', {
        onUndo: async () => {
          await updateGlobalTask(t.id, { data_scadenta: vechi })
          await reload()
        },
      })
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function setTermenData(t, v) {
    const vechi = t.data_scadenta || ''
    try {
      await updateGlobalTask(t.id, { data_scadenta: v || '' })
      await reload()
      toastUndo(v ? `Mutat pe ${etichetaTermen(v)}` : 'Termen scos', {
        onUndo: async () => {
          await updateGlobalTask(t.id, { data_scadenta: vechi })
          await reload()
        },
      })
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  function resetForm() {
    formTitle = ''; formDesc = ''
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
        categorie: formCategory,
        sfera: sferaActiva,
        data_scadenta: formDeadline || undefined,
        recurenta: formRecurenta || undefined,
        status: 'to_do',
      }, { arhiva: showArchive, sfera: sferaActiva })
      resetForm()
      showNewModal = false
    } finally { creating = false }
  }

  // Adaugarea si planificarea sunt ACELASI gest, nu doua.
  // Inainte: scriai titlul, Enter, si taskul cadea in „fara termen"; ca sa-i pui o
  // zi trebuia sa-l gasesti in lista, sa glisezi, sa deschizi editorul. Practic
  // fiecare task nou nascut fara data, si sertarul crestea. Acum, cat timp ai text
  // in camp, sub el apar „Azi / Mâine / Alege data" — Enter tot inseamna „fara
  // termen", pentru ca uneori chiar asta vrei.
  let quickInput = $state(null)
  let cautareDeschisa = $state(false)
  let cautareInput = $state(null)
  function deschideCautarea() {
    cautareDeschisa = true
    // `tick` nu ajunge: inputul apare abia dupa ce Svelte comite schimbarea de
    // ramura din `{#if}`, iar pe iOS focusul cerut prea devreme nu scoate tastatura.
    setTimeout(() => cautareInput?.focus(), 40)
  }
  let quickData = $state('')

  async function quickAdd(zile) {
    if (!quickTitle.trim() || quickAdding) return
    quickAdding = true
    let termen = quickData
    if (zile !== undefined && zile !== null) {
      termen = addDays(todayISO(), zile)
    }
    try {
      await createGlobalTask({
        titlu: quickTitle.trim(), status: 'to_do', sfera: sferaActiva,
        data_scadenta: termen || undefined,
      }, { arhiva: showArchive, sfera: sferaActiva })
      quickTitle = ''
      quickData = ''
      // Focusul RAMANE in camp: intr-o lista de facut adaugi trei lucruri la rand,
      // nu unul. Fara asta, tastatura se inchide dupa fiecare.
      quickInput?.focus()
    } finally { quickAdding = false }
  }

  function openNoteModal(t) {
    noteTask = t
    noteDraft = t.descriere || ''
    noteOriginal = noteDraft
    showNoteModal = true
  }

  /** INCHIDEREA SALVEAZA. NU EXISTA „ANULEAZĂ" CARE SA ARUNCE CE AI SCRIS.
   *  Inainte: modalul avea „Anulează" si „Salvează", dar un click pe fundal (sau
   *  Escape, sau X) inchidea pur si simplu — fara sa intrebe, fara sa salveze.
   *  Adica trei din patru feluri de a inchide o pagina de scriere de 92% din ecran
   *  aruncau in tacere tot ce tastasei. Iar o notita de PIF se scrie cu casca pe cap,
   *  in hala, cu o mana.
   *  Alternativa clasica — un dialog „ai modificari nesalvate" — pune un al doilea
   *  dialog peste primul si te intreaba ceva ce se poate deduce. Aici inchiderea
   *  COMITE, iar drumul inapoi e cel pe care aplicatia il foloseste deja peste tot:
   *  un toast cu „Anulează" (vezi bifarea unui task, mutarea unui termen). */
  async function saveNote() {
    if (noteSaving || !noteTask) return
    const taskId = noteTask.id
    const vechi = noteOriginal
    if (noteDraft === vechi) { showNoteModal = false; return }   // nimic de salvat, niciun zgomot
    noteSaving = true
    try {
      await updateGlobalTask(taskId, { descriere: noteDraft })
      showNoteModal = false
      await reload()
      toastUndo(vechi ? 'Notă actualizată' : 'Notă salvată', {
        onUndo: async () => {
          await updateGlobalTask(taskId, { descriere: vechi })
          await reload()
        },
      })
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
        categorie: formCategory,
        data_scadenta: formDeadline,
        recurenta: formRecurenta || null,
      })
      showEditModal = false
      editingTask = null
      await reload()
    } finally { creating = false }
  }

  // PE TELEFON TASKUL SE DESCHIDE INTR-O FOAIE, NU IN LISTA (cerinta Ion, dupa
  // capturile din Todoist).
  //
  // Motivul nu e „asa face Todoist", ci ca la noi continutul unui task era
  // imprastiat pe TREI suprafete: subtaskurile in lista, nota intr-un modal,
  // titlul in alt modal. Foaia le pune la un loc.
  // Al doilea motiv e tastatura: acopera ~40% din ecran, iar un camp editat
  // intr-un rand de lista poate ajunge sub ea. Foaia e ancorata jos, deci campul
  // ramane deasupra tastaturii.
  // Al treilea: extinderea in lista impinge tot ce e sub ea, deci iti pierzi
  // locul in lista exact cand te intorci la ea.
  //
  // Pe DESKTOP ramane extinderea in lista: acolo e loc pe verticala, exista hover
  // si tastatura fizica nu acopera nimic — o foaie ar fi un clic in plus degeaba.
  let sheetTaskId = $state('')
  let showSheet = $state(false)
  let termenDeschis = $state(false)   // panoul de replanificare din foaie
  // Derivat din lista, NU o copie: altfel bifarea unui subtask sau schimbarea
  // termenului din foaie ar lasa antetul foii pe valorile vechi.
  const sheetTask = $derived(globalTasks.items.find(x => x.id === sheetTaskId) || null)

  async function deschideFoaia(taskId) {
    sheetTaskId = taskId
    termenDeschis = false
    // Subtaskurile INAINTE de foaie, acelasi motiv ca la extinderea din lista:
    // o foaie care se ridica pe jumatate goala si apoi creste sub degetul tau
    // arata ca doua evenimente pentru un singur gest.
    await incarcaSubtaskuri(taskId)
    showSheet = true
  }

  // Cererile in zbor, ca sa nu plece doua pentru acelasi task: cu preincarcarea
  // pe hover, trecerea cu mouse-ul peste o lista de 15 randuri ar putea trimite
  // 15 cereri, iar in productie limita e 60 pe minut per IP (vezi app.py).
  // Cu harta asta, un task cere O SINGURA data pe sesiune.
  const inZbor = new Map()

  function incarcaSubtaskuri(taskId) {
    if (subtasksCache[taskId]) return Promise.resolve()
    if (inZbor.has(taskId)) return inZbor.get(taskId)
    const p = (async () => {
      try {
        const subs = await loadSubtasks(taskId)
        subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
      } catch (_) {
        // Si pe eroare cheia se scrie: panoul se deschide gol, cu invitatia de
        // adaugare. Fara ea, `toggleTaskExpand` n-ar avea ce arata si atingerea
        // randului ar ramane fara raspuns.
        subtasksCache = { ...subtasksCache, [taskId]: [] }
      } finally {
        inZbor.delete(taskId)
      }
    })()
    inZbor.set(taskId, p)
    return p
  }

  // FOAIA DOAR PE TELEFON; pe desktop taskul se desface in lista (cerinta Ion).
  // Am incercat foaia si pe desktop si a fost respinsa — iar motivul se sustine:
  // pe desktop nu exista niciunul dintre cele trei argumente care o justifica pe
  // telefon. Tastatura fizica nu acopera ecranul, e loc pe verticala fara sa
  // pierzi lista din ochi, iar un modal peste o lista larga inseamna un clic in
  // plus si contextul acoperit.
  // DESIGNUL ramane insa acelasi in ambele: `taskDetail` e UN SINGUR snippet,
  // randat ori in foaie, ori in rand. Cardurile de subtask, antetul de sectiune,
  // bara de progres si butonul de adaugare arata identic — se schimba doar unde
  // sunt asezate.
  //
  // ORDINEA CONTEAZA: intai datele, apoi deschiderea. Invers (cum era), panoul
  // se randa cu „Se încarcă…", `slide` masura ACEA inaltime si animeaza spre
  // ea — iar sectiunea de subtaskuri, sosita dupa aceea, aparea taiata peste
  // panoul deja terminat de animat. Un gest, doua evenimente vizuale.
  // Acum se deschide o singura data, cu ansamblul intreg si inaltimea finala.
  async function toggleTaskExpand(taskId) {
    if (ecran.telefon) { await deschideFoaia(taskId); return }
    if (expandedTask === taskId) {
      expandedTask = null
      return
    }
    await incarcaSubtaskuri(taskId)
    expandedTask = taskId
  }

  // Asteptarea de mai sus se plateste O DATA per task si, pe desktop, de obicei
  // deloc: mouse-ul trece pe rand inainte sa apese, deci subtaskurile sunt deja
  // in `subtasksCache` cand vine clicul. `incarcaSubtaskuri` iese imediat daca
  // exista cheia, deci trecerea peste zece randuri nu inseamna zece cereri de
  // fiecare data.
  function preincarca(taskId) {
    if (!ecran.telefon) incarcaSubtaskuri(taskId)
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
    // Compozitorul RAMANE deschis, gol si focalizat: subtaskurile se scriu in
    // rafala, nu unul singur. La fel ca la compozitorul de taskuri din lista.
    await createSubtask(taskId, newSubtaskTitle.trim())
    newSubtaskTitle = ''
    const subs = await loadSubtasks(taskId)
    subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
    await reload()
  }

  // REDENUMIREA UNUI SUBTASK.
  // API-ul o accepta de la inceput (`titlu` prin COALESCE in PUT /api/subtasks),
  // dar interfata n-a expus-o niciodata: ca sa corectezi o litera trebuia sa
  // stergi randul si sa-l scrii din nou. Atingi textul si il editezi pe loc, ca
  // in orice lista de bifat.
  let editSubId = $state('')
  let editSubTitlu = $state('')

  function incepeRedenumirea(sub) {
    editSubId = sub.id
    editSubTitlu = sub.titlu
  }

  async function salveazaRedenumirea(sub) {
    if (editSubId !== sub.id) return
    const nou = editSubTitlu.trim()
    editSubId = ''
    if (!nou || nou === sub.titlu) return
    await updateSubtask(sub.id, { titlu: nou })
    subtasksCache = {
      ...subtasksCache,
      [sub.task_id]: (subtasksCache[sub.task_id] || []).map(s => s.id === sub.id ? { ...s, titlu: nou } : s),
    }
  }

  // Deschide direct in scriere, cu textul selectat: de cele mai multe ori
  // rescrii randul, nu adaugi la el.
  function focalizeaza(node) { node.focus(); node.select() }

  // APASARE LUNGA, pentru actiunea rara de pe o tinta mare (redenumirea unui
  // subtask). Aceleasi 300ms ca la `lib/tragere.js`, si aceeasi conditie de
  // anulare: prima miscare peste 8px o opreste — altfel o glisare pornita din
  // greseala pe titlu ar declansa si redenumirea, si pista de stergere.
  // Doar pe pointer nu-mouse: cu mouse, clicul simplu redenumeste deja.
  const PRAG_LUNG = 300
  const PRAG_MISCARE = 8
  function apasareLunga(node, actiune) {
    let t = null, x0 = 0, y0 = 0, pornit = false
    const stop = () => { if (t) { clearTimeout(t); t = null } }
    const jos = (e) => {
      if (e.pointerType === 'mouse') return
      x0 = e.clientX; y0 = e.clientY; pornit = false
      stop()
      t = setTimeout(() => {
        t = null
        pornit = true
        try { navigator.vibrate?.(12) } catch (_) {}
        actiune?.()
      }, PRAG_LUNG)
    }
    const misca = (e) => {
      if (!t) return
      if (Math.abs(e.clientX - x0) > PRAG_MISCARE || Math.abs(e.clientY - y0) > PRAG_MISCARE) stop()
    }
    // Dupa o apasare lunga, clicul care urmeaza ridicarii degetului ar bifa —
    // deci se inghite, exact ca in `glisare` dupa un gest.
    const clic = (e) => { if (pornit) { e.preventDefault(); e.stopPropagation(); pornit = false } }
    node.addEventListener('pointerdown', jos)
    node.addEventListener('pointermove', misca)
    node.addEventListener('pointerup', stop)
    node.addEventListener('pointercancel', stop)
    node.addEventListener('click', clic, true)
    return {
      update: (a) => { actiune = a },
      destroy: () => {
        stop()
        node.removeEventListener('pointerdown', jos)
        node.removeEventListener('pointermove', misca)
        node.removeEventListener('pointerup', stop)
        node.removeEventListener('pointercancel', stop)
        node.removeEventListener('click', clic, true)
      },
    }
  }

  // ACELASI OBIECT, ACEEASI ATINGERE, ACELASI COMPORTAMENT. Aceeasi functie din
  // ProjectDetail sterge optimist si ofera `toastUndo` cu commit intarziat; aici
  // chema direct `deleteSubtask()` pe server, fara drum inapoi — iar cea fara
  // plasa era tocmai in lista folosita cel mai des. Pe telefon stergerea vine
  // acum dintr-un GEST, deci se poate porni si din greseala.
  function removeSubtask(sub) {
    const taskId = sub.task_id
    const list = subtasksCache[taskId] || []
    const idx = list.findIndex(s => s.id === sub.id)
    if (idx === -1) return
    const removed = list[idx]
    subtasksCache = { ...subtasksCache, [taskId]: list.filter(s => s.id !== sub.id) }
    toastUndo('Subtask șters', {
      onUndo: () => {
        const cur = [...(subtasksCache[taskId] || [])]
        cur.splice(Math.min(idx, cur.length), 0, removed)
        subtasksCache = { ...subtasksCache, [taskId]: cur }
      },
      onCommit: async () => {
        try {
          await deleteSubtask(sub.id)
          await reload()
        } catch (e) {
          toast(`Eroare: ${e.message}`, 'error')
          const subs = await loadSubtasks(taskId)
          subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
        }
      },
    })
  }

  async function doDeleteTask() {
    if (!taskDeleteId) return
    await deleteGlobalTask(taskDeleteId)
    taskDeleteId = null
    await reload()
    toast('Task șters', 'success')
  }



  // isOverdue/isToday vin din formatters.js (esteDepasit/esteAzi): aceeasi axa
  // si aceleasi praguri ca dueRing(), o singura definitie.

  // Banda de carduri urgente a plecat (Ion, 2026-07-27: „cardurile astea ce apar
  // nu am nevoie de ele"): repeta primele randuri din lista de imediat dedesubt,
  // care oricum e sortata cu urgentele sus si are aceleasi actiuni.


  // Abonarea in Google Calendar: feed-ul .ics personal se serveste cu o cheie
  // secreta in URL (Google il descarca de pe serverele lui, fara sesiune).
  // Butonul copiaza linkul gata format — in Google Calendar: „Adaugă din URL".
  // Din varianta cu API, asta e FALLBACK-ul din modalul Google (sincronizare
  // automata dar lenta — Google reciteste feedul la cateva ore).
  async function copiazaLinkIcs() {
    try {
      const { key } = await apiJson('/api/export/ics-key')
      const url = `${location.origin}/api/export/ics?sfera=personal&key=${key}`
      await navigator.clipboard.writeText(url)
      toast('Link copiat — în Google Calendar: „Alte calendare” → „Din URL”.', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  // Sincronizarea directa prin Google Calendar API (push instant, doar
  // personale). Chip-ul deschide un modal de stare; conectarea e o navigare
  // full-page catre fluxul OAuth de pe server — client id-ul nu traieste in
  // bundle, iar CSP ramane neatins.
  let showGoogleModal = $state(false)
  let googleStatus = $state(null)     // null = se incarca
  let googleBusy = $state(false)
  let showGoogleDisconnect = $state(false)

  async function deschideGoogle() {
    // Nu golim starea deja incarcata: modalul se deschide pe ce stim si se
    // improspateaza; scheletul apare doar la prima incarcare.
    showGoogleModal = true
    try { googleStatus = await apiJson('/api/google/status') }
    catch (e) { showGoogleModal = false; toast(`Eroare: ${e.message}`, 'error') }
  }

  // Starea se ia o data la intrarea in vederea Personal, ca punctul rosu de pe
  // iconita sa poata semnala o sincronizare stricata FARA sa deschizi modalul —
  // o stare care decide ce vezi in calendar nu are voie sa fie invizibila.
  $effect(() => {
    if (sferaActiva === 'personal' && googleStatus === null) {
      apiJson('/api/google/status').then(s => { googleStatus = s }).catch(() => {})
    }
  })

  // Acelasi motiv ca la Google: punctul rosu de pe clopotel trebuie sa poata
  // semnala o trimitere esuata FARA sa deschizi modalul.
  $effect(() => {
    if (sferaActiva === 'personal' && pushStatus === null) {
      apiJson('/api/push/status').then(s => { pushStatus = s }).catch(() => {})
    }
  })

  async function resyncGoogle() {
    if (googleBusy) return
    googleBusy = true
    try {
      await apiJson('/api/google/resync', { method: 'POST', body: {} })
      toast('Resincronizare pornită.', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { googleBusy = false }
  }

  async function disconnectGoogle() {
    try {
      await apiJson('/api/google/disconnect', { method: 'POST', body: {} })
      toast('Deconectat de la Google Calendar.', 'success')
      googleStatus = await apiJson('/api/google/status')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  // Configurare fara SSH: JSON-ul OAuth descarcat din consola se lipeste aici
  // si intra in app_settings pe server (validat acolo; exclus din backup).
  let credText = $state('')
  let credSaving = $state(false)
  let schimbCred = $state(false)   // redeschide campul cand esti deja configurat

  async function salveazaCred() {
    if (credSaving || !credText.trim()) return
    credSaving = true
    try {
      googleStatus = await apiJson('/api/google/credentials', { method: 'PUT', body: { json: credText.trim() } })
      credText = ''
      schimbCred = false
      toast('Credențiale salvate — acum conectează contul.', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { credSaving = false }
  }

  // Notificarile zilnice: o notificare PER task personal care sta fara termen
  // de peste doua zile, cu „Facut"/„Azi" direct pe notificare.
  let showPushModal = $state(false)
  let pushStatus = $state(null)     // starea de pe server
  let pushLocal = $state(null)      // permisiunea + abonamentul acestui browser
  let pushBusy = $state(false)

  async function reincarcaPush() {
    const [server, local] = await Promise.all([
      apiJson('/api/push/status'),
      suportaPush() ? stareAbonament() : Promise.resolve({ permisiune: 'unsupported', abonat: false }),
    ])
    pushStatus = server
    pushLocal = local
  }

  async function deschidePush() {
    // Setarile se cer la DESCHIDEREA ferestrei, nu la incarcarea paginii: sunt
    // folosite doar aici, si o cerere in plus la fiecare intrare pe Taskuri ar
    // fi trafic pentru un ecran pe care il deschizi de doua ori pe an.
    if (esteNativ() && !setari) {
      apiJson('/api/push/setari').then((s) => { setari = s }).catch(() => {})
    }
    showPushModal = true
    try { await reincarcaPush() }
    catch (e) { showPushModal = false; toast(`Eroare: ${e.message}`, 'error') }
  }

  async function activeazaPush() {
    if (pushBusy) return
    pushBusy = true
    try {
      await aboneaza()
      await reincarcaPush()
      toast('Notificări activate pe dispozitivul ăsta.', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { pushBusy = false }
  }

  async function dezactiveazaPush() {
    if (pushBusy) return
    pushBusy = true
    try {
      await dezaboneaza()
      await reincarcaPush()
      toast('Notificări dezactivate pe dispozitivul ăsta.', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { pushBusy = false }
  }

  async function testPush() {
    if (pushBusy) return
    pushBusy = true
    try {
      const r = await apiJson('/api/push/test', { method: 'POST', body: {} })
      await reincarcaPush()
      toast(r.esuate ? (r.motiv || `Eșuate: ${r.esuate}`) : 'Notificare de test trimisă.',
            r.esuate ? 'error' : 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { pushBusy = false }
  }

  // In aplicatia de pe telefon, proba nu trece prin server deloc: pune o alarma
  // locala peste ~40s, pe acelasi canal si cu aceleasi butoane ca cele de la 8
  // dimineata. Daca lantul e rupt undeva (permisiune, canal, alarma exacta),
  // afli ACUM si afli unde — nu maine dimineata, din tacere.
  async function probaLocala() {
    if (pushBusy) return
    pushBusy = true
    try {
      toast(await probeaza(), 'success')
    } catch (e) { toast(e.message, 'error') }
    finally { pushBusy = false }
  }

  // SETARILE DE NOTIFICARI (doar in aplicatia nativa — pe web nu exista canalul
  // local pe care sa-l regleze). Stau pe server, deci sunt aceleasi de pe orice
  // dispozitiv si supravietuiesc unei reinstalari.
  let setari = $state(null)
  let setariEroare = $state('')
  const oreDisponibile = Array.from({ length: 24 }, (_, h) => ({
    value: h, label: `${String(h).padStart(2, '0')}:00`,
  }))

  async function salveazaSetari() {
    if (pushBusy || !setari) return
    pushBusy = true
    setariEroare = ''
    try {
      // Serverul valideaza si INTOARCE forma normalizata — o folosim pe aia, nu
      // pe cea din formular: altfel un camp corectat de server (numar venit ca
      // text din <input type=number>) ar ramane afisat gresit.
      const salvate = await apiJson('/api/push/setari', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ora: Number(setari.ora), zileVechime: Number(setari.zileVechime),
          scadente: !!setari.scadente, faraTermen: !!setari.faraTermen,
        }),
      })
      setari = salvate
      // Reprogramarea IMEDIAT dupa salvare: altfel alarmele deja puse ar suna la
      // ora veche pana la urmatoarea deschidere a aplicatiei, iar tu ai crede ca
      // setarea n-a prins.
      const d = await apiJson('/api/global-tasks?sfera=personal')
      const cate = await reprogrameaza(Array.isArray(d) ? d : d.tasks || [], salvate)
      toast(`Salvat — ${cate} notificări programate.`, 'success')
    } catch (e) {
      setariEroare = e.message
    } finally { pushBusy = false }
  }

  // Aterizarea din fluxul OAuth: serverul redirectioneaza cu ?google=conectat|
  // eroare. Toast + consumarea parametrului, ca un refresh sa nu re-toasteze.
  $effect(() => {
    const g = router.query.google
    if (!g) return
    if (g === 'conectat') toast('Google Calendar conectat — sincronizarea a pornit.', 'success')
    else toast('Conectarea la Google a eșuat. Verifică logurile serverului.', 'error')
    navigate('/tasks?sfera=personal')
  })

  // Un singur $effect in loc de onMount + load-uri explicite pe chip-uri: ruleaza
  // la montare SI ori de cate ori se schimba sfera (din URL) sau arhiva — trei
  // declansatoare, un singur drum, fara dublu-load.
  $effect(() => { loadGlobalTasks({ arhiva: showArchive, sfera: sferaActiva }) })
</script>

{#snippet taskDetail(t)}
  {@const subs = subtasksCache[t.id] || []}

  <!-- Inauntru raman DOAR subtaskurile (cerinta Ion). Descrierea se deschide din
       butonul de pe rand, langa editare — nu mai imparte extinderea in doua. -->
  <!-- Randul desfasurat = taskul deschis. Subtaskurile plus cele doua actiuni
       rare care au iesit din panoul de glisare (nota si titlul). Asa „atinge
       taskul" inseamna „vezi tot ce e in el", ca in orice aplicatie de to-do,
       in loc sa fie imprastiate pe doua gesturi diferite. -->
  <!-- CHIPURI DE ACTIUNE, ca randul „Description / Reminders / Labels" din
       Todoist: lucrurile pe care le faci RAR cu un task stau grupate si mici,
       ca sa nu concureze cu subtaskurile, care sunt continutul. -->
  <!-- CONTINUTUL INAINTEA BUTOANELOR.
       Aici stateau doua chipuri de actiune DEASUPRA subtaskurilor: deschideai un
       task si primul lucru pe care il vedeai erau doua butoane despre operatii
       rare, nu pasii lui. Nota ca CONTINUT ramane sus (e ce ai scris); nota si
       termenul ca ACTIUNI au coborat sub lista, la 11px. „Editează" a plecat de
       tot — creionul e pe acelasi rand, la 4cm, iar titlul se editeaza de acolo. -->
  {#if t.descriere}
    <div class="td-nota"><RichText value={t.descriere} collapsible maxHeight={140} noToggle /></div>
  {/if}

  <!-- Fara stare de asteptare aici: `taskDetail` se randeaza DOAR cu
       subtaskurile deja in `subtasksCache` (vezi `toggleTaskExpand` si
       `deschideFoaia`). Un „Se încarcă…" care se schimba intr-o sectiune mai
       inalta era exact ruptura pe care o repara ordinea de acolo. -->
  <div class="sub-section">
    <!-- ANTET DE SECTIUNE, ca „Sub-tasks 0/2" la Todoist. In lista nu era nevoie
         de el (extinderea continea doar subtaskuri); in foaie sunt trei lucruri
         unul sub altul, deci sectiunea trebuie sa-si spuna numele. Bara de
         progres sta pe acelasi rand: „1/4" da cifra, bara da distanta. -->
    <div class="sub-cap">
      <span class="sub-cap-t">Subtaskuri</span>
      {#if subs.length}
        {@const gata = subs.filter(s => s.done).length}
        <div class="sub-bara" role="img"
             aria-label="{gata} din {subs.length} subtaskuri făcute">
          <span style="width: {(gata / subs.length) * 100}%"></span>
        </div>
        <span class="sub-num">{gata}/{subs.length}</span>
      {/if}
    </div>

    {#each subs as sub (sub.id)}
      <!-- CEA MAI MARE TINTA FACE LUCRUL CEL MAI DES. Titlul — zona pe care cade
           degetul — pornea REDENUMIREA, adica lucrul cel mai rar; bifarea statea
           intr-un cerc de 26px. Pe desktop `cursor: text` sugera macar ceva, pe
           telefon nu exista hover, deci singurul mod de a afla era sa atingi si
           sa fii surprins. Randul parinte respecta deja regula corecta.
           Acum: atingi randul -> se bifeaza; redenumirea pe APASARE LUNGA.
           Pe desktop nimic nu se schimba — clic pe titlu redenumeste, pubela
           apare la hover. Gestul e o solutie pentru absenta hover-ului, nu o
           imbunatatire universala. -->
      <div class="sub-row" class:sub-done={sub.done} class:gl-sub={ecran.telefon}
           animate:flip={{ duration: motionDuration(DUR_BASE) }} transition:slide|local={{ duration: motionDuration(DUR_BASE) }}
           use:glisare={{ activ: ecran.telefon && editSubId !== sub.id, onAmana: () => removeSubtask(sub) }}>
        <div class="gl-pista-s" aria-hidden="true"><span class="gl-et-s">Șterge</span><span class="gl-ico-s"><SolidIcon name="trash" size={15} /></span></div>
        <div class="gl-fata">
        <button class="check" onclick={() => toggleSubtaskDone(sub)} title={sub.done ? 'Redeschide subtaskul' : 'Bifează subtaskul'}>
          {#if sub.done}<CheckCircle2 size={16} />{:else}<div class="check-empty small"></div>{/if}
        </button>
        {#if editSubId === sub.id}
          <input class="sub-edit" bind:value={editSubTitlu} use:focalizeaza
                 onblur={() => salveazaRedenumirea(sub)}
                 onkeydown={(e) => {
                   if (e.key === 'Enter') e.currentTarget.blur()
                   // `stopPropagation`: altfel Escape urca la backdrop si
                   // inchidea TOATA foaia, nu doar redenumirea. Un strat.
                   else if (e.key === 'Escape') { e.stopPropagation(); editSubId = '' }
                 }} />
        {:else}
          <button class="sub-title" use:apasareLunga={() => incepeRedenumirea(sub)}
                  onclick={() => { if (ecran.telefon) toggleSubtaskDone(sub); else incepeRedenumirea(sub) }}
                  title={ecran.telefon ? 'Atinge ca să bifezi · ține apăsat ca să redenumești' : 'Atinge ca să redenumești'}>{sub.titlu}</button>
        {/if}
        <button class="sub-del" onclick={() => removeSubtask(sub)}
                aria-label="Șterge subtaskul"><SolidIcon name="trash" size={13} /></button>
        </div>
      </div>
    {/each}

    {#if !subs.length}
      <p class="sub-gol">Niciun subtask. Împarte taskul în pași dacă e prea mare.</p>
    {/if}

    <!-- „+ Adaugă subtask" pe toata latimea, ca la Todoist, nu un camp ingust
         cu un buton patrat langa. Campul se deschide la atingere: pana atunci
         randul e o INVITATIE, nu un formular care sta gol pe ecran. -->
    {#if adaugSubLa === t.id}
      <div class="sub-add">
        <input type="text" placeholder="Ce pas urmează?" bind:value={newSubtaskTitle} use:focalizeaza
               onkeydown={(e) => {
                 if (e.key === 'Enter') addSubtask(t.id)
                 // Acelasi motiv ca la redenumire: Escape inchide compozitorul,
                 // nu foaia din jurul lui.
                 else if (e.key === 'Escape') { e.stopPropagation(); adaugSubLa = ''; newSubtaskTitle = '' }
               }} />
        <button class="sub-add-btn" disabled={!newSubtaskTitle.trim()} onclick={() => addSubtask(t.id)}>
          <Plus size={16} />
        </button>
      </div>
    {:else}
      <!-- „+ Adaugă subtask" e ULTIMUL RAND al listei, nu cel mai puternic obiect
           din panou: `+` aliniat pe coloana bifei, text palid, fara chenar punctat. -->
      <button class="sub-nou" onclick={() => { adaugSubLa = t.id; newSubtaskTitle = '' }}>
        <span class="sub-nou-p"><Plus size={14} /></span> Adaugă subtask
      </button>
    {/if}
  </div>

  <!-- Actiunile rare, sub o linie: se gasesc cand le cauti, nu concureaza cu
       subtaskurile, care sunt continutul. -->
  <div class="td-jos">
    <button class="td-link" class:areNota={!!t.descriere} onclick={() => openNoteModal(t)}>
      <Text size={12} strokeWidth={2} /> {t.descriere ? 'Editează nota' : 'Adaugă notă'}
    </button>
    <span class="td-link td-dp">
      <DatePicker value={t.data_scadenta} placeholder="Schimbă termenul" onchange={(v) => setTermenData(t, v)} />
    </span>
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

  <!-- Pe telefon cautarea si filtrele impart UN rand, iar caseta de cautare e
       pliata intr-o iconita pana ceri altceva. Cu ~15 taskuri cauti rar, dar
       campul mananca 60px din ecran de fiecare data — adica un task intreg, sus,
       unde conteaza cel mai mult. Se desface la atingere si primeste focus. -->
  <div class="toolbar">
    <div class="search-box" class:pliata={ecran.telefon && !cautareDeschisa && !taskSearch}>
      {#if ecran.telefon && !cautareDeschisa && !taskSearch}
        <button class="sb-ico" onclick={deschideCautarea} aria-label="Caută taskuri"><Search size={16} /></button>
      {:else}
        <Search size={14} />
        <input type="text" placeholder="Caută taskuri..." bind:value={taskSearch} bind:this={cautareInput}
               onblur={() => { if (!taskSearch) cautareDeschisa = false }} />
      {/if}
    </div>
    <div class="filters">
      <!-- SFERA NU E FILTRU (observatia lui Ion, a doua): Munca/Personal schimba
           IN CE LUME esti, Active/Arhiva alege ce subset vezi din ea. Doua naturi
           diferite, doua haine: sfera e un comutator segmentat (capsula unita,
           segment activ ridicat pe suprafata neutra), filtrele raman chip-uri
           separate cu amber la activ. -->
      <div class="sfere" role="tablist" aria-label="Sfera taskurilor">
        <button class="seg" role="tab" aria-selected={sferaActiva === 'munca'} class:on={sferaActiva === 'munca'} onclick={() => navigate('/tasks')}><Briefcase size={13} />Muncă</button>
        <button class="seg" role="tab" aria-selected={sferaActiva === 'personal'} class:on={sferaActiva === 'personal'} onclick={() => navigate('/tasks?sfera=personal')}><User size={13} />Personal</button>
      </div>
      <!-- „ACTIVE" A PLECAT, „ARHIVĂ" NU MAI E CHIP.
           „Active" era un filtru MEREU pornit: un chip amber care nu spunea nimic,
           dar care lasa nelamurit daca „Arhivă" de langa el ADAUGA sau INLOCUIESTE.
           Iar doua chipuri lipite de capsula segmentata a sferei citeau ca patru
           butoane din care doua sunt altfel din motive care traiau doar in cod.
           Arhiva e o DESTINATIE rara, deci primeste haina de actiune-fantoma —
           aceeasi cu a iconitei Google de langa, care e si ea o setare, nu un filtru.
           Butonul doar schimba starea; $effect-ul reincarca (un singur drum de load). -->
      <button class="a-ico" class:on={showArchive} aria-pressed={showArchive}
              onclick={() => { showArchive = !showArchive }}
              title={showArchive ? 'Înapoi la taskurile active' : 'Vezi arhiva'}>
        <Archive size={15} /><span class="a-et">Arhivă</span>
      </button>
      {#if sferaActiva === 'personal'}
        <!-- NU chip: chip-urile din randul asta sunt FILTRE (Munca/Personal,
             Active/Arhiva), iar asta e o actiune de setari — aceeasi haina
             pentru lucruri diferite ar minti (observatia lui Ion). Sincronizarea
             merge singura; iconita exista ca stare stricata sa aiba unde sa se
             arate (punctul rosu) si ca Resincronizeaza/Deconecteaza sa ramana
             accesibile. -->
        <button class="g-ico" onclick={deschideGoogle} title="Google Calendar — stare sincronizare" aria-label="Google Calendar">
          <CalendarPlus size={15} />
          {#if googleStatus?.last_error}<span class="g-punct" aria-hidden="true"></span>{/if}
        </button>
        <button class="g-ico" onclick={deschidePush} title="Notificări zilnice" aria-label="Notificări">
          <Bell size={15} />
          {#if pushStatus?.last_error}<span class="g-punct" aria-hidden="true"></span>{/if}
        </button>
      {/if}
    </div>
  </div>


  <div class="v3grid">
  <div class="list-cell cell-in">
  <div class="cell-label list-label"><span class="ico ico-amber"><ListTodo size={13} /></span>{showArchive ? 'Taskuri arhivate' : (sferaActiva === 'personal' ? 'Taskuri personale' : 'Lista taskuri')}<span class="tail">{showArchive ? globalTasks.items.length : activeTasks.length}</span></div>
  {#if !showArchive}
    <form class="quick-add" onsubmit={(e) => { e.preventDefault(); quickAdd() }}>
      <div class="qa-rand">
        <input type="text" bind:this={quickInput}
               placeholder={ecran.telefon ? 'Task rapid…' : 'Task rapid... Enter pentru a adăuga'}
               bind:value={quickTitle} disabled={quickAdding} />
        <button type="submit" class="quick-add-btn" disabled={!quickTitle.trim() || quickAdding} title="Adaugă task"><Plus size={16} /></button>
      </div>
      {#if quickTitle.trim()}
        <div class="qa-cand" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
          <button type="button" class="qa-chip" onclick={() => quickAdd(0)}>Azi</button>
          <button type="button" class="qa-chip" onclick={() => quickAdd(1)}>Mâine</button>
          <span class="qa-dp" class:pus={!!quickData}>
            <DatePicker bind:value={quickData} placeholder="Alege data" onchange={(v) => { quickData = v; if (v) quickAdd() }} />
          </span>
          <span class="qa-hint">Enter = fără termen</span>
        </div>
      {/if}
    </form>
  {/if}

  <!-- SCHELETELE SUNT PENTRU PRIMA INCARCARE, NU PENTRU FIECARE ACTIUNE.
       Conditia era doar `globalTasks.loading`, iar `loadGlobalTasks()` se cheama
       dupa ORICE modificare (bifat, mutat termen, adaugat, sters). Deci de fiecare
       data cand atingeai ceva, toata lista era distrusa si inlocuita cu cinci
       dungi gri, apoi reconstruita — o clipire pe fiecare gest.
       Efect secundar care m-a costat o ora: nicio animatie de iesire nu se putea
       vedea, fiindca subarborele ei era demolat in aceeasi clipa. Un rand nu apuca
       sa plece elegant dintr-o lista care tocmai a fost stearsa toata.
       `&& items.length === 0`: schelete doar cand chiar n-ai ce arata. Aceeasi
       regula o avea deja TodayBoard. -->
  {#if globalTasks.loading && globalTasks.items.length === 0}
    <div class="list">{#each Array(5) as _}<div class="task-skeleton"><Skeleton width="70%" height="16px" /></div>{/each}</div>
  {:else if globalTasks.error}
    <ErrorState message={globalTasks.error} onretry={() => reload()} />
  {:else if globalTasks.items.length === 0}
    <!-- Aceeasi stare acopera „n-ai avut niciodata taskuri" si „tocmai le-ai
         terminat pe toate" — pagina nu le poate deosebi, fiindca API-ul nu-i da
         cele bifate. Deci textul trebuie sa fie adevarat in amandoua si sa spuna
         unde au plecat cele facute, altfel „Niciun task" se citeste ca o pierdere. -->
    <EmptyState icon={ListTodo} title={showArchive ? 'Arhiva e goală' : (sferaActiva === 'personal' ? 'Niciun task personal' : 'Nimic de făcut')} description={showArchive ? 'Aici ajung taskurile bifate.' : 'Scrie un task în câmpul de sus. Ce ai terminat e în „Arhivă".'} />
  {:else}
    <div class="task-list">
      <!-- Se itereaza ORDINEA — siruri constante — nu lista de grupe.
           Vezi `lib/grupare.js`: un each imbricat peste obiecte NOI la fiecare
           recalcul face Svelte sa re-creeze blocul interior in loc sa-l
           actualizeze, iar randurile dinauntru sunt distruse fara sa-si joace
           iesirea. Masurat: 0 cadre de animatie asa, 13 cu acelasi rand intr-un
           each de nivel superior. Cu chei constante, blocul exterior nu se mai
           schimba niciodata. -->
      {#each ordine as gid (gid)}
      {#if grupe[gid]}
      {#if grupe[gid].titlu && grupe[gid].items.length}
        <!-- Capul de grupa e reperul dupa care citesti lista fara sa citesti
             fiecare rand: vezi „Restante 2" si stii ca ai doua de recuperat. -->
        <div class="grup-cap ton-{grupe[gid].ton}"><span class="grup-t">{grupe[gid].titlu}</span><span class="grup-n">{grupe[gid].items.length}</span></div>
      {/if}
      {#each grupe[gid].items as t (t.id)}
<!-- Iesirea randului bifat: se stinge si se strange, in loc sa sara.
               Vezi `plecare` in lib/motion.svelte.js. -->
                    <div class="trow-wrap" class:deschis={expandedTask === t.id}
             style="--ring: {dueRing(t.data_scadenta)}"
             animate:flip={{ duration: motionDuration(DUR_BASE) }}
             onpointerenter={() => preincarca(t.id)}
             in:sosire|local out:plecare>
          <div class="trow" class:done={t.status === 'done'} use:focusOnLand={focusKey('global', t.id)}
               use:glisare={{ activ: ecran.telefon, onBifa: t.status === 'done' ? null : () => toggleStatus(t), onAmana: () => { deschideFoaia(t.id); termenDeschis = true } }}>
            <!-- Actiunile de intretinere (notita / editare / stergere) stau in
                 panoul de sub rand: sunt rare fata de „bifat" si „deschis", si
                 tocmai ele umflau randul cu o linie intreaga. -->
            <!-- UN GEST = UN VERB, IN AMBELE SENSURI.
                 Aici era un panou de patru actiuni × 58px = 232px din 390: taskul pe
                 care actionai dispare aproape complet de sub deget, deci nu mai stii
                 pe ce apesi — si „Șterge", ultimul, cadea exact unde ajunge o glisare
                 rapida. Pe langa asta, cele doua direcii aveau doua modele diferite
                 (stanga „deschide un meniu", dreapta „executa"), deci se invatau
                 separat. Acum stanga e „Mâine" — amanarea e a doua actiune ca
                 frecventa, dupa bifare — cu aceeasi pista progresiva ca „Făcut".
                 NU muta pe mâine de la sine (observatia lui Ion): pe /tasks termenele
                 sunt imprastiate pe saptamani, deci un „mâine" implicit ar fi o zi
                 aleasa de aplicatie. Gestul deschide foaia cu panoul de termen deja
                 desfacut — Azi / Mâine / Alege ziua / Scoate — adica alegi tu, dar
                 dintr-un singur gest. Stergerea ramane in foaie. -->
            <div class="gl-pista" aria-hidden="true"><span class="gl-ico"><Check size={17} strokeWidth={3} /></span><span class="gl-et">Făcut</span></div>
            <div class="gl-pista-s" aria-hidden="true"><span class="gl-et-s">Planifică</span><span class="gl-ico-s"><CalendarDays size={17} strokeWidth={2.4} /></span></div>
            <div class="gl-fata">
            <button class="check" onclick={() => toggleStatus(t)} title={t.status === 'done' ? 'Redeschide' : 'Marchează ca făcut'}>
              {#if t.status === 'done'}<CheckCircle2 size={18} />{:else}<div class="check-empty"></div>{/if}
            </button>
            <button class="tmain" onclick={() => toggleTaskExpand(t.id)}>
              <div class="ttitle-row">
                <!-- Sageata de desfasurare doar pe desktop. Pe telefon „atingi
                     randul si se deschide" e conventia, nu are nevoie de indiciu;
                     iar sageata mananca 20px din titlu pe fiecare rand. -->
                <span class="tchev">{#if expandedTask === t.id}<ChevronDown size={14} />{:else}<ChevronRight size={14} />{/if}</span>
                <span class="ttitle">{t.titlu}</span>
              </div>
              <!-- ORDINEA E CEA DIN TODOIST, adaptata (cerinta Ion).
                   Intai CAND (termenul, cu iconita de calendar si culoarea
                   severitatii), apoi CAT (subtaskurile, cu iconita lor), apoi
                   semnele mici; iar categoria pleaca la capatul din dreapta, unde
                   Todoist tine proiectul. Motivul ordinii: pe un rand citit din
                   mers, prima informatie trebuie sa fie cea care decide daca te
                   ocupi acum de el — termenul. Categoria nu decide nimic, deci sta
                   ultima si aliniata la dreapta, unde ochiul o gaseste cand o
                   cauta si o sare cand nu.
                   „acum 3 zile" / „vineri", nu „27.07.2026": o data plina te pune
                   sa calculezi in cap cate zile mai ai, la fiecare rand. Si nu se
                   scrie deloc acolo unde capul de grupa a spus-o deja („Azi",
                   „Mâine", „Fără termen") — repetat pe fiecare rand ar fi zgomot. -->
              <div class="tinfo">
                {#if chipTermen(t, gid)}
                  <span class="tdeadline" class:sev={isOverdue(t.data_scadenta) || isToday(t.data_scadenta)}>
                    <CalendarDays size={11} />{chipTermen(t, gid)}
                  </span>
                {/if}
                {#if t.subtask_total}
                  <span class="tsub-chip" class:gata={t.subtask_done === t.subtask_total}
                        title="{t.subtask_done || 0} din {t.subtask_total} subtaskuri făcute">
                    <ListChecks size={11} />{t.subtask_done || 0}/{t.subtask_total}
                  </span>
                {/if}
                {#if t.descriere}<span class="note-ind" title="Are notiță"><Text size={11} strokeWidth={2.2} /></span>{/if}
                {#if t.recurenta}<span class="recur-badge" title="Recurent: {t.recurenta}"><Repeat size={10} /> {t.recurenta}</span>{/if}
                <!-- „General" nu se scrie: e valoarea implicita, deci apare pe
                     jumatate din randuri fara sa deosebeasca nimic de nimic. -->
                {#if t.categorie && t.categorie !== 'General'}<span class="task-cat">{t.categorie}</span>{/if}
              </div>
            </button>
            <div class="task-actions">
              <!-- REPLANIFICAREA, DAR NU UN „MÂINE" GHICIT (observatia lui Ion).
                   Pe desktop nu exista niciun drum scurt pentru a doua actiune ca
                   frecventa dintr-o lista de facut — deschideai modalul de editare.
                   Un buton „Mâine" fix ar fi insa raspunsul greset AICI: pe /tasks
                   termenele sunt imprastiate pe saptamani, deci „mâine" e o zi
                   aleasa de aplicatie, nu de tine. Pe boardul „Astăzi" e alta
                   situatie — acolo tot ce vezi e scadent azi si butonul „Mâine"
                   ramane. Aici calendarul deschide direct alegerea zilei. -->
              <span class="task-dp" title="Planifică — alege ziua">
                <DatePicker value={t.data_scadenta} onchange={(v) => setTermenData(t, v)} />
              </span>
              <!-- Trei linii de text, nu o pagina plina cu colt indoit: la 12px
                   pagina solida e o pata, iar aceeasi forma o purta si „fisier".
                   Liniile spun „aici e text scris" si nu se confunda cu creionul
                   de langa, care spune „schimba". -->
              <button class="task-edit" onclick={() => openNoteModal(t)}
                      title={t.descriere ? 'Editează descrierea' : 'Adaugă descriere'}
                      class:areNota={!!t.descriere}><Text size={13} strokeWidth={2} /></button>
              <button class="task-edit" onclick={() => openEditModal(t)} title="Editează task"><SolidIcon name="pencil" size={12} /></button>
              <button class="task-del" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Șterge task"><SolidIcon name="trash" size={13} /></button>
            </div>
            </div>
          </div>
          <!-- Pe desktop taskul se desface AICI, in lista. Acelasi `taskDetail` ca
               in foaia de pe telefon, deci designul e identic — se schimba doar
               unde e asezat. -->
          {#if expandedTask === t.id}
            <div class="subtask-body" transition:desfacere={{ duration: motionDuration(DUR_BASE) }}>
              {@render taskDetail(t)}
            </div>
          {/if}
        </div>
      {/each}
      {/if}
      {/each}

    </div>
  {/if}
  </div>
  </div>
</div>

<!-- FOAIA TASKULUI (doar pe telefon — vezi `toggleTaskExpand`).
     `Modal` e deja sertar lipit de marginea de jos pe telefon, deci foaia nu e o
     componenta noua, e acelasi modal cu alt continut. -->
{#if sheetTask}
  <!-- Antetul modalului primeste CONTEXTUL taskului (categoria), ca „Inbox" la
       Todoist. Fara titlu, `Modal` randa oricum bara cu butonul de inchidere, deci
       ramanea o banda goala de ~60px deasupra taskului — spatiu platit degeaba,
       exact acolo unde ochiul cade prima data. -->
  <Modal bind:open={showSheet} size="md" title={sheetTask.categorie || 'Task'}>
    <!-- Foaia poarta `--ring` pe cap: bifa mare e primul lucru din foaie, deci e
         chiar locul unde severitatea trebuie sa se vada. -->
    <div class="ts-cap" style="--ring: {dueRing(sheetTask.data_scadenta)}">
      <button class="ts-check" onclick={() => { toggleStatus(sheetTask); showSheet = false }}
              aria-label={sheetTask.status === 'done' ? 'Redeschide' : 'Marchează ca făcut'}>
        {#if sheetTask.status === 'done'}<CheckCircle2 size={24} />{:else}<div class="check-empty big"></div>{/if}
      </button>
      <h2 class="ts-titlu" class:gata={sheetTask.status === 'done'}>{sheetTask.titlu}</h2>
    </div>

    <!-- TERMENUL, UN SINGUR RAND — ca la Todoist („📅 28 Feb 11:00"), nu un bloc.
         Prima varianta lasa cele patru actiuni desfacute permanent: pe 390px se
         rupeau pe doua randuri, calendarul lua jumatate de latime si `×`-ul
         ramanea singur pe randul al doilea. Un panou de replanificare deschis tot
         timpul plateste spatiu pentru ceva ce faci O DATA per deschidere.
         Acum randul ARATA data; atingerea lui desface actiunile dedesubt. -->
    <button class="ts-rand" class:activ={termenDeschis}
            onclick={() => termenDeschis = !termenDeschis}>
      <CalendarDays size={16} />
      {#if sheetTask.data_scadenta}
        <span class="ts-val" style="--ring: {dueRing(sheetTask.data_scadenta)}"
              class:sev={isOverdue(sheetTask.data_scadenta) || isToday(sheetTask.data_scadenta)}>{etichetaTermen(sheetTask.data_scadenta)}</span>
      {:else}<span class="ts-val ts-fara">Fără termen</span>{/if}
      <ChevronDown size={15} class="ts-chev" />
    </button>
    {#if termenDeschis}
      <div class="ts-zile" transition:slide|local={{ duration: motionDuration(DUR_FAST) }}>
        <button class="ts-zi" onclick={() => { setTermen(sheetTask, 0); termenDeschis = false }}>Azi</button>
        <button class="ts-zi" onclick={() => { setTermen(sheetTask, 1); termenDeschis = false }}>Mâine</button>
        <span class="ts-zi ts-data"><DatePicker value={sheetTask.data_scadenta} placeholder="Alege"
              onchange={(v) => { setTermenData(sheetTask, v); termenDeschis = false }} /></span>
        {#if sheetTask.data_scadenta}
          <button class="ts-zi ts-scoate" onclick={() => { setTermen(sheetTask, null); termenDeschis = false }}>
            <X size={14} /> Scoate
          </button>
        {/if}
      </div>
    {/if}

    {@render taskDetail(sheetTask)}
  </Modal>
{/if}

<Modal bind:open={showNewModal} title="Task Nou" size="md">
  <form class="task-form" onsubmit={(e) => { e.preventDefault(); handleCreate() }}>
    <Input label="Titlu" bind:value={formTitle} placeholder="Ce ai de făcut?" />
    <Textarea label="Descriere" bind:value={formDesc} placeholder="Detalii (opțional)" rows={3} />
    <div class="form-row-2">
      <!-- Componentele librariei, nu campuri de mana: regula din CLAUDE.md
           („NU <input> brut in formulare"). Categoria era singurul camp brut
           din modal — fara focus-ring-ul si fara fontul de 16px pe telefon pe
           care Input le aduce singur. -->
      <Input label="Categorie" bind:value={formCategory} placeholder="General" />
      <DatePicker label="Termen" bind:value={formDeadline} />
    </div>
    <Select label="Recurență" size="sm" bind:value={formRecurenta} options={[{ value: '', label: 'Fără' }, { value: 'zilnic', label: 'Zilnic' }, { value: 'saptamanal', label: 'Săptămânal' }, { value: 'lunar', label: 'Lunar' }]} />
  </form>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showNewModal = false}>Anulează</Button>
      <Button loading={creating} disabled={!formTitle.trim()} onclick={handleCreate}>Creează</Button>
    </div>
  {/snippet}
</Modal>

<Modal bind:open={showEditModal} title="Editează Task" size="md">
  <form class="task-form" onsubmit={(e) => { e.preventDefault(); handleEdit() }}>
    <Input label="Titlu" bind:value={formTitle} placeholder="Titlu task" />
    <Textarea label="Descriere" bind:value={formDesc} placeholder="Detalii (opțional)" rows={3} />
    <div class="form-row-2">
      <!-- Componentele librariei, nu campuri de mana: regula din CLAUDE.md
           („NU <input> brut in formulare"). Categoria era singurul camp brut
           din modal — fara focus-ring-ul si fara fontul de 16px pe telefon pe
           care Input le aduce singur. -->
      <Input label="Categorie" bind:value={formCategory} placeholder="General" />
      <DatePicker label="Termen" bind:value={formDeadline} />
    </div>
    <Select label="Recurență" size="sm" bind:value={formRecurenta} options={[{ value: '', label: 'Fără' }, { value: 'zilnic', label: 'Zilnic' }, { value: 'saptamanal', label: 'Săptămânal' }, { value: 'lunar', label: 'Lunar' }]} />
  </form>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => showEditModal = false}>Anulează</Button>
      <Button loading={creating} disabled={!formTitle.trim()} onclick={handleEdit}>Salvează</Button>
    </div>
  {/snippet}
</Modal>

<ConfirmDialog bind:open={showTaskDelete} title="Șterge task" message="Ștergi acest task? Toate subtaskurile asociate vor fi șterse." confirmLabel="Șterge" onconfirm={doDeleteTask} />

<!-- Titlul e TASKUL, nu „Notițe — <task>": ai deschis nota DIN el, deci prefixul
     spunea ce se vede oricum, si tocmai el facea randul sa se taie. Antetul e o
     linie de context (vezi `.modal-doc .modal-title` in Modal.svelte).
     `tools="nota"`: sapte unelte, nu treisprezece — vezi RichTextEditor.
     `onclose`: X / fundal / Escape salveaza, ca si butonul. -->
<Modal bind:open={showNoteModal} onclose={saveNote} size="doc"
       title={noteTask ? noteTask.titlu : 'Notiță'}>
  <div class="note-modal">
    {#if showNoteModal}
      <RichTextEditor bind:value={noteDraft} variant="doc" tools="nota"
                      placeholder="Scrie notițe pentru acest task…" onsave={saveNote} />
    {/if}
  </div>
  {#snippet footer()}
    <div class="modal-actions">
      <Button loading={noteSaving} onclick={saveNote}>Gata</Button>
    </div>
  {/snippet}
</Modal>

<!-- Sincronizarea cu Google Calendar (doar sfera personala). Trei stari:
     neconfigurat (doar fallback .ics), configurat-neconectat (buton OAuth),
     conectat (stare + resincronizare/deconectare). -->
<Modal bind:open={showGoogleModal} title="Google Calendar" size="sm">
  {#if googleStatus === null}
    <div class="g-skel"><Skeleton width="80%" height="14px" /><Skeleton width="60%" height="14px" /></div>
  {:else if !googleStatus.configurat || schimbCred}
    <p class="g-text">Lipește mai jos conținutul fișierului JSON descărcat din Google Cloud
      Console (clientul OAuth de tip „Web application”). Se salvează pe server și nu intră
      în backup-uri.</p>
    <Textarea label="JSON-ul descărcat de la Google" bind:value={credText} rows={4}
              placeholder={'{"web": {"client_id": "...", "client_secret": "..."}}'} />
    <div class="g-actiuni">
      <Button loading={credSaving} disabled={!credText.trim()} onclick={salveazaCred}>Salvează</Button>
      {#if schimbCred}
        <Button variant="secondary" onclick={() => { schimbCred = false; credText = '' }}>Anulează</Button>
      {:else}
        <Button variant="secondary" onclick={copiazaLinkIcs}>Copiază link .ics</Button>
      {/if}
    </div>
  {:else if !googleStatus.conectat}
    <p class="g-text">Conectează-ți contul Google: taskurile personale cu termen apar în
      calendarul „PIF Personal” în momentul în care le setezi.</p>
    {#if googleStatus.last_error}<p class="g-eroare">{googleStatus.last_error}</p>{/if}
    <div class="g-actiuni">
      <Button onclick={() => { window.location.href = '/oauth/google/start' }}>Conectează cu Google</Button>
      <Button variant="secondary" onclick={copiazaLinkIcs}>Copiază link .ics</Button>
      {#if googleStatus.sursa === 'setari'}
        <button class="g-link" onclick={() => { schimbCred = true }}>Schimbă credențialele</button>
      {/if}
    </div>
  {:else}
    <div class="g-stare">
      <div class="g-rand"><span class="g-et">Calendar</span><span class="g-val">{googleStatus.calendar || 'PIF Personal'}</span></div>
      <div class="g-rand"><span class="g-et">Ultima sincronizare</span><span class="g-val">{googleStatus.last_sync ? formatDate(googleStatus.last_sync) : '—'}</span></div>
      {#if googleStatus.last_error}<p class="g-eroare">{googleStatus.last_error}</p>{/if}
    </div>
  {/if}
  {#snippet footer()}
    {#if googleStatus?.configurat && googleStatus?.conectat}
      <div class="modal-actions">
        <Button variant="secondary" disabled={googleBusy} onclick={resyncGoogle}>Resincronizează</Button>
        <Button variant="danger" onclick={() => showGoogleDisconnect = true}>Deconectează</Button>
      </div>
    {/if}
  {/snippet}
</Modal>

<ConfirmDialog bind:open={showGoogleDisconnect} title="Deconectează Google Calendar"
               message="Se deconectează de la Google. Evenimentele deja create rămân în calendar."
               confirmLabel="Deconectează" onconfirm={disconnectGoogle} />

<!-- Notificările zilnice. Aceeași scară în trepte ca modalul Google:
     indisponibil pe server → browser nesuportat → permisiune refuzată →
     neabonat → abonat. -->
<Modal bind:open={showPushModal} title="Notificări" size="sm">
  <!-- IN APLICATIA DE PE TELEFON, NIMIC DIN ASTA NU MAI TRECE PRIN SERVER.
       Alarma o pune Android, din timp, deci starea de abonament push de mai jos
       n-are niciun inteles aici — ar arata o masinarie care nu mai e folosita. -->
  {#if esteNativ()}
    <p class="g-text">Aici alarma o pune telefonul, din timp — nu vine de pe server, deci nu
      depinde nici de rețea, nici de starea aplicației în momentul în care sună.</p>
    {#if setari}
      <!-- Setarile stau pe SERVER, nu pe telefon: le vezi si le schimbi si din
           browser, si supravietuiesc unei reinstalari a aplicatiei. -->
      <div class="n-setari">
        <Select label="Ora" bind:value={setari.ora} options={oreDisponibile} size="sm" />
        <Input label="Fără termen, după (zile)" type="number" min="0" max="60"
               bind:value={setari.zileVechime} />
        <label class="n-comutator">
          <input type="checkbox" bind:checked={setari.scadente} />
          <span>Taskurile scadente, în dimineața zilei</span>
        </label>
        <label class="n-comutator">
          <input type="checkbox" bind:checked={setari.faraTermen} />
          <span>Taskurile fără termen, în fiecare dimineață</span>
        </label>
        {#if setariEroare}<p class="g-eroare">{setariEroare}</p>{/if}
      </div>
    {:else}
      <div class="g-skel"><Skeleton width="70%" height="14px" /><Skeleton width="50%" height="14px" /></div>
    {/if}
  {:else if pushStatus === null}
    <div class="g-skel"><Skeleton width="80%" height="14px" /><Skeleton width="60%" height="14px" /></div>
  {:else if !pushStatus.disponibil}
    <p class="g-text">Notificările nu sunt disponibile pe server (lipsește pachetul
      <span class="g-mono">pywebpush</span>). Verifică logurile de deploy.</p>
  {:else if !suportaPush()}
    <p class="g-text">
      {#if esteIosNeinstalat()}
        Pe iPhone notificările merg doar din aplicația instalată: Distribuie →
        „Adaugă la ecranul principal”, deschide-o de acolo și revino aici.
      {:else}
        Browserul ăsta nu suportă notificări push.
      {/if}
    </p>
  {:else if pushLocal?.permisiune === 'denied'}
    <p class="g-text">Notificările sunt blocate pentru site. Deblochează-le din setările
      browserului (lacătul din bara de adresă → Notificări) și revino aici.</p>
  {:else if !pushLocal?.abonat}
    <p class="g-text">Un task personal care stă fără termen mai mult de {'2'} zile îți trimite
      dimineața, la {pushStatus.ora}, o notificare proprie — cu titlul lui și cu butoanele
      „Făcut” și „Azi” direct pe notificare (pe Android; pe iPhone atingerea deschide taskul).</p>
    {#if pushStatus.last_error}<p class="g-eroare">{pushStatus.last_error}</p>{/if}
    <div class="g-actiuni">
      <Button loading={pushBusy} onclick={activeazaPush}>Activează pe telefonul ăsta</Button>
    </div>
  {:else}
    <div class="g-stare">
      <div class="g-rand"><span class="g-et">Dispozitive abonate</span><span class="g-val">{pushStatus.abonamente}</span></div>
      <div class="g-rand"><span class="g-et">Ora</span><span class="g-val">{pushStatus.ora}</span></div>
      <div class="g-rand"><span class="g-et">Regula</span><span class="g-val">{pushStatus.regula}</span></div>
      {#if pushStatus.last_error}<p class="g-eroare">{pushStatus.last_error}</p>{/if}
    </div>
  {/if}
  {#snippet footer()}
    {#if esteNativ()}
      <div class="modal-actions">
        <Button variant="secondary" disabled={pushBusy} onclick={probaLocala}>Notificare de probă</Button>
        <Button disabled={pushBusy || !setari} onclick={salveazaSetari}>Salvează</Button>
      </div>
    {:else if pushStatus?.disponibil && pushLocal?.abonat}
      <div class="modal-actions">
        <Button variant="secondary" disabled={pushBusy} onclick={testPush}>Trimite test</Button>
        <Button variant="danger" disabled={pushBusy} onclick={dezactiveazaPush}>Dezactivează aici</Button>
      </div>
    {/if}
  {/snippet}
</Modal>

<style>
  .page { padding: var(--space-lg); }
  /* Vezi Projects.svelte: fara `flex-wrap`/`gap` antetul nu se poate rupe si
     butonul iese din ecran, unde `overflow-x: clip` il taie fara sa spuna nimic. */
  .page-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); flex-wrap: wrap; margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); min-width: 0; }
  .page-title-row h1 { font-size: var(--font-title); font-weight: var(--fw-semibold); }
  /* `.count` a plecat in global.css. E NEUTRA acum, nu amber: numarul de langa
     titlul paginii spune cate SUNT, iar accentul e rezervat pentru „cate sunt de
     facut aici" (backlog, tabul de taskuri al proiectului). */

  .toolbar { display: flex; gap: var(--space-md); align-items: center; margin-bottom: var(--space-md); flex-wrap: wrap; }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 6px 12px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-full); color: var(--text-dim); flex: 1; max-width: 280px; }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; box-shadow: none; }
  .search-box input::placeholder { color: var(--text-dim); }
  .search-box:focus-within { border-color: var(--accent); box-shadow: var(--focus-ring); }
  /* Compozitorul are DOUA randuri acum (camp + chipuri de zi), deci coloana.
     Cat timp era `flex-direction: row`, chipurile se asezau LANGA camp, ieseau
     din ecran, iar campul se intindea pe inaltimea lor. */
  .quick-add { display: flex; flex-direction: column; margin-bottom: var(--space-md); }
  .quick-add input { flex: 1; min-height: 40px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); }
  .quick-add input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .filters { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
  /* ARHIVA — ACTIUNE-FANTOMA, NU CHIP. Aici erau doua chipuri („Active"/„Arhivă"),
     din care unul era mereu pornit. Ramane un singur buton, cu haina iconitei
     Google de langa el: si aceea e o setare, nu un filtru. Activ = tinta amber,
     ca sa se vada din bara in ce lista te uiti. */
  .a-ico { display: inline-flex; align-items: center; gap: 6px; min-height: 30px;
    padding: 0 10px; border: none; background: none; border-radius: var(--radius-sm);
    color: var(--text-faint); font-size: var(--font-small); font-weight: var(--fw-medium);
    cursor: pointer; transition: var(--transition-colors); }
  .a-ico:hover { color: var(--text); background: var(--bg-hover); }
  .a-ico.on { color: var(--accent-on-subtle); background: var(--accent-subtle); }
  .a-ico:active { transform: scale(var(--press-scale)); }
  /* Comutatorul de sfera — capsula unita cu segment activ RIDICAT pe suprafata
     neutra (nu amber: amber la activ e limbajul FILTRELOR de langa el). Punctul
     violet de pe Personal (--purple, huea „libera") e acelasi cu cel din antetul
     sectiunii „Personal" de pe Acasa — cele doua suprafete se refera una la alta.
     Randurile raman identice — severitatea e singura culoare pe rand. */
  .sfere { display: flex; background: var(--bg-input); border: 1px solid var(--border);
           border-radius: var(--radius-full); padding: 2px; flex-shrink: 0; margin-right: 4px; }
  .seg { display: inline-flex; align-items: center; gap: 6px; padding: 2px 12px; min-height: 24px; border: none; background: none; cursor: pointer;
         border-radius: var(--radius-full); font-size: var(--font-small); font-weight: var(--fw-medium);
         color: var(--text-dim); transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease); }
  .seg:hover { color: var(--text); }
  .seg.on { background: var(--bg-elevated); color: var(--text); box-shadow: var(--shadow-sm); }
  /* SFERA SE DEOSEBESTE PRIN SEMN, NU PRIN CULOARE.
     Aici era un punct violet lipit inaintea lui „Personal": o bulina decorativa
     care aducea a treia culoare pe o bara unde amberul insemna deja „activ", iar
     violetul nu insemna nimic in afara acestui punct. Iconita spune acelasi lucru
     CAT TIMP nu e activ segmentul (bulina se citea greu pe segmentul stins) si e
     acelasi semn cu cel din antetul „Personal" de pe Acasa — cele doua suprafete
     se refera in continuare una la alta, doar c-o fac cu un desen, nu cu o culoare. */
  /* Iconita Google — fantoma, nu chip: chip-urile din toolbar sunt filtre, iar
     asta e o intrare de setari. Punctul rosu apare doar cand sync-ul are o
     problema — singurul moment in care merita atentie. */
  .g-ico { position: relative; display: flex; align-items: center; justify-content: center;
           width: 30px; min-height: 30px; background: none; border: none; cursor: pointer;
           color: var(--text-faint); border-radius: var(--radius-sm);
           transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease); }
  .g-ico:hover { color: var(--text); background: var(--bg-hover); }
  .g-punct { position: absolute; top: 4px; right: 4px; width: 6px; height: 6px;
             border-radius: 50%; background: var(--danger); }

  /* Modalul Google Calendar — text de stare, nu formular. */
  .g-skel { display: flex; flex-direction: column; gap: var(--space-sm); }
  .g-text { font-size: var(--font-small); color: var(--text-secondary); line-height: var(--lh-normal); }
  .g-mono { font-family: var(--font-mono); font-size: var(--font-small); color: var(--text); }
  .g-actiuni { display: flex; flex-wrap: wrap; gap: var(--space-sm); margin-top: var(--space-md); }
  .g-stare { display: flex; flex-direction: column; gap: var(--space-xs); }
  .g-rand { display: flex; justify-content: space-between; gap: var(--space-md); font-size: var(--font-small); }
  .g-et { color: var(--text-dim); }
  .g-val { font-family: var(--font-mono); font-size: var(--font-small); color: var(--text); }
  .g-eroare { font-size: var(--font-small); color: var(--danger); margin-top: var(--space-sm); }
  .g-link { font-size: var(--font-small); color: var(--text-dim); background: none; border: none;
            cursor: pointer; text-decoration: underline; padding: 0; align-self: center; }
  .g-link:hover { color: var(--text); }

  /* SETARILE DE NOTIFICARI. Fara haina proprie: campurile sunt `Input`/`Select`
     din aceeasi trusa ca peste tot, iar aici raman doar asezarea si comutatoarele.
     Doua coloane pe latime, o coloana pe telefon — ora si pragul sunt scurte si
     ar arata pierdute pe un rand intreg. */
  .n-setari { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: var(--space-sm) var(--space-md); margin-top: var(--space-sm); }
  /* Comutatoarele sunt propozitii, nu campuri: tin toata latimea si se citesc
     ca o fraza, ca sa se vada CE se opreste, nu doar ca exista un buton. */
  .n-comutator { grid-column: 1 / -1; display: flex; align-items: center; gap: var(--space-sm);
                 font-size: var(--font-small); color: var(--text-secondary);
                 min-height: var(--tap-min); cursor: pointer; }
  .n-comutator input { width: 18px; height: 18px; flex: none; accent-color: var(--accent);
                       cursor: pointer; }
  .n-setari :global(.g-eroare) { grid-column: 1 / -1; }
  @media (max-width: 620px) {
    .n-setari { grid-template-columns: 1fr; }
  }
  /* Chipurile de status si prioritate au plecat in v34: taskul e facut sau nu,
     iar severitatea se citeste din bordura din stanga, dupa termen. */

  /* ===== capul de grupa =====
     Nu e un titlu de sectiune, e un reper de citire: cat te uiti in jos pe lista,
     el iti spune in ce zi esti. De aceea e mic, monospace si LIPIT de ecran
     (`sticky`) — grupa „Restante" trebuie sa scrie „Restante" si cand esti la al
     saselea rand al ei. */
  .grup-cap { position: sticky; top: 0; z-index: 2;
    display: flex; align-items: center; gap: var(--space-xs);
    padding: 10px 2px 5px; margin-top: var(--space-xs);
    background: linear-gradient(var(--bg-surface) 72%, transparent);
    font-family: var(--font-mono); font-size: var(--font-label);
    font-weight: var(--fw-semibold); text-transform: uppercase;
    letter-spacing: var(--tracking-label); color: var(--text-faint); }
  .grup-cap:first-child { margin-top: 0; }
  .grup-n { display: inline-flex; align-items: center; justify-content: center;
    min-width: 17px; height: 17px; padding: 0 5px; border-radius: var(--radius-full);
    background: var(--bg-elevated); color: var(--text-dim);
    font-size: var(--font-small); line-height: 1; font-variant-numeric: tabular-nums; }
  /* Tonul repeta EXACT limbajul de culoare al inelului bifei si al termenului
     (`dueRing`), ca sa nu inveti doua coduri pentru acelasi lucru. */
  .grup-cap.ton-danger { color: var(--danger); }
  .grup-cap.ton-danger .grup-n { background: var(--danger-subtle); color: var(--danger); }
  .grup-cap.ton-accent { color: var(--accent); }
  .grup-cap.ton-accent .grup-n { background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .grup-cap.ton-warning { color: var(--warning); }

  /* ===== compozitorul ===== */
  .qa-rand { display: flex; gap: var(--space-sm); }
  .qa-cand { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 8px 2px 0; }
  .qa-chip { padding: 5px 14px; border-radius: var(--radius-full);
    background: var(--bg-elevated); border: 1px solid var(--border);
    color: var(--text-secondary); font-size: var(--font-small);
    font-weight: var(--fw-medium); cursor: pointer;
    transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .qa-chip:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-subtle); }
  .qa-dp :global(.dp-trigger) { min-height: 30px; padding: 4px 12px;
    border-radius: var(--radius-full); font-size: var(--font-small); }
  .qa-hint { font-size: var(--font-small); color: var(--text-faint); margin-left: auto; }

  /* ===== randul desfasurat ===== */
  /* Cele doua actiuni rare, SUB continut si la 11px: chipurile de dinainte stateau
     deasupra subtaskurilor si erau primul lucru pe care il vedeai la deschiderea
     unui task. O linie punctata le separa de lista fara sa deseneze o a doua cutie. */
  .td-jos { display: flex; align-items: center; gap: var(--space-md);
    margin-top: var(--space-sm); padding-top: var(--space-sm);
    border-top: 1px dashed var(--border-subtle); }
  .td-link { display: inline-flex; align-items: center; gap: 6px; padding: 0;
    background: none; border: none; color: var(--text-faint);
    font-size: var(--font-small); cursor: pointer; transition: var(--transition-colors); }
  .td-link:hover { color: var(--accent); }
  .td-link.areNota { color: var(--text-dim); }
  /* DatePicker-ul isi aduce caseta de camp; aici trebuie sa arate ca vecinul lui —
     un link, nu un input. */
  .td-dp :global(.dp) { width: auto; }
  .td-dp :global(.dp-trigger) { min-height: 0; padding: 0; gap: 6px;
    background: none; border: none; box-shadow: none; border-radius: 0;
    color: var(--text-faint); font-size: var(--font-small); }
  .td-dp :global(.dp-trigger:hover) { color: var(--accent); background: none; }
  .td-nota { margin-bottom: var(--space-sm); font-size: var(--font-small); color: var(--text-secondary); }

  .task-list { display: flex; flex-direction: column; }
  /* MUCHIA DE SEVERITATE A PLECAT — severitatea e pe inelul bifei (`--ring`) si
     pe textul termenului. Cei 2px pierduti de la bordura se intorc in padding,
     ca lista sa nu se decaleze fata de capetele de grupa. */
  .trow-wrap { display: flex; flex-direction: column; background: var(--bg-panel);
    border: 1px solid var(--border); padding-left: 2px;
    border-radius: var(--radius-md); margin-bottom: 6px; overflow: hidden;
    transition: border-color var(--dur-fast) var(--ease); }
  /* Fara reafirmare de `border-left-color`: nu mai exista culoare rezervata pe
     bordura, deci `border-color` scurt n-are ce sa stearga. */
  .trow-wrap:hover { border-color: var(--border-strong); }
  /* UN SINGUR obiect: rama, fundalul si colturile stau pe WRAPPER. Randul si
     extinderea sunt continutul lui, fara rame proprii — altfel se citeau ca doua
     cutii lipite („de parca sunt rupte in doua"). */
  /* Tranzitia acopera si `transform`: acelasi rand exista pe Acasa (.arow) si in
     pagina de proiect, unde deplasarea de hover se face lin — aici lipsea din
     lista si randul SAREA 4px la intrarea cursorului. Doua liste cu acelasi rand
     n-au voie sa raspunda diferit la acelasi gest. */
  /* Ion: „poti face putin mai inguste pe desktop taskurile, pe inaltime?"
     8px sus / 10px jos -> 5/7: randul scade de la ~62 la ~56px, fara sa se
     atinga fontul sau meta-randul. Doar desktop — pe telefon padding-ul
     vertical e al lui `.gl-fata` si ramane cum e. */
  .trow { position: relative; display: flex; align-items: center; gap: var(--space-sm); padding: 5px var(--space-sm) 7px; background: none; border: 0; transition: transform var(--dur-fast) var(--ease), opacity var(--dur-base) var(--ease); }
  /* Doar unde exista cursor — pe touch :hover ramane lipit dupa atingere si randul
     ar rămâne impins la dreapta. (Fara `border-color`: randul are `border: 0`,
     rama e a wrapperului — declaratia de aici nu facea nimic.) */
  @media (hover: hover) {
    .trow:hover { transform: translateX(4px); }
  }
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
  /* INDEXUL MONO A PLECAT. Fusese deja stins la 38% dintr-un motiv bun, dar sub
     15 taskuri nu spui niciodata „fa taskul 07", nu se sorteaza manual, iar pe
     telefon era oricum `display: none`. Costa 36px pe fiecare rand exact inaintea
     titlului si era a doua codificare a aceleiasi severitati pe care o da deja
     bordura din stanga. Titlul incepe acum la 40px in loc de 76, iar desktopul
     arata ca telefonul — se folosesc la fel de mult. */
  .trow.done { opacity: 0.5; }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; }
  .check:hover { color: var(--accent); }
  .trow.done .check { color: var(--success); }
  /* `.check-empty` (toate cele trei marimi) traieste acum in global.css, o
     singura data pentru toate listele — inclusiv haloul de hover, care adauga in
     loc sa rescrie `--ring`. */
  .tmain { flex: 1; min-width: 0; cursor: pointer; text-align: left; }
  .ttitle-row { display: flex; align-items: center; gap: var(--space-xs); min-width: 0; }
  .tchev { display: inline-flex; align-items: center; color: inherit; flex-shrink: 0; }
  .ttitle { font-size: var(--font-body); color: var(--text); font-weight: var(--fw-medium); flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  .note-ind { display: inline-flex; align-items: center; color: var(--text-dim); }
  .tinfo { display: flex; gap: var(--space-sm); font-size: var(--font-small); color: var(--text-dim); margin-top: 2px; align-items: center; }
  /* Categoria pleaca la capatul din dreapta (ca „Inbox" la Todoist): e ultima ca
     importanta, deci nu are voie sa stea intre ochi si termen. */
  /* ACEEASI HAINA PE AMBELE ECRANE. Pe telefon categoria era deja text simplu,
     tocmai fiindca pastila era cel mai tare lucru de pe rand; pe desktop ramasese
     pastila — douasprezece capsule gri intr-o coloana, pentru informatia care
     conteaza cel mai putin din rand. Pastila ramane rezervata pentru CIFRE
     (chipul de subtaskuri), unde chiar spune ceva. */
  .task-cat { margin-left: auto; padding: 0; background: none; color: var(--text-faint); font-weight: var(--fw-normal); flex: none; }
  .tdeadline { display: inline-flex; align-items: center; gap: 3px; }
  /* Trei semne pe fiecare din douasprezece randuri erau al doilea lucru pe care
     il vedeai, dupa titlu. Se sting cand cursorul nu e pe rand — dar NU dispar
     (`opacity`, nu `display`), ca sa nu-si mute locul cand apar. */
  .task-actions { display: flex; align-items: center; gap: var(--space-xs); flex-shrink: 0; }
  @media (hover: hover) {
    .task-actions { opacity: 0.5; transition: opacity var(--dur-fast) var(--ease); }
    .trow:hover .task-actions,
    .task-actions:focus-within { opacity: 1; }
  }
  /* REPLANIFICAREA PE DESKTOP. Pe telefon amani cu un gest; aici nu exista niciun
     drum scurt pentru a doua actiune ca frecventa dintr-o lista de facut. Acelasi
     verb ca gestul de pe telefon. */
  /* DatePicker-ul isi aduce caseta de camp; in randul de lista trebuie sa arate ca
     vecinii lui — un buton-iconita de 28px, nu un input. */
  .task-dp { flex-shrink: 0; }
  .task-dp :global(.dp) { width: auto; }
  .task-dp :global(.dp-trigger) { width: 28px; height: 28px; min-height: 0; padding: 0;
    justify-content: center; background: none; border: none; box-shadow: none;
    border-radius: var(--radius-sm); color: var(--text-faint); }
  .task-dp :global(.dp-trigger:hover) { color: var(--accent); background: var(--accent-subtle); }
  .task-dp :global(.dp-value) { display: none; }
  /* Pe desktop invelisul de glisare nu exista pentru layout. */
  .gl-fata { display: contents; }
  .task-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .task-del:hover { color: var(--danger); background: var(--danger-subtle); }


  /* Corp expandat: panou inset (nu mai pluteste pe negru), continut grupat cu gap */
  /* Extinderea e CONTINUAREA randului, nu un card separat: se lipeste de el
     (randul isi pierde colturile de jos si marginea), preia bordura de severitate
     din stanga si sta pe acelasi fundal. Inainte pareau doua obiecte fara legatura. */
  /* Extinderea: continut in acelasi card, separat doar de o linie subtire. */
  .subtask-body { margin: 0; padding: 6px var(--space-12) var(--space-12) 34px;
    border-top: 1px solid var(--border-subtle);
    display: flex; flex-direction: column; gap: 4px; }

  /* Actiuni discrete: chip-uri "+ Descriere / + Fisier" in loc de link-uri italic plutinde */
  /* Fara rand propriu pentru un singur buton: se aliniaza la stanga, discret. */


  /* ===== Foaia taskului ===== */
  .sub-cap { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: 6px; }
  .sub-cap-t { font-size: var(--font-label); text-transform: uppercase;
    letter-spacing: var(--tracking-label); font-weight: var(--fw-semibold); color: var(--text-faint); flex: none; }
  .sub-gol { font-size: var(--font-small); color: var(--text-dim); padding: var(--space-sm) 0; }
  /* Fiecare subtask e un card, ca la Todoist: pe fundalul foii randurile fara
     suprafata proprie se citeau ca un bloc de text, nu ca lucruri separate.
     O SINGURA declaratie: mai jos exista pana acum o a doua `.sub-row` (ramasa
     de la designul de lista), care la specificitate egala castiga fiind ultima
     si rescria TACUT padding-ul cardului la `3px 0` — adica un card desenat cu
     rama la 0px de text. Masurat inainte: padding calculat `3px 0` pe desktop,
     `2px 0` in foaie. Exact felul de abatere care nu arunca nicio eroare. */
  .sub-row { display: flex; align-items: center; gap: 9px; min-height: 32px;
    padding: 0 6px; border-radius: var(--radius-xs); }
  .sub-row:hover { background: var(--bg-hover); }
  /* ULTIMUL RAND AL LISTEI, nu un obiect mai tare decat ea. Dreptunghiul punctat
     de 44px era cel mai puternic lucru din panou, desi „mai adaug un pas" e ultima
     intentie cu care deschizi un task. Bifa lipsa e inlocuita de „+", pe aceeasi
     coloana, ca randul sa se alinieze cu subtaskurile de deasupra. */
  .sub-nou { display: flex; align-items: center; gap: 9px; width: 100%;
    min-height: 32px; padding: 0 6px; border: none; border-radius: var(--radius-xs);
    background: none; color: var(--text-faint); font-size: var(--font-small);
    cursor: pointer; transition: var(--transition-colors); }
  .sub-nou:hover { background: var(--accent-subtle); color: var(--accent); }
  .sub-nou-p { display: flex; align-items: center; justify-content: center;
    width: 18px; flex: none; }

  /* ===== Antetul foii ===== */
  .ts-cap { display: flex; align-items: flex-start; gap: var(--space-sm); margin-bottom: var(--space-sm); }
  .ts-check { flex: none; min-width: var(--tap-min); min-height: var(--tap-min);
    display: flex; align-items: center; justify-content: flex-start; color: var(--success);
    background: none; border: none; cursor: pointer; padding: 0; }
  .ts-titlu { font-family: var(--font-heading); font-size: var(--font-h3); font-weight: var(--fw-semibold);
    color: var(--text); line-height: var(--lh-snug); overflow-wrap: anywhere; padding-top: 9px; }
  .ts-titlu.gata { text-decoration: line-through; color: var(--text-dim); }
  /* Randul de termen: UN card de o linie, ca „📅 28 Feb 11:00" la Todoist. */
  .ts-rand { display: flex; align-items: center; gap: var(--space-sm); width: 100%;
    min-height: var(--tap-min); padding: 0 var(--space-12); margin-bottom: var(--space-sm);
    background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-md);
    color: var(--text-dim); font-size: var(--font-small); text-align: left; cursor: pointer;
    transition: var(--transition-pressable); }
  .ts-rand:hover { border-color: var(--border-strong); }
  .ts-rand:active { transform: scale(var(--press-scale)); }
  .ts-rand.activ { border-color: var(--accent); }
  .ts-val { flex: 1; color: var(--text); font-weight: var(--fw-medium); }
  /* Acelasi `--ring` ca inelul bifei din capul foii — un singur izvor de culoare. */
  .ts-val.sev { color: var(--ring); }
  .ts-fara { color: var(--text-dim); font-weight: var(--fw-normal); }
  .ts-rand :global(.ts-chev) { flex: none; opacity: 0.5; transition: transform var(--dur-fast) var(--ease); }
  .ts-rand.activ :global(.ts-chev) { transform: rotate(180deg); }

  .ts-zile { display: flex; gap: 6px; flex-wrap: wrap; margin: -2px 0 var(--space-sm); }
  /* `--tap-min`, nu 40: foaia exista DOAR pe telefon (vezi toggleTaskExpand),
     deci butoanele astea sunt intotdeauna tinte de deget. */
  .ts-zi { display: inline-flex; align-items: center; justify-content: center; gap: 4px;
    min-height: var(--tap-min); padding: 0 var(--space-12); border-radius: var(--radius-md);
    background: var(--bg-input); border: 1px solid var(--border); color: var(--text-secondary);
    font-size: var(--font-small); font-weight: var(--fw-medium); cursor: pointer;
    transition: var(--transition-pressable); }
  .ts-zi:hover { border-color: var(--accent); color: var(--text); }
  .ts-zi:active { transform: scale(var(--press-scale)); }
  .ts-scoate { color: var(--danger); }

  /* Sectiunea de subtaskuri: eticheta micro + progres X/Y */
  .sub-section { display: flex; flex-direction: column; gap: 2px; }
  .note-modal { display: flex; flex-direction: column; gap: var(--space-sm); }
  .sub-row.sub-done .sub-title { text-decoration: line-through; color: var(--text-dim); }
  /* Titlul e BUTON (atingi = redenumesti), dar trebuie sa arate ca text: fara
     fundal, aliniat la stanga, pe toata latimea ramasa. */
  .sub-title { flex: 1; min-width: 0; font-size: var(--font-small); color: var(--text);
    background: none; border: none; padding: 0; text-align: left; cursor: text;
    overflow-wrap: anywhere; }
  /* ACELEASI METRICI ca `.sub-title`, plus doar o linie de accent dedesubt.
     Inainte inputul aducea caseta lui (padding 2px 6px + rama 1px), deci textul
     SAREA 7px la dreapta exact in clipa in care il atingeai ca sa-l corectezi.
     Redenumirea inline trebuie sa arate ca textul care era acolo, nu ca un camp
     nou; `:focus` e redeclarat fiindca regula globala pe `input:focus` i-ar pune
     inel si rama de camp. */
  .sub-edit { flex: 1; min-width: 0; font-size: var(--font-small); color: var(--text);
    background: none; border: none; border-radius: 0; padding: 0;
    box-shadow: 0 1px 0 var(--accent); }
  .sub-edit:focus { border: none; box-shadow: 0 1px 0 var(--accent); outline: none; }
  /* Bara de progres: subtire, aceeasi latime cu randurile de sub ea. */
  .sub-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; opacity: 0; transition: opacity var(--dur-fast); }
  .sub-row:hover .sub-del { opacity: 1; }
  .sub-del:hover { color: var(--danger); background: var(--danger-subtle); }
  .sub-add { display: flex; gap: var(--space-xs); margin-top: 0; }
  .sub-add input { flex: 1; padding: 6px 10px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-small); }
  /* `flex-shrink: 0`: fara el butonul se strangea la 12px (masurat) — inputul de
     langa are `flex: 1` si il storcea, iar „+" ajungea o dunga netastabila. */
  .sub-add-btn { width: 32px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .sub-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
  .sub-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }


  .task-edit.areNota { color: var(--accent-on-subtle); }
  .task-edit { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .task-edit:hover { color: var(--accent); background: var(--accent-subtle); }
  .recur-badge { display: inline-flex; align-items: center; gap: 3px; padding: 0 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-dim); font-weight: var(--fw-medium); }
  .tdeadline { font-size: var(--font-small); }
  /* Al doilea canal al severitatii, si vine din ACELASI `--ring` ca inelul, nu
     dintr-o a doua harta de culori — asa cele doua nu pot sa se desincronizeze.
     Treapta „curand" a plecat: era `--warning`, adica exact acelasi hex ca
     `--accent`, deci „azi" si „in doua zile" erau literalmente acelasi pixel.
     Textul suporta totusi o treapta in plus fata de inel — „mâine" ramane scris,
     doar ca in gri: un cuvant poate ce un cerc de 2px nu poate. */
  .tdeadline.sev { color: var(--ring); font-weight: var(--fw-medium); }

  .task-form { display: flex; flex-direction: column; gap: var(--space-md); }
  /* DOUA coloane pentru DOUA campuri. Grila era `1fr 1fr 1fr` cu numele
     `form-row-3` — al treilea camp (prioritatea) a plecat in v34, dar coloana
     lui a ramas: o treime din latimea modalului, goala, pe ambele formulare. */
  .form-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-md); }

  .task-skeleton { padding: var(--space-sm) var(--space-md); }


  /* ===== V3: grid lista + agenda 7 zile ===== */
  /* AGENDA DE 7 ZILE A PLECAT (2026-08-07). Era o a doua coloana de 300px care
     asezea ACELEASI taskuri dupa aceeasi cheie — termenul — langa lista care
     tocmai fusese grupata dupa termen. Sub 15 taskuri repeta pur si simplu ce
     scria alaturi, si tocmai de aceea era deja `display: none` pe telefon: o
     coloana care nu-si plateste locul pe 390px nu si-l plateste nici pe 1440,
     doar ca acolo e loc sa nu se observe. Lista ia toata latimea. */
  .v3grid { display: grid; grid-template-columns: 1fr; gap: 14px; align-items: start; }
  .list-cell { min-width: 0; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-md); }
  .list-label { margin-bottom: var(--space-12); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .toolbar { flex-direction: column; align-items: stretch; }
    .search-box { max-width: none; }
    .quick-add input, .quick-add-btn { min-height: 44px; }
    .quick-add-btn { width: 44px; }
    .task-del, .task-edit { opacity: 1; }
    .form-row-2 { grid-template-columns: 1fr; }
    /* O LINIE, ca in aplicatiile de to-do.
       Inainte: titlul sus, cele trei actiuni de intretinere pe o linie proprie
       dedesubt = 110px pe task. Acum randul are ~56px si actiunile vin din gest
       (glisare spre stanga); glisarea spre dreapta bifeaza. */
    .trow { flex-wrap: nowrap; align-items: center; padding: 0; overflow: hidden;
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
    /* BIFA: 44px de ATINS, dar nu 44px de LATIME.
       Cercul are 18px si statea centrat intr-o caseta de 44 — adica 13px de aer
       de fiecare parte, plus inca 8 de spatiu dupa. Masurat pe 375px, titlul
       incepea la x=96: un sfert din latimea ecranului consumat inainte de prima
       litera, pe fiecare rand. Caseta se ingusteaza la 30px, iar suprafata de
       atingere revine dintr-un strat invizibil (`::after`), care se intinde in
       padding-ul randului si in spatiul dintre bifa si titlu — NU peste titlu,
       ca sa nu fure atingerile care trebuie sa deschida taskul. */
    .check { position: relative; min-width: 30px; width: 30px; min-height: var(--tap-min);
      align-items: center; justify-content: center; padding: 0; }
    .check::after { content: ''; position: absolute; inset: -7px; }
    /* (`.tmain`/`.ttitle` se declara o singura data, mai jos in acelasi bloc —
       aici statusera doua declaratii moarte pe care ultima le anula.) */
    .tinfo { flex-wrap: nowrap; overflow: hidden; }
    .tinfo > * { flex-shrink: 0; }

    .trow:global(.gl-bifa) { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }
    /* Cautarea si filtrele: caseta de cautare avea 25px inaltime utila, iar
       chipurile 30. */
    /* Ca la Proiecte: caseta are 44px, dar inputul dinauntru avea 25 si doar el
       primeste focus. */
    .search-box { max-width: none; align-items: stretch; padding: 0 14px; }
    .search-box input { align-self: stretch; min-height: var(--tap-min); }
    .search-box :global(svg) { align-self: center; }
    .a-ico { min-height: var(--tap-min); padding: 0 12px; font-size: var(--font-small); }
    .filters { gap: var(--space-xs); }
    .g-ico { width: var(--tap-min); min-height: var(--tap-min); }
    /* Capsula creste ODATA cu segmentele: tinta de 44 vine din segment, nu din
       padding-ul capsulei, altfel jumatate din capsula n-ar face nimic la atins. */
    .seg { min-height: calc(var(--tap-min) - 4px); padding: 2px 14px; font-size: var(--font-small); }
    .tmain { min-height: var(--tap-min); }
    .page-header :global(.btn) { min-height: var(--tap-min); }

    /* Capul de grupa se lipeste SUB antetul paginii, nu de marginea ferestrei:
       altfel prima grupa ar sta pe jumatate ascunsa dupa bara de sus. */
    .grup-cap { top: var(--header-height); padding-top: 12px; }

    /* Eticheta cartonasului („LISTA TASKURI 5") pleaca: antetul paginii scrie deja
       „Taskuri 5" la 40px deasupra. Doua titluri pentru aceeasi lista inseamna un
       task in minus pe ecran, si primul lucru pe care il vezi nu e un task. */
    .list-label { display: none; }
    /* Cartonasul listei isi pierde rama, fundalul si padding-ul lateral.
       Motivul nu e doar spatiul: `.page` avea deja 16px si cartonasul inca 16, iar
       cele doua se adunau inaintea fiecarui rand. Dar odata scos padding-ul,
       randurile ajungeau lipite de propria lui rama — o cutie desenata la 1px de
       continut se citeste ca o greseala. Iar gruparea face acum ce facea el:
       spune unde incepe si unde se termina o bucata de lista.
       Randurile devin cat pagina; titlul castiga 32px pe fiecare rand. */
    /* RITMUL DE DEASUPRA LISTEI.
       Masurat pe 390×800: primul task incepea la y=296, adica 37% din ecran
       consumat de antet, filtre si compozitor — trei randuri despartite de cate
       16px, plus 16 de la marginea paginii. Nimic nu dispare, doar se strang
       distantele: aceleasi elemente, ~30px mai sus. Pe desktop raman cele 16. */
    .page { padding-top: var(--space-12); }
    .page-header, .toolbar, .quick-add { margin-bottom: 10px; }
    .grup-cap:first-child { padding-top: 4px; }
    .list-cell { background: none; border: none; border-radius: 0;
      padding: var(--space-sm) 0 0; }
    /* Capul lipit se estompeaza peste fundalul PAGINII acum, nu peste al cutiei. */
    .grup-cap { background: linear-gradient(var(--bg) 72%, transparent); }

    /* Cautarea pliata: o iconita de 44px, nu o caseta cat randul. */
    .toolbar { flex-direction: row; align-items: center; gap: var(--space-sm); }
    .search-box.pliata { flex: 0 0 auto; max-width: none; width: var(--tap-min); padding: 0;
      justify-content: center; border-radius: var(--radius-full); }
    .sb-ico { width: var(--tap-min); height: var(--tap-min); display: flex;
      align-items: center; justify-content: center; color: var(--text-dim);
      background: none; border: none; cursor: pointer; }
    .filters { flex: 1; justify-content: flex-end; }

    .tchev { display: none; }

    /* TITLUL ARE VOIE SA CADA PE DOUA RANDURI.
       Pe o singura linie, „Reinnoire certificat de acces in site Co…" nu spune la
       ce site — adica randul arata a task fara sa fie unul. Doua randuri costa
       ~16px si rezolva aproape toate titlurile reale; de la al treilea in jos
       taierea e corecta, fiindca acolo chiar e o descriere, nu un titlu. */
    .ttitle { white-space: normal; display: -webkit-box; -webkit-line-clamp: 2;
      line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
      text-overflow: initial; line-height: var(--lh-snug); }

    /* Agenda „7 zile" e acum o a doua copie a aceleiasi liste: gruparea de
       deasupra spune deja azi/mâine/zilele astea, cu actiuni cu tot. Pe desktop
       ramane — acolo sta pe coloana din dreapta si nu ia nimic de la lista. */

    /* Interiorul taskului deschis: aici se bifeaza subtaskuri si se scrie unul nou,
       deci sunt tinte ca oricare altele. Erau 28-39px. */
    .sub-add input, .sub-add-btn { min-height: var(--tap-min); }
    .sub-add-btn { width: var(--tap-min); }
    /* Cardul isi pastreaza padding-ul orizontal si pe telefon — `2px 0` de aici
       anula (a doua oara) rama-la-0px reparata mai sus. Vertical ramane strans:
       inaltimea o da oricum bifa de 40px. */
    .sub-row { padding: 0 6px; min-height: var(--tap-min); }
    .sub-nou { min-height: var(--tap-min); font-size: var(--font-small); }
    .sub-nou-p { width: 26px; }
    /* ACEEASI SOCOTEALA CA LA RANDUL PARINTE, care a coborat de la 96px la 66px
       pana la prima litera. Masurat pe 390px, un subtask incepea la x=111: 28%
       din latimea ecranului consumata inainte de primul cuvant, pe fiecare rand.
       Doua lucruri o produceau — indentarea de 40px a sectiunii si o bifa cu
       caseta de 44px in jurul unui cerc de 14. Indentarea scade la 12 si devine
       o LINIE (spina), care spune „astea tin de taskul de deasupra" mai bine
       decat spatiul gol; caseta bifei se ingusteaza la 26px, iar suprafata de
       atins revine dintr-un strat invizibil (`::after`), exact ca la randul
       parinte. Titlul incepe acum pe la 67px. */
    .subtask-body { padding-left: var(--space-12) !important; }
    .sub-row .check { min-width: 26px; width: 26px; min-height: 40px;
      align-items: center; justify-content: center; padding: 0; }
    /* Pe touch nu exista hover, deci un buton care apare la hover nu apare
       niciodata: „sterge subtask" era invizibil si de neatins pe telefon. */
    /* PUBELA PLEACA DE TOT DE PE RAND. Pe telefon `:hover` nu exista, deci regula
       „apare la hover" devenise „e mereu acolo": pe 390px randul avea 70px de
       mecanica (cerc 26 + pubela 44) si singura actiune distructiva din foaie
       statea fix la marginea dreapta, unde se odihneste degetul mare. Stergerea
       vine acum din glisare spre stanga — acelasi gest si acelasi sens ca la
       taskul parinte — cu „Anulează" in toast. Titlul castiga 44px pe fiecare rand. */
    .sub-del { display: none; }
    /* Randul devine pista: invelisul se translateaza peste fundalul colorat.
       Aceeasi mecanica exacta ca la `.trow`, doar cu metricile subtaskului. */
    .sub-row { position: relative; overflow: hidden; touch-action: pan-y; padding: 0; }
    .sub-row .gl-fata { padding: 0 6px; gap: 9px; min-height: var(--tap-min);
      background: var(--bg-overlay); border-radius: var(--radius-xs); }
    .sub-row:global(.gl-tras) .gl-fata { box-shadow: -6px 0 12px -8px rgba(0,0,0,0.55); }
    /* Titlul e tinta cea mai mare si face lucrul cel mai des: bifeaza. */
    .sub-title { text-align: left; cursor: pointer; }
    /* 1rem = 16px, aceeasi valoare pe CITIRE si pe SCRIERE. Regula globala urca
       oricum orice input la 16px pe telefon (zoom-ul Safari la focus), deci cu
       titlul la `--font-body` (14.4px) textul crestea cu 1.6px fix cand incepeai
       sa-l editezi. Egalarea se face in sus, nu in jos — sub 16 nu se poate. */
    .sub-title, .sub-edit { font-size: var(--font-input-mobile); }
    .qa-chip, .qa-dp :global(.dp-trigger) { min-height: var(--tap-min); padding: 0 16px;
      font-size: var(--font-small); }
    /* Indiciul despre Enter n-are cui sa se adreseze pe o tastatura de telefon. */
    .qa-hint { display: none; }
    .td-link { min-height: var(--tap-min); font-size: var(--font-small); }
    .td-dp :global(.dp-trigger) { min-height: var(--tap-min); font-size: var(--font-small); }
    .td-jos { gap: var(--space-lg); }
  }
</style>
