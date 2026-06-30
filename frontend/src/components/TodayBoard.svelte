<script>
  import { onMount } from 'svelte'
  import { slide } from 'svelte/transition'
  import {
    CalendarCheck, Plus, GripVertical, ArrowRight, CalendarDays, X,
    ChevronRight, CheckCircle2, Repeat, ArrowUp, ArrowDown, ListPlus
  } from '@lucide/svelte'
  import {
    agenda, loadAgendaToday, quickAddToday, moveToTomorrow, moveToDate,
    removeFromToday, toggleDone, reorderAgenda
  } from '../stores/agenda.svelte.js'
  import { TASK_STATUS_LABELS, STATUS_COLORS, priorityColor, priorityLabel, formatDate } from '../lib/formatters.js'
  import { navigate } from '../lib/router.svelte.js'
  import { toast } from '../stores/ui.svelte.js'
  import TaskPickerModal from './TaskPickerModal.svelte'
  import EmptyState from './ui/EmptyState.svelte'
  import Skeleton from './ui/Skeleton.svelte'

  let quickTitle = $state('')
  let quickAdding = $state(false)
  let showPicker = $state(false)

  let dragIndex = $state(null)
  let overIndex = $state(null)
  let dateInput = $state(null)
  let dateTarget = null

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
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  async function onTomorrow(it) {
    try { await moveToTomorrow(it.tip, it.id); toast('Mutat pe mâine', 'success') }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function onRemove(it) {
    try { await removeFromToday(it.tip, it.id) }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  function openDatePicker(it) {
    dateTarget = it
    if (!dateInput) return
    dateInput.value = ''
    if (dateInput.showPicker) dateInput.showPicker()
    else dateInput.click()
  }

  async function onDateChange(e) {
    const v = e.target.value
    const target = dateTarget
    dateTarget = null
    if (!v || !target) return
    try { await moveToDate(target.tip, target.id, v); toast(`Mutat pe ${formatDate(v)}`, 'success') }
    catch (err) { toast(`Eroare: ${err.message}`, 'error') }
  }

  function openItem(it) {
    if (it.tip === 'proiect' && it.proiect_id) navigate(`/projects/${it.proiect_id}`)
    else navigate('/tasks')
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

  onMount(loadAgendaToday)
</script>

<section class="board">
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
          style="border-left-color: {priorityColor(it.prioritate || 'normal')}"
          role="listitem"
          ondragover={(e) => onDragOver(e, i)}
          ondrop={(e) => onDrop(e, i)}
        >
          <span class="grip" draggable="true" ondragstart={(e) => onDragStart(e, i)} ondragend={onDragEnd} title="Trage pentru a reordona"><GripVertical size={15} /></span>

          <button class="check" onclick={() => onToggle(it)} title="Marchează ca făcut">
            {#if it.status === 'done'}<CheckCircle2 size={18} />{:else}<span class="check-empty"></span>{/if}
          </button>

          <button class="amain" onclick={() => openItem(it)}>
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

          <div class="arow-arrows">
            <button class="abtn" disabled={i === 0} onclick={() => moveUp(i)} title="Mută mai sus"><ArrowUp size={14} /></button>
            <button class="abtn" disabled={i === agenda.items.length - 1} onclick={() => moveDown(i)} title="Mută mai jos"><ArrowDown size={14} /></button>
          </div>

          <div class="arow-actions">
            <button class="abtn" onclick={() => onTomorrow(it)} title="Mută pe mâine"><ArrowRight size={15} /></button>
            <button class="abtn" onclick={() => openDatePicker(it)} title="Mută pe altă zi"><CalendarDays size={15} /></button>
            <button class="abtn danger" onclick={() => onRemove(it)} title="Scoate din azi"><X size={15} /></button>
            <button class="abtn" onclick={() => openItem(it)} title="Deschide"><ChevronRight size={15} /></button>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <input type="date" class="hidden-date" bind:this={dateInput} min={agenda.today} onchange={onDateChange} tabindex="-1" aria-hidden="true" />
</section>

<TaskPickerModal bind:open={showPicker} />

<style>
  .board { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-md); margin-bottom: var(--space-lg); }

  .board-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); margin-bottom: var(--space-md); }
  .bh-left { display: flex; align-items: center; gap: var(--space-xs); color: var(--text); min-width: 0; }
  .bh-left h2 { font-size: var(--font-h3); font-weight: 700; }
  .bh-count { font-size: var(--font-tiny); padding: 1px 8px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-dim); }
  .bh-restante { font-size: var(--font-tiny); font-weight: 600; padding: 1px 8px; border-radius: var(--radius-full); background: var(--danger-subtle); color: var(--danger); }
  .bh-add { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; font-size: var(--font-small); font-weight: 500; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; transition: all var(--dur-fast) var(--ease); flex-shrink: 0; }
  .bh-add:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }

  .quick-add { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); }
  .quick-add input { flex: 1; min-height: 40px; padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); }
  .quick-add input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); outline: none; }
  .quick-add input::placeholder { color: var(--text-dim); }
  .quick-add-btn { width: 40px; min-height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; flex-shrink: 0; transition: all var(--dur-fast) var(--ease); }
  .quick-add-btn:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); background: var(--accent-subtle); }
  .quick-add-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .a-skel { display: flex; flex-direction: column; gap: var(--space-xs); }
  .a-error { color: var(--danger); font-size: var(--font-small); padding: var(--space-sm); }

  .a-list { display: flex; flex-direction: column; }
  .arow { display: flex; align-items: center; gap: var(--space-xs); padding: var(--space-xs) var(--space-sm); border-left: 2px solid var(--border); border-radius: var(--radius-xs); margin-bottom: 2px; transition: background var(--dur-fast) var(--ease); }
  .arow:hover { background: var(--bg-elevated); }
  .arow.done { opacity: 0.5; }
  .arow.dragging { opacity: 0.4; }
  .arow.dragover { background: var(--accent-subtle); box-shadow: inset 0 2px 0 var(--accent); }

  .grip { display: flex; align-items: center; color: var(--text-faint); cursor: grab; flex-shrink: 0; padding: 2px; }
  .grip:active { cursor: grabbing; }

  .check { flex-shrink: 0; color: var(--text-dim); cursor: pointer; padding: 2px; display: flex; }
  .check:hover { color: var(--accent); }
  .arow.done .check { color: var(--success); }
  .check-empty { width: 18px; height: 18px; border: 2px solid var(--border); border-radius: 50%; display: inline-block; }
  .check:hover .check-empty { border-color: var(--accent); }

  .amain { flex: 1; min-width: 0; cursor: pointer; text-align: left; display: flex; flex-direction: column; gap: 2px; }
  .atitle { font-size: var(--font-small); color: var(--text); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .arow.done .atitle { text-decoration: line-through; color: var(--text-dim); }
  .ainfo { display: flex; flex-wrap: wrap; gap: var(--space-xs); align-items: center; font-size: var(--font-tiny); color: var(--text-dim); }
  .tag { padding: 0 6px; background: var(--bg-elevated); border-radius: var(--radius-xs); white-space: nowrap; max-width: 180px; overflow: hidden; text-overflow: ellipsis; }
  .tag.proj { color: var(--accent); background: var(--accent-subtle); }
  .recur { display: inline-flex; align-items: center; gap: 3px; padding: 0 6px; background: var(--accent-subtle); color: var(--accent); border-radius: var(--radius-xs); }
  .badge { font-size: 10px; font-weight: 600; padding: 1px 7px; border-radius: var(--radius-full); white-space: nowrap; }
  .badge.restant { background: var(--danger-subtle); color: var(--danger); }
  .badge.scadent { background: var(--accent-subtle); color: var(--accent); }
  .deadline { font-size: 10px; color: var(--text-dim); }
  .deadline.overdue { color: var(--danger); font-weight: 600; }
  .deadline.soon { color: var(--warning); }

  .arow-arrows { display: none; align-items: center; gap: 2px; flex-shrink: 0; }
  .arow-actions { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
  .abtn { width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; transition: all var(--dur-fast) var(--ease); }
  .abtn:hover:not(:disabled) { background: var(--bg-hover); color: var(--text); }
  .abtn.danger:hover:not(:disabled) { color: var(--danger); background: var(--danger-subtle); }
  .abtn:disabled { opacity: 0.3; cursor: not-allowed; }

  .hidden-date { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; border: 0; opacity: 0; pointer-events: none; }

  @media (max-width: 768px) {
    .bh-add-txt { display: none; }
    .grip { display: none; }
    .arow-arrows { display: flex; }
    .quick-add input, .quick-add-btn { min-height: 44px; }
    .quick-add-btn { width: 44px; }
    .abtn { width: 34px; height: 34px; }
  }
</style>
