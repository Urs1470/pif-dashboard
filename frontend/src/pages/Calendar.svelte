<script>
  // Calendar — „unde sunt".
  //
  // Ion e o singura persoana, iar planificarea lui reala sunt PERIOADELE de
  // implementare, nu deadline-urile (le au 2 din 20 de proiecte). Intrebarea la
  // care raspunde ecranul asta e „unde sunt marti", iar deciziile stau TOT aici,
  // pe ziua respectiva — nu intr-o lista separata de reprosuri.
  //
  // Culoarea codeaza CLIENTUL, nu proiectul: unitatea reala e deplasarea. Trei
  // lucrari intr-o zi la acelasi client = o deplasare (un bloc), la clienti
  // diferiti = zi impartita, semnalata.
  import { onMount, onDestroy } from 'svelte'
  import { fade } from 'svelte/transition'
  import { ChevronLeft, ChevronRight, MapPin, Building2, Check, Undo2, ExternalLink, AlertTriangle, GripVertical, CalendarDays } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { navigate } from '../lib/router.svelte.js'
  import { toast } from '../stores/ui.svelte.js'
  import { ui } from '../stores/ui.svelte.js'
  import { motionDuration, DUR_BASE } from '../lib/motion.svelte.js'
  import { PROJECT_STATUS_LABELS } from '../lib/formatters.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import {
    WEEKDAYS, buildGrid, monthStart, addMonths, addDays, weekStart,
    diffDays, isWeekend, monthLabel, dayLabel, shortDate, todayISO, parseISO,
  } from '../lib/calendarDates.js'

  let data = $state(null)
  let loading = $state(true)
  let error = $state(null)
  let mod = $state('luna')            // 'luna' | 'saptamani'
  let anchor = $state(monthStart(todayISO()))
  let selectata = $state(todayISO())
  let busy = $state('')
  let dragged = $state(null)          // { tip: 'perioada'|'proiect', ... }
  let dropZi = $state('')
  let mutaId = $state('')      // perioada pentru care e deschis selectorul de data
  let mutaVal = $state('')

  const azi = todayISO()

  // Paleta pe client — stabila (acelasi client, aceeasi culoare la fiecare
  // incarcare) si distincta pe fundalul cald-inchis. Amber e rezervat pentru
  // accentul aplicatiei, deci lipseste din lista.
  const PALETA = ['#3f9dc4', '#3fae74', '#8b6fe0', '#d1697f', '#5f8fd0', '#c9a13a', '#b9a5ff']
  function culoare(client) {
    const k = (client || '').trim().toLowerCase()
    if (!k) return '#948a7d'
    let h = 0
    for (let i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) >>> 0
    return PALETA[h % PALETA.length]
  }
  function scurt(client) {
    const c = (client || '').trim()
    if (!c) return '—'
    // „Continental Automotive Products SRL" -> „Continental"
    return c.split(/\s+/)[0].replace(/[.,]$/, '')
  }

  async function load(silent = false) {
    if (!silent) { loading = true; error = null }
    try {
      const start = mod === 'luna' ? weekStart(monthStart(anchor)) : weekStart(anchor)
      const zile = mod === 'luna' ? 49 : 28
      data = await apiJson(`/api/calendar?start=${start}&zile=${zile}`)
    } catch (e) {
      if (!silent) error = e.message
    } finally {
      if (!silent) loading = false
    }
  }

  const grila = $derived(buildGrid(anchor, mod, 2))

  // zi ISO -> perioadele care o acopera
  const peZi = $derived.by(() => {
    const m = new Map()
    for (const p of (data?.perioade || [])) {
      const a = p.data_start
      const b = p.data_sfarsit || p.data_start
      const n = Math.max(0, diffDays(a, b))
      for (let i = 0; i <= n; i++) {
        const iso = addDays(a, i)
        if (!m.has(iso)) m.set(iso, [])
        m.get(iso).push(p)
      }
    }
    return m
  })

  function aleZilei(iso) { return peZi.get(iso) || [] }

  // ===== gruparea pe DEPLASARE =====
  // Unitatea afisata nu e lucrarea, e deplasarea: trei lucrari intr-o zi la
  // Continental inseamna ca te urci o data in masina. Deci grupam perioadele
  // zilei pe (loc, client) si desenam UN bloc per grup, nu cate o dunga per
  // lucrare. O zi la SEDIU nu e deplasare — e grup separat si nu se numara.
  function cheieGrup(p) {
    const loc = p.locatie === 'sediu' ? 'sediu' : 'site'
    return `${loc}|${(p.client || '').trim().toLowerCase()}`
  }

  const grupuriPeZi = $derived.by(() => {
    const m = new Map()
    for (const [iso, items] of peZi) {
      const g = new Map()
      for (const p of items) {
        const k = cheieGrup(p)
        if (!g.has(k)) {
          g.set(k, { cheie: k, client: (p.client || '').trim(), sediu: p.locatie === 'sediu', items: [] })
        }
        g.get(k).items.push(p)
      }
      m.set(iso, [...g.values()])
    }
    return m
  })

  function grupurile(iso) { return grupuriPeZi.get(iso) || [] }
  function areGrup(iso, cheie) { return grupurile(iso).some(b => b.cheie === cheie) }

  /** Ziua e impartita intre locuri diferite? (doi clienti, sau sediu + teren) */
  function impartita(iso) { return grupurile(iso).length > 1 }

  // O DEPLASARE = rulajul contiguu de zile cu aceeasi cheie de grup. O construim
  // explicit ca sa putem eticheta blocul cu identitatea iesirii, nu cu numele
  // unei lucrari: pe 28 era doar „Migrare CU240S", dar blocul tine pana pe 30,
  // asa ca eticheta aia facea sa para ca migrarea dureaza trei zile.
  const deplasari = $derived.by(() => {
    const perCheie = new Map()
    for (const iso of [...grupuriPeZi.keys()].sort()) {
      for (const b of grupurile(iso)) {
        if (!perCheie.has(b.cheie)) perCheie.set(b.cheie, [])
        perCheie.get(b.cheie).push({ iso, b })
      }
    }
    const out = []
    for (const [cheie, lista] of perCheie) {
      let cur = null
      for (const { iso, b } of lista) {
        if (cur && diffDays(cur.end, iso) === 1) cur.end = iso
        else {
          cur = { cheie, client: b.client, sediu: b.sediu, start: iso, end: iso, items: new Map() }
          out.push(cur)
        }
        for (const p of b.items) cur.items.set(p.id, p)
      }
    }
    return out
  })

  const deplasareaZilei = $derived.by(() => {
    const m = new Map()
    for (const d of deplasari) {
      let iso = d.start
      for (;;) {
        m.set(`${iso}|${d.cheie}`, d)
        if (iso === d.end) break
        iso = addDays(iso, 1)
      }
    }
    return m
  })

  function deplasareaLui(b, iso) { return deplasareaZilei.get(`${iso}|${b.cheie}`) }

  /** Eticheta blocului: numele lucrarii DOAR cand iesirea e o zi cu o lucrare —
   *  altfel identitatea deplasarii (client + cate lucrari are in total). */
  function etichetaGrup(b, iso) {
    const d = deplasareaLui(b, iso)
    const n = d ? d.items.size : b.items.length
    const oSinguraZi = d ? d.start === d.end : true
    if (oSinguraZi && n === 1) return b.items[0].eticheta || (b.sediu ? 'Sediu' : scurt(b.client))
    return `${b.sediu ? 'Sediu' : scurt(b.client)} · ${n} ${n === 1 ? 'lucrare' : 'lucrări'}`
  }

  // O deplasare = zile CONSECUTIVE cu acelasi grup de teren. 28-29-30 la
  // Continental = o singura iesire; o pauza de o zi rupe deplasarea in doua.
  const rezumat = $derived.by(() => {
    if (!data) return { zile: 0, deplasari: 0, zileSediu: 0, deDecis: 0 }
    const zileGrila = grila.filter(g => !g.alta).map(g => g.iso).sort()
    let zile = 0, deplasari = 0, zileSediu = 0
    let ieri = new Set()
    for (const iso of zileGrila) {
      const grupuri = grupurile(iso)
      const teren = new Set(grupuri.filter(b => !b.sediu).map(b => b.cheie))
      if (teren.size) zile++
      if (grupuri.some(b => b.sediu)) zileSediu++
      for (const k of teren) if (!ieri.has(k)) deplasari++
      ieri = teren
    }
    return { zile, deplasari, zileSediu, deDecis: (data.de_decis || []).length }
  })

  const selectate = $derived(aleZilei(selectata))
  const grupuriSelectate = $derived(grupurile(selectata))

  // Legenda arata DOAR clientii din fereastra curenta — o legenda fixa cu toti
  // clientii ar fi zgomot cand luna are un singur client (cazul obisnuit).
  const legenda = $derived.by(() => {
    const m = new Map()
    for (const g of grila) {
      if (g.alta) continue
      for (const p of aleZilei(g.iso)) {
        const c = (p.client || '').trim()
        const cheie = c || '—'
        m.set(cheie, (m.get(cheie) || 0) + 1)
      }
    }
    return [...m.keys()].sort().map(c => ({ nume: c, scurt: scurt(c), culoare: culoare(c === '—' ? '' : c) }))
  })

  // ===== navigatie =====
  function pas(n) {
    anchor = mod === 'luna' ? addMonths(anchor, n) : addDays(anchor, n * 14)
    load()
  }
  function laAzi() {
    anchor = mod === 'luna' ? monthLuna(azi) : weekStart(azi)
    selectata = azi
    load()
  }
  function monthLuna(iso) { return monthStart(iso) }
  // La schimbarea modului ramai unde te uitai. Ancorarea pe ziua selectata sare
  // inapoi daca selectia era dintr-o luna pe care ai parasit-o intre timp, deci
  // o folosim doar cand e chiar in fereastra vizibila.
  function setMod(m) {
    if (mod === m) return
    // Ramai unde te uitai. Daca ziua selectata nu e in fereastra (ai navigat mai
    // departe intre timp), ancoram pe MIJLOCUL ferestrei — capatul de stanga al
    // unei ferestre de 2 saptamani cade des in luna anterioara si te-ar trimite
    // inapoi la comutare.
    const vizibile = grila.filter(g => !g.alta).map(g => g.iso)
    const inVizor = vizibile.includes(selectata)
    const baza = inVizor ? selectata : (vizibile[Math.floor(vizibile.length / 2)] || azi)
    mod = m
    anchor = m === 'luna' ? monthStart(baza) : weekStart(baza)
    load()
  }

  // ===== actiuni =====
  async function setStatus(p, status) {
    busy = p.id
    try {
      await apiJson(`/api/proiecte/${p.proiect_id}`, { method: 'PUT', body: { status } })
      toast(`„${p.nume}" — ${PROJECT_STATUS_LABELS[status] || status}`, 'success')
      await load(true)
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = '' }
  }

  /** Muta perioada pastrand durata. Folosit si de drop, si de butoane. */
  async function muta(p, ziNoua) {
    if (!ziNoua) return
    const durata = Math.max(0, diffDays(p.data_start, p.data_sfarsit || p.data_start))
    busy = p.id
    try {
      await apiJson(`/api/implementari/${p.id}`, {
        method: 'PUT',
        body: { data_start: ziNoua, data_sfarsit: addDays(ziNoua, durata) },
      })
      toast(`Mutat pe ${shortDate(ziNoua)}`, 'success')
      selectata = ziNoua
      await load(true)
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = '' }
  }

  /** Scoate perioada din calendar. Daca era ultima, proiectul reapare in
   *  „Fara data" — asta e calea de intoarcere pentru o planificare gresita. */
  async function scoate(p) {
    busy = p.id
    try {
      await apiJson(`/api/implementari/${p.id}`, { method: 'DELETE' })
      toast(`„${p.nume}" — scos din calendar`, 'success')
      await load(true)
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = '' }
  }

  async function planifica(proj, zi) {
    busy = proj.proiect_id
    try {
      await apiJson(`/api/proiecte/${proj.proiect_id}/implementari`, {
        method: 'POST',
        body: { data_start: zi, data_sfarsit: zi, locatie: 'site', eticheta: '' },
      })
      toast(`„${proj.nume}" planificat pe ${shortDate(zi)}`, 'success')
      selectata = zi
      await load(true)
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = '' }
  }

  /** Muta o deplasare intreaga: toate lucrarile ei se decaleaza cu acelasi
   *  numar de zile, deci forma iesirii se pastreaza (2 zile raman 2 zile,
   *  iar lucrarea care incepea a doua zi tot a doua zi incepe). */
  async function mutaGrup(b, ziSursa, ziTinta) {
    const delta = diffDays(ziSursa, ziTinta)
    if (!delta) return
    busy = b.cheie
    try {
      for (const p of b.items) {
        await apiJson(`/api/implementari/${p.id}`, {
          method: 'PUT',
          body: {
            data_start: addDays(p.data_start, delta),
            data_sfarsit: addDays(p.data_sfarsit || p.data_start, delta),
          },
        })
      }
      toast(b.items.length > 1
        ? `Deplasare mutată — ${b.items.length} lucrări`
        : `Mutat pe ${shortDate(ziTinta)}`, 'success')
      selectata = ziTinta
      await load(true)
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = '' }
  }

  // ===== drag & drop =====
  function dragGrup(e, b, iso) {
    dragged = { tip: 'grup', b, iso }
    e.dataTransfer.effectAllowed = 'move'
    try { e.dataTransfer.setData('text/plain', b.cheie) } catch (_) {}
  }
  function dragProiect(e, proj) {
    dragged = { tip: 'proiect', proj }
    e.dataTransfer.effectAllowed = 'copy'
    try { e.dataTransfer.setData('text/plain', proj.proiect_id) } catch (_) {}
  }
  function overZi(e, iso) {
    if (!dragged) return
    e.preventDefault()
    e.dataTransfer.dropEffect = dragged.tip === 'grup' ? 'move' : 'copy'
    dropZi = iso
  }
  function dropPeZi(e, iso) {
    if (!dragged) return
    e.preventDefault()
    const d = dragged
    dragged = null
    dropZi = ''
    if (d.tip === 'grup') { if (d.iso !== iso) mutaGrup(d.b, d.iso, iso) }
    else planifica(d.proj, iso)
  }
  function endDrag() { dragged = null; dropZi = '' }

  onMount(() => {
    ui.pageHeader = { title: 'Calendar', subtitle: 'Unde ești în fiecare zi' }
    load()
  })
  onDestroy(() => { ui.pageHeader = { title: '', subtitle: '' } })
