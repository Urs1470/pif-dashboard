<script>
  import { onMount } from 'svelte'
  import { flip } from 'svelte/animate'
  import { CalendarCheck, Plus, GripVertical, ArrowRight, X, CheckCircle2, ListPlus, Check, CalendarDays, User, Briefcase } from '@lucide/svelte'
  import {
    agenda, loadAgendaToday, quickAddToday, moveToTomorrow, moveToDate,
    removeFromToday, toggleDone, reorderAgenda
  } from '../stores/agenda.svelte.js'
  import { dueRing, formatDate, esteDepasit as isOverdue, esteAzi as isToday } from '../lib/formatters.js'
  import { etichetaTermenScurt } from '../lib/grupare.js'
  import ContorPasi from './ui/ContorPasi.svelte'
  import { glisare, inchideGlisarea } from '../lib/glisare.js'
  import { apasareLunga } from '../lib/apasareLunga.js'
  import { puls } from '../lib/gesturi.js'
  import { reordonare } from '../lib/reordonare.js'
  import { stergeTask, updateGlobalTask, actualizeazaTask } from '../stores/tasks.svelte.js'
  import FoaieTask from './FoaieTask.svelte'
  import { ecran } from '../lib/ecran.svelte.js'
  import { morphNavigate } from '../lib/focus.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import FoaieAdauga from './FoaieAdauga.svelte'
  import { inregistreaza } from '../lib/reincarcare.svelte.js'
  import { uita } from '../lib/cache.js'
  import EmptyState from './ui/EmptyState.svelte'
  import ErrorState from './ui/ErrorState.svelte'
  import Skeleton from './ui/Skeleton.svelte'
  import DatePicker from './ui/DatePicker.svelte'
  import { motionDuration, DUR_BASE, EASE, plecare, sosire, INTARZIERE_BIFA } from '../lib/motion.svelte.js'
  import { inregistreazaActiune } from '../lib/actiuneNoua.svelte.js'

  // Home paseaza un callback ca sa-si reincarce KPI-urile + cardul "urgente"/
  // "deadline-uri" dupa ce bifez / mut / scot un task (altfel ramaneau stale
  // pana la refresh sau schimbare de tab).
  let { onchange = () => {} } = $props()

  let quickTitle = $state('')
  let quickAdding = $state(false)
  let showAdauga = $state(false)

  let dragIndex = $state(null)
  let overIndex = $state(null)

  // Reorder settle animation (FLIP). Honors reduced-motion live (matchMedia change listener).
  const flipDur = $derived(motionDuration(DUR_BASE))

  const restanteCount = $derived(agenda.items.filter(i => i.is_restant).length)

  /** A doua linie a randului: UNDE e taskul. Proiectul, daca vine dintr-unul;
   *  altfel categoria — dar niciodata „General", valoarea implicita, care apare
   *  pe jumatate din randuri fara sa deosebeasca nimic de nimic. */
  function contextRand(it) {
    if (it.tip === 'proiect' && it.proiect_nume) return it.proiect_nume
    if (it.categorie && it.categorie !== 'General') return it.categorie
    return ''
  }

  /** Coloana pironita din dreapta. Un task recurent isi spune CADENTA: pentru el
   *  „când" nu e o zi, e un ritm.
   *
   *  IAR PE „AZI", DACA ARE ORA, SCRIE ORA (v41). Acelasi raţionament care e deja
   *  scris in Planificator pentru chipul de termen: „data de azi o stii; ce vrei sa
   *  vezi e ca a ajuns scadenta". Duse pana la capat: pe boardul de AZI, unde tot
   *  ce vezi e scadent azi, cuvantul „azi" in coloana nu deosebeste niciun rand de
   *  vecinul lui — ora, da. Coloana rămâne de 46px si mono, deci „09:00" incape si
   *  se citeste pe verticala cu termenele celorlalte randuri. */
  function termenScurt(it) {
    if (it.recurenta && !it.data_scadenta) return it.recurenta
    if (it.ora && isToday(it.data_scadenta)) return it.ora
    return etichetaTermenScurt(it.data_scadenta)
  }

  // ZIUA SE SCRIE AICI, O SINGURA DATA PE ECRAN.
  // Statea in bara de sus, ca subtitlu al salutului („Bună dimineața, Ion ·
  // vineri, 7 august 2026") — deci pe telefon nu se vedea deloc: `.header-context`
  // e `display: none` sub 768px, cu motivul scris in cod („brandul + titlul
  // propriu al paginii sunt de ajuns"). Numai ca Acasa e SINGURA pagina fara
  // titlu propriu, tocmai ca sa nu existe o banda in plus. Cele doua reguli se
  // anulau reciproc si ramanea un ecran care nu spune ce zi e.
  // Capul boardului scrie deja „Astăzi", deci ziua nu costa niciun rand nou.
  //
  // Se RECALCULEAZA, nu se scrie la montare: dashboardul ramane deschis peste
  // noapte, iar o data gresita pe ecranul cu care incepi ziua e mai rea decat
  // niciuna. `azi` se improspateaza cand tabul redevine vizibil — momentul in
  // care te uiti la el — si la trecerea de miezul noptii daca ramane deschis.
  // Majuscula se pune pe PRIMA litera, nu prin `text-transform: capitalize` —
  // acela ar scrie „Vineri, 7 August", iar in romana luna e cu litera mica.
  let azi = $state(new Date())
  const ziua = $derived.by(() => {
    const s = azi.toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'long' })
    return s.charAt(0).toUpperCase() + s.slice(1)
  })

  function improspateazaZiua() {
    const acum = new Date()
    if (acum.toDateString() !== azi.toDateString()) azi = acum
  }

  // isOverdue/isToday vin din formatters.js — aceeasi axa si aceleasi praguri ca
  // dueRing(), o singura definitie pentru toate listele.

  async function doQuickAdd() {
    const t = quickTitle.trim()
    if (!t || quickAdding) return
    quickAdding = true
    try {
      await quickAddToday(t)
      quickTitle = ''
      onchange()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally {
      quickAdding = false
    }
  }

  // Randul care isi joaca stampila chiar acum (`.bifare`, reguli in global.css).
  let bifatAcum = $state('')

  async function onToggle(it, dinGest = false) {
    const eraFacut = it.status === 'done'
    // Stampila + taietura, inainte ca randul sa plece — dar nu pe gest, unde
    // verdele pistei si zborul sunt deja raspunsul (o animatie pe schimbare).
    if (!eraFacut && !dinGest) {
      bifatAcum = it.tip + ':' + it.id
      await new Promise(r => setTimeout(r, motionDuration(INTARZIERE_BIFA)))
      bifatAcum = ''
    }
    try {
      // Scot randul din lista INAINTE de dus-intorsul cu serverul: boardul nu
      // tine taskuri bifate (`/api/agenda/today` filtreaza `status != 'done'`),
      // deci oricum pleaca — dar altfel ar pleca dupa ~200ms, cand nu mai e clar
      // ca a plecat fiindca l-ai atins tu. `toggleDone` reincarca agenda la
      // final, deci adevarul se aseaza singur (si la eroare, tot el).
      if (!eraFacut) {
        if (it.sfera === 'personal') agenda.personale = agenda.personale.filter(x => x.id !== it.id)
        else agenda.items = agenda.items.filter(x => !(x.tip === it.tip && x.id === it.id))
      }
      const res = await toggleDone(it.tip, it.id, it.status)
      if (res?.recurring_spawned) {
        toast(`Finalizat ✓ — următoarea apariție: ${formatDate(res.recurring_next)}`, 'success')
      } else if (!eraFacut) {
        // Acelasi „Anulează" ca in Taskuri si in pagina de proiect. Aici conteaza
        // cel mai mult: pe boardul de azi bifezi si prin glisare, cu degetul mare,
        // in timp ce derulezi — deci si din greseala.
        toastUndo(`Făcut: ${it.titlu.slice(0, 34)}${it.titlu.length > 34 ? '…' : ''}`, {
          // `toggleDone` reincarca singur agenda; al treilea argument e starea
          // CURENTA, iar acum e „done" — deci apelul asta o intoarce la „to_do".
          onUndo: async () => { await toggleDone(it.tip, it.id, 'done'); onchange() },
        })
      }
      onchange()
    } catch (e) {
      await loadAgendaToday()
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  // ACELASI VERB, ACEEASI PLASA CA IN /tasks (constatarea B2 din auditul de UI).
  // `onRemove` scotea termenul si chema `onchange()` — atat. Randul disparea de
  // pe board FARA NICIUN mesaj, in timp ce exact aceeasi actiune din /tasks
  // scrie „Termen scos" si ofera „Anulează". Boardul „Astăzi" e primul ecran al
  // zilei, deci suprafata cea mai expusa era cea fara plasa — acelasi defect de
  // paritate care a fost reparat o data la `removeSubtask`.
  //
  // Undo-ul repune EXACT data dinainte, nu „azi": un task restant scos din
  // greseala trebuie sa se intoarca restant, nu replanificat in tacere.
  async function onTomorrow(it) {
    const inainte = it.data_scadenta || ''
    try {
      await moveToTomorrow(it.tip, it.id)
      onchange()
      toastUndo('Mutat pe mâine', {
        onUndo: async () => { await setTermen(it, inainte); onchange() },
      })
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function onRemove(it) {
    const inainte = it.data_scadenta || ''
    try {
      await removeFromToday(it.tip, it.id)
      onchange()
      toastUndo('Termen scos', {
        onUndo: async () => { await setTermen(it, inainte); onchange() },
      })
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  /** Ora unui task personal (v41). `''` o scoate. Vezi nota din `pages/Tasks.svelte`
   *  pentru de ce n-are toast: controlul din care vine ARATA valoarea. */
  async function setOra(it, v) {
    if (!it) return
    try {
      await updateGlobalTask(it.id, { ora: v || '' })
      await loadAgendaToday()
      onchange()
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  /** Repune un termen (sau il scoate, daca e gol) — drumul de intoarcere al
   *  celor doua actiuni de mai sus. */
  async function setTermen(it, zi) {
    if (zi) await moveToDate(it.tip, it.id, zi)
    else await removeFromToday(it.tip, it.id)
  }

  // GESTUL DUCE LA ALEGEREA ZILEI, NU LA O ZI ALEASA DE APLICATIE.
  // Stanga executa „Mâine" — pe boardul de azi mâine parea verbul potrivit,
  // fiindca tot ce vezi e scadent azi. Dar amanarea nu e „inca o zi": muti un
  // task cand stii CAND il faci, iar ziua aia e rareori mâine.
  //
  // ===== FOAIA RANDULUI DE PE TELEFON =====
  //
  // Gestul deschidea DIRECT calendarul (`dpGest.deschideCalendarul()`) — deci pe
  // „Astăzi" alegerea zilei era o grila de luna, in /tasks era `SelectorZi`
  // (Azi · Mâine · Alege · Scoate), iar in pagina proiectului un formular. Trei
  // raspunsuri la aceeasi intrebare — exact cele trei pe care le numeste ca bug
  // antetul lui `SelectorZi`, si care pe drumul GESTULUI nu fusesera unificate.
  // Acum toate patru listele deschid aceeasi foaie.
  //
  // Odata cu gestul a plecat si `.dp-gest` — invelisul de 0×0 care tinea un
  // `DatePicker` fara declansator vizibil, doar ca sa aiba gestul ce calendar sa
  // deschida. Calendarul e acum al foii, iar pe desktop randul isi are propriul
  // declansator la vedere (`.arow-actions`, „Altă zi"), care n-a fost atins.
  let foaieTask = $state(null)
  let foaieMod = $state('actiuni')
  let foaieDeschisa = $state(false)
  let taskEditat = $state(null)

  function deschideFoaia(it, mod) {
    foaieTask = it
    foaieMod = mod
    foaieDeschisa = true
  }

  // Stergere reversibila din boardul de azi. Randul pleaca pe loc, scrierea pe
  // server abia la expirarea toastului — aceeasi mecanica ca la subtaskuri.
  function stergeDinBoard(it) {
    const lista = it.sfera === 'personal' ? agenda.personale : agenda.items
    const cheie = it.tip + ':' + it.id
    const idx = lista.findIndex(x => x.tip + ':' + x.id === cheie)
    if (idx === -1) return
    const scos = lista[idx]
    if (it.sfera === 'personal') agenda.personale = lista.filter(x => x.tip + ':' + x.id !== cheie)
    else agenda.items = lista.filter(x => x.tip + ':' + x.id !== cheie)
    toastUndo('Task șters', {
      onUndo: () => {
        const cur = [...(it.sfera === 'personal' ? agenda.personale : agenda.items)]
        cur.splice(Math.min(idx, cur.length), 0, scos)
        if (it.sfera === 'personal') agenda.personale = cur
        else agenda.items = cur
      },
      onCommit: async () => {
        try { await stergeTask(it.tip, it.id) }
        catch (e) { toast(`Eroare: ${e.message}`, 'error') }
        onchange()
      },
    })
  }

  // Reschedule via the shared DatePicker (inline, same calendar as global/project
  // tasks). Picking a day moves the task; clearing ("Sterge") removes it from today.
  async function onMoveDate(it, v) {
    const inainte = it.data_scadenta || ''
    try {
      if (v) await moveToDate(it.tip, it.id, v)
      else await removeFromToday(it.tip, it.id)
      onchange()
      // Si ramura de golire (`×` din calendar) anunta si se poate anula: era
      // singura din cele patru care nu scotea niciun sunet.
      toastUndo(v ? `Mutat pe ${formatDate(v)}` : 'Termen scos', {
        onUndo: async () => { await setTermen(it, inainte); onchange() },
      })
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  function openItem(e, it) {
    const src = e?.currentTarget?.closest?.('.arow') || e?.currentTarget
    if (it.tip === 'proiect' && it.proiect_id) morphNavigate(src, `/projects/${it.proiect_id}`, 'task', it.id)
    // Un task personal aterizeaza in VEDEREA lui de pe /tasks, nu in cea de munca.
    else morphNavigate(src, it.sfera === 'personal' ? '/tasks?sfera=personal' : '/tasks', 'global', it.id)
  }

  // --- Reordering (HTML5 drag on desktop, arrow buttons on mobile) ---
  function onDragStart(e, i) {
    dragIndex = i
    e.dataTransfer.effectAllowed = 'move'
    try { e.dataTransfer.setData('text/plain', String(i)) } catch (_) {}
  }
  function onDragOver(e, i) {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    overIndex = i
  }
  async function onDrop(e, i) {
    e.preventDefault()
    const from = dragIndex
    dragIndex = null
    overIndex = null
    await commitMove(from, i)
  }
  function onDragEnd() { dragIndex = null; overIndex = null }

  async function commitMove(from, to) {
    if (from == null || to == null || from === to) return
    const arr = [...agenda.items]
    const [m] = arr.splice(from, 1)
    arr.splice(to, 0, m)
    agenda.items = arr // optimistic
    try { await reorderAgenda(arr) }
    catch (e) { toast(`Eroare: ${e.message}`, 'error'); await loadAgendaToday() }
  }

  // Glisarea inlocuieste butoanele DOAR unde nu exista cursor. Pe desktop randul
  // isi pastreaza actiunile la vedere.
  const peTelefon = $derived(ecran.telefon)
  // Cand ecranul creste (rotire, tableta), randul deschis prin glisare trebuie
  // inchis: pe desktop panoul e ascuns, deci ar ramane un rand impins la stanga
  // fara nimic dedesubt.
  $effect(() => { if (!peTelefon) inchideGlisarea() })

  // TRAGE SA REINCARCI, pe Acasa. `uita` inainte: altfel cererea s-ar servi din
  // cache si arcul s-ar roti degeaba — exact in singurul moment in care gestul e
  // chemat, adica atunci cand banuiesti ca ce vezi nu mai e adevarat.
  $effect(() => inregistreaza(async () => { uita('/api/agenda'); await loadAgendaToday() }))

  onMount(() => {
    loadAgendaToday()
    // Un ceas care bate la fiecare minut ar fi risipa pentru un text care se
    // schimba o data pe zi: verificam cand tabul redevine vizibil, plus un tic
    // rar pentru cazul in care ramane deschis peste miezul noptii.
    document.addEventListener('visibilitychange', improspateazaZiua)
    const tic = setInterval(improspateazaZiua, 60_000)
    return () => {
      document.removeEventListener('visibilitychange', improspateazaZiua)
      clearInterval(tic)
      inchideGlisarea()
    }
  })

  // BUTONUL „+" E AL DOCULUI ACUM (AURORA). Pagina spune doar CE creeaza el; cutia,
  // pozitia si materialul le tine `Dock.svelte`. Inainte, fiecare pagina cu lista
  // isi desena propriul `.fab` in coltul de jos — patru copii ale aceleiasi cutii,
  // care acopereau ultimul rand exact acolo unde te uitai.
  // `$effect` cheama singur curatarea la demontare si la fiecare schimbare a
  // conditiei, deci butonul dispare cand nu mai are ce crea (arhiva, alt tab).
  $effect(() => {
    if (!(peTelefon)) return
    return inregistreazaActiune('Adaugă task pentru azi', () => { puls(); taskEditat = null; showAdauga = true })
  })
</script>

<section class="board cell-in">
  <div class="board-head">
    <!-- „Astăzi · sâmbătă, 8 august · 2 restante".
         Contorul total a plecat: pe un board unde vezi toate randurile deodata,
         „14" nu decide nimic — le numeri uitandu-te. Restantele raman, fiindca
         ele decid daca te apuci de ce ai pe azi sau recuperezi ce n-ai facut.
         Iconita a plecat si ea: titlul scrie deja „Astăzi". -->
    <div class="bh-left">
      <h2>Astăzi</h2>
      <span class="bh-zi">{ziua}</span>
      {#if restanteCount > 0}
        <span class="bh-restante"><span class="bh-punct"></span>{restanteCount} {restanteCount === 1 ? 'restant' : 'restante'}</span>
      {/if}
    </div>
    <!-- „Adaugă task", nu „Adaugă task EXISTENT": foaia nu mai e doar o cautare.
         Scrii, si primul rand e „Creează «…»" — cine scria aici un titlu care nu
         exista primea inainte „Niciun task găsit" si un drum inchis. -->
    <button class="bh-add" onpointerdown={() => puls()} onclick={() => { taskEditat = null; showAdauga = true }} aria-label="Adaugă task">
      <ListPlus size={15} /> <span class="bh-add-txt">Adaugă task</span>
    </button>
  </div>

  <form class="quick-add" onsubmit={(e) => { e.preventDefault(); doQuickAdd() }}>
    <!-- O SINGURA CALE DE ADAUGARE PE ECRAN (A3). Langa camp statea un buton „+"
         care facea exact ce face Enter — a doua cale catre aceeasi actiune, in
         acelasi loc. Plusul ramane, dar ca SEMN in interiorul campului: spune ce
         e linia asta fara sa mai fie o tinta de apasat.
         Pe telefon nu ramane nimic de apasat fiindca nu e nevoie: formularul are
         un singur camp de text, deci tasta Go a tastaturii il trimite nativ.
         Placeholderul o scrie pe desktop, unde Enter e singurul drum. -->
    <div class="qa-camp">
      <span class="qa-ico" aria-hidden="true"><Plus size={17} /></span>
      <input type="text" placeholder={peTelefon ? 'Task rapid pentru azi' : 'Task rapid pentru azi, apoi Enter'} bind:value={quickTitle} disabled={quickAdding} />
    </div>
  </form>

  <!-- `!agenda.incarcat`, NU `items.length === 0`: a doua forma confunda „inca
       n-am primit nimic" cu „raspunsul e gol", deci pe un board fara niciun task
       se vedea intai scheletul si abia apoi starea goala — de fiecare data, chiar
       si cu raspunsul deja in memorie. Vezi nota de la `incarcat` din store. -->
  <!-- `!incarcat`, fara `loading`: daca n-avem inca un raspuns, ASTEPTAM — prin
       definitie. Cu `loading &&` in fata, primul cadru (inainte ca incarcarea sa
       apuce sa porneasca) cadea pe ramura urmatoare si arata STAREA GOALA, apoi
       scheletul, apoi raspunsul: trei forme pentru un board gol. -->
  {#if !agenda.incarcat && !agenda.error}
    <div class="asteptare"><Skeleton varianta="rand" randuri={4} /></div>
  {:else if agenda.error}
    <!-- ErrorState cu retry, ca in restul aplicatiei (regula de design: „erori:
         <ErrorState> (cu retry)"). Aici era un paragraf rosu fara niciun drum
         inainte — singura lista din aplicatie care la esec te lasa sa dai
         refresh din browser. -->
    <ErrorState message={agenda.error} onretry={() => loadAgendaToday()} />
  {:else if agenda.items.length === 0}
    <EmptyState icon={CalendarCheck} title="Nimic planificat azi" description="Adaugă un task rapid sau alege din taskurile existente." />
  {:else}
    <!-- Capul grupei „Muncă" apare doar cand exista si sectiunea personala:
         desenul (3a) arata cele doua grupuri cu aceeasi haina, dar o grupare cu
         o singura grupa n-ar imparti nimic — antetul ar fi zgomot. -->
    {#if agenda.personale.length}
      <div class="pers-cap munca"><span class="pers-ico" aria-hidden="true"><Briefcase size={13} /></span>Muncă<span class="pers-n">{agenda.items.length}</span></div>
    {/if}
    <div class="a-list" role="list"
         use:reordonare={{ activ: peTelefon, selectorRand: '.arow', selectorManer: '.gl-maner', onMutare: commitMove }}>
      {#each agenda.items as it, i (it.tip + ':' + it.id)}
        <div
          class="arow"
          class:done={it.status === 'done'}
          class:bifare={bifatAcum === it.tip + ':' + it.id}
          class:dragover={overIndex === i}
          class:dragging={dragIndex === i}
          style="--ring: {dueRing(it.data_scadenta)}"
          role="listitem"
          ondragover={(e) => onDragOver(e, i)}
          ondrop={(e) => onDrop(e, i)}
          animate:flip={{ duration: flipDur, easing: EASE }}
          in:sosire|local
          out:plecare
          use:glisare={{ activ: peTelefon, onBifa: it.status === 'done' ? null : () => onToggle(it, true), onAmana: () => deschideFoaia(it, 'plan') }}
          use:apasareLunga={{ activ: peTelefon, actiune: () => deschideFoaia(it, 'actiuni'), ignora: '.gl-maner' }}
        >
          <!-- UN GEST = UN VERB, IN AMBELE SENSURI (vezi lib/glisare.js).
               Dreapta = „Făcut", stanga = „Mâine", amandoua cu pista care se
               coloreaza progresiv. Aici era un panou de trei actiuni × 58px care se
               descoperea glisand: 176px din 390 acopereau taskul pe care actionai,
               iar cele doua direcii aveau doua modele diferite („descopera un meniu"
               vs „executa"). „Dată" si „Scoate" au ramas pe desktop, in rand
               (`.arow-actions`), si la o atingere pe titlu — care oricum deschide
               taskul in lista lui. Pe desktop, unde nu se gliseaza, ambele piste
               ramanind ascunse nu costa nimic. -->
          <div class="gl-pista" aria-hidden="true"><span class="gl-ico"><Check size={17} strokeWidth={3} /></span><span class="gl-et">Făcut</span></div>
          <div class="gl-pista-s" aria-hidden="true"><span class="gl-et-s">Planifică</span><span class="gl-ico-s"><CalendarDays size={17} strokeWidth={2.4} /></span></div>

          <div class="gl-fata">
          <!-- Doua manere in ACELASI slot de 16px, niciodata amandoua deodata:
               `.grip` are drag nativ (mouse), `.gl-maner` e suprafata de apucat
               cu degetul (lib/reordonare.js). Statea la capatul din dreapta al
               randului, adica exact unde e coloana de termen — deci pe telefon
               reordonarea si termenul se bateau pe aceiasi pixeli. -->
          <span class="grip" role="button" tabindex="0" aria-label="Reordonează cu săgețile" draggable="true" ondragstart={(e) => onDragStart(e, i)} ondragend={onDragEnd} onkeydown={(e) => { if (e.key === 'ArrowUp' && i > 0) { e.preventDefault(); commitMove(i, i - 1) } else if (e.key === 'ArrowDown' && i < items.length - 1) { e.preventDefault(); commitMove(i, i + 1) } }} title="Trage sau folosește săgețile pentru a reordona"><GripVertical size={15} /></span>
          <span class="gl-maner" aria-hidden="true"><GripVertical size={17} /></span>

          <button class="check" onclick={() => onToggle(it)} title="Marchează ca făcut">
            {#if it.status === 'done'}<CheckCircle2 size={18} />{:else}<span class="check-empty"></span>{/if}
          </button>

          <!-- `title`: TITLUL TAIAT TREBUIE SA SE POATA CITI UNDEVA.
               Randul scurteaza cu ellipsis („Citire log alarme AL-4 supratensiu…")
               si nu exista niciun alt loc in ecran care sa arate restul — masurat,
               6 elemente taiate fara `title` pe Acasa si in Planificator. -->
          <button class="amain" title={it.titlu} onclick={(e) => openItem(e, it)}>
            <!-- CONTORUL DE PASI STA LANGA TITLU, ca in /tasks si in pagina de
                 proiect — un singur loc pentru aceeasi informatie. Statea pe
                 linia a doua, si acolo avea un bug tacut: intreaga linie era
                 gardata pe `contextRand(it)`, deci un task cu pasi dar fara
                 proiect si fara categorie nu-si arata contorul deloc. -->
            <span class="atitlu">
              <span class="atitle">{it.titlu}</span>
              <ContorPasi gata={it.subtask_done || 0} total={it.subtask_total || 0} />
            </span>
            <!-- A DOUA LINIE, doar cand are ce spune: unde e taskul (proiectul
                 sau categoria). Erau cinci chipuri pe un rand — termen, pasi,
                 recurenta, proiect, categorie — dintre care termenul si recurenta
                 au urcat in coloana pironita din dreapta, iar restul erau pastile
                 colorate mai tari decat titlul.
                 Aici raman ca TEXT, la 13px, gri: se citesc cand le cauti. -->
            {#if contextRand(it)}
              <span class="ainfo"><span class="a-unde">{contextRand(it)}</span></span>
            {/if}
          </button>

          <!-- Un singur invelis pentru cele doua grupuri de actiuni. Pe desktop e
               `display: contents`, deci nu schimba nimic; pe telefon e ce cade pe
               linia a doua, INTREG. Fara el, wrap-ul de flex decidea singur unde se
               rupe randul si iesea pe trei linii (bifa singura sus, titlu, actiuni)
               = 172px pe task, adica patru taskuri pe ecran. -->
          <div class="arow-tools">
          <!-- TREI ACTIUNI, CU TEXT. Erau patru iconite mute, si una dintre ele
               („Deschide") repeta ce face deja clicul pe rand. Toate trei
               raspund la aceeasi intrebare — CAND — deci stau impreuna, in
               ordinea in care le folosesti. -->
          <div class="arow-actions">
            <button class="abtn" onclick={() => onTomorrow(it)}><ArrowRight size={14} strokeWidth={1.5} />Mâine</button>
            <span class="row-date" title="Planifică pe altă zi">
              <DatePicker value={it.data_scadenta} eticheta="Altă zi" onchange={(v) => onMoveDate(it, v)} />
            </span>
            <button class="abtn danger" onclick={() => onRemove(it)}
                    title="Scoate termenul — taskul se întoarce în „fără termen”"><X size={14} strokeWidth={1.5} />Scoate</button>
          </div>
          </div>
          <span class="atermen" class:sev={isOverdue(it.data_scadenta)}
                class:acum={isToday(it.data_scadenta)}>{termenScurt(it)}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- SECTIUNEA PERSONALA — o anexa tacuta, nu un al doilea board.
       Apare DOAR cand exista taskuri personale scadente azi/restante (cerinta
       Ion: taskurile personale nu se amesteca cu munca, dar un termen personal
       pe azi nu are voie sa fie invizibil). Antetul e haina desenata pentru un
       cap de grupa: SEMN (iconita 13), eticheta majuscula si numarul — nicio
       culoare, niciun punct. Semnul e acelasi `user` de pe comutatorul de sfera
       din /tasks, deci cele doua suprafete se refera in continuare una la alta,
       fara sa aduca o a treia culoare pe ecran (punctul violet de dinainte).
       NU foloseste .grup-cap/.grup-t (clase citite de audit_mobil pe /tasks) si
       nici <h2> pereche cu „Astăzi".
       Randurile sunt ACELEASI .arow (severitatea = singura culoare), fara insa
       index, grip si reordonare: lista e scurta, ordinea o da serverul
       (restante-first, apoi alfabetic). -->
  {#if agenda.personale.length}
    <div class="pers-cap"><span class="pers-ico" aria-hidden="true"><User size={13} /></span>Personal<span class="pers-n">{agenda.personale.length}</span></div>
    <div class="a-list" role="list">
      {#each agenda.personale as it (it.id)}
        <div
          class="arow"
          class:done={it.status === 'done'}
          class:bifare={bifatAcum === it.tip + ':' + it.id}
          style="--ring: {dueRing(it.data_scadenta)}"
          role="listitem"
          animate:flip={{ duration: flipDur, easing: EASE }}
          in:sosire|local
          out:plecare
          use:glisare={{ activ: peTelefon, onBifa: it.status === 'done' ? null : () => onToggle(it, true), onAmana: () => deschideFoaia(it, 'plan') }}
          use:apasareLunga={{ activ: peTelefon, actiune: () => deschideFoaia(it, 'actiuni'), ignora: '.gl-maner' }}
        >
          <div class="gl-pista" aria-hidden="true"><span class="gl-ico"><Check size={17} strokeWidth={3} /></span><span class="gl-et">Făcut</span></div>
          <div class="gl-pista-s" aria-hidden="true"><span class="gl-et-s">Planifică</span><span class="gl-ico-s"><CalendarDays size={17} strokeWidth={2.4} /></span></div>

          <div class="gl-fata">
          <!-- Coloana manerului ramane REZERVATA si aici, unde nu se reordoneaza:
               altfel randurile personale ar incepe cu 16px mai la stanga decat
               cele de munca, iar decalajul s-ar citi ca o greseala de aliniere,
               nu ca „astea nu se muta". -->
          <span class="grip-loc" aria-hidden="true"></span>

          <button class="check" onclick={() => onToggle(it)} title="Marchează ca făcut">
            {#if it.status === 'done'}<CheckCircle2 size={18} />{:else}<span class="check-empty"></span>{/if}
          </button>

          <button class="amain" title={it.titlu} onclick={(e) => openItem(e, it)}>
            <span class="atitlu">
              <span class="atitle">{it.titlu}</span>
              <ContorPasi gata={it.subtask_done || 0} total={it.subtask_total || 0} />
            </span>
          </button>

          <div class="arow-tools">
          <div class="arow-actions">
            <button class="abtn" onclick={() => onTomorrow(it)}><ArrowRight size={14} strokeWidth={1.5} />Mâine</button>
            <span class="row-date" title="Planifică pe altă zi">
              <DatePicker value={it.data_scadenta} eticheta="Altă zi" onchange={(v) => onMoveDate(it, v)} />
            </span>
            <button class="abtn danger" onclick={() => onRemove(it)}
                    title="Scoate termenul — taskul se întoarce în „fără termen”"><X size={14} strokeWidth={1.5} />Scoate</button>
          </div>
          </div>
          <span class="atermen" class:sev={isOverdue(it.data_scadenta)}
                class:acum={isToday(it.data_scadenta)}>{termenScurt(it)}</span>
          </div>
        </div>
      {/each}
    </div>
  {/if}

</section>

<!-- BUTONUL PLUTITOR DE ADAUGARE, pe telefon — acelasi ca in /tasks (58px, rază
     20, peste dock, la dreapta). Ion, 2026-08-21: „butonul de adaugare de pe
     Acasa nu e foarte reactiv si vreau sa-l faci mai proeminent pe mobil."
     Butonul mic „Adaugă task" din capul boardului ramane doar pe desktop (vezi
     `.bh-add { display: none }` in blocul de telefon). -->

<!-- ACEEASI foaie de adaugare ca in /tasks si ca in tabul Taskuri al unui proiect.
     Aici a inlocuit `TaskPickerModal`, care putea doar sa CAUTE. -->
<FoaieAdauga bind:open={showAdauga} onSchimbare={() => { loadAgendaToday(); onchange() }}
             sfera={taskEditat?.sfera || 'munca'}
             editeaza={taskEditat}
             onSalveaza={async (d) => { await actualizeazaTask(taskEditat.tip, taskEditat.id, d) }} />

<!-- Foaia randului de pe telefon. „Deschide" duce taskul in lista lui, exact unde
     ducea si atingerea titlului (`openItem`). -->
<FoaieTask bind:open={foaieDeschisa} task={foaieTask} mod={foaieMod}
           onZi={(v) => onMoveDate(foaieTask, v)}
           onMaine={() => onTomorrow(foaieTask)}
           onOra={(v) => setOra(foaieTask, v)}
           onEditeaza={() => { taskEditat = foaieTask; showAdauga = true }}
           onSterge={() => stergeDinBoard(foaieTask)} />

<style>

  /* Suprafata se desprinde prin umbra. Padding-ul lateral scade la 8, fiindca
     randul isi aduce propriii 12 — separatorul iese la 20 de la marginea
     cardului, adica marja laterala ceruta, fara s-o scrie nimeni a doua oara. */
  /* `--panel-line`, nu `--border`: cardul se desprinde prin UMBRA, iar linia doar
     ii inchide conturul. Cu `border: 0` (cum era) marginea se pierdea pe tema
     deschisa, unde umbra e slaba si suprafata e alba pe un fond aproape alb. */
  .board { background: var(--bg-surface); border: 1px solid var(--panel-line); border-radius: var(--radius-md);
    box-shadow: var(--shadow-md); padding: var(--space-20) var(--space-sm) var(--space-6);
    margin-bottom: var(--space-lg); }

  .board-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-12); margin: 0 var(--space-sm) var(--space-md); }
  /* Alinierea e pe LINIA DE BAZA, nu pe centru: „Astăzi" e la 25px si ziua la
     13, deci centrate ar pluti una fata de alta. Pe baza, se citesc ca o
     propozitie. */
  .bh-left { display: flex; align-items: baseline; gap: var(--space-12); color: var(--text); min-width: 0; }
  /* Perechea de TITLU din AURORA: greutatea si urmarirea au nume de rol
     (`--w-title` / `--tracking-title`), nu trepte de scara — un titlu se strange mai
     mult decat un rand de text obisnuit. */
  .bh-left h2 { font-size: var(--font-title); font-family: var(--font-heading);
                font-weight: var(--w-title); letter-spacing: var(--tracking-title); }
  .bh-zi { font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-dim);
           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .bh-restante { display: inline-flex; align-items: center; gap: var(--space-6); flex: none;
    font-size: var(--font-small); font-weight: var(--fw-semibold);
    color: var(--danger); white-space: nowrap; }
  .bh-punct { width: 7px; height: 7px; border-radius: 50%; background: var(--danger); }
  /* `.bh-count` / `.bh-restante` au plecat: sunt `.count` si `.count danger` din
     global.css — aceeasi pastila ca peste tot (vezi comentariul de acolo). */
  /* Controlul e in haina neutra a sistemului: tenta si cerneala de accent sunt
     limbajul lui „activ / ales", iar butonul asta nu e nici una, nici alta — e
     un drum secundar catre acelasi board. Hoverul ridica fondul, atat. (Aceeasi
     reteta ca la Calendar M3 si Departament C2.) `border-color` de la hover a
     plecat odata cu ea: butonul n-are chenar din care sa se schimbe ceva. */
  .bh-add { display: inline-flex; align-items: center; gap: 7px; height: var(--ctrl-md); padding: 0 var(--space-14); font-size: var(--font-body); font-weight: var(--fw-semibold); border-radius: var(--radius-sm); background: var(--bg-elevated); border: 1px solid var(--panel-line); color: var(--text-secondary); cursor: pointer; transition: var(--transition-pressable); flex-shrink: 0; }
  .bh-add:hover { background: var(--bg-hover); color: var(--text); }

  /* Campul e UN obiect, iar plusul e semnul lui dinauntru — nu un al doilea
     buton langa el (vezi comentariul din markup). Chenarul, fondul si raza trec
     de pe `input` pe invelis, ca iconita sa stea in interiorul lor; inputul
     ramane text gol pe fondul invelisului. Focusul se muta odata cu ele:
     `:focus-within`, fiindca ce primeste focusul e copilul. */
  .quick-add { display: flex; margin: 0 var(--space-sm) var(--space-md); }
  .qa-camp { flex: 1; min-width: 0; display: flex; align-items: center; gap: var(--space-10);
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

  /* `.a-skel` a plecat: invelisul de schelet al boardului nu mai exista in
     markup (scheletul vine acum din `Skeleton.svelte`, cu forma randului real).
     Clasa nu se mai randeaza nicaieri, deci Svelte taia regula din build. */

  /* Antetul sectiunii personale — haina de cap de grupa din desen: eticheta
     majuscula 12/600 in `--text-secondary`, semnul si numarul o treapta mai jos,
     in `--text-dim`. Eticheta e cea care se citeste, deci ea sta mai sus; semnul
     si cifra o insotesc. Bordura de sus il desparte de board fara sa-l ridice la
     rang de al doilea board.
     Doar NUMARUL e mono: DM Mono e pentru cifre care se compara pe verticala, iar
     „PERSONAL" e un cuvant — se poate traduce, deci nu e mono. */
  /* Haina din desen (3a): padding 14px 12px 4px — 12 lateral, cat paddingul
     randului, ca eticheta sa inceapa pe aceeasi verticala cu titlurile. */
  .pers-cap { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-14) var(--space-12) var(--space-xs); font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-secondary); }
  /* Doar grupa a doua poarta separatorul de sectiune; „Muncă" sta sub compozitor. */
  .pers-cap:not(.munca) { margin-top: var(--space-sm); border-top: 1px solid var(--border); }
  /* Semn, nu bulina — acelasi desen ca pe comutatorul de sfera din /tasks, ca cele
     doua suprafete sa se refere in continuare una la alta fara sa aduca o a treia
     culoare pe ecran. */
  .pers-ico { display: inline-flex; align-items: center; color: var(--text-dim); flex-shrink: 0; }
  .pers-n { font-family: var(--font-mono); color: var(--text-dim); font-variant-numeric: tabular-nums;
    text-transform: none; letter-spacing: var(--tracking-normal); }

  /* `relative` — vezi nota de la `plecare` (motion.svelte.js). */
  .a-list { display: flex; flex-direction: column; position: relative; }
  /* SEVERITATEA = BORDURA DIN STANGA, ca in /tasks si cum o scrie documentatia
     (CLAUDE.md/MEMORY: „severitatea se citeste din bordura din stanga, dupa
     termen"). Aici supravietuia varianta veche — un underline scurt jos
     (`::after`) — deci ACELASI task avea doua limbaje de severitate pe doua
     ecrane. Un task trebuie sa arate la fel oriunde apare. */
  /* Ion: „poti face putin mai inguste pe desktop taskurile, pe inaltime?"
     8px sus / 10px jos -> 5/7: randul scade de la ~62 la ~56px, fara sa se
     atinga fontul sau meta-randul. Doar desktop — pe telefon padding-ul
     vertical e al lui `.gl-fata` si ramane cum e. */
  /* MUCHIA DE SEVERITATE A PLECAT. Erau 3px care insemnau, in acelasi ecran, cand
     „urgent", cand „proiectul X" — iar din cele cinci trepte doar doua se vedeau
     (--accent si --warning sunt acelasi hex). Severitatea e acum pe inelul bifei
     (`--ring`) si pe textul termenului. Bordura devine uniforma, iar cei 2px
     pierduti de la stanga se intorc in padding, ca randul sa nu se decaleze fata
     de antetul listei. */
  /* ACELASI RAND CA IN /tasks: 46px, gap 12, coloana de termen pironita la 46px.
     Un task trebuie sa arate la fel oriunde apare — altfel inveti pagina, nu
     taskul. Cardul cu rama si 6px de distanta a plecat: lista e un obiect citit
     pe verticala, iar ce desparte doua randuri e o linie cu marja laterala.
     Fara `translateX(4px)` la hover: deplasarea muta si coloana de termen, adica
     exact ce trebuie sa stea pe loc cat cauti actiunile. */
  /* RAZA RANDULUI, pe desktop. V13 a scos-o de aici din reflex, desi cerea raza
     0 pe FATA DE GLISARE (`.gl-fata`, obiect de telefon) — iar fara ea fondul de
     hover se intindea dintr-o muchie a listei in cealalta, cu colturi drepte,
     sub un card cu raza 14. In /tasks acelasi rand ramanea rotunjit, fiindca
     acolo raza sta pe `.trow-wrap` care si decupeaza; aici randul e copil direct
     al listei, deci si-o poarta singur. Nu se bate cu separatorul: linia are
     acum marja de 12, iar curba ocupa primii 10px — nu se mai intalnesc.
     Pe telefon revine la 0 (vezi blocul de jos): acolo `overflow: hidden` ar
     decupa fata de glisare intr-un card, exact ce a scos V13. */
  .arow { position: relative; display: flex; align-items: center; gap: var(--space-12);
    min-height: var(--row-h); padding: 0 var(--space-12); background: none; border: 0;
    border-radius: var(--radius-sm);
    transition: background-color var(--dur-base) var(--ease), opacity var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
  /* SEPARATORUL ARE MARJA LATERALA, iar randul in repaus n-are colturi.
     Era `border-top` pe tot randul — linie dreapta de la un capat la altul —
     peste un rand care purta raza de control (10) si cand statea pe loc. Cele
     doua jumatati nu se potriveau: coltul rotunjit lasa un gol sub linia
     dreapta. Acum linia isi tine marja singura (pseudo-element absolut, ca sa
     nu intre ca element de flex intre bifa si titlu), iar raza apare doar cand
     randul e ridicat — tras sau glisat — si are deja umbra.
     `.sub-row` NU intra aici: subtaskurile sunt carduri prin desen.
     `z-index: 2` fiindca pe telefon fata de glisare e OPACA si sta la 1: fara
     el, linia ar fi desenata dedesubt si n-ar exista pe ecran. */
  .arow + .arow::before { content: ''; position: absolute; top: 0; z-index: 2;
    left: var(--space-12); right: var(--space-12); height: 1px; background: var(--border); }
  @media (hover: hover) {
    .arow:hover { background: var(--bg-elevated); }
  }
  /* APASAREA, IN AFARA MEDIA QUERY-ULUI. Masurat cu apasare de maus, izolata de
     hover: randul schimba ZERO pixeli cand il apesi. Pe desktop se salva prin
     hover; pe telefon nu exista nici hover, nici apasare, deci o atingere pe un
     rand nu da niciun semn pana nu se schimba datele. `--bg-active` (10%) e cu o
     treapta peste hover (6%) si e exact rolul pentru care exista in tokens.
     `transition-duration` pe starea de intrare: cu cele 220ms de baza, apasarea
     abia apuca sa apara inainte sa ridici degetul. Fond, nu `scale`: randul e cat
     pagina, iar un rand care se strange arata ca un defect de layout. */
  .arow:active { background: var(--bg-active); transition-duration: var(--dur-press); }
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
  /* Drag & drop — minimal, on-brand: the grabbed row fades; the drop target shows a
     crisp accent insertion line (no heavy fill); rows settle via animate:flip. */
  /* FARA OPACITATE PE RANDUL TRAS: identitatea lui e tocmai ce urmaresti cat il
     muti. Unde ajunge o spune deja linia de insertie de mai jos. */
  .arow.dragging { cursor: grabbing; box-shadow: var(--shadow-md); border-radius: var(--radius-sm); }
  /* LINIA DE INSERTIE STA INTRE RANDURI, nu in interiorul celui de dedesubt.
     Era `inset 0 2px 0 0` — o umbra INTERIOARA, deci 2px desenati sub muchia
     randului tinta: se citea ca o subliniere a lui, nu ca locul unde aterizeaza
     ce tragi. Acum e un pseudo-element asezat pe cusatura, cu aceeasi marja
     laterala ca separatorul pe care il inlocuieste vizual — altfel linia care
     spune „aici" ar fi mai lata decat linia care desparte.
     `top: -1px` o pune peste separator, nu sub el; `::after` fiindca `::before`
     e chiar separatorul. */
  .arow.dragover::after { content: ''; position: absolute; top: -1px; z-index: 4;
    left: var(--space-12); right: var(--space-12); height: 2px; border-radius: 1px;
    background: var(--accent); }

  /* Manerul apare la hover, ca actiunile — dar coloana lui de 16px e rezervata
     pe TOATE randurile (vezi si `.grip-loc`). `opacity`, nu `display`: daca
     aparitia lui ar imbrancit randul, hoverul ar muta titlul sub cursor. */
  .grip, .grip-loc { width: 16px; flex: none; display: flex; align-items: center;
    justify-content: center; color: var(--text-secondary); }
  .grip { cursor: grab; }
  .grip:active { cursor: grabbing; }
  @media (hover: hover) {
    .grip { opacity: 0; transition: opacity var(--dur-fast) var(--ease); }
    .arow:hover .grip, .grip:focus-visible { opacity: 1; }
  }

  /* Tragere de reordonare (lib/reordonare.js). Randul tras se ridica deasupra
     celorlalte si NU are tranzitie pe transform — altfel `.arow`-ul de mai sus i-ar
     interpola fiecare cadru si randul ar merge in urma degetului. Vecinii, dimpotriva,
     se dau la o parte cu tranzitie: acolo miscarea trebuie sa se vada ca o mutare. */
  .arow:global(.reord-tras) { z-index: 3; transition: none; box-shadow: var(--shadow-lg);
                              border-color: var(--accent); }
  /* Cat timp tragi, restul randurilor nu mai raspund la atingere: degetul e ocupat. */
  .a-list:global(.reord-activ) .arow:not(:global(.reord-tras)) { pointer-events: none; }
  .a-list:global(.reord-activ) { user-select: none; }

  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: var(--space-2xs); display: flex;
           position: relative; }
  /* Tinta de 44, desenul de 30 — aceeasi reparatie ca in `Tasks.svelte`, si
     acelasi motiv: se largeste suprafata, nu cutia, ca randul sa nu se reaseze. */
  .check::after {
    content: '';
    position: absolute;
    top: 0; bottom: 0;
    left: calc((var(--tap-min) - 30px) / -2);
    right: calc((var(--tap-min) - 30px) / -2);
  }
  .check:hover { color: var(--accent); }
  .arow.done .check { color: var(--success); }
  /* `.check-empty` traieste acum in global.css, o singura data pentru toate
     listele — inclusiv haloul de hover, care adauga in loc sa rescrie `--ring`. */

  .amain { flex: 1; min-width: 0; cursor: pointer; text-align: left; display: flex; flex-direction: column; gap: 1px; }
  /* --font-rand, nu --font-body: randul de lista ramane 15 si pe telefon. */
  /* `align-self: flex-start` — `.amain` e o COLOANA de flex, deci copiii ei se
     intind pe toata latimea. Cu titlul intins, si `text-decoration:
     line-through` din starea finala traversa tot randul, nu doar cuvantul
     (T3). Stranse la text, si taietura statica, si cea animata din `global.css`
     se opresc la ultima litera. `max-width: 100%` pastreaza trunchierea.
     Regula sta acum pe INVELISUL primei linii, nu pe titlu: titlul e copil de
     flex-rand langa contorul de pasi, unde `align-self` ar insemna aliniere pe
     verticala. Se strange la text oricum — `flex: 0 1 auto` cu baza pe continut —
     deci taietura se opreste in continuare la ultima litera. */
  .atitlu { display: flex; align-items: center; gap: var(--space-sm);
    min-width: 0; align-self: flex-start; max-width: 100%; }
  .atitle { font-size: var(--font-rand); color: var(--text); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    min-width: 0; }
  .arow.done .atitle { text-decoration: line-through; color: var(--text-dim); }
  /* A doua linie: text gri, doua bucati, nicio pastila. Erau cinci chipuri
     (termen, pasi, recurenta, proiect, categorie) — trei au urcat in coloana
     pironita sau au plecat, iar celelalte doua nu au nevoie de fundal ca sa se
     citeasca: sunt SUB titlu, deci deja subordonate prin pozitie. */
  .ainfo { display: flex; align-items: center; gap: var(--space-10); min-width: 0; overflow: hidden;
    font-size: var(--font-small); color: var(--text-dim); }
  /* `flex: 0 1 auto` + `min-width: 0`: fara ele, un copil de flex se dimensioneaza
     dupa continut si IESE din parinte in loc sa se taie — deci `text-overflow`
     n-avea pe ce sa se aplice si numele proiectului era retezat fara puncte. */
  .a-unde { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  /* `.a-pasi` a urcat pe linia titlului si se numeste `.tpasi` (global.css):
     acelasi fapt purta doua haine, una aici si niciuna in celelalte trei liste. */

  /* COLOANA DE TERMEN — aceeasi ca in /tasks, pana la pixel. */
  .atermen { flex: none; width: 46px; text-align: right;
    font-family: var(--font-mono); font-size: var(--font-label);
    color: var(--text-dim); font-variant-numeric: tabular-nums;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .atermen.sev { color: var(--danger); font-weight: var(--fw-medium); }
  /* „azi" ramane GRI (desen 3a): severitatea de „azi" o spune inelul bifei, in
     accent; textul se coloreaza doar cand e depasit. Doua canale colorate pentru
     aceeasi treapta ar face boardul — unde totul e azi sau restant — sa strige. */
  .atermen.acum { font-weight: var(--fw-medium); }

  /* Invelisul nu are geometrie proprie pe desktop: e doar ce cade pe linia a
     doua PE TELEFON, intreg. Fara `display: contents` aici, cele doua lucruri
     dinauntru (manerul de deget si actiunile) se stiveau pe verticala, iar
     randul crestea la ~50px cu un maner care oricum nu se foloseste cu mouse-ul.
     Regula exista deja in blocul de telefon; lipsea de la desktop. */
  .arow-tools { display: contents; }
  /* Manerul de DEGET (lib/reordonare.js) e al telefonului. Pe desktop se
     reordoneaza din `.grip`, cu drag nativ. */
  .gl-maner { display: none; }
  /* ACTIUNILE SE STING CAND CURSORUL NU E PE RAND (A1, raportat de Ion).
     Statele permanent, deci fiecare rand purta trei butoane si lista se citea ca
     un panou de comenzi, nu ca o lista. Manerul de alaturi avea deja regula;
     actiunile n-o primisera niciodata. Reteta e copiata din `Tasks.svelte`
     (`.task-actions`), ca cele doua liste sa raspunda identic la acelasi gest.
     `opacity`, NU `display`: coloana ramane rezervata, altfel aparitia lor ar
     imbrancit titlul chiar sub cursor. `pointer-events` merge cu ea — un buton
     invizibil dar apasabil e mai rau decat unul vizibil.
     `focus-within` pe ACTIUNI, nu pe rand: la tastatura conteaza sa se vada ce
     ai focalizat, nu sa se aprinda randul cand ajungi pe titlu. */
  .arow-actions { display: flex; align-items: center; gap: var(--space-6); flex-shrink: 0; }
  /* Intra 8px spre interior, pe 220 (contract miscare) — ca in /tasks. */
  @media (hover: hover) {
    .arow-actions { opacity: 0; pointer-events: none; transform: translateX(8px);
      transition: opacity var(--dur-base) var(--ease), transform var(--dur-base) var(--ease); }
    .arow:hover .arow-actions,
    .arow-actions:focus-within { opacity: 1; pointer-events: auto; transform: none; }
  }
  .abtn, .row-date :global(.dp-trigger) {
    display: inline-flex; align-items: center; gap: var(--space-6); height: var(--ctrl-sm); padding: 0 11px;
    border-radius: var(--radius-xs); background: var(--bg-surface); box-shadow: var(--shadow-sm);
    border: none; color: var(--text-secondary); font-family: inherit;
    font-size: var(--font-control); font-weight: var(--fw-semibold);
    white-space: nowrap; cursor: pointer; transition: var(--transition-pressable); }
  .abtn:hover:not(:disabled), .row-date :global(.dp-trigger:hover) { background: var(--bg-hover); color: var(--text); }
  .abtn:active { transform: scale(var(--press-scale)); }
  .abtn.danger:hover:not(:disabled) { background: var(--danger-subtle); color: var(--danger-deep); }
  .row-date { flex-shrink: 0; }
  .row-date :global(.dp) { width: auto; }
  .row-date :global(.dp-trigger) { min-height: 0; flex-direction: row-reverse; }

  /* ===== glisare (doar telefon) ===== */
  .gl-fata { display: contents; }

  /* Invelisul calendarului de gest chiar trebuie sa fie 0×0, cum promite
     comentariul din markup: fara regula asta, DatePicker-ul isi randa
     declansatorul „Selectează data" pe toata latimea, sub board. Sheet-ul lui
     iese in body prin use:portal, deci decuparea nu-l atinge. */

  @media (max-width: 768px) {
    /* UN RAND = O LINIE, ca in orice aplicatie de to-do de pe telefon.
       Inainte: titlu pe o linie + sase butoane de 44px pe a doua = 127px pe task,
       adica sase taskuri pe ecran si un perete de iconite. Acum randul are ~56px
       si NICIUN buton la vedere in afara de bifa: actiunile vin din gest.
         glisare spre stanga  -> Mâine / Dată / Scoate
         glisare spre dreapta -> bifeaza
         atingere pe titlu    -> deschide taskul
       Reordonarea (sagetile) ramane, dar numai cat timp ai ceva de reordonat —
       vezi `.arow-arrows` mai jos. */
    /* `border-radius: 0` INAPOI pe telefon: aici randul decupeaza (`overflow:
       hidden`) fata de glisare, deci raza de pe desktop i-ar rotunji colturile
       in repaus — adica exact cardul pe care V13 l-a scos. Pe telefon obiectul
       vizibil e `.gl-fata`, si ea isi ia raza doar pe gest. */
    .arow { flex-wrap: nowrap; row-gap: 0; min-height: var(--row-h-mobile);
            padding: 0; overflow: hidden; position: relative; touch-action: pan-y;
            border-radius: 0; }
    /* Fondul e al SUPRAFETEI, nu al unui panou propriu: randul nu mai e un card.
       Trebuie totusi OPAC — pista de bifare sta dedesubt si se descopera pe
       masura ce tragi. In repaus fata e DREAPTA (vezi separatorul de mai sus):
       raza vine pe gest, unde randul e ridicat si are deja umbra. */
    /* Desenul 3c: gap 12, padding lateral 10 — separatorul de mai jos coboara
       si el la 10, ca linia sa se termine exact unde incepe textul. */
    .gl-fata { display: flex; align-items: center; gap: var(--space-12); width: 100%;
               min-height: var(--row-h-mobile); padding: 0 var(--space-10);
               background: var(--bg-surface);
               border-radius: 0; position: relative; z-index: 1;
             }
    /* FARA `will-change` PERMANENT. Il tinea fiecare rand din lista, deci pe 40 de
       taskuri erau 40 de straturi de compozitare pastrate tot timpul, si cand nu
       atingeai nimic. Regula casei o scrie chiar proiectul, in `lib/tragereTimeline.js`:
       `will-change` DOAR cat tine gestul. Il pune si il scoate `lib/glisare.js`. */
    .arow + .arow::before { left: 10px; right: 10px; }
    /* `:global(...)` pe clasa pusa din JS, NU pe intreg selectorul.
       Svelte NU se multumeste sa avertizeze „Unused CSS selector": TAIE regula din
       build. Iar `gl-tras`/`gl-bifa` sunt puse la RULARE de `lib/glisare.js`, deci
       nu apar in markup si compilatorul le crede moarte. Efectul, verificat in CSS-ul
       livrat: din toate regulile de gest ale aplicatiei supravietuise UNA. Adica
       glisai spre dreapta si nu vedeai verdele care spune „ai trecut pragul" —
       exact semnalul fara de care gestul e o loterie.
       Ancora (`.arow`/`.trow`/`.mrow`) ramane scoped, deci regula nu scapa in alte
       componente. */
    .arow:global(.gl-tras) .gl-fata { box-shadow: var(--shadow-glisare);
                                      border-radius: var(--radius-sm); }


    /* Cursa de bifare: cat timp tragi spre dreapta destul, dedesubt se vede verde.
       Fara semnal, gestul e o loterie — nu stii cand ai trecut pragul. */
    .arow:global(.gl-bifa) { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }

    .bh-add-txt { display: none; }
    /* Cu degetul se apuca `.gl-maner`; `.grip` are drag nativ, care pe touch nu
       se declanseaza niciodata. Acelasi slot, celalalt maner. */
    .grip { display: none; }
    .gl-maner { display: flex; }
    /* Compozitorul e desenat la 48 (`Acasă.dc.html` 3c): e panoul de scris al
       boardului, stă jos, si se atinge cu degetul mare intins — de aceea
       `--tap-sheet`, nu podeaua de 44 a tintelor obisnuite. Inaltimea o tine
       acum invelisul, fiindca el e cutia; inputul se intinde in ea. */
    .qa-camp { min-height: var(--tap-sheet); }
    /* Pe telefon adaugarea vine din butonul de actiune al DOCULUI (`.dock-fab`), proeminent
       si peste dock — deci butonul mic din capul boardului nu mai are rost aici. */
    .bh-add { display: none; }

    /* Indexul pleaca: pe un rand de o linie, doua cifre in fata titlului nu spun
       nimic ce nu spune deja ordinea de sus in jos, si mananca 28px din titlu. */
    .amain { flex: 1 1 0; min-width: 0; padding: 0; gap: 1px; min-height: var(--tap-min); justify-content: center; }
    .atitle { white-space: nowrap; }
    /* Meta pe un singur rand. Taierea seaca lasa jumatate de litera la margine:
       „termen 28 iul" se oprea dupa `te`, si doua caractere orfane se citesc ca o
       pagina stricata, nu ca un text care continua. Doua schimbari:
       - numele proiectului se strange la 96px, cat sa incapa si termenul (chipul
         are deja `text-overflow: ellipsis`, deci se taie CU semn);
       - ce tot nu incape se stinge intr-un degrade, nu se reteaza.
       Ordinea ramane proiect -> stare -> termen: proiectul e cel dupa care alegi
       randul, iar cand chiar e restant o spune deja pastila rosie. */
    .ainfo { flex-wrap: nowrap; overflow: hidden;
             mask-image: linear-gradient(to right, #000 calc(100% - 18px), transparent);
             -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 18px), transparent); }
    .ainfo > * { flex-shrink: 0; }
    /* Ca in /tasks pe telefon: contextul devine TEXT, nu pastila — pe un rand
       ingust pastila era cel mai tare lucru dupa titlu, adica invers decat
       conteaza. (Acolo regula exista deja; aici ramasese pastila.) */

    /* Din cele sase butoane raman doua la vedere: bifa (actiunea principala) si
       reordonarea. Restul stau in panoul de sub rand. */
    .arow-tools { display: contents; }
    .arow-actions { display: none; }
    .abtn { width: var(--ctrl-sm); height: var(--ctrl-sm); }

    /* MANER, NU SAGETI.
       Aici erau doua sageti de 40×22 pe fiecare rand — 76 de tinte sub prag pe
       un ecran, si doua iconite in plus pe o lista adusa tocmai la o singura
       linie. Acum e o singura suprafata de 44px de care tragi randul, ca in
       aplicatiile native.
       `touch-action: none` DOAR aici: pe restul randului derularea verticala si
       glisarea laterala raman ale browserului si ale lui `glisare.js`. Daca ar
       sta pe rand, lista n-ar mai putea fi derulata cu degetul. */
    /* 16px de LATIME (slotul rezervat), dar 44px de ATINS: suprafata revine
       dintr-un strat invizibil care se intinde in padding-ul randului. Aceeasi
       solutie ca la bifa de langa — o tinta de deget nu trebuie sa fie si o
       coloana de layout. */
    .gl-maner { display: flex; align-items: center; justify-content: center;
                position: relative; width: 16px; height: var(--tap-min); flex: none;
                color: var(--text-secondary);
                touch-action: none; cursor: grab; }
    .gl-maner::after { content: ''; position: absolute; inset: 0 -14px; }
    .gl-maner:active { cursor: grabbing; }
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
  }
</style>
