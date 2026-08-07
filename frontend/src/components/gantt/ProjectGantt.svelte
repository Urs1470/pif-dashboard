<script>
  import { onMount } from 'svelte'
  import { Diamond, Milestone, FileDown, Sheet, ChevronRight, MapPin, Building2, CheckCircle2 } from '@lucide/svelte'
  import ImplPeriodModal from '../projects/ImplPeriodModal.svelte'
  import { apiJson } from '../../lib/api.js'
  import { buildColumns, spanRect, dayDiff, addDays, localToday } from '../../lib/planDates.js'
  import { formatDateShort } from '../../lib/formatters.js'
  import Skeleton from '../ui/Skeleton.svelte'
  import EmptyState from '../ui/EmptyState.svelte'

  // Read-only Gantt: tasks are inherited from the Tasks tab (no editing here).
  // The only editable thing is the implementation period (Site / Sediu EGB).
  let { projectId, onOpenTask } = $props()

  let data = $state({ proiect: null, tasks: [], dependencies: [], implementari: [] })
  let loading = $state(true)
  let error = $state(null)

  async function load() {
    loading = true; error = null
    try {
      data = await apiJson(`/api/proiecte/${projectId}/gantt`)
    } catch (e) { error = e.message } finally { loading = false }
  }
  onMount(load)

  const today = localToday()

  // Auto-fit the window to the project's real span (tasks + project dates + periods), padded.
  const win = $derived.by(() => {
    const ds = []
    for (const t of data.tasks) {
      if (t.data_start) ds.push(t.data_start.slice(0, 10))
      if (t.data_scadenta) ds.push(t.data_scadenta.slice(0, 10))
    }
    for (const im of (data.implementari || [])) {
      if (im.data_start) ds.push(im.data_start.slice(0, 10))
      if (im.data_sfarsit) ds.push(im.data_sfarsit.slice(0, 10))
    }
    ds.push(today)
    const lo = ds.reduce((a, b) => a < b ? a : b)
    const hi = ds.reduce((a, b) => a > b ? a : b)
    const start = addDays(lo, -2)
    let days = (dayDiff(start, hi) || 0) + 4
    days = Math.max(14, days)
    return { start, days }
  })

  const columns = $derived(buildColumns(win.start, win.days))
  const unit = $derived(columns.unit)
  const todayIdx = $derived(dayDiff(win.start, today))
  const colMin = $derived(unit === 'day' ? (win.days <= 21 ? 40 : 30) : unit === 'week' ? 60 : 90)
  const contentMin = $derived(colMin * columns.cols.length)

  function statusClass(t) {
    if (t.status === 'done' || t.status === 'finalizat') return 'done'
    if (t.status === 'in_progress' || t.status === 'in_lucru') return 'prog'
    return 'todo'
  }
  const isDone = (t) => statusClass(t) === 'done'
  function pctFor(iso) {
    const di = dayDiff(win.start, (iso || '').slice(0, 10))
    if (di == null) return null
    return ((di + 0.5) / win.days) * 100
  }
  function msPct(t) { return pctFor(t.data_start || t.data_scadenta) }
  // A task is a point marker at its due date. If it has a real multi-day span,
  // a thin connector line runs start→due behind the dot. Single-day tasks (Ion's
  // usual case) show as a visible dot instead of an invisible 3px sliver.
  function taskMark(t) {
    const due = (t.data_scadenta || t.data_start || '').slice(0, 10)
    const end = pctFor(due)
    if (end == null) return null
    const start = (t.data_start || '').slice(0, 10)
    let s = null
    if (start && start < due) { const sp = pctFor(start); if (sp != null) s = sp }
    return { end, start: s }
  }
  function implRect(im) { return spanRect(im.data_start, im.data_sfarsit, win.start, win.days) }
  function locLabel(l) { return l === 'sediu' ? 'Sediu EGB' : 'Site' }

  // Sub-randul unui task: data, o SINGURA data. Inainte, un task de o zi scria
  // „31 iul. → 31 iul.", iar chipul din dreapta repeta acelasi „31 iul." — plus
  // pozitia pe timeline. Trei exprimari ale aceleiasi zile.
  function metaText(t) {
    const s = t.data_start ? t.data_start.slice(0, 10) : ''
    const e = t.data_scadenta ? t.data_scadenta.slice(0, 10) : ''
    if (t.is_milestone) return s ? formatDateShort(s) : '—'
    if (s && e && s !== e) return `${formatDateShort(s)} → ${formatDateShort(e)}`
    return formatDateShort(e || s) || '—'
  }
  // Chipul din dreapta spune doar ce NU se vede deja: relatia cu ziua de azi.
  // Cand ar fi doar o data, tace — data e deja pe randul de sub titlu.
  function dueInfo(t) {
    if (isDone(t)) return null
    const d = t.data_scadenta ? t.data_scadenta.slice(0, 10) : ''
    if (!d) return null
    const k = dayDiff(today, d)
    if (k == null) return null
    if (k < 0) return { text: 'depășit', cls: 'hot' }
    if (k === 0) return { text: 'azi', cls: 'warm' }
    if (k === 1) return { text: 'mâine', cls: 'warm' }
    return null
  }
  // `sevColor()` a plecat: era a DOUA definitie a aceleiasi axe (cea din
  // formatters.js), si singurii ei consumatori erau indexul `.tix` — scos din
  // liste in tura 1 — si dunga de 3px de pe rand, scoasa acum. Ganttul n-are bifa
  // pe rand, deci severitatea ramane unde se citea oricum: in chipul din dreapta
  // (`dueInfo`), care e text, nu muchie.

  // Gruparea pe faze (WBS) a plecat in v32: coloana `tasks.faza` nu putea fi
  // completata din nicio interfata, deci antetele de faza nu s-au randat niciodata.

  // Intr-un Gantt, DIAGONALA e ce se citeste. Randurile veneau in ordinea `ordine`
  // (manuala), deci sareau inainte si inapoi in timp — ochiul nu putea urmari nimic.
  function ziTask(t) {
    return (t.data_start || t.data_scadenta || '').slice(0, 10) || '9999-12-31'
  }

  // Peste jumatate din randuri erau istorie (5 din 8 finalizate), taiate cu linie
  // dar ocupand rand intreg. Ascunse implicit, la un click distanta.
  let araFinalizate = $state(false)
  const nrFinalizate = $derived(data.tasks.filter(isDone).length)

  const displayRows = $derived.by(() => {
    const rows = []
    for (const im of (data.implementari || [])) rows.push({ kind: 'impl', im })
    const vizibile = (araFinalizate ? data.tasks : data.tasks.filter(t => !isDone(t)))
      .slice()
      .sort((a, b) => ziTask(a).localeCompare(ziTask(b)))
    // Fara numar de rand: singurul lui consumator era indexul din `.tix`, scos mai jos.
    for (const t of vizibile) rows.push({ kind: 'task', t })
    return rows
  })

  // PREGATIREA = golul dintre etapele de implementare (vezi Planificator).
  // Aici e locul ei cel mai firesc: cronologia proprie a proiectului.
  const segmentePregatire = $derived.by(() => {
    if (data.proiect?.status === 'finalizat') return []
    const etape = (data.implementari || [])
      .filter(im => im.data_start && (im.faza || 'implementare') === 'implementare')
      .map(im => ({ a: im.data_start.slice(0, 10), b: (im.data_sfarsit || im.data_start).slice(0, 10) }))
      .sort((x, y) => x.a.localeCompare(y.a))
    // `data_incepere` a plecat in v36, deci nu mai exista o zi „de cand se
    // pregateste". Pornim de la marginea ferestrei — prima zi planificata a
    // proiectului, task sau perioada — ca in Planificator. Daca ar porni de la
    // prima etapa, pregatirea de dinaintea ei ar avea latime zero.
    const inceput = win.start
    const out = []
    let cursor = inceput
    for (const e of etape) {
      if (cursor < e.a) out.push({ de: cursor, la: addDays(e.a, -1), deschis: false })
      if (e.b >= cursor) cursor = addDays(e.b, 1)
    }
    // Ca in Planificator: dupa ultima etapa nu mai e pregatire. Segmentul deschis
    // rămâne doar cand nu exista nicio etapa fixata.
    if (etape.length === 0) out.push({ de: cursor, la: '', deschis: true })
    return out
      .map(seg => {
        const capat = seg.deschis ? addDays(win.start, win.days) : seg.la
        const rect = spanRect(seg.de, capat, win.start, win.days)
        return rect ? { ...seg, rect } : null
      })
      .filter(Boolean)
  })

  // implementation-period editor (the one editable thing here)
  let implOpen = $state(false)
  let implEditing = $state(null)
  function newImpl() { implEditing = null; implOpen = true }
  function editImpl(im) { implEditing = im; implOpen = true }

  function openTask(t) { onOpenTask?.(t.id) }
