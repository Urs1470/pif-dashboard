<script>
  import { onMount } from 'svelte'
  import { fly, slide } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { FolderKanban, Plus, ChevronDown, Archive, CheckSquare, Square, ArrowUpDown, Zap, Wrench } from '@lucide/svelte'
  import SolidIcon from '../components/ui/SolidIcon.svelte'
  import { projects, loadProjects, updateProject, deleteProject } from '../stores/projects.svelte.js'
  import { PROJECT_STATUS_LABELS, STATUS_COLORS, formatDate } from '../lib/formatters.js'
  import { navigate } from '../lib/router.svelte.js'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../lib/motion.svelte.js'
  import { ecran } from '../lib/ecran.svelte.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import Badge from '../components/ui/Badge.svelte'
  import Button from '../components/ui/Button.svelte'
  import Select from '../components/ui/Select.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  import ProjectFormModal from '../components/projects/ProjectFormModal.svelte'

  // CHIPURILE DE FILTRU AU PLECAT. Grila separa deja finalizatele in „Arhivă"
  // pliabila; „Finalizat" ca chip arata exact acel continut, dar in grila, iar
  // „Toate" le arata pe amandoua. Acelasi continut, trei drumuri, trei asezari —
  // aceeasi decizie ca la „Active" din /tasks, care era un filtru mereu pornit.
  // Ce ramane in bara: cautarea, sortarea si arhiva.

  const sortOptions = [
    { value: 'nume', label: 'Nume' },
    { value: 'client', label: 'Client' },
    { value: 'tip', label: 'Tip' },
    { value: 'status', label: 'Status' },
    { value: 'urmatoarea', label: 'Următoarea ieșire' },
  ]

  const batchStatusOptions = [
    { value: 'pregatire', label: 'În pregătire' },
    { value: 'finalizat', label: 'Finalizat' },
  ]

  function daysUntil(zi) {
    if (!zi) return null
    const d = new Date(zi)
    if (isNaN(d)) return null
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    d.setHours(0, 0, 0, 0)
    return Math.round((d - today) / 86400000)
  }

  // Deadline-ul a plecat in v30 (nu se lua nimeni dupa el). Ce conteaza aici e
  // urmatoarea perioada: cand iesi efectiv pe teren sau te pregatesti.
  //
  // RANDUL DE JOS, DESFACUT IN TREI. Era un singur sir la 10.4px monospace —
  // „pregătire · 12.08.2026 — 5 zile" — adica faza, data plina si o socoteala
  // relativa, toate la cea mai mica treapta din scara; iar la ≤2 zile se inrosea
  // TOT sirul, inclusiv faza, care nu e urgenta. Acum: faza e eticheta micro,
  // socoteala urca la --font-small si poarta SINGURA culoarea, data plina trece
  // in `title` — o verifici cand o cauti.
  const FAZA_SCURT = { pregatire: 'Pregătire', implementare: 'Implementare' }
  function urmatoarea(p) {
    const zi = p.urmatoarea
    if (!zi) return { faza: '', cand: 'fără perioadă', data: '', urgent: false }
    const days = daysUntil(zi)
    const cand = days === null ? formatDate(zi)
      : days === 0 ? 'azi'
      : days === 1 ? 'mâine'
      : days < 0 ? `acum ${-days} zile`
      : `peste ${days} zile`
    return {
      faza: FAZA_SCURT[p.urmatoarea_faza] || '',
      cand, data: formatDate(zi),
      urgent: days !== null && days <= 2,
    }
  }

  // Cu doua statusuri, clickul pe status e un comutator, nu un ciclu.
  const STATUS_CYCLE = ['pregatire', 'finalizat']

  // O atingere gresita marcheaza un proiect viu „Finalizat" — si cardul DISPARE
  // din grila, in arhiva pliata. Deci schimbarea are plasa, ca la bifat si la
  // mutat termen: `toastUndo` cu drumul inapoi in mana.
  async function cycleProjectStatus(e, p) {
    e.stopPropagation()
    const cur = p.status || 'pregatire'
    const next = STATUS_CYCLE[(STATUS_CYCLE.indexOf(cur) + 1) % STATUS_CYCLE.length]
    try {
      await updateProject(p.id, { status: next })
      toastUndo(`Status: ${PROJECT_STATUS_LABELS[next] || next}`, {
        onUndo: async () => {
          try { await updateProject(p.id, { status: cur }); await loadProjects() }
          catch (err) { toast(`Eroare: ${err.message}`, 'error') }
        },
      })
    } catch (err) { toast(`Eroare: ${err.message}`, 'error') }
  }

  let showNewModal = $state(false)
  let showArchive = $state(false)
  let sort = $state({ key: 'nume', dir: 1 })

  let batchMode = $state(false)
  let selected = $state(new Set())
  let batchStatus = $state('')
  let showBatchDelete = $state(false)
  let batchBusy = $state(false)

  function toggleBatch() {
    batchMode = !batchMode
    if (!batchMode) selected = new Set()
  }

  function toggleSelect(id) {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id); else next.add(id)
    selected = next
  }

  function toggleSelectAll() {
    if (selected.size === activeItems.length) {
      selected = new Set()
    } else {
      selected = new Set(activeItems.map(p => p.id))
    }
  }

  async function batchUpdateStatus() {
    if (!batchStatus || selected.size === 0) return
    batchBusy = true
    try {
      await Promise.all([...selected].map(id => updateProject(id, { status: batchStatus })))
      toast(`${selected.size} proiecte actualizate`, 'success')
      selected = new Set()
      batchStatus = ''
      await loadProjects()
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { batchBusy = false }
  }

  async function batchDeleteSelected() {
    if (selected.size === 0) return
    batchBusy = true
    try {
      for (const id of selected) await deleteProject(id)
      toast(`${selected.size} proiecte șterse`, 'success')
      selected = new Set()
      showBatchDelete = false
      await loadProjects()
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { batchBusy = false }
  }

  let sortOpen = $state(false)
  let sortEl = $state(null)
  const sortLabel = $derived(sortOptions.find((o) => o.value === sort.key)?.label || 'Nume')

  function pickSort(v) {
    if (sort.key === v) sort = { key: v, dir: -sort.dir } // aceeasi optiune = inverseaza
    else sort = { key: v, dir: 1 }
    sortOpen = false
  }
  function onDocClick(e) {
    if (sortOpen && sortEl && !sortEl.contains(e.target)) sortOpen = false
  }

  function cardKeydown(e, p) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      if (batchMode) toggleSelect(p.id)
      else openProject(p)
    }
  }

  function sortItems(items) {
    const { key, dir } = sort
    return [...items].sort((a, b) => {
      const av = (a[key] ?? '').toString().toLowerCase()
      const bv = (b[key] ?? '').toString().toLowerCase()
      if (av < bv) return -dir
      if (av > bv) return dir
      return 0
    })
  }

  function openProject(p) {
    try {
      const recents = JSON.parse(localStorage.getItem('recent_projects') || '[]')
      const fresh = [{ id: p.id, nume: p.nume, client: p.client, tip: p.tip },
        ...recents.filter(r => r.id !== p.id)].slice(0, 6)
      localStorage.setItem('recent_projects', JSON.stringify(fresh))
    } catch (_) {}
    navigate(`/projects/${p.id}`)
  }

  onMount(() => { loadProjects() })

  const activeItems = $derived(sortItems(projects.items.filter(p => p.status !== 'finalizat')))
  const archivedItems = $derived(sortItems(projects.items.filter(p => p.status === 'finalizat')))
