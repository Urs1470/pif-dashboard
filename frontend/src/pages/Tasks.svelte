<script>
  import { onMount } from 'svelte'
  import { ecran } from '../lib/ecran.svelte.js'
  import { slide } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { motionDuration, DUR_BASE, plecare, DUR_FAST } from '../lib/motion.svelte.js'
  import { ListTodo, Plus, CheckCircle2, CalendarDays, ListChecks, ChevronDown, ChevronRight, Repeat, Search, CalendarPlus, ArrowRight, X, Check } from '@lucide/svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import { globalTasks, loadGlobalTasks, updateGlobalTask, createGlobalTask, deleteGlobalTask, loadSubtasks, createSubtask, updateSubtask, deleteSubtask } from '../stores/tasks.svelte.js'
  import { formatDate, dueColor, isFutureRecurrence } from '../lib/formatters.js'
  import { grupeazaDupaTermen, etichetaTermen, ORDINE_GRUPE } from '../lib/grupare.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import { router } from '../lib/router.svelte.js'
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
  import AgendaColumn from '../components/tasks/AgendaColumn.svelte'
  import { todayISO, addDays } from '../lib/calendarDates.js'

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
  let subtaskLoading = $state(false)

  let taskSearch = $state('')
  let quickTitle = $state('')
  let quickAdding = $state(false)
  let showNoteModal = $state(false)
  let noteTask = $state(null)
  let noteDraft = $state('')
  let noteSaving = $state(false)



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
      await loadGlobalTasks({ arhiva: showArchive })
      toast(`Eroare: ${e.message}`, 'error')
      return
    }
    await loadGlobalTasks({ arhiva: showArchive })
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
          await loadGlobalTasks({ arhiva: showArchive })
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
      await loadGlobalTasks({ arhiva: showArchive })
      toastUndo(v ? `Mutat pe ${etichetaTermen(v)}` : 'Termen scos', {
        onUndo: async () => {
          await updateGlobalTask(t.id, { data_scadenta: vechi })
          await loadGlobalTasks({ arhiva: showArchive })
        },
      })
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function setTermenData(t, v) {
    const vechi = t.data_scadenta || ''
    try {
      await updateGlobalTask(t.id, { data_scadenta: v || '' })
      await loadGlobalTasks({ arhiva: showArchive })
      toastUndo(v ? `Mutat pe ${etichetaTermen(v)}` : 'Termen scos', {
        onUndo: async () => {
          await updateGlobalTask(t.id, { data_scadenta: vechi })
          await loadGlobalTasks({ arhiva: showArchive })
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
        data_scadenta: formDeadline || undefined,
        recurenta: formRecurenta || undefined,
        status: 'to_do',
      })
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
        titlu: quickTitle.trim(), status: 'to_do',
        data_scadenta: termen || undefined,
      })
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
        categorie: formCategory,
        data_scadenta: formDeadline,
        recurenta: formRecurenta || null,
      })
      showEditModal = false
      editingTask = null
      await loadGlobalTasks({ arhiva: showArchive })
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
    showSheet = true
    await incarcaSubtaskuri(taskId)
  }

  async function incarcaSubtaskuri(taskId) {
    if (subtasksCache[taskId]) return
    subtaskLoading = true
    try {
      const subs = await loadSubtasks(taskId)
      subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
    } catch (_) {
      subtasksCache = { ...subtasksCache, [taskId]: [] }
    } finally { subtaskLoading = false }
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
  async function toggleTaskExpand(taskId) {
    if (ecran.telefon) { await deschideFoaia(taskId); return }
    if (expandedTask === taskId) {
      expandedTask = null
      return
    }
    expandedTask = taskId
    await incarcaSubtaskuri(taskId)
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
    await loadGlobalTasks({ arhiva: showArchive })
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
    toast('Task șters', 'success')
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

  // Banda de carduri urgente a plecat (Ion, 2026-07-27: „cardurile astea ce apar
  // nu am nevoie de ele"): repeta primele randuri din lista de imediat dedesubt,
  // care oricum e sortata cu urgentele sus si are aceleasi actiuni.


  onMount(() => { loadGlobalTasks() })
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
  <div class="td-actiuni">
    <button class="td-btn" class:areNota={!!t.descriere} onclick={() => openNoteModal(t)}>
      <SolidIcon name="notes" size={13} /> {t.descriere ? 'Editează nota' : 'Adaugă notă'}
    </button>
    <button class="td-btn" onclick={() => openEditModal(t)}>
      <SolidIcon name="pencil" size={13} /> Editează
    </button>
  </div>

  {#if t.descriere}
    <div class="td-nota"><RichText value={t.descriere} collapsible maxHeight={140} noToggle /></div>
  {/if}

  <div class="sub-section">
    {#if subtaskLoading && !subtasksCache[t.id]}
      <div class="sub-loading">Se încarcă...</div>
    {:else}
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
        <div class="sub-row" class:sub-done={sub.done} animate:flip={{ duration: motionDuration(DUR_BASE) }} transition:slide|local={{ duration: motionDuration(DUR_BASE) }}>
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
            <button class="sub-title" onclick={() => incepeRedenumirea(sub)}
                    title="Atinge ca să redenumești">{sub.titlu}</button>
          {/if}
          <button class="sub-del" onclick={() => removeSubtask(sub)}
                  aria-label="Șterge subtaskul"><SolidIcon name="trash" size={13} /></button>
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
        <button class="sub-nou" onclick={() => { adaugSubLa = t.id; newSubtaskTitle = '' }}>
          <Plus size={15} /> Adaugă subtask
        </button>
      {/if}
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
      <button class="chip" class:active={!showArchive} onclick={() => { showArchive = false; loadGlobalTasks() }}>Active</button>
      <button class="chip" class:active={showArchive} onclick={() => { showArchive = true; loadGlobalTasks({ arhiva: true }) }}>Arhivă</button>
    </div>
  </div>


  <div class="v3grid">
  <div class="list-cell cell-in">
  <div class="cell-label list-label"><span class="ico ico-amber"><ListTodo size={13} /></span>{showArchive ? 'Taskuri arhivate' : 'Lista taskuri'}<span class="tail">{showArchive ? globalTasks.items.length : activeTasks.length}</span></div>
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
    <ErrorState message={globalTasks.error} onretry={() => loadGlobalTasks({ arhiva: showArchive })} />
  {:else if globalTasks.items.length === 0}
    <!-- Aceeasi stare acopera „n-ai avut niciodata taskuri" si „tocmai le-ai
         terminat pe toate" — pagina nu le poate deosebi, fiindca API-ul nu-i da
         cele bifate. Deci textul trebuie sa fie adevarat in amandoua si sa spuna
         unde au plecat cele facute, altfel „Niciun task" se citeste ca o pierdere. -->
    <EmptyState icon={ListTodo} title={showArchive ? 'Arhiva e goală' : 'Nimic de făcut'} description={showArchive ? 'Aici ajung taskurile bifate.' : 'Scrie un task în câmpul de sus. Ce ai terminat e în „Arhivă".'} />
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
      {#each grupe[gid].items as t, i (t.id)}
<!-- Iesirea randului bifat: se stinge si se strange, in loc sa sara.
               Vezi `plecare` in lib/motion.svelte.js. -->
                    <div class="trow-wrap" class:deschis={expandedTask === t.id}
             style="--sev: {dueColor(t.data_scadenta)}"
             animate:flip={{ duration: motionDuration(DUR_BASE) }}
             out:plecare>
          <div class="trow" class:done={t.status === 'done'} use:focusOnLand={focusKey('global', t.id)}
               use:glisare={{ latime: 232, activ: ecran.telefon, onBifa: t.status === 'done' ? null : () => toggleStatus(t) }}>
            <!-- Actiunile de intretinere (notita / editare / stergere) stau in
                 panoul de sub rand: sunt rare fata de „bifat" si „deschis", si
                 tocmai ele umflau randul cu o linie intreaga. -->
            <!-- PATRU actiuni, nu sapte. Panoul se deschide PESTE rand: la sapte
                 butoane de 58px n-ar mai fi ramas nimic din titlu, deci n-ai mai
                 sti pe ce task actionezi. Aici stau cele care se folosesc des —
                 planificarea (de zeci de ori pe viata unui task) si stergerea.
                 Nota si editarea titlului sunt rare si stau in randul desfasurat,
                 la o atingere pe titlu.
                 „Scoate termenul" nu are buton propriu: e in calendarul de sub
                 „Dată", care are deja „Șterge". -->
            <div class="gl-pista" aria-hidden="true"><span class="gl-ico"><Check size={17} strokeWidth={3} /></span><span class="gl-et">Făcut</span></div>
            <div class="gl-actiuni">
              <button class="glb" onclick={() => setTermen(t, 0)} title="Termen azi">
                <CalendarPlus size={16} /><span>Azi</span>
              </button>
              <button class="glb" onclick={() => setTermen(t, 1)} title="Termen mâine">
                <ArrowRight size={16} /><span>Mâine</span>
              </button>
              <span class="glb datewrap" title="Alege ziua">
                <DatePicker value={t.data_scadenta} placeholder="Dată" onchange={(v) => setTermenData(t, v)} />
                <span>Dată</span>
              </span>
              <button class="glb danger" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Șterge task">
                <SolidIcon name="trash" size={16} /><span>Șterge</span>
              </button>
            </div>
            <div class="gl-fata">
            <span class="tix">{String(grupe[gid].start + i + 1).padStart(2, '0')}</span>
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
                  <span class="tdeadline" class:overdue={isOverdue(t.data_scadenta)} class:today={isToday(t.data_scadenta)} class:soon={isSoon(t.data_scadenta)}>
                    <CalendarDays size={11} />{chipTermen(t, gid)}
                  </span>
                {/if}
                {#if t.subtask_total}
                  <span class="tsub-chip" class:gata={t.subtask_done === t.subtask_total}
                        title="{t.subtask_done || 0} din {t.subtask_total} subtaskuri făcute">
                    <ListChecks size={11} />{t.subtask_done || 0}/{t.subtask_total}
                  </span>
                {/if}
                {#if t.descriere}<span class="note-ind" title="Are notiță"><SolidIcon name="notes" size={10} /></span>{/if}
                {#if t.recurenta}<span class="recur-badge" title="Recurent: {t.recurenta}"><Repeat size={10} /> {t.recurenta}</span>{/if}
                {#if t.categorie}<span class="task-cat">{t.categorie}</span>{/if}
              </div>
            </button>
            <div class="task-actions">
              <button class="task-edit" onclick={() => openNoteModal(t)}
                      title={t.descriere ? 'Editează descrierea' : 'Adaugă descriere'}
                      class:areNota={!!t.descriere}><SolidIcon name="notes" size={12} /></button>
              <button class="task-edit" onclick={() => openEditModal(t)} title="Editează task"><SolidIcon name="pencil" size={12} /></button>
              <button class="task-del" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }} title="Șterge task"><SolidIcon name="trash" size={13} /></button>
            </div>
            </div>
          </div>
          <!-- Pe desktop taskul se desface AICI, in lista. Acelasi `taskDetail` ca
               in foaia de pe telefon, deci designul e identic — se schimba doar
               unde e asezat. -->
          {#if expandedTask === t.id}
            <div class="subtask-body" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
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

  <AgendaColumn tasks={showArchive ? globalTasks.items : activeTasks} onopen={(t) => toggleTaskExpand(t.id)} />
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
    <div class="ts-cap">
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
        <span class="ts-val" class:overdue={isOverdue(sheetTask.data_scadenta)}
              class:today={isToday(sheetTask.data_scadenta)}>{etichetaTermen(sheetTask.data_scadenta)}</span>
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
    <div class="form-row-3">
      <label class="mf-field">
        <span class="mf-label">Categorie</span>
        <input type="text" class="mf-input" bind:value={formCategory} placeholder="General" />
      </label>
      <div class="mf-field">
        <span class="mf-label">Termen</span>
        <DatePicker bind:value={formDeadline} />
      </div>
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
    <div class="form-row-3">
      <label class="mf-field">
        <span class="mf-label">Categorie</span>
        <input type="text" class="mf-input" bind:value={formCategory} placeholder="General" />
      </label>
      <div class="mf-field">
        <span class="mf-label">Termen</span>
        <DatePicker bind:value={formDeadline} />
      </div>
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

<Modal bind:open={showNoteModal} title={noteTask ? `Notițe — ${noteTask.titlu}` : 'Notițe task'} size="doc">
  <div class="note-modal">
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
  /* Vezi Projects.svelte: fara `flex-wrap`/`gap` antetul nu se poate rupe si
     butonul iese din ecran, unde `overflow-x: clip` il taie fara sa spuna nimic. */
  .page-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); flex-wrap: wrap; margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); min-width: 0; }
  .page-title-row h1 { font-size: var(--font-h1); font-weight: var(--fw-bold); }
  .count { display: inline-flex; align-items: center; justify-content: center; min-width: 19px; height: 19px; padding: 0 5px; font-family: var(--font-mono); font-size: var(--font-micro); font-weight: var(--fw-semibold); line-height: 1; font-variant-numeric: tabular-nums; border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent-on-subtle); border: 1px solid var(--accent-ring); }

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
  .chip { padding: 4px 12px; font-size: var(--font-tiny); font-weight: var(--fw-medium); border-radius: var(--radius-full); background: var(--bg-input); color: var(--text-secondary); border: 1px solid transparent; cursor: pointer; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); min-height: 30px; }
  .chip:hover { background: var(--bg-hover); color: var(--text); }
  .chip.active { background: var(--accent-subtle); color: var(--accent-on-subtle); border-color: var(--accent); }
  .chip:active { transform: scale(0.97); }
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
    font-family: var(--font-mono); font-size: var(--font-micro);
    font-weight: var(--fw-semibold); text-transform: uppercase;
    letter-spacing: var(--tracking-wide); color: var(--text-faint); }
  .grup-cap:first-child { margin-top: 0; }
  .grup-n { display: inline-flex; align-items: center; justify-content: center;
    min-width: 17px; height: 17px; padding: 0 5px; border-radius: var(--radius-full);
    background: var(--bg-elevated); color: var(--text-dim);
    font-size: var(--font-micro); line-height: 1; font-variant-numeric: tabular-nums; }
  /* Tonul repeta EXACT limbajul de culoare al bordurii din stanga randului
     (`dueColor`), ca sa nu inveti doua coduri pentru acelasi lucru. */
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
    color: var(--text-secondary); font-size: var(--font-tiny);
    font-weight: var(--fw-medium); cursor: pointer;
    transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .qa-chip:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-subtle); }
  .qa-dp :global(.dp-trigger) { min-height: 30px; padding: 4px 12px;
    border-radius: var(--radius-full); font-size: var(--font-tiny); }
  .qa-hint { font-size: var(--font-micro); color: var(--text-faint); margin-left: auto; }

  /* ===== randul desfasurat ===== */
  .td-actiuni { display: flex; gap: var(--space-xs); flex-wrap: wrap; margin-bottom: var(--space-xs); }
  .td-btn { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px;
    border-radius: var(--radius-full); background: var(--bg-elevated);
    border: 1px solid var(--border); color: var(--text-secondary);
    font-size: var(--font-tiny); cursor: pointer;
    transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .td-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-subtle); }
  .td-btn.areNota { color: var(--accent); }
  .td-nota { margin-bottom: var(--space-sm); font-size: var(--font-tiny); color: var(--text-secondary); }

  .task-list { display: flex; flex-direction: column; }
  .trow-wrap { display: flex; flex-direction: column; background: var(--bg-panel);
    border: 1px solid var(--border); border-left: 3px solid var(--sev, var(--border-strong));
    border-radius: var(--radius-md); margin-bottom: 6px; overflow: hidden;
    transition: border-color var(--dur-fast) var(--ease); }
  /* `border-left-color` redeclarat: `border-color` scurt vopseste TOATE laturile,
     deci hover-ul stergea tocmai bordura de severitate — culoarea rezervata. */
  .trow-wrap:hover { border-color: var(--border-strong); border-left-color: var(--sev, var(--border-strong)); }
  /* UN SINGUR obiect: rama, fundalul si colturile stau pe WRAPPER. Randul si
     extinderea sunt continutul lui, fara rame proprii — altfel se citeau ca doua
     cutii lipite („de parca sunt rupte in doua"). */
  /* Tranzitia acopera si `transform`: acelasi rand exista pe Acasa (.arow) si in
     pagina de proiect, unde deplasarea de hover se face lin — aici lipsea din
     lista si randul SAREA 4px la intrarea cursorului. Doua liste cu acelasi rand
     n-au voie sa raspunda diferit la acelasi gest. */
  .trow { position: relative; display: flex; align-items: center; gap: var(--space-sm); padding: 8px var(--space-sm) 10px; background: none; border: 0; transition: transform var(--dur-fast) var(--ease), opacity var(--dur-base) var(--ease); }
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
  .tix { font-family: var(--font-mono); font-size: 0.8rem; font-weight: var(--fw-medium); letter-spacing: -0.02em; color: color-mix(in srgb, var(--sev, var(--border-strong)) 38%, transparent); min-width: 28px; flex-shrink: 0; font-variant-numeric: tabular-nums; }
  .trow.done { opacity: 0.5; }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; }
  .check:hover { color: var(--accent); }
  .trow.done .check { color: var(--success); }
  .check-empty { width: 18px; height: 18px; border: 2px solid var(--border); border-radius: 50%; }
  .check-empty.small { width: 14px; height: 14px; }
  .check:hover .check-empty { border-color: var(--accent); }
  .tmain { flex: 1; min-width: 0; cursor: pointer; text-align: left; }
  .ttitle-row { display: flex; align-items: center; gap: var(--space-xs); min-width: 0; }
  .tchev { display: inline-flex; align-items: center; color: inherit; flex-shrink: 0; }
  .ttitle { font-size: var(--font-body); color: var(--text); font-weight: var(--fw-medium); flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  .note-ind { display: inline-flex; align-items: center; color: var(--text-dim); }
  .tinfo { display: flex; gap: var(--space-sm); font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; align-items: center; }
  /* Categoria pleaca la capatul din dreapta (ca „Inbox" la Todoist): e ultima ca
     importanta, deci nu are voie sa stea intre ochi si termen. */
  .task-cat { margin-left: auto; padding: 1px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); font-weight: var(--fw-medium); flex: none; }
  .tdeadline { display: inline-flex; align-items: center; gap: 3px; }
  .task-actions { display: flex; align-items: center; gap: var(--space-xs); flex-shrink: 0; }
  /* Pe desktop invelisul de glisare nu exista pentru layout. */
  .gl-fata { display: contents; }
  .gl-actiuni { display: none; }
  .task-del { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .task-del:hover { color: var(--danger); background: var(--danger-subtle); }


  /* Corp expandat: panou inset (nu mai pluteste pe negru), continut grupat cu gap */
  /* Extinderea e CONTINUAREA randului, nu un card separat: se lipeste de el
     (randul isi pierde colturile de jos si marginea), preia bordura de severitate
     din stanga si sta pe acelasi fundal. Inainte pareau doua obiecte fara legatura. */
  /* Extinderea: continut in acelasi card, separat doar de o linie subtire. */
  .subtask-body { margin: 0; padding: var(--space-sm) var(--space-sm) var(--space-sm) 40px;
    border-top: 1px solid var(--border-subtle);
    display: flex; flex-direction: column; gap: 4px; }

  /* Actiuni discrete: chip-uri "+ Descriere / + Fisier" in loc de link-uri italic plutinde */
  /* Fara rand propriu pentru un singur buton: se aliniaza la stanga, discret. */


  /* ===== Foaia taskului ===== */
  .sub-cap { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: 6px; }
  .sub-cap-t { font-size: var(--font-micro); text-transform: uppercase;
    letter-spacing: var(--tracking-wide); font-weight: var(--fw-semibold); color: var(--text-faint); flex: none; }
  .sub-gol { font-size: var(--font-small); color: var(--text-dim); padding: var(--space-sm) 0; }
  /* Fiecare subtask e un card, ca la Todoist: pe fundalul foii randurile fara
     suprafata proprie se citeau ca un bloc de text, nu ca lucruri separate.
     O SINGURA declaratie: mai jos exista pana acum o a doua `.sub-row` (ramasa
     de la designul de lista), care la specificitate egala castiga fiind ultima
     si rescria TACUT padding-ul cardului la `3px 0` — adica un card desenat cu
     rama la 0px de text. Masurat inainte: padding calculat `3px 0` pe desktop,
     `2px 0` in foaie. Exact felul de abatere care nu arunca nicio eroare. */
  .sub-row { display: flex; align-items: center; gap: 6px;
    background: var(--bg-panel); border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md); padding: 4px 8px; margin-bottom: 5px; }
  .sub-row.sub-done { background: transparent; border-color: transparent; }
  .sub-nou { display: flex; align-items: center; justify-content: center; gap: 6px;
    width: 100%; min-height: var(--tap-min); margin-top: 2px;
    border: 1px dashed var(--border-strong); border-radius: var(--radius-md);
    background: none; color: var(--accent-on-subtle); font-size: var(--font-small);
    font-weight: var(--fw-semibold); cursor: pointer; transition: var(--transition-pressable); }
  .sub-nou:hover { background: var(--accent-subtle); border-color: var(--accent); }
  .sub-nou:active { transform: scale(0.99); }

  /* ===== Antetul foii ===== */
  .ts-cap { display: flex; align-items: flex-start; gap: var(--space-sm); margin-bottom: var(--space-sm); }
  .ts-check { flex: none; min-width: var(--tap-min); min-height: var(--tap-min);
    display: flex; align-items: center; justify-content: flex-start; color: var(--success);
    background: none; border: none; cursor: pointer; padding: 0; }
  .check-empty.big { width: 22px; height: 22px; border: 2px solid var(--border-strong); border-radius: 50%; }
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
  .ts-rand:active { transform: scale(0.995); }
  .ts-rand.activ { border-color: var(--accent); }
  .ts-val { flex: 1; color: var(--text); font-weight: var(--fw-medium); }
  .ts-val.overdue { color: var(--danger); }
  .ts-val.today { color: var(--accent); }
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
  .ts-zi:active { transform: scale(0.97); }
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
  .sub-loading { font-size: var(--font-tiny); color: var(--text-dim); padding: var(--space-xs) 0; }

  .mf-field { display: flex; flex-direction: column; gap: 4px; flex: 1; }
  .mf-label { font-size: var(--font-tiny); font-weight: var(--fw-medium); color: var(--text-secondary); text-transform: uppercase; letter-spacing: var(--tracking-wide); }
  .mf-input { padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-body); font-family: inherit; min-height: 40px; }
  .mf-input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }

  .task-edit.areNota { color: var(--accent-on-subtle); }
  .task-edit { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .task-edit:hover { color: var(--accent); background: var(--accent-subtle); }
  .recur-badge { display: inline-flex; align-items: center; gap: 3px; padding: 0 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-dim); font-weight: var(--fw-medium); }
  .tdeadline { font-size: var(--font-tiny); }
  .tdeadline.overdue { color: var(--danger); font-weight: var(--fw-semibold); }
  .tdeadline.today { color: var(--accent); font-weight: var(--fw-semibold); }
  .tdeadline.soon { color: var(--warning); }

  .task-form { display: flex; flex-direction: column; gap: var(--space-md); }
  .form-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-md); }

  .task-skeleton { padding: var(--space-sm) var(--space-md); }


  /* ===== V3: grid lista + agenda 7 zile ===== */
  .v3grid { display: grid; grid-template-columns: 1fr 300px; gap: 14px; align-items: start; }
  .list-cell { min-width: 0; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-md); }
  .list-label { margin-bottom: var(--space-12); }

  @media (max-width: 940px) {
    /* Agenda coboara sub lista (o singura coloana) */
    .v3grid { grid-template-columns: 1fr; }
  }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .toolbar { flex-direction: column; align-items: stretch; }
    .search-box { max-width: none; }
    .quick-add input, .quick-add-btn { min-height: 44px; }
    .quick-add-btn { width: 44px; }
    .task-del, .task-edit { opacity: 1; }
    .form-row-3 { grid-template-columns: 1fr; }
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
    .tix { display: none; }
    .tmain { min-height: 0; }
    .ttitle { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .tinfo { flex-wrap: nowrap; overflow: hidden; }
    .tinfo > * { flex-shrink: 0; }

    .gl-actiuni { display: flex; position: absolute; top: 0; right: 0; bottom: 0; z-index: 0; align-items: stretch; }
    .glb { width: 58px; display: flex; flex-direction: column; align-items: center; justify-content: center;
           gap: 3px; border: none; background: var(--bg-elevated); color: var(--text-secondary);
           font-size: var(--font-micro); cursor: pointer; }
    .glb span { line-height: 1; }
    .glb.danger { background: var(--danger-subtle); color: var(--danger); }
    .trow:global(.gl-bifa) { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }
    /* Cautarea si filtrele: caseta de cautare avea 25px inaltime utila, iar
       chipurile 30. */
    /* Ca la Proiecte: caseta are 44px, dar inputul dinauntru avea 25 si doar el
       primeste focus. */
    .search-box { max-width: none; align-items: stretch; padding: 0 14px; }
    .search-box input { align-self: stretch; min-height: var(--tap-min); }
    .search-box :global(svg) { align-self: center; }
    .chip { min-height: var(--tap-min); padding: 4px 16px; font-size: var(--font-small); }
    .filters { gap: var(--space-xs); }
    .tmain { min-height: var(--tap-min); }
    .mf-input { min-height: var(--tap-min); }
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

    /* Categoria devine text, nu pastila. Pe un rand ingust pastila mov era cel mai
       tare lucru de pe ecran — mai tare decat titlul si decat termenul, adica
       exact invers fata de cat conteaza. */
    .task-cat { background: none; color: var(--text-faint); padding: 0;
      font-weight: var(--fw-normal); }
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
    .v3grid :global(.agenda) { display: none; }

    /* Interiorul taskului deschis: aici se bifeaza subtaskuri si se scrie unul nou,
       deci sunt tinte ca oricare altele. Erau 28-39px. */
    .sub-add input, .sub-add-btn { min-height: var(--tap-min); }
    .sub-add-btn { width: var(--tap-min); }
    /* Cardul isi pastreaza padding-ul orizontal si pe telefon — `2px 0` de aici
       anula (a doua oara) rama-la-0px reparata mai sus. Vertical ramane strans:
       inaltimea o da oricum bifa de 40px. */
    .sub-row { padding: 2px 8px; }
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
    /* Stergerea ramane atingibila (44px), dar nu mai striga: pe telefon `:hover`
       nu exista, deci era o pubela plina, la fel de tare ca bifa, pe FIECARE
       rand. Ramane un semn stins intr-o tinta mare. */
    .sub-del { opacity: 1; width: var(--tap-min); height: var(--tap-min);
               color: var(--text-faint); background: none; }
    /* 1rem = 16px, aceeasi valoare pe CITIRE si pe SCRIERE. Regula globala urca
       oricum orice input la 16px pe telefon (zoom-ul Safari la focus), deci cu
       titlul la `--font-body` (14.4px) textul crestea cu 1.6px fix cand incepeai
       sa-l editezi. Egalarea se face in sus, nu in jos — sub 16 nu se poate. */
    .sub-title, .sub-edit { font-size: 1rem; }
    .qa-chip, .qa-dp :global(.dp-trigger) { min-height: var(--tap-min); padding: 0 16px;
      font-size: var(--font-small); }
    /* Indiciul despre Enter n-are cui sa se adreseze pe o tastatura de telefon. */
    .qa-hint { display: none; }
    .td-btn { min-height: var(--tap-min); padding: 0 16px; font-size: var(--font-small); }

    /* Calendarul din panoul de glisare: DatePicker-ul isi aduce declansatorul de
       camp, dar aici trebuie sa arate ca vecinii lui — o iconita cu o eticheta. */
    .glb.datewrap { position: relative; }
    .glb.datewrap :global(.dp) { position: absolute; inset: 0; width: auto; }
    .glb.datewrap :global(.dp-trigger) { width: 100%; height: 100%; min-height: 0;
      padding: 0 0 14px; justify-content: center; background: none; border: none;
      box-shadow: none; color: inherit; }
    .glb.datewrap :global(.dp-value) { display: none; }
    .glb.datewrap > span { position: absolute; left: 0; right: 0; bottom: 11px;
      text-align: center; pointer-events: none; }
  }
</style>
