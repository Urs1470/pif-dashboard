<script>
  // Calendar — „unde sunt".
  //
  // Ion e o singura persoana, iar planificarea lui reala sunt PERIOADELE, fiecare
  // cu faza ei: pregatire sau implementare. Deadline-urile au plecat in v30 —
  // „noi nu intram in deadline-uri din partea clientului niciodata". Intrebarea la
  // care raspunde ecranul asta e „unde sunt marti si ce fac", iar deciziile stau
  // TOT aici, pe ziua respectiva — nu intr-o lista separata de reprosuri.
  //
  // O bara per LUCRARE, cu numele ei. Culoarea NU mai urmareste proiectul: din 12
  // perioade ale anului 11 sunt la acelasi client, deci identitatea cromatica nu
  // selecta nimic (vezi `culoareLucrare`, care intoarce accentul pentru toate).
  // Deplasarea (zile consecutive la acelasi loc si client) e un chenar, cu
  // eticheta pe primul lui rand si lucrarile inauntru.
  import { onMount, onDestroy } from 'svelte'
  import { fade } from 'svelte/transition'
  import { ChevronLeft, ChevronRight, MapPin, Building2, Check, X, Undo2, ExternalLink, TriangleAlert, GripVertical, CalendarDays, CalendarX2, Download } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { navigate, router } from '../lib/router.svelte.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import { ui } from '../stores/ui.svelte.js'
  import { motion, motionDuration, alunecare, sosire, DUR_BASE, EASE } from '../lib/motion.svelte.js'
  import { PROJECT_STATUS_LABELS } from '../lib/formatters.js'
  import { incepeTragere } from '../lib/tragere.js'
  import { ecran } from '../lib/ecran.svelte.js'
  import { cheieDeplasare, grupeazaDeplasari, seAting, rezolvaCiocniri } from '../lib/deplasari.js'
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
  // `mod` a plecat (V9): comutatorul „Lună / 2 săpt." a fost sters in turul 6,
  // dar starea si toate ramurile lui au ramas — masinarie moarta, pe care o
  // citeai ca specificatie si o copiai. Calendarul e LUNA, peste tot.
  let anchor = $state(monthStart(todayISO()))
  // PANOUL FACE LOC, NU ACOPERA — deci la incarcare NU e selectata nicio zi.
  // Grila are toata latimea (127 -> 176px pe zi, adica textul din bare se
  // citeste), iar „azi" ramane marcat in grila. Panoul intra cu coloana lui abia
  // cand ceri o zi. Inainte pornea cu ziua de azi selectata, deci pagina se
  // deschidea mereu ingustata, pentru un panou pe care de cele mai multe ori nu
  // il ceruse nimeni.
  let selectata = $state('')
  // Sursa „Proiecte fara perioada", urcata din panou in capul paginii.
  let deschideNeplanificate = $state(false)
  // Coloana panoului exista doar cand are ce arata. Cand nu, grila e pe toata
  // latimea — ceea ce inseamna 176px pe zi in loc de 127, adica exact pragul de
  // la care eticheta unei lucrari se poate citi in bara ei.
  const panouDeschis = $derived(!!selectata || deschideNeplanificate)
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
  // Incotro ai mers ultima data: -1 inapoi, +1 inainte, 0 „n-a fost o navigare"
  // (prima randare, sau un salt care cade pe luna in care esti deja).
  let sensLuna = $state(0)

  const azi = todayISO()

  function scurt(client) {
    const c = (client || '').trim()
    if (!c) return '—'
    // „Continental Automotive Products SRL" -> „Continental"
    return c.split(/\s+/)[0].replace(/[.,]$/, '')
  }

  async function load(silent = false) {
    // SCHELETUL DOAR LA PRIMA INCARCARE, NU LA FIECARE LUNA.
    //
    // `loading = true` la orice navigare stingea grila si punea in locul ei o
    // forma care nu seamana cu niciun calendar — desi `grila` se recalculeaza
    // SINCRON din `anchor`, deci zilele lunii noi erau deja gata de desenat si
    // doar benzile intarziau cat tine cererea. Plateai un ecran gol pentru
    // altceva decat ce asteptai. Si taia din start alunecarea din 13c: elementul
    // pe care ea o joaca era distrus si refacut inainte s-o apuce cineva sa vada.
    //
    // Erorile raman raportate — `error` se pune in `catch` la fel ca inainte.
    if (!silent) { loading = data === null; error = null }
    try {
      const start = weekStart(monthStart(anchor))
      data = await apiJson(`/api/calendar?start=${start}&zile=49`)
    } catch (e) {
      if (!silent) error = e.message
    } finally {
      if (!silent) loading = false
    }
  }

  const grila = $derived(buildGrid(anchor, 'luna', 2))

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
  // Cheia si gruparea in rulaje traiesc in `lib/deplasari.js`: aceeasi regula o
  // citeste si notificarea de plecare pe teren (turul 15), iar scrisa in doua
  // locuri s-ar rupe tacut — calendarul ar arata o iesire, telefonul ar suna de
  // doua ori.
  const cheieGrup = cheieDeplasare

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

  /* `impartita()` a plecat: singurul ei consumator era `class:split`, iar regula
     `.zi.split` (muchia de 3px) a fost scoasa la R4 — deci clasa se punea si nu
     desena nimic. Ca o zi e impartita intre doua locuri se citeste oricum din
     cele doua chenare de iesire de pe rand. */

  // O DEPLASARE = rulajul contiguu de zile cu aceeasi cheie de grup. O eticheta
  // cu identitatea IESIRII, nu cu numele unei lucrari: pe 28 era doar „Migrare
  // CU240S", dar blocul tine pana pe 30, asa ca eticheta aia facea sa para ca
  // migrarea dureaza trei zile.
  const deplasari = $derived(grupeazaDeplasari(data?.perioade || []))

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
  /* Randul de KPI („zile pe teren", „deplasari", „zile la sediu") a plecat in
     turele 7-8: numere care nu decideau nicio actiune. Calculul lor a ramas si
     s-a rulat degeaba la fiecare randare — si, mai rau, tinea randul la un pas
     de a se intoarce. Ce ramane e singurul numar care duce undeva. */
  const rezumat = $derived({ deDecis: (data?.de_decis || []).length })

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
  // Plafonul numara RANDURI, nu lucrari: de cand eticheta iesirii are randul ei
  // (vezi `impachetare`), o deplasare cu doua lucrari ocupa trei. Era 3 cat timp
  // un rand insemna o lucrare.
  const MAX_BENZI = 5

  /** Un identificator stabil pentru o deplasare: `cheie` singura se repeta (acelasi
   *  loc si acelasi client, alta saptamana), iar ziua de plecare o face unica. */
  function idDeplasare(d) { return `${d.cheie}|${d.start}` }

  /** IMPACHETAREA: o deplasare ocupa un BLOC de randuri consecutive — primul e al
   *  ETICHETEI ei, restul sunt lucrarile.
   *
   *  Inainte se impachetau lucrarile una cate una, iar eticheta („Sediu EGB · 3
   *  zile") era un chip lipit de cifra zilei, in antet. Chenarul iesirii exista ca
   *  obiect, dar numele lui statea in afara lui — deci „asta e o iesire de 3 zile,
   *  cu lucrarile astea" se citea din doua locuri, nu dintr-o privire.
   *
   *  Ca eticheta sa incapa INAUNTRU, ii trebuie un rand pe care nimic altceva
   *  nu-l poate ocupa: de-aia blocul se aloca intreg, nu rand cu rand. Altfel
   *  lucrarea altei deplasari s-ar aseza fix pe randul etichetei, iar chenarul ar
   *  ingloba o bara care nu-i apartine.
   *
   *  Pe telefon nu se rezerva nimic: `.chenar-et` e ascunsa acolo (o celula de
   *  ~48px n-are loc de text), deci un rand gol ar fi 15px de nimic in fiecare
   *  saptamana cu o iesire. */
  const impachetare = $derived.by(() => {
    const lucrari = new Map()
    const etichete = new Map()
    const cuEticheta = !ecran.telefon
    const ultima = []                       // ultima[rand] = ultima zi ocupata
    const ds = [...deplasari].sort((a, b) =>
      (a.start || '').localeCompare(b.start || '') || idDeplasare(a).localeCompare(idDeplasare(b)))
    for (const d of ds) {
      const items = [...d.items.values()].sort((a, b) =>
        (a.data_start || '').localeCompare(b.data_start || '') ||
        String(a.id).localeCompare(String(b.id)))
      // Cate randuri ii trebuie: lucrarile ei, impachetate intre ele.
      const intern = []
      const local = new Map()
      for (const p of items) {
        const a = p.data_start
        const b = p.data_sfarsit || p.data_start
        let k = 0
        while (intern[k] !== undefined && intern[k] >= a) k++
        intern[k] = b
        local.set(p.id, k)
      }
      const cap = cuEticheta ? 1 : 0
      const inalt = cap + Math.max(1, intern.length)
      // Primul BLOC de `inalt` randuri libere pe intervalul deplasarii.
      let baza = 0
      for (;;) {
        let liber = true
        for (let k = 0; k < inalt; k++) {
          if (ultima[baza + k] !== undefined && ultima[baza + k] >= d.start) { liber = false; break }
        }
        if (liber) break
        baza++
      }
      for (let k = 0; k < inalt; k++) ultima[baza + k] = d.end
      if (cuEticheta) etichete.set(idDeplasare(d), baza)
      for (const [id, k] of local) lucrari.set(id, baza + cap + k)
    }
    return { lucrari, etichete }
  })

  const benzi = $derived(impachetare.lucrari)

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

  /* `plafonZi` si `ascunseZi` au plecat odata cu contorul din celula (C6): erau
     folosite DOAR de el. Plafonul in sine ramane — `benziPeRand` il aplica la
     desenare (`MAX_BENZI`), deci o zi cu prea multe lucrari tot nu le arata pe
     toate; ce nu mai exista e numarul care o spunea. Pe baza reala nu se atinge:
     maximul masurat e 3 lucrari suprapuse, plafonul e 5. */

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
        // `p?.id`: taie si intervale care nu apartin unei lucrari (chenarul unei
        // deplasari), iar acolo cheia se rescrie oricum de apelant.
        cheie: `${p?.id ?? ''}|${grila[i].iso}`,
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

  /** CHENARUL IESIRII — zilele consecutive la acelasi `loc|client`, ca un singur
   *  obiect, cu lucrarile desenate INAUNTRU.
   *
   *  Fara el, alipirea n-avea ce sa arate: doua perioade care se ating devin o
   *  singura deplasare (`deplasari` le grupeaza deja pe cheia asta), dar pe ecran
   *  ramaneau doua bare la fel ca inainte — schimbarea se vedea doar in captura
   *  din antetul zilei. Acum peretele dintre cele doua chenare chiar se stinge, iar
   *  colturile din dreptul lui se indreapta: raza sta doar pe capetele ADEVARATE
   *  ale iesirii, deci la alipire cele doua muchii rotunjite din mijloc dispar.
   *
   *  Verticala: chenarul acopera exact benzile lucrarilor lui (de la cea mai de sus
   *  la cea mai de jos). Perioadele nu se suprapun, deci doua iesiri ajung pe
   *  aceeasi zi doar cand una e la sediu si alta pe teren — si atunci lucrarile lor
   *  sunt oricum pe benzi diferite. */
  const chenare = $derived.by(() => {
    const out = []
    for (const d of deplasari) {
      let sus = Infinity, jos = -1
      for (const p of d.items.values()) {
        const l = benzi.get(p.id) ?? 0
        if (l < sus) sus = l
        if (l > jos) jos = l
      }
      if (jos < 0) continue
      // Randul etichetei e capatul de sus al chenarului: numele iesirii sta
      // INAUNTRU, pe primul ei rand, iar lucrarile incep sub el.
      const et = impachetare.etichete.get(idDeplasare(d))
      if (et !== undefined && et < sus) sus = et
      for (const f of feliaza(d.start, d.end, sus, null)) {
        const plafon = benziPeRand[f.rand - 1] ?? 1
        if (sus >= plafon) continue
        out.push({
          ...f,
          d,
          areEticheta: et !== undefined,
          inalt: Math.min(jos, plafon - 1) - sus + 1,
          cheie: `${d.cheie}|${f.zile[0]}`,
        })
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
  /* CULOAREA PE PROIECT A PLECAT (turele 7-8).
     Sapte nuante impartite peste proiecte pareau informatie, dar nu SELECTAU
     nimic: din 12 perioade ale anului, 11 sunt la acelasi client — deci grila
     iesea aproape monocroma oricum, iar cele doua-trei exceptii erau singurele
     care primeau o culoare proprie, adica exact pe dos fata de cat conteaza.
     Mai grav, culoarea de identitate statea pe ACELASI ecran cu fillul care
     spune faza: acelasi canal, doua intelesuri.
     Acum: FORMA spune faza (plin = implementare, contur palid = pregatire),
     LOCUL SE SCRIE (iconita + „Sediu EGB · 3 zile" in eticheta iesirii), iar
     culoarea e una singura. Numele lucrarii scrie in bara — el deosebeste
     lucrarile, si el se poate citi. Nicio textura: ar fi a treia axa. */
  function culoareLucrare(_p) { return 'var(--accent)' }

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
    ancoreazaPe(selectata)
    idxDecis = (decisCurent + 1) % deDecis.length
    load()
    aratPanoul()
  }

  // AGENDA FERESTREI — raspunsul la „ce am luna asta", pe telefon.
  //
  // Sub 620px `.banda-t` si `.chenar-et` sunt `display: none`, deci grila ramane o harta
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
  // Orice salt la o zi anume („de clarificat", „Urmează") e tot o navigare in
  // timp — doar ca lungimea pasului o da destinatia, nu butonul. Se calculeaza
  // INAINTE de a rescrie `anchor`, altfel s-ar compara cu el insusi.
  function ancoreazaPe(iso) {
    const tinta = monthStart(iso)
    sensLuna = tinta === anchor ? 0 : (tinta < anchor ? -1 : 1)
    anchor = tinta
  }

  function pas(n) {
    sensLuna = n < 0 ? -1 : 1
    anchor = addMonths(anchor, n)
    load()
  }
  function laAzi() {
    // „Azi" e tot un salt la o zi anume, doar ca poate fi de un an: acelasi
    // calcul de sens ca la „de clarificat" sau „Urmează". Daca esti deja acolo,
    // n-ai mers nicaieri si grila nu se misca.
    ancoreazaPe(azi)
    selectata = azi
    load()
  }
  // `setMod` a plecat odata cu `mod` (V9): nu-l mai chema nimeni de cand
  // comutatorul „Lună / 2 săpt." a fost sters din bara, in turul 6.

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
   *  durata.
   *
   *  PERIOADELE NU SE SUPRAPUN — asta era deja regula, doar ca aici nimeni nu o
   *  tinea: `redimensioneaza` scria capetele si lasa coliziunea sa se intample.
   *  Ce se intampla cu vecinul depinde de CINE e vecinul, si cele doua cazuri nu
   *  seamana deloc:
   *
   *    acelasi `loc|client`  -> nu e coliziune, e CONTINUARE. Nu se scrie nimic in
   *      plus: `deplasari` grupeaza deja zilele consecutive pe cheia asta, deci in
   *      clipa in care se ating, datele spun „o singura iesire" (o captura, un
   *      numar de zile mai mare). Desenul ajunge din urma singur.
   *    alt loc sau alt client -> nu poti fi in doua locuri in aceeasi zi, deci
   *      vecinul se da mai incolo, cu o zi LUCRATOARE (sare peste weekend), si
   *      isi pastreaza durata.
   *
   *  Amandoua sunt schimbari de date, deci amandoua se pot da inapoi din toast. */
  async function intinde(p, start, sfarsit) {
    const s0 = p.data_start
    const f0 = p.data_sfarsit || p.data_start
    if (start === s0 && sfarsit === f0) return
    const cheie = cheieGrup(p)
    const toate = data?.perioade || []

    // Alipirea nu are nevoie de nicio scriere — se citeste din date. O tinem doar
    // ca sa stim ce scrie in toast, si NUMAI cand chiar s-a alipit ceva nou: doi
    // vecini care se atingeau si inainte erau deja o singura deplasare, deci
    // „s-au unit acum" ar fi o minciuna despre ce tocmai ai facut.
    const alipite = toate.filter((q) => q.id !== p.id && cheieGrup(q) === cheie
      && seAting(q, start, sfarsit) && !seAting(q, s0, f0))

    // IMPINGEREA E A DATELOR, NU A ECRANULUI — deci algoritmul sta in
    // `lib/deplasari.js`, langa regula `loc|client` pe care o foloseste. A trait
    // o vreme aici, scris de mana, si a doua oara in formularul de perioada; doua
    // implementari ale aceleiasi reguli se despart tacut la prima corectie, iar
    // atunci calendarul si formularul ti-ar promite mutari diferite.
    const mutari = rezolvaCiocniri(
      toate,
      { id: p.id, data_start: start, data_sfarsit: sfarsit, locatie: p.locatie, client: p.client },
    ).map((m) => ({ q: m.p, start: m.data_start, sfarsit: m.data_sfarsit }))

    const inapoi = [
      { id: p.id, data_start: s0, data_sfarsit: f0 },
      ...mutari.map((m) => ({
        id: m.q.id, data_start: m.q.data_start, data_sfarsit: m.q.data_sfarsit || m.q.data_start,
      })),
    ]

    busy = p.id
    try {
      await apiJson(`/api/implementari/${p.id}`, {
        method: 'PUT', body: { data_start: start, data_sfarsit: sfarsit },
      })
      for (const m of mutari) {
        await apiJson(`/api/implementari/${m.q.id}`, {
          method: 'PUT', body: { data_start: m.start, data_sfarsit: m.sfarsit },
        })
      }
      selectata = start
      await load(true)

      const refa = async () => {
        for (const v of inapoi) {
          await apiJson(`/api/implementari/${v.id}`, {
            method: 'PUT', body: { data_start: v.data_start, data_sfarsit: v.data_sfarsit },
          })
        }
        await load(true)
      }
      if (mutari.length) {
        const m = mutari[0]
        const cine = (m.q.client || '').trim() ? scurt(m.q.client) : etichetaLucrare(m.q)
        toastUndo(mutari.length > 1
          ? `${mutari.length} perioade împinse — prima pe ${shortDate(m.start)}`
          : `${cine} · împins pe ${shortDate(m.start)}`, { onUndo: refa })
      } else if (alipite.length) {
        // Numarul de zile e al DEPLASARII de dupa, nu al perioadei trase: tocmai
        // asta s-a schimbat sub ochi (2 zile + 3 zile = o iesire de 5). Se ia din
        // datele reincarcate, nu se recalculeaza aici — alipirea poate prinde si un
        // al treilea vecin, iar doua socoteli ale aceluiasi lucru diverg.
        const d = deplasareaZilei.get(`${start}|${cheie}`)
        const zile = d ? Math.max(0, diffDays(d.start, d.end)) + 1
                       : Math.max(0, diffDays(start, sfarsit)) + 1
        const cine = (p.client || '').trim() ? scurt(p.client) : ''
        toastUndo(`${cine ? cine + ' · ' : ''}${d ? `${shortDate(d.start)}–${shortDate(d.end)}` : shortDate(start)} · o deplasare, ${zile} zile`,
                  { onUndo: refa })
      } else {
        const zile = Math.max(0, diffDays(start, sfarsit)) + 1
        toastUndo(`${shortDate(start)}–${shortDate(sfarsit)} · ${zile} ${zile === 1 ? 'zi' : 'zile'}`,
                  { onUndo: refa })
      }
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
      deschideNeplanificate = false
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

  /** PE TELEFON PISTA SE CITESTE, NU SE MANIPULEAZA.
   *
   *  Toate trei gesturile de mai jos sunt de precizie: alegi o ZI dintr-o celula
   *  care pe telefon are ~48px si e acoperita de benzi. Ce iese din gest nu e
   *  „aproape ce voiai" — e o alta zi, scrisa in baza. Grila ramane harta; ce se
   *  poate face de pe telefon incape intr-o intrebare: atingi ziua si raspunzi in
   *  panou (mută, scoate, s-a făcut).
   *
   *  `grosier` (adica `@media (hover: none)`), nu doar latimea: pe un ecran fara
   *  hover nu exista nici afordanta — manerele n-au cum sa apara la apropierea
   *  cursorului, deci gestul n-ar fi anuntat de nimic. Aceeasi conditie ca in CSS,
   *  ca desenul si comportamentul sa nu se poata desincroniza. */
  function seManipuleaza() {
    return !ecran.telefon && !ecran.grosier
  }

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
    if (!seManipuleaza()) return
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
    if (!seManipuleaza()) return
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
          intinde(p, v.data_start, v.data_sfarsit)
        }
      },
      laAnulare: curataTragere,
    })
  }

  /** Deplasarea intreaga: toate lucrarile ei se decaleaza cu acelasi numar de
   *  zile, deci forma iesirii se pastreaza. */
  function apucaDeplasare(e, d) {
    if (!seManipuleaza()) return
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
  // Eticheta iesirii (`.chenar-et`, care muta toata deplasarea) si `.maner` (schimba
  // capetele) erau `<span>`-uri cu `onpointerdown`, fara `role` si fara `tabindex`,
  // si stateau IN INTERIORUL unui `<button>`. Buton in buton e markup invalid,
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
      intinde(p, s, nou)
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
      deschideNeplanificate = false
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

<!-- `.ruta-in` sta pe INVELIS, deci se joaca odata la intrarea pe ruta — inclusiv
     peste schelet. Bara de sus nu primeste `.cell-in`: ea e cadrul, si urca odata
     cu el. Celulele sunt cele trei lucruri care se schimba (KPI, grila, panoul). -->
<div class="page ruta-in">
  {#if loading}
    <Skeleton height="360px" />
  {:else if error}
    <ErrorState message={error} onretry={load} />
  {:else if data}

    <div class="bar">
      <div class="nav">
        <button class="ico" onclick={() => pas(-1)} aria-label="Înapoi"><ChevronLeft size={16} /></button>
        <span class="titlu">{monthLabel(anchor)}</span>
        <button class="ico" onclick={() => pas(1)} aria-label="Înainte"><ChevronRight size={16} /></button>
        <button class="b-azi" onclick={laAzi}>Azi</button>
        <!-- Exportul .ics a venit aici din Admin (sters): calendarul de abonat din
             telefon apartine paginii de calendar, nu unui sertar de intretinere.
             STA IN RANDUL DE NAVIGARE, imediat dupa „Azi", cum e desenat
             (`Calendar.dc.html`, bara din 6a/7a/8a). Ramasese singur in `.mods` —
             containerul comutatorului „Luna / 2 sapt.", care a fost sters: pe
             desktop iesea un grup separat impins la capatul barei, iar pe telefon
             `.mods { width: 100% }` ii dadea un RAND intreg doar lui, sub bara. -->
        <button class="ics" onclick={() => window.open('/api/export/ics', '_blank')}
                title="Descarcă .ics — perioadele și scadențele de task. Abonează-te din calendarul telefonului.">
          <Download size={13} /> .ics
        </button>
      </div>
    </div>

    <!-- RANDUL DE KPI A PLECAT. „Zile pe teren", „deplasări", „zile la sediu"
         sunt statistici: le citeai, dadeai din cap si mergeai mai departe —
         niciuna nu decidea o actiune, iar toate trei se pot NUMARA uitandu-te la
         grila de dedesubt, care le si arata UNDE sunt.

         Raman cele doua care duc undeva si cer ceva de facut. Plus „Proiecte
         fara perioada", urcat aici din coloana care dispare: e o SURSA (proiecte
         care asteapta sa fie asezate pe zile), nu un detaliu al zilei selectate
         — iar in panou nu se vedea tocmai cand n-aveai nicio zi deschisa. -->
    <div class="surse cell-in" style="--celula: 0">
      {#if data.neplanificate?.length}
        <button class="sursa" onclick={() => { selectata = ''; deschideNeplanificate = !deschideNeplanificate }}
                aria-expanded={deschideNeplanificate}
                title="Proiecte active fără nicio zi planificată">
          <CalendarX2 size={14} strokeWidth={1.5} />
          <span class="s-n">{data.neplanificate.length}</span> fără perioadă
        </button>
      {/if}
      {#if rezumat.deDecis}
        <!-- Contorul PARCURGE lista: fiecare apasare duce la urmatoarea zi de
             clarificat, si arata unde esti. -->
        <button class="sursa rau" onclick={urmatorulDeClarificat}
                title="Mergi la următoarea zi de clarificat">
          <TriangleAlert size={14} strokeWidth={1.5} />
          <span class="s-n">{rezumat.deDecis > 1 ? `${decisCurent + 1}/${rezumat.deDecis}` : rezumat.deDecis}</span> de clarificat
        </button>
      {/if}
      {#if data.probleme?.length}
        <!-- Nimic nu dispare in tacere: o data pe care aplicatia nu o poate citi
             nu se aseaza pe nicio zi, deci randul lipseste din calendar fara
             niciun semn. Mai bine un semnal suparator decat o absenta tacuta. -->
        <button class="sursa rau" onclick={() => navigate(`/projects/${data.probleme[0].proiect_id}`)}
                title={data.probleme.map(p => `${p.nume} — ${p.unde}, ${p.camp}: „${p.valoare}”`).join('\n')}>
          <TriangleAlert size={14} strokeWidth={1.5} />
          <span class="s-n">{data.probleme.length}</span>
          {data.probleme.length === 1 ? 'dată necitibilă' : 'date necitibile'}
        </button>
      {/if}
    </div>

    <div class="wrap" class:cu-panou={panouDeschis}>
      <div class="cal cell-in" style="--celula: 1">
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
        <!-- `{#key anchor}` REFACE grila la fiecare navigare, si tocmai de-asta e
             aici: o clasa comutata nu re-porneste o animatie CSS cand ramane
             aceeasi (doua apasari „inainte" la rand = o singura alunecare, adica
             fix cazul pe care 13c il rezolva). Un bloc nou inseamna o tranzitie
             noua, de fiecare data. Cheia e `anchor`: fereastra e ce se schimba. -->
        {#key anchor}
        <div class="grid" class:trag={!!trag} role="grid" aria-label="Calendar"
             in:alunecare={{ sens: sensLuna }}>
          {#each grila as g, i (g.iso)}
            {@const items = aleZilei(g.iso)}
            {@const decizie = items.some(p => p.necesita_decizie)}
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
              class:col-ultima={i % 7 === 6}
              class:rand-ultim={i >= grila.length - 7}
              class:we={isWeekend(g.iso)}
              class:azi={g.iso === azi}
              class:sel={g.iso === selectata}
              class:drop={dropZi === g.iso}
              class:decizie
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
                <!-- AZI E TENTA PE CELULA + CUVANTUL; PASTILA E A SELECTIEI.
                     Erau invers, si asta costa doua lucruri. Azi purta pastila
                     plina, deci ziua in care te uiti tipa mai tare decat orice
                     actiune de pe o pagina care e despre planificare. Iar selectia
                     lua tenta PLUS un inel de 2px — deci inelul era deja ocupat si
                     la tragere nu mai aveai cu ce arata ziua de sub deget, exact
                     rolul pentru care fusese rezervat.
                     Cuvantul „azi" e scris, nu doar colorat: o tenta singura nu
                     spune CARE din stari e, iar un cuvant nu se confunda cu nimic. -->
                <span class="n">{parseISO(g.iso).getDate()}</span>
                {#if g.iso === azi}<span class="azi-et">azi</span>{/if}
                <!-- CONTORUL DE LUCRARI A PLECAT (C6): singurul numar din celula e
                     cifra zilei. Numara ce se vede oricum — la 100px randul isi
                     desfasoara toate benzile, fiecare cu numele scris in ea, deci
                     „2" statea langa doua bare pe care le vezi. Era pus si ca semn
                     pentru lucrarile peste `MAX_BENZI`, care nu se deseneaza; masurat
                     pe baza reala, maximul e 3 lucrari suprapuse intr-o zi si ZERO
                     zile peste plafon, deci ramura aia nu s-a randat niciodata. -->
              </div>
              {#if decizie}<span class="flag" title="Perioadă trecută, proiect nemutat"><TriangleAlert size={11} /></span>{/if}

              <!-- Barele NU mai stau in celula: o lucrare de mai multe zile e un
                   singur element, desenat peste coloane mai jos. Celula pastreaza
                   doar antetul, semnalele si inaltimea rezervata benzilor. -->
            </div>
          {/each}

          <!-- CHENARUL IESIRII, sub benzi. O singura muchie pentru zilele
               consecutive la acelasi `loc|client`, cu lucrarile inauntru: asa se
               vede dintr-o privire ca 12–16 august e O deplasare cu doua lucrari,
               nu cinci zile separate. La alipire, doua chenare devin unul —
               peretele dintre ele se stinge si colturile se indreapta, fiindca
               raza sta doar pe capetele adevarate ale iesirii. -->
          {#each chenare as c (c.cheie)}
            <div class="chenar"
                 class:inceput={c.inceput}
                 class:sfarsit={c.sfarsit}
                 class:sediu={c.d.sediu}
                 style="grid-row: {c.rand}; grid-column: {c.col} / span {c.span}; --i: {c.banda}; --n: {c.inalt}">
              <!-- ETICHETA STA IN CHENARUL EI, pe primul lui rand. Era un chip
                   lipit de cifra zilei, in antet — deci numele iesirii statea in
                   AFARA obiectului pe care il numeste, iar „asta e o iesire de 3
                   zile, cu lucrarile astea" se citea din doua locuri.
                   Doar pe felia de INCEPUT: la granita de saptamana chenarul se
                   taie, iar a doua bucata nu incepe nimic — ar scrie a doua oara
                   durata intregii iesiri, ca si cum ar reincepe. -->
              {#if c.inceput && c.areEticheta}
                <button class="chenar-et" class:sediu={c.d.sediu}
                        class:se-trage={trag?.tip === 'deplasare' && trag.cheie === c.d.cheie}
                        onpointerdown={(e) => apucaDeplasare(e, c.d)}
                        onclick={(e) => e.stopPropagation()}
                        title={etichetaDeplasare(c.d)}
                        aria-label="Deplasare {c.d.client || 'la sediu'} — {textCaptura(c.d)}. Trage ca să muți toată ieșirea.">
                  {#if c.d.sediu}<Building2 size={12} />{:else}<MapPin size={12} />{/if}{textCaptura(c.d)}
                </button>
              {/if}
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
        {/key}

        <!-- LEGENDA A PLECAT DE TOT.
             Avea patru mostre pentru cele doua axe combinate (loc x faza) — o
             matrice corecta, dar care exista fiindca aveam TREI canale de citit
             deodata: culoare (proiect), textura (loc) si intensitate (faza).
             Culoarea de identitate a plecat, deci raman doua, iar amandoua se
             spun si in CUVINTE in panoul zilei, langa lucrare. O legenda care
             traduce ce scrie la un centimetru mai jos nu invata pe nimeni nimic. -->
        <!-- IESIRILE FERESTREI, SCRISE. Doar pe telefon: acolo grila e o harta de
             dungi fara nume (vezi `agendaLunii`). Grila ramane harta — unde esti,
             cat de plin e — iar dedesubt scrie ce sunt dungile, in ordinea zilelor. -->
        {#if agendaLunii.length}
          <div class="agenda">
            <div class="ag-cap">
              <span>Ieșirile lunii</span>
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

      {#if panouDeschis}
      <aside class="side cell-in" style="--celula: 2">
        <!-- PANOUL E UN OBIECT CARE SE SCHIMBA, NU O LISTA CARE CLIPESTE SUB UN
             TITLU FIX.
             Lucrarile se estompau una cate una, dar `.pan-zi` — data zilei, adica
             exact partea care se schimba cel mai vizibil cand alegi alta zi —
             sarea. Ochiul urmarea ce se misca, deci se uita la lista, si citea
             titlul cu o intarziere; iar cand ziua noua avea tot doua lucrari,
             singurul semn ca s-a schimbat ceva era o stingere pe randuri care
             arata la fel.
             `|local`: la prima incarcare panoul soseste odata cu `.side` prin
             `.cell-in`. Fara `local`, cele doua ar juca peste aceiasi pixeli.
             `{#key}` pe ziua selectata — nu pe continut: doua zile pot avea
             aceleasi lucrari, si tot trebuie sa se vada ca ai schimbat ziua. -->
        {#key selectata}
        <div class="pan" in:sosire|local>
          <div class="pan-zi">{dayLabel(selectata)}</div>
          {#if selectate.length}
            <div class="pan-sub">
              {#if grupuriSelectate.length > 1}
                <TriangleAlert size={13} /> {grupuriSelectate.length} locuri diferite în aceeași zi — verifică
              {:else if grupuriSelectate[0]?.sediu}
                <!-- la sediu NU esti in deplasare: nu urci in masina -->
                <Building2 size={13} /> la sediu{grupuriSelectate[0].client ? ' · ' + scurt(grupuriSelectate[0].client) : ''} · {selectate.length} {selectate.length === 1 ? 'lucrare' : 'lucrări'}
              {:else}
                {@const d = grupuriSelectate[0] ? deplasareaLui(grupuriSelectate[0], selectata) : null}
                <MapPin size={13} /> o deplasare{grupuriSelectate[0]?.client ? ' · ' + scurt(grupuriSelectate[0].client) : ''}{#if d && d.start !== d.end}{' · '}{shortDate(d.start)}–{shortDate(d.end)}, {d.items.size} {d.items.size === 1 ? 'lucrare' : 'lucrări'} în total{:else}{' · '}{selectate.length} {selectate.length === 1 ? 'lucrare' : 'lucrări'}{/if}
              {/if}
            </div>
            {#each selectate as p (p.id)}
              <!-- Fara stingere pe rand: panoul intreg a sosit deja, o data.
                   Doua sosiri peste aceiasi pixeli nu se aduna, se incurca. -->
              <div class="it" style="--c: {culoareLucrare(p)}">
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
                    <div class="mut" in:fade={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
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
              <button class="urm" onclick={() => { selectata = ceUrmeaza.start; ancoreazaPe(ceUrmeaza.start) }}>
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
        {/key}

        {#if deschideNeplanificate && data.neplanificate?.length}
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
                     style="--c: var(--accent)"
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
      {/if}
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
  /* O SINGURA HAINA DE CONTROL PE ECRAN. Erau 28px cu chenar, imediat deasupra
     lui `.sursa`, care e fara chenar si cu umbra — doua haine pentru acelasi fel
     de buton, iar a doua e cea din sistem (suprafata se desprinde prin umbra).
     38px, cat spune desenul (`Calendar.dc.html`), si aceeasi valoare pe `.sursa`
     de sub ele: doua randuri de controale nu se pot deosebi prin patru pixeli
     pe care nu i-a ales nimeni.
     Treapta de text e `--font-body` (15/600), nu `--font-control` (13): bara
     Calendarului e ETICHETA DE PAGINA, nu un control asezat in rand. */
  .ico, .b-azi, .ics { border: none; background: var(--bg-surface); color: var(--text-secondary);
    box-shadow: var(--shadow-sm); transition: var(--transition-pressable);
    border-radius: var(--radius-sm); cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
  .ico { width: 38px; height: 38px; }
  .b-azi, .ics { height: 38px; padding: 0 12px; font-size: var(--font-body); font-weight: var(--fw-semibold); }
  .ico:hover, .b-azi:hover, .ics:hover { background: var(--bg-hover); color: var(--text); }
  .ico:active, .b-azi:active, .ics:active { transform: scale(var(--press-scale)); }
  .ics { gap: 5px; }

  /* SURSELE — controale cu numar in capul paginii, nu contoare.
     Fiecare DUCE undeva si cere ceva de facut; aceeasi haina ca perechea de pe
     Acasa, ca sa se recunoasca de pe un ecran pe altul. Tonul e singura
     diferenta: neutru = ce lipseste, restant = ce e gresit acum. */
  .surse { display: flex; gap: var(--space-sm); margin-bottom: var(--space-md); flex-wrap: wrap; }
  .sursa { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap;
    min-height: 38px; padding: 0 12px; border-radius: var(--radius-xs);
    background: var(--bg-surface); box-shadow: var(--shadow-sm); border: none;
    color: var(--text-dim); font-family: inherit; font-size: var(--font-small);
    cursor: pointer; transition: var(--transition-pressable); }
  .sursa:hover { background: var(--bg-hover); color: var(--text-secondary); }
  .sursa:active { transform: scale(var(--press-scale)); }
  .s-n { font-family: var(--font-mono); font-variant-numeric: tabular-nums; color: var(--text-secondary); }
  /* Tenta de restant poarta cerneala ADANCA, niciodata culoarea plina. */
  .sursa.rau { background: var(--danger-subtle); color: var(--danger-deep); box-shadow: none; }
  .sursa.rau:hover { background: color-mix(in oklab, var(--danger) 22%, var(--bg-surface)); }
  .sursa.rau .s-n { color: var(--danger-deep); }

  /* PANOUL FACE LOC, NU ACOPERA: coloana lui apare ODATA CU EL. */
  .wrap { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-md); align-items: start; }
  .wrap.cu-panou { grid-template-columns: minmax(0, 1fr) 300px; }

  /* Cardul nu mai are padding (C7): grila ATINGE marginile lui, deci linia de sub
     antetul zilelor si separatoarele dintre coloane merg dintr-o muchie in alta.
     Cu `--space-sm` de jur imprejur, capetele liniilor se opreau in aer si grila
     plutea intr-o rama de fond — adica exact cele 35 de cutii pe care R1 le-a scos,
     doar mutate cu un pas mai incolo. Raza sta pe card, deci `overflow: hidden`
     taie colturile celulelor din primul si ultimul rand. */
  .cal { background: var(--bg-surface); border: 0; border-radius: var(--radius-md); box-shadow: var(--shadow-md); padding: 0; overflow: hidden; }
  /* Antetul zilelor e PRIMUL RAND AL GRILEI, nu o eticheta deasupra ei: aceleasi
     sapte coloane, aceleasi separatoare verticale `--border`, si o linie
     `--border-strong` dedesubt — mai tare decat cele dintre zile, fiindca desparte
     antetul de continut, nu o zi de alta. */
  .wd { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 0;
        box-shadow: inset 0 -1px 0 var(--border-strong); }
  .wd span { height: 32px; display: inline-flex; align-items: center; justify-content: center;
             font-size: var(--font-label); font-weight: var(--fw-semibold); color: var(--text-faint);
             text-transform: uppercase; letter-spacing: var(--tracking-label);
             box-shadow: inset -1px 0 0 var(--border); }
  .wd span:last-child { box-shadow: none; }
  /* `minmax(0, 1fr)`, nu `1fr`: `1fr` inseamna `minmax(auto, 1fr)`, deci o banda
     care se intinde peste coloane si are `nowrap` isi impune latimea minima si
     largeste coloanele pe care le acopera. Zilele nu mai erau egale si nu se mai
     aliniau cu antetul de zile al saptamanii. */
  .grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 0; }

  /* O LUNA E O HARTA, NU 35 DE OBIECTE.
     Celula statea pe `border: 1px` + `radius-md` + fond propriu, intr-o grila cu
     gap de 4px — deci pagina desena 35 de cutii rotunjite, fiecare cu conturul ei,
     si ochiul le numara una cate una in loc sa citeasca luna. Acum grila e O
     SINGURA suprafata (`.cal`), iar celulele se desprind din linii INTERIOARE:
     muchia din dreapta desparte zilele, cea de jos desparte saptamanile — de aceea
     a doua e `--border-strong`, ca randul de saptamana sa se citeasca mai tare
     decat coloana de zi.
     `gap: 0` e obligatoriu: cu spatiu intre celule liniile ar pluti separat si n-ar
     mai forma o grila. Consecinta se vede mai jos, la benzi — capetele care
     „continua" nu mai au un gol de acoperit, deci margina negativa a plecat. */
  /* CELULA E O SUPRAFATA DE CITIT, NU UN RAND STRANS IN JURUL BENZILOR (C3/C4).
     `calc(32px + benzi * 20px)` dadea 52px pe o luna cu o lucrare pe zi: luna se
     citea ca o listă indesata, nu ca o harta pe care vezi unde esti. Acum podeaua
     e 100px si randul CRESTE doar daca benzile chiar cer mai mult — `max()`, nu
     invers. Cu MAX_BENZI = 5 plafonul urca la 132px; augustul real, cu 3 benzi pe
     randul cel mai plin, sta la 124. */
  .zi { position: relative; min-height: max(100px, calc(32px + var(--benzi, 1) * 20px)); padding: 5px 8px 0;
        border: 0; background: none; text-align: left; cursor: pointer;
        box-shadow: inset -1px 0 0 var(--border), inset 0 -1px 0 var(--border-strong);
        display: flex; flex-direction: column; gap: 3px; overflow: hidden;
        transition: background var(--dur-fast) var(--ease); }
  .zi:hover { background: var(--bg-hover); }
  .zi:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  /* Ziua din alta luna: cifra trece pe `--text-dim`, nu toata celula pe 42%.
     Opacitatea inmulteste peste tokenuri deja la limita — si stingea si benzile,
     nu doar cifra, desi lucrarile din ele sunt la fel de reale. */
  .zi.alta .n { color: var(--text-dim); }
  /* Liniile sunt SEPARATOARE, deci nu au ce cauta pe marginea de afara: acolo n-au
     ce despartii, si impreuna ar desena inapoi chiar chenarul scos de R1 — doar cu
     un pas mai incolo, pe cardul intreg. */
  .zi.col-ultima { box-shadow: inset 0 -1px 0 var(--border-strong); }
  .zi.rand-ultim { box-shadow: inset -1px 0 0 var(--border); }
  .zi.col-ultima.rand-ultim { box-shadow: none; }
  /* WEEKENDUL E SUPRAFATA A DOUA, NU UN PROCENT DE TEXT.
     Statea pe `color-mix(--text 4%, --bg-elevated)` — adica o culoare inventata
     peste un fond care era el insusi ridicat. Acum, grila fiind o singura
     suprafata (`--bg-surface`), sambata si duminica sunt pur si simplu
     `--bg-elevated`: contrastul vine din NIVELUL de suprafata, pe care sistemul
     il are deja, nu dintr-un procent ales de mana. */
  .zi.we { background: var(--bg-elevated); }
  /* UN CANAL PER INTREBARE — si canalele NU sunt cele de dinainte.
     Erau inversate: azi purta pastila plina (deci tipa mai tare decat orice
     actiune de pe ecran), iar selectia lua tenta PLUS un inel de 2px. Doua
     consecinte: ziua in care te uiti domina o pagina care e despre planificare,
     si — mai grav — inelul era deja ocupat, deci la TRAGERE nu mai aveai cu ce
     arata ziua de sub deget, exact rolul pentru care fusese rezervat.
       tenta pe celula + cuvantul „azi" = AZI (o zi ca oricare, doar insemnata)
       cifra in pastila plina           = ziua SELECTATA
       inelul                           = ziua de sub deget, la tragere
       coltul                           = de clarificat (triunghiul `.flag`)
     „azi" se si SCRIE, nu doar se coloreaza: o tenta singura n-ar spune care din
     cele doua stari e, iar cuvantul nu se poate confunda cu nimic. */
  .zi.azi { background: var(--accent-subtle); }
  .zi.drop, .zi.tinta:hover, .zi.tinta:active {
    outline: 2px solid var(--accent); outline-offset: -2px; background: var(--accent-subtle); }
  /* Cat timp un proiect asteapta sa fie asezat, TOATE zilele arata ca destinatii
     posibile — altfel „alege un proiect, apoi ziua" cere sa stii ca a doua
     atingere face altceva decat de obicei. */
  .zi.tinta { outline: 2px dashed color-mix(in srgb, var(--accent) 55%, transparent); outline-offset: -2px; }

  /* Cifra zilei sta pe `--text-secondary`, nu pe `--text-dim`: intr-o celula de
     100px ea e reperul dupa care citesti luna, iar `--text-dim` e podeaua pentru
     text mic — o folosea si ziua din alta luna, deci cele doua nu se deosebeau. */
  .n { display: inline-flex; align-items: center; justify-content: center;
    min-width: 15px; height: 15px; padding: 0 3px; border-radius: var(--radius-full);
    font-family: var(--font-mono); font-size: var(--font-small); font-weight: var(--fw-medium);
    color: var(--text-secondary); font-variant-numeric: tabular-nums; }
  /* Pastila plina e a SELECTIEI: ea e raspunsul la „ce zi am deschis", si e
     singura stare pe care o alegi tu. Azi doar se intampla sa fie azi. */
  /* DREPTUNGHI, NU BULINA. Bulina de 15px era rotunda ca bifa unui task si nu
     incapea decat o cifra ingusta — „31" o umfla intr-un oval. 24×22 cu
     `--radius-xs` tine orice zi la aceeasi latime si se citeste ca o CELULA
     insemnata, nu ca un punct. Paddingul celulei scade la `3px 3px 0` doar pe ea,
     ca dreptunghiul sa nu impinga benzile in jos cu cei 5px in plus. */
  .zi.sel { padding: 3px 3px 0; }
  .zi.sel .n { width: 24px; height: 22px; min-width: 0; padding: 0; border-radius: var(--radius-xs);
               background: var(--accent); color: var(--accent-text); font-weight: var(--fw-semibold); }
  /* Cuvantul, nu inca o culoare. Sta pe cerneala adanca fiindca fondul celulei e
     deja tenta de accent — text pe tenta ia intotdeauna varianta `-deep`. */
  /* Pe ziua de azi cifra poarta ea insasi accentul: tenta celulei spune „azi",
     dar pe un rand de 100px tenta e o suprafata mare si palida, iar cifra ramanea
     la fel ca in orice alta zi. Cuvantul de langa ea sta pe aceeasi linie de baza,
     nu centrat — doua marimi centrate una langa alta plutesc. */
  .zi.azi .n { color: var(--accent-deep); font-weight: var(--fw-semibold); }
  .zi.azi .zi-h { align-items: baseline; }
  .azi-et { font-family: var(--font-mono); font-size: var(--font-label); font-weight: var(--fw-semibold);
            color: var(--accent-deep); letter-spacing: var(--tracking-label); }
  .flag { position: absolute; top: 4px; right: 4px; color: var(--danger); display: inline-flex; }

  /* O LUCRARE = O BANDA, oricat de multe zile ar tine. Se intinde peste coloane,
     acopera si spatiile dintre ele, deci numele se scrie o data si are toata
     latimea lucrarii la dispozitie.
     `--i` e banda (randul) lucrarii. Decalajul de sus trebuie sa fie EXACT cel al
     zonei de bare din celula, altfel benzile plutesc pe langa celule:
       padding 5 + antet 15 + gap 3 = 23px
     iar pasul unei benzi = inaltimea barei 17 + gap 3 = 20px. Cele doua numere
     sunt aceleasi cu cele din `min-height` al celulei — se schimba impreuna.
     Erau 24 cat timp celula avea bordura de 1px; R1 a scos-o, deci si pixelul ei. */
  .grid { --h-antet: 23px; --h-banda: 20px; }

  /* CHENARUL IESIRII. Sta SUB benzi (`z-index: 0`) si nu primeste evenimente:
     lucrarile raman obiectele pe care le apuci, el doar spune ca fac parte din
     aceeasi deplasare. Inaltimea acopera exact benzile lui (`--n`), minus gapul de
     3px de sub ultima, ca sa nu inghita randul urmator.
     Raza NUMAI pe capetele adevarate: la alipire, cele doua muchii rotunjite din
     mijloc dispar de la sine — asta E „peretele se stinge". Tranzitia de 280ms e
     cea de SUPRAFATA (`--dur-slow`): chenarul e o suprafata care se lungeste, nu
     un element care se muta. */
  .chenar { position: relative; z-index: 0; align-self: start; pointer-events: none;
            margin-top: calc(var(--h-antet) + var(--i) * var(--h-banda) - 3px);
            height: calc(var(--n) * var(--h-banda) + 3px);
            border: 1px solid color-mix(in srgb, var(--accent) 34%, transparent);
            border-left: none; border-right: none;
            background: color-mix(in srgb, var(--accent) 5%, transparent);
            transition: height var(--dur-slow) var(--ease), margin-top var(--dur-slow) var(--ease); }
  .chenar.inceput { margin-left: 3px; border-left: 1px solid color-mix(in srgb, var(--accent) 34%, transparent);
                    border-top-left-radius: var(--radius-sm); border-bottom-left-radius: var(--radius-sm); }
  .chenar.sfarsit { margin-right: 3px; border-right: 1px solid color-mix(in srgb, var(--accent) 34%, transparent);
                    border-top-right-radius: var(--radius-sm); border-bottom-right-radius: var(--radius-sm); }
  /* Sediul nu e deplasare: chenarul lui e doar o linie punctata, ca sa nu para ca
     ai plecat undeva. Locul RAMANE SCRIS (captura din antet) — asta e doar forma. */
  .chenar.sediu { border-style: dashed; background: none; }

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
  /* Capatul care CONTINUA se opreste fix pe muchia celulei. Cat timp grila avea
     gap de 4px, `-3px` il faceau sa treaca peste gol, ca sa nu para intrerupt;
     acum golul nu mai exista (R1), deci aceiasi 3px ar intra peste ziua vecina. */
  .banda:not(.inceput) { margin-left: 0; }
  .banda:not(.sfarsit) { margin-right: 0; }
  /* Cat timp se trage, nimic din ce pluteste peste celule nu mai raspunde la
     pointer: `ziDinPunct` foloseste `elementFromPoint`, deci ar nimeri banda in
     locul zilei. Fantoma e oricum inertă, dar o trecem si pe ea prin regula ca
     sa nu depinda de ordinea in care sunt scrise selectoarele. */
  .grid.trag .banda, .grid.trag .chenar-et { pointer-events: none; }

  /* FANTOMA E CONTUR PESTE BANDA REALA, NU O MUTA.
     Inainte banda apucata cobora la 32% si fantoma venea plina peste ea: la
     intindere cele doua se suprapun aproape complet, deci vedeai un singur
     dreptunghi cu doua opacitati si nu mai stiai care e starea de acum. Acum
     lucrarea ramane exact cum e — plina, cu numele ei — iar unde ar ajunge se
     spune printr-un contur de accent desenat peste ea. Fara fundal si fara text:
     al doilea exemplar al aceluiasi nume, decalat cu o zi, se citeste ca doua
     lucrari. */
  .fantoma { pointer-events: none; z-index: 3; background: none;
             outline: 2px solid var(--accent); outline-offset: -1px; }

  /* MANERELE DE PERIOADA — doua bare subtiri de accent, la hover.
     Late de 9px ca zona de prindere, dar ce se VEDE e o bara de 2px pe toata
     inaltimea benzii: la capatul unei perioade, o linie verticala inseamna „de
     aici se trage", pe cand pastila alba de dinainte era doar un semn ca exista
     ceva acolo. Zona de prindere se intinde peste inaltimea benzii si inca 5px
     sus/jos (`::before`) — banda are 17px, adica sub orice tinta rezonabila daca
     ne-am opri la conturul ei. */
  .maner { position: absolute; top: 0; bottom: 0; width: 9px; cursor: ew-resize;
           opacity: 0; transition: opacity var(--dur-fast) var(--ease); }
  .maner.st { left: 0; }
  .maner.dr { right: 0; }
  .maner::before { content: ''; position: absolute; inset: -5px -2px; }
  .maner::after { content: ''; position: absolute; top: -1px; bottom: -1px; left: 50%; width: 2px;
                  transform: translateX(-50%); border-radius: 1px; background: var(--accent); }
  .banda:hover .maner, .banda.se-trage .maner { opacity: 1; }
  /* PE TELEFON PISTA SE CITESTE, NU SE MANIPULEAZA.
     Manerele nu se ascund doar vizual — gestul insusi e oprit (vezi
     `incepeTragere` din `apuca*`). Un maner desenat fara gest in spate ar promite
     ceva ce nu se intampla, exact greseala pe care a facut-o versiunea cu
     drag-and-drop HTML5. */
  @media (hover: none) {
    .maner { display: none; }
  }
  /* FORMA SPUNE FAZA, LOCUL SE SCRIE.
     Hasura de „sediu" (`repeating-linear-gradient`) era a TREIA axa de citit pe
     acelasi obiect — ramasa din versiunea dinaintea redesenarii, desi comentariul
     de la `culoareLucrare` explica de ce culoarea de identitate a plecat. Locul
     il spun iconita (`building-2` / `map-pin`) si eticheta ieșirii („Sediu EGB ·
     3 zile"), adica un canal care se poate CITI. Ramane o singura diferenta de
     desen: plin = implementare, contur palid = pregatire. */
  .banda.pregatire { background: color-mix(in srgb, var(--c) 9%, transparent);
                     box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--c) 42%, transparent); }
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
  /* Eticheta iesirii: primul rand DIN chenar, nu un chip langa cifra zilei.
     Chenarul e `pointer-events: none` (lucrarile raman obiectele pe care le
     apuci), deci eticheta si-l reia pe al ei — ea E manerul cu care muti toata
     ieșirea. Inaltimea e exact un rand de banda fara gap (20 - 3), ca lucrarile
     de sub ea sa cada pe randurile lor. */
  .chenar-et { pointer-events: auto; display: inline-flex; align-items: center; gap: 4px;
               max-width: calc(100% - 10px); height: 17px; margin: 3px 0 0 7px; padding: 0 4px;
               border: none; background: none; cursor: grab;
               font-size: var(--font-label); font-weight: var(--fw-semibold);
               letter-spacing: var(--tracking-label); color: var(--accent-deep);
               overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chenar-et:active { cursor: grabbing; }
  .chenar-et:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
  /* Sediul nu e o deplasare, deci nici eticheta lui nu striga: chenarul lui e
     punctat, iar numele trece pe cerneala neutra. */
  .chenar-et.sediu { color: var(--text-secondary); }

  /* `.nr-lucrari` a plecat cu C6 — motivul e scris in markup, langa cifra zilei. */

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
  .pan { background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); padding: var(--space-md); }
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
  .it-m .tk.warn { color: var(--danger); }

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
    .surse { order: 2; margin: var(--space-md) 0 0; }
  }
  @media (max-width: 620px) {
    .page { padding: var(--space-md); }
    /* Benzile sunt mai subtiri pe telefon, deci si pasul lor — cele doua numere
       trebuie sa rămână in acord cu `--h-banda`, altfel benzile ies din celule. */
    .grid { --h-banda: 15px; }
    .zi { min-height: calc(25px + var(--benzi, 1) * 15px); }
    .banda { min-height: 12px; }
    .banda-t { display: none; }
    /* Captura se taia oricum la o felie ilizibila intr-o celula de ~48px. Ce spune
       ea — cine si cat — scrie acum in AGENDA de sub grila, unde incape. */
    /* Eticheta iesirii NU se ascunde de aici. Decizia e a lui `impachetare`, care
       pe telefon nu-i mai rezerva randul deloc (o celula de ~48px n-are loc de
       text, iar un rand gol ar fi insemnat 15px de nimic in fiecare saptamana cu
       o iesire). Un `display: none` scris aici ar fi fost a doua sursa — si cu alt
       prag: blocul asta e la 620px, iar `ecran.telefon` la 768. Numele lucrarilor
       stau in agenda de dedesubt. */
    /* Grila ramane harta (unde esti, cat de plin e); numele lucrarilor stau jos. */
    .agenda { display: flex; }
    .ag-rand { min-height: var(--tap-min); }

    /* BANDA E DECOR LA ATINGERE. PE TELEFON PISTA SE CITESTE, NU SE MANIPULEAZA.
       Blocul asta se aplica de la 620px in jos — adica si pe fereastra INGUSTA
       DE DESKTOP, cu mouse, nu doar pe telefon. Distinctia conteaza, fiindca
       gesturile de manipulare (`apuca*`) ies din `seManipuleaza()`, care cere
       `!telefon && !grosier`: pe un ecran fara hover ele nu exista deloc, si
       nici nu trebuie sa existe (regula din CLAUDE.md).
       Ce ramane pe telefon: o atingere pe banda cheama `atingeZi` cu ziua de sub
       deget, adica exact ce ar fi facut celula. Banda nu e `pointer-events:
       none` tocmai ca atingerea sa nu cada in gol intre doua dungi de 12px.
       Manerele de capat se randeaza doar pe benzile de mai multe zile: pe una de
       o singura zi, doua manere de 9px ar manca o celula de 44px. */
    .banda:not(.lat) .maner { display: none; }

    /* Navigarea si butoanele barei: erau de 28px inaltime. */
    .ico { width: var(--tap-min); height: var(--tap-min); }
    .b-azi, .ics { height: var(--tap-min); padding: 0 14px; font-size: var(--font-small); }
    .nav { gap: var(--space-xs); flex: 1; }
    .titlu { flex: 1; min-width: 0; font-size: var(--font-small); }
    .bar { gap: var(--space-xs); }

    /* Actiunile din panoul zilei — „Da", „Mută pe azi", „Mută", „Scoate". Erau
       pastile de 22px, adica exact tipul de buton pe care il ratezi si apesi
       „Scoate" in loc de „Mută".
       `--tap-sheet` (48), nu `--tap-min` (44): panoul zilei sta jos pe ecran si
       se atinge cu degetul mare INTINS, nu cu varful. Regula era scrisa in
       tokenuri si folosita intr-un singur loc din tot frontendul. */
    .b { min-height: var(--tap-sheet); padding: 0 12px; font-size: var(--font-small); }
    .dec { gap: var(--space-xs); }
    .mut { flex-wrap: wrap; }
    .mut :global(.dp) { flex: 1 1 160px; }

    /* Randurile din „Proiecte fără perioadă" sunt acum butoane (alegi, apoi
       atingi ziua), deci trebuie sa aiba caseta unui buton. */
    .np { min-height: var(--tap-min); padding: 6px 8px; }
    .np-t { font-size: var(--font-small); }
    .rail { max-height: none; gap: 6px; }

    .sursa { min-height: var(--tap-min); }
    .it-t { min-height: var(--tap-min); }
  }
</style>
