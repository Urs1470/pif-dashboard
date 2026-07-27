<script>
  // Review saptamanal — bucla care tine sistemul curat.
  //
  // Problema pe care o rezolva: cand esti singur pe teren, statusurile raman in
  // urma. O perioada planificata trece, lucrarea se face, dar proiectul ramane
  // in „pregatire" — si atunci alertele de pe Acasa devin zgomot si le ignori.
  // Aici le inchizi sau le replanifici in cateva click-uri, fara sa intri in
  // 5 proiecte separat.
  import { onMount, onDestroy } from 'svelte'
  import { fade } from 'svelte/transition'
  import { CalendarCheck, ChevronRight, Check, CalendarRange, Copy } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { formatDate, PROJECT_STATUS_LABELS } from '../lib/formatters.js'
  import { navigate } from '../lib/router.svelte.js'
  import { toast } from '../stores/ui.svelte.js'
  import { motionDuration, DUR_BASE } from '../lib/motion.svelte.js'
  import Card from '../components/ui/Card.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import { ui } from '../stores/ui.svelte.js'

  let data = $state(null)
  let loading = $state(true)
  let error = $state(null)
  let busy = $state('')          // id-ul randului in lucru (dezactiveaza butoanele lui)
  let replanId = $state('')      // perioada pentru care e deschis date pickerul
  let replanVal = $state('')

  async function load(silent = false) {
    if (!silent) { loading = true; error = null }
    try {
      data = await apiJson('/api/review')
    } catch (e) {
      if (!silent) error = e.message
    } finally {
      if (!silent) loading = false
    }
  }

  function zileTrecute(iso) {
    if (!iso) return 0
    return Math.round((new Date().setHours(0, 0, 0, 0) - new Date(iso)) / 86400000)
  }

  function perioadaText(r) {
    const a = r.data_start, b = r.data_sfarsit || r.data_start
    return a === b ? formatDate(a) : `${formatDate(a)} – ${formatDate(b)}`
  }

  // Inchide proiectul: perioada a trecut si lucrarea s-a facut.
  async function inchide(r) {
    busy = r.id
    try {
      await apiJson(`/api/proiecte/${r.proiect_id}`, { method: 'PUT', body: { status: 'finalizat' } })
      toast(`„${r.nume}" — finalizat`, 'success')
      await load(true)
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = '' }
  }

  // Marcheaza proiectul ca fiind in lucru (perioada a trecut, dar nu s-a terminat).
  async function inLucru(r) {
    busy = r.id
    try {
      await apiJson(`/api/proiecte/${r.proiect_id}`, { method: 'PUT', body: { status: 'in_lucru' } })
      toast(`„${r.nume}" — în lucru`, 'success')
      await load(true)
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = '' }
  }

  // Muta perioada, pastrand durata (o perioada de 2 zile ramane de 2 zile).
  async function replanifica(r, nouaData) {
    if (!nouaData) return
    busy = r.id
    try {
      const d0 = new Date(r.data_start)
      const d1 = new Date(r.data_sfarsit || r.data_start)
      const durata = Math.max(0, Math.round((d1 - d0) / 86400000))
      const start = new Date(nouaData)
      const sfarsit = new Date(start.getTime() + durata * 86400000)
      const iso = (d) => d.toISOString().slice(0, 10)
      await apiJson(`/api/implementari/${r.id}`, {
        method: 'PUT',
        body: { data_start: iso(start), data_sfarsit: iso(sfarsit) },
      })
      toast(`Replanificat pe ${formatDate(iso(start))}`, 'success')
      replanId = ''
      replanVal = ''
      await load(true)
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = '' }
  }

  // Rezumatul: text simplu, de lipit in jurnal / observatii / mail.
  const rezumat = $derived.by(() => {
    if (!data) return ''
    const L = [`Review ${formatDate(new Date().toISOString().slice(0, 10))}`, '']
    if (data.taskuri_gata?.length) {
      L.push(`Terminate (7 zile) — ${data.taskuri_gata.length}:`)
      for (const t of data.taskuri_gata) L.push(`  · ${t.titlu} (${t.proiect_nume})`)
      L.push('')
    }
    if (data.proiecte_inchise?.length) {
      L.push('Proiecte închise:')
      for (const p of data.proiecte_inchise) L.push(`  · ${p.nume}`)
      L.push('')
    }
    if (data.de_inchis?.length) {
      L.push(`De clarificat — ${data.de_inchis.length}:`)
      for (const r of data.de_inchis) L.push(`  · ${r.nume} — perioada ${perioadaText(r)}, încă „${r.status}"`)
      L.push('')
    }
    if (data.urmeaza?.length) {
      L.push(`Urmează (${data.zile} zile) — ${data.urmeaza.length}:`)
      for (const r of data.urmeaza) L.push(`  · ${perioadaText(r)} — ${r.nume}${r.eticheta ? ' (' + r.eticheta + ')' : ''}`)
    }
    return L.join('\n').trim()
  })

  async function copiazaRezumat() {
    try {
      await navigator.clipboard.writeText(rezumat)
      toast('Rezumat copiat', 'success')
    } catch { toast('Nu am putut copia', 'error') }
  }

  const nimicDeFacut = $derived(!!data && !data.de_inchis?.length && !data.urmeaza?.length)

  onMount(() => {
    ui.pageHeader = { title: 'Review săptămânal', subtitle: 'Închide ce s-a făcut, replanifică ce a alunecat' }
    load()
  })
  onDestroy(() => { ui.pageHeader = { title: '', subtitle: '' } })