</script>

{#if loading}
  <div class="gk">{#each Array(5) as _}<Skeleton height="46px" />{/each}</div>
{:else if error}
  <p class="g-err">Eroare: {error}</p>
{:else if data.tasks.length === 0 && (data.implementari || []).length === 0}
  <EmptyState icon={Milestone} title="Nimic de arătat" description="Taskurile apar aici automat din tabul „Taskuri”. Adaugă o perioadă de implementare (Site / Sediu EGB) ca să apară pe diagramă.">
    <div class="es-actions">
      <button class="exp-btn" onclick={newImpl}><MapPin size={15} /> Perioadă</button>
    </div>
  </EmptyState>
{:else}
  <div class="g-toolbar">
    <div class="g-tl">
      <button class="exp-btn" onclick={newImpl} title="Adaugă perioadă de implementare (Site / Sediu EGB)"><MapPin size={14} /> Perioadă</button>
      <a class="exp-btn" href={`/api/proiecte/${projectId}/gantt.pdf`} target="_blank" rel="noopener" title="Export PDF (client)"><FileDown size={14} /> PDF</a>
      <a class="exp-btn" href={`/api/proiecte/${projectId}/gantt.xlsx`} title="Export Excel"><Sheet size={14} /> Excel</a>
    </div>
    <span class="g-legend">
      {#if nrFinalizate}
        <button class="lg-btn" onclick={() => araFinalizate = !araFinalizate}>
          {araFinalizate ? 'ascunde' : 'arată'} finalizate · {nrFinalizate}
        </button>
      {/if}
      <span class="lg"><span class="dot done leg"></span>finalizat</span>
      <span class="lg"><span class="dot prog leg"></span>în lucru</span>
      <span class="lg"><span class="dot todo leg"></span>de făcut</span>
      <span class="lg"><span class="sw-ms"></span>milestone</span>
      <span class="lg"><span class="sw" style="background:var(--loc-site)"></span>site</span>
      <span class="lg"><span class="sw" style="background:var(--loc-sediu)"></span>sediu</span>
    </span>
  </div>

  <div class="gantt2">
    <!-- left: read-only task list -->
    <div class="g-table">
      <div class="gh-row lhead"><span>Activități</span></div>
      {#each displayRows as row (row.kind === 'impl' ? 'i:' + row.im.id : row.t.id)}
        {#if row.kind === 'impl'}
          <button class="impl-lrow loc-{row.im.locatie}" onclick={() => editImpl(row.im)} title="Editează perioada">
            {#if row.im.locatie === 'sediu'}<Building2 size={14} />{:else}<MapPin size={14} />{/if}
            <span class="impl-lname">{locLabel(row.im.locatie)}{row.im.eticheta ? ' · ' + row.im.eticheta : ''}</span>
          </button>
        {:else}
          {@const t = row.t}
          {@const due = dueInfo(t)}
          <button class="tk-row" class:done={isDone(t)} onclick={() => openTask(t)} title="Deschide în tabul Taskuri">
            <!-- Doar semnul de bifat. Numarul „01 / 02 / 03" a plecat din toate
                 listele in tura 1 (sub 15 taskuri nu spui „fa taskul 07", si era
                 a doua codificare a severitatii pe care o da deja bordura din
                 stanga); Ganttul era ultimul loc unde ramasese. Casuta ramane
                 latita, ca titlurile sa se alinieze intre randuri bifate si nu. -->
            <span class="tk-stare">
              {#if isDone(t)}<CheckCircle2 size={15} />{/if}
            </span>
            <span class="row-content">
              <span class="row-title">{#if t.is_milestone}<Diamond size={11} class="mini-ms" />{/if}{t.titlu}</span>
              <span class="row-meta">{metaText(t)}</span>
            </span>
            {#if due}<span class="due-chip {due.cls}">{due.text}</span>{/if}
            <ChevronRight size={14} class="tk-chev" />
          </button>
        {/if}
      {/each}
    </div>

    <!-- right: read-only timeline -->
    <div class="g-time">
      <div class="g-time-inner" style="min-width:{contentMin}px">
        <div class="gh-row time-head">
          {#each columns.cols as c (c.key)}
            <div class="col-h" class:we={unit === 'day' && c.isWeekend} class:today={c.iso && c.iso === today} style="left:{c.leftPct}%; width:{c.widthPct}%">
              <span class="ch-sub">{c.sub}</span><span class="ch-main">{c.main}</span>
            </div>
          {/each}
        </div>
        <div class="g-body">
          <div class="overlay">
            {#each segmentePregatire as seg, i (i)}
              <div class="prep" class:deschis={seg.deschis}
                   style="left:{seg.rect.left}%; width:{seg.rect.width}%"
                   title="Pregătire{seg.deschis ? ' — următoarea etapă nu e încă fixată' : ''}"></div>
            {/each}
            {#each columns.cols as c (c.key)}
              <div class="col-line" style="left:{c.leftPct}%"></div>
              {#if unit === 'day' && c.isWeekend}<div class="col-we" style="left:{c.leftPct}%; width:{c.widthPct}%"></div>{/if}
            {/each}
            {#if todayIdx != null && todayIdx >= 0 && todayIdx < win.days}
              <div class="today-line" style="left:{(todayIdx / win.days) * 100}%"></div>
            {/if}
          </div>
          {#each displayRows as row (row.kind === 'impl' ? 'i:' + row.im.id : row.t.id)}
            {#if row.kind === 'impl'}
              {@const ir = implRect(row.im)}
              <div class="gb-row impl-track">
                {#if ir}
                  <button class="impl-band loc-{row.im.locatie}" class:pregatire={(row.im.faza || 'implementare') === 'pregatire'}
                          style="left:{ir.left}%; width:{ir.width}%" onclick={() => editImpl(row.im)}
                          title="{locLabel(row.im.locatie)} · {(row.im.faza || 'implementare') === 'pregatire' ? 'pregătire' : 'implementare'} · {formatDateShort(row.im.data_start)} → {formatDateShort(row.im.data_sfarsit)}">
                    {#if row.im.locatie === 'sediu'}<Building2 size={11} class="ib-ico" />{:else}<MapPin size={11} class="ib-ico" />{/if}
                    <span class="ib-txt">{locLabel(row.im.locatie)}{row.im.eticheta ? ' · ' + row.im.eticheta : ''}</span>
                  </button>
                {/if}
              </div>
            {:else}
              {@const t = row.t}
              {@const mk = taskMark(t)}
              {@const mp = t.is_milestone ? msPct(t) : (mk ? mk.end : null)}
              <div class="gb-row">
                {#if mp != null}
                  {#if !t.is_milestone && mk.start != null}<div class="tk-line {statusClass(t)}" style="left:{mk.start}%; width:{mk.end - mk.start}%"></div>{/if}
                  {#if t.is_milestone}
                    <div class="ms" style="left:{mp}%" title="{t.titlu} · {formatDateShort(t.data_start)}"></div>
                  {:else}
                    <div class="dot {statusClass(t)}" style="left:{mp}%" title="{t.titlu} · {formatDateShort(t.data_scadenta || t.data_start)}"></div>
                  {/if}
                {/if}
              </div>
            {/if}
          {/each}
        </div>
      </div>
    </div>
  </div>
{/if}

<ImplPeriodModal bind:open={implOpen} projectId={projectId} period={implEditing} onsaved={load} />

<style>
  .gk { display: flex; flex-direction: column; gap: 6px; }
  .g-err { color: var(--danger); padding: var(--space-md); }
  .es-actions { display: flex; gap: var(--space-sm); flex-wrap: wrap; justify-content: center; }

  .g-toolbar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); margin-bottom: var(--space-sm); flex-wrap: wrap; }
  .g-tl { display: flex; align-items: center; gap: var(--space-sm); flex-wrap: wrap; }
  .exp-btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 12px; border-radius: var(--radius-md); background: var(--bg-panel); border: 1px solid var(--border); color: var(--text-secondary); font-size: var(--font-small); font-weight: var(--fw-medium); cursor: pointer; text-decoration: none; }
  .exp-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-subtle); }
  .g-legend { flex-wrap: wrap; justify-content: flex-end; row-gap: 4px; display: flex; gap: 12px; flex-wrap: wrap; }
  .lg-btn { font-size: var(--font-small); padding: 2px 9px; border-radius: var(--radius-full);
    border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-secondary); cursor: pointer; }
  .lg-btn:hover { border-color: var(--accent); color: var(--accent); }
  .lg { display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-small); color: var(--text-dim); font-family: var(--font-mono); }
  .sw { width: 18px; height: 10px; border-radius: 3px; }
  .sw.done { background: var(--success); } .sw.prog { background: var(--accent); }
  .sw.todo { background: var(--bg-elevated); border: 1px solid var(--border-strong); }
  .sw-ms { width: 10px; height: 10px; background: var(--accent); transform: rotate(45deg); }

  /* ===== two-pane gantt ===== */
  .gantt2 { --row-h: 46px; --head-h: 38px; display: flex; border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; background: var(--bg-panel); }

  .g-table { flex: none; width: 340px; border-right: 2px solid var(--border-strong); background: var(--bg-surface); }
  .gh-row { height: var(--head-h); display: flex; align-items: center; background: var(--bg-overlay); border-bottom: 1px solid var(--border-strong); font-size: var(--font-label); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); }
  .lhead { padding: 0 14px; }

  /* read-only task rows (island look, aligned to timeline) */
  .tk-row { height: var(--row-h); width: 100%; display: flex; align-items: center; gap: var(--space-sm); padding: 0 12px; border: none; border-bottom: 1px solid var(--border); background: none; text-align: left; cursor: pointer; color: var(--text-secondary); position: relative; transition: background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); }
  .tk-row:hover { background: var(--bg-hover); }
  .tk-row:last-child { border-bottom: 0; }
  .tk-row .tk-stare { min-width: 24px; flex-shrink: 0; display: inline-flex; align-items: center; }
  .row-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .row-title { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: inline-flex; align-items: center; gap: 5px; }
  .row-title :global(.mini-ms) { color: var(--accent); flex: none; }
  .row-meta { font-size: var(--font-small); color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tk-row.done .row-title { color: var(--text-dim); text-decoration: line-through; text-decoration-color: var(--text-faint); }
  .tk-row.done .tk-stare { color: var(--success); }
  .due-chip { font-family: var(--font-mono); font-size: var(--font-small); padding: 3px 9px; border-radius: var(--radius-full); background: var(--bg-hover); color: var(--text-dim); white-space: nowrap; flex-shrink: 0; }
  .due-chip.hot { background: var(--danger-subtle); color: var(--danger); }
  .due-chip.warm { background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .tk-row :global(.tk-chev) { color: var(--text-faint); flex: none; }

  /* implementation periods (Site / Sediu EGB) — the editable rows */
  /* Dunga de identitate a plecat: randul e DEJA umplut cu aceeasi culoare
     (`color-mix(… var(--il) 8% …)`) si poarta si iconita de locatie in ea, deci
     muchia era a treia oara acelasi lucru. Cei 3px se intorc in padding. */
  .impl-lrow { height: var(--row-h); width: 100%; display: flex; align-items: center; gap: 7px; padding: 0 12px 0 15px; border: none; border-bottom: 1px solid var(--border); background: color-mix(in srgb, var(--il) 8%, transparent); color: var(--text); cursor: pointer; text-align: left; }
  .impl-lrow:hover { background: color-mix(in srgb, var(--il) 16%, transparent); }
  .impl-lname { font-size: var(--font-small); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .loc-site { --il: var(--loc-site); } .loc-sediu { --il: var(--loc-sediu); }
  /* Perioada de implementare umple randul, nu pluteste ca o pastila subtire in
     mijlocul lui: e un BLOC de zile in care esti acolo, nu un marcaj. Randul
     ramane cu aceeasi inaltime, doar continutul lui se vede acum. */
  /* Aceeasi regula ca la `.impl-lrow`: banda e DEJA plina cu `var(--il)`, deci
     muchia era aceeasi culoare peste ea insasi, doar mai inchisa. Cei 3px se
     intorc in padding. */
  .impl-band { position: absolute; top: 2px; bottom: 2px; border-radius: 5px; display: flex; align-items: center; gap: 5px; padding: 0 10px 0 13px; cursor: pointer; overflow: hidden; color: var(--on-color);
    border: none;
    background: linear-gradient(180deg,
      color-mix(in oklab, var(--il) 88%, #fff) 0%, var(--il) 46%,
      color-mix(in oklab, var(--il) 90%, #000) 100%);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--on-color) 20%, transparent), 0 1px 3px rgba(0,0,0,0.28); }
  .impl-band.loc-sediu { --il: var(--loc-sediu); }
  /* A doua axa, ca in Calendar si in Planificator: palid = pregatire, plin =
     implementare. Aceeasi perioada, alta faza — nu acelasi bloc. */
  .impl-band.pregatire { background: color-mix(in oklab, var(--il) 16%, transparent);
    border-left-color: color-mix(in oklab, var(--il) 70%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in oklab, var(--il) 45%, transparent);
    color: color-mix(in oklab, var(--il) 55%, var(--text)); }
  .impl-band :global(.ib-ico) { flex: none; opacity: 0.72; }
  .ib-txt { font-size: var(--font-small); font-weight: var(--fw-semibold); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* ===== timeline ===== */
  .g-time { flex: 1; overflow-x: auto; min-width: 0; }
  .g-time-inner { position: relative; }
  .time-head { position: relative; }
  .col-h { position: absolute; top: 0; bottom: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px; border-left: 1px solid var(--border); overflow: hidden; }
  .col-h.we { background: color-mix(in srgb, var(--purple) 6%, transparent); }
  .col-h.today { background: var(--accent-subtle); }
  .ch-sub { font-size: var(--font-label); color: var(--text-faint); text-transform: uppercase; white-space: nowrap; }
  .ch-main { font-family: var(--font-mono); font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary); white-space: nowrap; }
  .col-h.today .ch-main, .col-h.today .ch-sub { color: var(--accent); }

  .g-body { position: relative; }
  .overlay { position: absolute; inset: 0; pointer-events: none; z-index: 0; }
  .col-line { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--border-subtle); }
  .col-we { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--purple) 5%, transparent); }
  /* Pregatirea = golul dintre etape. Tenta cea mai discreta posibila: e un fundal
     de stare, nu un obiect — barele si punctele trebuie sa ramana citibile peste ea. */
  .prep { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--text-faint) 7%, transparent);
    border-left: 1px solid color-mix(in srgb, var(--text-faint) 18%, transparent); z-index: 0; }
  .prep.deschis { border-right: 0;
    -webkit-mask-image: linear-gradient(to right, #000 55%, transparent 100%);
    mask-image: linear-gradient(to right, #000 55%, transparent 100%); }

  .today-line { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--danger); opacity: 0.7; z-index: 1; }

  .gb-row { position: relative; height: var(--row-h); border-bottom: 1px solid var(--border); }
  .gb-row:last-child { border-bottom: 0; }
  /* tasks are point markers (repere) at their due date, not bars */
  .dot { position: absolute; top: 50%; width: 13px; height: 13px; border-radius: 50%; transform: translate(-50%, -50%); z-index: 2; box-shadow: 0 0 0 3px color-mix(in srgb, var(--bg-panel) 70%, transparent); }
  .dot.done { background: var(--success); }
  .dot.prog { background: var(--accent); }
  .dot.todo { background: var(--bg-panel); border: 2px solid var(--border-strong); box-shadow: none; }
  .dot.leg { position: static; transform: none; width: 11px; height: 11px; box-shadow: none; }
  .tk-line { position: absolute; top: 50%; height: 4px; border-radius: 2px; transform: translateY(-50%); z-index: 1; opacity: 0.55; }
  .tk-line.done { background: var(--success); }
  .tk-line.prog { background: var(--accent); }
  .tk-line.todo { background: var(--border-strong); }
  .ms { position: absolute; top: 50%; width: 15px; height: 15px; background: var(--accent); border: 2px solid var(--bg-panel); transform: translate(-50%, -50%) rotate(45deg); box-shadow: 0 0 0 3px var(--accent-subtle); z-index: 2; }
  /* label next to the marker so a task is readable without hovering */

  @media (max-width: 720px) {
    .g-table { width: 210px; }
    /* Bara de unelte a Ganttului: „Perioadă", „PDF", „Excel" erau de 36px.
       Ele deschid modalul de perioada si descarca exporturile — actiuni pe care
       le faci exact o data si trebuie sa nimeresti din prima. */
    .exp-btn { min-height: var(--tap-min); padding: 7px 14px; }
    /* Banda de perioada din timeline: e si buton (deschide editorul perioadei). */
    .impl-band { min-height: var(--tap-min); }
  }
</style>
