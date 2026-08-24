<script module>
  import { urlGlobalTasks as _url } from '../stores/tasks.svelte.js'
  import { preia as _preia } from '../lib/cache.js'

  /** Chemata de router la hover pe tabul din Doc, INAINTE de schimbarea rutei.
   *  Fara ea, hoverul aducea doar chunkul paginii, iar cererea de date pornea
   *  abia la montare — deci prima intrare pe tab in fiecare sesiune trecea
   *  printr-un schelet, oricat de repede venea codul.
   *  URL-ul vine din store, unde il construieste si `loadGlobalTasks`: doua sabloane
   *  ale aceluiasi raspuns n-ar mai nimeri aceeasi intrare in cache, si atunci
   *  preincarcarea ar face o cerere in plus fara sa scoata scheletul. */
  export function pregateste() {
    return _preia(_url({ sfera: 'toate' }), { proaspat: 5000 })
  }
</script>

<script>
  import { ecran } from '../lib/ecran.svelte.js'
  import { inregistreaza } from '../lib/reincarcare.svelte.js'
  import { uita } from '../lib/cache.js'
  import { slide } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { motionDuration, DUR_BASE, plecare, sosire, alunecare, DUR_FAST, EASE, INTARZIERE_BIFA } from '../lib/motion.svelte.js'
  // Acelasi puls de prag ca la glisarea unui rand: doua gesturi diferite, dar
  // „ai trecut pragul" trebuie sa se simta la fel, altfel se invata separat.
  import { ListTodo, Plus, CheckCircle2, CalendarDays, ChevronDown, X, Check, Archive, Briefcase, User, Text, Bell, BellRing, Info, AlarmClockOff, ExternalLink } from '@lucide/svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import { globalTasks, loadGlobalTasks, updateGlobalTask, createGlobalTask, deleteGlobalTask, loadSubtasks, createSubtask, updateSubtask, deleteSubtask } from '../stores/tasks.svelte.js'
  import { formatDate, dueRing, isFutureRecurrence, esteDepasit as isOverdue, esteAzi as isToday } from '../lib/formatters.js'
  import { grupeazaDupaTermen, etichetaTermen, etichetaTermenScurt, ORDINE_GRUPE } from '../lib/grupare.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import { router, navigate } from '../lib/router.svelte.js'
  import { focusOnLand, focusKey } from '../lib/focus.js'
  import { glisare } from '../lib/glisare.js'
  import { apasareLunga } from '../lib/apasareLunga.js'
  import { puls } from '../lib/gesturi.js'
  import FoaieTask from '../components/FoaieTask.svelte'
  import FoaieAdauga from '../components/FoaieAdauga.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ContorPasi from '../components/ui/ContorPasi.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import Button from '../components/ui/Button.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import Input from '../components/ui/Input.svelte'
  import Textarea from '../components/ui/Textarea.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import SelectorZi from '../components/ui/SelectorZi.svelte'
  import Select from '../components/ui/Select.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  // EDITORUL LUNG NU E PE DRUMUL CRITIC AL LISTEI.
  //
  // Masurat pe 4G cu procesorul incetinit de patru ori, la prima deschidere pe
  // telefon: `EditorLung` -> `RichTextEditor` -> `katex` inseamna **257 KB de
  // KaTeX plus 58 KB de editor**, descarcate ca sa se afiseze o lista de
  // to-do-uri. Pe telefon aterizarea implicita E lista asta (`/tasks?sfera=
  // personal`), deci fix ecranul cu care se deschide aplicatia platea tipografia
  // matematica pe care n-o foloseste. In cascada, KaTeX termina la 1447ms si
  // tinea banda ocupata cat timp chunkul paginii inca venea.
  //
  // Acum vine cand ai nevoie de el, si e adus din vreme in liniste (vezi
  // `aduEditorul` + `onMount`). Deschiderea ASTEAPTA modulul — aceeasi regula ca
  // peste tot: un panou se deschide cu continutul in mana, nu inainte.
  let EditorLung = $state(null)
  let cerereEditor = null
  function aduEditorul() {
    if (!cerereEditor) {
      cerereEditor = import('../components/ui/EditorLung.svelte')
        .then((m) => { EditorLung = m.default })
        .catch((e) => { cerereEditor = null; throw e })
    }
    return cerereEditor
  }
  import RichText from '../components/ui/RichText.svelte'
  import { todayISO, addDays } from '../lib/calendarDates.js'
  import { apiJson } from '../lib/api.js'
  import { suportaPush, esteIosNeinstalat, stareAbonament, aboneaza, dezaboneaza } from '../lib/push.js'
  import { esteNativ, probeaza, reprogrameaza, alarmaExacta, deschideAlarmaExacta } from '../lib/notificari.js'
  import { inregistreazaActiune, consumaCerereTaskNou } from '../lib/actiuneNoua.svelte.js'

  // Sfera vine din URL (#/tasks?sfera=personal), nu din state local: vederea e
  // adresabila — un link din paleta, din cautare sau de pe Acasa aterizeaza
  // direct in ea. Orice altceva decat 'personal' inseamna munca (fail-closed,
  // ca pe server).
  const sferaActiva = $derived(router.query.sfera === 'personal' ? 'personal' : 'munca')

  let showArchive = $state(router.query.arhiva === '1')
  let taskDeleteId = $state(null)
  let showTaskDelete = $state(false)
  let showAdauga = $state(false)
  let creating = $state(false)

  let formTitle = $state('')
  /** Ce lipseste, scris pe camp — vezi nota de la formularul de editare. */
  let eroareTitlu = $state('')
  // Muchia de restant pleaca in clipa in care incepi sa repari, nu la urmatoarea
  // apasare pe „Salvează".
  $effect(() => { if (formTitle.trim() && eroareTitlu) eroareTitlu = '' })
  let formDesc = $state('')
  let formCategory = $state('General')
  let formDeadline = $state('')
  let formRecurenta = $state('')
  let editingTask = $state(null)
  let showEditModal = $state(false)

  let subtasksCache = $state({})
  let newSubtaskTitle = $state('')
  let adaugSubLa = $state('')   // id-ul taskului al carui compozitor de subtask e deschis

  let quickTitle = $state('')
  let quickAdding = $state(false)
  let showNoteModal = $state(false)
  let noteTask = $state(null)
  let noteDraft = $state('')
  let noteSalveaza = $state(null)



  /** Reincarcarea listei, mereu cu AMBELE filtre ale vederii curente. Un singur
   *  drum: fara el, un call-site uitat cu `loadGlobalTasks()` gol ar repicta
   *  vederea Personal cu lista de munca. */
  // `sfera: 'toate'` — AMBELE sfere vin intr-un singur raspuns, iar comutarea
  // Munca/Personal e filtrare in memorie, instanta (Ion: comutarea „este
  // deficienta" — fiecare atingere astepta un dus-intors cu serverul).
  const reload = () => loadGlobalTasks({ arhiva: showArchive, sfera: 'toate' })

  // Hide a recurring task's next occurrence until its scadenta arrives, so finalizing
  // today's instance doesn't look like an identical unchecked copy reappearing.
  // Sfera se filtreaza AICI, nu pe server: `items` tine ambele sfere (un singur
  // fetch cu `sfera=toate`), deci comutarea e o filtrare in memorie. `sfera`
  // NULL pe randuri vechi inseamna 'munca' — aceeasi conventie ca in DB.
  const activeTasks = $derived(globalTasks.items.filter(t =>
    t.status !== 'done' && !isFutureRecurrence(t) && (t.sfera || 'munca') === sferaAfisata))
  // NU exista `doneTasks` in vederea activa: `/api/global-tasks` adauga
  // `AND status != 'done'` cand nu ceri arhiva, deci lista nu contine niciodata
  // taskuri bifate. Aici traia o sectiune „N finalizate" pliabila, cu randuri
  // proprii si stil propriu — gardata pe `!showArchive && doneTasks.length > 0`,
  // adica pe o conditie care nu putea fi adevarata. Cod viu si corect, care nu
  // s-a randat niciodata. Ce ai terminat se vede in „Arhivă".

  // Lista se citeste de sus in jos ca o zi de lucru: restante, azi, mâine, restul.
  // In arhiva gruparea n-ar spune nimic (toate sunt facute), deci ramane o grupa
  // fara cap — acelasi drum de randare, zero markup duplicat.
  // STAREA AFISATA, nu comutatoarele vii: cat timp cererea de arhiva e pe drum,
  // lista VECHE ramane pe ecran (vezi `listaCheie`) — si trebuie filtrata si
  // grupata dupa regula EI, altfel continutul ar sari inainte de alunecare.
  // Sfera comuta instant (nu cere retea), deci pentru ea cele doua coincid.
  const arhivaAfisata = $derived(listaCheie.endsWith(':true'))
  const sferaAfisata = $derived(listaCheie ? listaCheie.split(':')[0] : sferaActiva)
  const grupe = $derived(arhivaAfisata
    ? { arhiva: { id: 'arhiva', titlu: null, ton: 'sters', items: globalTasks.items.filter(t => (t.sfera || 'munca') === sferaAfisata), start: 0 } }
    : grupeazaDupaTermen(activeTasks))
  // Arhiva e o grupa fara cap, pusa la coada ordinii — acelasi drum de randare.
  const ordine = [...ORDINE_GRUPE, 'arhiva']
  const nrRestante = $derived(grupe.restant?.items.length || 0)

  /** Ce scrie coloana de termen. Un task RECURENT isi spune cadenta, nu data:
   *  „când" pentru el nu e o zi, e un ritm, iar data urmatoarei aparitii se
   *  regenereaza singura la fiecare bifare. */
  function termenScurt(t) {
    if (t.recurenta && !t.data_scadenta) return t.recurenta
    // Pe „azi", ora bate cuvantul — vezi nota lunga din `TodayBoard.svelte`. Aici
    // lista acopera mai multe zile, deci inlocuirea se face DOAR pe azi: pe „mâine"
    // ziua e inca informatia care deosebeste randurile intre ele.
    if (t.ora && isToday(t.data_scadenta)) return t.ora
    return etichetaTermenScurt(t.data_scadenta)
  }

  /** Contorul de pasi de pe rand („2/5"), sau `null` cand taskul n-are subtaskuri.
   *
   *  CEA MAI PROASPATA SURSA CASTIGA. Serverul trimite `subtask_total`/`_done` cu
   *  lista, dar cat timp randul e desfacut adevarul e in `subtasksCache`: bifarea
   *  unui pas o scrie ACOLO si nu reincarca lista (vezi `toggleSubtaskDone`), deci
   *  citit doar de la server contorul ar sta nemiscat exact in clipa in care il
   *  privesti si il schimbi.
   *  Un `[]` in cache inseamna „am intrebat, n-are niciunul" — nu „nu stiu" — deci
   *  are prioritate si el, si scoate contorul de pe rand. */
  function pasi(t) {
    const subs = subtasksCache[t.id]
    const total = subs ? subs.length : (t.subtask_total || 0)
    if (!total) return { total: 0, gata: 0 }
    return { total, gata: subs ? subs.filter(s => s.done).length : (t.subtask_done || 0) }
  }

  // Randul care isi joaca STAMPILA chiar acum (contractul de miscare: bifare =
  // stampila + taietura care matura + textul care se stinge, apoi randul pleaca).
  // Regulile traiesc in global.css (`.bifare`); aici doar clipa.
  let bifatAcum = $state('')
  let toggling = $state(false)

  async function toggleStatus(task, dinGest = false) {
    if (toggling) return
    toggling = true
    try {
      const next = task.status === 'done' ? 'to_do' : 'done'
      // STAMPILA INAINTE DE PLECARE — dar nu si pe gest: la glisare verdele
      // pistei si zborul randului sunt deja raspunsul, iar a doua animatie peste
      // aceiasi pixeli ar incalca „o singura animatie pe schimbare".
      if (next === 'done' && !dinGest) {
        bifatAcum = task.id
        await new Promise(r => setTimeout(r, motionDuration(INTARZIERE_BIFA)))
        bifatAcum = ''
      }
      // OPTIMIST, ca randul sa plece IN CLIPA in care il atingi.
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
      if (next === 'done') {
        toastUndo(`Făcut: ${task.titlu.slice(0, 34)}${task.titlu.length > 34 ? '…' : ''}`, {
          onUndo: async () => {
            await updateGlobalTask(task.id, { status: 'to_do' })
            await reload()
          },
        })
      }
    } finally { toggling = false }
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

  /** Ora unui task personal (v41). `''` o scoate.
   *
   *  Fara `toastUndo`, si e o alegere, nu o omisiune: ora se pune din randul care o
   *  ARATA, iar valoarea veche rămâne pe ecran pana o schimbi — deci „inapoi" e
   *  chiar controlul din care ai venit. Un toast peste el ar acoperi exact randul
   *  pe care te uiti. Termenul are toast fiindca acolo randul PLEACA din grupa lui
   *  si nu mai ai de unde sa-l intorci.
   */
  async function setOra(t, v) {
    if (!t) return
    try {
      await updateGlobalTask(t.id, { ora: v || '' })
      await reload()
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

  function openEditModal(t) {
    editingTask = t
    formTitle = t.titlu || ''
    formDesc = t.descriere || ''
    formCategory = t.categorie || 'General'
    formDeadline = t.data_scadenta || ''
    formRecurenta = t.recurenta || ''
    eroareTitlu = ''
    showEditModal = true
  }

  // `handleCreate` si modalul „Task Nou" au plecat in `components/FoaieAdauga.svelte`.
  // Aici mai raman DOUA cai de adaugare, si niciuna nu e un formular: linia rapida
  // de mai jos (desktop) si butonul plutitor care deschide foaia (telefon).
  // `resetForm` si `campTitlu` au plecat cu el — al doilea exista doar ca sa dea
  // focusul campului „Titlu" prin `flushSync`, iar foaia isi gestioneaza singura
  // focusul (si pe telefon dinadins NU-l ia, ca sa nu cheme tastatura peste
  // sosirea foii). Starea `form*` rămâne: o foloseste modalul de EDITARE.

  // Adaugarea si planificarea sunt ACELASI gest, nu doua.
  // Inainte: scriai titlul, Enter, si taskul cadea in „fara termen"; ca sa-i pui o
  // zi trebuia sa-l gasesti in lista, sa glisezi, sa deschizi editorul. Practic
  // fiecare task nou nascut fara data, si sertarul crestea. Acum, cat timp ai text
  // in camp, sub el apar „Azi / Mâine / Alege data" — Enter tot inseamna „fara
  // termen", pentru ca uneori chiar asta vrei.
  let quickInput = $state(null)
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
      }, { arhiva: showArchive, sfera: 'toate' })
      quickTitle = ''
      quickData = ''
      quickInput?.focus()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { quickAdding = false }
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
   *  un toast cu „Anulează" (vezi bifarea unui task, mutarea unui termen).
   *  Ritualul asta traieste acum intr-un singur loc — `EditorLung` — si e acelasi
   *  pentru toate cele patru campuri lungi din aplicatie. */
  async function openNoteModal(t) {
    noteTask = t
    noteDraft = t.descriere || ''
    noteSalveaza = async (text) => {
      await updateGlobalTask(t.id, { descriere: text })
      await reload()
    }
    // Modulul se cere INAINTE de `open`: altfel `{#if EditorLung}` ar fi fals in
    // clipa in care steagul devine adevarat, iar modalul s-ar deschide gol si ar
    // primi continutul dupa — exact saritura reparata la modalul de pe Acasa.
    // De obicei e deja adus (`onMount` il cere in liniste), deci nu se asteapta.
    await aduEditorul()
    showNoteModal = true
  }

  async function handleEdit() {
    if (!editingTask) return
    if (!formTitle.trim()) { eroareTitlu = 'Un task are nevoie de un titlu.'; return }
    eroareTitlu = ''
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
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
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
    // Subtaskurile INAINTE de foaie, cand se poate: o foaie care se ridica pe
    // jumatate goala si apoi creste sub degetul tau arata ca doua evenimente
    // pentru un singur gest. Dar „inainte" nu poate insemna „oricat": prin tunel,
    // prima deschidere a unui task costa 300-800ms in care atingerea nu primeste
    // NIMIC inapoi — masurat: 900ms fara foaie, si gestul se repeta.
    // Compromisul: un tact scurt (cache-ul si reteaua locala intra in el), apoi
    // foaia se ridica ORICUM — cu un schelet de exact atatea randuri cate spune
    // contorul de pe rand (`subtask_total`), la aceeasi inaltime ca randurile
    // reale. Cand sosesc, iau locul scheletului fara ca foaia sa se miste.
    const date = incarcaSubtaskuri(taskId)
    await Promise.race([date, new Promise(r => setTimeout(r, 120))])
    showSheet = true
  }

  // ===== FOAIA DE ACTIUNI (apasare lunga pe rand) =====
  //
  // GLISAREA nu se schimba: ea deschide foaia taskului cu panoul de termen deja
  // desfacut, adica ACELASI `SelectorZi` pe care il arata foaia de actiuni in
  // celelalte trei liste — doar intr-o gazda mai bogata, fiindca aici exista una.
  // Apasarea lunga aduce ce lipsea de tot pe telefon: „Șterge" (randul isi ascunde
  // actiunile sub 768px, iar foaia taskului n-are buton de stergere), plus
  // „Deschide" si „Mută pe mâine" fara sa treci prin foaia mare.
  let foaieTask = $state(null)
  let foaieDeschisa = $state(false)
  // Taskul pe care foaia de adaugare il EDITEAZA. Se stinge la inchidere, altfel
  // urmatorul „+" ar redeschide ultima editare.
  let taskEditat = $state(null)

  function deschideFoaiaActiuni(t) {
    foaieTask = t
    foaieDeschisa = true
  }

  // Stergere reversibila, aceeasi mecanica ca la `removeSubtask` de mai jos.
  // Butonul „Șterge" de pe desktop pastreaza `ConfirmDialog`-ul lui: acolo apesi
  // un buton anume, deci intrebarea are sens; aici actiunea vine dintr-un gest si
  // plasa e undo-ul, nu o confirmare in plus.
  function stergeDinLista(t) {
    const idx = globalTasks.items.findIndex(x => x.id === t.id)
    if (idx === -1) return
    const scos = globalTasks.items[idx]
    globalTasks.items = globalTasks.items.filter(x => x.id !== t.id)
    toastUndo('Task șters', {
      onUndo: () => {
        const cur = [...globalTasks.items]
        cur.splice(Math.min(idx, cur.length), 0, scos)
        globalTasks.items = cur
      },
      onCommit: async () => {
        try { await deleteGlobalTask(t.id); await reload() }
        catch (e) { toast(`Eroare: ${e.message}`, 'error'); await reload() }
      },
    })
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
      } catch (e) {
        // Si pe eroare cheia se scrie: panoul se deschide gol, cu invitatia de
        // adaugare. Fara ea, `toggleTaskExpand` n-ar avea ce arata si atingerea
        // randului ar ramane fara raspuns.
        console.error('Subtaskuri:', e)
        subtasksCache = { ...subtasksCache, [taskId]: [] }
        toast('Nu s-au putut încărca subtaskurile', 'error')
      } finally {
        inZbor.delete(taskId)
      }
    })()
    inZbor.set(taskId, p)
    return p
  }

  // ISTORIC, in doua randuri: intai foaia pe desktop a fost RESPINSA de Ion
  // (modal centrat peste lista = context acoperit) si taskul se desfacea in
  // rand; pe 2026-08-09, la verificarea pe capturi, Ion a cerut PANOUL LATERAL
  // din desenul 3a — care nu acopera lista, sta langa ea. Deci: foaie pe
  // telefon, panou pe desktop, expandarea in rand a ramas doar cod istoric.
  // DESIGNUL ramane acelasi in ambele gazde: `taskDetail` e UN SINGUR snippet.
  //
  // ORDINEA CONTEAZA: intai datele, apoi deschiderea. Invers (cum era), panoul
  // se randa cu „Se încarcă…", `slide` masura ACEA inaltime si animeaza spre
  // ea — iar sectiunea de subtaskuri, sosita dupa aceea, aparea taiata peste
  // panoul deja terminat de animat. Un gest, doua evenimente vizuale.
  // Acum se deschide o singura data, cu ansamblul intreg si inaltimea finala.
  // PE DESKTOP TASKUL SE DESCHIDE IN PANOU LATERAL (decizia lui Ion la
  // verificarea finala din 2026-08-09, dupa desenul Taskuri 3a — RASTOARNA
  // decizia veche „se desface in lista", pastrata mai sus doar ca istorie).
  // Acelasi drum ca foaia de pe telefon: `deschideFoaia` incarca datele INAINTE
  // sa deschida, deci panoul soseste cu ansamblul intreg; difera doar gazda —
  // `Modal size="panou"` pe desktop, foaie jos pe telefon. Al doilea click pe
  // acelasi rand inchide panoul, ca vechiul expand.
  async function toggleTaskExpand(taskId) {
    if (!ecran.telefon && showSheet && sheetTask?.id === taskId) {
      showSheet = false
      return
    }
    await deschideFoaia(taskId)
  }

  // Asteptarea de mai sus se plateste O DATA per task si, pe desktop, de obicei
  // deloc: mouse-ul trece pe rand inainte sa apese, deci subtaskurile sunt deja
  // in `subtasksCache` cand vine clicul. `incarcaSubtaskuri` iese imediat daca
  // exista cheia, deci trecerea peste zece randuri nu inseamna zece cereri de
  // fiecare data.
  function preincarca(taskId) {
    if (!ecran.telefon) incarcaSubtaskuri(taskId)
  }


  let subtaskBusy = $state(new Set())

  async function toggleSubtaskDone(sub) {
    if (subtaskBusy.has(sub.id)) return
    subtaskBusy = new Set([...subtaskBusy, sub.id])
    const next = sub.done ? 0 : 1
    subtasksCache = {
      ...subtasksCache,
      [sub.task_id]: subtasksCache[sub.task_id].map(s => s.id === sub.id ? { ...s, done: next } : s)
    }
    try {
      await updateSubtask(sub.id, { done: next })
    } catch (e) {
      subtasksCache = {
        ...subtasksCache,
        [sub.task_id]: subtasksCache[sub.task_id].map(s => s.id === sub.id ? { ...s, done: sub.done } : s)
      }
      toast(`Eroare: ${e.message}`, 'error')
    } finally {
      const s = new Set(subtaskBusy); s.delete(sub.id); subtaskBusy = s
    }
  }

  let addingSubtask = $state(false)

  async function addSubtask(taskId) {
    if (!newSubtaskTitle.trim() || addingSubtask) return
    addingSubtask = true
    try {
      await createSubtask(taskId, newSubtaskTitle.trim())
      newSubtaskTitle = ''
      const subs = await loadSubtasks(taskId)
      subtasksCache = { ...subtasksCache, [taskId]: Array.isArray(subs) ? subs : [] }
      await reload()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { addingSubtask = false }
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
    try {
      await updateSubtask(sub.id, { titlu: nou })
      subtasksCache = {
        ...subtasksCache,
        [sub.task_id]: (subtasksCache[sub.task_id] || []).map(s => s.id === sub.id ? { ...s, titlu: nou } : s),
      }
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  // Deschide direct in scriere, cu textul selectat: de cele mai multe ori
  // rescrii randul, nu adaugi la el.
  function focalizeaza(node) { node.focus(); node.select() }

  // APASAREA LUNGA A PLECAT IN `lib/apasareLunga.js`.
  //
  // Era scrisa aici, cu doua constante proprii (`PRAG_LUNG = 300`,
  // `PRAG_MISCARE = 8`) care erau copii ale lui `APASARE_LUNGA` si
  // `PRAG_DIRECTIE` din `gesturi.js`, si cu un `navigator.vibrate?.(12)` inline
  // in loc de `puls()`. Cand acelasi gest a fost cerut si pe RANDUL de task (foaia
  // de actiuni), copierea ar fi ajuns la trei perechi de valori pentru acelasi
  // „cat de mult tin apasat" — exact ce previne `gesturi.js`.
  // Semnatura s-a schimbat: obiect (`{ actiune, activ, ignora }`), nu functie
  // simpla, fiindca randul are nevoie si de „doar pe telefon" si de o zona
  // exclusa (manerul de reordonare).

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

  // INTREBAREA DE STERGERE SE SCRIE CU NUMELE SI CU CE DISPARE ODATA CU EL.
  // Vezi `ConfirmDialog`: butonul poarta verbul si obiectul, iar consecinta are
  // voie sa fie un numar, fiindca ea decide actiunea.
  //
  // Subtaskurile se numara din `subtasksCache`, care e deja plin cand se poate
  // apasa „Șterge": pe desktop butonul apare la hover, iar hoverul chema deja
  // `preincarca`; in foaie le incarca `deschideFoaia` inainte s-o ridice. Daca
  // totusi n-au apucat sa vina, propozitia NU inventeaza o cifra — spune doar ce
  // stie sigur.
  const taskDeSters = $derived(globalTasks.items.find(x => x.id === taskDeleteId) || null)
  const subDeSters = $derived(taskDeleteId ? (subtasksCache[taskDeleteId] || null) : null)

  async function doDeleteTask() {
    if (!taskDeleteId) return
    try {
      await deleteGlobalTask(taskDeleteId)
      taskDeleteId = null
      await reload()
      toast('Task șters', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }



  // isOverdue/isToday vin din formatters.js (esteDepasit/esteAzi): aceeasi axa
  // si aceleasi praguri ca dueRing(), o singura definitie.

  // Banda de carduri urgente a plecat (Ion, 2026-07-27: „cardurile astea ce apar
  // nu am nevoie de ele"): repeta primele randuri din lista de imediat dedesubt,
  // care oricum e sortata cu urgentele sus si are aceleasi actiuni.


  // INTEGRAREA GOOGLE CALENDAR A PLECAT DE TOT (Ion, 2026-08-10: „sterge
  // integrarea google calendar"). Intai butonul si modalul din interfata, apoi
  // serverul: `blueprints/google_calendar.py`, rutele `/api/google/*` si
  // `/oauth/google/*`, apelurile de sincronizare din tasks.py/push.py, si
  // cheile `google_*` din `app_settings` (migrarea v40 le sterge — tokenul de
  // refresh n-avea ce cauta intr-un backup de la care filtrul tocmai plecase).
  // Ce NU s-a atins: feedul `.ics` (`/api/export/ics`), care e o abonare prin
  // URL, fara OAuth, si merge in orice calendar. Daca integrarea se reia
  // vreodata, se reia din istoricul git, cu ambele capete.

  // Punctul rosu de pe clopotel trebuie sa poata semnala o trimitere esuata
  // FARA sa deschizi modalul — o stare care decide ce primesti dimineata nu
  // are voie sa fie invizibila.
  // O DATA PER SESIUNE, NU DOAR IN SFERA PERSONAL (T15).
  // Starea se cerea numai cand intrai in „Personal", iar punctul rosu se randa
  // tot numai acolo — deci o trimitere esuata ramanea invizibila cat timp
  // lucrai in „Muncă", adica exact in sfera in care esti toata ziua. O stare
  // stricata trebuie sa se vada de unde te afli, nu de unde ai fi putut fi.
  $effect(() => {
    if (pushStatus === null) {
      apiJson('/api/push/status').then(s => { pushStatus = s }).catch(() => {})
    }
  })

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

  // Alarma exacta: `null` = intrebarea n-are sens aici (web, sau Android sub 12).
  let exacta = $state(null)

  async function pornesteAlarma() {
    try {
      await deschideAlarmaExacta()
      // Se re-citeste la revenirea in aplicatie, nu acum: ecranul de sistem e
      // deschis peste noi, iar raspunsul vine dupa ce-l inchizi.
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function deschidePush() {
    // Setarile se cer la DESCHIDEREA ferestrei, nu la incarcarea paginii: sunt
    // folosite doar aici, si o cerere in plus la fiecare intrare pe Taskuri ar
    // fi trafic pentru un ecran pe care il deschizi de doua ori pe an.
    if (!setari) {
      apiJson('/api/push/setari').then((s) => { setari = s }).catch(() => {})
    }
    alarmaExacta().then((v) => { exacta = v }).catch(() => {})
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

  // SETARILE DE NOTIFICARI. Stau pe SERVER, deci sunt aceleasi de pe orice
  // dispozitiv si supravietuiesc unei reinstalari.
  //
  // NU MAI SUNT ASCUNSE PE WEB. Erau gardate pe `esteNativ()`, cu motivul „pe web
  // nu exista canalul local pe care sa-l regleze" — dar cele patru reglaje nu sunt
  // ale canalului, sunt ale REGULII, iar regula o citeste si planificatorul de pe
  // server (`check_and_send_daily`). Deci ora la care suna telefonul se schimba de
  // pe telefon si de nicaieri altundeva, desi setarea era comuna. Se arata oriunde
  // exista ceva de programat: nativ mereu, pe web cand exista macar un dispozitiv
  // abonat (nu neaparat asta — de pe PC regleze ce suna pe telefon).
  let setari = $state(null)
  let setariEroare = $state('')
  const oreDisponibile = Array.from({ length: 24 }, (_, h) => ({
    value: h, label: `${String(h).padStart(2, '0')}:00`,
  }))
  const arataSetari = $derived(
    esteNativ() || (pushStatus?.disponibil && (pushLocal?.abonat || pushStatus?.abonamente > 0))
  )

  async function salveazaSetari() {
    if (pushBusy || !setari) return
    pushBusy = true
    setariEroare = ''
    try {
      // Serverul valideaza si INTOARCE forma normalizata — o folosim pe aia, nu
      // pe cea din formular: altfel un camp corectat de server (numar venit ca
      // text din <input type=number>) ar ramane afisat gresit.
      const { programate, ...salvate } = await apiJson('/api/push/setari', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        // SE TRIMIT TOATE, nu doar cele patru de dinainte.
        //
        // `deplasari` si `oraDeplasare` lipseau din corp, iar serverul completeaza
        // ce nu primeste din IMPLICITE (`_valideaza_setari` porneste de la
        // `SETARI_IMPLICITE`, nu de la ce e in baza) — deci stingeai „Seara
        // dinaintea unei plecări", salvai, si se reaprindea singura. Un comutator
        // care nu-si tine starea te invata ca setarile mint, exact ce spune nota de
        // la `taskuri_scadente` din `push.py`.
        // Gasit adaugand `oreExacte`: el ar fi avut exact aceeasi soarta.
        body: JSON.stringify({
          ora: Number(setari.ora), zileVechime: Number(setari.zileVechime),
          scadente: !!setari.scadente, faraTermen: !!setari.faraTermen,
          oreExacte: !!setari.oreExacte,
          deplasari: !!setari.deplasari, oraDeplasare: Number(setari.oraDeplasare),
        }),
      })
      setari = salvate
      // SALVAREA CONFIRMA CU UN NUMAR. O setare de notificari se verifica altfel
      // abia a doua zi dimineata, deci fara numar nu ai de unde sti daca a prins.
      // Pe telefon numarul vine din reprogramarea locala — care se face IMEDIAT,
      // altfel alarmele deja puse ar suna la ora veche pana la urmatoarea
      // deschidere a aplicatiei. Pe web il da serverul: cate pleaca data viitoare.
      let cate = programate ?? 0
      if (esteNativ()) {
        // Si perioadele, nu doar taskurile: de la turul 15 incoace reprogramarea
        // pune si alarma de plecare pe teren, iar ea se calculeaza din deplasari.
        const [d, cal] = await Promise.all([
          apiJson('/api/global-tasks?sfera=personal'),
          apiJson(`/api/calendar?start=${todayISO()}&zile=60`).catch(() => null),
        ])
        cate = await reprogrameaza(Array.isArray(d) ? d : d.tasks || [], salvate,
                                   cal?.perioade || [])
      }
      await reincarcaPush()
      toast(`Salvat — ${cate} ${cate === 1 ? 'notificare programată' : 'notificări programate'}.`, 'success')
    } catch (e) {
      setariEroare = e.message
    } finally { pushBusy = false }
  }

  // Un singur $effect in loc de onMount + load-uri explicite pe chip-uri: ruleaza
  // la montare SI ori de cate ori se schimba sfera (din URL) sau arhiva — trei
  // declansatoare, un singur drum, fara dublu-load.
  // FARA sferaActiva printre dependinte: sfera nu mai cere retea (vine „toate"
  // dintr-un foc), deci comutarea ei nu redeclanseaza fetch-ul.
  $effect(() => { loadGlobalTasks({ arhiva: showArchive, sfera: 'toate' }) })

  // TRAGE SA REINCARCI. `uita` inainte de `reload`: fara el cererea s-ar servi
  // din cache si gestul ar roti degeaba — adica ar minti exact in singurul caz
  // in care e chemat, cand banuiesti ca ce vezi nu mai e adevarat.
  $effect(() => inregistreaza(async () => { uita('/api/global-tasks'); await reload() }))

  // Arhiva in URL: starea supravietuieste unui refresh.
  $effect(() => {
    const arhiva = showArchive
    const hash = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : ''
    const qi = hash.indexOf('?')
    const path = qi === -1 ? hash : hash.slice(0, qi)
    const params = new URLSearchParams(qi === -1 ? '' : hash.slice(qi + 1))
    if (arhiva) params.set('arhiva', '1')
    else params.delete('arhiva')
    const qs = params.toString()
    const target = '#' + (path || '/tasks') + (qs ? '?' + qs : '')
    if (window.location.hash !== target) {
      history.replaceState(null, '', target)
    }
  })

  // Editorul lung se aduce IN LINISTE, dupa ce pagina e gata de folosit — nu la
  // import, unde ar sta pe drumul critic al primei deschideri (vezi
  // `aduEditorul`), si nu abia la prima atingere, unde s-ar simti.
  // `requestIdleCallback` cu plafon: pe un telefon care nu sta niciodata degeaba
  // n-are voie sa amane la nesfarsit. Rezerva pentru Safari, care abia in 2025
  // l-a primit si tot poate lipsi in WebView-uri mai vechi.
  $effect(() => {
    const cere = () => { aduEditorul().catch(() => {}) }
    if (typeof requestIdleCallback === 'function') {
      const id = requestIdleCallback(cere, { timeout: 2500 })
      return () => cancelIdleCallback(id)
    }
    const t = setTimeout(cere, 1200)
    return () => clearTimeout(t)
  })

  // CHEIA LISTEI SE SCHIMBA ABIA DUPA CE AU SOSIT DATELE (raportat de Ion:
  // „se incarca aiurea, parca se rupe pagina"). Cheiat direct pe sferaActiva,
  // lista se DEMOLA in clipa atingerii, aluneca inauntru cu taskurile sferei
  // VECHI (fetch-ul inca pe drum), si era demolata a doua oara cand soseau
  // cele noi — doua reconstructii intr-o suta de milisecunde. Acum lista veche
  // sta pe loc cat tine cererea, iar cea noua aluneca O DATA, gata umpluta —
  // aceeasi regula ca la deschiderea modalului („un panou se deschide numai cu
  // continutul masurabil").
  let listaCheie = $state('')
  let listaSens = $state(0)
  $effect(() => {
    const tinta = sferaActiva + ':' + showArchive
    if (listaCheie === tinta) return
    // SFERA NU ASTEAPTA RETEAUA, ARHIVA DA.
    //
    // Garda pe `loading` a fost scrisa cand comutarea sferei CEREA date. Nu mai
    // cere: lista vine „toate" dintr-un foc, iar sfera e o filtrare in memorie.
    // Ramasa peste tot, ea intarzia comutarea cu cat tinea o improspatare in
    // fundal — apasai „Personal" si nu se intampla nimic o zecime de secunda,
    // exact felul de intarziere care se citeste ca „aplicatia s-a blocat".
    // Arhiva chiar cere o cerere (`arhiva` e in dependintele fetch-ului), deci
    // ea asteapta mai departe.
    const doarSfera = listaCheie.split(':')[1] === String(showArchive)
    if (!doarSfera && globalTasks.loading) return
    // Prima asezare nu e o comutare: pagina soseste prin `.ruta-in`, nu
    // aluneca dintr-o parte (sens 0 = `alunecare` nu face nimic).
    listaSens = listaCheie === '' ? 0 : (showArchive ? 1 : (sferaActiva === 'personal' ? 1 : -1))
    listaCheie = tinta
  })

  // ===== DE CE NU EXISTA UN GEST DE COMUTARE A SFEREI =====
  //
  // A existat, in patru variante, si a plecat de tot (Ion: „scoate swipeul,
  // oricum nu e bine, sterge de tot in aplicatie"). Merita scris de ce, ca sa nu
  // fie reinventat a cincea oara.
  //
  // Intai a stat pe bara de unelte — 46px dintr-un ecran de 844, adica un gest
  // care practic nu exista. Apoi pe toata pagina, cu randurile exceptate. Apoi
  // intr-o banda de jos, fiindca pe un telefon inalt degetul mare nu ajunge
  // decat acolo. Apoi banda s-a ancorat la doc, cu prag de directie, de
  // dominanta si de viteza, si cu un veto care dadea gestul inapoi derularii.
  //
  // Fiecare tura a reparat ce se raportase si a lasat altceva stramb. Motivul de
  // fond: pe ACELASI ecran orizontala are deja doua intelesuri pe rand („Făcut"
  // la dreapta, „Planifică" la stanga), verticala e a derularii, iar comutarea
  // sferei ar fi al treilea verb pe doua axe — si singurul care trebuia sa se
  // strecoare printre celelalte. Tot esafodajul (banda, pragurile, vetoul)
  // exista ca sa tina separate niste gesturi care nu se pot separa curat.
  //
  // Comutarea are deja o unealta care nu se poate rata: cele doua segmente din
  // bara, cu pastila care aluneca intre ele. E la vedere, spune in ce sfera esti,
  // si o atingere gresita nu bifeaza niciun task.
  // BUTONUL "+" E AL DOCULUI ACUM (AURORA). Pagina spune doar CE creeaza el; cutia,
  // pozitia si materialul le tine `Dock.svelte`. Inainte, fiecare pagina cu lista
  // isi desena propriul `.fab` in coltul de jos - patru copii ale aceleiasi cutii,
  // care acopereau ultimul rand exact acolo unde te uitai.
  // `$effect` cheama singur curatarea la demontare si la fiecare schimbare a
  // conditiei, deci butonul dispare cand nu mai are ce crea (arhiva, alt tab).
  $effect(() => {
    if (!(ecran.telefon && !showArchive)) return
    return inregistreazaActiune('Task nou', () => { puls(); taskEditat = null; showAdauga = true })
  })

  // AM VENIT AICI APASAND „+" DE PE ALTA PAGINA. Foaia se deschide o data, la
  // sosire. `consuma...` sterge cererea in aceeasi chemare, deci o intoarcere
  // ulterioara pe pagina asta nu o redeschide.
  $effect(() => {
    if (!consumaCerereTaskNou()) return
    taskEditat = null
    showAdauga = true
  })
</script>

{#snippet taskDetail(t)}
  {@const subs = subtasksCache[t.id] || []}
  <!-- `subtasksCache[t.id]` lipsa = inca pe drum; se randeaza scheletul, cu
       atatea randuri cat stie contorul (vezi `deschideFoaia`). -->
  {@const peDrum = !subtasksCache[t.id] && (t.subtask_total || 0) > 0}

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
      {#if peDrum}
        <span class="sub-num">{t.subtask_done || 0}/{t.subtask_total}</span>
      {:else if subs.length}
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
           animate:flip={{ duration: motionDuration(DUR_BASE), easing: EASE }}
           in:sosire|local out:plecare
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
          <button class="sub-title" use:apasareLunga={{ actiune: () => incepeRedenumirea(sub) }}
                  onclick={() => { if (ecran.telefon) toggleSubtaskDone(sub); else incepeRedenumirea(sub) }}
                  title={ecran.telefon ? 'Atinge ca să bifezi · ține apăsat ca să redenumești' : 'Atinge ca să redenumești'}>{sub.titlu}</button>
        {/if}
        <button class="sub-del" onclick={() => removeSubtask(sub)}
                aria-label="Șterge subtaskul"><SolidIcon name="trash" size={13} /></button>
        </div>
      </div>
    {/each}

    {#if peDrum}
      {#each Array(Math.min(t.subtask_total, 8)) as _, i (i)}
        <div class="sub-row sub-schelet" aria-hidden="true">
          <Skeleton width="14px" height="14px" rounded />
          <Skeleton width={['62%', '78%', '48%', '70%'][i % 4]} height="12px" />
        </div>
      {/each}
    {:else if !subs.length}
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

<div class="page lista-ingusta">
  <!-- O SINGURA CALE DE ADAUGARE PER ECRAN.
       Erau doua, mereu amandoua pe ecran: butonul „+ Nou" din cap (deschide un
       formular cu patru campuri) si linia de scriere rapida din lista. Doua usi
       catre acelasi lucru inseamna ca de fiecare data alegi una — si niciuna nu
       devine reflex.
       Pe desktop ramane LINIA: ai tastatura, iar Enter e cel mai scurt drum de la
       gand la task. Pe telefon ramane BUTONUL mare, sub degetul mare — acolo o
       linie de text ceruta permanent inseamna tastatura deschisa peste lista.
       Subtitlul spune cate sunt deschise si cate restante: doua numere care chiar
       decid ceva (daca te apuci acum sau recuperezi). -->
  <div class="page-header">
    <div class="page-title-row">
      <h1>Taskuri</h1>
      <span class="ph-sub">{activeTasks.length} {activeTasks.length === 1 ? 'deschis' : 'deschise'}</span>
      {#if nrRestante}
        <span class="ph-restante"><span class="ph-punct"></span>{nrRestante} {nrRestante === 1 ? 'restant' : 'restante'}</span>
      {/if}
    </div>
  </div>

  <!-- CAUTAREA TRAIESTE INTR-UN SINGUR LOC: paleta din dock (Ctrl+K pe desktop,
       butonul de cautare in capul paginii pe telefon). Aici era un al doilea
       camp, care filtra doar lista curenta — deci acelasi gest („caut un task")
       avea doua unelte cu rezultate diferite: una gasea si taskuri de proiect si
       note, cealalta doar randurile din fata ta. Paleta le gaseste pe toate si
       aterizeaza pe randul cerut (`?focus=`), deci nu se pierde nimic.

       Ce ramane pe rand: SFERA — care nu e un filtru, ci in ce lume esti — si
       arhiva, o destinatie rara, in haina de actiune-fantoma. -->
  <div class="toolbar">
    <!-- CURSORUL DE TAB — singurul elastic din aplicatie (contractul de miscare).
         Fillul activ nu mai e fondul segmentului: e un CURSOR care ALUNECA de pe
         un segment pe celalalt (220ms, --ease-spring). Raportat de Ion: „nu pare
         sa fie o animatie de tranzitie nici la comutator". Segmentele sunt
         jumatati egale, ca translatia de 100% sa cada exact pe vecin. -->
    <div class="sfere" role="tablist" aria-label="Sfera taskurilor">
      <span class="seg-cursor" aria-hidden="true" style="--i:{sferaActiva === 'personal' ? 1 : 0}"></span>
      <button class="seg" role="tab" aria-selected={sferaActiva === 'munca'} class:on={sferaActiva === 'munca'} onclick={() => navigate('/tasks')}><Briefcase size={14} strokeWidth={1.5} />Muncă</button>
      <!-- Punctul de eroare sta pe SEGMENT, nu doar pe clopotel: clopotelul se
           randeaza doar in sfera Personal, deci o trimitere esuata nu avea unde
           sa se arate cat timp erai in „Muncă". -->
      <button class="seg" role="tab" aria-selected={sferaActiva === 'personal'} class:on={sferaActiva === 'personal'} onclick={() => navigate('/tasks?sfera=personal')}><User size={14} strokeWidth={1.5} />Personal{#if pushStatus?.last_error}<span class="seg-punct" title="O notificare nu a putut fi trimisă" aria-hidden="true"></span>{/if}</button>
    </div>
    <button class="a-ico" class:on={showArchive} aria-pressed={showArchive}
            onclick={() => { showArchive = !showArchive }}
            title={showArchive ? 'Înapoi la taskurile active' : 'Vezi arhiva'}>
      <Archive size={15} strokeWidth={1.5} /><span class="a-et">Arhivă</span>
    </button>
    {#if sferaActiva === 'personal'}
      <!-- NU chip: e o setare, nu un filtru. Sta LANGA „Arhivă" (cerinta Ion)
           — butonul Google Calendar care statea intre ele a plecat. -->
      <button class="g-ico" onclick={deschidePush} title="Notificări zilnice" aria-label="Notificări">
        <Bell size={15} strokeWidth={1.5} />
        {#if pushStatus?.last_error}<span class="g-punct" aria-hidden="true"></span>{/if}
      </button>
    {/if}
  </div>

  <div class="v3grid">
  <div class="list-cell cell-in">
  {#if !showArchive && !ecran.telefon}
    <form class="quick-add" onsubmit={(e) => { e.preventDefault(); quickAdd() }}>
        <!-- ACEEASI FORMA CA PE ACASA (A3, vezi `components/TodayBoard.svelte`).
             Aici statea un buton „+" langa camp, care facea exact ce face Enter —
             a doua cale catre aceeasi actiune, in acelasi loc. Plusul ramane, dar
             ca SEMN in interiorul campului: spune ce e linia asta fara sa mai fie o
             tinta de apasat. Bara asta se randeaza doar pe desktop, unde Enter e
             oricum singurul drum, si placeholderul o scrie.
             Ion, 2026-08-24: „bara din acasa si bara din taskuri si bara din
             proiecte de adaugare taskuri nu este la fel." -->
        <div class="qa-camp">
          <span class="qa-ico" aria-hidden="true"><Plus size={17} /></span>
          <input type="text" bind:this={quickInput}
                 placeholder="Task rapid... Enter pentru a adăuga"
                 bind:value={quickTitle} disabled={quickAdding} />
        </div>
      {#if quickTitle.trim()}
        <div class="qa-cand" transition:slide={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
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
  <!-- `!incarcat`, fara `loading`: daca n-avem inca un raspuns, ASTEPTAM — prin
       definitie. Cu `loading &&` in fata, primul cadru (inainte ca incarcarea sa
       apuce sa porneasca) cadea pe ramura urmatoare si arata STAREA GOALA, apoi
       scheletul, apoi raspunsul: trei forme pentru un board gol. -->
  {#if !globalTasks.incarcat && !globalTasks.error}
    <div class="asteptare"><Skeleton varianta="rand" randuri={4} /></div>
  {:else if globalTasks.error}
    <ErrorState message={globalTasks.error} onretry={() => reload()} />
  {:else if (arhivaAfisata ? grupe.arhiva.items.length : activeTasks.length) === 0}
    <!-- Golul se judeca pe SFERA AFISATA, nu pe tot raspunsul: `items` tine
         acum ambele sfere, deci „Personal gol" trebuie sa se vada si cand
         Munca e plina.
         Aceeasi stare acopera „n-ai avut niciodata taskuri" si „tocmai le-ai
         terminat pe toate" — pagina nu le poate deosebi, fiindca vederea activa
         nu contine cele bifate. Deci textul trebuie sa fie adevarat in amandoua
         si sa spuna unde au plecat cele facute. -->
    <EmptyState icon={ListTodo} title={showArchive ? 'Arhiva e goală' : (sferaActiva === 'personal' ? 'Niciun task personal' : 'Nimic de făcut')} description={showArchive ? 'Aici ajung taskurile bifate.' : 'Scrie un task în câmpul de sus. Ce ai terminat e în „Arhivă".'} />
  {:else}
    <!-- COMUTAREA SFEREI E O NAVIGARE MICA, deci are sens (raportat de Ion: „nu
         pare sa fie o animatie de tranzitie... nici la taskuri"). Lista noua
         soseste dinspre tabul pe care l-ai ales: Personal e in dreapta -> vine
         din dreapta; Munca din stanga. `{#key}` fiindca o clasa comutata nu
         re-porneste o animatie (aceeasi lectie ca la schimbarea lunii). -->
    <!-- Cheia include si arhiva: intrarea in arhiva aluneca dinspre dreapta
         (un loc „mai adanc"), iesirea dinspre stanga — aceeasi gramatica
         directionala ca sfera si ca luna din Calendar. `listaCheie`, nu
         sferaActiva direct: se schimba abia cand datele au sosit (vezi
         comentariul din script). -->
    {#key listaCheie}
    <div class="task-list" in:alunecare={{ sens: listaSens }}>
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
             fiecare rand: vezi „Restante 2" si stii ca ai doua de recuperat.
             UN NUMAR APARE DOAR DACA DECIDE O ACTIUNE, deci doar la Restante.
             La „Azi", „Mâine" sau „Fără termen" cifra nu schimba nimic — grupa e
             deschisa sub ea si o numeri din ochi — iar patru numere pe patru
             capete se citesc ca un antet de tabel, adica nu se mai citesc. -->
        <div class="grup-cap ton-{grupe[gid].ton}"><span class="grup-t">{grupe[gid].titlu}</span>{#if grupe[gid].ton === 'danger'}<span class="grup-n">{grupe[gid].items.length}</span>{/if}</div>
      {/if}
      {#each grupe[gid].items as t (t.id)}
<!-- Iesirea randului bifat: se stinge si se strange, in loc sa sara.
               Vezi `plecare` in lib/motion.svelte.js. -->
                    <div class="trow-wrap" role="presentation" class:deschis={showSheet && sheetTask?.id === t.id}
             style="--ring: {dueRing(t.data_scadenta)}"
             animate:flip={{ duration: motionDuration(DUR_BASE), easing: EASE }}
             onpointerenter={() => preincarca(t.id)}
             in:sosire|local out:plecare>
          <div class="trow" class:done={t.status === 'done'} class:bifare={bifatAcum === t.id} use:focusOnLand={focusKey('global', t.id)}
               use:glisare={{ activ: ecran.telefon, onBifa: t.status === 'done' ? null : () => toggleStatus(t, true), onAmana: () => { deschideFoaia(t.id); termenDeschis = true } }}
               use:apasareLunga={{ activ: ecran.telefon, actiune: () => deschideFoaiaActiuni(t) }}>
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
              <span class="ttitle">{t.titlu}</span>
              <!-- CONTORUL DE PASI — langa titlu, nu intr-o coloana proprie.
                   O coloana ar fi goala pe majoritatea randurilor, iar o coloana
                   cu goluri nu se mai citeste pe verticala — adica pierde exact
                   singurul motiv pentru care ar fi coloana (vezi termenul).
                   Aici e legat de titlu: e „cat din lucrul asta", nu „cand".
                   Componenta se randeaza singura ca nimic daca `total` e 0. -->
              <ContorPasi {...pasi(t)} />
            </button>
            <!-- ACTIUNILE APAR LA HOVER, CU TEXT, SPRE INTERIOR.
                 Erau patru iconite mute pironite in dreapta, adica exact acolo
                 unde trebuie sa stea TERMENUL — deci randul isi pierdea al
                 doilea lucru (cand) ca sa faca loc unor semne pe care oricum
                 trebuia sa le inveti. Acum termenul e pironit si vizibil mereu,
                 iar actiunile intra la stanga lui: titlul cedeaza latimea, dar
                 coloana din dreapta nu se misca. -->
            <div class="task-actions">
              <span class="ta-dp" title="Planifică — alege ziua">
                <DatePicker value={t.data_scadenta} eticheta="Planifică" onchange={(v) => setTermenData(t, v)} />
              </span>
              <button class="ta-chip" onclick={() => openEditModal(t)}>
                <SolidIcon name="pencil" size={13} />Editează
              </button>
              <button class="ta-chip ta-sterge" onclick={() => { taskDeleteId = t.id; showTaskDelete = true }}>
                <SolidIcon name="trash" size={13} />Șterge
              </button>
            </div>
            <!-- COLOANA DE TERMEN — 46px, fixa, aliniata la dreapta.
                 Are valoare pe FIECARE rand, inclusiv in grupele care au spus-o
                 deja in cap („azi" sub „Azi"). Cand termenul era metadata sub
                 titlu, repetarea era zgomot; acum e o coloana, iar o coloana cu
                 goluri nu se mai poate citi pe verticala — si tocmai citirea pe
                 verticala e singurul motiv pentru care e o coloana. -->
            <span class="ttermen" class:sev={isOverdue(t.data_scadenta)}
                  class:acum={isToday(t.data_scadenta)}>{termenScurt(t)}</span>            </div>
          </div>
          <!-- Aici se desfacea taskul in lista, pe desktop. A ramas fara declansator
               de cand taskul se deschide in PANOU lateral (`showSheet`): `expandedTask`
               nu se mai asigneaza nicaieri, deci blocul nu s-a mai randat niciodata,
               iar tranzitia lui (`desfacere`, sapte proprietati de layout pe cadru)
               era cod mort. Sters cu tot cu starea. -->
        </div>
      {/each}
      {/if}
      {/each}

    </div>
    {/key}
  {/if}
  </div>
  </div>

  <!-- BUTONUL MARE CU PLUS — singura cale de adaugare de pe telefon.
       Sta peste dock, la aceeasi distanta de margine ca el, in dreapta: acolo
       ajunge degetul mare fara sa muti telefonul in mana.
       Deschidea un formular de patru campuri („Task Nou": Titlu, Categorie,
       Termen, Recurență), cu motivul scris aici: „pe telefon scrii mai rar si
       atunci vrei sa pui si termenul din prima". Termenul se pune tot din prima,
       dar SCRIS — „mâine revizie pompa" — iar Categoria si Recurenta au intrat in
       foaie, unde nu mai ocupa doua randuri din patru pentru ceva folosit rar. -->
</div>

<!-- TASKUL DESCHIS: foaie pe telefon, PANOU LATERAL pe desktop (desen 3a,
     cerut de Ion la verificarea finala). Acelasi continut in ambele gazde —
     `Modal size="panou"` e deja „panou pe desktop, foaie pe telefon". -->
{#if sheetTask}
  <!-- Antetul modalului primeste CONTEXTUL taskului (categoria), ca „Inbox" la
       Todoist. Fara titlu, `Modal` randa oricum bara cu butonul de inchidere, deci
       ramanea o banda goala de ~60px deasupra taskului — spatiu platit degeaba,
       exact acolo unde ochiul cade prima data. -->
  <!-- Titlul foii e TITLUL TASKULUI. Era `categorie`, care e implicit „General"
       si nu se scrie niciodata in interfata — deci fiecare foaie deschisa pe
       telefon se numea „General". -->
  <!-- `iesireGest`: pe telefon foaia asta nu mai are `X` in colt. Iesirea e
       gestul in jos (din antet SAU din continut, cat timp lista e la capatul de
       sus) plus butonul „inapoi" de pe Android. Coltul din dreapta sus e, pe un
       telefon inalt, singurul loc de pe ecran la care nu ajungi fara sa muti mana
       din priza — iar foaia asta se deschide de zece ori mai des decat cea a
       zilei din Calendar, care primise deja tratamentul.
       Se poate cere aici fiindca foaia n-are NICIUN camp de text: cat timp
       tastatura e sus, gestul din continut se opreste dinadins (`tastaturaSus`),
       si atunci `X`-ul chiar ar fi singura iesire vizibila. -->
  <Modal bind:open={showSheet} size="panou" iesireGest title={sheetTask.titlu || 'Task'}>
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
      <!-- ACELASI selector de zi ca oriunde altundeva se replanifica ceva
           (`components/ui/SelectorZi.svelte`). Aici erau patru butoane scrise
           local; pe „Astăzi" erau patru iconite; in pagina de proiect doar un
           calendar. Aceeasi intrebare, trei raspunsuri de invatat. -->
      <div class="ts-zile" transition:slide|local={{ duration: motionDuration(DUR_FAST), easing: EASE }}>
        <SelectorZi value={sheetTask.data_scadenta}
                    onalege={(v) => { setTermenData(sheetTask, v || ''); termenDeschis = false }} />
      </div>
    {/if}

    {@render taskDetail(sheetTask)}
  </Modal>
{/if}

<!-- Foaia de actiuni (apasare lunga pe rand). „Deschide" e foaia taskului — aceeasi
     pe care o deschide si atingerea randului. -->
<FoaieTask bind:open={foaieDeschisa} task={foaieTask} mod="actiuni"
           onZi={(v) => setTermenData(foaieTask, v)}
           onMaine={() => setTermen(foaieTask, 1)}
           onOra={(v) => setOra(foaieTask, v)}
           onEditeaza={() => { taskEditat = foaieTask; showAdauga = true }}
           onSterge={() => stergeDinLista(foaieTask)} />

<!-- FOAIA DE ADAUGARE — aceeasi in /tasks, pe „Astăzi" si in tabul Taskuri al unui
     proiect. Aici a inlocuit modalul „Task Nou" (patru campuri peste tastatura),
     care nu putea spune daca taskul exista deja: scriai „revizie pompa", apasai
     Creează, si se năștea al doilea. -->
<FoaieAdauga bind:open={showAdauga} sfera={sferaActiva} onSchimbare={reload}
             editeaza={taskEditat}
             onSalveaza={async (d) => { await updateGlobalTask(taskEditat.id, d) }} />

<Modal bind:open={showEditModal} title="Editează Task" size="md">
  <!--
      ENTER SALVEAZA. Butonul din subsolul lui `Modal` sta in AFARA elementului
      `<form>`, deci formularul ramanea fara `type="submit"` si HTML bloca
      trimiterea implicita (mai multe campuri) — masurat: zero cereri catre API.
      `form="<id>"` leaga butonul de forma oriunde ar sta el in pagina.
      Si nu mai e stins cand titlul lipseste: un buton stins nu spune de ce e
      stins. Acum afli pe CAMPUL care trebuie reparat (`<Input error>`), nu
      intr-un toast care pleaca in patru secunde. -->
  <form class="task-form" id="task-edit-form" onsubmit={(e) => { e.preventDefault(); handleEdit() }}>
    <!-- ACELASI camp ca la creare, dinadins: doua ferestre vecine care cer
         acelasi lucru n-au voie sa-l ceara in doua feluri. Descrierea RAMANE
         doar aici — la creare nu se scrie niciodata (Ion), la editare e singura
         cale scurta catre nota unui task deja existent. -->
    <Input label="Titlu" bind:value={formTitle} placeholder="Titlu task" error={eroareTitlu} />
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
      <Button type="button" variant="secondary" onclick={() => showEditModal = false}>Anulează</Button>
      <Button type="submit" form="task-edit-form" loading={creating}>Salvează</Button>
    </div>
  {/snippet}
</Modal>

<ConfirmDialog bind:open={showTaskDelete}
               title={taskDeSters ? `Ștergi „${taskDeSters.titlu}”?` : 'Ștergi taskul?'}
               message={subDeSters?.length
                 ? `Dispar odată cu el ${subDeSters.length} ${subDeSters.length === 1 ? 'subtask' : 'subtaskuri'}. Nu se poate anula.`
                 : 'Nu se poate anula.'}
               confirmLabel="Șterge taskul" onconfirm={doDeleteTask} />

<!-- Titlul e TASKUL, nu „Notițe — <task>": ai deschis nota DIN el, deci prefixul
     spunea ce se vede oricum, si tocmai el facea randul sa se taie. Antetul e o
     linie de context (vezi `.modal-doc .modal-title` in Modal.svelte).
     `tools="nota"`: sapte unelte, nu treisprezece — vezi RichTextEditor. -->
{#if EditorLung}
  <EditorLung bind:open={showNoteModal} titlu={noteTask ? noteTask.titlu : 'Notiță'}
              valoare={noteDraft} tools="nota" salveaza={noteSalveaza}
              placeholder="Scrie notițe pentru acest task…" />
{/if}

<!-- O LEGATURA CU UN SERVICIU DIN AFARA SE CITESTE CA O STARE, NU CA UN FORMULAR.
     E pornita sau nu, iar cand e pornita trebuie sa stii ce se sincronizeaza si
     cand s-a intamplat ultima oara. Era o insiruire de paragrafe si butoane
     egale, in care „Deconectează" (rar, si ireversibil pe jumatate) statea la fel
     de tare ca „Resincronizează" (des si inofensiv).
     Ordinea: iconita + nume + sursa · pastila de stare · ce se sincronizeaza ·
     ultima sincronizare · (eroarea) · actiunea principala · (linie) · .ics si
     Deconectează. Zona de lipit JSON apare DOAR cand nu exista credentiale — nu e
     un camp permanent intr-un ecran deschis zilnic. -->
<!-- Modalul Google Calendar a plecat cu tot cu buton (Ion, 2026-08-10) —
     vezi comentariul din script. -->

<!-- Notificările zilnice, în trepte: indisponibil pe server → browser
     nesuportat → permisiune refuzată → neabonat → abonat. -->
<Modal bind:open={showPushModal} title="Notificări zilnice" size="sm">
  <!-- IN APLICATIA DE PE TELEFON, NIMIC DIN ASTA NU MAI TRECE PRIN SERVER.
       Alarma o pune Android, din timp, deci starea de abonament push de mai jos
       n-are niciun inteles aici — ar arata o masinarie care nu mai e folosita. -->
  {#if esteNativ()}
    <p class="g-text">O notificare <strong>per task</strong>, nu un rezumat, cu „Făcut” și „Azi” pe
      ea. Aici alarma o pune telefonul, din timp — nu vine de pe server, deci nu depinde nici
      de rețea, nici de starea aplicației în momentul în care sună.</p>
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
    <!-- `.modal-actions`, nu `.g-actiuni`: aceea era o clasa fara nicio regula
         CSS (bug preexistent — perechea ei se numea `.g-actiune`, singular, si
         era a cardului Google). Butoanele modalului au deja o asezare in
         sistem, si asta e ea. -->
    <div class="modal-actions">
      <Button loading={pushBusy} onclick={activeazaPush}>Activează pe telefonul ăsta</Button>
    </div>
  {:else}
    <p class="g-text">O notificare <strong>per task</strong>, nu un rezumat, cu „Făcut” și „Azi” pe
      ea. Setările stau pe server, deci sunt aceleași de pe orice dispozitiv.</p>
    <div class="g-stare">
      <div class="g-rand">
        <span class="g-et">Dispozitive abonate</span>
        <span class="g-val">{pushStatus.abonamente}</span>
      </div>
      {#if pushStatus.last_error}<p class="g-eroare">{pushStatus.last_error}</p>{/if}
    </div>
    <!-- „Dezactivează aici" e despre ACEST dispozitiv, nu despre regula de pe
         server — deci sta langa numarul de dispozitive, nu in bara de jos, unde
         ar fi al treilea verb langa „Salvează" si „Trimite test". -->
    <button class="g-link" disabled={pushBusy} onclick={dezactiveazaPush}>Nu mai trimite pe dispozitivul ăsta</button>
  {/if}

  <!-- CELE PATRU REGLAJE. Aceleasi de pe orice dispozitiv (stau pe server) si
       aceeasi forma pe telefon ca pe web: ora si vechimea sus, cele doua feluri
       de notificare ca doua propozitii de 48px sub ele. -->
  {#if arataSetari}
    {#if setari}
      <div class="n-setari">
        <Select label="Ora" bind:value={setari.ora} options={oreDisponibile} size="sm" />
        <Input label="Vechime (zile)" type="number" min="0" max="60"
               bind:value={setari.zileVechime} />
      </div>
      <div class="n-feluri">
        <label class="n-comutator">
          <input type="checkbox" bind:checked={setari.scadente} />
          <span>Taskurile scadente în ziua respectivă</span>
        </label>
        <label class="n-comutator">
          <input type="checkbox" bind:checked={setari.faraTermen} />
          <span>Taskurile rămase fără termen</span>
        </label>
        <!-- ORA EXACTĂ (v41). Ion: „trebuie să fie notificări pentru taskurile cu
             ore precise." E al treilea fel, și nu se suprapune cu primul: „scadente"
             anunță DIMINEAȚA tot ce cade azi, ăsta anunță LA ORA lui. Un task cu oră
             primește ambele, și e corect — unul spune „ai asta azi", altul „acum".
             N-are selector de oră lângă el, ca deplasările: ora nu e o setare aici,
             e a taskului. Și nu intră în regula „cel puțin un fel pornit" — nu e un
             semnal de dimineață, e o alarmă. -->
        <label class="n-comutator">
          <input type="checkbox" bind:checked={setari.oreExacte} />
          <span>La ora exactă a taskului</span>
        </label>
        <!-- AL TREILEA COMUTATOR E ALTĂ ÎNTREBARE: nu „ce am de făcut azi", ci
             „mâine plec". De aceea are ora lui (seara dinainte), canalul lui pe
             Android („Deplasări", se poate opri separat din sistem) și NU intră în
             regula „cel puțin un fel pornit" — aia păzește taskurile. -->
        <!-- Randul asta NU e un `<label>` intreg: eticheta ar prinde si clicul pe
             selectorul de ora, deci alegerea orei ar stinge comutatorul. Label-ul
             tine doar bifa si textul. -->
        <div class="n-comutator">
          <label class="n-com-et">
            <input type="checkbox" bind:checked={setari.deplasari} />
            <span>Seara dinaintea unei plecări pe site</span>
          </label>
          <Select bind:value={setari.oraDeplasare} options={oreDisponibile} size="sm" />
        </div>
      </div>
      <!-- Regula e SCRISA, nu descoperita dintr-o eroare: serverul respinge
           oprirea amandurora, iar un refuz care apare abia dupa ce ai apasat
           „Salvează" se citeste ca o defectiune, nu ca o limita. -->
      <p class="n-nota">
        <Info size={15} strokeWidth={1.5} />
        <span>Cel puțin un fel trebuie să rămână pornit — altfel n-ar mai suna nimic, iar
          tăcerea nu se poate deosebi de o defecțiune.</span>
      </p>
      <!-- ALARMA EXACTĂ E O PERMISIUNE SEPARATĂ (Android 12+), și fără ea
           sistemul adună alarmele într-o trezire: o notificare de dimineață care
           vine la 8:40 nu mai e o notificare de dimineață. Se verifică și la
           fiecare pornire (`MainActivity.onResume`), dar acolo ecranul de sistem
           se deschide o singură dată per retragere — drumul care rămâne mereu la
           îndemână e ăsta. Nu-i dăm calea prin meniuri: diferă de la un
           producător la altul, iar o instrucțiune care nu se potrivește cu ce
           vezi pe ecran te face să crezi că ai greșit tu. -->
      {#if exacta === false}
        <div class="n-alarma">
          <AlarmClockOff size={16} strokeWidth={1.5} />
          <div>
            <strong>Alarma exactă e oprită</strong>
            <p>Dimineața ar putea întârzia cu zeci de minute. Deschide comutatorul din
              sistem — nu-ți spunem calea, fiindcă diferă de la un telefon la altul.</p>
            <button class="n-alarma-b" onclick={pornesteAlarma}>
              <ExternalLink size={14} strokeWidth={1.5} />Deschide ecranul
            </button>
          </div>
        </div>
      {/if}
      {#if setariEroare}<p class="g-eroare">{setariEroare}</p>{/if}
    {:else}
      <div class="g-skel"><Skeleton width="70%" height="14px" /><Skeleton width="50%" height="14px" /></div>
    {/if}
  {/if}
  {#snippet footer()}
    <!-- PROBA E LA STANGA, DEPARTE DE „SALVEAZĂ". Una verifica lantul ACUM,
         cealalta schimba ce se intampla maine — doua verbe care nu trebuie sa
         stea lipite, fiindca a le confunda inseamna sa crezi ca ai salvat cand
         de fapt ai trimis o notificare. -->
    <div class="n-foot">
      {#if esteNativ()}
        <Button variant="secondary" disabled={pushBusy} onclick={probaLocala}>
          <BellRing size={15} strokeWidth={1.5} />Notificare de probă
        </Button>
      {:else if pushStatus?.disponibil && pushLocal?.abonat}
        <Button variant="secondary" disabled={pushBusy} onclick={testPush}>
          <BellRing size={15} strokeWidth={1.5} />Notificare de probă
        </Button>
      {:else}
        <span></span>
      {/if}
      <div class="modal-actions">
        {#if arataSetari}
          <Button disabled={pushBusy || !setari} onclick={salveazaSetari}>Salvează</Button>
        {/if}
      </div>
    </div>
  {/snippet}
</Modal>

<style>
  .page { padding: var(--space-lg); }
  /* Vezi Projects.svelte: fara `flex-wrap`/`gap` antetul nu se poate rupe si
     butonul iese din ecran, unde `overflow-x: clip` il taie fara sa spuna nimic. */
  .page-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); flex-wrap: wrap; margin-bottom: var(--space-md); }
  /* Subtitlul de pagina: doua numere care decid ceva, pe linia de baza a
     titlului. Nu e un contor de umplutura — „cate deschise" spune daca ai timp,
     „cate restante" spune daca te apuci de altceva. */
  .ph-sub { font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-dim); }
  .ph-restante { display: inline-flex; align-items: center; gap: var(--space-6);
    font-size: var(--font-small); font-weight: var(--fw-semibold);
    color: var(--danger); white-space: nowrap; }
  .ph-punct { width: 7px; height: 7px; border-radius: 50%; background: var(--danger); }

  /* Butonul mare cu plus (doar telefon). Peste dock, nu langa el — valorile din
     desen (T4): 58×58, raza 18, plusul 25/1.5, cu 24px deasupra dockului randat
     (72 = 68 + 4). Acelasi obiect ca in `Projects.svelte`. */
  /* Presiunea se simte IMEDIAT: scalare mai adanca, pe durata de apasare (nu pe
     tranzitia de vopsea), plus un puls haptic la atingere (Ion: „butonul de
     creare parca reactioneaza prea greu, trebuie o presiune mai mare"). */
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); min-width: 0; }
  .page-title-row h1 { font-size: var(--font-title); font-weight: var(--fw-semibold); }
  /* `.count` a plecat in global.css. E NEUTRA acum, nu amber: numarul de langa
     titlul paginii spune cate SUNT, iar accentul e rezervat pentru „cate sunt de
     facut aici" (backlog, tabul de taskuri al proiectului). */

  /* FARA `flex-wrap` (constatarea E2 din auditul de UI).
     Pe 390px cele trei controale nu incapeau pe un rand, deci clopotelul trecea
     pe al doilea — singur, aliniat la stanga, cu 314px de gol langa el, iar bara
     crestea de la 46 la 98px. Se citea ca o scapare de randare, nu ca o decizie.
     Acum comutatorul cedeaza latimea (`min-width: 0`), iar cele trei raman pe
     un rand pe orice telefon. */
  .toolbar { display: flex; gap: var(--space-md); align-items: center; margin-bottom: var(--space-md); flex-wrap: nowrap; }
  .toolbar .sfere { min-width: 0; }
  /* Compozitorul are DOUA randuri acum (camp + chipuri de zi), deci coloana.
     Cat timp era `flex-direction: row`, chipurile se asezau LANGA camp, ieseau
     din ecran, iar campul se intindea pe inaltimea lor. */
  .quick-add { display: flex; flex-direction: column; margin-bottom: var(--space-md); }
  /* RAZA DE CAMP, NU DE SUPRAFATA. Purta `--radius-md` (24) — treapta panoului,
     pusa pe un camp de text — si scria la 13px cand orice alt camp scrie la 15.
     Reperul e `components/TodayBoard.svelte`, care le avea deja pe amandoua bine. */
  /* Invelisul e cel care poarta haina; campul dinauntru e text gol pe el. Focusul
     se muta odata cu ele — `:focus-within`, fiindca ce primeste focusul e copilul.
     Aceeasi reteta ca `.qa-camp` din `components/TodayBoard.svelte`. */
  .qa-camp { display: flex; align-items: center; gap: var(--space-10);
    min-height: var(--tap-min); padding: 0 var(--space-14); background: var(--bg-elevated);
    border: 1px solid var(--border); border-radius: var(--radius-sm);
    transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
  .qa-camp:focus-within { border-color: var(--accent); box-shadow: var(--focus-ring); }
  .qa-ico { display: inline-flex; align-items: center; color: var(--text-dim); flex: none; }
  .quick-add input { flex: 1; min-width: 0; background: none; border: 0; padding: 0;
    align-self: stretch; color: var(--text); font-size: var(--font-body); }
  /* INELUL DE FOCUS STA PE INVELIS, NU SI PE CAMP. `global.css:296` il pune pe
     ORICE `input:focus` — iar aici campul e invelit, deci primea si el unul, cu
     `border-radius: 0`. Ieseau doua chenare: cel rotunjit al invelisului si un
     dreptunghi cu colturi drepte inauntru, ale carui capete se vedeau ca doua bare
     verticale (Ion, 2026-08-24: „doar un chenar in jurul campului si atat, fara
     barele verticale pe margini"). */
  .quick-add input:focus { outline: none; box-shadow: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .filters { display: flex; gap: var(--space-xs); flex-wrap: wrap; align-items: center; }
  /* ARHIVA — ACTIUNE-FANTOMA, NU CHIP. Aici erau doua chipuri („Active"/„Arhivă"),
     din care unul era mereu pornit. Ramane un singur buton, cu haina iconitei
     Google de langa el: si aceea e o setare, nu un filtru. Activ = tinta amber,
     ca sa se vada din bara in ce lista te uiti. */
  .a-ico { display: inline-flex; align-items: center; gap: var(--space-6); min-height: var(--ctrl-sm);
    padding: 0 var(--space-10); border: none; background: none; border-radius: var(--radius-sm);
    color: var(--text-dim); font-size: var(--font-small); font-weight: var(--fw-medium);
    cursor: pointer; transition: var(--transition-colors); }
  .a-ico:hover { color: var(--text); background: var(--bg-hover); }
  .a-ico.on { color: var(--accent-on-subtle); background: var(--accent-subtle); }
  .a-ico:active { transform: scale(var(--press-scale)); }
  /* Comutatorul de sfera — capsula de 36 cu segmentul activ pe FILL DE ACCENT.
     Trei lucruri erau pe langa sistem:
     - `--radius-full` pe capsula SI pe segmente, adica pastile rotunde, cand
       scara spune „cerc doar bifa". Acum 10 afara si 7 inauntru — nu o a sasea
       raza, ci regula razei imbricate: raza interioara = cea exterioara minus
       paddingul, altfel curbele nu sunt concentrice si segmentul activ pare
       lipit strambin capsula.
     - activul era `--bg-elevated` + umbra, adica o treapta de SUPRAFATA. Dar
       sfera nu e o suprafata ridicata, e o ALEGERE — si alegerea se scrie cu
       accent. (Vechiul comentariu spunea „nu amber, amber e limbajul filtrelor";
       amberul nu mai exista in sistem, deci nici motivul.)
     - 24px inaltime: sub pragul de atingere pe ferestre inguste.
     Sferele se deosebesc in continuare prin SEMN (briefcase / user), nu prin
     culoare — punctul violet de pe „Personal" a plecat demult, si nu se intoarce
     acum pe alta usa. */
  /* Jumatati EGALE (grid), ca cursorul sa alunece exact 100% din propria latime
     de pe un segment pe celalalt. */
  .sfere { display: grid; grid-template-columns: 1fr 1fr; position: relative;
    background: var(--bg-elevated); border: none;
           border-radius: var(--radius-sm); padding: 3px; flex-shrink: 0; margin-right: var(--space-xs); }
  .seg { display: inline-flex; align-items: center; justify-content: center; gap: var(--space-6); padding: 0 var(--space-14); min-height: var(--ctrl-sm); border: none; background: none; cursor: pointer;
         position: relative; z-index: 1;
         border-radius: calc(var(--radius-sm) - 3px); font-size: var(--font-small); font-weight: var(--fw-medium);
         color: var(--text-secondary); transition: color var(--dur-base) var(--ease); }
  .seg:hover { color: var(--text); }
  /* Fillul e al CURSORULUI de dedesubt, nu al segmentului: doar asa alegerea
     ALUNECA de pe un tab pe celalalt in loc sa se teleporteze. */
  .seg.on { color: var(--accent-text); font-weight: var(--fw-semibold); }
  .seg-cursor { position: absolute; top: 3px; bottom: 3px; left: 3px;
    width: calc(50% - 3px); border-radius: calc(var(--radius-sm) - 3px);
    background: var(--accent);
    transform: translateX(calc(var(--i, 0) * 100%));
    /* ELAN, ca pastila din dock (15 august): acelasi fel de obiect — o tenta
       care traverseaza o distanta pe care o vezi. `--ease-spring` depasea cu
       35%, potrivit cand mana ta da elanul; aici elanul il da comutatorul. */
    transition: transform var(--dur-arc-elan) var(--ease-arc-elan); }
  /* SFERA SE DEOSEBESTE PRIN SEMN, NU PRIN CULOARE.
     Aici era un punct violet lipit inaintea lui „Personal": o bulina decorativa
     care aducea a treia culoare pe o bara unde amberul insemna deja „activ", iar
     violetul nu insemna nimic in afara acestui punct. Iconita spune acelasi lucru
     CAT TIMP nu e activ segmentul (bulina se citea greu pe segmentul stins) si e
     acelasi semn cu cel din antetul „Personal" de pe Acasa — cele doua suprafete
     se refera in continuare una la alta, doar c-o fac cu un desen, nu cu o culoare. */
  /* Clopotelul de notificari — fantoma, nu chip: chipurile din toolbar sunt
     filtre, iar asta e o intrare de setari. Punctul rosu apare doar cand o
     trimitere a esuat — singurul moment in care merita atentie.
     Prefixul `g-` e mostenit de la modalul Google (sters 2026-08-10); clasele
     au ramas ale ferestrei de notificari, care le folosea deja pe toate. */
  .g-ico { position: relative; display: flex; align-items: center; justify-content: center;
           width: var(--ctrl-sm); min-height: var(--ctrl-sm); background: none; border: none; cursor: pointer;
           color: var(--text-dim); border-radius: var(--radius-sm);
           transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease); }
  .g-ico:hover { color: var(--text); background: var(--bg-hover); }
  /* Acelasi punct ca pe clopotel, pe segmentul de sfera. */
  .seg-punct { width: 6px; height: 6px; border-radius: 50%; background: var(--danger);
    flex: none; margin-left: var(--space-2xs); }
  .g-punct { position: absolute; top: 4px; right: 4px; width: 6px; height: 6px;
             border-radius: 50%; background: var(--danger); }

  /* Fereastra de notificari — text de stare, nu formular. */
  .g-skel { display: flex; flex-direction: column; gap: var(--space-sm); }
  .g-text { font-size: var(--font-small); color: var(--text-secondary); line-height: var(--lh-normal); text-wrap: pretty; }
  .g-mono { font-family: var(--font-mono); font-size: var(--font-small); color: var(--text); }

  /* Blocul de aici (`.g-card`, `.g-cap`, `.g-emblema`, `.g-nume`, `.g-t`,
     `.g-sub`, `.g-pastila`, `.g-linie`, `.g-main`, `.g-rar`, `.g-rar-rand`,
     `.g-sp`, `.g-actiune`, `.g-per`) descria cardul „Legatura cu Google" si a
     plecat odata cu integrarea (2026-08-10). Ce ramane mai jos e al ferestrei
     de notificari, care folosea deja aceleasi clase de stare. */
  .g-stare { display: flex; flex-direction: column; }
  .g-rand { display: flex; align-items: center; justify-content: space-between; gap: var(--space-md);
    min-height: var(--ctrl-md); font-size: var(--font-body); color: var(--text-secondary); }
  .g-et { color: var(--text-secondary); }
  .g-val { color: var(--text); text-align: right; }

  .g-eroare { display: flex; gap: 9px; padding: 11px 13px; border-radius: var(--radius-sm);
    background: var(--danger-subtle); color: var(--danger-deep);
    font-family: var(--font-mono); font-size: var(--font-small); line-height: var(--lh-snug);
    overflow-wrap: anywhere; }
  .g-eroare :global(svg) { flex: none; margin-top: var(--space-2xs); }

  .g-link { font-size: var(--font-small); color: var(--text-dim); background: none; border: none;
            cursor: pointer; text-decoration: underline; padding: 0; align-self: center; }
  .g-link:hover { color: var(--text); }
  .g-link:disabled { color: var(--text-dim); cursor: default; text-decoration: none; }

  /* SETARILE DE NOTIFICARI. Fara haina proprie: campurile sunt `Input`/`Select`
     din aceeasi trusa ca peste tot, iar aici raman doar asezarea si comutatoarele.
     Doua coloane pe latime, o coloana pe telefon — ora si pragul sunt scurte si
     ar arata pierdute pe un rand intreg. */
  .n-setari { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
              gap: var(--space-sm) var(--space-md); margin-top: var(--space-md); }
  /* Cele doua feluri de notificare sunt o LISTA, nu doua campuri: rand de 48px,
     separator de 1px cu marja laterala — aceeasi reteta ca listele din aplicatie.
     Asa se citesc ca doua intrari intre care alegi, nu ca doua bife razlete. */
  .n-feluri { display: flex; flex-direction: column; margin-top: var(--space-12); }
  .n-feluri .n-comutator + .n-comutator { border-top: 1px solid var(--border); }
  /* Comutatoarele sunt propozitii, nu campuri: tin toata latimea si se citesc
     ca o fraza, ca sa se vada CE se opreste, nu doar ca exista un buton. */
  .n-comutator { display: flex; align-items: center; gap: var(--space-12);
                 font-size: var(--font-body); color: var(--text);
                 min-height: 48px; padding: 0 var(--space-2xs); cursor: pointer; }
  .n-comutator input { width: 18px; height: 18px; flex: none; accent-color: var(--accent);
                       cursor: pointer; }
  /* Ora plecarii sta CHIAR PE RANDUL ei, nu intr-un al treilea camp sus: e ora
     acelui comutator, nu inca un reglaj global. */
  .n-com-et { flex: 1; min-width: 0; display: flex; align-items: center; gap: var(--space-12);
              cursor: pointer; }
  .n-comutator :global(.field) { flex: none; width: 96px; }
  /* Alarma exacta oprita — o stare a SISTEMULUI, deci suprafata in tenta de
     restant, cu iconita si cu drumul catre ecranul care o repara. */
  .n-alarma { display: flex; gap: var(--space-12); margin-top: var(--space-12);
              padding: var(--space-12); border-radius: var(--radius-md);
              background: var(--danger-subtle); }
  .n-alarma :global(svg) { flex: none; margin-top: var(--space-2xs); color: var(--danger-deep); }
  .n-alarma strong { display: block; font-size: var(--font-body); font-weight: var(--fw-semibold);
                     color: var(--text); }
  .n-alarma p { margin-top: var(--space-xs); font-size: var(--font-small); color: var(--text-secondary); }
  .n-alarma-b { display: inline-flex; align-items: center; gap: var(--space-6); margin-top: var(--space-sm);
                min-height: var(--tap-min); padding: 0 var(--space-12);
                border: 1px solid var(--border); border-radius: var(--radius-md);
                background: var(--bg-surface); color: var(--text);
                font-size: var(--font-control); font-weight: var(--fw-semibold); cursor: pointer;
                transition: var(--transition-colors); }
  .n-alarma-b:hover { border-color: var(--text-dim); }

  /* Regula scrisa, in gri, cu iconita — nu un avertisment: nu s-a intamplat
     nimic rau, doar spune de ce nu se pot stinge amandoua. */
  .n-nota { display: flex; align-items: flex-start; gap: var(--space-sm);
            margin-top: var(--space-12); font-size: var(--font-small);
            color: var(--text-secondary); }
  .n-nota :global(svg) { flex: none; margin-top: 1px; color: var(--text-dim); }
  /* Proba la stanga, „Salvează" la dreapta — cat mai departe una de alta pe
     acelasi rand. Pe telefon `.modal-actions` isi intinde butonul pe toata
     latimea (regula din Modal), deci cele doua trec pe randuri diferite. */
  .n-foot { display: flex; align-items: center; justify-content: space-between;
            gap: var(--space-sm); flex-wrap: wrap; }
  .n-foot > :global(.modal-actions) { flex: 1; }
  /* PE TELEFON ACTIUNEA PRINCIPALA E PRIMA SI LATA (T15).
     `space-between` + `flex-wrap` + `.modal-actions > * { flex: 1 }` trimiteau
     „Salvează" pe randul al doilea, SUB „Notificare de probă" — adica actiunea
     care schimba ce se intampla maine ajungea desenata ca secundara, sub cea
     care doar verifica lantul acum. `column-reverse` schimba doar ce vezi:
     markupul ramane proba -> salveaza, deci si ordinea de Tab. */
  @media (max-width: 768px) {
    .n-foot { flex-direction: column-reverse; align-items: stretch; flex-wrap: nowrap; }
    .n-foot > :global(.btn-secondary) { background: none; border: none; min-height: var(--tap-min); }
  }
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
  /* Capul de grupa: PUNCT + eticheta micro + numar.
     Eticheta e neutra (`--text-secondary`) chiar si la „Restante" — ce e urgent
     spune PUNCTUL si numarul, iar un rand intreg de text rosu peste o lista de
     randuri rosii nu mai selecteaza nimic. Numarul e singurul care poarta rolul.
     `--font-sans`, nu mono: e un cuvant, nu o cifra care se compara. */
  /* UN SINGUR REPER, PE TOATE LATIMILE (T10).
     `top: 0` insemna marginea FERESTREI, dar bara de sus e `sticky` cu
     `--z-sticky` (200) — deci „RESTANTE" aluneca sub ea si disparea exact cand
     derulai, adica exact cand aveai nevoie de el ca sa stii in ce grupa esti.
     Regula de telefon o avea deja corect; acum o are si desktopul. */
  .grup-cap { position: sticky; top: var(--header-height); z-index: 2;
    display: flex; align-items: center; gap: var(--space-sm);
    padding: var(--space-20) var(--space-12) var(--space-sm); margin-top: 0;
    background: linear-gradient(var(--bg-surface) 72%, transparent);
    font-size: var(--font-label);
    font-weight: var(--fw-semibold); text-transform: uppercase;
    letter-spacing: var(--tracking-label); color: var(--text-secondary); }
  .grup-cap::before { content: ''; width: 7px; height: 7px; border-radius: 50%;
    background: var(--border-strong); flex: none; }
  .grup-cap:first-child { padding-top: var(--space-xs); }
  /* Numarul se randeaza doar la „Restante" (vezi markup), deci si culoarea lui e
     una singura. Regula pentru `ton-accent` a plecat cu el: fara rand care s-o
     poarte, era vopsea pentru un element care nu mai exista. */
  .grup-n { font-family: var(--font-mono); font-size: var(--font-label);
    color: var(--danger); font-variant-numeric: tabular-nums;
    text-transform: none; letter-spacing: var(--tracking-normal); }
  .grup-cap.ton-danger::before { background: var(--danger); }
  .grup-cap.ton-accent::before { background: var(--accent); }
  /* „Fără termen" e INEL, nu punct plin: absenta termenului se spune prin absenta
     fillului. Altfel ea si „Mâine"/„Zilele astea" au exact acelasi semn — patru
     grupe, trei semne. `box-shadow: inset`, nu `border`: pastreaza punctul la 7px
     ca celelalte trei, deci eticheta de langa nu se decaleaza cu 3px. */
  .grup-cap.ton-sters::before { background: none;
    box-shadow: inset 0 0 0 1.5px var(--border-strong); }

  /* ===== compozitorul ===== */
  .qa-cand { display: flex; align-items: center; gap: var(--space-6); flex-wrap: wrap; padding: var(--space-sm) var(--space-2xs) 0; }
  .qa-chip { padding: 5px var(--space-14); border-radius: var(--radius-full);
    background: var(--bg-elevated); border: 1px solid var(--border);
    color: var(--text-secondary); font-size: var(--font-small);
    font-weight: var(--fw-medium); cursor: pointer;
    transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .qa-chip:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-subtle); }
  .qa-dp :global(.dp-trigger) { min-height: var(--ctrl-sm); padding: var(--space-xs) var(--space-12);
    border-radius: var(--radius-full); font-size: var(--font-small); }
  .qa-hint { font-size: var(--font-small); color: var(--text-dim); margin-left: auto; }

  /* ===== randul desfasurat ===== */
  /* Cele doua actiuni rare, SUB continut si la 11px: chipurile de dinainte stateau
     deasupra subtaskurilor si erau primul lucru pe care il vedeai la deschiderea
     unui task. O linie punctata le separa de lista fara sa deseneze o a doua cutie. */
  .td-jos { display: flex; align-items: center; gap: var(--space-md);
    margin-top: var(--space-sm); padding-top: var(--space-sm);
    border-top: 1px dashed var(--border-subtle); }
  /* IN FOAIE, ACTIUNILE NU SE DERULEAZA (T1c).
     `taskDetail` e acelasi snippet si in randul desfasurat de pe desktop, si in
     foaia de pe telefon — dar numai in foaie corpul deruleaza, deci numai acolo
     „Adaugă notă" si „Schimbă termenul" plecau de sub deget cand aveai zece
     subtaskuri. `:global(.modal-body)` tinteste exact gazda care deruleaza;
     randul desfasurat nu are asa ceva, deci ramane cum era.
     DESCENDENT, NU `>`: cu `>`, compilatorul nu poate verifica parintele
     (`.td-jos` ajunge in `.modal-body` prin `{@render}`, nu prin markup) si
     TAIA regula din build. Verificat in CSS-ul livrat: regula lipsea, deci
     bara nu era lipita pe telefon de la scrierea ei. Ancora `.td-jos` ramane
     scoped, deci regula nu scapa in ProjectDetail, care are si el un
     `.td-jos`; `:global(...)` pe TOT selectorul ar fi scapat, fiindca
     pierde clasa de scope.
     Fondul e obligatoriu: fara el subtaskurile s-ar citi prin bara lipita. */
  :global(.modal-body) .td-jos {
    position: sticky;
    bottom: calc(-1 * var(--space-md));
    z-index: 1;
    margin-top: var(--space-12);
    padding-bottom: var(--space-md);
    background: var(--bg-overlay);
  }
  .td-link { display: inline-flex; align-items: center; gap: var(--space-6); padding: 0;
    background: none; border: none; color: var(--text-dim);
    font-size: var(--font-small); cursor: pointer; transition: var(--transition-colors); }
  .td-link:hover { color: var(--accent); }
  .td-link.areNota { color: var(--text-dim); }
  /* DatePicker-ul isi aduce caseta de camp; aici trebuie sa arate ca vecinul lui —
     un link, nu un input. */
  .td-dp :global(.dp) { width: auto; }
  .td-dp :global(.dp-trigger) { min-height: 0; padding: 0; gap: var(--space-6);
    background: none; border: none; box-shadow: none; border-radius: 0;
    color: var(--text-dim); font-size: var(--font-small); }
  .td-dp :global(.dp-trigger:hover) { color: var(--accent); background: none; }
  .td-nota { margin-bottom: var(--space-sm); font-size: var(--font-small); color: var(--text-secondary); }

  /* `relative`: randul care pleaca se scoate din flux fata de lista (vezi
     `plecare` in motion.svelte.js), ca golul sa se inchida fara animatie de layout. */
  .task-list { display: flex; flex-direction: column; position: relative; }
  /* MUCHIA DE SEVERITATE A PLECAT — severitatea e pe inelul bifei (`--ring`) si
     pe textul termenului. Cei 2px pierduti de la bordura se intorc in padding,
     ca lista sa nu se decaleze fata de capetele de grupa. */
  /* RANDUL NU MAI E UN CARD. Fiecare avea rama proprie, fundal si 6px de
     distanta, deci lista era douasprezece cutii — iar cutia e cel mai puternic
     semnal de „lucruri separate" pe care il are un ecran. O lista de facut e
     insa un singur lucru, citit pe verticala; ce desparte doua randuri e o
     LINIE, si aia cu marja laterala, ca sa nu taie suprafata de la un capat la
     altul. Cardul ramane unul singur: lista intreaga (`.list-cell`). */
  .trow-wrap { display: flex; flex-direction: column; background: none;
    border: 0; border-radius: var(--radius-sm); overflow: hidden; }
  /* SEPARATORUL ARE MARJA LATERALA — si o are EL, nu o mosteneste.
     Era `border-top` pe wrapper, adica o linie dreapta pe toata latimea lui;
     singura marja reala erau cei 8px ai cardului (`.list-cell`), nu 20 —
     paddingul de 12 e al CONTINUTULUI randului, borderul wrapperului nu-l
     vede. Iar pe telefon linia dreapta se intalnea cu coltul rotunjit al fetei
     de glisare, si nepotrivirea se vedea la fiecare gest. Ca pseudo-element cu
     `margin` propriu, linia sta unde spune regula sistemului si nu mai depinde
     de ce padding are altcineva. */
  .trow-wrap + .trow-wrap::before { content: ''; display: block; flex: none;
    height: 1px; margin: 0 var(--space-12); background: var(--border); }
  /* Separatorul se retrage cand un rand e deschis: acolo panoul de sub el ii tine
     deja locul, iar o linie peste el ar imparti un obiect care s-a facut mai mare. */
  .trow-wrap.deschis::before, .trow-wrap.deschis + .trow-wrap::before { background: transparent; }
  .trow-wrap.deschis { background: var(--bg-elevated); }
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
  /* RANDUL: doua lucruri, o inaltime, o coloana pironita.
     46px minim, gap 12, raza de control. Nu se mai deplaseaza la hover
     (`translateX(4px)`): translatia muta si coloana de termen, iar termenul e
     tocmai lucrul care trebuie sa stea pe loc cat timp cauti actiunile. */
  /* Fondul de hover pe 220 (contract miscare: „randul sub cursor — 220ms"),
     acelasi ceas cu actiunile care intra. */
  .trow { position: relative; display: flex; align-items: center; gap: var(--space-12);
    min-height: var(--row-h); padding: 0 var(--space-12); background: none; border: 0;
    transition: background-color var(--dur-base) var(--ease), opacity var(--dur-base) var(--ease); }
  @media (hover: hover) {
    .trow:hover { background: var(--bg-elevated); }
  }
  /* Apasarea, in afara media query-ului — vezi nota din TodayBoard: pe telefon
     randul nu dadea niciun semn ca a fost atins. */
  .trow:active { background: var(--bg-active); transition-duration: var(--dur-press); }
  /* Un rand bifat nu se stinge cu `opacity`: opacitatea se inmulteste peste
     tokenuri deja la limita de contrast, deci textul ajunge sub prag. Ce e facut
     o spun tăietura si culoarea rolului. */
  .trow.done .ttitle { text-decoration: line-through; color: var(--text-dim); }
  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: var(--space-2xs); display: inline-flex;
           position: relative; }
  /* TINTA E DE 44, DESENUL RAMANE DE 30. Masurat: bifa iesea 30x44 — inalta cat
     trebuie, dar prea ingusta, si e cel mai apasat lucru din aplicatie. Se
     largeste SUPRAFATA, nu cutia: o latire reala ar fi impins titlul cu 14px si
     ar fi schimbat ritmul randului, pentru un defect care nu e vizual.
     (`--tap-min` = 44 exista deja ca prag; aici era aplicat doar pe inaltime.) */
  .check::after {
    content: '';
    position: absolute;
    top: 0; bottom: 0;
    left: calc((var(--tap-min) - 30px) / -2);
    right: calc((var(--tap-min) - 30px) / -2);
  }
  .check:hover { color: var(--accent); }
  .trow.done .check { color: var(--success); }
  /* `.check-empty` (toate cele trei marimi) traieste in global.css, o singura
     data pentru toate listele — inclusiv haloul de hover, care ADAUGA in loc sa
     rescrie `--ring`. */
  /* `gap` pentru contorul de pasi, care sta lipit de titlu. Titlul e singurul
     copil care cedeaza latimea (`.tpasi` e `flex: none` in global.css). */
  .tmain { flex: 1; min-width: 0; cursor: pointer; text-align: left; align-self: stretch; display: flex; align-items: center; gap: var(--space-sm); }
  /* --font-rand, nu --font-body: randul de lista ramane 15 si pe telefon. */
  .ttitle { font-size: var(--font-rand); color: var(--text); font-weight: var(--fw-medium);
    min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* ACTIUNILE: chipuri cu TEXT, nu iconite mute.
     Se sting cand cursorul nu e pe rand — `opacity`, nu `display`, ca sa nu-si
     mute locul cand apar si ca titlul sa cedeze latimea o singura data. */
  .task-actions { display: flex; align-items: center; gap: var(--space-6); flex-shrink: 0; }
  /* Actiunile INTRA 8px spre interior (dinspre dreapta, spre titlu), pe 220 —
     contractul de miscare. Termenul, pironit la dreapta lor, nu se misca. */
  @media (hover: hover) {
    .task-actions { opacity: 0; pointer-events: none; transform: translateX(8px);
      transition: opacity var(--dur-base) var(--ease), transform var(--dur-base) var(--ease); }
    .trow:hover .task-actions,
    .task-actions:focus-within { opacity: 1; pointer-events: auto; transform: none; }
  }
  .ta-chip, .ta-dp :global(.dp-trigger) {
    display: inline-flex; align-items: center; gap: var(--space-6); height: var(--ctrl-sm); padding: 0 11px;
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

  /* COLOANA DE TERMEN — pironita, 46px, mono ca sa se alinieze pe verticala.
     Severitatea se citeste din ea SI din inelul bifei, amandoua din `--ring`.
     13, nu 12: pe rand termenul e METADATA, iar 12 e treapta etichetelor
     majuscule — o alta clasa de text, cu alt rol si alt tracking. */
  .ttermen { flex: none; width: 46px; text-align: right;
    font-family: var(--font-mono); font-size: var(--font-small);
    color: var(--text-dim); font-variant-numeric: tabular-nums;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .ttermen.sev { color: var(--danger); }
  /* „azi" gri, ca in desen — inelul bifei poarta accentul; textul doar rosul. */
  .ttermen.acum { font-weight: var(--fw-medium); }

  /* Pe desktop invelisul de glisare nu exista pentru layout. */
  .gl-fata { display: contents; }


  /* Corp expandat: panou inset (nu mai pluteste pe negru), continut grupat cu gap */
  /* Extinderea e CONTINUAREA randului, nu un card separat: se lipeste de el
     (randul isi pierde colturile de jos si marginea), preia bordura de severitate
     din stanga si sta pe acelasi fundal. Inainte pareau doua obiecte fara legatura. */
  /* Extinderea: continut in acelasi card, separat doar de o linie subtire. */
  .subtask-body { margin: 0; padding: var(--space-6) var(--space-12) var(--space-12) 34px;
    border-top: 1px solid var(--border-subtle);
    display: flex; flex-direction: column; gap: var(--space-xs); }

  /* Actiuni discrete: chip-uri "+ Descriere / + Fisier" in loc de link-uri italic plutinde */
  /* Fara rand propriu pentru un singur buton: se aliniaza la stanga, discret. */


  /* ===== Foaia taskului ===== */
  .sub-cap { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-6); }
  .sub-cap-t { font-size: var(--font-label); text-transform: uppercase;
    letter-spacing: var(--tracking-label); font-weight: var(--fw-semibold); color: var(--text-dim); flex: none; }
  .sub-gol { font-size: var(--font-small); color: var(--text-dim); padding: var(--space-sm) 0; }
  /* Fiecare subtask e un card, ca la Todoist: pe fundalul foii randurile fara
     suprafata proprie se citeau ca un bloc de text, nu ca lucruri separate.
     O SINGURA declaratie: mai jos exista pana acum o a doua `.sub-row` (ramasa
     de la designul de lista), care la specificitate egala castiga fiind ultima
     si rescria TACUT padding-ul cardului la `3px 0` — adica un card desenat cu
     rama la 0px de text. Masurat inainte: padding calculat `3px 0` pe desktop,
     `2px 0` in foaie. Exact felul de abatere care nu arunca nicio eroare. */
  .sub-row { display: flex; align-items: center; gap: 9px; min-height: var(--ctrl-sm);
    padding: 0 var(--space-6); border-radius: var(--radius-xs); }
  .sub-row:hover { background: var(--bg-hover); }
  /* Scheletul are FORMA randului real — aceeasi inaltime, aceeasi coloana a
     bifei — ca sosirea subtaskurilor sa nu miste nimic (vezi `Skeleton`). */
  .sub-schelet { gap: 9px; padding-left: var(--space-12); }
  .sub-schelet > :global(:first-child) { flex: none; }
  /* ULTIMUL RAND AL LISTEI, nu un obiect mai tare decat ea. Dreptunghiul punctat
     de 44px era cel mai puternic lucru din panou, desi „mai adaug un pas" e ultima
     intentie cu care deschizi un task. Bifa lipsa e inlocuita de „+", pe aceeasi
     coloana, ca randul sa se alinieze cu subtaskurile de deasupra. */
  .sub-nou { display: flex; align-items: center; gap: 9px; width: 100%;
    min-height: var(--ctrl-sm); padding: 0 var(--space-6); border: none; border-radius: var(--radius-xs);
    background: none; color: var(--text-dim); font-size: var(--font-small);
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
  .ts-rand :global(.ts-chev) { flex: none; opacity: 0.5; transition: transform var(--dur-press) var(--ease); }
  .ts-rand.activ :global(.ts-chev) { transform: rotate(180deg); }

  /* Doar asezarea; butoanele sunt ale lui `SelectorZi`. */
  .ts-zile { margin: -2px 0 var(--space-sm); }

  /* Sectiunea de subtaskuri: eticheta micro + progres X/Y */
  .sub-section { display: flex; flex-direction: column; gap: var(--space-2xs); }
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
  .sub-del { width: var(--ctrl-xs); height: var(--ctrl-xs); display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; flex-shrink: 0; opacity: 0; transition: opacity var(--dur-fast); }
  .sub-row:hover .sub-del { opacity: 1; }
  .sub-del:hover { color: var(--danger); background: var(--danger-subtle); }
  .sub-add { display: flex; gap: var(--space-xs); margin-top: 0; }
  .sub-add input { flex: 1; padding: var(--space-6) var(--space-10); background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-body); }
  /* `flex-shrink: 0`: fara el butonul se strangea la 12px (masurat) — inputul de
     langa are `flex: 1` si il storcea, iar „+" ajungea o dunga netastabila. */
  .sub-add-btn { width: 32px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .sub-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
  .sub-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }



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
  .v3grid { display: grid; grid-template-columns: 1fr; gap: var(--space-14); align-items: start; }
  /* Suprafata se desprinde prin UMBRA, nu prin chenar (doua niveluri, vezi
     tokens.css). Padding-ul lateral scade la 8: cei 12px ai randului sunt ai
     CONTINUTULUI lui, deci textul incepe la 20 de la marginea cardului.
     Separatorul insa nu mostenea nimic din asta — de aceea marja lui e scrisa
     la el acasa, pe `.trow-wrap + .trow-wrap::before`. */
  .list-cell { min-width: 0; background: var(--bg-surface); border: 0;
    border-radius: var(--radius-md); box-shadow: var(--shadow-md);
    padding: var(--space-md) var(--space-sm); }

  @media (max-width: 768px) {
    /* `touch-action: pan-y` — FARA EA GESTUL DE SFERA NU EXISTA PE UN TELEFON
       ADEVARAT, si asta a fost raportat: „comutatia doar cu swipe pe toolbar a
       ramas". Motivul: `pan-y` ii spune browserului „verticala e a ta,
       orizontala e a mea". Fara declaratie, browserul pastreaza dreptul de a
       revendica un drag orizontal pentru propria lui mecanica de derulare si
       trimite `pointercancel` — deci gestul murea inainte de prag. Bara mergea
       fiindca `.toolbar` isi are de mult propriul `touch-action: pan-y`; de aceea
       simptomul arata exact ca „n-am schimbat nimic".
       NU se vede cu evenimente `PointerEvent` fabricate din pagina: alea ocolesc
       complet arbitrajul de touch-action al browserului, deci prima proba trecea
       vesela peste bug. Se verifica doar cu atingere reala (CDP
       `Input.dispatchTouchEvent`) — vezi `proba_sfere_deget`.
       Sigur aici fiindca `.page` e scopat la Tasks si pe /tasks nu exista niciun
       scroller orizontal; derularea verticala ramane nativa. */
    .page { padding: var(--space-md); touch-action: pan-y;
      /* BUTONUL PLUTITOR ISI FACE LOC. `.app-content` rezerva doar cat dockul
         (`--dock-h + 24`), dar butonul sta cu 28px peste dock si e inalt de 58 —
         deci ultimul rand al listei ajungea sub el, cu tot cu coloana termenului,
         si nici nu se mai putea atinge. 58 + 16 acopera banda cu 12px de scapare. */
      padding-bottom: calc(58px + var(--space-md)); }
    .toolbar { flex-direction: column; align-items: stretch; }
    .form-row-2 { grid-template-columns: 1fr; }
    /* O LINIE, ca in aplicatiile de to-do.
       Inainte: titlul sus, cele trei actiuni de intretinere pe o linie proprie
       dedesubt = 110px pe task. Acum randul are ~56px si actiunile vin din gest
       (glisare spre stanga); glisarea spre dreapta bifeaza. */
    .trow { flex-wrap: nowrap; align-items: center; min-height: var(--row-h-mobile);
            padding: 0; overflow: hidden; position: relative; touch-action: pan-y; }
    /* 52px: inaltimea de rand ceruta pe telefon. Fondul e al SUPRAFETEI, nu al
       unui panou propriu — randul nu mai e un card, e o linie din lista, iar
       ce-l desparte de vecin e separatorul de pe wrapper. Fondul trebuie sa fie
       totusi OPAC, fiindca pista de bifare sta sub el si trebuie acoperita pana
       cand degetul o descopera.
       IN REPAUS FATA E DREAPTA. Purta raza de control (10) si cand statea pe
       loc, deci colturile ei rotunjite lasau un gol sub separatorul drept de
       deasupra; la glisare coltul aluneca pe sub linie si nepotrivirea se vedea
       cu ochiul liber (raportat de Ion). O linie din lista n-are colturi — raza
       apare doar pe gest, cand randul e „ridicat" si are deja umbra. */
    .gl-fata { display: flex; align-items: center; gap: var(--space-12); width: 100%;
               min-height: var(--row-h-mobile); padding: 0 var(--space-12);
               background: var(--bg-surface); position: relative;
               z-index: 1; border-radius: 0; }
    /* FARA `will-change` PERMANENT. Il tinea fiecare rand din lista, deci pe 40 de
       taskuri erau 40 de straturi de compozitare pastrate tot timpul, si cand nu
       atingeai nimic. Regula casei o scrie chiar proiectul, in `lib/tragereTimeline.js`:
       `will-change` DOAR cat tine gestul. Il pune si il scoate `lib/glisare.js`. */
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
    .trow:global(.gl-tras) .gl-fata { box-shadow: var(--shadow-glisare);
                                      border-radius: var(--radius-sm); }
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

    .trow:global(.gl-bifa) { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }
    /* Cautarea si filtrele: caseta de cautare avea 25px inaltime utila, iar
       chipurile 30. */
    /* Ca la Proiecte: caseta are 44px, dar inputul dinauntru avea 25 si doar el
       primeste focus. */
        .a-ico { min-height: var(--tap-min); padding: 0 var(--space-12); font-size: var(--font-small); }
    .filters { gap: var(--space-xs); }
    .g-ico { width: var(--tap-min); min-height: var(--tap-min); }
    /* Capsula creste ODATA cu segmentele: tinta de 44 vine din segment, nu din
       padding-ul capsulei, altfel jumatate din capsula n-ar face nimic la atins.
       Pe telefon capsula sta pe suprafata cu umbra, iar segmentele urca la 15 —
       haina din desenul 3c, unde comutatorul e o tinta principala, nu un accesoriu. */
    .sfere { background: var(--bg-surface); box-shadow: var(--shadow-sm); }
    .seg { min-height: calc(var(--tap-min) - 4px); padding: var(--space-2xs) var(--space-14); font-size: var(--font-rand); }
    .tmain { min-height: var(--tap-min); }
    .page-header :global(.btn) { min-height: var(--tap-min); }

    /* Capul de grupa se lipeste SUB antetul paginii, nu de marginea ferestrei:
       altfel prima grupa ar sta pe jumatate ascunsa dupa bara de sus. */
    .grup-cap { top: var(--header-height); padding-top: var(--space-12); }

    /* Eticheta cartonasului („LISTA TASKURI 5") pleaca: antetul paginii scrie deja
       „Taskuri 5" la 40px deasupra. Doua titluri pentru aceeasi lista inseamna un
       task in minus pe ecran, si primul lucru pe care il vezi nu e un task. */
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
    .page-header, .toolbar, .quick-add { margin-bottom: var(--space-10); }
    .grup-cap:first-child { padding-top: var(--space-xs); }
    .list-cell { background: none; border: none; border-radius: 0;
      padding: var(--space-sm) 0 0; }
    /* Capul lipit se estompeaza peste fundalul PAGINII acum, nu peste al cutiei. */
    .grup-cap { background: linear-gradient(var(--bg) 72%, transparent); }

    /* Cautarea pliata: o iconita de 44px, nu o caseta cat randul. */
    .toolbar { flex-direction: row; align-items: center; gap: var(--space-sm); }
    .filters { flex: 1; justify-content: flex-end; }

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

    /* IN FOAIE, 48 — NU 44.
       `--tap-sheet` era definit in tokens si folosit intr-un singur loc din tot
       frontendul, deci foile mergeau la minimul de 44. Diferenta e a contextului,
       nu a gustului: 44 e pragul de la care NIMERESTI, iar in foaie apesi cu
       telefonul in mana, adesea pe teren, pe randuri lipite unul de altul. Cele
       44 raman pe controalele PAGINII (bifa din lista, filtrele, butoanele din
       cap); ce e mai jos e continutul foii.
       Interiorul taskului deschis: aici se bifeaza subtaskuri si se scrie unul nou. */
    .ts-check { min-width: var(--tap-sheet); min-height: var(--tap-sheet); }
    .ts-rand { min-height: var(--tap-sheet); }
    .sub-add input, .sub-add-btn { min-height: var(--tap-sheet); }
    .sub-add-btn { width: var(--tap-sheet); }
    /* Cardul isi pastreaza padding-ul orizontal si pe telefon — `2px 0` de aici
       anula (a doua oara) rama-la-0px reparata mai sus. Vertical ramane strans:
       inaltimea o da oricum bifa de 40px. */
    .sub-row { padding: 0 var(--space-6); min-height: var(--tap-sheet); }
    .sub-nou { min-height: var(--tap-sheet); font-size: var(--font-small); }
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
    .sub-row .gl-fata { padding: 0 var(--space-6); gap: 9px; min-height: var(--tap-sheet);
      background: var(--bg-overlay); border-radius: var(--radius-xs); }
    .sub-row:global(.gl-tras) .gl-fata { box-shadow: var(--shadow-glisare); }
    /* Titlul e tinta cea mai mare si face lucrul cel mai des: bifeaza. */
    .sub-title { text-align: left; cursor: pointer; }
    /* 1rem = 16px, aceeasi valoare pe CITIRE si pe SCRIERE. Regula globala urca
       oricum orice input la 16px pe telefon (zoom-ul Safari la focus), deci cu
       titlul la `--font-body` (14.4px) textul crestea cu 1.6px fix cand incepeai
       sa-l editezi. Egalarea se face in sus, nu in jos — sub 16 nu se poate. */
    .sub-title, .sub-edit { font-size: var(--font-input-mobile); }
    .qa-chip, .qa-dp :global(.dp-trigger) { min-height: var(--tap-sheet); padding: 0 var(--space-md);
      font-size: var(--font-small); }
    /* Indiciul despre Enter n-are cui sa se adreseze pe o tastatura de telefon. */
    .qa-hint { display: none; }
    .td-link { min-height: var(--tap-sheet); font-size: var(--font-small); }
    .td-dp :global(.dp-trigger) { min-height: var(--tap-sheet); font-size: var(--font-small); }
    .td-jos { gap: var(--space-lg); }
  }
</style>
