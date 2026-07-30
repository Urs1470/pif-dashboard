<script>
  import { onMount } from 'svelte'
  import { flip } from 'svelte/animate'
  import {
    CalendarCheck, Plus, GripVertical, ArrowRight, X,
    ChevronRight, CheckCircle2, Repeat, ArrowUp, ArrowDown, ListPlus
  } from '@lucide/svelte'
  import {
    agenda, loadAgendaToday, quickAddToday, moveToTomorrow, moveToDate,
    removeFromToday, toggleDone, reorderAgenda
  } from '../stores/agenda.svelte.js'
  import { dueColor, formatDate } from '../lib/formatters.js'
  import { glisare, inchideGlisarea } from '../lib/glisare.js'
  import { navigate } from '../lib/router.svelte.js'
  import { morphNavigate } from '../lib/focus.js'
  import { toast } from '../stores/ui.svelte.js'
  import TaskPickerModal from './TaskPickerModal.svelte'
  import EmptyState from './ui/EmptyState.svelte'
  import Skeleton from './ui/Skeleton.svelte'
  import DatePicker from './ui/DatePicker.svelte'
  import { motionDuration, DUR_BASE } from '../lib/motion.svelte.js'

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

  function dateOnly(d) { return new Date(new Date(d).toDateString()) }
  function isOverdue(d) { if (!d) return false; return dateOnly(d) < new Date(new Date().toDateString()) }
  function isToday(d) { if (!d) return false; return new Date(d).toDateString() === new Date().toDateString() }
  function isSoon(d) { if (!d) return false; const diff = (dateOnly(d) - new Date(new Date().toDateString())) / 86400000; return diff > 0 && diff <= 7 }

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
    try {
      const res = await toggleDone(it.tip, it.id, it.status)
      if (res?.recurring_spawned) {
        toast(`Finalizat ✓ — următoarea apariție: ${formatDate(res.recurring_next)}`, 'success')
      }
      onchange()
    } catch (e) {
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
    else morphNavigate(src, '/tasks', 'global', it.id)
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
  async function moveUp(i) { if (i > 0) await commitMove(i, i - 1) }
  async function moveDown(i) { if (i < agenda.items.length - 1) await commitMove(i, i + 1) }

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
  let peTelefon = $state(false)

  onMount(() => {
    loadAgendaToday()
    const mq = window.matchMedia('(max-width: 768px)')
    const apply = () => { peTelefon = mq.matches; if (!peTelefon) inchideGlisarea() }
    apply()
    mq.addEventListener?.('change', apply)
    return () => { mq.removeEventListener?.('change', apply); inchideGlisarea() }
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
    <input type="text" placeholder="Task rapid pentru azi... Enter pentru a adăuga" bind:value={quickTitle} disabled={quickAdding} />
    <button type="submit" class="quick-add-btn" disabled={!quickTitle.trim() || quickAdding} title="Adaugă task"><Plus size={16} /></button>
  </form>

  {#if agenda.loading && agenda.items.length === 0}
    <div class="a-skel">{#each Array(3) as _}<Skeleton height="40px" />{/each}</div>
  {:else if agenda.error}
    <p class="a-error">Eroare: {agenda.error}</p>
  {:else if agenda.items.length === 0}
    <EmptyState icon={CalendarCheck} title="Nimic planificat azi" description="Adaugă un task rapid sau alege din taskurile existente." />
  {:else}
    <div class="a-list" role="list">
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
          use:glisare={{ latime: peTelefon ? 176 : 0, activ: peTelefon, onBifa: it.status === 'done' ? null : () => onToggle(it) }}
        >
          <!-- Panoul de actiuni sta SUB rand si se descopera glisand spre stanga
               (vezi lib/glisare.js). Pe desktop e ascuns: acolo actiunile stau la
               vedere in rand, unde le ajunge cursorul. -->
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
              {#if it.tip === 'proiect' && it.proiect_nume}<span class="tag proj">{it.proiect_nume}</span>
              {:else if it.categorie}<span class="tag">{it.categorie}</span>{/if}
              {#if it.recurenta}<span class="recur" title="Recurent: {it.recurenta}"><Repeat size={10} /> {it.recurenta}</span>{/if}
              {#if it.is_restant}<span class="badge restant">Restant</span>{/if}
              {#if it.is_scadent_azi}<span class="badge scadent">Termen azi</span>{/if}
              {#if it.data_scadenta && !it.is_scadent_azi}<span class="deadline" class:overdue={isOverdue(it.data_scadenta)} class:soon={isSoon(it.data_scadenta)}>termen {formatDate(it.data_scadenta)}</span>{/if}
            </span>
          </button>

          <!-- Un singur invelis pentru cele doua grupuri de actiuni. Pe desktop e
               `display: contents`, deci nu schimba nimic; pe telefon e ce cade pe
               linia a doua, INTREG. Fara el, wrap-ul de flex decidea singur unde se
               rupe randul si iesea pe trei linii (bifa singura sus, titlu, actiuni)
               = 172px pe task, adica patru taskuri pe ecran. -->
          <div class="arow-tools">
          <div class="arow-arrows">
            <button class="abtn" disabled={i === 0} onclick={() => moveUp(i)} title="Mută mai sus"><ArrowUp size={14} /></button>
            <button class="abtn" disabled={i === agenda.items.length - 1} onclick={() => moveDown(i)} title="Mută mai jos"><ArrowDown size={14} /></button>
          </div>

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

</section>

<TaskPickerModal bind:open={showPicker} />

<style>
  .board { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-md); margin-bottom: var(--space-lg); }

  .board-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); margin-bottom: var(--space-md); }
  .bh-left { display: flex; align-items: center; gap: var(--space-xs); color: var(--text); min-width: 0; }
  .bh-left h2 { font-family: var(--font-heading); letter-spacing: -0.02em; font-size: var(--font-h3); font-weight: var(--fw-bold); }
  .bh-count { font-size: var(--font-tiny); padding: 1px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }
  .bh-restante { font-size: var(--font-tiny); font-weight: var(--fw-semibold); padding: 1px 8px; border-radius: var(--radius-full); background: var(--danger-subtle); color: var(--danger); }
  .bh-add { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; font-size: var(--font-small); font-weight: var(--fw-medium); border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; transition: all var(--dur-fast) var(--ease); flex-shrink: 0; }
  .bh-add:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }

  .quick-add { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); }
  .quick-add input { flex: 1; min-height: 40px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); }
  .quick-add input:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .a-skel { display: flex; flex-direction: column; gap: var(--space-xs); }
  .a-error { color: var(--danger); font-size: var(--font-small); padding: var(--space-sm); }

  .a-list { display: flex; flex-direction: column; }
  /* Insula (V3+V2): fara bara pe stanga — underline scurt de severitate jos
     + index mono ghost; delimitare prin spatiu, nu linii. */
  .arow { position: relative; display: flex; align-items: center; gap: var(--space-xs); padding: 8px var(--space-sm) 10px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: 6px; transition: transform var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease), opacity var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
  .arow::after { content: ''; position: absolute; left: 12px; bottom: 0; height: 2px; width: 40px; border-radius: 2px 2px 0 0; background: var(--sev, var(--border-strong)); box-shadow: 0 0 8px color-mix(in srgb, var(--sev, transparent) 45%, transparent); }
  /* Doar unde exista cursor. Pe touch :hover se aplica la atingere si RAMANE
     aplicat pana atingi altceva — randul bifat ar rămâne impins 4px la dreapta,
     ceea ce se citeste ca „s-a stricat", nu ca „am atins". */
  @media (hover: hover) {
    .arow:hover { transform: translateX(4px); border-color: var(--border-strong); }
  }
  /* Raspunsul la atingere e apasarea, nu deplasarea. */
  .arow:active { border-color: var(--border-strong); }
  .tix { font-family: var(--font-mono); font-size: 1rem; font-weight: var(--fw-bold); letter-spacing: -0.04em; color: color-mix(in srgb, var(--sev, var(--border-strong)) 70%, transparent); min-width: 28px; flex-shrink: 0; font-variant-numeric: tabular-nums; }
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

  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; display: flex; }
  .check:hover { color: var(--accent); }
  .arow.done .check { color: var(--success); }
  .check-empty { width: 18px; height: 18px; border: 2px solid var(--border); border-radius: 50%; display: inline-block; }
  .check:hover .check-empty { border-color: var(--accent); }

  .amain { flex: 1; min-width: 0; cursor: pointer; text-align: left; display: flex; flex-direction: column; gap: 2px; }
  .atitle { font-size: var(--font-small); color: var(--text); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .arow.done .atitle { text-decoration: line-through; color: var(--text-dim); }
  .ainfo { display: flex; flex-wrap: wrap; gap: var(--space-xs); align-items: center; font-size: var(--font-tiny); color: var(--text-dim); }
  .tag { padding: 0 6px; background: var(--bg-elevated); border-radius: var(--radius-xs); white-space: nowrap; max-width: 180px; overflow: hidden; text-overflow: ellipsis; }
  .tag.proj { color: var(--accent); background: var(--accent-subtle); }
  .recur { display: inline-flex; align-items: center; gap: 3px; padding: 0 6px; background: var(--accent-subtle); color: var(--accent); border-radius: var(--radius-xs); }
  .badge { font-size: var(--font-micro); font-weight: var(--fw-semibold); padding: 1px 7px; border-radius: var(--radius-full); white-space: nowrap; }
  .badge.restant { background: var(--danger-subtle); color: var(--danger); }
  .badge.scadent { background: var(--accent-subtle); color: var(--accent); }
  .deadline { font-size: var(--font-micro); color: var(--text-dim); }
  .deadline.overdue { color: var(--danger); font-weight: var(--fw-semibold); }
  .deadline.soon { color: var(--warning); }

  /* `contents` = invelisul nu exista pentru layout; cele doua grupuri raman copii
     directi ai randului, exact ca inainte. Pe telefon devine cutie adevarata. */
  .arow-tools { display: contents; }
  .arow-arrows { display: none; align-items: center; gap: 2px; flex-shrink: 0; }
  .arow-actions { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
  .abtn { width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; transition: all var(--dur-fast) var(--ease); }
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
    .arow.gl-tras .gl-fata { box-shadow: -6px 0 12px -8px rgba(0,0,0,0.55); }

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
    .arow.gl-bifa { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }

    .bh-add-txt { display: none; }
    .grip { display: none; }
    .arow-arrows { display: flex; }
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
    /* Meta pe un singur rand, taiata la capat: pe o linie de 56px nu incap doua
       randuri de chipuri, iar cel mai important lucru — termenul — e primul. */
    .ainfo { flex-wrap: nowrap; overflow: hidden; }
    .ainfo > * { flex-shrink: 0; }
    .tag { max-width: 130px; }

    /* Din cele sase butoane raman doua la vedere: bifa (actiunea principala) si
       reordonarea. Restul stau in panoul de sub rand. */
    .arow-tools { display: contents; }
    .arow-actions { display: none; }
    .abtn { width: 34px; height: 34px; }
    /* Sagetile de reordonare sunt singurele tinte sub 44px care raman, si stau
       asa cu buna stiinta: sunt DOUA lipite pe verticala, iar perechea are
       40×44 — degetul nu cade LANGA ele, cade pe una din doua. Amandoua fac
       acelasi fel de lucru (muta randul cu o pozitie), in directii opuse, deci
       cea mai rea greseala posibila se repara atingand cealalta sageata. */
    .arow-arrows { display: flex; flex-direction: column; gap: 0; margin-left: 2px; }
    .arow-arrows .abtn { width: 40px; height: 22px; }
    /* Bifa e actiunea principala a randului — merita cea mai mare tinta, nu cea
       mai mica. Cercul vizibil ramane de 18px; caseta din jur ajunge la 44. */
    .check { width: var(--tap-min); height: var(--tap-min); align-items: center; justify-content: center; padding: 0; }
  }
</style>