</script>

<svelte:document onclick={onDocClick} />

<div class="page">
  <div class="page-header">
    <div class="page-title-row">
      <FolderKanban size={22} />
      <h1>Proiecte</h1>
      <span class="count">{projects.items.length}</span>
    </div>
    <div class="header-btns">
      <!-- „Selectează" lua jumatate din antet pentru un mod in care intri o data
           pe luna. Pe telefon ramane doar iconita; „Proiect Nou" devine „Nou". -->
      <button class="b-select" class:on={batchMode} onclick={toggleBatch}
              title="Selectează mai multe" aria-pressed={batchMode}>
        <CheckSquare size={ecran.telefon ? 17 : 14} />
        {#if !ecran.telefon}<span>Selectează</span>{/if}
      </button>
      <Button size="sm" onclick={() => showNewModal = true}><Plus size={14} /> {ecran.telefon ? 'Nou' : 'Proiect Nou'}</Button>
    </div>
  </div>

  <!-- TOT CE TINE DE SELECTIE INTR-O SINGURA BARA. Era imprastiat in trei locuri:
       butonul in antet, „Selectează toate" ca al patrulea element in bara de
       filtre si actiunile intr-o a treia bara care se deschidea dedesubt — trei
       asezari pentru o singura stare, si niciun „ieși" limpede. Bara apare acum
       de la INTRAREA in mod, nu abia dupa prima bifa, ca sa aiba unde sta iesirea. -->
  {#if batchMode}
    <div class="batch-bar" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
      <span class="batch-count">{selected.size} selectate</span>
      <button class="select-all" onclick={toggleSelectAll}>
        {#if selected.size === activeItems.length && activeItems.length > 0}<CheckSquare size={14} />{:else}<Square size={14} />{/if}
        Selectează toate
      </button>
      <Select size="sm" bind:value={batchStatus} placeholder="Schimbă status..." options={batchStatusOptions} aria-label="Schimbă status" />
      <Button size="sm" disabled={!batchStatus || selected.size === 0 || batchBusy} onclick={batchUpdateStatus}>Aplică</Button>
      <Button size="sm" variant="danger" disabled={selected.size === 0 || batchBusy} onclick={() => showBatchDelete = true}><SolidIcon name="trash" size={12} /> Șterge</Button>
      <Button size="sm" variant="ghost" onclick={toggleBatch}>Ieși</Button>
    </div>
  {/if}

  <div class="toolbar">
    <!-- PAGINA PROIECTE NU ARE CAMP DE CAUTARE.
         Sunt 21 de proiecte si se vad TOATE, in grila de sub bara asta. Un camp
         de cautare peste o lista pe care o cuprinzi din ochi nu scurteaza nimic
         — te pune sa scrii ca sa ajungi unde ajungeai uitandu-te. Cautarea care
         chiar cauta (peste note, taskuri, clienti) traieste in paleta din dock. -->
    <div class="sort-box" bind:this={sortEl}>
      <button class="sort-trigger" class:on={sortOpen} onclick={() => sortOpen = !sortOpen} title="Sortare: {sortLabel} {sort.dir === 1 ? '\u2191' : '\u2193'}" aria-haspopup="listbox" aria-expanded={sortOpen}>
        <ArrowUpDown size={ecran.telefon ? 17 : 13} />
        {#if !ecran.telefon}
          <span>{sortLabel}</span>
          <span class="sort-dir-ind">{sort.dir === 1 ? '\u2191' : '\u2193'}</span>
        {/if}
      </button>
      {#if sortOpen}
        <div class="sort-menu" role="listbox" transition:fly={{ y: -4, duration: motionDuration(DUR_FAST) }}>
          {#each sortOptions as opt (opt.value)}
            <button class="sort-opt" class:sel={sort.key === opt.value} role="option" aria-selected={sort.key === opt.value} onclick={() => pickSort(opt.value)}>
              <span>{opt.label}</span>
              {#if sort.key === opt.value}<span class="sort-dir-ind">{sort.dir === 1 ? '\u2191' : '\u2193'}</span>{/if}
            </button>
          {/each}
        </div>
      {/if}
    </div>
    <!-- Arhiva e o DESTINATIE rara, nu un filtru — deci aceeasi haina de
         actiune-fantoma ca sortarea de langa ea, si ca „Arhivă" din /tasks. -->
    {#if archivedItems.length > 0}
      <button class="a-ico" class:on={showArchive} onclick={() => showArchive = !showArchive}
              title="Arhivă ({archivedItems.length} finalizate)" aria-pressed={showArchive}>
        <Archive size={ecran.telefon ? 17 : 14} />
        {#if !ecran.telefon}<span>Arhivă</span>{/if}
        <span class="a-n">{archivedItems.length}</span>
      </button>
    {/if}
  </div>

  <!-- SCHELETELE SUNT PENTRU PRIMA INCARCARE, NU PENTRU FIECARE ACTIUNE —
       aceeasi regula pe care o au deja Taskuri, boardul „Astăzi" si
       Planificatorul. `loadProjects()` se cheama dupa comutarea statusului de pe
       card, dupa stergere si la fiecare filtru, iar fara garda toata grila era
       inlocuita cu sase schelete si reconstruita la fiecare atingere. -->
  {#if projects.loading && projects.items.length === 0}
    <div class="cards-grid">
      {#each Array(6) as _}
        <div class="pcard skeleton-card"><Skeleton width="40%" height="14px" /><Skeleton width="70%" height="18px" /><Skeleton width="50%" height="12px" /></div>
      {/each}
    </div>
  {:else if projects.error}
    <ErrorState message={projects.error} onretry={() => loadProjects()} />
  {:else if activeItems.length === 0 && archivedItems.length === 0}
    <EmptyState icon={FolderKanban} title="Niciun proiect" description="Nu există proiecte cu filtrele selectate." />
  {:else}
    <div class="cards-grid">
      {#each activeItems as p, i (p.id)}
        {@const urm = urmatoarea(p)}
        <div class="pcard cell-in" style="--celula: {i}" class:batch-selected={batchMode && selected.has(p.id)} role="button" tabindex="0" animate:flip={{ duration: motionDuration(DUR_BASE) }} onclick={(e) => { if (batchMode) { e.stopPropagation(); toggleSelect(p.id) } else openProject(p) }} onkeydown={(e) => cardKeydown(e, p)}>
          <div class="card-top">
            {#if batchMode}
              <button class="batch-check card-check" onclick={(e) => { e.stopPropagation(); toggleSelect(p.id) }}>
                {#if selected.has(p.id)}<CheckSquare size={16} />{:else}<Square size={16} />{/if}
              </button>
            {/if}
            <!-- TIPUL, SPUS O SINGURA DATA. Era un fulger amber intr-un chip
                 patrat PLUS cuvantul „PIF" — doua obiecte pentru un fapt care nu
                 se schimba niciodata, chiar langa pastila de status, care se
                 schimba. Iconita ramane, fara fill: linie subtire, gri, lipita de
                 cuvant. Culoarea din coltul de sus ramane DOAR la status.
                 Asta stinge si defectul „un fapt, doua culori": „Service" era
                 verde pe card (--success) si amber in arhiva (--service-accent). -->
            {#if p.tip}
              <span class="tip-ico">{#if p.tip === 'PIF'}<Zap size={13} strokeWidth={1.7} />{:else}<Wrench size={13} strokeWidth={1.7} />{/if}</span>
              <span class="tip-label">{p.tip}</span>
            {:else}<span class="tip-label">—</span>{/if}
            <!-- PE TOUCH E ETICHETA, NU BUTON. Pastila are 22px si sta in
                 interiorul zonei de atingere a cardului: o atingere usor deviata
                 ori deschide proiectul, ori ii schimba statusul, si nu se poate
                 sti dinainte care. Un card = o tinta; statusul se schimba din
                 pagina proiectului. Pe desktop ramane control — dar unul care
                 ARATA ca un control: fill discret + chevron, nu o eticheta. -->
            {#if ecran.telefon}
              <span class="status-pill" style="--st: {STATUS_COLORS[p.status] || 'var(--text-dim)'}">{PROJECT_STATUS_LABELS[p.status] || p.status || '—'}</span>
            {:else}
              <button class="status-pill act" style="--st: {STATUS_COLORS[p.status] || 'var(--text-dim)'}" onclick={(e) => cycleProjectStatus(e, p)} title="Schimbă statusul">
                {PROJECT_STATUS_LABELS[p.status] || p.status || '—'}<ChevronDown size={11} strokeWidth={2.2} />
              </button>
            {/if}
          </div>
          <div class="card-name">{p.nume || '—'}</div>
          <div class="card-client">{p.client || '—'}</div>
          <div class="card-foot" title={urm.data}>
            {#if urm.faza}<span class="foot-faza">{urm.faza}</span>{/if}
            <span class="foot-cand" class:urgent={urm.urgent}>{urm.cand}</span>
          </div>
        </div>
      {/each}
      {#if !batchMode}
        <button class="pcard new-card cell-in" style="--celula: {activeItems.length}" onclick={() => showNewModal = true}>
          <span class="new-plus">+</span>
          <span class="new-label">Proiect nou</span>
        </button>
      {/if}
    </div>

    <!-- Arhiva se deschide din bara de sus; aici ramane doar continutul, cu un
         cap de sectiune care spune unde esti. -->
    {#if archivedItems.length > 0 && showArchive}
      <div class="archive" transition:slide={{ duration: motionDuration(DUR_BASE) }}>
        <div class="arch-cap"><Archive size={13} /><span>Arhivă · finalizate</span><span class="grup-n">{archivedItems.length}</span></div>
        <div class="arch-list">
          {#each archivedItems as p (p.id)}
            <button class="arch-row archived" animate:flip={{ duration: motionDuration(DUR_BASE) }} onclick={() => openProject(p)}>
              <span class="arch-name">{p.nume || '—'}</span>
              <span class="dim arch-client">{p.client || '—'}</span>
              <!-- Acelasi tip, aceeasi haina ca pe card: linie subtire + cuvant.
                   Aici statea ca pastila colorata — a doua definitie a aceluiasi
                   fapt, si tocmai cea care nu se potrivea cu prima. -->
              {#if p.tip}<span class="ptip"><span class="tip-ico">{#if p.tip === 'PIF'}<Zap size={12} strokeWidth={1.7} />{:else}<Wrench size={12} strokeWidth={1.7} />{/if}</span>{p.tip}</span>{/if}
              <span class="arch-tail">
                <Badge label="Finalizat" color="var(--success)" small />
                <span class="dim arch-deadline">{p.urmatoarea ? formatDate(p.urmatoarea) : '—'}</span>
              </span>
            </button>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>

<ProjectFormModal bind:open={showNewModal} onsaved={() => loadProjects()} />
<ConfirmDialog bind:open={showBatchDelete} title="Șterge proiecte" message={`Ștergi ${selected.size} proiecte selectate? Această acțiune este ireversibilă.`} confirmLabel="Șterge" onconfirm={batchDeleteSelected} />

<style>
  .page { padding: var(--space-lg); }
  /* `flex-wrap` + `gap`: fara ele randul nu se putea rupe, iar „Selectează" si
     „Proiect Nou" nu se puteau micsora sub textul lor — deci ieseau din ecran si
     `.app-main { overflow-x: clip }` le taia in tacere. Pe 375px „Proiect Nou"
     era retezat de marginea din dreapta. Acum, cand nu incap langa titlu, coboara
     pe randul lor si il umplu. */
  .page-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); flex-wrap: wrap; margin-bottom: var(--space-md); }
  .page-title-row { min-width: 0; }
  .page-title-row h1 { overflow-wrap: anywhere; }
  .page-title-row { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-title); font-weight: var(--fw-semibold); }
  /* `.count` a plecat in global.css — vezi nota din Tasks.svelte. */

  .toolbar { display: flex; gap: var(--space-md); align-items: center; margin-bottom: var(--space-md); flex-wrap: wrap; }

  /* Arhiva si „Selectează": actiuni-fantoma, aceeasi haina cu sortarea de langa
     ele si cu „Arhivă" din /tasks. Nu sunt filtre, deci nu poarta chip. */
  .a-ico, .b-select { display: inline-flex; align-items: center; gap: 6px;
    min-height: 30px; padding: 0 10px; border-radius: var(--radius-sm);
    background: transparent; border: 1px solid transparent;
    font-size: var(--font-small); font-weight: var(--fw-medium);
    color: var(--text-faint); cursor: pointer; transition: var(--transition-colors); }
  .a-ico:hover, .b-select:hover { color: var(--text); background: var(--bg-hover); }
  .a-ico.on, .b-select.on { background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .a-n { font-family: var(--font-mono); color: var(--text-dim); font-variant-numeric: tabular-nums; }
  .a-ico.on .a-n { color: inherit; }

  /* Sortare — control ghost discret + meniu custom; click pe optiunea
     activa inverseaza directia (sageata arata directia curenta). */
  .sort-box { position: relative; }
  .sort-trigger { display: inline-flex; align-items: center; gap: 6px; min-height: 30px; padding: 4px 12px; font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-dim); background: transparent; border: 1px solid transparent; border-radius: var(--radius-full); cursor: pointer; transition: var(--transition-colors); }
  .sort-trigger:hover { color: var(--text); background: var(--bg-hover); }
  .sort-trigger.on { color: var(--accent-on-subtle); background: var(--accent-subtle); border-color: var(--accent); }
  .sort-dir-ind { font-size: var(--font-small); opacity: .8; }
  .sort-menu { position: absolute; top: calc(100% + 5px); right: 0; z-index: var(--z-dropdown, 50); min-width: 150px; background: var(--bg-overlay); border: 1px solid var(--border-strong); border-radius: var(--radius-md); box-shadow: var(--shadow-lg); padding: 4px; }
  .sort-opt { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); width: 100%; padding: 7px 10px; border-radius: var(--radius-sm); color: var(--text-secondary); font-size: var(--font-small); background: transparent; border: none; text-align: left; cursor: pointer; }
  .sort-opt:hover { background: var(--bg-hover); color: var(--text); }
  .sort-opt.sel { background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .select-all { display: inline-flex; align-items: center; gap: 6px; font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-secondary); cursor: pointer; padding: 4px 10px; border-radius: var(--radius-sm); background: var(--bg-input); border: 1px solid var(--border); }
  .select-all:hover { color: var(--text); border-color: var(--border-strong); }

  .cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 14px; }
  /* HOVERUL RASPUNDE IN `--dur-fast`, CA RESTUL APLICATIEI. Cardul urca 4px pe
     `--dur-base` (240ms), in timp ce orice alta suprafata raspunde la cursor in
     120ms: la 240ms cursorul apucase deja sa plece de pe card inainte ca el sa fi
     terminat de urcat. Hoverul e raspunsul la o intentie care inca se formeaza —
     trebuie sa ajunga inaintea deciziei, nu dupa. Ridicarea ramane 4px; doar
     viteza se aliniaza. */
  .pcard { position: relative; display: flex; flex-direction: column; min-height: 132px; background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); padding: 18px 20px; cursor: pointer; text-align: left; transition: box-shadow var(--dur-fast) var(--ease); }
  /* Doar unde exista cursor. Pe touch, cardul atins ramanea ridicat cu 4px si cu
     umbra pana atingeai altceva — parea selectat, desi nu era. */
  @media (hover: hover) {
    .pcard:hover { box-shadow: var(--shadow-md); }
  }
  .pcard:active { border-color: var(--border-strong); }
  .pcard:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .pcard.batch-selected { background: var(--accent-subtle); border-color: var(--accent); }
  /* dim, nu faint: „Proiect nou" e o actiune de citit, nu o eticheta —
     masurat 3.18:1 la 12.8px, sub AA. Cardul ramane discret prin rama
     punctata si fundalul gol, nu prin text ilizibil. */
  .pcard.new-card { border-style: dashed; align-items: center; justify-content: center; gap: 6px; color: var(--text-dim); background: transparent; }
  .pcard.new-card:hover { color: var(--accent); border-color: var(--accent); box-shadow: none; }
  .new-plus { font-size: var(--font-h2); line-height: 1; }
  .new-label { font-size: var(--font-small); font-weight: var(--fw-semibold); }
  .card-top { display: flex; align-items: center; gap: var(--space-xs); margin-bottom: 10px; }
  .card-top { display: flex; align-items: center; }
  .card-top .status-pill { margin-left: auto; }
  .card-check { width: auto; height: auto; }
  /* Numele proiectului urca pe `--font-h2`: e numele unui lucru, deci poarta
     fontul de titlu la o treapta care EXISTA. Era la 1.05rem — o marime pe care
     n-o numea niciun token, intre h3 si body, aleasa o data si ramasa acolo. */
  .card-name { font-family: var(--font-heading); font-size: var(--font-h2); font-weight: var(--fw-semibold); letter-spacing: var(--tracking-tight); color: var(--text); line-height: var(--lh-snug); overflow-wrap: anywhere; }
  /* --text-dim, nu faint: numele clientului e INFORMATIE, nu eticheta —
     iar faint e documentat „doar etichete/large" (3:1). Masurat: 3.18:1 la
     11.2px, sub pragul AA de 4.5 pentru text mic. */
  .card-client { font-size: var(--font-small); color: var(--text-dim); margin-top: 2px; }
  /* Doua trepte, nu una: faza e ETICHETA (micro, uppercase, faint), socoteala e
     INFORMATIE (tiny, mono) si poarta singura culoarea. Data plina sta in
     `title` — nu ocupa un rand pentru ceva ce verifici cand cauti. */
  .card-foot { margin-top: auto; padding-top: 14px; display: flex; align-items: baseline; gap: 7px; }
  .foot-faza { font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-faint); }
  .foot-cand { font-family: var(--font-mono); font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-secondary); }
  .foot-cand.urgent { color: var(--danger); font-weight: var(--fw-semibold); }
  .skeleton-card { gap: 8px; cursor: default; }

  .dim { color: var(--text-secondary); }
  /* Tipul e o LINIE, nu un fill: aceeasi definitie pe card si in arhiva. */
  .tip-ico { display: inline-flex; align-items: center; color: var(--text-faint); flex-shrink: 0; }
  .ptip { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-faint); }
  .tip-label { font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-faint); margin-left: 7px; }

  .archive { margin-top: var(--space-lg); }
  .arch-cap { display: flex; align-items: center; gap: var(--space-xs);
    padding: 0 2px var(--space-sm); color: var(--text-faint);
    font-family: var(--font-mono); font-size: var(--font-label);
    font-weight: var(--fw-semibold); text-transform: uppercase;
    letter-spacing: var(--tracking-label); }
  .grup-n { display: inline-flex; align-items: center; justify-content: center;
    min-width: 17px; height: 17px; padding: 0 5px; border-radius: var(--radius-full);
    background: var(--success-subtle); color: var(--success);
    font-family: var(--font-mono); font-size: var(--font-small);
    line-height: 1; font-variant-numeric: tabular-nums; }
  /* NICIO OPACITATE PE UN RAND DE TEXT (regula sistemului). Ca e arhivat o spune
     ANTETUL sectiunii, sub care randul chiar sta — nu o stingere care se inmulteste
     peste tokenuri deja la limita si scoate randul sub AA. */
  .archived .arch-name { color: var(--text-secondary); }
  .arch-list { display: flex; flex-direction: column; background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); overflow: hidden; }
  .arch-row { display: flex; align-items: center; gap: var(--space-sm); width: 100%; padding: 10px 16px; font-size: var(--font-small); color: var(--text); text-align: left; cursor: pointer; background: transparent; border: none; border-bottom: 1px solid var(--border); transition: background var(--dur-fast) var(--ease); }
  .arch-row:last-child { border-bottom: none; }
  .arch-row:hover { background: var(--bg-hover); opacity: 1; }
  .arch-name { font-weight: var(--fw-medium); }
  .arch-client { font-size: var(--font-small); }
  .arch-tail { margin-left: auto; display: inline-flex; align-items: center; gap: var(--space-sm); }
  .arch-deadline { font-size: var(--font-small); font-family: var(--font-mono); }

  .header-btns { display: flex; gap: var(--space-xs); }
  .batch-bar { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) var(--space-md); background: var(--accent-subtle); border: 1px solid color-mix(in srgb, var(--accent) 25%, transparent); border-radius: var(--radius-md); margin-bottom: var(--space-md); flex-wrap: wrap; }
  .batch-count { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--accent); }
  .batch-check { display: flex; align-items: center; justify-content: center; color: var(--text-dim); cursor: pointer; background: transparent; border: none; padding: 0; }
  .batch-check:hover { color: var(--accent); }
  /* Fill discret in loc de contur gol: o pastila conturata se citeste ca eticheta,
     iar asta comuta statusul. Chevronul o spune fara `title`. Culoarea vine din
     `--st` (STATUS_COLORS), deci fondul se deduce din ea — o singura regula
     pentru amandoua statusurile, nu doua tokenuri scrise de mana. */
  .status-pill { display: inline-flex; align-items: center; gap: 4px;
    margin-left: auto; font-size: var(--font-small); font-weight: var(--fw-semibold);
    padding: 2px 10px; min-height: 22px; border-radius: var(--radius-full);
    color: var(--st); background: color-mix(in oklab, var(--st) 13%, transparent);
    border: 1px solid transparent; white-space: nowrap; }
  .status-pill.act { padding-right: 8px; cursor: pointer;
    transition: border-color var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); }
  .status-pill.act :global(svg) { opacity: .6; }
  @media (hover: hover) {
    .status-pill.act:hover { border-color: var(--st); }
  }
  .status-pill.act:active { transform: scale(var(--press-scale-sm)); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    /* ACELASI RITM CA /tasks (decizia din 2026-07-30: „aceleasi elemente, ~30px
       mai sus"). Masurat aici inainte: primul card incepea la y=314 pe 390×844 —
       37% din ecran, exact procentul pentru care /tasks a fost strans; pagina
       asta ramasese in urma. Nimic nu dispare, doar distantele. */
    .page { padding-top: var(--space-12); }
    .page-header, .toolbar, .batch-bar { margin-bottom: 10px; }
    /* UN RAND DE BARA, NU TREI. Reparatia de dinainte a scazut doar marginile de
       la 16 la 10 — dar cei 37% pana la primul card erau ELEMENTELE, nu
       distantele: cautare, trei chipuri si sortare, fiecare pe randul lui, ~150px.
       Cu chipurile scoase si cu sortarea si arhiva ca iconite de 44px, totul intra
       pe un rand: primul card urca de la y≈314 la y≈224 — un card intreg castigat. */
    .toolbar { flex-direction: row; align-items: center; gap: var(--space-sm); }
    /* Caseta are 44px, dar inputul dinauntru avea 25 — iar el e singurul care
       primeste focus (caseta e un <div>, nu un <label>), deci tinta reala era de
       25px. `align-self: stretch` il face sa umple caseta. */
    .batch-bar { flex-direction: column; align-items: stretch; }

    /* Iconite patrate de 44px: eticheta e in `title`, forma o spune. */
    .sort-trigger, .a-ico, .b-select {
      width: var(--tap-min); height: var(--tap-min); min-height: var(--tap-min);
      padding: 0; justify-content: center; flex-shrink: 0;
      border-radius: var(--radius-md); }
    /* Contorul arhivei ar dubla latimea iconitei; numarul se citeste oricum din
       lista cand o deschizi. */
    .a-n { display: none; }
    /* PASTILA DE STATUS E ETICHETA PE TOUCH (vezi markup: nici nu mai e <button>),
       deci stratul invizibil de 44px din jurul ei — care fura atingeri de la card
       — a plecat cu totul. Un card = o tinta. */
    /* „Proiect Nou" ramane singurul buton cu text si primeste latimea ramasa. */
    .header-btns :global(.btn) { min-height: var(--tap-min); }
  }

  @media (max-width: 560px) {
    .cards-grid { grid-template-columns: 1fr; }
  }
</style>
