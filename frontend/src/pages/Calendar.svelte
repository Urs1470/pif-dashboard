<script>
  // Calendar — „unde sunt".
  //
  // Ion e o singura persoana, iar planificarea lui reala sunt PERIOADELE, fiecare
  // cu faza ei: pregatire sau implementare. Deadline-urile au plecat in v30 —
  // „noi nu intram in deadline-uri din partea clientului niciodata". Intrebarea la
  // care raspunde ecranul asta e „unde sunt marti si ce fac", iar deciziile stau
  // TOT aici, pe ziua respectiva — nu intr-o lista separata de reprosuri.
  //
  // O bara per LUCRARE, cu numele ei; culoarea urmareste proiectul. Deplasarea
  // (zile consecutive la acelasi client) ramane, dar ca o captura in ziua de
  // plecare, nu ca un bloc care inghite lucrarile.
  import { onMount, onDestroy } from 'svelte'
  import { fade } from 'svelte/transition'
  import { ChevronLeft, ChevronRight, MapPin, Building2, Check, X, Undo2, ExternalLink, AlertTriangle, GripVertical, CalendarDays, Download } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { navigate, router } from '../lib/router.svelte.js'
  import { toast } from '../stores/ui.svelte.js'
  import { ui } from '../stores/ui.svelte.js'
  import { motion, motionDuration, DUR_BASE } from '../lib/motion.svelte.js'
  import { PROJECT_STATUS_LABELS } from '../lib/formatters.js'
  import { culoareProiect } from '../lib/culori.js'
  import { incepeTragere } from '../lib/tragere.js'
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
  // Gestul in curs: { tip: 'lucrare'|'capat'|'deplasare'|'proiect', ... }.
  let trag = $state(null)
  let dropZi = $state('')
  // Ce s-ar intampla daca ai lasa acum: Map(id perioada -> {data_start, data_sfarsit}).
  // Se aplica DOAR benzilor desenate, nu si datelor din care se calculeaza randul
  // benzii sau continutul zilei — altfel toata grila s-ar reaseza sub deget.
  let previz = $state(null)
  // Un `click` vine si dupa o tragere reusita. Fara steag, mutarea unei benzi
  // ar schimba pe urma si ziua selectata, adica panoul ar sari in alta parte.
  let tocmaiTras = false
  let mutaId = $state('')      // perioada pentru care e deschis selectorul de data
  let mutaVal = $state('')

  const azi = todayISO()

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

  // INALTIMEA URMEAZA SAPTAMANA, NU FEREASTRA.
  //
  // Era UN singur numar — maximul pe toata fereastra — si intra direct in
  // `min-height`-ul FIECAREI celule. O zi cu trei lucrari facea toate cele 42 de
  // celule ale lunii inalte de 98px: doua sute de pixeli de gol rezervat pe
  // verticala pentru o singura zi. In „2 săpt." baza urca de la 38 la 62px, deci
  // efectul se dubla.
  //
  // Se poate dimensiona pe saptamana tocmai pentru ca `feliaza()` taie deja orice
  // banda la granita de saptamana: nicio banda nu traverseaza doua randuri, deci
  // inaltimile pot sa difere fara ca nimic sa se desincronizeze.
  const benziPeRand = $derived.by(() => {
    const out = []
    for (let i = 0; i < grila.length; i++) {
      const r = Math.floor(i / 7)
      let max = 0
      for (const p of aleZilei(grila[i].iso)) max = Math.max(max, (benzi.get(p.id) ?? 0) + 1)
      out[r] = Math.max(out[r] || 0, Math.min(MAX_BENZI, max))
    }
    return out.map(v => Math.max(1, v || 0))
  })

  /** Cate benzi incap in randul din care face parte ziua. */
  function plafonZi(iso) {
    const i = indexZile.get(iso)
    return i === undefined ? 1 : (benziPeRand[Math.floor(i / 7)] ?? 1)
  }

  /** Lucrarile care nu incap in benzile disponibile — se numara in „+N". */
  function ascunseZi(iso) {
    const plafon = plafonZi(iso)
    return aleZilei(iso).filter(p => (benzi.get(p.id) ?? 0) >= plafon).length
  }

  /** Ce se deseneaza: UN element per lucrare per SAPTAMANA, nu per zi.
   *
   *  De ce s-a schimbat: o perioada de patru zile era desenata ca patru obiecte,
   *  fiecare cu numele scris din nou si trunchiat la latimea UNEI celule. Pentru o
   *  singura lucrare de sase zile, „Pregatire documentatie …" aparea de noua ori —
   *  si fiecare copie era ciuntita, desi lucrarea avea sase celule de spatiu. Doua
   *  trunchieri diferite ale aceluiasi text, una langa alta, se citesc ca doua
   *  lucruri diferite, nu ca unul care continua.
   *
   *  Acum felia se intinde peste coloane (`grid-column: <col> / span <n>`), deci
   *  numele se scrie o data si are la dispozitie toata latimea lucrarii. Singura
   *  taietura e la granita de saptamana, unde randul se termina fizic — acolo
   *  capatul rămâne drept si eticheta primeste „…", ca sa se vada ca vine de mai
   *  sus.
   */
  const indexZile = $derived(new Map(grila.map((g, i) => [g.iso, i])))

  /** Taie intervalul [a, b] in felii de saptamana, gata de asezat in grila. */
  function feliaza(a, b, banda, p) {
    const out = []
    if (!grila.length || !a) return out
    const prima = grila[0].iso
    const ultimaZi = grila[grila.length - 1].iso
    if (b < prima || a > ultimaZi) return out
    let i = indexZile.get(a < prima ? prima : a)
    const fin = indexZile.get(b > ultimaZi ? ultimaZi : b)
    if (i === undefined || fin === undefined) return out
    while (i <= fin) {
      const capat = Math.min(fin, Math.floor(i / 7) * 7 + 6)
      out.push({
        p, banda,
        rand: Math.floor(i / 7) + 1,
        col: (i % 7) + 1,
        span: capat - i + 1,
        zile: grila.slice(i, capat + 1).map(g => g.iso),
        inceput: grila[i].iso === a,        // capatul ADEVARAT, nu al feliei
        sfarsit: grila[capat].iso === b,
        cheie: `${p.id}|${grila[i].iso}`,
      })
      i = capat + 1
    }
    return out
  }

  const bare = $derived.by(() => {
    const out = []
    for (const p of (data?.perioade || [])) {
      const banda = benzi.get(p.id) ?? 0
      for (const f of feliaza(p.data_start, p.data_sfarsit || p.data_start, banda, p)) {
        // Plafonul e al SAPTAMANII feliei, nu al ferestrei: o lucrare poate incapea
        // intr-un rand si sa se numere in „+N" in altul. Peste plafon: „+N".
        if (banda < (benziPeRand[f.rand - 1] ?? 1)) out.push(f)
      }
    }
    return out
  })

  /** UNDE AR AJUNGE, cat timp tii apasat.
   *
   *  E un al doilea set de benzi, desenat peste cele reale — nu o mutare a celor
   *  reale. Motivul e mecanic, nu estetic: banda apucata e chiar elementul care
   *  primeste evenimentele gestului. Daca ar fi re-randata la fiecare pixel
   *  (cheia ei contine ziua de inceput), Svelte ar distruge nodul, iar pe touch
   *  captura implicita a pointerului moare odata cu el — tragerea s-ar rupe
   *  exact in momentul in care incepe sa functioneze. */
  const fantome = $derived.by(() => {
    if (!previz) return []
    const out = []
    for (const p of (data?.perioade || [])) {
      const v = previz.get(p.id)
      if (!v) continue
      const banda = benzi.get(p.id) ?? 0
      for (const f of feliaza(v.data_start, v.data_sfarsit || v.data_start, banda, p)) {
        if (banda < (benziPeRand[f.rand - 1] ?? 1)) out.push(f)
      }
    }
    return out
  })

  /** Ziua de sub cursor INTR-O banda: pe o felie de patru zile, punctul apasat
   *  pe joi inseamna joi, nu inceputul lucrarii. */
  function ziDinBanda(x, el, b) {
    const r = el.getBoundingClientRect()
    const k = Math.floor(((x - r.left) / r.width) * b.span)
    return b.zile[Math.min(b.span - 1, Math.max(0, k))]
  }

  /** Atingerea unei benzi face exact ce face ziua de sub ea. Asa banda ramane
   *  „decor peste celula" (decizia luata pentru telefon) desi acum e apucabila:
   *  o atingere scurta nu poate ajunge altundeva decat ar fi ajuns fara ea. */
  function clickBanda(e, b) {
    if (tocmaiTras) return
    atingeZi(ziDinBanda(e.clientX, e.currentTarget, b))
  }

  /** Numele lucrarii, nu al clientului: „Montaj", nu „Continental". */
  function etichetaLucrare(p) {
    return (p.eticheta || '').trim() || (p.nume || '').trim() || '—'
  }

  // Titlurile pe mai multe randuri se construiesc in JS, nu in atribut. Motivul:
  // intr-un atribut Svelte, `\n` e text literal, iar `&#10;` nu e decodat
  // consecvent — ajungea sa se vada „&#10;" chiar si in bula nativa. Aici, intr-un
  // sir JS, `\n` chiar e rand nou, iar Tooltip.svelte il randeaza ca atare.
  function etichetaDeplasare(d) {
    const n = d.items.size
    return `${d.sediu ? 'La sediu' : 'Deplasare'}${d.client ? ' · ' + d.client : ''}`
      + ` · ${n} ${n === 1 ? 'lucrare' : 'lucrări'}`
      + `\nTrage ca să muți toată ieșirea`
  }

  function etichetaLucrareLunga(p) {
    const sfarsit = p.data_sfarsit && p.data_sfarsit !== p.data_start
      ? ` – ${shortDate(p.data_sfarsit)}` : ''
    return [
      p.nume,
      p.eticheta || '',
      `${shortDate(p.data_start)}${sfarsit}`
        + `${p.locatie === 'sediu' ? ' · la sediu' : ' · pe teren'}`
        + ` · ${p.faza === 'pregatire' ? 'pregătire' : 'implementare'}`,
      'Trage de mijloc ca să muți · de capete ca să schimbi perioada',
    ].filter(Boolean).join('\n')
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
  function culoareLucrare(p) { return culoareProiect(p.proiect_id || p.nume) }

  /** Deplasarile care INCEP in ziua asta — captura mica de deasupra barelor.
   *  Doar la inceput, nu in fiecare zi: altfel „Continental" s-ar repeta peste tot. */
  function incepDeplasari(iso) {
    return deplasari.filter(d => d.start === iso)
  }

  /** Clientul obisnuit al ferestrei. Din 12 perioade ale anului, 11 sunt la
   *  Continental — deci numele lui nu selecteaza nimic. */
  const clientObisnuit = $derived.by(() => {
    const n = new Map()
    for (const p of (data?.perioade || [])) {
      const c = (p.client || '').trim()
      if (c) n.set(c, (n.get(c) || 0) + 1)
    }
    let best = '', bn = 0
    for (const [c, k] of n) if (k > bn) { best = c; bn = k }
    return best
  })

  /** CAPTURA SCRIE CE VARIAZA.
   *  Comentariul de la benzi spune limpede ca nu codam prin culoare si grupare
   *  dimensiunea care NU variaza — dar captura ramasese pe `scurt(client)`, deci
   *  scria „Continental" pe patru din sapte iesiri ale lunii. Si `scurt()` ia
   *  primul cuvant, deci doi clienti cu acelasi prim cuvant ajungeau aceeasi
   *  eticheta. Acum scrie DURATA ieșirii — ce te intereseaza dupa ce ai planificat
   *  — iar clientul apare doar cand nu e cel obisnuit al ferestrei. Numele complet
   *  ramane in tooltip si in panoul zilei. */
  function textCaptura(d) {
    const z = Math.max(0, diffDays(d.start, d.end)) + 1
    const durata = `${z} ${z === 1 ? 'zi' : 'zile'}`
    const c = (d.client || '').trim()
    return c && c !== clientObisnuit ? `${scurt(c)} · ${durata}` : durata
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

  // „N DE CLARIFICAT" PARCURGE LISTA, NU DUCE MEREU LA PRIMUL.
  // Contorul numara `de_decis.length`, dar clickul sarea fix la `de_decis[0]`:
  // apasai a doua oara si nu se intampla nimic, erai deja acolo. Un contor care
  // spune trei si duce intr-un singur loc nu e navigatie, e o notificare care se
  // preface. Acum fiecare apasare duce la urmatoarea, iar contorul arata unde esti.
  let idxDecis = $state(0)
  const deDecis = $derived(data?.de_decis || [])
  // Cand una se bifeaza, lista se scurteaza sub indexul curent — il aducem inapoi
  // in interval ca bucla sa se inchida singura.
  const decisCurent = $derived(deDecis.length ? idxDecis % deDecis.length : 0)

  function urmatorulDeClarificat() {
    if (!deDecis.length) return
    const d = deDecis[decisCurent]
    selectata = d.data_sfarsit || d.data_start
    anchor = mod === 'luna' ? monthStart(selectata) : weekStart(selectata)
    idxDecis = (decisCurent + 1) % deDecis.length
    load()
    aratPanoul()
  }

  // AGENDA FERESTREI — raspunsul la „ce am luna asta", pe telefon.
  //
  // Sub 620px `.banda-t` si `.cap` sunt `display: none`, deci grila ramane o harta
  // de dungi colorate in care singurul purtator de identitate e CULOAREA — iar
  // `culoareProiect()` imparte sapte culori peste toate proiectele, deci doua pot
  // cadea pe aceeasi. Pe desktop numele le desparte; aici nu le despartea nimic.
  // Ca sa afli ce e o dunga trebuia s-o atingi; ca sa citesti luna, treizeci si una
  // de atingeri — si tot atatea derulari, fiindca `aratPanoul()` derula de fiecare
  // data. `deplasari` era deja calculat in pagina: asta e prima lui folosire care
  // nu cere o atingere.
  const agendaLunii = $derived.by(() => {
    if (!grila.length) return []
    const prima = grila[0].iso
    const ultima = grila[grila.length - 1].iso
    return deplasari
      .filter(d => d.end >= prima && d.start <= ultima)
      .sort((a, b) => a.start.localeCompare(b.start) || a.cheie.localeCompare(b.cheie))
      .map(d => {
        const lucrari = [...d.items.values()]
        return {
          ...d, lucrari,
          titlu: d.sediu ? (d.client ? `Sediu · ${scurt(d.client)}` : 'Sediu') : (scurt(d.client) || 'Pe teren'),
          cand: d.start === d.end ? shortDate(d.start) : `${shortDate(d.start)} – ${shortDate(d.end)}`,
          culoare: culoareLucrare(lucrari[0] || {}),
        }
      })
  })

  /** Ziua selectata cade in iesirea asta? Atingerea unei zile APRINDE randul ei
   *  din agenda, in loc sa schimbe un panou. */
  function esteAprinsa(d) { return selectata >= d.start && selectata <= d.end }

  /** Randul aprins, adus in vizor doar daca a ramas complet in afara ecranului —
   *  aceeasi garda ca la `aratPanoul`, dar saritura e de cateva randuri, nu peste
   *  toata grila. */
  function aratIesirea() {
    if (window.innerWidth > 900) return
    requestAnimationFrame(() => {
      const el = document.querySelector('.ag-rand.aprins')
      if (!el) return
      const r = el.getBoundingClientRect()
      if (r.top >= 0 && r.bottom <= window.innerHeight) return
      el.style.scrollMarginTop = 'calc(var(--header-height) + 8px)'
      el.scrollIntoView({ behavior: motion.reduced ? 'auto' : 'smooth', block: 'center' })
    })
  }

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
  /** „S-a facut?" e o intrebare despre PERIOADA, deci raspunsul se scrie tot pe
   *  ea. Pana in v39, „Da" chema `PUT /api/proiecte {status: 'finalizat'}` —
   *  adica inchidea proiectul pentru ca ai fost intr-o deplasare. Ion: „dupa
   *  implementare pot sa mai am de facut pv-uri sau altceva, sau poate va mai
   *  trebui de facut vizita pe care nu stiu cand va fi."
   *
   *  Si greseala se ascundea singura: proiectul inchis iese din „Proiecte fara
   *  perioada", deci exact vizita aia nedatata nu mai avea de unde sa fie
   *  planificata. Proiectul se inchide doar din formularul lui, langa
   *  „Finalizat pe". */
  async function confirma(p, val) {
    busy = p.id
    try {
      await apiJson(`/api/implementari/${p.id}`, { method: 'PUT', body: { confirmata: val } })
      toast(val ? 'S-a făcut · proiectul rămâne deschis' : 'Bifa scoasă', 'success')
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

  /** Schimba capetele perioadei, fara sa o mute. Perechea lui `muta`: acolo
   *  durata e fixa si se schimba ziua, aici ziua de sprijin e fixa si se schimba
   *  durata. */
  async function redimensioneaza(p, start, sfarsit) {
    busy = p.id
    try {
      await apiJson(`/api/implementari/${p.id}`, {
        method: 'PUT',
        body: { data_start: start, data_sfarsit: sfarsit },
      })
      const zile = Math.max(0, diffDays(start, sfarsit)) + 1
      toast(`${shortDate(start)}–${shortDate(sfarsit)} · ${zile} ${zile === 1 ? 'zi' : 'zile'}`, 'success')
      selectata = start
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

  // ===== tragere directa =====
  // Trei manere, trei intelesuri, ca sa nu trebuiasca sa alegi dintr-un meniu:
  //   mijlocul barei -> muti LUCRAREA
  //   capetele barei -> ii schimbi PERIOADA (o lungesti sau o scurtezi)
  //   captura zilei  -> muti toata DEPLASAREA, pastrandu-i forma
  //
  // Mecanica gestului (mouse vs deget, praguri, blocarea derularii) sta in
  // `lib/tragere.js`; aici raman doar intelesurile.

  /** Ziua de sub un punct de pe ecran. Cat timp se trage, benzile si capturile
   *  sunt scoase din calea cursorului (`.grid.trag`), deci aici ajunge celula. */
  function ziDinPunct(x, y) {
    const el = document.elementFromPoint(x, y)
    return el?.closest?.('.zi')?.dataset?.zi || ''
  }

  function curataTragere() {
    trag = null
    previz = null
    dropZi = ''
    tocmaiTras = true
    // Click-ul vine dupa pointerup, in acelasi tick de evenimente.
    setTimeout(() => { tocmaiTras = false }, 0)
  }

  /** Mutarea unei lucrari. Ziua APUCATA e cea care ajunge sub cursor, nu
   *  inceputul lucrarii: daca prinzi o perioada de patru zile de a treia zi si o
   *  lasi pe joi, a treia zi cade pe joi. Altfel o simpla ajustare de o zi ar
   *  arunca inceputul cu trei zile inainte. */
  function apucaLucrare(e, b) {
    const p = b.p
    const apucata = ziDinBanda(e.clientX, e.currentTarget, b)
    const decalaj = diffDays(p.data_start, apucata)
    const durata = Math.max(0, diffDays(p.data_start, p.data_sfarsit || p.data_start))
    incepeTragere(e, {
      laInceput: () => { trag = { tip: 'lucrare', id: p.id } },
      laMiscare: (x, y) => {
        const zi = ziDinPunct(x, y)
        if (!zi) return
        dropZi = zi
        const start = addDays(zi, -decalaj)
        previz = new Map([[p.id, { data_start: start, data_sfarsit: addDays(start, durata) }]])
      },
      laFinal: () => {
        const v = previz?.get(p.id)
        curataTragere()
        if (v && v.data_start !== p.data_start) muta(p, v.data_start)
      },
      laAnulare: curataTragere,
    })
  }

  /** Redimensionarea: capatul apucat urmareste ziua de sub cursor, celalalt sta.
   *  Capetele nu se pot incaleca — perioada se opreste la o zi, nu se intoarce
   *  pe dos. */
  function apucaCapat(e, b, capat) {
    e.stopPropagation()               // altfel ar porni si mutarea
    const p = b.p
    incepeTragere(e, {
      laInceput: () => { trag = { tip: 'capat', id: p.id, capat } },
      laMiscare: (x, y) => {
        const zi = ziDinPunct(x, y)
        if (!zi) return
        dropZi = zi
        const s0 = p.data_start
        const f0 = p.data_sfarsit || p.data_start
        const s = capat === 'start' ? (zi > f0 ? f0 : zi) : s0
        const f = capat === 'start' ? f0 : (zi < s0 ? s0 : zi)
        previz = new Map([[p.id, { data_start: s, data_sfarsit: f }]])
      },
      laFinal: () => {
        const v = previz?.get(p.id)
        curataTragere()
        if (v && (v.data_start !== p.data_start || v.data_sfarsit !== (p.data_sfarsit || p.data_start))) {
          redimensioneaza(p, v.data_start, v.data_sfarsit)
        }
      },
      laAnulare: curataTragere,
    })
  }

  /** Deplasarea intreaga: toate lucrarile ei se decaleaza cu acelasi numar de
   *  zile, deci forma iesirii se pastreaza. */
  function apucaDeplasare(e, d) {
    e.stopPropagation()
    const lucrari = [...d.items.values()]
    let delta = 0
    incepeTragere(e, {
      laInceput: () => { trag = { tip: 'deplasare', cheie: d.cheie } },
      laMiscare: (x, y) => {
        const zi = ziDinPunct(x, y)
        if (!zi) return
        dropZi = zi
        delta = diffDays(d.start, zi)
        const m = new Map()
        for (const p of lucrari) {
          m.set(p.id, {
            data_start: addDays(p.data_start, delta),
            data_sfarsit: addDays(p.data_sfarsit || p.data_start, delta),
          })
        }
        previz = m
      },
      laFinal: () => {
        const n = delta
        curataTragere()
        if (n) mutaGrup(lucrari, d.start, addDays(d.start, n))
      },
      laAnulare: curataTragere,
    })
  }

  /** Un proiect fara perioada, tras pe o zi. Ramane si asezarea prin atingere
   *  (alegi proiectul, apoi ziua): tragerea e pentru mouse, atingerea e pentru
   *  cine prefera doua apasari sigure in locul unui gest lung pe telefon. */
  function apucaProiect(e, proj) {
    incepeTragere(e, {
      laInceput: () => { trag = { tip: 'proiect', id: proj.proiect_id }; asezare = null },
      laMiscare: (x, y) => { dropZi = ziDinPunct(x, y) },
      laFinal: () => {
        const zi = dropZi
        curataTragere()
        if (zi) planifica(proj, zi)
      },
      laAnulare: curataTragere,
    })
  }

  // ===== tastatura: aceleasi trei intelesuri, cu alta unealta =====
  //
  // `.cap` (muta toata deplasarea) si `.maner` (schimba capetele) erau `<span>`-uri
  // cu `onpointerdown`, fara `role` si fara `tabindex`, si stateau IN INTERIORUL
  // unui `<button>` (`.zi`, respectiv `.banda`). Buton in buton e markup invalid,
  // iar doua din cele trei gesturi principale ale ecranului n-aveau niciun
  // echivalent la tastatura — „Mută" din panou acoperea doar mutarea unei lucrari.
  //
  // Acum celula e `role="gridcell"`, iar captura si manerele sunt butoane reale.
  // Sagetile muta perioada selectata cu o zi, Shift+sageti ii schimba un capat:
  // acelasi model ca tragerea (mijloc = muta, capete = redimensioneaza).
  let perioadaSel = $state('')   // id-ul perioadei pe care sta focusul

  function perioadaDupaId(id) {
    return (data?.perioade || []).find(p => p.id === id) || null
  }

  function tastaPerioada(e) {
    if (!perioadaSel) return
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
    const p = perioadaDupaId(perioadaSel)
    if (!p || busy) return
    e.preventDefault()
    const n = e.key === 'ArrowLeft' ? -1 : 1
    const s = p.data_start
    const f = p.data_sfarsit || p.data_start
    if (e.shiftKey) {
      // Capatul din DREAPTA, ca la maner: perioada nu se poate intoarce pe dos.
      const nou = addDays(f, n)
      if (nou < s) return
      redimensioneaza(p, s, nou)
    } else {
      muta(p, addDays(s, n))
    }
  }

  // ===== asezare prin atingere =====
  // Drag-and-drop-ul HTML5 nu exista pe touch: nu se declanseaza niciun
  // `dragstart` la deget. Consecinta era ca „Proiecte fara perioada" NU se putea
  // planifica deloc de pe telefon — singura cale era sa deschizi proiectul si sa-i
  // adaugi o perioada din alta pagina.
  //
  // Aici nu punem un al doilea calendar peste calendar (un DatePicker ar fi asta).
  // Alegi proiectul, apoi atingi ziua — acelasi gest ca la drag, doar rupt in doua
  // atingeri, pe aceeasi harta. Ramane si dragul, neatins, pentru mouse.
  let asezare = $state(null)   // proiectul ales, in asteptarea unei zile

  function comutaAsezare(proj) {
    asezare = asezare?.proiect_id === proj.proiect_id ? null : proj
  }
  /** Ziua atinsa: daca ceva asteapta sa fie asezat, o consuma; altfel o selecteaza. */
  function atingeZi(iso) {
    if (asezare) {
      const proj = asezare
      asezare = null
      planifica(proj, iso)
      return
    }
    selectata = iso
    // Nu mai derulam la panou: agenda de sub grila raspunde deja la „ce e ziua
    // asta", iar randul ei se aprinde. Panoul ramane unde e, pentru actiuni.
    aratIesirea()
  }

  /** Pe o singura coloana, panoul zilei sta SUB grila. Daca a ramas complet in
   *  afara ecranului, atingerea unei zile ar schimba ceva ce nu se vede — deci il
   *  aducem in vizor. Numai atunci: cat timp se vede macar o parte din el, orice
   *  derulare automata ar fi o smucitura peste ce faceai. */
  function aratPanoul() {
    if (window.innerWidth > 900) return
    requestAnimationFrame(() => {
      const el = document.querySelector('.side .pan')
      if (!el) return
      const r = el.getBoundingClientRect()
      if (r.top < window.innerHeight - 40) return
      el.style.scrollMarginTop = 'calc(var(--header-height) + 8px)'
      el.scrollIntoView({ behavior: motion.reduced ? 'auto' : 'smooth', block: 'start' })
    })
  }

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

<svelte:window onkeydown={(e) => {
  if (e.key === 'Escape') { if (asezare) asezare = null; else perioadaSel = '' ; return }
  tastaPerioada(e)
}} />

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
        <button class="b-azi" onclick={laAzi}>Azi</button>
      </div>
      <div class="mods">
        <button class:on={mod === 'saptamani'} onclick={() => setMod('saptamani')}>2 săpt.</button>
        <button class:on={mod === 'luna'} onclick={() => setMod('luna')}>Lună</button>
        <!-- Exportul .ics a venit aici din Admin (sters): calendarul de abonat din
             telefon apartine paginii de calendar, nu unui sertar de intretinere. -->
        <button class="ics" onclick={() => window.open('/api/export/ics', '_blank')}
                title="Descarcă .ics — perioadele și scadențele de task. Abonează-te din calendarul telefonului.">
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
        <!-- Contorul PARCURGE lista: fiecare apasare duce la urmatoarea zi de
             clarificat, si arata unde esti. Inainte numara `de_decis.length` dar
             sarea mereu la `de_decis[0]` — apasai a doua oara si nu se intampla
             nimic, erai deja acolo. -->
        <button class="kpi warn" onclick={urmatorulDeClarificat}
                title="Mergi la următoarea zi de clarificat">
          <span class="k-n">{rezumat.deDecis > 1 ? `${decisCurent + 1}/${rezumat.deDecis}` : rezumat.deDecis}</span>
          <span class="k-l">de clarificat</span>
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
        <!-- `trag` scoate benzile din calea cursorului cat timp tragi: ele stau
             PESTE celule, deci altfel `ziDinPunct` ar nimeri banda, nu ziua. -->
        <!-- `--benzi` sta acum pe CELULA, nu pe grila: fiecare saptamana se
             dimensioneaza dupa cea mai plina zi a ei (vezi `benziPeRand`). -->
        <div class="grid" class:sapt={mod === 'saptamani'} class:trag={!!trag} role="grid" aria-label="Calendar">
          {#each grila as g, i (g.iso)}
            {@const items = aleZilei(g.iso)}
            {@const decizie = items.some(p => p.necesita_decizie)}
            {@const capturi = incepDeplasari(g.iso)}
            {@const ascunse = ascunseZi(g.iso)}
            <!-- Celulele se asaza EXPLICIT in grila. Fara asta, benzile (care au
                 poziție explicită) ar impinge celulele auto-plasate din loc.
                 `div role="gridcell"`, nu `<button>`: captura din antet e ea insasi
                 un buton, iar buton in buton e markup invalid. -->
            <div
              class="zi"
              data-zi={g.iso}
              role="gridcell"
              tabindex="0"
              aria-selected={g.iso === selectata}
              style="grid-row: {Math.floor(i / 7) + 1}; grid-column: {i % 7 + 1}; --benzi: {benziPeRand[Math.floor(i / 7)] ?? 1}"
              class:alta={g.alta}
              class:we={isWeekend(g.iso)}
              class:azi={g.iso === azi}
              class:sel={g.iso === selectata}
              class:drop={dropZi === g.iso}
              class:decizie
              class:split={impartita(g.iso)}
              class:tinta={!!asezare}
              onclick={() => atingeZi(g.iso)}
              onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); atingeZi(g.iso) } }}
            >
              <!-- Antetul zilei e o linie de inaltime FIXA: numarul + captura
                   deplasarii. Captura a stat initial pe rand propriu si impingea
                   barele in jos doar in zilele de plecare — asa, bara de patru
                   zile nu se mai lega intre 3 si 4 august, adica exact ce trebuia
                   sa repare benzile. Un rand in plus intr-o singura celula strica
                   alinierea intregii saptamani. -->
              <div class="zi-h">
                <!-- AZI E PE CIFRA, NU PE CHENAR.
                     Chenarul si conturul raman EXCLUSIV pentru selectie. Inainte
                     azi era chenar amber, selectia contur amber, „de clarificat"
                     chenar coral — iar cand ziua de azi era si zi de clarificat,
                     chenarul rosu il acoperea pe cel amber: codul spunea „bate pe
                     azi", dar rezultatul era ca AZI dispare exact in ziua in care
                     te uiti la ea. Pastila se vede de la distanta si nu se bate cu
                     nimic, fiindca e singurul lucru care sta pe cifra. -->
                <span class="n">{parseISO(g.iso).getDate()}</span>
                {#each capturi as d (d.cheie)}
                  <button class="cap" class:sediu={d.sediu}
                          class:se-trage={trag?.tip === 'deplasare' && trag.cheie === d.cheie}
                          onpointerdown={(e) => apucaDeplasare(e, d)}
                          onclick={(e) => e.stopPropagation()}
                          title={etichetaDeplasare(d)}
                          aria-label="Deplasare {d.client || 'la sediu'} — {textCaptura(d)}. Trage ca să muți toată ieșirea.">
                    {#if d.sediu}<Building2 size={9} />{:else}<MapPin size={9} />{/if}{textCaptura(d)}
                  </button>
                {/each}
                {#if items.length > 1 || ascunse}
                  <!-- UN SINGUR INTELES PE AMBELE ECRANE: cate lucrari are ziua.
                       Aceeasi pozitie si acelasi stil aratau „+N" (doar cele
                       ascunse) pe desktop si `items.length` (toate) pe telefon —
                       doua numere diferite pentru aceeasi zi, in functie de latimea
                       ecranului. Ca una e ascunsa se vede din faptul ca numarul e
                       mai mare decat benzile desenate.
                       `|| ascunse` prinde cazul in care ziua are O SINGURA lucrare
                       si TOCMAI ea e peste plafon (indicele de banda vine din
                       impachetarea globala, deci poate fi mare si intr-o zi goala):
                       fara el, lucrarea ar fi invizibila si fara niciun semn. -->
                  <span class="nr-lucrari" class:ascunse title="{items.length} {items.length === 1 ? 'lucrare' : 'lucrări'} în ziua asta{ascunse ? ` · ${ascunse} nu încap în benzi` : ''}">{items.length}</span>
                {/if}
              </div>
              {#if decizie}<span class="flag" title="Perioadă trecută, proiect nemutat"><AlertTriangle size={11} /></span>{/if}

              <!-- Barele NU mai stau in celula: o lucrare de mai multe zile e un
                   singur element, desenat peste coloane mai jos. Celula pastreaza
                   doar antetul, semnalele si inaltimea rezervata benzilor. -->
            </div>
          {/each}

          <!-- Benzile, peste celule: UN element per lucrare per saptamana. Vezi
               comentariul de la `bare` pentru ce anume repara. -->
          {#each bare as b (b.cheie)}
            <div
              class="banda"
              data-perioada={b.p.id}
              role="button"
              tabindex="0"
              class:inceput={b.inceput}
              class:sfarsit={b.sfarsit}
              class:lat={b.span > 1}
              class:sediu={b.p.locatie === 'sediu'}
              class:pregatire={b.p.faza === 'pregatire'}
              class:se-trage={trag?.id === b.p.id}
              class:tastata={perioadaSel === b.p.id}
              style="grid-row: {b.rand}; grid-column: {b.col} / span {b.span}; --c: {culoareLucrare(b.p)}; --i: {b.banda}"
              onpointerdown={(e) => apucaLucrare(e, b)}
              onclick={(e) => clickBanda(e, b)}
              onfocusin={() => perioadaSel = b.p.id}
              onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); atingeZi(b.zile[0]) } }}
              title={etichetaLucrareLunga(b.p)}
              aria-label="{etichetaLucrare(b.p)} — {shortDate(b.p.data_start)}{b.p.data_sfarsit && b.p.data_sfarsit !== b.p.data_start ? ' – ' + shortDate(b.p.data_sfarsit) : ''}. Săgeți: mută cu o zi. Shift+săgeți: schimbă sfârșitul."
            >
              <!-- Manerele stau pe capetele ADEVARATE, nu pe taietura de
                   saptamana: „…" inseamna „continua", deci acolo n-ai ce trage.
                   Zona de prindere e mai inalta decat banda (`::before`), ca sa
                   fie prinsa si cu degetul pe o banda de 12px.
                   Butoane reale, nu `<span>`: erau doua gesturi fara niciun
                   echivalent la tastatura, si stateau intr-un `<button>`. -->
              {#if b.inceput}
                <button class="maner st" onpointerdown={(e) => apucaCapat(e, b, 'start')}
                        onclick={(e) => e.stopPropagation()}
                        title="Trage ca să schimbi începutul"
                        aria-label="Schimbă începutul perioadei {etichetaLucrare(b.p)}"></button>
              {/if}
              <!-- Pe o banda de mai multe zile incape si detaliul din paranteze —
                   `etichetaBara` il taia doar pentru ca inainte fiecare bara avea
                   latimea unei singure celule. Acum se taie doar cand chiar nu
                   incape. -->
              <span class="banda-t">{b.inceput ? '' : '… '}{b.span > 1 ? etichetaLucrare(b.p) : etichetaBara(b.p)}</span>
              {#if b.sfarsit}
                <button class="maner dr" onpointerdown={(e) => apucaCapat(e, b, 'sfarsit')}
                        onclick={(e) => e.stopPropagation()}
                        title="Trage ca să schimbi sfârșitul"
                        aria-label="Schimbă sfârșitul perioadei {etichetaLucrare(b.p)}"></button>
              {/if}
            </div>
          {/each}

          <!-- Unde ar ajunge. Nu primeste evenimente si nu inlocuieste banda
               reala — vezi `fantome` pentru de ce cele doua nu pot fi acelasi
               element. -->
          {#each fantome as f (f.cheie)}
            <div class="banda fantoma"
                 class:inceput={f.inceput}
                 class:sfarsit={f.sfarsit}
                 style="grid-row: {f.rand}; grid-column: {f.col} / span {f.span}; --c: {culoareLucrare(f.p)}; --i: {f.banda}"
                 aria-hidden="true">
              <span class="banda-t">{f.inceput ? '' : '… '}{etichetaBara(f.p)}</span>
            </div>
          {/each}
        </div>

        <!-- Legenda de culori a plecat: culoarea urmareste proiectul, iar numele
             lucrarii scrie chiar in bara, deci o legenda ar repeta ce se vede.
             Ramane doar textura, care nu se poate citi altfel. -->
        {#if data.perioade?.length}
          <!-- DOUA AXE CARE SE COMBINA SE DESENEAZA CA O MATRICE, NU CA DOUA LISTE.
               Incercarea de dinainte scria „Unde" si „Fază" in fata a doua liste —
               dar asta EXPLICA coliziunea, n-o scotea: „pe teren" si „implementare"
               ramaneau exact aceeasi mostra, la un centimetru una de alta, fiindca
               ambele axe folosesc „plin" pentru valoarea lor pozitiva. Ochiul care
               scaneaza vedea tot acelasi patratel de doua ori, si nimic nu spunea ca
               cele doua axe SE COMBINA.
               Patru mostre = patru combinatii reale, cu ACELEASI retete ca benzile
               din grila, doar cu o culoare neutra in loc de cea a proiectului. Si
               raspunde si la „cum arata pregatire la sediu", la care cele doua liste
               nu raspundeau deloc. -->
          <div class="leg">
            <!-- Coltul gol e OBLIGATORIU, nu decor: fara el auto-plasarea grilei
                 pune „Implementare" fix in celula libera din stanga-sus si toata
                 matricea aluneca cu o coloana (masurat). Cele noua celule se
                 scriu in ordine, fara nicio regula de pozitionare. -->
            <span aria-hidden="true"></span>
            <span class="leg-ax">Pe teren</span>
            <span class="leg-ax">La sediu</span>
            <span class="leg-r">Implementare</span>
            <i class="sw neted"></i>
            <i class="sw hatch"></i>
            <span class="leg-r">Pregătire</span>
            <i class="sw palid"></i>
            <i class="sw palid hatch"></i>
          </div>
        {/if}

        <!-- IESIRILE FERESTREI, SCRISE. Doar pe telefon: acolo grila e o harta de
             dungi fara nume (vezi `agendaLunii`). Grila ramane harta — unde esti,
             cat de plin e — iar dedesubt scrie ce sunt dungile, in ordinea zilelor. -->
        {#if agendaLunii.length}
          <div class="agenda">
            <div class="ag-cap">
              <span>Ieșirile {mod === 'luna' ? 'lunii' : 'perioadei'}</span>
              <span class="ag-linie"></span>
              <span class="ag-n">{agendaLunii.length}</span>
            </div>
            {#each agendaLunii as d (d.cheie + '|' + d.start)}
              <button class="ag-rand" class:aprins={esteAprinsa(d)}
                      style="--c: {d.culoare}"
                      onclick={() => atingeZi(d.start)}>
                <span class="ag-sus">
                  <span class="ag-ico">{#if d.sediu}<Building2 size={11} />{:else}<MapPin size={11} />{/if}</span>
                  <span class="ag-titlu">{d.titlu}</span>
                  <span class="ag-cand">{d.cand}</span>
                </span>
                <span class="ag-lucrari">
                  {#each d.lucrari as p (p.id)}
                    <span class="ag-l" class:pregatire={p.faza === 'pregatire'}>{etichetaLucrare(p)}</span>
                  {/each}
                </span>
              </button>
            {/each}
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
                  <span class="it-punct" aria-hidden="true"></span>{p.nume}<ExternalLink size={12} />
                </button>
                <div class="it-m">
                  {#if p.eticheta}<span>{p.eticheta}</span>{/if}
                  <!-- Locatia si faza sunt amandoua despre PERIOADA, deci stau
                       lipite. Statusul e despre PROIECT si sta separat — altfel
                       „Pregătire" (faza) si „Pregătire" (status de proiect, il au
                       10 din 20) ar aparea ca doua chipuri identice cu intelesuri
                       diferite. -->
                  <span class="loc" title="Unde ești în ziua asta">{p.locatie === 'sediu' ? 'Sediu' : 'Site'}</span>
                  <span class="loc faza" class:pal={p.faza === 'pregatire'} title="Faza acestei perioade">{p.faza === 'pregatire' ? 'Pregătire' : 'Implementare'}</span>
                  <!-- Bifa e tot despre perioadă, deci stă lipită de loc și fază.
                       Rămâne etichetă, nu buton: pe deget un chip de 15px e exact
                       ținta pe care o ratezi. Anularea stă jos, între acțiuni. -->
                  {#if p.confirmata}
                    <span class="loc fac" title="Perioada s-a făcut. Statusul proiectului nu s-a schimbat."><Check size={11} /> Făcut</span>
                  {/if}
                  <span class="tk" class:warn={!p.taskuri_deschise}>{p.taskuri_deschise ? `${p.taskuri_deschise} ${p.taskuri_deschise === 1 ? 'task' : 'taskuri'}` : 'niciun task'}</span>
                </div>
                {#if p.necesita_decizie}
                  <div class="dec">
                    <span class="dec-q">A trecut. S-a făcut?</span>
                    <button class="b ok" disabled={busy === p.id} onclick={() => confirma(p, 1)}
                            title="Bifează perioada ca făcută. Proiectul NU se închide — asta se face din pagina proiectului.">
                      <Check size={12} /> Da
                    </button>
                    <button class="b" disabled={busy === p.id} onclick={() => muta(p, azi)}><Undo2 size={12} /> Mută pe azi</button>
                  </div>
                {/if}
                <div class="dec">
                  <!-- Calea de intoarcere pentru bifă. „Nu s-a făcut", nu „Scoate
                       bifa": e răspunsul opus la aceeași întrebare, și nu se poate
                       confunda cu „Scoate", care scoate perioada din calendar. -->
                  {#if p.confirmata}
                    <button class="b" disabled={busy === p.id} onclick={() => confirma(p, 0)}>
                      <X size={12} /> Nu s-a făcut
                    </button>
                  {/if}
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
          {:else}
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
        </div>

        {#if data.neplanificate?.length}
          <div class="pan">
            <!-- „fara perioada", nu „fara data": perioada e un interval (unde
                 esti), termenul e un punct (pana cand). Sertarul din Planificator
                 tine ALTCEVA — taskuri fara termen — si numele trebuie sa spuna
                 asta, nu sa le faca sa para acelasi lucru. -->
            <div class="pan-h">Proiecte fără perioadă <span class="cnt">{data.neplanificate.length}</span></div>
            <div class="pan-hint">
              {#if asezare}Atinge ziua în care începe.{:else}Alege un proiect, apoi ziua. (Sau trage-l pe o zi.){/if}
            </div>
            <div class="rail">
              {#each data.neplanificate as pr (pr.proiect_id)}
                <button class="np" class:ales={asezare?.proiect_id === pr.proiect_id}
                     class:se-trage={trag?.id === pr.proiect_id}
                     style="--c: {culoareProiect(pr.proiect_id)}"
                     onpointerdown={(e) => apucaProiect(e, pr)}
                     onclick={() => { if (!tocmaiTras) comutaAsezare(pr) }}
                     aria-pressed={asezare?.proiect_id === pr.proiect_id}
                     title={asezare?.proiect_id === pr.proiect_id ? 'Atinge o zi din calendar — sau atinge din nou ca să renunți' : 'Alege-l, apoi atinge ziua de început (sau trage-l direct pe o zi)'}>
                  <GripVertical size={12} />
                  <span class="np-punct" aria-hidden="true"></span>
                  <span class="np-t">{pr.nume}</span>
                  <span class="np-s" class:lucru={pr.status === 'pregatire'}>{PROJECT_STATUS_LABELS[pr.status] || pr.status}</span>
                </button>
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
  /* `b-azi`, nu `azi`: clasa `azi` e si pe celula zilei de azi (`.zi.azi`), iar un
     selector neprefixat o prindea si pe ea — celula primea `display: inline-flex`
     cu centrare si `padding: 0 10px`, deci numarul zilei de azi sta centrat in
     mijlocul celulei in loc de colt. Doua lucruri diferite, doua nume. */
  .ico, .b-azi, .mods button { border: 1px solid var(--border); background: var(--bg-surface); color: var(--text-secondary);
    border-radius: var(--radius-sm); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
  .ico { width: 28px; height: 28px; }
  .b-azi, .mods button { height: 28px; padding: 0 10px; font-size: var(--font-small); }
  .ico:hover, .b-azi:hover, .mods button:hover { border-color: var(--accent); color: var(--accent); }
  .mods { display: flex; gap: 4px; }
  .mods button.on { background: var(--accent-subtle); color: var(--accent); border-color: var(--accent-ring); }
  .mods button.ics { gap: 5px; margin-left: 6px; }

  .kpis { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); flex-wrap: wrap; }
  .kpi { display: flex; align-items: baseline; gap: 6px; padding: 7px 12px; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); }
  .kpi.warn { background: color-mix(in srgb, var(--danger) 14%, transparent); border-color: var(--danger); cursor: pointer; }
  .k-n { font-family: var(--font-mono); font-size: var(--font-body); font-weight: var(--fw-semibold); color: var(--text); font-variant-numeric: tabular-nums; }
  .kpi.warn .k-n { color: var(--danger); }
  .k-l { font-size: var(--font-small); color: var(--text-dim); }
  .kpi.warn .k-l { color: var(--danger); }

  .wrap { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: var(--space-md); align-items: start; }

  .cal { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-sm); }
  .wd { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; margin-bottom: 4px; }
  .wd span { font-size: var(--font-label); color: var(--text-faint); text-align: center; text-transform: uppercase; letter-spacing: var(--tracking-label); }
  /* `minmax(0, 1fr)`, nu `1fr`: `1fr` inseamna `minmax(auto, 1fr)`, deci o banda
     care se intinde peste coloane si are `nowrap` isi impune latimea minima si
     largeste coloanele pe care le acopera. Zilele nu mai erau egale si nu se mai
     aliniau cu antetul de zile al saptamanii. */
  .grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; }

  .zi { position: relative; min-height: calc(38px + var(--benzi, 1) * 20px); padding: 5px 5px 4px; border-radius: var(--radius-md);
        border: 1px solid var(--border); background: var(--bg-elevated); text-align: left; cursor: pointer;
        display: flex; flex-direction: column; gap: 3px; overflow: hidden;
        transition: border-color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease); }
  /* In „2 sapt." sunt doar doua randuri de afisat, deci celulele pot respira. */
  .grid.sapt .zi { min-height: calc(62px + var(--benzi, 1) * 20px); }
  .zi:hover { border-color: var(--border-strong); }
  .zi:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .zi.alta { opacity: 0.42; }
  .zi.we { background: color-mix(in srgb, var(--purple) 5%, var(--bg-elevated)); }
  /* UN CANAL PER INTREBARE.
     Erau sase stari pe doua canale, patru dintre ele amber: azi (chenar), selectata
     (fundal + contur), de clarificat (chenar), tinta de asezare (chenar punctat),
     drop (chenar punctat), impartita (bara jos). Trei stateau pe chenar, doua pe
     contur. Iar cand ziua de azi era si zi de clarificat, chenarul rosu il acoperea
     pe cel amber — codul spunea „bate pe azi", dar rezultatul era ca AZI dispare
     exact in ziua in care te uiti la ea.
       chenar / contur = SELECTIE (si starile ei momentane: drop, tinta)
       cifra           = azi (pastila amber plina, vezi `.zi.azi .n`)
       coltul          = de clarificat (triunghiul `.flag`, care era deja acolo)
       bara de jos     = zi impartita intre locuri
     Atentie la o capcana: in tema asta --warning === --accent (#ffb454), deci
     avertizarile NU pot folosi warning — ar arata exact ca „azi". */
  .zi.sel { background: var(--accent-subtle); outline: 2px solid var(--accent); outline-offset: -2px; }
  .zi.drop { border-style: dashed; border-color: var(--accent); background: var(--accent-subtle); }
  /* Cat timp un proiect asteapta sa fie asezat, TOATE zilele arata ca destinatii
     posibile — altfel „alege un proiect, apoi ziua" cere sa stii ca a doua
     atingere face altceva decat de obicei. */
  .zi.tinta { border-style: dashed; border-color: color-mix(in srgb, var(--accent) 55%, transparent); }
  .zi.tinta:hover, .zi.tinta:active { border-color: var(--accent); background: var(--accent-subtle); }
  .zi.split { box-shadow: inset 0 -3px 0 var(--purple); }

  .n { display: inline-flex; align-items: center; justify-content: center;
    min-width: 15px; height: 15px; padding: 0 3px; border-radius: var(--radius-full);
    font-family: var(--font-mono); font-size: var(--font-small); color: var(--text-dim);
    font-variant-numeric: tabular-nums; }
  /* Pastila plina: se vede de la distanta si nu se bate cu niciun chenar. */
  .zi.azi .n { background: var(--accent); color: var(--on-color); font-weight: var(--fw-semibold); }
  .flag { position: absolute; top: 4px; right: 4px; color: var(--danger); display: inline-flex; }

  /* O LUCRARE = O BANDA, oricat de multe zile ar tine. Se intinde peste coloane,
     acopera si spatiile dintre ele, deci numele se scrie o data si are toata
     latimea lucrarii la dispozitie.
     `--i` e banda (randul) lucrarii. Decalajul de sus trebuie sa fie EXACT cel al
     zonei de bare din celula, altfel benzile plutesc pe langa celule:
       bordura 1 + padding 5 + antet 15 + gap 3 = 24px
     iar pasul unei benzi = inaltimea barei 17 + gap 3 = 20px. Cele doua numere
     sunt aceleasi cu cele din `min-height` al celulei — se schimba impreuna. */
  .grid { --h-antet: 24px; --h-banda: 20px; }
  .banda { position: relative; z-index: 1; align-self: start;
           margin-top: calc(var(--h-antet) + var(--i) * var(--h-banda));
           min-height: 17px; padding: 1px 6px; border: none; text-align: left;
           cursor: grab; background: color-mix(in srgb, var(--c) 26%, transparent); }
  .banda:active { cursor: grabbing; }
  /* Capetele rotunjite spun unde INCEPE si unde se TERMINA lucrarea. La granita de
     saptamana capatul rămâne drept si iese peste marginea celulei: asa se citeste
     „continua", nu „s-a incheiat". */
  /* Inceputul se marcheaza prin FORMA, nu prin culoare: banda e deja plina cu
     `var(--c)`, deci dunga era aceeasi culoare peste ea insasi, doar mai tare.
     Raza de pe colturile din stanga spune acelasi lucru si nu adauga un al doilea
     cod de culoare. Cei 3px se intorc in padding. */
  .banda.inceput { margin-left: 6px; padding-left: 8px;
                   border-top-left-radius: var(--radius-sm); border-bottom-left-radius: var(--radius-sm); }
  .banda.sfarsit { margin-right: 6px;
                   border-top-right-radius: var(--radius-sm); border-bottom-right-radius: var(--radius-sm); }
  .banda:not(.inceput) { margin-left: -3px; }
  .banda:not(.sfarsit) { margin-right: -3px; }
  /* Cat timp se trage, nimic din ce pluteste peste celule nu mai raspunde la
     pointer: `ziDinPunct` foloseste `elementFromPoint`, deci ar nimeri banda in
     locul zilei. Fantoma e oricum inertă, dar o trecem si pe ea prin regula ca
     sa nu depinda de ordinea in care sunt scrise selectoarele. */
  .grid.trag .banda, .grid.trag .cap { pointer-events: none; }

  /* Ce apuci ramane pe loc si se stinge; ce se misca e fantoma. Doua obiecte, ca
     sa se vada si de UNDE, si PANA UNDE — o singura bara care sare ar sterge
     prima jumatate a informatiei. */
  .banda.se-trage { opacity: 0.32; }
  .fantoma { pointer-events: none; z-index: 2; outline: 1px solid var(--accent);
             outline-offset: -1px; background: color-mix(in srgb, var(--c) 40%, transparent); }

  /* MANERELE DE PERIOADA.
     Late de 9px, dar zona de prindere se intinde peste toata inaltimea benzii si
     inca 5px sus/jos (`::before`) — banda are 17px pe desktop si 12px pe telefon,
     adica sub orice tinta rezonabila daca ne-am opri la conturul ei. */
  .maner { position: absolute; top: 0; bottom: 0; width: 9px; cursor: ew-resize;
           opacity: 0; transition: opacity var(--dur-fast) var(--ease); }
  .maner.st { left: 0; }
  .maner.dr { right: 0; }
  .maner::before { content: ''; position: absolute; inset: -5px -2px; }
  .maner::after { content: ''; position: absolute; top: 50%; left: 50%; width: 2px; height: 9px;
                  transform: translate(-50%, -50%); border-radius: 1px; background: var(--on-color); }
  .banda:hover .maner, .banda.se-trage .maner { opacity: 0.75; }
  .maner:hover { opacity: 1; }
  /* Fara hover nu exista „apropii cursorul si apare manerul". Pe deget ele
     trebuie sa se vada de la inceput, altfel nimic nu spune ca perioada se poate
     lungi tragand de capat. */
  @media (hover: none) {
    .maner { opacity: 0.6; }
  }
  /* Zi la sediu = hasurat, zi pe teren = plin. Diferenta conteaza: una e zi de
     drum, cealalta nu. Aceeasi culoare de client, alta textura. */
  .banda.sediu { background: repeating-linear-gradient(135deg,
      color-mix(in srgb, var(--c) 30%, transparent) 0 4px,
      transparent 4px 8px); }
  /* Faza e a DOUA axa, independenta de locatie: pregatirea e mai palida si
     conturata, implementarea e plina. Se combina cu hasura de sediu. */
  .banda.pregatire { background: color-mix(in srgb, var(--c) 9%, transparent);
                     box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--c) 42%, transparent); }
  .banda.pregatire.sediu { background: repeating-linear-gradient(135deg,
      color-mix(in srgb, var(--c) 16%, transparent) 0 4px, transparent 4px 8px); }
  .banda.pregatire .banda-t { color: var(--text-secondary); }
  .banda-t { display: block; font-size: var(--font-small); line-height: var(--lh-snug); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* Numele nu intra sub maner: linia lui de prindere ar cadea peste prima si
     ultima litera, si n-ai sti daca textul e taiat sau desenat gresit. */
  .banda.inceput .banda-t { padding-left: 6px; }
  .banda.sfarsit .banda-t { padding-right: 6px; }

  /* Antet de inaltime fixa — vezi comentariul din template: orice variatie aici
     desincronizeaza benzile pe orizontala. nowrap + overflow hidden garanteaza
     ca ramane pe un rand oricat de lung ar fi numele clientului. */
  .zi-h { display: flex; align-items: center; gap: 5px; min-height: 15px; max-width: 100%;
          white-space: nowrap; overflow: hidden; padding-right: 14px; }
  .cap { display: inline-flex; align-items: center; gap: 3px; min-width: 0;
         padding: 0 5px 0 3px; border-radius: var(--radius-full);
         font-size: var(--font-small); line-height: var(--lh-normal); color: var(--text-secondary);
         background: var(--bg-hover); border: 1px solid var(--border); cursor: grab;
         overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .cap:active { cursor: grabbing; }
  .cap:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
  .cap.se-trage { opacity: 0.32; }
  .cap.sediu { color: var(--text-dim); }

  /* Cate lucrari are ziua — acelasi inteles pe ambele ecrane (vezi markup). */
  .nr-lucrari { margin-left: auto; font-family: var(--font-mono); font-size: var(--font-small);
    color: var(--text-faint); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .nr-lucrari.ascunse { color: var(--text-dim); font-weight: var(--fw-semibold); }

  /* MATRICE 2×2, nu doua liste. Coloanele = unde, randurile = faza; fiecare mostra
     e o combinatie reala, cu aceeasi reteta ca banda din grila. */
  /* `justify-content: start`: fara el coloana `auto` inghite tot spatiul ramas
     (masurat: 700px) si cele doua coloane de mostre ajung la marginea din dreapta,
     departe de etichetele lor de rand. Matricea trebuie sa fie compacta ca sa se
     citeasca DREPT matrice. */
  .leg { display: grid; grid-template-columns: auto 76px 76px; gap: 7px 14px;
    justify-content: start; align-items: center;
    padding: 10px 4px 2px; margin-top: 6px; border-top: 1px solid var(--border); }
  .leg-ax { font-size: var(--font-label); text-transform: uppercase;
    letter-spacing: var(--tracking-label); color: var(--text-faint); }
  .leg-r { font-size: var(--font-small); color: var(--text-secondary); }
  /* Mostrele au forma benzilor (dreptunghi lat, nu patrat de 10px): la 10×10 o
     hasura de 4px arata ca doua dungi, nu ca o textura. */
  .sw { display: block; width: 66px; height: 13px; border-radius: 3px; flex-shrink: 0; --c: var(--text); }
  .sw.neted { background: color-mix(in srgb, var(--c) 26%, transparent); }
  .sw.hatch { background: repeating-linear-gradient(135deg,
      color-mix(in srgb, var(--c) 30%, transparent) 0 4px, transparent 4px 8px); }
  .sw.palid { background: color-mix(in srgb, var(--c) 9%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--c) 42%, transparent); }
  /* Pregatire LA SEDIU: cele doua axe se combina, deci si retetele. E fix
     combinatia la care legenda veche nu raspundea deloc. */
  .sw.palid.hatch { background: repeating-linear-gradient(135deg,
      color-mix(in srgb, var(--c) 16%, transparent) 0 4px, transparent 4px 8px); }

  /* ===== agenda ferestrei (telefon) ===== */
  .agenda { display: none; flex-direction: column; gap: 6px; margin-top: 6px; }
  .ag-cap { display: flex; align-items: center; gap: var(--space-sm);
    padding: 12px 2px 6px; border-top: 1px solid var(--border);
    font-family: var(--font-mono); font-size: var(--font-label);
    letter-spacing: var(--tracking-label); text-transform: uppercase; color: var(--text-faint); }
  .ag-linie { flex: 1; height: 1px; background: var(--border-subtle); }
  .ag-n { font-variant-numeric: tabular-nums; }
  /* Identitatea trece de pe muchie pe FUNDAL: randul intreg apartine unei singure
     lucrari, iar iconita lui de locatie e gri (`--text-dim`), deci nu era un al
     doilea semn colorat pe care sa ne bazam. Fill tentat, ca la vecinii din
     Planificator. */
  .ag-rand { display: flex; flex-direction: column; gap: 4px; width: 100%;
    padding: 8px 9px 8px 11px; text-align: left; border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--c) 8%, var(--bg-panel)); border: 1px solid var(--border);
    cursor: pointer;
    transition: var(--transition-colors); }
  /* Atingi o zi -> se aprinde iesirea ei, nu se schimba un panou. */
  .ag-rand.aprins { background: var(--accent-subtle); border-color: var(--accent-ring); }
  .ag-sus { display: flex; align-items: center; gap: 6px; min-height: 20px; }
  .ag-ico { display: inline-flex; color: var(--text-dim); flex: none; }
  .ag-titlu { flex: 1; min-width: 0; font-size: var(--font-small); font-weight: var(--fw-semibold);
    color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ag-cand { flex: none; font-family: var(--font-mono); font-size: var(--font-small); color: var(--text-dim); }
  .ag-lucrari { display: flex; flex-wrap: wrap; gap: 4px 8px; }
  .ag-l { font-size: var(--font-small); color: var(--text-secondary); }
  .ag-l.pregatire { color: var(--text-faint); }

  .side { display: flex; flex-direction: column; gap: var(--space-md); }
  .pan { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-md); }
  .pan-zi { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); }
  .pan-sub { display: flex; align-items: center; gap: 5px; font-size: var(--font-small); color: var(--text-dim); margin: 3px 0 10px; }
  .pan-h { display: flex; align-items: center; gap: 8px; font-size: var(--font-label); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-faint); }
  .cnt { padding: 0 7px; border-radius: var(--radius-full); background: var(--bg-hover); color: var(--text-secondary); letter-spacing: 0; }
  .pan-hint { font-size: var(--font-small); color: var(--text-faint); margin: 4px 0 8px; }
  .gol { font-size: var(--font-small); color: var(--text-dim); }

  .urm { display: flex; flex-direction: column; gap: 3px; width: 100%; text-align: left; margin-top: 10px;
         padding: 9px 11px; border-radius: var(--radius-md); border: 1px solid var(--border);
         background: var(--bg-elevated); cursor: pointer; }
  .urm:hover { border-color: var(--accent); }
  .urm-h { font-size: var(--font-label); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-faint); }
  .urm-d { display: flex; align-items: center; gap: 5px; font-size: var(--font-small); color: var(--text); }
  .urm-l { font-size: var(--font-small); color: var(--text-dim); line-height: var(--lh-normal); }

  /* Lista zilei e MIXTA (mai multe lucrari, culori diferite) si randul n-are nici
     fill, nici iconita colorata — deci identitatea primeste un punct inaintea
     numelui, nu o dunga pe muchie. */
  .it { padding: 2px 0; margin-bottom: 12px; }
  .it-punct { width: 6px; height: 6px; border-radius: 50%; background: var(--c); flex: none; }
  .it-t { display: flex; align-items: center; gap: 5px; font-size: var(--font-small); color: var(--text); text-align: left; cursor: pointer; }
  .it-t:hover { color: var(--accent); }
  .it-m { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 3px; font-size: var(--font-small); color: var(--text-dim); }
  .it-m .loc { padding: 0 6px; border-radius: var(--radius-full); background: var(--bg-hover); }
  /* Faza preia limbajul barelor: palid = pregatire, plin = implementare. */
  .it-m .faza { background: color-mix(in srgb, var(--c) 26%, transparent); color: var(--text); }
  .it-m .faza.pal { background: none; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--c) 45%, transparent); color: var(--text-secondary); }
  /* Verdele spune „s-a facut", nu „urgent" — e singurul loc din rand unde
     culoarea nu tine de identitatea proiectului, si de aia e conturat, nu plin. */
  .it-m .fac { display: inline-flex; align-items: center; gap: 3px; background: none;
               color: var(--success); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--success) 40%, transparent); }
  .it-m .tk.warn { color: var(--warning); }

  .dec { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-top: 7px; }
  .dec-q { font-size: var(--font-small); color: var(--danger); width: 100%; }
  .mut { display: flex; align-items: flex-end; gap: 6px; width: 100%; margin-top: 4px; }
  .b { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-small); padding: 3px 8px; border-radius: var(--radius-sm);
       border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-secondary); cursor: pointer; }
  .b:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .b:disabled { opacity: 0.5; cursor: default; }
  .b.ok { color: var(--success); border-color: color-mix(in srgb, var(--success) 45%, transparent); }
  .b.del:hover:not(:disabled) { border-color: var(--danger); color: var(--danger); }

  .rail { display: flex; flex-direction: column; gap: 4px; max-height: 260px; overflow-y: auto; }
  /* Sertarul e o lista MIXTA de proiecte, iar chipul n-are fill si n-are iconita
     colorata (grip-ul e gri) — deci identitatea primeste un punct, ca in lista
     zilei de deasupra. */
  .np { display: flex; align-items: center; gap: 5px; padding: 5px 7px; border-radius: var(--radius-sm);
        width: 100%; text-align: left; border: none;
        background: var(--bg-elevated); cursor: grab; }
  .np-punct { width: 6px; height: 6px; border-radius: 50%; background: var(--c); flex: none; }
  .np:active { cursor: grabbing; }
  /* Ales, in asteptarea unei zile. Nu e „selectat" in sensul unei liste — e un
     obiect ridicat, care asteapta sa fie pus jos. De aceea si calendarul se
     schimba in acelasi timp (vezi `.zi.tinta`): daca doar chipul s-ar aprinde,
     n-ai sti ca urmatoarea atingere pe o zi INSEAMNA ceva. */
  .np.ales { background: var(--accent-subtle); box-shadow: inset 0 0 0 1px var(--accent); }
  .np.ales .np-t { color: var(--text); font-weight: var(--fw-semibold); }
  .np-t { flex: 1; font-size: var(--font-small); color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .np-s { font-size: var(--font-small); color: var(--text-faint); }
  .np-s.lucru { color: var(--accent); }

  /* ===== O SINGURA COLOANA: ORDINEA SE SCHIMBA =====
     Pe desktop grila si panoul stau unul langa altul, deci ordinea nu conteaza:
     atingi o zi si vezi imediat, in dreapta, ce e in ea. Pe o coloana nu mai e
     asa. Panoul statea DEASUPRA grilei — adica atingeai o zi si rezultatul
     aparea in afara ecranului, deasupra degetului. Trebuia sa derulezi in sus ca
     sa vezi ce tocmai ai cerut.
     Acum: harta, apoi ziua atinsa imediat sub ea — ca in orice calendar de
     telefon. Contoarele coboara la urma: sunt un rezumat al ferestrei pe care
     tocmai ai citit-o, nu o intrebare cu care incepi. Semnalul care chiar cere
     actiune („de clarificat") e oricum DESENAT pe zi, cu chenar rosu. */
  @media (max-width: 900px) {
    .wrap { grid-template-columns: minmax(0, 1fr); }
    .side { order: 0; }
    .page { display: flex; flex-direction: column; }
    .bar { order: 0; }
    .wrap { order: 1; }
    .kpis { order: 2; margin: var(--space-md) 0 0; }
  }
  @media (max-width: 620px) {
    .page { padding: var(--space-md); }
    /* Benzile sunt mai subtiri pe telefon, deci si pasul lor — cele doua numere
       trebuie sa rămână in acord cu `--h-banda`, altfel benzile ies din celule. */
    .grid { --h-banda: 15px; }
    .zi { min-height: calc(30px + var(--benzi, 1) * 15px); }
    .grid.sapt .zi { min-height: calc(46px + var(--benzi, 1) * 15px); }
    .banda { min-height: 12px; }
    .banda-t { display: none; }
    /* Captura se taia oricum la o felie ilizibila intr-o celula de ~48px. Ce spune
       ea — cine si cat — scrie acum in AGENDA de sub grila, unde incape. */
    .cap { display: none; }
    /* Grila ramane harta (unde esti, cat de plin e); numele lucrarilor stau jos. */
    .agenda { display: flex; }
    .ag-rand { min-height: var(--tap-min); }

    /* BANDA E TOT DECOR LA ATINGERE, DAR SE POATE APUCA.
       Pana la 2026-08-07 banda era `pointer-events: none` pe telefon, ca o dunga
       de 12px sa nu fure atingerile destinate zilei de ~50×60. Intentia aia
       ramane — dar acum e obtinuta din COMPORTAMENT, nu din a face banda
       inexistenta: o atingere scurta pe banda cheama exact `atingeZi` cu ziua de
       sub deget, adica fix ce ar fi facut celula. Ce se castiga: apasarea lunga
       apuca lucrarea si o poti muta, ceea ce inainte nu se putea deloc de pe
       telefon (`dragstart` nu exista la deget).
       Manerele de capat raman doar pe benzile de mai multe zile: pe una de o
       singura zi, doua manere de 9px ar manca o celula de 44px si n-ai mai avea
       de unde s-o apuci ca s-o muti. */
    .banda:not(.lat) .maner { display: none; }

    /* Navigarea si comutatoarele de mod: erau de 28px inaltime. */
    .ico { width: var(--tap-min); height: var(--tap-min); }
    .b-azi, .mods button { height: var(--tap-min); padding: 0 14px; font-size: var(--font-small); }
    .nav { gap: var(--space-xs); flex: 1; }
    .titlu { flex: 1; min-width: 0; font-size: var(--font-small); }
    .bar { gap: var(--space-xs); }
    .mods { width: 100%; }
    .mods button { flex: 1; }
    .mods button.ics { flex: 0 0 auto; margin-left: 0; }

    /* Actiunile din panoul zilei — „Da", „Mută pe azi", „Mută", „Scoate". Erau
       pastile de 22px, adica exact tipul de buton pe care il ratezi si apesi
       „Scoate" in loc de „Mută". */
    .b { min-height: var(--tap-min); padding: 0 12px; font-size: var(--font-small); }
    .dec { gap: var(--space-xs); }
    .mut { flex-wrap: wrap; }
    .mut :global(.dp) { flex: 1 1 160px; }

    /* Randurile din „Proiecte fără perioadă" sunt acum butoane (alegi, apoi
       atingi ziua), deci trebuie sa aiba caseta unui buton. */
    .np { min-height: var(--tap-min); padding: 6px 8px; }
    .np-t { font-size: var(--font-small); }
    .rail { max-height: none; gap: 6px; }

    .kpi { min-height: var(--tap-min); }
    .it-t { min-height: var(--tap-min); }
  }
</style>
