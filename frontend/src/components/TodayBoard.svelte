<script>
  import { onMount } from 'svelte'
  import { flip } from 'svelte/animate'
  import { CalendarCheck, Plus, GripVertical, ArrowRight, X, CheckCircle2, ListPlus, Check, CalendarDays, User } from '@lucide/svelte'
  import {
    agenda, loadAgendaToday, quickAddToday, moveToTomorrow, moveToDate,
    removeFromToday, toggleDone, reorderAgenda
  } from '../stores/agenda.svelte.js'
  import { dueRing, formatDate, esteDepasit as isOverdue, esteAzi as isToday } from '../lib/formatters.js'
  import { etichetaTermenScurt } from '../lib/grupare.js'
  import { glisare, inchideGlisarea } from '../lib/glisare.js'
  import { reordonare } from '../lib/reordonare.js'
  import { ecran } from '../lib/ecran.svelte.js'
  import { navigate } from '../lib/router.svelte.js'
  import { morphNavigate } from '../lib/focus.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import TaskPickerModal from './TaskPickerModal.svelte'
  import EmptyState from './ui/EmptyState.svelte'
  import ErrorState from './ui/ErrorState.svelte'
  import Skeleton from './ui/Skeleton.svelte'
  import DatePicker from './ui/DatePicker.svelte'
  import { motionDuration, DUR_BASE, plecare, sosire } from '../lib/motion.svelte.js'

  // Home paseaza un callback ca sa-si reincarce KPI-urile + cardul "urgente"/
  // "deadline-uri" dupa ce bifez / mut / scot un task (altfel ramaneau stale
  // pana la refresh sau schimbare de tab).
  let { onchange = () => {} } = $props()

  let quickTitle = $state('')
  let quickAdding = $state(false)
  let showPicker = $state(false)

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
   *  „când" nu e o zi, e un ritm. */
  function termenScurt(it) {
    if (it.recurenta && !it.data_scadenta) return it.recurenta
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

  async function onToggle(it) {
    const eraFacut = it.status === 'done'
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

  async function onTomorrow(it) {
    try { await moveToTomorrow(it.tip, it.id); toast('Mutat pe mâine', 'success'); onchange() }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function onRemove(it) {
    try { await removeFromToday(it.tip, it.id); onchange() }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  // GESTUL DUCE LA ALEGEREA ZILEI, NU LA O ZI ALEASA DE APLICATIE.
  // Stanga executa „Mâine" — pe boardul de azi mâine parea verbul potrivit,
  // fiindca tot ce vezi e scadent azi. Dar amanarea nu e „inca o zi": muti un
  // task cand stii CAND il faci, iar ziua aia e rareori mâine. Acum gestul
  // deschide acelasi calendar ca butonul „Planifică" de pe desktop si ca foaia
  // din /tasks — un singur raspuns la aceeasi intrebare, pe toate suprafetele.
  //
  // Calendarul e UNUL PE BOARD, nu unul pe rand: pe telefon `.arow-actions` nu se
  // randeaza, deci nu exista declansator de apasat. Instanta traieste intr-un
  // invelis de 0×0 (`.dp-gest`), iar sheet-ul ei se muta oricum in `body`
  // (`use:portal`), deci nu are ce sa taie invelisul.
  let dpGest = $state(null)
  let tintaGest = $state(null)
  function planificaDinGest(it) {
    tintaGest = it
    dpGest?.deschideCalendarul()
  }

  // Reschedule via the shared DatePicker (inline, same calendar as global/project
  // tasks). Picking a day moves the task; clearing ("Sterge") removes it from today.
  async function onMoveDate(it, v) {
    try {
      if (v) { await moveToDate(it.tip, it.id, v); toast(`Mutat pe ${formatDate(v)}`, 'success') }
      else { await removeFromToday(it.tip, it.id) }
      onchange()
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
        <span class="bh-restante"><span class="bh-punct"></span>{restanteCount} restante</span>
      {/if}
    </div>
    <button class="bh-add" onclick={() => showPicker = true}>
      <ListPlus size={14} /> <span class="bh-add-txt">Adaugă task existent</span>
    </button>
  </div>

  <form class="quick-add" onsubmit={(e) => { e.preventDefault(); doQuickAdd() }}>
    <!-- Pe telefon indicatia despre Enter se taia la jumatate („...Enter pe") si
         oricum nu spune nimic acolo: tastatura are butonul ei si langa camp e
         butonul „+". Ramane doar ce se citeste intreg. -->
    <input type="text" placeholder={peTelefon ? 'Task rapid pentru azi…' : 'Task rapid pentru azi... Enter pentru a adăuga'} bind:value={quickTitle} disabled={quickAdding} />
    <button type="submit" class="quick-add-btn" disabled={!quickTitle.trim() || quickAdding} title="Adaugă task"><Plus size={16} /></button>
  </form>

  {#if agenda.loading && agenda.items.length === 0}
    <Skeleton varianta="rand" randuri={4} />
  {:else if agenda.error}
    <!-- ErrorState cu retry, ca in restul aplicatiei (regula de design: „erori:
         <ErrorState> (cu retry)"). Aici era un paragraf rosu fara niciun drum
         inainte — singura lista din aplicatie care la esec te lasa sa dai
         refresh din browser. -->
    <ErrorState message={agenda.error} onretry={() => loadAgendaToday()} />
  {:else if agenda.items.length === 0}
    <EmptyState icon={CalendarCheck} title="Nimic planificat azi" description="Adaugă un task rapid sau alege din taskurile existente." />
  {:else}
    <div class="a-list" role="list"
         use:reordonare={{ activ: peTelefon, selectorRand: '.arow', selectorManer: '.gl-maner', onMutare: commitMove }}>
      {#each agenda.items as it, i (it.tip + ':' + it.id)}
        <div
          class="arow"
          class:done={it.status === 'done'}
          class:dragover={overIndex === i}
          class:dragging={dragIndex === i}
          style="--ring: {dueRing(it.data_scadenta)}"
          role="listitem"
          ondragover={(e) => onDragOver(e, i)}
          ondrop={(e) => onDrop(e, i)}
          animate:flip={{ duration: flipDur }}
          in:sosire|local
          out:plecare
          use:glisare={{ activ: peTelefon, onBifa: it.status === 'done' ? null : () => onToggle(it), onAmana: () => planificaDinGest(it) }}
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
          <span class="grip" role="button" tabindex="-1" aria-label="Trage pentru a reordona" draggable="true" ondragstart={(e) => onDragStart(e, i)} ondragend={onDragEnd} title="Trage pentru a reordona"><GripVertical size={15} /></span>
          <span class="gl-maner" aria-hidden="true"><GripVertical size={17} /></span>

          <button class="check" onclick={() => onToggle(it)} title="Marchează ca făcut">
            {#if it.status === 'done'}<CheckCircle2 size={18} />{:else}<span class="check-empty"></span>{/if}
          </button>

          <button class="amain" onclick={(e) => openItem(e, it)}>
            <span class="atitle">{it.titlu}</span>
            <!-- A DOUA LINIE, doar cand are ce spune: unde e taskul (proiectul
                 sau categoria) si cat s-a facut din el. Erau cinci chipuri pe un
                 rand — termen, pasi, recurenta, proiect, categorie — dintre care
                 termenul si recurenta au urcat in coloana pironita din dreapta,
                 iar restul erau pastile colorate mai tari decat titlul.
                 Aici raman ca TEXT, la 13px, gri: se citesc cand le cauti. -->
            {#if contextRand(it)}
              <span class="ainfo">
                {#if contextRand(it)}<span class="a-unde">{contextRand(it)}</span>{/if}
                {#if it.subtask_total}<span class="a-pasi">{it.subtask_done || 0}/{it.subtask_total}</span>{/if}
              </span>
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
       pe azi nu are voie sa fie invizibil). Antetul e micro/mono cu un punct
       violet — acelasi punct de pe chip-ul „Personal" din /tasks, ca cele doua
       suprafete sa se refere una la alta. NU foloseste .grup-cap/.grup-t (clase
       citite de audit_mobil pe /tasks) si nici <h2> pereche cu „Astăzi".
       Randurile sunt ACELEASI .arow (severitatea = singura culoare), fara insa
       index, grip si reordonare: lista e scurta, ordinea o da serverul
       (restante-first, apoi alfabetic). -->
  {#if agenda.personale.length}
    <div class="pers-cap"><span class="pers-ico" aria-hidden="true"><User size={12} /></span>Personal<span class="pers-n">{agenda.personale.length}</span></div>
    <div class="a-list" role="list">
      {#each agenda.personale as it (it.id)}
        <div
          class="arow"
          class:done={it.status === 'done'}
          style="--ring: {dueRing(it.data_scadenta)}"
          role="listitem"
          in:sosire|local
          out:plecare
          use:glisare={{ activ: peTelefon, onBifa: it.status === 'done' ? null : () => onToggle(it), onAmana: () => planificaDinGest(it) }}
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

          <button class="amain" onclick={(e) => openItem(e, it)}>
            <span class="atitle">{it.titlu}</span>
            {#if it.subtask_total}
              <span class="ainfo"><span class="a-pasi">{it.subtask_done || 0}/{it.subtask_total}</span></span>
            {/if}
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

<TaskPickerModal bind:open={showPicker} />

<!-- Calendarul pe care il deschide glisarea spre stanga. Nu se vede niciodata ca
     declansator (invelis de 0×0): pe telefon randul nu are `.arow-actions`, deci
     n-are unde sta un buton. Sheet-ul lui iese in `body` prin `use:portal`, asa
     ca invelisul strans nu-l taie. -->
{#if peTelefon}
  <span class="dp-gest" aria-hidden="true">
    <DatePicker bind:this={dpGest} value={tintaGest?.data_scadenta || ''}
                onchange={(v) => { if (tintaGest) onMoveDate(tintaGest, v) }} />
  </span>
{/if}

<style>
  /* Suprafata se desprinde prin umbra. Padding-ul lateral scade la 8, fiindca
     randul isi aduce propriii 12 — separatorul iese la 20 de la marginea
     cardului, adica marja laterala ceruta, fara s-o scrie nimeni a doua oara. */
  .board { background: var(--bg-surface); border: 0; border-radius: var(--radius-md);
    box-shadow: var(--shadow-md); padding: var(--space-20) var(--space-sm) 6px;
    margin-bottom: var(--space-lg); }

  .board-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-12); margin: 0 var(--space-sm) var(--space-md); }
  /* Alinierea e pe LINIA DE BAZA, nu pe centru: „Astăzi" e la 25px si ziua la
     13, deci centrate ar pluti una fata de alta. Pe baza, se citesc ca o
     propozitie. */
  .bh-left { display: flex; align-items: baseline; gap: var(--space-12); color: var(--text); min-width: 0; }
  .bh-left h2 { font-size: var(--font-title); font-weight: var(--fw-semibold);
                letter-spacing: -0.015em; }
  .bh-zi { font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-dim);
           white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .bh-restante { display: inline-flex; align-items: center; gap: 6px; flex: none;
    font-size: var(--font-small); font-weight: var(--fw-semibold);
    color: var(--danger); white-space: nowrap; }
  .bh-punct { width: 7px; height: 7px; border-radius: 50%; background: var(--danger); }
  /* `.bh-count` / `.bh-restante` au plecat: sunt `.count` si `.count danger` din
     global.css — aceeasi pastila ca peste tot (vezi comentariul de acolo). */
  .bh-add { display: inline-flex; align-items: center; gap: 7px; height: 34px; padding: 0 14px; font-size: var(--font-body); font-weight: var(--fw-semibold); border-radius: var(--radius-sm); background: var(--bg-elevated); border: none; color: var(--text-secondary); cursor: pointer; transition: var(--transition-pressable); flex-shrink: 0; }
  .bh-add:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }

  .quick-add { display: flex; gap: var(--space-sm); margin: 0 var(--space-sm) 18px; }
  .quick-add input { flex: 1; min-height: 44px; padding: 0 14px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); font-size: var(--font-body); }
  .quick-add input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .a-skel { display: flex; flex-direction: column; gap: var(--space-xs); }

  /* Antetul sectiunii personale: micro/mono/uppercase ca .cell-label, cu punctul
     violet (--purple — huea „libera"; amber e severitate/identitate). Bordura de
     sus il desparte de board fara sa-l ridice la rang de al doilea board. */
  .pers-cap { display: flex; align-items: center; gap: 6px; margin-top: var(--space-md); margin-bottom: var(--space-sm); padding-top: var(--space-md); border-top: 1px solid var(--border); font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-faint); }
  /* Semn, nu bulina — acelasi desen ca pe comutatorul de sfera din /tasks, ca cele
     doua suprafete sa se refere in continuare una la alta fara sa aduca o a treia
     culoare pe ecran. */
  .pers-ico { display: inline-flex; align-items: center; color: var(--text-faint); flex-shrink: 0; }
  .pers-n { color: var(--text-dim); font-variant-numeric: tabular-nums; }

  .a-list { display: flex; flex-direction: column; }
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
  .arow { position: relative; display: flex; align-items: center; gap: var(--space-12);
    min-height: 46px; padding: 0 var(--space-12); background: none; border: 0;
    border-radius: var(--radius-sm);
    transition: background-color var(--dur-fast) var(--ease), opacity var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
  .arow + .arow { border-top: 1px solid var(--border); }
  @media (hover: hover) {
    .arow:hover { background: var(--bg-elevated); }
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
  /* Drag & drop — minimal, on-brand: the grabbed row fades; the drop target shows a
     crisp accent insertion line (no heavy fill); rows settle via animate:flip. */
  .arow.dragging { opacity: 0.45; cursor: grabbing; }
  .arow.dragover { box-shadow: inset 0 2px 0 0 var(--accent); }
  @media (prefers-reduced-motion: reduce) {
    .arow { transition: none; }
  }

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

  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; display: flex; }
  .check:hover { color: var(--accent); }
  .arow.done .check { color: var(--success); }
  /* `.check-empty` traieste acum in global.css, o singura data pentru toate
     listele — inclusiv haloul de hover, care adauga in loc sa rescrie `--ring`. */

  .amain { flex: 1; min-width: 0; cursor: pointer; text-align: left; display: flex; flex-direction: column; gap: 2px; }
  .atitle { font-size: var(--font-body); color: var(--text); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .arow.done .atitle { text-decoration: line-through; color: var(--text-dim); }
  /* A doua linie: text gri, doua bucati, nicio pastila. Erau cinci chipuri
     (termen, pasi, recurenta, proiect, categorie) — trei au urcat in coloana
     pironita sau au plecat, iar celelalte doua nu au nevoie de fundal ca sa se
     citeasca: sunt SUB titlu, deci deja subordonate prin pozitie. */
  .ainfo { display: flex; align-items: center; gap: 10px; min-width: 0; overflow: hidden;
    font-size: var(--font-small); color: var(--text-dim); }
  /* `flex: 0 1 auto` + `min-width: 0`: fara ele, un copil de flex se dimensioneaza
     dupa continut si IESE din parinte in loc sa se taie — deci `text-overflow`
     n-avea pe ce sa se aplice si numele proiectului era retezat fara puncte. */
  .a-unde { flex: 0 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .a-pasi { font-family: var(--font-mono); flex: none; font-variant-numeric: tabular-nums; }

  /* COLOANA DE TERMEN — aceeasi ca in /tasks, pana la pixel. */
  .atermen { flex: none; width: 46px; text-align: right;
    font-family: var(--font-mono); font-size: var(--font-label);
    color: var(--text-dim); font-variant-numeric: tabular-nums;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .atermen.sev { color: var(--danger); font-weight: var(--fw-medium); }
  .atermen.acum { color: var(--accent-deep); font-weight: var(--fw-medium); }

  /* Invelisul nu are geometrie proprie pe desktop: e doar ce cade pe linia a
     doua PE TELEFON, intreg. Fara `display: contents` aici, cele doua lucruri
     dinauntru (manerul de deget si actiunile) se stiveau pe verticala, iar
     randul crestea la ~50px cu un maner care oricum nu se foloseste cu mouse-ul.
     Regula exista deja in blocul de telefon; lipsea de la desktop. */
  .arow-tools { display: contents; }
  /* Manerul de DEGET (lib/reordonare.js) e al telefonului. Pe desktop se
     reordoneaza din `.grip`, cu drag nativ. */
  .gl-maner { display: none; }
  .arow-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
  .abtn, .row-date :global(.dp-trigger) {
    display: inline-flex; align-items: center; gap: 6px; height: 32px; padding: 0 11px;
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
    .arow { flex-wrap: nowrap; row-gap: 0; min-height: var(--row-h-mobile);
            padding: 0; overflow: hidden; position: relative; touch-action: pan-y; }
    /* Fondul e al SUPRAFETEI, nu al unui panou propriu: randul nu mai e un card.
       Trebuie totusi OPAC — pista de bifare sta dedesubt si se descopera pe
       masura ce tragi. */
    .gl-fata { display: flex; align-items: center; gap: 10px; width: 100%;
               min-height: var(--row-h-mobile); padding: 0 var(--space-12);
               background: var(--bg-surface);
               border-radius: var(--radius-sm); position: relative; z-index: 1;
               will-change: transform; }
    /* `:global(...)` pe clasa pusa din JS, NU pe intreg selectorul.
       Svelte NU se multumeste sa avertizeze „Unused CSS selector": TAIE regula din
       build. Iar `gl-tras`/`gl-bifa` sunt puse la RULARE de `lib/glisare.js`, deci
       nu apar in markup si compilatorul le crede moarte. Efectul, verificat in CSS-ul
       livrat: din toate regulile de gest ale aplicatiei supravietuise UNA. Adica
       glisai spre dreapta si nu vedeai verdele care spune „ai trecut pragul" —
       exact semnalul fara de care gestul e o loterie.
       Ancora (`.arow`/`.trow`/`.mrow`) ramane scoped, deci regula nu scapa in alte
       componente. */
    .arow:global(.gl-tras) .gl-fata { box-shadow: -6px 0 12px -8px rgba(0,0,0,0.55); }


    /* Cursa de bifare: cat timp tragi spre dreapta destul, dedesubt se vede verde.
       Fara semnal, gestul e o loterie — nu stii cand ai trecut pragul. */
    .arow:global(.gl-bifa) { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }

    .bh-add-txt { display: none; }
    /* Cu degetul se apuca `.gl-maner`; `.grip` are drag nativ, care pe touch nu
       se declanseaza niciodata. Acelasi slot, celalalt maner. */
    .grip { display: none; }
    .gl-maner { display: flex; }
    .quick-add input, .quick-add-btn { min-height: var(--tap-min); }
    .quick-add-btn { width: var(--tap-min); }
    /* „Adaugă task existent" ramane doar iconita pe telefon — deci iconita trebuie
       sa aiba caseta unui buton, nu 40×28. */
    .bh-add { min-width: var(--tap-min); min-height: var(--tap-min); justify-content: center; padding: 0 10px; }

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
    .abtn { width: 34px; height: 34px; }

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
