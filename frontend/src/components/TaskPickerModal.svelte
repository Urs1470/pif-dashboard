<script>
  import { Search, Plus, FolderKanban, ListTodo } from '@lucide/svelte'
  import Modal from './ui/Modal.svelte'
  import Skeleton from './ui/Skeleton.svelte'
  import { loadCandidates, scheduleForToday } from '../stores/agenda.svelte.js'
  import { dueRing, formatDate } from '../lib/formatters.js'
  import { toast } from '../stores/ui.svelte.js'

  let { open = $bindable(false) } = $props()

  let q = $state('')
  let items = $state([])
  let loading = $state(false)
  let addingKey = $state(null)
  let searchTimer = null

  // CASETA SE DESCHIDE CU DATELE IN MANA.
  //
  // Masurat: se deschidea la 228px si SAREA la 374 dupa 16ms, cat era inca la
  // opacitate 0,19. Cauza: `open` randa imediat, cu `items` gol, deci caseta se
  // dimensiona dupa o singura linie de text („Niciun task disponibil"), iar lista
  // venea dupa. Scalarea de intrare (0,96 -> 1) misca vreo 15px; saltul era de
  // zece ori mai mare si se juca peste ea. Ce vedeai nu era un modal care
  // soseste, era unul care se corecteaza — si sarea si pe verticala, fiindca e
  // centrat (top 361 -> 288).
  //
  // Aceeasi regula ca la `desfacere` din motion.svelte.js, unde e scrisa deja:
  // un panou se deschide numai cu continutul masurabil, altfel tranzitia
  // animeaza spre o tinta care se schimba sub ea.
  //
  // `deschis` e ce vede <Modal>; `open` ramane intentia parintelui. Inchiderea
  // pornita de utilizator se intoarce prin `onclose`, singurul drum pe care
  // Modal il semnaleaza in afara.
  let deschis = $state(false)

  // Plafon, ca butonul sa nu para stricat daca API-ul intarzie: peste atat
  // deschidem oricum, cu schelet in loc de lista. Scheletul tine locul listei,
  // deci umplerea de dupa e o inlocuire, nu un salt. Sub plafon (cazul normal)
  // nu se vede niciodata.
  const PLAFON_DESCHIDERE = 250

  async function runSearch() {
    loading = true
    try {
      items = await loadCandidates(q)
    } catch (e) {
      items = []
      toast(`Eroare: ${e.message}`, 'error')
    } finally {
      loading = false
      deschis = true
    }
  }

  // Load on open and on (debounced) query change. The modal stays mounted, so
  // this effect re-runs whenever `open` or `q` changes.
  $effect(() => {
    if (!open) return
    const query = q
    clearTimeout(searchTimer)
    searchTimer = setTimeout(runSearch, query ? 200 : 0)
    return () => clearTimeout(searchTimer)
  })

  // Citeste DOAR `open`, ca sa nu se rearmeze la fiecare tasta.
  $effect(() => {
    if (!open) { deschis = false; return }
    const ceas = setTimeout(() => { deschis = true }, PLAFON_DESCHIDERE)
    return () => clearTimeout(ceas)
  })

  const groups = $derived.by(() => {
    const g = []
    const globals = items.filter(i => i.tip === 'global')
    if (globals.length) g.push({ key: 'global', label: 'Taskuri globale', icon: ListTodo, rows: globals })
    const byProj = new Map()
    for (const it of items.filter(i => i.tip === 'proiect')) {
      const k = it.proiect_id || '—'
      if (!byProj.has(k)) byProj.set(k, { key: k, label: it.proiect_nume || 'Proiect', icon: FolderKanban, rows: [] })
      byProj.get(k).rows.push(it)
    }
    for (const v of byProj.values()) g.push(v)
    return g
  })

  async function pick(it) {
    const key = it.tip + ':' + it.id
    addingKey = key
    try {
      // scheduleForToday reloads the board store, so it updates live behind the modal.
      await scheduleForToday(it.tip, it.id)
      items = items.filter(x => (x.tip + ':' + x.id) !== key)
      toast('Adăugat în Astăzi', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally {
      addingKey = null
    }
  }
</script>

<Modal bind:open={deschis} onclose={() => open = false} title="Adaugă task în Astăzi" size="md">
  <div class="picker">
    <div class="search-box">
      <Search size={15} />
      <input type="text" placeholder="Caută în taskuri..." bind:value={q} />
    </div>

    <!-- Schelet DOAR la prima incarcare (`items` inca gol) — regula din sistemul
         de design. Cand tastezi o cautare peste o lista deja adusa, randurile
         vechi RAMAN pe ecran cat vin cele noi: altfel caseta s-ar strange la
         inaltimea scheletului si s-ar umfla inapoi la fiecare tasta. -->
    {#if loading && items.length === 0}
      <div class="pk-schelet" aria-hidden="true">
        {#each Array(5) as _}<Skeleton height="36px" />{/each}
      </div>
    {:else if items.length === 0}
      <div class="pk-hint">{q ? 'Niciun task găsit.' : 'Niciun task disponibil de adăugat.'}</div>
    {:else}
      <div class="pk-list">
        {#each groups as grp (grp.key)}
          <div class="pk-group">
            <div class="pk-group-head">
              <grp.icon size={13} />
              <span>{grp.label}</span>
              <span class="pk-group-count">{grp.rows.length}</span>
            </div>
            {#each grp.rows as it (it.tip + ':' + it.id)}
              <button class="pk-row" disabled={addingKey === (it.tip + ':' + it.id)} onclick={() => pick(it)}>
                <!-- Punctul se randeaza DOAR cand spune ceva. Pe neutru era un
                     punct de culoarea bordurii: cerneala fara informatie, pe
                     fiecare rand din lista. -->
                {#if dueRing(it.data_scadenta) !== 'var(--border)'}
                  <span class="pk-prio" style="background: {dueRing(it.data_scadenta)}"></span>
                {/if}
                <span class="pk-title">{it.titlu}</span>
                {#if it.data_scadenta}<span class="pk-scad">termen {formatDate(it.data_scadenta)}</span>{/if}
                <span class="pk-add"><Plus size={15} /></span>
              </button>
            {/each}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</Modal>

<style>
  .picker { display: flex; flex-direction: column; gap: var(--space-md); }
  .search-box { display: flex; align-items: center; gap: var(--space-xs); padding: 8px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text-dim); }
  .search-box input { background: transparent; border: none; color: var(--text); font-size: var(--font-small); flex: 1; outline: none; box-shadow: none; }
  .search-box input::placeholder { color: var(--text-dim); }
  .search-box:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-subtle); }

  .pk-hint { font-size: var(--font-small); color: var(--text-dim); padding: var(--space-lg); text-align: center; }
  /* Aceeasi geometrie ca `.pk-list` (cinci randuri de 36px + acelasi gap): cand
     lista chiar vine, ea INLOCUIESTE scheletul in loc sa impinga caseta. */
  .pk-schelet { display: flex; flex-direction: column; gap: 4px; }
  .pk-list { display: flex; flex-direction: column; gap: var(--space-md); max-height: 52dvh; overflow-y: auto; scrollbar-width: thin; }
  .pk-group { display: flex; flex-direction: column; }
  .pk-group-head { display: flex; align-items: center; gap: 6px; font-size: var(--font-small); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); padding: 4px 2px; }
  .pk-group-count { margin-left: auto; padding: 0 7px; border-radius: var(--radius-full); background: var(--bg-elevated); color: var(--text-secondary); }

  .pk-row { display: flex; align-items: center; gap: var(--space-sm); padding: 8px 10px; border-radius: var(--radius-sm); text-align: left; cursor: pointer; transition: background var(--dur-fast) var(--ease); }
  .pk-row:hover:not(:disabled) { background: var(--bg-hover); }
  .pk-row:disabled { opacity: 0.5; cursor: default; }
  .pk-prio { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  .pk-title { flex: 1; min-width: 0; font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pk-scad { font-size: var(--font-small); color: var(--text-dim); white-space: nowrap; }
  .pk-add { display: inline-flex; align-items: center; justify-content: center; color: var(--text-faint); flex-shrink: 0; }
  .pk-row:hover .pk-add { color: var(--accent); }

  @media (max-width: 768px) {
    /* O lista de randuri de 36px, lipite unul de altul: atingi randul de deasupra
       celui pe care il voiai si adaugi ALT task pe ziua de azi. */
    .pk-row { min-height: var(--tap-min); }
    /* Caseta de cautare are 41px, dar inputul dinauntru avea 25 — si doar el
       primeste focus. */
    .search-box { padding: 0 12px; align-items: stretch; }
    .search-box input { align-self: stretch; min-height: var(--tap-min); }
    .search-box :global(svg) { align-self: center; }
    .pk-list { max-height: 46dvh; overscroll-behavior: contain; }
  }
</style>