</script>

<div class="page">
  {#if loading}
    <Skeleton height="360px" />
  {:else if error}
    <ErrorState message={error} onretry={load} />
  {:else if data}

    <div class="bar">
      <div class="nav">
        <button class="ico" onclick={() => pas(-1)} aria-label="Înapoi"><ChevronLeft size={16} /></button>
        <span class="titlu">{mod === 'luna' ? monthLabel(anchor) : `${shortDate(weekStart(anchor))} – ${shortDate(addDays(weekStart(anchor), 13))}`}</span>
        <button class="ico" onclick={() => pas(1)} aria-label="Înainte"><ChevronRight size={16} /></button>
        <button class="azi" onclick={laAzi}>Azi</button>
      </div>
      <div class="mods">
        <button class:on={mod === 'saptamani'} onclick={() => setMod('saptamani')}>2 săpt.</button>
        <button class:on={mod === 'luna'} onclick={() => setMod('luna')}>Lună</button>
      </div>
    </div>

    <div class="kpis">
      <div class="kpi"><span class="k-n">{rezumat.zile}</span><span class="k-l">zile pe teren</span></div>
      <div class="kpi"><span class="k-n">{rezumat.deplasari}</span><span class="k-l">{rezumat.deplasari === 1 ? 'deplasare' : 'deplasări'}</span></div>
      {#if rezumat.zileSediu}
        <div class="kpi"><span class="k-n">{rezumat.zileSediu}</span><span class="k-l">{rezumat.zileSediu === 1 ? 'zi la sediu' : 'zile la sediu'}</span></div>
      {/if}
      {#if rezumat.deDecis}
        <button class="kpi warn" onclick={() => { const d = data.de_decis[0]; selectata = d.data_sfarsit || d.data_start; anchor = mod === 'luna' ? monthStart(selectata) : weekStart(selectata); load() }}>
          <span class="k-n">{rezumat.deDecis}</span><span class="k-l">de clarificat</span>
        </button>
      {/if}
    </div>

    <div class="wrap">
      <div class="cal">
        <div class="wd">
          {#each WEEKDAYS as w}<span>{w}</span>{/each}
        </div>
        <div class="grid" class:sapt={mod === 'saptamani'}>
          {#each grila as g (g.iso)}
            {@const items = aleZilei(g.iso)}
            {@const grupuri = grupurile(g.iso)}
            {@const decizie = items.some(p => p.necesita_decizie)}
            <button
              class="zi"
              class:alta={g.alta}
              class:we={isWeekend(g.iso)}
              class:azi={g.iso === azi}
              class:sel={g.iso === selectata}
              class:drop={dropZi === g.iso}
              class:decizie
              class:split={impartita(g.iso)}
              onclick={() => selectata = g.iso}
              ondragover={(e) => overZi(e, g.iso)}
              ondrop={(e) => dropPeZi(e, g.iso)}
            >
              <span class="n">{parseISO(g.iso).getDate()}</span>
              {#if decizie}<span class="flag" title="Perioadă trecută, proiect nemutat"><AlertTriangle size={11} /></span>{/if}
              <div class="segs">
                {#each grupuri as b (b.cheie)}
                  {@const start = !areGrup(addDays(g.iso, -1), b.cheie)}
                  {@const end = !areGrup(addDays(g.iso, 1), b.cheie)}
                  <div class="seg" class:start class:end class:sediu={b.sediu}
                       style="--c: {culoare(b.client)}"
                       draggable="true"
                       ondragstart={(e) => { e.stopPropagation(); dragGrup(e, b, g.iso) }}
                       ondragend={endDrag}
                       title="{b.sediu ? 'La sediu' : 'Deplasare'}{b.client ? ' · ' + b.client : ''}&#10;{b.items.map(p => '· ' + p.nume + (p.eticheta ? ' — ' + p.eticheta : '')).join('&#10;')}">
                    {#if start}<span class="seg-t">{etichetaGrup(b, g.iso)}</span>{/if}
                  </div>
                {/each}
              </div>
              {#if grupuri.length && !grupuri.some(b => !areGrup(addDays(g.iso, -1), b.cheie))}
                <!-- zi de continuare: blocurile n-au eticheta (ea sta pe prima zi
                     a deplasarii), deci spunem aici unde esti — altfel a doua zi
                     a unei iesiri arata ca niste dungi fara sens -->
                <span class="grp">{grupuri.length === 1 ? etichetaGrup(grupuri[0], g.iso) : `${grupuri.length} locuri`}</span>
              {/if}
            </button>
          {/each}
        </div>

        {#if legenda.length}
          <div class="leg">
            {#each legenda as l (l.nume)}
              <span class="leg-i" title={l.nume}><i style="background: {l.culoare}"></i>{l.scurt}</span>
            {/each}
            <span class="leg-i sep" title="Zilele la sediu apar hașurat, cele pe teren pline"><i class="hatch"></i>sediu</span>
          </div>
        {/if}
      </div>

      <aside class="side">
        <div class="pan">
          <div class="pan-zi">{dayLabel(selectata)}</div>
          {#if selectate.length}
            <div class="pan-sub">
              {#if grupuriSelectate.length > 1}
                <AlertTriangle size={13} /> {grupuriSelectate.length} locuri diferite în aceeași zi — verifică
              {:else if grupuriSelectate[0]?.sediu}
                <!-- la sediu NU esti in deplasare: nu urci in masina -->
                <Building2 size={13} /> la sediu{grupuriSelectate[0].client ? ' · ' + scurt(grupuriSelectate[0].client) : ''} · {selectate.length} {selectate.length === 1 ? 'lucrare' : 'lucrări'}
              {:else}
                {@const d = grupuriSelectate[0] ? deplasareaLui(grupuriSelectate[0], selectata) : null}
                <MapPin size={13} /> o deplasare{grupuriSelectate[0]?.client ? ' · ' + scurt(grupuriSelectate[0].client) : ''}{#if d && d.start !== d.end}{' · '}{shortDate(d.start)}–{shortDate(d.end)}, {d.items.size} {d.items.size === 1 ? 'lucrare' : 'lucrări'} în total{:else}{' · '}{selectate.length} {selectate.length === 1 ? 'lucrare' : 'lucrări'}{/if}
              {/if}
            </div>
            {#each selectate as p (p.id)}
              <div class="it" style="--c: {culoare(p.client)}" in:fade={{ duration: motionDuration(DUR_BASE) }}>
                <button class="it-t" onclick={() => navigate(`/projects/${p.proiect_id}`)}>
                  {p.nume}<ExternalLink size={12} />
                </button>
                <div class="it-m">
                  {#if p.eticheta}<span>{p.eticheta}</span>{/if}
                  <span class="loc">{p.locatie === 'sediu' ? 'Sediu' : 'Site'}</span>
                  <span class="st">{PROJECT_STATUS_LABELS[p.status] || p.status}</span>
                  <span class="tk" class:warn={!p.taskuri_deschise}>{p.taskuri_deschise ? `${p.taskuri_deschise} ${p.taskuri_deschise === 1 ? 'task' : 'taskuri'}` : 'niciun task'}</span>
                </div>
                {#if p.necesita_decizie}
                  <div class="dec">
                    <span class="dec-q">A trecut. S-a făcut?</span>
                    <button class="b ok" disabled={busy === p.id} onclick={() => setStatus(p, 'finalizat')}><Check size={12} /> Da</button>
                    {#if p.status !== 'in_lucru'}
                      <button class="b" disabled={busy === p.id} onclick={() => setStatus(p, 'in_lucru')}>În lucru</button>
                    {/if}
                    <button class="b" disabled={busy === p.id} onclick={() => muta(p, azi)}><Undo2 size={12} /> Mută pe azi</button>
                  </div>
                {/if}
                <div class="dec">
                  <button class="b" disabled={busy === p.id}
                          onclick={() => { mutaId = mutaId === p.id ? '' : p.id; mutaVal = '' }}>
                    <CalendarDays size={12} /> Mută
                  </button>
                  <!-- calea de intoarcere: fara ea, un proiect tras din „Fara
                       data" ramanea blocat in calendar -->
                  <button class="b del" disabled={busy === p.id} onclick={() => scoate(p)}
                          title="Scoate perioada din calendar — proiectul se întoarce în „Fără dată”">
                    <Undo2 size={12} /> Scoate
                  </button>
                  {#if mutaId === p.id}
                    <div class="mut" in:fade={{ duration: motionDuration(DUR_BASE) }}>
                      <DatePicker bind:value={mutaVal} />
                      <button class="b ok" disabled={!mutaVal || busy === p.id}
                              onclick={() => { muta(p, mutaVal); mutaId = ''; mutaVal = '' }}>Mută</button>
                    </div>
                  {/if}
                </div>
              </div>
            {/each}
          {:else}
            <div class="gol">Liber. Trage un proiect din „Proiecte fără dată" ca să-l planifici aici.</div>
          {/if}
        </div>

        {#if data.neplanificate?.length}
          <div class="pan">
            <div class="pan-h">Proiecte fără dată <span class="cnt">{data.neplanificate.length}</span></div>
            <div class="pan-hint">Trage pe o zi ca să planifici.</div>
            <div class="rail">
              {#each data.neplanificate as pr (pr.proiect_id)}
                <div class="np" style="--c: {culoare(pr.client)}" draggable="true"
                     ondragstart={(e) => dragProiect(e, pr)} ondragend={endDrag}>
                  <GripVertical size={12} />
                  <span class="np-t">{pr.nume}</span>
                  <span class="np-s" class:lucru={pr.status === 'in_lucru'}>{PROJECT_STATUS_LABELS[pr.status] || pr.status}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </aside>
    </div>
  {/if}
</div>

<style>
  .page { padding: var(--space-lg); }

  .bar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); flex-wrap: wrap; margin-bottom: var(--space-sm); }
  .nav { display: flex; align-items: center; gap: 6px; }
  .titlu { font-size: var(--font-body); font-weight: var(--fw-semibold); min-width: 148px; text-align: center; }
  .ico, .azi, .mods button { border: 1px solid var(--border); background: var(--bg-surface); color: var(--text-secondary);
    border-radius: var(--radius-sm); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
  .ico { width: 28px; height: 28px; }
  .azi, .mods button { height: 28px; padding: 0 10px; font-size: var(--font-tiny); }
  .ico:hover, .azi:hover, .mods button:hover { border-color: var(--accent); color: var(--accent); }
  .mods { display: flex; gap: 4px; }
  .mods button.on { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent-ring); }

  .kpis { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); flex-wrap: wrap; }
  .kpi { display: flex; align-items: baseline; gap: 6px; padding: 7px 12px; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); }
  .kpi.warn { background: color-mix(in srgb, var(--danger) 14%, transparent); border-color: var(--danger); cursor: pointer; }
  .k-n { font-family: var(--font-mono); font-size: var(--font-body); font-weight: var(--fw-bold); color: var(--text); font-variant-numeric: tabular-nums; }
  .kpi.warn .k-n { color: var(--danger); }
  .k-l { font-size: var(--font-tiny); color: var(--text-dim); }
  .kpi.warn .k-l { color: var(--danger); }

  .wrap { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: var(--space-md); align-items: start; }

  .cal { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-sm); }
  .wd { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; margin-bottom: 4px; }
  .wd span { font-size: var(--font-micro); color: var(--text-faint); text-align: center; text-transform: uppercase; letter-spacing: var(--tracking-wide); }
  .grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }

  .zi { position: relative; min-height: 76px; padding: 5px 5px 4px; border-radius: var(--radius-md);
        border: 1px solid var(--border); background: var(--bg-elevated); text-align: left; cursor: pointer;
        display: flex; flex-direction: column; gap: 3px; overflow: hidden;
        transition: border-color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease); }
  .grid.sapt .zi { min-height: 104px; }
  .zi:hover { border-color: var(--border-strong); }
  .zi.alta { opacity: 0.42; }
  .zi.we { background: color-mix(in srgb, var(--purple) 5%, var(--bg-elevated)); }
  /* Trei stari se pot suprapune pe aceeasi zi, deci fiecare pe alt canal SI pe
     alta culoare. Atentie: in tema asta --warning === --accent (#ffb454), deci
     avertizarile NU pot folosi warning — ar arata exact ca „azi".
       azi     = chenar amber (accent)
       decizie = chenar coral (danger), bate pe azi
       zi impartita intre clienti = bara violet jos
       selectia = contur interior (outline, ca sa nu se bata cu box-shadow) */
  .zi.azi { border-color: var(--accent); }
  .zi.decizie { border-color: var(--danger); }
  .zi.sel { background: var(--accent-subtle); outline: 2px solid var(--accent); outline-offset: -2px; }
  .zi.drop { border-style: dashed; border-color: var(--accent); background: var(--accent-subtle); }
  .zi.split { box-shadow: inset 0 -3px 0 var(--purple); }

  .n { font-family: var(--font-mono); font-size: var(--font-tiny); color: var(--text-dim); font-variant-numeric: tabular-nums; }
  .zi.azi .n { color: var(--accent); font-weight: var(--fw-bold); }
  .flag { position: absolute; top: 4px; right: 4px; color: var(--danger); display: inline-flex; }

  .segs { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
  .seg { position: relative; min-height: 17px; padding: 1px 5px; background: color-mix(in srgb, var(--c) 26%, transparent);
         border-left: 3px solid var(--c); cursor: grab; margin-right: -5px; margin-left: -5px; padding-left: 5px; }
  .seg.start { margin-left: 0; border-top-left-radius: var(--radius-sm); border-bottom-left-radius: var(--radius-sm); }
  .seg.end { margin-right: 0; border-top-right-radius: var(--radius-sm); border-bottom-right-radius: var(--radius-sm); }
  .seg:not(.start) { border-left: none; padding-left: 5px; }
  .seg:active { cursor: grabbing; }
  /* Zi la sediu = hasurat, zi pe teren = plin. Diferenta conteaza: una e zi de
     drum, cealalta nu. Aceeasi culoare de client, alta textura. */
  .seg.sediu { background: repeating-linear-gradient(135deg,
      color-mix(in srgb, var(--c) 30%, transparent) 0 4px,
      transparent 4px 8px); }
  .seg-t { display: block; font-size: var(--font-micro); line-height: 1.35; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .grp { font-size: var(--font-micro); color: var(--text-faint); margin-top: auto; }

  .leg { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; padding: 9px 4px 2px; margin-top: 6px; border-top: 1px solid var(--border); }
  .leg-i { display: inline-flex; align-items: center; gap: 6px; font-size: var(--font-micro); color: var(--text-dim); }
  .leg-i i { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
  .leg-i i.hatch { background: repeating-linear-gradient(135deg, var(--text-faint) 0 2px, transparent 2px 4px); border: 1px solid var(--border-strong); }

  .side { display: flex; flex-direction: column; gap: var(--space-md); }
  .pan { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-md); }
  .pan-zi { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); }
  .pan-sub { display: flex; align-items: center; gap: 5px; font-size: var(--font-tiny); color: var(--text-dim); margin: 3px 0 10px; }
  .pan-h { display: flex; align-items: center; gap: 8px; font-size: var(--font-micro); text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-faint); }
  .cnt { padding: 0 7px; border-radius: var(--radius-full); background: var(--bg-hover); color: var(--text-secondary); letter-spacing: 0; }
  .pan-hint { font-size: var(--font-micro); color: var(--text-faint); margin: 4px 0 8px; }
  .gol { font-size: var(--font-tiny); color: var(--text-dim); }

  .it { border-left: 3px solid var(--c); padding: 2px 0 2px 9px; margin-bottom: 12px; }
  .it-t { display: flex; align-items: center; gap: 5px; font-size: var(--font-small); color: var(--text); text-align: left; cursor: pointer; }
  .it-t:hover { color: var(--accent); }
  .it-m { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 3px; font-size: var(--font-micro); color: var(--text-dim); }
  .it-m .loc, .it-m .st { padding: 0 6px; border-radius: var(--radius-full); background: var(--bg-hover); }
  .it-m .tk.warn { color: var(--warning); }

  .dec { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-top: 7px; }
  .dec-q { font-size: var(--font-micro); color: var(--danger); width: 100%; }
  .mut { display: flex; align-items: flex-end; gap: 6px; width: 100%; margin-top: 4px; }
  .b { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-micro); padding: 3px 8px; border-radius: var(--radius-sm);
       border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-secondary); cursor: pointer; }
  .b:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .b:disabled { opacity: 0.5; cursor: default; }
  .b.ok { color: var(--success); border-color: color-mix(in srgb, var(--success) 45%, transparent); }
  .b.del:hover:not(:disabled) { border-color: var(--danger); color: var(--danger); }

  .rail { display: flex; flex-direction: column; gap: 4px; max-height: 260px; overflow-y: auto; }
  .np { display: flex; align-items: center; gap: 5px; padding: 5px 7px; border-radius: var(--radius-sm);
        background: var(--bg-elevated); border-left: 3px solid var(--c); cursor: grab; }
  .np:active { cursor: grabbing; }
  .np-t { flex: 1; font-size: var(--font-micro); color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .np-s { font-size: var(--font-micro); color: var(--text-faint); }
  .np-s.lucru { color: var(--accent); }

  @media (max-width: 900px) {
    .wrap { grid-template-columns: minmax(0, 1fr); }
    .side { order: -1; }
  }
  @media (max-width: 620px) {
    .page { padding: var(--space-md); }
    .zi { min-height: 58px; }
    .grid.sapt .zi { min-height: 76px; }
    .seg-t { display: none; }
    .seg { min-height: 12px; }
  }
</style>
