<script>
  import { onMount } from 'svelte'
  import { flip } from 'svelte/animate'
  import { CalendarCheck, Plus, GripVertical, ArrowRight, X, ChevronRight, CheckCircle2, Repeat, ListPlus, Check, CalendarDays, ListChecks } from '@lucide/svelte'
  import {
    agenda, loadAgendaToday, quickAddToday, moveToTomorrow, moveToDate,
    removeFromToday, toggleDone, reorderAgenda
  } from '../stores/agenda.svelte.js'
  import { dueColor, formatDate, esteDepasit as isOverdue, esteCurand as isSoon } from '../lib/formatters.js'
  import { etichetaTermen } from '../lib/grupare.js'
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

  // isOverdue/isSoon vin din formatters.js — aceeasi axa si aceleasi praguri ca
  // dueColor(), o singura definitie pentru toate listele.

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
    return () => inchideGlisarea()
  })
</script>

<section class="board cell-in">
  <div class="board-head">
    <div class="bh-left">
      <CalendarCheck size={17} />
      <h2>Astăzi</h2>
      <span class="bh-count">{agenda.items.length}</span>
      {#if restanteCount > 0}<span class="bh-restante">{restanteCount} restante</span>{/if}
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
    <div class="a-skel">{#each Array(3) as _}<Skeleton height="40px" />{/each}</div>
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
          style="--sev: {dueColor(it.data_scadenta)}"
          role="listitem"
          ondragover={(e) => onDragOver(e, i)}
          ondrop={(e) => onDrop(e, i)}
          animate:flip={{ duration: flipDur }}
          in:sosire|local
          out:plecare
          use:glisare={{ latime: peTelefon ? 176 : 0, activ: peTelefon, onBifa: it.status === 'done' ? null : () => onToggle(it) }}
        >
          <!-- Panoul de actiuni sta SUB rand si se descopera glisand spre stanga
               (vezi lib/glisare.js). Pe desktop e ascuns: acolo actiunile stau la
               vedere in rand, unde le ajunge cursorul. -->
          <div class="gl-pista" aria-hidden="true"><span class="gl-ico"><Check size={17} strokeWidth={3} /></span><span class="gl-et">Făcut</span></div>
          <div class="gl-actiuni" aria-hidden={!peTelefon}>
            <button class="glb" onclick={() => onTomorrow(it)} title="Mută pe mâine"><ArrowRight size={17} /><span>Mâine</span></button>
            <span class="glb datewrap" title="Planifică pe altă zi">
              <DatePicker value={it.data_scadenta} placeholder="Dată" onchange={(v) => onMoveDate(it, v)} />
              <span>Dată</span>
            </span>
            <button class="glb danger" onclick={() => onRemove(it)} title="Scoate termenul — taskul se întoarce în „fără termen”"><X size={17} /><span>Scoate</span></button>
          </div>

          <div class="gl-fata">
          <span class="tix">{String(i + 1).padStart(2, '0')}</span>
          <span class="grip" role="button" tabindex="-1" aria-label="Trage pentru a reordona" draggable="true" ondragstart={(e) => onDragStart(e, i)} ondragend={onDragEnd} title="Trage pentru a reordona"><GripVertical size={15} /></span>

          <button class="check" onclick={() => onToggle(it)} title="Marchează ca făcut">
            {#if it.status === 'done'}<CheckCircle2 size={18} />{:else}<span class="check-empty"></span>{/if}
          </button>

          <button class="amain" onclick={(e) => openItem(e, it)}>
            <span class="atitle">{it.titlu}</span>
            <span class="ainfo">
              <!-- ACEEASI ORDINE CA IN /tasks (si ca la Todoist): intai CAND,
                   apoi CAT, iar proiectul/categoria la capatul din dreapta. Un
                   task trebuie sa arate la fel oriunde apare — altfel inveti
                   pagina, nu taskul. -->
              <!-- UN SINGUR SEMN PENTRU TERMEN, nu trei.
                   Aici erau doua pastile („Restant" rosu, „Termen azi" amber) SI
                   data, colorata tot dupa severitate. Pe un board unde totul e
                   scadent azi sau restant, pastilele partitioneaza lista si atat:
                   „Termen azi" e pur si simplu starea implicita a boardului, iar
                   „Restant" spunea in cuvinte exact ce spunea deja data rosie de
                   langa el. Doua lucruri rosii cu acelasi inteles, pe fiecare rand.
                   Ramane data, scrisa relativ: „azi", „ieri", „acum 3 zile" — spune
                   si CE stare, si CAT de departe, intr-un singur chip.
                   Numarul din antet („28 restante") ramane: acolo e un rezumat,
                   nu o repetitie. -->
              {#if it.data_scadenta}<span class="deadline" class:overdue={isOverdue(it.data_scadenta)} class:soon={isSoon(it.data_scadenta)}><CalendarDays size={11} />{etichetaTermen(it.data_scadenta)}</span>{/if}
              {#if it.subtask_total}
                <span class="tsub-chip" class:gata={it.subtask_done === it.subtask_total}
                      title="{it.subtask_done || 0} din {it.subtask_total} subtaskuri făcute">
                  <ListChecks size={11} />{it.subtask_done || 0}/{it.subtask_total}
                </span>
              {/if}
              {#if it.recurenta}<span class="recur" title="Recurent: {it.recurenta}"><Repeat size={10} /> {it.recurenta}</span>{/if}
              {#if it.tip === 'proiect' && it.proiect_nume}<span class="tag proj">{it.proiect_nume}</span>
              {:else if it.categorie}<span class="tag">{it.categorie}</span>{/if}
            </span>
          </button>

          <!-- Un singur invelis pentru cele doua grupuri de actiuni. Pe desktop e
               `display: contents`, deci nu schimba nimic; pe telefon e ce cade pe
               linia a doua, INTREG. Fara el, wrap-ul de flex decidea singur unde se
               rupe randul si iesea pe trei linii (bifa singura sus, titlu, actiuni)
               = 172px pe task, adica patru taskuri pe ecran. -->
          <div class="arow-tools">
          <!-- Manerul de tragere, doar pe telefon (vezi lib/reordonare.js). Nu e
               un <button>: nu face nimic la atingere scurta, e o suprafata de
               apucat. `aria-hidden` fiindca reordonarea are si un drum accesibil
               pe desktop (grip + drag), iar aici n-avem ce anunta. -->
          <span class="gl-maner" aria-hidden="true"><GripVertical size={17} /></span>

          <div class="arow-actions">
            <button class="abtn" onclick={() => onTomorrow(it)} title="Mută pe mâine"><ArrowRight size={15} /></button>
            <span class="row-date" title="Planifică pe altă zi">
              <DatePicker value={it.data_scadenta} placeholder="Planifică" onchange={(v) => onMoveDate(it, v)} />
            </span>
            <button class="abtn danger" onclick={() => onRemove(it)} title="Scoate termenul — taskul se întoarce în „fără termen”"><X size={15} /></button>
            <!-- Pe telefon lipseste: titlul randului deschide deja taskul, iar un
                 al saselea buton de 44px ar imbatrani randul cu inca un rand. -->
            <button class="abtn deschide" onclick={(e) => openItem(e, it)} title="Deschide"><ChevronRight size={15} /></button>
          </div>
          </div>
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
    <div class="pers-cap"><span class="pers-dot" aria-hidden="true"></span>Personal<span class="pers-n">{agenda.personale.length}</span></div>
    <div class="a-list" role="list">
      {#each agenda.personale as it (it.id)}
        <div
          class="arow"
          class:done={it.status === 'done'}
          style="--sev: {dueColor(it.data_scadenta)}"
          role="listitem"
          in:sosire|local
          out:plecare
          use:glisare={{ latime: peTelefon ? 176 : 0, activ: peTelefon, onBifa: it.status === 'done' ? null : () => onToggle(it) }}
        >
          <div class="gl-pista" aria-hidden="true"><span class="gl-ico"><Check size={17} strokeWidth={3} /></span><span class="gl-et">Făcut</span></div>
          <div class="gl-actiuni" aria-hidden={!peTelefon}>
            <button class="glb" onclick={() => onTomorrow(it)} title="Mută pe mâine"><ArrowRight size={17} /><span>Mâine</span></button>
            <span class="glb datewrap" title="Planifică pe altă zi">
              <DatePicker value={it.data_scadenta} placeholder="Dată" onchange={(v) => onMoveDate(it, v)} />
              <span>Dată</span>
            </span>
            <button class="glb danger" onclick={() => onRemove(it)} title="Scoate termenul — taskul se întoarce în „fără termen”"><X size={17} /><span>Scoate</span></button>
          </div>

          <div class="gl-fata">
          <button class="check" onclick={() => onToggle(it)} title="Marchează ca făcut">
            {#if it.status === 'done'}<CheckCircle2 size={18} />{:else}<span class="check-empty"></span>{/if}
          </button>

          <button class="amain" onclick={(e) => openItem(e, it)}>
            <span class="atitle">{it.titlu}</span>
            <span class="ainfo">
              {#if it.data_scadenta}<span class="deadline" class:overdue={isOverdue(it.data_scadenta)} class:soon={isSoon(it.data_scadenta)}><CalendarDays size={11} />{etichetaTermen(it.data_scadenta)}</span>{/if}
              {#if it.subtask_total}
                <span class="tsub-chip" class:gata={it.subtask_done === it.subtask_total}
                      title="{it.subtask_done || 0} din {it.subtask_total} subtaskuri făcute">
                  <ListChecks size={11} />{it.subtask_done || 0}/{it.subtask_total}
                </span>
              {/if}
              {#if it.recurenta}<span class="recur" title="Recurent: {it.recurenta}"><Repeat size={10} /> {it.recurenta}</span>{/if}
            </span>
          </button>

          <div class="arow-tools">
          <div class="arow-actions">
            <button class="abtn" onclick={() => onTomorrow(it)} title="Mută pe mâine"><ArrowRight size={15} /></button>
            <span class="row-date" title="Planifică pe altă zi">
              <DatePicker value={it.data_scadenta} placeholder="Planifică" onchange={(v) => onMoveDate(it, v)} />
            </span>
            <button class="abtn danger" onclick={() => onRemove(it)} title="Scoate termenul — taskul se întoarce în „fără termen”"><X size={15} /></button>
            <button class="abtn deschide" onclick={(e) => openItem(e, it)} title="Deschide"><ChevronRight size={15} /></button>
          </div>
          </div>
          </div>
        </div>
      {/each}
    </div>
  {/if}

</section>

<TaskPickerModal bind:open={showPicker} />

<style>
  .board { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-md); margin-bottom: var(--space-lg); }

  .board-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); margin-bottom: var(--space-md); }
  .bh-left { display: flex; align-items: center; gap: var(--space-xs); color: var(--text); min-width: 0; }
  .bh-left h2 { font-family: var(--font-heading); letter-spacing: -0.02em; font-size: var(--font-h3); font-weight: var(--fw-bold); }
  .bh-count { font-size: var(--font-tiny); padding: 1px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }
  .bh-restante { font-size: var(--font-tiny); font-weight: var(--fw-semibold); padding: 1px 8px; border-radius: var(--radius-full); background: var(--danger-subtle); color: var(--danger); }
  .bh-add { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; font-size: var(--font-small); font-weight: var(--fw-medium); border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); flex-shrink: 0; }
  .bh-add:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }

  .quick-add { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); }
  .quick-add input { flex: 1; min-height: 40px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); }
  .quick-add input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .a-skel { display: flex; flex-direction: column; gap: var(--space-xs); }

  /* Antetul sectiunii personale: micro/mono/uppercase ca .cell-label, cu punctul
     violet (--purple — huea „libera"; amber e severitate/identitate). Bordura de
     sus il desparte de board fara sa-l ridice la rang de al doilea board. */
  .pers-cap { display: flex; align-items: center; gap: 6px; margin-top: var(--space-md); margin-bottom: var(--space-sm); padding-top: var(--space-md); border-top: 1px solid var(--border); font-family: var(--font-mono); font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-faint); }
  .pers-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--purple); flex-shrink: 0; }
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
  .arow { position: relative; display: flex; align-items: center; gap: var(--space-xs); padding: 5px var(--space-sm) 7px; background: var(--bg-panel); border: 1px solid var(--border); border-left: 3px solid var(--sev, var(--border-strong)); border-radius: var(--radius-md); margin-bottom: 6px; transition: transform var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease), opacity var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
  /* Doar unde exista cursor. Pe touch :hover se aplica la atingere si RAMANE
     aplicat pana atingi altceva — randul bifat ar rămâne impins 4px la dreapta,
     ceea ce se citeste ca „s-a stricat", nu ca „am atins". */
  /* `border-left-color` redeclarat: `border-color` scurt vopseste TOATE laturile,
     deci hover-ul ar sterge tocmai bordura de severitate — culoarea rezervata. */
  @media (hover: hover) {
    .arow:hover { transform: translateX(4px); border-color: var(--border-strong); border-left-color: var(--sev, var(--border-strong)); }
  }
  /* Raspunsul la atingere e apasarea, nu deplasarea. */
  .arow:active { border-color: var(--border-strong); border-left-color: var(--sev, var(--border-strong)); }
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
  .arow.done { opacity: 0.5; }
  /* Drag & drop — minimal, on-brand: the grabbed row fades; the drop target shows a
     crisp accent insertion line (no heavy fill); rows settle via animate:flip. */
  .arow.dragging { opacity: 0.45; cursor: grabbing; }
  .arow.dragover { box-shadow: inset 0 2px 0 0 var(--accent); }
  @media (prefers-reduced-motion: reduce) {
    .arow { transition: none; }
  }

  .grip { display: flex; align-items: center; color: var(--text-faint); cursor: grab; flex-shrink: 0; padding: 2px; }
  .grip:active { cursor: grabbing; }

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
  .check-empty { width: 18px; height: 18px; border: 2px solid var(--border); border-radius: 50%; display: inline-block; }
  .check:hover .check-empty { border-color: var(--accent); }

  .amain { flex: 1; min-width: 0; cursor: pointer; text-align: left; display: flex; flex-direction: column; gap: 2px; }
  .atitle { font-size: var(--font-body); color: var(--text); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .arow.done .atitle { text-decoration: line-through; color: var(--text-dim); }
  .ainfo { display: flex; flex-wrap: wrap; gap: var(--space-xs); align-items: center; font-size: var(--font-tiny); color: var(--text-dim); }
  /* Ca in /tasks: eticheta de context pleaca la capatul din dreapta. */
  .ainfo .tag { margin-left: auto; flex: none; }
  .deadline { display: inline-flex; align-items: center; gap: 3px; }
  /* ACEEASI PASTILA CA `.task-cat` DIN /tasks: acelasi obiect (contextul
     taskului — categorie sau proiect) avea aici colturi de radius-xs si acolo
     radius-full. Un obiect, un desen, pe orice ecran apare. */
  .tag { padding: 1px 8px; background: var(--bg-elevated); border-radius: var(--radius-full); font-weight: var(--fw-medium); white-space: nowrap; max-width: 180px; overflow: hidden; text-overflow: ellipsis; }
  .tag.proj { color: var(--text-dim); background: var(--bg-elevated); }
  .recur { display: inline-flex; align-items: center; gap: 3px; padding: 0 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-dim); font-weight: var(--fw-medium); }
  .deadline { font-size: var(--font-tiny); color: var(--text-dim); }
  .deadline.overdue { color: var(--danger); font-weight: var(--fw-semibold); }
  .deadline.soon { color: var(--warning); }

  /* `contents` = invelisul nu exista pentru layout; cele doua grupuri raman copii
     directi ai randului, exact ca inainte. Pe telefon devine cutie adevarata. */
  .arow-tools { display: contents; }
  .gl-maner { display: none; }
  .arow-actions { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
  .abtn { width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease); }
  .abtn:hover:not(:disabled) { background: var(--bg-hover); color: var(--text); }
  .abtn.danger:hover:not(:disabled) { color: var(--danger); background: var(--danger-subtle); }
  .abtn:disabled { opacity: 0.3; cursor: not-allowed; }

  /* Inline reschedule = a calendar ICON button (the date is implicit on the
     "today" board), styled like the other row actions; opens the shared DatePicker.
     The date text is hidden so rows stay compact. */
  .row-date { width: 30px; flex-shrink: 0; }
  .row-date :global(.dp-trigger) {
    width: 30px; min-height: 30px; padding: 0;
    justify-content: center;
    background: transparent; border: none; box-shadow: none;
    color: var(--text-faint);
  }
  .row-date :global(.dp-trigger:hover) { background: var(--bg-hover); color: var(--text); }
  .row-date :global(.dp-trigger svg) { color: inherit; }
  .row-date :global(.dp-value) { display: none; }

  /* ===== glisare (doar telefon) ===== */
  .gl-fata { display: contents; }
  .gl-actiuni { display: none; }

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
    .arow { flex-wrap: nowrap; row-gap: 0; padding: 0; overflow: hidden; position: relative;
            touch-action: pan-y; }
    .gl-fata { display: flex; align-items: center; gap: var(--space-xs); width: 100%;
               padding: 7px var(--space-sm) 9px; background: var(--bg-panel);
               border-radius: var(--radius-md); position: relative; z-index: 1;
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

    .gl-actiuni { display: flex; position: absolute; top: 0; right: 0; bottom: 0; z-index: 0;
                  align-items: stretch; }
    .glb { width: 58px; display: flex; flex-direction: column; align-items: center; justify-content: center;
           gap: 3px; border: none; background: var(--bg-elevated); color: var(--text-secondary);
           font-size: var(--font-micro); cursor: pointer; }
    .glb span { line-height: 1; }
    .glb.danger { background: var(--danger-subtle); color: var(--danger); }
    .glb.datewrap { position: relative; }
    /* DatePicker-ul aduce cu el un declansator de camp; aici trebuie sa fie doar
       iconita, ca vecinii lui. */
    .glb.datewrap :global(.dp) { position: absolute; inset: 0; width: auto; }
    .glb.datewrap :global(.dp-trigger) { width: 100%; height: 100%; min-height: 0; padding: 0 0 14px;
      justify-content: center; background: none; border: none; box-shadow: none; color: inherit; }
    .glb.datewrap :global(.dp-value) { display: none; }
    .glb.datewrap > span { position: absolute; left: 0; right: 0; bottom: 11px; text-align: center; pointer-events: none; }

    /* Cursa de bifare: cat timp tragi spre dreapta destul, dedesubt se vede verde.
       Fara semnal, gestul e o loterie — nu stii cand ai trecut pragul. */
    .arow:global(.gl-bifa) { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }

    .bh-add-txt { display: none; }
    .grip { display: none; }
    .quick-add input, .quick-add-btn { min-height: var(--tap-min); }
    .quick-add-btn { width: var(--tap-min); }
    /* „Adaugă task existent" ramane doar iconita pe telefon — deci iconita trebuie
       sa aiba caseta unui buton, nu 40×28. */
    .bh-add { min-width: var(--tap-min); min-height: var(--tap-min); justify-content: center; padding: 0 10px; }

    /* Indexul pleaca: pe un rand de o linie, doua cifre in fata titlului nu spun
       nimic ce nu spune deja ordinea de sus in jos, si mananca 28px din titlu. */
    .tix { display: none; }
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
    .tag { max-width: 96px; background: none; padding: 0; font-weight: var(--fw-normal); color: var(--text-faint); }

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
    .gl-maner { display: flex; align-items: center; justify-content: center;
                width: var(--tap-min); height: var(--tap-min); flex-shrink: 0;
                margin-right: -6px; color: var(--text-faint);
                touch-action: none; cursor: grab; }
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