</script>

<div class="page">
  {#if loading}
    <Skeleton height="120px" />
  {:else if error}
    <ErrorState message={error} onretry={load} />
  {:else if data}
    {#if nimicDeFacut}
      <EmptyState icon={CalendarCheck} title="Nimic de clarificat"
        description="Nicio perioadă trecută rămasă deschisă și nimic planificat în fereastra următoare." />
    {/if}

    <div class="cols">
      <!-- ===== 1. De clarificat: perioade trecute, status nemiscat ===== -->
      {#if data.de_inchis?.length}
        <Card padding={false}>
          <div class="col-head danger">
            <span class="ch-t">De clarificat</span>
            <span class="ch-n">{data.de_inchis.length}</span>
          </div>
          <p class="col-hint">Perioada a trecut, dar proiectul n-a fost mutat. S-a făcut, sau a alunecat?</p>
          <div class="col-list">
            {#each data.de_inchis as r (r.id)}
              <div class="row" in:fade={{ duration: motionDuration(DUR_BASE) }}>
                <button class="row-main" onclick={() => navigate(`/projects/${r.proiect_id}`)}>
                  <div class="row-title">{r.nume}</div>
                  <div class="row-meta">
                    <span class="per">{perioadaText(r)}</span>
                    <span class="ago">acum {zileTrecute(r.data_sfarsit || r.data_start)} zile</span>
                    <span class="st">{PROJECT_STATUS_LABELS[r.status] || r.status}</span>
                    {#if r.eticheta}<span class="et">{r.eticheta}</span>{/if}
                    {#if r.taskuri_deschise}<span class="tk">{r.taskuri_deschise} taskuri deschise</span>{/if}
                  </div>
                </button>
                <div class="row-acts">
                  <button class="act ok" disabled={busy === r.id} onclick={() => inchide(r)} title="Marchează proiectul finalizat"><Check size={13} /> S-a făcut</button>
                  {#if r.status !== 'in_lucru'}
                    <button class="act" disabled={busy === r.id} onclick={() => inLucru(r)} title="Marchează proiectul în lucru">În lucru</button>
                  {/if}
                  <button class="act" disabled={busy === r.id} onclick={() => { replanId = replanId === r.id ? '' : r.id; replanVal = '' }} title="Mută perioada în viitor"><CalendarRange size={13} /> Replanifică</button>
                </div>
                {#if replanId === r.id}
                  <div class="replan" in:fade={{ duration: motionDuration(DUR_BASE) }}>
                    <DatePicker bind:value={replanVal} label="Dată nouă de început" />
                    <button class="act ok" disabled={!replanVal || busy === r.id} onclick={() => replanifica(r, replanVal)}>Mută</button>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </Card>
      {/if}

      <!-- ===== 2. Urmeaza ===== -->
      {#if data.urmeaza?.length}
        <Card padding={false}>
          <div class="col-head accent">
            <span class="ch-t">Urmează ({data.zile} zile)</span>
            <span class="ch-n">{data.urmeaza.length}</span>
          </div>
          <p class="col-hint">Confirmă că e pregătit: taskuri, documentație, backup-uri.</p>
          <div class="col-list">
            {#each data.urmeaza as r (r.id)}
              <button class="row-main solo" onclick={() => navigate(`/projects/${r.proiect_id}`)}>
                <div class="row-title">{r.nume}</div>
                <div class="row-meta">
                  <span class="per">{perioadaText(r)}</span>
                  <span class="loc" class:sediu={r.locatie === 'sediu'}>{r.locatie === 'sediu' ? 'Sediu' : 'Site'}</span>
                  {#if r.client}<span class="cli">{r.client}</span>{/if}
                  {#if r.eticheta}<span class="et">{r.eticheta}</span>{/if}
                  <span class="tk" class:warn={!r.taskuri_deschise}>{r.taskuri_deschise ? `${r.taskuri_deschise} ${r.taskuri_deschise === 1 ? 'task' : 'taskuri'}` : 'niciun task'}</span>
                </div>
                <ChevronRight size={14} />
              </button>
            {/each}
          </div>
        </Card>
      {/if}

      <!-- ===== 3. S-a facut ===== -->
      {#if data.taskuri_gata?.length || data.proiecte_inchise?.length}
        <Card padding={false}>
          <div class="col-head success">
            <span class="ch-t">S-a făcut (7 zile)</span>
            <span class="ch-n">{(data.taskuri_gata?.length || 0) + (data.proiecte_inchise?.length || 0)}</span>
          </div>
          <div class="col-list">
            {#each data.proiecte_inchise || [] as p (p.proiect_id)}
              <button class="row-main solo" onclick={() => navigate(`/projects/${p.proiect_id}`)}>
                <div class="row-title">{p.nume}</div>
                <div class="row-meta"><span class="st done">proiect finalizat</span>{#if p.client}<span class="cli">{p.client}</span>{/if}</div>
              </button>
            {/each}
            {#each data.taskuri_gata || [] as t, i (t.titlu + i)}
              <button class="row-main solo" onclick={() => navigate(`/projects/${t.proiect_id}`)}>
                <div class="row-title dim">{t.titlu}</div>
                <div class="row-meta"><span class="cli">{t.proiect_nume}</span><span class="per">{formatDate(t.data_finalizare)}</span></div>
              </button>
            {/each}
          </div>
        </Card>
      {/if}
    </div>

    {#if rezumat}
      <div class="sum">
        <div class="sum-head">
          <span>Rezumat</span>
          <button class="act" onclick={copiazaRezumat}><Copy size={13} /> Copiază</button>
        </div>
        <pre class="sum-body">{rezumat}</pre>
      </div>
    {/if}
  {/if}
</div>

<style>
  .page { padding: var(--space-lg); }
  .cols { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: var(--space-md); align-items: start; }

  .col-head { display: flex; align-items: center; gap: 9px; padding: 12px var(--space-md); border-bottom: 1px solid var(--border); }
  .col-head .ch-t { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-faint); }
  .col-head .ch-n { margin-left: auto; font-size: var(--font-tiny); padding: 1px 8px; border-radius: var(--radius-full); background: var(--bg-hover); color: var(--text-secondary); }
  .col-head.danger { box-shadow: inset 3px 0 0 var(--danger); }
  .col-head.accent { box-shadow: inset 3px 0 0 var(--accent); }
  .col-head.success { box-shadow: inset 3px 0 0 var(--success); }
  .col-hint { padding: 8px var(--space-md) 0; font-size: var(--font-tiny); color: var(--text-dim); }

  .col-list { display: flex; flex-direction: column; padding: var(--space-sm); gap: 4px; max-height: 520px; overflow-y: auto; }
  .row { display: flex; flex-direction: column; gap: 6px; padding: 8px; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); }
  .row-main { display: flex; flex-direction: column; gap: 4px; text-align: left; width: 100%; cursor: pointer; }
  .row-main.solo { padding: 8px; border-radius: var(--radius-md); }
  .row-main.solo:hover { background: var(--bg-hover); }
  .row-title { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); }
  .row-title.dim { font-weight: var(--fw-regular); color: var(--text-secondary); }
  .row-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: var(--font-micro); color: var(--text-dim); }
  .row-meta .per { font-family: var(--font-mono); color: var(--text-secondary); font-variant-numeric: tabular-nums; }
  .row-meta .ago { color: var(--danger); }
  .row-meta .st { padding: 0 6px; border-radius: var(--radius-full); background: var(--bg-hover); }
  .row-meta .st.done { color: var(--success); }
  .row-meta .et { font-style: italic; }
  .row-meta .cli { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 190px; }
  .row-meta .tk { color: var(--text-faint); }
  .row-meta .tk.warn { color: var(--warning); }
  .row-meta .loc { padding: 0 6px; border-radius: var(--radius-full); background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .row-meta .loc.sediu { background: var(--bg-hover); color: var(--text-dim); }

  .row-acts { display: flex; flex-wrap: wrap; gap: 6px; }
  .act { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-tiny); padding: 3px 9px; border-radius: var(--radius-sm);
         border: 1px solid var(--border); color: var(--text-secondary); background: var(--bg-surface); cursor: pointer; }
  .act:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .act:disabled { opacity: 0.5; cursor: default; }
  .act.ok { color: var(--success); border-color: color-mix(in srgb, var(--success) 45%, transparent); }
  .act.ok:hover:not(:disabled) { background: color-mix(in srgb, var(--success) 14%, transparent); border-color: var(--success); color: var(--success); }

  .replan { display: flex; align-items: flex-end; gap: 8px; padding-top: 4px; }

  .sum { margin-top: var(--space-lg); border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-surface); }
  .sum-head { display: flex; align-items: center; justify-content: space-between; padding: 10px var(--space-md); border-bottom: 1px solid var(--border);
              font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-faint); }
  .sum-body { margin: 0; padding: var(--space-md); font-family: var(--font-mono); font-size: var(--font-tiny); line-height: 1.6;
              color: var(--text-secondary); white-space: pre-wrap; word-break: break-word; }

  @media (max-width: 720px) {
    .page { padding: var(--space-md); }
    .col-list { max-height: none; }
  }
</style>
