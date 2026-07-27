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
  import { ChevronLeft, ChevronRight, MapPin, Building2, Check, Undo2, ExternalLink, AlertTriangle, GripVertical, CalendarDays, Flag, Download } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { navigate, router } from '../lib/router.svelte.js'
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

  // Termenele (deadline de proiect) sunt ALTCEVA decat perioadele: perioada e
  // cand lucrezi, termenul e cand trebuie predat. Le aratam ca semn pe ziua lor,
  // ca sa se vada cand editezi un deadline si ca sa sara in ochi daca o iesire
  // e planificata DUPA termen.
  const termenePeZi = $derived.by(() => {
    const m = new Map()
    for (const t of (data?.termene || [])) {
      const iso = (t.deadline || '').slice(0, 10)
      if (!iso) continue
      if (!m.has(iso)) m.set(iso, [])
      m.get(iso).push(t)
    }
    return m
  })
  function termeneleZilei(iso) { return termenePeZi.get(iso) || [] }

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

  // ===== asezarea pe benzi =====
  // Ce s-a schimbat si de ce: pana acum ziua arata UN bloc per client, etichetat
  // „Continental · 4 lucrari". Dar din 12 perioade ale anului, 11 sunt la
  // Continental — deci codam prin culoare si grupare exact dimensiunea care NU
  // variaza, si ascundeam dupa un click singura care variaza: ce lucrare faci.
  // Acum fiecare LUCRARE are bara ei, cu numele ei.
  //
  // Banda (randul) e stabila pe toata durata lucrarii. Fara asta, o lucrare de
  // doua zile ar aparea pe randul 1 luni si pe randul 2 marti, iar bara n-ar mai
  // citi ca un singur lucru — ar sari. Impachetarea e cea clasica pe intervale:
  // primul rand liber, in ordinea inceputului.
  const MAX_BENZI = 3

  const benzi = $derived.by(() => {
    const m = new Map()
    const items = [...(data?.perioade || [])].sort((a, b) =>
      (a.data_start || '').localeCompare(b.data_start || '') ||
      String(a.id).localeCompare(String(b.id)))
    const ultima = []                       // ultima[banda] = ultima zi ocupata
    for (const p of items) {
      const a = p.data_start
      const b = p.data_sfarsit || p.data_start
      let l = 0
      while (ultima[l] !== undefined && ultima[l] >= a) l++
      ultima[l] = b
      m.set(p.id, l)
    }
    return m
  })

  const nrBenzi = $derived.by(() => {
    let max = 0
    for (const g of grila) {
      for (const p of aleZilei(g.iso)) max = Math.max(max, (benzi.get(p.id) ?? 0) + 1)
    }
    return Math.min(MAX_BENZI, max)
  })

  /** Randurile zilei: pozitia din array E banda, `null` = rand gol (distantier,
   *  ca barele vecine sa ramana aliniate pe orizontala). */
  function randurileZilei(iso) {
    const randuri = new Array(nrBenzi).fill(null)
    let ascunse = 0
    for (const p of aleZilei(iso)) {
      const l = benzi.get(p.id) ?? 0
      if (l < nrBenzi) randuri[l] = p
      else ascunse++
    }
    return { randuri, ascunse }
  }

  function esteInceput(p, iso) { return iso === p.data_start }
  function esteSfarsit(p, iso) { return iso === (p.data_sfarsit || p.data_start) }

  /** Numele lucrarii, nu al clientului: „Montaj", nu „Continental". */
  function etichetaLucrare(p) {
    return (p.eticheta || '').trim() || (p.nume || '').trim() || '—'
  }

  /** Pentru bara din grila: fara detaliul din paranteze. Intr-o celula de ~145px
   *  „Upgrade PILZ + MM (Apex 4/5/7/10)" se taia fix dupa „(Ap...", adica pierdeai
   *  si detaliul, si finalul numelui. Textul intreg ramane in tooltip si in
   *  panoul zilei, unde exista loc. */
  function etichetaBara(p) {
    return etichetaLucrare(p).replace(/\s*\([^)]*\)\s*/g, ' ').trim() || etichetaLucrare(p)
  }

  /** Culoarea urmareste PROIECTUL, ca aceeasi lucrare sa fie acelasi lucru de la
   *  o zi la alta. Pe client n-avea sens: aproape tot e Continental. */
  function culoareLucrare(p) { return culoare(p.proiect_id || p.nume) }

  /** Deplasarile care INCEP in ziua asta — captura mica de deasupra barelor.
   *  Doar la inceput, nu in fiecare zi: altfel „Continental" s-ar repeta peste tot. */
  function incepDeplasari(iso) {
    return deplasari.filter(d => d.start === iso)
  }

  // Ce urmeaza, cand ziua selectata e goala: pagina trebuie sa raspunda la
  // „cand ies data viitoare" fara sa navighezi luni intregi. Perioadele din
  // fereastra sunt deja incarcate; luam prima care incepe dupa ziua selectata.
  const ceUrmeaza = $derived.by(() => {
    const dupa = deplasari
      .filter(d => d.start >= selectata)
      .sort((a, b) => a.start.localeCompare(b.start))
    return dupa[0] || null
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
  async function mutaGrup(lucrari, ziSursa, ziTinta) {
    const delta = diffDays(ziSursa, ziTinta)
    if (!delta) return
    busy = ziSursa
    try {
      for (const p of lucrari) {
        await apiJson(`/api/implementari/${p.id}`, {
          method: 'PUT',
          body: {
            data_start: addDays(p.data_start, delta),
            data_sfarsit: addDays(p.data_sfarsit || p.data_start, delta),
          },
        })
      }
      toast(lucrari.length > 1
        ? `Deplasare mutată — ${lucrari.length} lucrări`
        : `Mutat pe ${shortDate(ziTinta)}`, 'success')
      selectata = ziTinta
      await load(true)
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = '' }
  }

  // ===== drag & drop =====
  // Doua manere, doua intelesuri, ca sa nu trebuiasca sa alegi dintr-un meniu:
  //   bara      -> muti LUCRAREA aia
  //   captura   -> muti toata DEPLASAREA, pastrandu-i forma
  function dragLucrare(e, p) {
    dragged = { tip: 'lucrare', p }
    e.dataTransfer.effectAllowed = 'move'
    try { e.dataTransfer.setData('text/plain', String(p.id)) } catch (_) {}
  }
  function dragDeplasare(e, d) {
    dragged = { tip: 'deplasare', d }
    e.dataTransfer.effectAllowed = 'move'
    try { e.dataTransfer.setData('text/plain', d.cheie) } catch (_) {}
  }
  function dragProiect(e, proj) {
    dragged = { tip: 'proiect', proj }
    e.dataTransfer.effectAllowed = 'copy'
    try { e.dataTransfer.setData('text/plain', proj.proiect_id) } catch (_) {}
  }
  function overZi(e, iso) {
    if (!dragged) return
    e.preventDefault()
    e.dataTransfer.dropEffect = dragged.tip === 'proiect' ? 'copy' : 'move'
    dropZi = iso
  }
  function dropPeZi(e, iso) {
    if (!dragged) return
    e.preventDefault()
    const d = dragged
    dragged = null
    dropZi = ''
    if (d.tip === 'lucrare') { if (d.p.data_start !== iso) muta(d.p, iso) }
    else if (d.tip === 'deplasare') { if (d.d.start !== iso) mutaGrup([...d.d.items.values()], d.d.start, iso) }
    else planifica(d.proj, iso)
  }
  function endDrag() { dragged = null; dropZi = '' }

  onMount(() => {
    ui.pageHeader = { title: 'Calendar', subtitle: 'Unde ești în fiecare zi' }
    // Planificatorul trimite aici cu #/calendar?zi=AAAA-LL-ZZ cand dai click pe o
    // banda de perioada: perioadele se editeaza intr-un singur loc, aici.
    const zi = router.query?.zi
    if (zi && /^\d{4}-\d{2}-\d{2}$/.test(zi)) {
      selectata = zi
      anchor = monthStart(zi)
    }
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
        <!-- Exportul .ics a venit aici din Admin (sters): calendarul de abonat din
             telefon apartine paginii de calendar, nu unui sertar de intretinere. -->
        <button class="ics" onclick={() => window.open('/api/export/ics', '_blank')}
                title="Descarcă .ics — perioadele, termenele și scadențele. Abonează-te din calendarul telefonului.">
          <Download size={13} /> .ics
        </button>
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
      {#if data.probleme?.length}
        <!-- Nimic nu dispare in tacere: o data pe care aplicatia nu o poate citi
             nu se aseaza pe nicio zi, deci randul lipseste din calendar fara
             niciun semn. Mai bine un semnal suparator decat o absenta tacuta. -->
        <button class="kpi warn" onclick={() => navigate(`/projects/${data.probleme[0].proiect_id}`)}
                title={data.probleme.map(p => `${p.nume} — ${p.unde}, ${p.camp}: „${p.valoare}”`).join('\n')}>
          <span class="k-n">{data.probleme.length}</span>
          <span class="k-l">{data.probleme.length === 1 ? 'dată necitibilă' : 'date necitibile'}</span>
        </button>
      {/if}
    </div>

    <div class="wrap">
      <div class="cal">
        <div class="wd">
          {#each WEEKDAYS as w}<span>{w}</span>{/each}
        </div>
        <!-- Inaltimea celulei urmeaza numarul real de benzi din fereastra: o luna
             cu o singura lucrare pe zi nu mai are jumatate de celula goala, iar
             una densa ca augustul incape fara sa strivim barele. -->
        <div class="grid" class:sapt={mod === 'saptamani'} style="--benzi: {Math.max(1, nrBenzi)}">
          {#each grila as g (g.iso)}
            {@const items = aleZilei(g.iso)}
            {@const decizie = items.some(p => p.necesita_decizie)}
            {@const zi = randurileZilei(g.iso)}
            {@const capturi = incepDeplasari(g.iso)}
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
              <!-- Antetul zilei e o linie de inaltime FIXA: numarul + captura
                   deplasarii. Captura a stat initial pe rand propriu si impingea
                   barele in jos doar in zilele de plecare — asa, bara de patru
                   zile nu se mai lega intre 3 si 4 august, adica exact ce trebuia
                   sa repare benzile. Un rand in plus intr-o singura celula strica
                   alinierea intregii saptamani. -->
              <div class="zi-h">
                <span class="n">{parseISO(g.iso).getDate()}</span>
                {#each capturi as d (d.cheie)}
                  <span class="cap" class:sediu={d.sediu}
                        draggable="true"
                        ondragstart={(e) => { e.stopPropagation(); dragDeplasare(e, d) }}
                        ondragend={endDrag}
                        title="{d.sediu ? 'La sediu' : 'Deplasare'}{d.client ? ' · ' + d.client : ''} · {d.items.size} {d.items.size === 1 ? 'lucrare' : 'lucrări'}&#10;Trage ca să muți toată ieșirea">
                    {#if d.sediu}<Building2 size={9} />{:else}<MapPin size={9} />{/if}{d.sediu && d.client ? `Sediu · ${scurt(d.client)}` : d.sediu ? 'Sediu' : scurt(d.client)}
                  </span>
                {/each}
              </div>
              {#if decizie}<span class="flag" title="Perioadă trecută, proiect nemutat"><AlertTriangle size={11} /></span>
              {:else if termeneleZilei(g.iso).length}
                <span class="term" title="Termen: {termeneleZilei(g.iso).map(t => t.nume).join(', ')}"><Flag size={11} /></span>
              {/if}

              <!-- O bara per LUCRARE, pe banda ei. Randurile goale sunt
                   distantiere: fara ele, o lucrare de doua zile s-ar muta de pe
                   un rand pe altul si bara n-ar mai citi ca un singur lucru. -->
              <div class="segs">
                {#each zi.randuri as p, l (l)}
                  {#if p}
                    <div class="seg" class:start={esteInceput(p, g.iso)} class:end={esteSfarsit(p, g.iso)}
                         class:sediu={p.locatie === 'sediu'}
                         style="--c: {culoareLucrare(p)}"
                         draggable="true"
                         ondragstart={(e) => { e.stopPropagation(); dragLucrare(e, p) }}
                         ondragend={endDrag}
                         title="{p.nume}{p.eticheta ? '&#10;' + p.eticheta : ''}&#10;{shortDate(p.data_start)}{p.data_sfarsit && p.data_sfarsit !== p.data_start ? ' – ' + shortDate(p.data_sfarsit) : ''}{p.locatie === 'sediu' ? ' · la sediu' : ''}&#10;Trage ca să muți lucrarea">
                      <span class="seg-t">{etichetaBara(p)}</span>
                    </div>
                  {:else}
                    <div class="seg-gol" aria-hidden="true"></div>
                  {/if}
                {/each}
              </div>
              {#if zi.ascunse}<span class="plus">+{zi.ascunse}</span>{/if}
              {#if items.length > 1}
                <!-- Doar pe telefon. La 390px o celula are ~48px: nu incape text,
                     iar „Upg…" nu spune nimic. Numarul de lucrari se citeste, si
                     detaliul e oricum in panoul de deasupra, la o atingere. -->
                <span class="grp">{items.length}</span>
              {/if}
            </button>
          {/each}
        </div>

        <!-- Legenda de culori a plecat: culoarea urmareste proiectul, iar numele
             lucrarii scrie chiar in bara, deci o legenda ar repeta ce se vede.
             Ramane doar textura, care nu se poate citi altfel. -->
        {#if data.perioade?.length}
          <div class="leg">
            <span class="leg-i" title="Zilele la sediu apar hașurat, cele pe teren pline"><i class="hatch"></i>la sediu</span>
            <span class="leg-i"><i class="plin"></i>pe teren</span>
            <span class="leg-i"><Flag size={11} /> termen</span>
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
              <div class="it" style="--c: {culoareLucrare(p)}" in:fade={{ duration: motionDuration(DUR_BASE) }}>
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
                          title="Scoate perioada din calendar — proiectul se întoarce în „Proiecte fără perioadă”">
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
          {:else if !termeneleZilei(selectata).length}
            <!-- O zi goala nu trebuie sa fie un ecran gol. Intrebarea reala nu e
                 „ce e azi", ci „cand ies data viitoare" — mai ales ca lunile
                 intregi sunt libere si altfel ai naviga in gol ca s-o afli. -->
            <div class="gol">Liber.</div>
            {#if ceUrmeaza}
              <button class="urm" onclick={() => { selectata = ceUrmeaza.start; anchor = monthStart(ceUrmeaza.start) }}>
                <span class="urm-h">Urmează</span>
                <span class="urm-d">
                  {#if ceUrmeaza.sediu}<Building2 size={12} />{:else}<MapPin size={12} />{/if}
                  {ceUrmeaza.sediu ? 'Sediu' : scurt(ceUrmeaza.client)}
                  · {shortDate(ceUrmeaza.start)}{#if ceUrmeaza.start !== ceUrmeaza.end}–{shortDate(ceUrmeaza.end)}{/if}
                </span>
                <span class="urm-l">{[...ceUrmeaza.items.values()].map(etichetaLucrare).join(' · ')}</span>
              </button>
            {:else}
              <div class="gol">Trage un proiect din „Proiecte fără perioadă" ca să-l planifici aici.</div>
            {/if}
          {/if}

          {#each termeneleZilei(selectata) as t (t.proiect_id)}
            <div class="term-it">
              <Flag size={12} />
              <button class="term-t" onclick={() => navigate(`/projects/${t.proiect_id}`)}>{t.nume}</button>
              <span class="term-l">termen</span>
            </div>
          {/each}
        </div>

        {#if data.neplanificate?.length}
          <div class="pan">
            <!-- „fara perioada", nu „fara data": perioada e un interval (unde
                 esti), termenul e un punct (pana cand). Sertarul din Planificator
                 tine ALTCEVA — taskuri fara termen — si numele trebuie sa spuna
                 asta, nu sa le faca sa para acelasi lucru. -->
            <div class="pan-h">Proiecte fără perioadă <span class="cnt">{data.neplanificate.length}</span></div>
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
  .mods button.ics { gap: 5px; margin-left: 6px; }

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

  .zi { position: relative; min-height: calc(38px + var(--benzi, 1) * 20px); padding: 5px 5px 4px; border-radius: var(--radius-md);
        border: 1px solid var(--border); background: var(--bg-elevated); text-align: left; cursor: pointer;
        display: flex; flex-direction: column; gap: 3px; overflow: hidden;
        transition: border-color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease); }
  /* In „2 sapt." sunt doar doua randuri de afisat, deci celulele pot respira. */
  .grid.sapt .zi { min-height: calc(62px + var(--benzi, 1) * 20px); }
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
  /* Termen = alt tip de semnal decat „perioada a trecut", deci alta culoare */
  .term { position: absolute; top: 4px; right: 4px; color: var(--purple); display: inline-flex; }
  .term-it { display: flex; align-items: center; gap: 6px; padding: 6px 0 0; border-top: 1px solid var(--border); margin-top: 8px; color: var(--purple); }
  .term-t { flex: 1; text-align: left; font-size: var(--font-tiny); color: var(--text-secondary); cursor: pointer; }
  .term-t:hover { color: var(--accent); }
  .term-l { font-size: var(--font-micro); color: var(--purple); }

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
  /* Rand gol = distantier. Trebuie sa aiba EXACT inaltimea unei bare, altfel
     benzile vecine nu se mai aliniaza si continuitatea pe orizontala se pierde. */
  .seg-gol { min-height: 17px; }
  .seg-t { display: block; font-size: var(--font-micro); line-height: 1.35; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* Antet de inaltime fixa — vezi comentariul din template: orice variatie aici
     desincronizeaza benzile pe orizontala. nowrap + overflow hidden garanteaza
     ca ramane pe un rand oricat de lung ar fi numele clientului. */
  .zi-h { display: flex; align-items: center; gap: 5px; min-height: 15px; max-width: 100%;
          white-space: nowrap; overflow: hidden; padding-right: 14px; }
  .cap { display: inline-flex; align-items: center; gap: 3px; min-width: 0;
         padding: 0 5px 0 3px; border-radius: var(--radius-full);
         font-size: var(--font-micro); line-height: 1.45; color: var(--text-secondary);
         background: var(--bg-hover); border: 1px solid var(--border); cursor: grab;
         overflow: hidden; text-overflow: ellipsis; }
  .cap:active { cursor: grabbing; }
  .cap.sediu { color: var(--text-dim); }

  .plus { align-self: flex-start; font-size: var(--font-micro); color: var(--text-faint); }
  /* Eticheta de sub zi e ACUM exclusiv pentru telefon — pe desktop textul sta in
     bara, pe fiecare zi a deplasarii. Un singur rand, obligatoriu: lasata sa se
     impacheteze, umfla celula si trage dupa ea tot randul de saptamana. */
  .grp { display: none; font-size: var(--font-micro); color: var(--text-faint); margin-top: auto;
         max-width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .leg { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 14px; padding: 9px 4px 2px; margin-top: 6px; border-top: 1px solid var(--border); }
  .leg-i { display: inline-flex; align-items: center; gap: 6px; font-size: var(--font-micro); color: var(--text-dim); }
  .leg-i i { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
  .leg-i i.hatch { background: repeating-linear-gradient(135deg, var(--text-faint) 0 2px, transparent 2px 4px); border: 1px solid var(--border-strong); }
  .leg-i i.plin { background: color-mix(in srgb, var(--text-faint) 45%, transparent); border: 1px solid var(--border-strong); }

  .side { display: flex; flex-direction: column; gap: var(--space-md); }
  .pan { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-md); }
  .pan-zi { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); }
  .pan-sub { display: flex; align-items: center; gap: 5px; font-size: var(--font-tiny); color: var(--text-dim); margin: 3px 0 10px; }
  .pan-h { display: flex; align-items: center; gap: 8px; font-size: var(--font-micro); text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-faint); }
  .cnt { padding: 0 7px; border-radius: var(--radius-full); background: var(--bg-hover); color: var(--text-secondary); letter-spacing: 0; }
  .pan-hint { font-size: var(--font-micro); color: var(--text-faint); margin: 4px 0 8px; }
  .gol { font-size: var(--font-tiny); color: var(--text-dim); }

  .urm { display: flex; flex-direction: column; gap: 3px; width: 100%; text-align: left; margin-top: 10px;
         padding: 9px 11px; border-radius: var(--radius-md); border: 1px solid var(--border);
         background: var(--bg-elevated); cursor: pointer; }
  .urm:hover { border-color: var(--accent); }
  .urm-h { font-size: var(--font-micro); text-transform: uppercase; letter-spacing: 0.14em; color: var(--text-faint); }
  .urm-d { display: flex; align-items: center; gap: 5px; font-size: var(--font-small); color: var(--text); }
  .urm-l { font-size: var(--font-micro); color: var(--text-dim); line-height: 1.45; }

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
    .zi { min-height: calc(30px + var(--benzi, 1) * 14px); }
    .grid.sapt .zi { min-height: calc(46px + var(--benzi, 1) * 14px); }
    .seg-t { display: none; }
    /* Captura se taia oricum la o felie ilizibila intr-o celula de ~48px, iar
       „unde ești" scrie in panoul de deasupra. */
    .cap { display: none; }
    .grp { display: block; text-align: right; }
    .seg { min-height: 12px; }
  }
</style>
