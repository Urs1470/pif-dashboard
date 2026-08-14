<script module>
  import { monthStart as _monthStart, weekStart as _weekStart, todayISO as _todayISO } from '../lib/calendarDates.js'
  import { preia as _preia, dinCache as _dinCache, uita as _uita } from '../lib/cache.js'

  // FEREASTRA CERUTA DE LA SERVER, SCRISA O SINGURA DATA.
  //
  // O cer doua locuri: `load()`, cand esti deja pe pagina, si `pregateste()`,
  // cand routerul incalzeste ruta inainte s-o deschizi. Doua sabloane de URL
  // pentru acelasi raspuns s-ar desparti tacut la prima schimbare de fereastra
  // — preincarcarea ar aduce alte 49 de zile decat cere pagina, deci cache-ul
  // n-ar fi niciodata lovit si scheletul ar reveni fara ca nimic sa para stricat.
  const urlPentru = (ancora) => `/api/calendar?start=${_weekStart(_monthStart(ancora))}&zile=49`

  /** Adus de router INAINTE de schimbarea rutei (vezi `setPreincarcaRuta` din
   *  App): pana termini de apasat, raspunsul e in cache, iar pagina se monteaza
   *  cu grila plina. Ancora e aceeasi regula ca la montare — `?zi=` daca vine
   *  din Planificator, altfel luna curenta. */
  export function pregateste(_params, query) {
    const zi = query?.zi
    const ancora = zi && /^\d{4}-\d{2}-\d{2}$/.test(zi) ? zi : _todayISO()
    return _preia(urlPentru(ancora), { proaspat: 5000 })
  }
</script>

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
  import { onMount, onDestroy, tick } from 'svelte'
  import { fade, slide } from 'svelte/transition'
  import { ChevronLeft, ChevronRight, MapPin, Building2, Check, X, Undo2, ExternalLink, TriangleAlert, GripVertical, CalendarDays, CalendarX2, Download } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { navigate, router } from '../lib/router.svelte.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import { motion, motionDuration, alunecare, sosire, DUR_BASE, EASE } from '../lib/motion.svelte.js'
  // `PROJECT_STATUS_LABELS` a plecat cu C14: sertarul „fara perioada" contine prin
  // definitie doar proiecte active, iar de la v31 activ inseamna un singur status
  // — deci eticheta scria acelasi cuvant pe fiecare rand. Acolo scrie clientul.
  import { incepeTragere } from '../lib/tragere.js'
  import { aterizare } from '../lib/motion.svelte.js'
  import { ecran } from '../lib/ecran.svelte.js'
  import { cheieDeplasare, grupeazaDeplasari, seAting, rezolvaCiocniri } from '../lib/deplasari.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import {
    WEEKDAYS, buildGrid, monthStart, addMonths, addDays, weekStart,
    diffDays, isWeekend, monthLabel, dayLabel, shortDate, todayISO, parseISO,
  } from '../lib/calendarDates.js'

  let data = $state(null)
  let loading = $state(true)
  let error = $state(null)
  // Doar prima citire are voie sa ia ce stie cache-ul (vezi `load`).
  let primaCitire = true
  // `mod` a plecat (V9): comutatorul „Lună / 2 săpt." a fost sters in turul 6,
  // dar starea si toate ramurile lui au ramas — masinarie moarta, pe care o
  // citeai ca specificatie si o copiai. Calendarul e LUNA, peste tot.
  let anchor = $state(monthStart(todayISO()))
  // PAGINA SE DESCHIDE CU AZI SELECTAT SI CU SERTARUL DESCHIS — cerut explicit de
  // Ion (2026-08-09): „vizualizarea default cand deschid pagina vreau sa fie azi
  // selectat si proiecte fara perioade selectate, adica sa fie cele doua pe partea
  // dreapta".
  //
  // Asta RASTOARNA regula de dinainte („panoul face loc, nu acopera, deci la
  // incarcare nu e selectata nicio zi"), scrisa cand panoul costa latime pe care
  // grila n-o avea de dat: fara el ziua trecea de la 127 la 176px, adica pragul de
  // la care textul din bara se putea citi. Argumentul s-a stins intre timp — de la
  // C8 bara e plina, de 24px, cu numele scris pe ea, iar de la C3 celula are 100px
  // inaltime, deci lucrarea se citeste si pe coloana ingusta.
  //
  // Ce ramane adevarat: cu panoul deschis ziua e mai ingusta. E o alegere, nu o
  // scapare — pagina se deschide aratand raspunsul la „ce am azi" si „ce n-am pus
  // inca pe calendar", care sunt exact intrebarile cu care intri pe ea.
  let selectata = $state(todayISO())
  // Sursa „Proiecte fara perioada", urcata din panou in capul paginii. Deschisa
  // din start, ca sa stea langa ziua de azi in coloana din dreapta.
  let deschideNeplanificate = $state(true)
  // FOAIA ZILEI (telefon) E SEPARATA DE SELECTIE, si trebuie sa fie.
  // Pe desktop „ziua selectata" si „panoul deschis" sunt acelasi lucru: panoul e o
  // coloana care sta langa grila. Pe telefon panoul e o FOAIE cu voal, care acopera
  // pagina — iar ziua de azi e selectata din start (cerinta lui Ion). Daca foaia
  // s-ar lega direct de `selectata`, Calendarul s-ar deschide pe telefon cu o foaie
  // peste grila, de fiecare data, fara s-o fi cerut nimeni. Deci: ziua ramane
  // insemnata in grila, iar foaia se ridica doar cand chiar atingi o zi.
  let foaieZi = $state(false)
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

  /** Perioada s-a incheiat inainte de azi. Se uita la ULTIMA zi (`data_sfarsit`,
   *  cu `data_start` ca rezerva pentru perioadele de o zi) — o perioada in curs
   *  nu se bifeaza, fiindca inca nu se stie daca s-a facut. */
  const aTrecut = (p) => (p.data_sfarsit || p.data_start) < azi

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
    //
    // SI NICI LA REVENIREA PE TAB. Pana acum `data` traia in componenta, iar
    // routerul o distruge la fiecare navigare — deci reveneai pe Calendar si
    // primeai iar scheletul de 360px, desi vazusesi grila acum treizeci de
    // secunde. `dinCache` o intoarce SINCRON, inainte de primul cadru.
    //
    // Se seedeaza doar LA MONTARE (`primaCitire`). Dupa o scriere — muti o
    // perioada, o stergi, bifezi „s-a facut" — `load()` se cheama din nou, iar
    // acolo cache-ul e starea DINAINTE de scriere: ar clipi inapoi la vechi
    // pentru cateva cadre, adica exact opusul confirmarii pe care o astepti.
    const url = urlPentru(anchor)
    let dinMemorie = false
    if (primaCitire) {
      primaCitire = false
      const gata = _dinCache(url)
      if (gata !== undefined) { data = gata; dinMemorie = true }
    } else {
      // Orice reincarcare de dupa montare vine ori dintr-o scriere, ori dintr-o
      // schimbare de luna. In primul caz lunile VECINE pot fi deja gresite — o
      // perioada mutata peste granita de luna nu apare in raspunsul lunii pe
      // care o ceri acum — si nimic nu le-ar corecta pana la o reincarcare de
      // pagina. In al doilea caz stergerea nu costa nimic.
      _uita('/api/calendar')
    }
    if (!silent && !dinMemorie) { loading = data === null; error = null }
    try {
      data = await _preia(url)
    } catch (e) {
      // Cand ecranul e deja plin din cache, o improspatare picata NU are voie
      // sa-l inlocuiasca cu o stare de eroare: ai in fata date bune, doar putin
      // vechi. Eroarea se arata cand n-avem ce arata.
      if (!silent && !dinMemorie) error = e.message
    } finally {
      if (!silent) loading = false
    }
  }

  const grila = $derived(buildGrid(anchor))

  // zi ISO -> perioadele care o acopera
  const peZi = $derived.by(() => {
    const m = new Map()
    for (const p of perioade) {
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
  // PERIOADELE SCOASE, DAR INCA NECOMISE (vezi `scoate`). Cat timp toastul de
  // „Anulează" e pe ecran, perioada e deja plecata din interfata si inca
  // intreaga in baza — deci se filtreaza AICI, o singura data, si nu la fiecare
  // dintre cele sase locuri care citesc lista.
  let scoaseTemporar = $state(new Set())
  const perioade = $derived((data?.perioade || []).filter(p => !scoaseTemporar.has(p.id)))

  const deplasari = $derived(grupeazaDeplasari(perioade))

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
    for (const p of perioade) {
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
    for (const p of perioade) {
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

  /** ETICHETA SCRIE INTOTDEAUNA LOCUL (C11) — si asta RASTOARNA regula de dinainte.
   *
   *  Varianta veche arunca clientul „cand e cel obisnuit al ferestrei": din 12
   *  perioade ale anului 11 sunt la Continental, deci numele lui nu selecta nimic
   *  si captura scria doar durata. Rationamentul era bun cat timp eticheta era un
   *  chip mic lipit de cifra zilei, intr-o grila unde culoarea inca purta
   *  identitatea proiectului.
   *
   *  Doua lucruri s-au schimbat de atunci si il anuleaza. Culoarea nu mai codeaza
   *  identitatea nicaieri in Calendar (`culoareLucrare` intoarce accentul pentru
   *  orice lucrare), iar eticheta a intrat INAUNTRUL cutiei ieșirii, pe primul ei
   *  rand — deci e singurul loc care mai poate spune UNDE te duci. Fara client,
   *  cutia scria „3 zile" si atat: o iesire fara destinatie.
   *
   *  Ce ramane adevarat din vechea observatie: `scurt()` ia primul cuvant, deci doi
   *  clienti cu acelasi prim cuvant se scriu la fel. Numele complet e in `title` si
   *  in panoul zilei. */
  /* In doua bucati, fiindca in eticheta vizibila se randeaza SEPARAT (C11):
     locul la 12/600, durata in mono, greutate normala. `textCaptura` le lipeste
     pentru title si aria-label, unde tipografia nu exista. */
  function etLoc(d) {
    const c = (d.client || '').trim()
    return c ? scurt(c) : 'Sediu'
  }
  function etZile(d) {
    const z = Math.max(0, diffDays(d.start, d.end)) + 1
    return `${z} ${z === 1 ? 'zi' : 'zile'}`
  }
  function textCaptura(d) {
    return `${etLoc(d)} · ${etZile(d)}`
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
          // `culoare` a plecat odata cu fillul tentat al randului (M5): randurile nu
          // mai sunt carduri colorate, iar `culoareLucrare` intoarce oricum accentul
          // pentru orice lucrare de cand identitatea nu se mai codeaza cromatic.
          necesitaDecizie: lucrari.some(p => p.necesita_decizie),
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

  /** A DISPARUT DIN CALENDAR? Spune de ce, si cum se intoarce.
   *
   *  Un proiect inchis se opreste in ziua inchiderii (v35), deci `/api/calendar`
   *  nu mai intoarce deloc o perioada mutata dincolo de `data_finalizare`.
   *  Mutarea a reusit — banda doar nu mai are unde sa fie desenata. Fara
   *  atentionarea asta, singurul lucru pe care il vezi e ca lucrarea s-a
   *  evaporat sub deget.
   *
   *  Se cheama DUPA `load(true)`; `perioade` e deja lista proaspata. */
  function avertizeazaDacaADisparut(p, undo) {
    if (perioade.some(x => String(x.id) === String(p.id))) return false
    toastUndo(`„${scurt(p.nume)}" nu se mai vede: proiectul e închis mai devreme de ziua asta`,
              { onUndo: undo })
    return true
  }

  /** Muta perioada pastrand durata. Folosit si de drop, si de butoane. */
  async function muta(p, ziNoua) {
    if (!ziNoua) return
    const durata = Math.max(0, diffDays(p.data_start, p.data_sfarsit || p.data_start))
    busy = p.id
    // ATERIZARE (T9): pozitia benzii vine din `grid-column`, care nu se poate
    // anima — deci dupa commit banda aparea DIRECT pe ziua noua, in timp ce
    // chenarul deplasarii (care are `transition`) aluneca. Se masoara inainte,
    // se animeaza diferenta dupa re-randare.
    const el = document.querySelector(`.banda[data-perioada="${p.id}"]`)
    const dinainte = el?.getBoundingClientRect()
    try {
      await apiJson(`/api/implementari/${p.id}`, {
        method: 'PUT',
        body: { data_start: ziNoua, data_sfarsit: addDays(ziNoua, durata) },
      })
      const inapoi = { start: p.data_start, sfarsit: p.data_sfarsit || p.data_start }
      selectata = ziNoua
      await load(true)
      const revino = async () => {
        await apiJson(`/api/implementari/${p.id}`, {
          method: 'PUT',
          body: { data_start: inapoi.start, data_sfarsit: inapoi.sfarsit },
        })
        selectata = inapoi.start
        await load(true)
      }
      if (!avertizeazaDacaADisparut(p, revino)) {
        toast(`Mutat pe ${shortDate(ziNoua)}`, 'success')
      }
      await tick()
      aterizare(document.querySelector(`.banda[data-perioada="${p.id}"]`), dinainte)
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

  /** Scoate perioada din calendar, CU DRUM INAPOI.
   *
   *  Comentariul de dinainte spunea ca proiectul reapare in „Proiecte fara
   *  perioada", deci exista cale de intoarcere. Se intoarce insa PROIECTUL, nu
   *  perioada: eticheta lucrarii, locatia, faza, bifa „Făcut" si intervalul
   *  exact se pierdeau si trebuiau retastate din memorie. Iar tragerea aceleiasi
   *  benzi — o schimbare mult mai mica — avea de mult „Anulează".
   *
   *  Stergerea e AMANATA (semantica lui `toastUndo`): perioada pleaca din
   *  interfata acum, din baza abia cand expira toastul. Nu prin re-creare:
   *  `POST /implementari` nu primeste `confirmata`, deci un undo care
   *  re-creeaza ar pierde bifa in tacere. */
  async function scoate(p) {
    scoaseTemporar = new Set([...scoaseTemporar, p.id])
    toastUndo(`„${p.nume}" — scos din calendar`, {
      onUndo: () => {
        const s = new Set(scoaseTemporar); s.delete(p.id); scoaseTemporar = s
      },
      onCommit: async () => {
        try {
          await apiJson(`/api/implementari/${p.id}`, { method: 'DELETE' })
          await load(true)
        } catch (e) {
          toast(`Eroare: ${e.message}`, 'error')
        } finally {
          const s = new Set(scoaseTemporar); s.delete(p.id); scoaseTemporar = s
        }
      },
    })
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
    // GARDA DE LATIME A PLECAT (T8). Ea oprea gestul pe orice ecran fara hover —
    // deci pe telefon perioadele nu se puteau muta deloc, si nici pe un laptop
    // cu ecran tactil. Ce tine locul afordantei de hover e apasarea lunga din
    // `incepeTragere`: 300ms fara miscare pornesc gestul, 10px il anuleaza (deci
    // derularea castiga), iar cand chiar a inceput banda se RIDICA si isi arata
    // manerele de 44px. Semnalul vine dupa intentie, nu inaintea ei — singurul
    // fel in care poate veni pe un ecran fara cursor.
    return true
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
    return perioade.find(p => p.id === id) || null
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
    // Atingerea unei zile RIDICA foaia — pe telefon asta e panoul. La incarcare nu
    // se ridica singura (vezi `foaieZi`), dar aici gestul e explicit.
    if (ecran.telefon) foaieZi = true
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
  /* TITLUL STA IN PAGINA, ca pe /projects, /tasks si /plan — nu in bara
     aplicatiei (raportat de Ion: „titlurile paginilor sunt neuniforme, undeva
     mai sus, undeva mai jos, undeva sus pe mijloc"). `ui.pageHeader` era exact
     acel „sus pe mijloc": traia in Header, la alta inaltime decat titlurile
     scrise in pagina, si pe telefon disparea cu totul (`.header-context` e
     `display: none` sub 768). Luna ramane SUBTITLU (C1), doar ca acum sta unde
     stau toate subtitlurile — langa h1. */
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

    <!-- CAPUL PAGINII: titlul + luna la stanga (aceeasi pozitie ca pe /projects,
         /tasks, /plan), apoi sursele si navigatia la dreapta (C2).
         Sursele stau INAINTEA navigatiei in DOM, nu mutate cu `order`: altfel
         tabularea ar merge invers decat se citeste. Separatorul de 24px spune ca
         sunt doua feluri de butoane — surse (de unde iei lucru) vs navigatie
         (cum te muti prin timp). `.bar-cap` de telefon a plecat: titlul din
         pagina exista acum pe orice latime, deci nu mai are ce dubla. -->
    <div class="page-header">
      <div class="page-title-row">
        <h1>Calendar</h1>
        <span class="page-sub">{monthLabel(anchor)}</span>
      </div>
    <div class="bar">
      <div class="surse cell-in" style="--celula: 0">
        {#if data.neplanificate?.length}
          <!-- Comuta DOAR sertarul. Golea si ziua selectata, ca sa nu stea doua
               panouri in aceeasi coloana — dar de cand pagina se deschide cu
               amandoua (cerinta lui Ion), asta ar inchide exact ce trebuie sa
               ramana. Coloana le tine pe amandoua, una sub alta. -->
          <button class="sursa" onclick={() => { deschideNeplanificate = !deschideNeplanificate }}
                  aria-expanded={deschideNeplanificate}
                  title="Proiecte active fără nicio zi planificată de azi înainte (pot avea perioade trecute)">
            <CalendarX2 size={14} strokeWidth={1.5} />
            <span class="s-n">{data.neplanificate.length}</span> de planificat
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
      <div class="nav">
        <button class="ico" onclick={() => pas(-1)} aria-label="Înapoi"><ChevronLeft size={16} /></button>
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
    </div>

    <!-- RANDUL DE KPI A PLECAT. „Zile pe teren", „deplasări", „zile la sediu"
         sunt statistici: le citeai, dadeai din cap si mergeai mai departe —
         niciuna nu decidea o actiune, iar toate trei se pot NUMARA uitandu-te la
         grila de dedesubt, care le si arata UNDE sunt.
         Cele doua care raman — plus „Proiecte fara perioada" — au urcat in bara
         (C2); vezi comentariul de acolo. -->

    <div class="wrap" class:cu-panou={panouDeschis}>
      <div class="cal cell-in" style="--celula: 1">
        <div class="wd">
          <!-- Doua scrieri ale aceleiasi zile, comutate din CSS (M7): pe telefon
               coloana are ~50px, iar „Sâ"/„Du" plus separatoarele fac antetul mai
               inghesuit decat grila de sub el. Initiala vine din `w[0]`, nu dintr-o
               a doua lista scrisa de mana — `WEEKDAYS` ramane singura sursa, si
               iese exact L M M J V S D. -->
          {#each WEEKDAYS as w}<span><i class="wd-lung">{w}</i><i class="wd-scurt">{w[0]}</i></span>{/each}
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
              <!-- TRIUNGHIUL DIN COLT A PLECAT (C10). „De clarificat" e o stare a
                   IESIRII, nu a zilei: un semn de 11px in coltul celulei o punea
                   pe zi, desi ce trebuie clarificat e deplasarea intreaga. Acum o
                   poarta cutia ei — tenta si inelul in restant, triunghiul in
                   eticheta, barele pline `--danger` — deci se vede pe toate zilele
                   ei deodata si nu mai concureaza cu cifra zilei pentru acelasi colt. -->

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
            {@const cDecizie = [...c.d.items.values()].some(p => p.necesita_decizie)}
            <div class="chenar"
                 class:inceput={c.inceput}
                 class:sfarsit={c.sfarsit}
                 class:sediu={c.d.sediu}
                 class:decizie={cDecizie}
                 style="grid-row: {c.rand}; grid-column: {c.col} / span {c.span}; --i: {c.banda}; --n: {c.inalt}">
              <!-- ETICHETA STA IN CHENARUL EI, pe primul lui rand. Era un chip
                   lipit de cifra zilei, in antet — deci numele iesirii statea in
                   AFARA obiectului pe care il numeste, iar „asta e o iesire de 3
                   zile, cu lucrarile astea" se citea din doua locuri.
                   Doar pe felia de INCEPUT: la granita de saptamana chenarul se
                   taie, iar a doua bucata nu incepe nimic — ar scrie a doua oara
                   durata intregii iesiri, ca si cum ar reincepe. -->
              {#if c.inceput && c.areEticheta}
                <button class="chenar-et" class:sediu={c.d.sediu} class:decizie={cDecizie}
                        class:se-trage={trag?.tip === 'deplasare' && trag.cheie === c.d.cheie}
                        onpointerdown={(e) => apucaDeplasare(e, c.d)}
                        onclick={(e) => e.stopPropagation()}
                        title={etichetaDeplasare(c.d)}
                        aria-label="Deplasare {c.d.client || 'la sediu'} — {textCaptura(c.d)}. Trage ca să muți toată ieșirea.">
                  {#if cDecizie}<TriangleAlert size={12} />{:else if c.d.sediu}<Building2 size={12} />{:else}<MapPin size={12} />{/if}{etLoc(c.d)}<span class="et-zile">&nbsp;· {etZile(c.d)}</span>
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
              class:facuta={!!b.p.confirmata}
              class:decizie={!!b.p.necesita_decizie}
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
              <!-- ICONITA LOCULUI, DOAR PE TELEFON (M1). Acolo banda isi poarta
                   singura starea — chenarul iesirii nu se deseneaza (M6) — deci
                   „Site sau sediu" n-are de unde sa se citeasca altfel. Pe desktop
                   o spune eticheta chenarului, si aici ar fi a doua oara. -->
              <span class="banda-ico" aria-hidden="true">
                {#if b.p.locatie === 'sediu'}<Building2 size={10} />{:else}<MapPin size={10} />{/if}
              </span>
              <!-- Bifa sta INAINTEA numelui, ca pe randul de task: „s-a facut" e o
                   stare a lucrarii, deci se citeste odata cu ea, nu dupa. -->
              {#if b.p.confirmata}<Check size={12} class="banda-bifa" />{/if}
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
        <!-- Agenda iesirilor a IESIT din cardul grilei (M5) — sta mai jos, pe
             fundalul paginii. Aici era inauntru, iar de la C7 cardul are
             `padding: 0` si `overflow: hidden`: randurile ei ar fi atins muchiile
             si le-ar fi taiat colturile. -->
      </div>

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
        <!-- ACELASI CONTINUT, DOUA GAZDE (M9): coloana laterala pe desktop, foaie
             de jos pe telefon. Declarat ca snippet ca sa NU existe doua copii care
             se despart la a treia modificare — regula e deja in `Modal.svelte`
             („un detaliu, o componenta"), aici e doar aplicata mai sus.
             Titlul zilei ramane in snippet pe desktop; pe telefon il scrie foaia,
             prin `title`, ca sa stea pe mânerul ei. -->
        {#snippet panouZi(cuTitlu)}
        {#key selectata}
        <div class="pan" class:in-foaie={!cuTitlu} in:sosire|local>
          <!-- Titlul zilei se scrie la 21/600 in AMBELE gazde (M9): in foaie,
               linia mica de pe manerul Modalului se ascunde (vezi regula
               `:has(.pan.in-foaie)` de mai jos) — acelasi tipar ca N2-N5. -->
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
                <!-- TITLUL IA RANDUL INTREG; actiunile coboara pe randul lor
                     (Ion, 2026-08-10: „muta butoanele pe un rand nou ca sa
                     incapa titlul cum trebuie"). Desenul (C13) le punea pe linia
                     titlului, dar acolo trei actiuni-text luau ~180px dintr-o
                     coloana de 330, iar numele proiectelor („Upgrade Motoare
                     Extruder TDE FML + PIF — Continental") se taia dupa trei
                     cuvinte. Numele e lucrul dupa care recunosti randul; el
                     castiga latimea.
                     In foaie (telefon) actiunile raman randuri de 48px, mai jos. -->
                <div class="it-cap">
                  <button class="it-t" onclick={() => navigate(`/projects/${p.proiect_id}`)}>
                    {p.nume}<ExternalLink size={12} />
                  </button>
                </div>
                <!-- Eticheta lucrarii („Contrapanou A12 (montaj)") pe randul ei:
                     e text, nu chip, si e singurul lucru care spune CE faci. -->
                {#if p.eticheta}<div class="it-et">{p.eticheta}</div>{/if}
                <!-- CELE TREI CHIPURI PE UN RAND, TOATE LA FEL (Ion, 2026-08-10).
                     „niciun task" purta pana acum alta haina (fond de restant,
                     inaltime proprie) si statea lipit de data — deci trei fapte
                     despre aceeasi perioada aratau ca trei feluri de lucruri.
                     Acum au aceeasi cutie; ce le deosebeste ramane doar TONUL:
                     locul si faza sunt neutre/accent, lipsa taskurilor e rosie.
                     Bifa „Făcut" intra in acelasi rand — e tot despre perioada. -->
                <div class="it-chips">
                  <span class="loc" title="Unde ești în ziua asta">{p.locatie === 'sediu' ? 'Sediu' : 'Site'}</span>
                  <span class="loc faza" class:pal={p.faza === 'pregatire'} title="Faza acestei perioade">{p.faza === 'pregatire' ? 'Pregătire' : 'Implementare'}</span>
                  <span class="loc tk" class:warn={!p.taskuri_deschise}
                        title={p.taskuri_deschise ? 'Taskuri deschise pe proiect' : 'Perioada n-are niciun task deschis'}>
                    {#if !p.taskuri_deschise}<TriangleAlert size={11} />{/if}{p.taskuri_deschise ? `${p.taskuri_deschise} ${p.taskuri_deschise === 1 ? 'task' : 'taskuri'}` : 'niciun task'}
                  </span>
                </div>
                <!-- RANDUL 4: cele trei ACTIUNI, mereu la vedere (vezi nota din
                     CSS). Doar pe desktop: in foaia de telefon ele sunt randuri
                     de 48px, mai jos. -->
                {#if cuTitlu}
                  <div class="it-act">
                    {#if p.confirmata}
                      <button class="ia" disabled={busy === p.id} onclick={() => confirma(p, 0)}
                              title="Răspunsul opus la „S-a făcut?” — nu scoate perioada."><X size={13} /> Nu s-a făcut</button>
                    {:else if aTrecut(p)}
                      <!-- Vezi nota din foaie: bifa ramane la indemana si cand
                           intrebarea tace (proiect inchis). -->
                      <button class="ia" disabled={busy === p.id} onclick={() => confirma(p, 1)}
                              title="Bifează perioada ca făcută. Statusul proiectului nu se schimbă."><Check size={13} /> Făcut</button>
                    {/if}
                    <button class="ia" disabled={busy === p.id}
                            onclick={() => { mutaId = mutaId === p.id ? '' : p.id; mutaVal = '' }}>
                      <CalendarDays size={13} /> Mută
                    </button>
                    <button class="ia del" disabled={busy === p.id} onclick={() => scoate(p)}
                            title="Scoate perioada din calendar — proiectul se întoarce în „De planificat”">
                      <Undo2 size={13} /> Scoate
                    </button>
                  </div>
                {/if}
                <!-- RANDUL 5: STAREA la stanga, DATA la dreapta (Ion).
                     „Făcut" de aici e o STARE, nu butonul de deasupra: unul spune
                     ce s-a intamplat, celalalt il schimba. De aceea nu mai stau
                     in acelasi rand — doua obiecte cu acelasi cuvant, lipite, se
                     citeau ca unul singur. -->
                <div class="it-jos">
                  {#if p.confirmata}
                    <span class="loc fac" title="Perioada s-a făcut. Statusul proiectului nu s-a schimbat."><Check size={11} /> Făcut</span>
                  {/if}
                  <span class="it-data">{shortDate(p.data_start)}{p.data_sfarsit && p.data_sfarsit !== p.data_start ? ` – ${shortDate(p.data_sfarsit)}` : ''}</span>
                </div>
                {#if p.necesita_decizie}
                  <!-- E O INTREBARE, NU O NOTA (M10). Statea ca o linie rosie cu
                       doua pastile de 22px langa ea — se citea ca un avertisment
                       pe care il inchizi, nu ca ceva ce trebuie sa raspunzi.
                       Acum e un bloc cu tenta si inel, cu intrebarea la 15/600 si
                       doua raspunsuri de 48px: „Da, s-a facut" plin, fiindca e
                       raspunsul asteptat, si „Muta pe azi" pe suprafata. -->
                  <div class="dec intrebare">
                    <span class="dec-q"><TriangleAlert size={13} /> A trecut. S-a făcut?</span>
                    <button class="b ok" disabled={busy === p.id} onclick={() => confirma(p, 1)}
                            title="Bifează perioada ca făcută. Proiectul NU se închide — asta se face din pagina proiectului.">
                      <Check size={14} /> Da, s-a făcut
                    </button>
                    <button class="b" disabled={busy === p.id} onclick={() => muta(p, azi)}><Undo2 size={14} /> Mută pe azi</button>
                  </div>
                {/if}
                {#if !cuTitlu}
                  <!-- IN FOAIE actiunile rare sunt RANDURI de 48px cu chevron (M9)
                       — pe deget, un sir de pastile de 22px era exact tinta pe
                       care o ratezi. „Nu s-a făcut" ramane primul: e raspunsul
                       opus la aceeasi intrebare (v39), nu o actiune de rand. -->
                  <div class="f-act">
                    {#if p.confirmata}
                      <button class="fa-r" disabled={busy === p.id} onclick={() => confirma(p, 0)}>
                        <X size={15} /> <span class="fa-c"><span>Nu s-a făcut</span></span> <ChevronRight size={15} class="fa-chev" />
                      </button>
                    {:else if aTrecut(p)}
                      <!-- BIFA EXISTA SI CAND NIMENI NU MAI INTREABA (Ion, pentru
                           perioadele TDE din 29-30 iulie). `necesita_decizie` tace
                           pe un proiect INCHIS — corect, ca sa nu bata la usa
                           pentru o lucrare terminata — dar pana acum tacerea lua
                           si singurul drum de a bifa perioada. Deci: intrebarea
                           ramane doar unde e cazul, bifa e mereu la indemana. -->
                      <button class="fa-r" disabled={busy === p.id} onclick={() => confirma(p, 1)}>
                        <Check size={15} /> <span class="fa-c"><span>Marchează ca făcut</span><span class="fa-hint">statusul proiectului nu se schimbă</span></span> <ChevronRight size={15} class="fa-chev" />
                      </button>
                    {/if}
                    <button class="fa-r" disabled={busy === p.id}
                            onclick={() => { mutaId = mutaId === p.id ? '' : p.id; mutaVal = '' }}>
                      <CalendarDays size={15} /> <span class="fa-c"><span>Mută pe altă zi</span></span> <ChevronRight size={15} class="fa-chev" />
                    </button>
                    {#if mutaId === p.id}
                      <div class="mut" in:fade={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
                        <DatePicker bind:value={mutaVal} />
                        <button class="b ok" disabled={!mutaVal || busy === p.id}
                                onclick={() => { muta(p, mutaVal); mutaId = ''; mutaVal = '' }}>Mută</button>
                      </div>
                    {/if}
                    <button class="fa-r" disabled={busy === p.id} onclick={() => scoate(p)}>
                      <Undo2 size={15} /> <span class="fa-c"><span>Scoate din calendar</span><span class="fa-hint">se întoarce în „fără perioadă”</span></span> <ChevronRight size={15} class="fa-chev" />
                    </button>
                  </div>
                {:else if mutaId === p.id}
                  <div class="mut" in:fade={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
                    <DatePicker bind:value={mutaVal} />
                    <button class="b ok" disabled={!mutaVal || busy === p.id}
                            onclick={() => { muta(p, mutaVal); mutaId = ''; mutaVal = '' }}>Mută</button>
                  </div>
                {/if}
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
        {/snippet}

        <!-- SNIPPET-UL SE DECLARA IN AFARA LUI `{#if panouDeschis}`, si asta nu e
             stil: un snippet e vizibil DOAR in blocul in care e declarat. Cat timp
             statea inauntrul lui `<aside>`, foaia de mai jos — care e frate cu
             aside-ul — crapa cu `ReferenceError: panouZi is not defined`, iar
             Modalul nu se mai randa deloc. -->
      {#if panouDeschis}
      <aside class="side cell-in" style="--celula: 2">
        <!-- Pe desktop panoul zilei sta in coloana. Pe telefon il ia foaia de mai
             jos, deci aici nu se randeaza — altfel ar fi si in pagina, si in foaie. -->
        {#if !ecran.telefon}{@render panouZi(true)}{/if}

        {#if deschideNeplanificate && data.neplanificate?.length}
          <!-- Sertarul se DESFACE, nu apare (fluenta comutarilor, Ion
               2026-08-10): slide pe --dur-base, ca orice panou care isi face
               loc. `|local`, ca la navigarea intre rute sa nu se mai joace. -->
          <div class="pan" transition:slide|local={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
            <!-- „DE PLANIFICAT", nu „fara perioada" (Ion, 2026-08-10: „de ce la
                 apex imi apare ca proiect fara perioada daca acolo a fost
                 implementat deja si e aratat pe calendar?").
                 Lista era corecta, NUMELE mintea: interogarea intoarce proiectele
                 active fara nicio zi DE AZI INAINTE (`neplanificate` in
                 admin.py) — un proiect caruia i s-a facut deplasarea, dar care
                 ramane deschis pentru PV-uri sau o vizita nedatata, chiar n-are
                 nimic planificat inainte si TREBUIE sa stea aici (e chiar
                 scenariul v39). Dar el ARE perioade, in trecut, si se vad in
                 grila — de unde contradictia.
                 Numele spune acum ce face sertarul: sursa din care iei lucru si
                 il pui pe o zi. Sertarul din Planificator tine ALTCEVA (taskuri
                 fara termen), deci numele raman diferite. -->
            <div class="pan-h">De planificat <span class="cnt">{data.neplanificate.length}</span></div>
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
                  <GripVertical size={14} />
                  <!-- CLIENTUL, NU STATUSUL (C14). Lista asta contine, prin
                       definitie, doar proiecte ACTIVE (`status NOT IN
                       ('finalizat','anulat')`) — iar de la v31 activ inseamna un
                       singur status. Deci eticheta scria „În pregătire" pe fiecare
                       rand: o coloana intreaga cu aceeasi valoare. Clientul spune
                       de fapt care proiect e care.
                       Punctul de identitate a plecat din acelasi motiv ca in lista
                       zilei: `--c` e accentul pe toate randurile. -->
                  <span class="np-c">
                    <span class="np-t">{pr.nume}</span>
                    {#if pr.client}<span class="np-s">{pr.client}</span>{/if}
                  </span>
                  {#if asezare?.proiect_id === pr.proiect_id}
                    <span class="np-hint">Atinge ziua</span>
                  {/if}
                </button>
              {/each}
            </div>
          </div>
        {/if}
      </aside>
      {/if}

      <!-- FOAIA ZILEI, PE TELEFON (M9). `Modal` e deja „panou lateral pe desktop,
           foaie de jos pe telefon" — voal, raza pe colturile de sus, mâner, blocarea
           derularii si tragerea in jos. Scrisa de mana aici, ar fi fost a doua
           implementare a aceluiasi lucru, cu alt comportament la Escape si la focus.
           `title` duce data zilei pe mânerul foii, deci `panouZi(false)` n-o mai
           scrie inca o data inauntru. -->
      {#if ecran.telefon}
        <!-- `inalt`: foaia zilei se deschide direct aproape pe tot ecranul
             (Ion, 2026-08-10) — detaliile unei zile nu incap intr-o jumatate
             de foaie, iar intinderea manuala era un gest in plus de fiecare
             data. -->
        <Modal open={foaieZi} inalt title={dayLabel(selectata)} onclose={() => foaieZi = false}>
          {@render panouZi(false)}
        </Modal>
      {/if}

      <!-- IESIRILE FERESTREI, SCRISE. Doar pe telefon: acolo grila e o harta de
           dungi cu nume scurte (vezi `agendaLunii`), iar aici scrie cine, cand si
           ce lucrari — in ordinea zilelor.
           Sta ULTIMA in `.wrap`, dupa panou: pe o coloana ordinea trebuie sa fie
           harta -> ziua pe care tocmai ai atins-o -> restul lunii. Intre grila si
           panou ar fi impins raspunsul in afara ecranului, exact ce repara ordinea
           de la 900px. -->
      {#if agendaLunii.length}
        <div class="agenda">
          <div class="ag-cap">
            <span>Ieșirile lunii</span>
            <span class="ag-linie"></span>
            <span class="ag-n">{agendaLunii.length}</span>
          </div>
          {#each agendaLunii as d (d.cheie + '|' + d.start)}
            <button class="ag-rand" class:aprins={esteAprinsa(d)}
                    class:rau={d.necesitaDecizie}
                    onclick={() => atingeZi(d.start)}>
              <span class="ag-sus">
                <span class="ag-ico">{#if d.sediu}<Building2 size={11} />{:else}<MapPin size={11} />{/if}</span>
                <span class="ag-titlu">{d.titlu}</span>
                <span class="ag-cand">{d.cand}</span>
              </span>
              <!-- A doua linie SCRIE starea, nu doar o coloreaza (desen 6c):
                   bifa verde pe ce s-a facut, „· pregătire" pe ce nu e inca in
                   site, iar pe iesirea care asteapta raspuns — chiar intrebarea. -->
              <span class="ag-lucrari">
                {#each d.lucrari as p (p.id)}
                  <span class="ag-l" class:pregatire={p.faza === 'pregatire'} class:facuta={p.confirmata}>
                    {#if p.confirmata}<Check size={11} strokeWidth={2.4} />{/if}{etichetaLucrare(p)}{#if p.faza === 'pregatire'}<span class="ag-faza">&nbsp;· pregătire</span>{/if}
                  </span>
                {/each}
                {#if d.necesitaDecizie}<span class="ag-intrebare">· a trecut, s-a făcut?</span>{/if}
              </span>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .page { padding: var(--space-lg); }

  /* ACEEASI POZITIE DE TITLU CA /projects, /tasks, /plan (raportat de Ion:
     titlurile stateau la inaltimi diferite). Titlul la stanga, bara la dreapta,
     pe acelasi rand; sub 768 randul se rupe si bara coboara sub titlu. */
  /* `flex-start`, nu `center`: cu bara de 38px alaturi, centrarea cobora h1 cu
     ~6px fata de paginile fara controale in cap — exact neuniformitatea
     raportata de Ion. Titlul sta pe ACEEASI linie pe toate rutele. */
  .page-header { display: flex; align-items: flex-start; justify-content: space-between;
    gap: var(--space-sm); flex-wrap: wrap; margin-bottom: var(--space-md); }
  .page-title-row { display: flex; align-items: baseline; gap: var(--space-sm);
    color: var(--text); min-width: 0; }
  .page-title-row h1 { font-size: var(--font-title); font-weight: var(--fw-semibold); }
  .page-sub { font-size: var(--font-small); font-weight: var(--fw-medium);
    color: var(--text-secondary); white-space: nowrap; }
  .bar { display: flex; align-items: center; justify-content: flex-end; gap: var(--space-sm); flex-wrap: wrap; }
  /* Separatorul dintre surse si navigatie: 24px, cat inaltimea la care se citesc
     doua grupuri ca fiind despartite fara sa para doua bare. */
  .nav { display: flex; align-items: center; gap: 6px; }
  .wd-scurt { display: none; }
  .wd-lung { font-style: normal; }
  /* Iconita locului de pe banda: doar pe telefon (M1). */
  .banda-ico { display: none; }
  /* Separatorul e un `::before` de 24px, nu un `border-left`: bordura ar fi cat
     toata inaltimea randului (38px) si ar arata ca marginea unei bare, nu ca o
     cusatura intre doua grupuri.
     `:has(.surse > *)` il aprinde DOAR cand chiar exista surse — altfel, intr-o
     luna fara nimic de clarificat, ar ramane o liniuta care nu desparte nimic. */
  .bar:has(.surse > *) .nav::before {
    content: ''; width: 1px; height: 24px; margin-right: 2px;
    background: var(--border); flex: none; }
  /* `.titlu` a plecat cu C1 — luna se scrie in subtitlul paginii. */
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
  /* Fara `margin-bottom`: sursele stau ACUM in bara (C2), deci marja de sub ele ar
     impinge grila cu inca un rand de gol. */
  .surse { display: flex; gap: var(--space-sm); flex-wrap: wrap; }
  .sursa { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap;
    min-height: 38px; padding: 0 12px; border-radius: var(--radius-sm);
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
  /* 330px, nu 300: la 300 randul „Continental — Retrofit FML3" se rupea in doua
     sub titlul de 21px, iar chipurile de loc si faza treceau pe al treilea rand. */
  .wrap.cu-panou { grid-template-columns: minmax(0, 1fr) 330px; }

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
             font-size: var(--font-label); font-weight: var(--fw-semibold); color: var(--text-dim);
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
     invers. 31px = fundul cutiei ieșirii (28 + n×27, vezi `.chenar`) plus 3px de
     aer sub ea; cu 3 randuri de benzi randul face 112, cu 5 (MAX_BENZI) 166. */
  .zi { position: relative; min-height: max(100px, calc(31px + var(--benzi, 1) * 27px)); padding: 5px 8px 0;
        border: 0; background: none; text-align: left; cursor: pointer;
        box-shadow: inset -1px 0 0 var(--border), inset 0 -1px 0 var(--border-strong);
        display: flex; flex-direction: column; gap: 3px; overflow: hidden;
        transition: background-color var(--dur-fast) var(--ease); }
  .zi:hover { background: var(--bg-hover); }
  .zi:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  /* Ziua din alta luna: cifra trece pe `--text-dim`, nu toata celula pe 42%.
     Opacitatea inmulteste peste tokenuri deja la limita — si stingea si benzile,
     nu doar cifra, desi lucrarile din ele sunt la fel de reale. */
  .zi.alta .n { color: var(--text-dim); }
  /* Liniile sunt SEPARATOARE, deci nu au ce cauta pe marginea de afara: acolo n-au
     ce desparti, si impreuna ar desena inapoi chiar chenarul scos de R1 — doar cu
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
  /* Fara tracking de eticheta: „azi" e mono, iar mono cu litere rarite se citeste
     ca un cod. Desenul il are strans (11px; scara se opreste la 12). */
  .azi-et { font-family: var(--font-mono); font-size: var(--font-label); font-weight: var(--fw-semibold);
            color: var(--accent-deep); }
  /* `.flag` a plecat cu C10 — „de clarificat" e acum starea cutiei ieșirii, nu un
     colt al zilei. Motivul e scris in markup, langa cifra. */

  /* O LUCRARE = O BANDA, oricat de multe zile ar tine. Se intinde peste coloane,
     acopera si spatiile dintre ele, deci numele se scrie o data si are toata
     latimea lucrarii la dispozitie.
     `--i` e banda (randul) lucrarii. Decalajul de sus trebuie sa fie EXACT cel al
     zonei de bare din celula, altfel benzile plutesc pe langa celule.
     Geometria vine din desen (C10): cutia ieșirii incepe la 28 de la marginea de
     sus a celulei, are 5px de aer inauntru, eticheta 17, apoi 3 pana la prima
     bara — deci randul etichetei (randul 0 al blocului) porneste la
       28 − 2 = 26px  (cei 2px sunt aerul cutiei DEASUPRA randului 0)
     iar pasul unei benzi = inaltimea barei 24 + gap 3 = 27px. Numerele astea,
     cele din `.chenar` si cele din `min-height` al celulei se schimba IMPREUNA. */
  .grid { --h-antet: 26px; --h-banda: 27px; }

  /* CHENARUL IESIRII. Sta SUB benzi (`z-index: 0`) si nu primeste evenimente:
     lucrarile raman obiectele pe care le apuci, el doar spune ca fac parte din
     aceeasi deplasare. Inaltimea acopera exact benzile lui (`--n`), minus gapul de
     3px de sub ultima, ca sa nu inghita randul urmator.
     Raza NUMAI pe capetele adevarate: la alipire, cele doua muchii rotunjite din
     mijloc dispar de la sine — asta E „peretele se stinge". Tranzitia de 280ms e
     cea de SUPRAFATA (`--dur-slow`): chenarul e o suprafata care se lungeste, nu
     un element care se muta. */
  /* CUTIA CARE LE CONTINE, nu un strat lipit sub ele (C10).
     Se subtiase pana ajunsese o umbra in spatele barelor: incepea la 18 — adica
     SUB randul cifrei, care se termina la 20 — si ultima bara ii atingea muchia
     de jos (problema semnalata de Ion). Geometria din desen: cutia porneste la
     28 (8px de aer sub cifra zilei), 5px de aer inauntru pe toate laturile —
     eticheta la 33, prima bara la 53, gap 3 intre ele — si fundul la 5px sub
     ultima bara. Cu randul blocului la `--h-antet` = 26, asta inseamna:
       margin-top = 26 + i×27 + 2   (cutia incepe cu 2px sub randul 0)
       height     = n×27            (27n+28 jos − 28 sus, fix pe formula)
     `box-sizing: border-box`, ca cei 2px de bordura sa nu se adune la socoteala. */
  .chenar { position: relative; z-index: 0; align-self: start; pointer-events: none;
            box-sizing: border-box;
            margin-top: calc(var(--h-antet) + var(--i) * var(--h-banda) + 2px);
            height: calc(var(--n) * var(--h-banda));
            border: 1px solid color-mix(in srgb, var(--accent) 26%, transparent);
            border-left: none; border-right: none;
            background: color-mix(in srgb, var(--accent) 10%, transparent);
            transition: height var(--dur-slow) var(--ease), margin-top var(--dur-slow) var(--ease); }
  .chenar.inceput { margin-left: 3px; border-left: 1px solid color-mix(in srgb, var(--accent) 26%, transparent);
                    border-top-left-radius: var(--radius-sm); border-bottom-left-radius: var(--radius-sm); }
  .chenar.sfarsit { margin-right: 3px; border-right: 1px solid color-mix(in srgb, var(--accent) 26%, transparent);
                    border-top-right-radius: var(--radius-sm); border-bottom-right-radius: var(--radius-sm); }
  /* Sediul nu e deplasare: chenarul lui e doar o linie punctata, ca sa nu para ca
     ai plecat undeva. Locul RAMANE SCRIS (captura din antet) — asta e doar forma. */
  .chenar.sediu { border-style: dashed; background: none; }
  /* Cutia intreaga trece in restant cand ceva din ea asteapta un raspuns (C10). */
  .chenar.decizie { background: var(--danger-subtle);
                    border-color: color-mix(in srgb, var(--danger) 30%, transparent); }
  .chenar.decizie.inceput { border-left-color: color-mix(in srgb, var(--danger) 30%, transparent); }
  .chenar.decizie.sfarsit { border-right-color: color-mix(in srgb, var(--danger) 30%, transparent); }

  /* BARA E OBIECTUL CEL MAI CITIBIL DIN CELULA, NU UN FUNDAL (C8).
     Era o spalatura `color-mix(--c 26%)` de 17px cu text `--text` la 13: la
     latimea unei zile se citea ca o umbra sub cifra, iar numele lucrarii — singurul
     lucru care spune CE faci acolo — statea pe o tenta care il inghitea. Acum e
     plina cu accentul, la 24px, cu cerneala de pe fill (`--accent-text`) la 12/600.
     Raza `--radius-xs`, nu `--radius-sm`: bara e un chip, iar la 24px inaltime raza
     de 10 ar rotunji-o pana la pastila. */
  .banda { position: relative; z-index: 1; align-self: start;
           margin-top: calc(var(--h-antet) + var(--i) * var(--h-banda));
           min-height: 24px; display: flex; align-items: center;
           padding: 0 9px; border: none; text-align: left; border-radius: var(--radius-xs);
           cursor: grab; background: var(--c); }
  .banda:active { cursor: grabbing; }
  /* Capetele rotunjite spun unde INCEPE si unde se TERMINA lucrarea. La granita de
     saptamana capatul rămâne drept si iese peste marginea celulei: asa se citeste
     „continua", nu „s-a incheiat". */
  /* Inceputul se marcheaza prin FORMA, nu prin culoare: banda e deja plina cu
     `var(--c)`, deci dunga era aceeasi culoare peste ea insasi, doar mai tare.
     Raza de pe colturile din stanga spune acelasi lucru si nu adauga un al doilea
     cod de culoare. Cei 3px se intorc in padding. */
  /* Raza capetelor e `--radius-xs`, ca a barei: la 24px inaltime `--radius-sm` (10)
     o rotunjea pana aproape de pastila, iar bara e un chip, nu o pilula. */
  /* 8 = marginea cutiei (3) + aerul ei interior (5): capetele adevarate ale barei
     stau la 5px de peretele cutiei, cum cere desenul. */
  .banda.inceput { margin-left: 8px; padding-left: 8px;
                   border-top-left-radius: var(--radius-xs); border-bottom-left-radius: var(--radius-xs); }
  .banda.sfarsit { margin-right: 8px;
                   border-top-right-radius: var(--radius-xs); border-bottom-right-radius: var(--radius-xs); }
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
     ceva acolo.
     LINIA INCAPE IN BARA, nu o depaseste. Iesea 1px sus si 1px jos, iar zona de
     prindere inca 5px peste ea (`::before`): valorile erau alese cand banda avea
     17px si trebuia ingrosata ca sa poata fi apucata. De cand bara are 24px (C8)
     ea e ea insasi o tinta buna, iar linia care trece peste muchii nu mai citeste
     ca maner, ci ca o taietura prin bara. Acum sta la 4px de sus si de jos —
     inauntru, limpede — si zona de prindere se lateste doar pe orizontala. */
  .maner { position: absolute; top: 0; bottom: 0; width: 9px; cursor: ew-resize;
           opacity: 0; transition: opacity var(--dur-fast) var(--ease); }
  .maner.st { left: 0; }
  .maner.dr { right: 0; }
  .maner::before { content: ''; position: absolute; inset: 0 -2px; }
  /* CERNEALA DE PE FILL, NU ACCENTUL (raportat de Ion: „nu apar barele").
     Linia era `--accent` — pe vremea cand banda era o spalatura de 26%. De la C8
     banda e FILL PLIN de accent, deci linia era accent pe accent: exista, la
     opacitate 1, si nu se vedea deloc. Pe fill scrie `--accent-text`, ca textul. */
  .maner::after { content: ''; position: absolute; top: 4px; bottom: 4px; left: 50%; width: 2px;
                  transform: translateX(-50%); border-radius: 1px; background: var(--accent-text); }
  /* Starile care nu sunt fill de accent isi aleg cerneala potrivita: conturata
     (fond de suprafata) — accent; facuta (tenta verde) — verdele adanc; decizia
     (fill rosu) ramane pe cerneala de fill. */
  .banda.pregatire .maner::after { background: var(--accent); }
  .banda.facuta .maner::after { background: var(--success-deep); }
  .banda:hover .maner, .banda.se-trage .maner { opacity: 1; }
  /* PE TELEFON PISTA SE CITESTE, NU SE MANIPULEAZA.
     Manerele nu se ascund doar vizual — gestul insusi e oprit (vezi
     `incepeTragere` din `apuca*`). Un maner desenat fara gest in spate ar promite
     ceva ce nu se intampla, exact greseala pe care a facut-o versiunea cu
     drag-and-drop HTML5. */
  /* PE TELEFON MANERELE APAR DUPA CE GESTUL A INCEPUT (T8).
     Nu „in repaus": doua dungi permanente pe fiecare banda ar fi zgomot, si nici
     n-ar avea ce apuca degetul intr-o celula de ~48px. Dar odata ce apasarea
     lunga a prins — deci utilizatorul a CERUT gestul — manerele se arata la
     latime de deget, fiindca de acolo incolo intinderea e o actiune reala. */
  @media (hover: none) {
    .maner { opacity: 0; }
    .banda.se-trage .maner { opacity: 1; width: var(--tap-min); }
    .banda.se-trage .maner::after { width: 3px; }
  }
  /* FORMA SPUNE FAZA, LOCUL SE SCRIE.
     Hasura de „sediu" (`repeating-linear-gradient`) era a TREIA axa de citit pe
     acelasi obiect — ramasa din versiunea dinaintea redesenarii, desi comentariul
     de la `culoareLucrare` explica de ce culoarea de identitate a plecat. Locul
     il spun iconita (`building-2` / `map-pin`) si eticheta ieșirii („Sediu EGB ·
     3 zile"), adica un canal care se poate CITI. Ramane o singura diferenta de
     desen: plin = implementare, contur palid = pregatire. */
  /* Pregatirea ramane CONTURATA, dar pe suprafata (C9): fond `--bg-surface`, nu o
     tenta transparenta. Peste chenarul ieșirii — care e el insusi o tenta — o
     bara translucida se aduna cu fondul de dedesubt si iese o a treia culoare care
     nu e in sistem. Inelul de 1.5px o tine vizibila pe fond deschis fara sa para
     o bara plina stinsa. */
  .banda.pregatire { background: var(--bg-surface);
                     box-shadow: inset 0 0 0 1.5px var(--accent); }
  .banda.pregatire .banda-t { color: var(--accent-deep); }
  /* FACUTA — tenta de „facut" cu inel si bifa (C9). Verdele e o STARE, ca peste
     tot in sistem; nu se adauga o a treia culoare de identitate. Textul ia
     `--success-deep`, fiindca sta pe tenta, nu pe fill. */
  .banda.facuta { background: var(--success-subtle);
                  box-shadow: inset 0 0 0 1.5px color-mix(in srgb, var(--success) 45%, transparent); }
  .banda.facuta .banda-t { color: var(--success-deep); }
  .banda.facuta :global(.banda-bifa) { color: var(--success-deep); flex: none; margin-right: 4px; }
  /* DE CLARIFICAT — bara plina de restant. Aici culoarea e plina, nu tenta:
     lucrarea asta e chiar lucrul pe care trebuie sa-l rezolvi, iar cutia din
     jurul ei poarta deja tenta. */
  .banda.decizie { background: var(--danger); }
  .banda.decizie .banda-t { color: var(--accent-text); }
  .banda-t { display: block; font-size: var(--font-label); font-weight: var(--fw-semibold);
             line-height: var(--lh-snug); color: var(--accent-text);
             white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* Numele nu intra sub maner: linia lui de prindere ar cadea peste prima si
     ultima litera, si n-ai sti daca textul e taiat sau desenat gresit. */
  .banda.inceput .banda-t { padding-left: 6px; }
  .banda.sfarsit .banda-t { padding-right: 6px; }

  /* Antet de inaltime fixa — vezi comentariul din template: orice variatie aici
     desincronizeaza benzile pe orizontala. nowrap + overflow hidden garanteaza
     ca ramane pe un rand oricat de lung ar fi numele clientului. */
  /* `padding-right: 14px` a plecat odata cu contorul de lucrari (C6) — era spatiul
     rezervat lui, iar pe telefon strica centrarea cifrei (M2). */
  .zi-h { display: flex; align-items: center; gap: 6px; min-height: 15px; max-width: 100%;
          white-space: nowrap; overflow: hidden; }
  /* Eticheta iesirii: primul rand DIN chenar, nu un chip langa cifra zilei.
     Chenarul e `pointer-events: none` (lucrarile raman obiectele pe care le
     apuci), deci eticheta si-l reia pe al ei — ea E manerul cu care muti toata
     ieșirea. Inaltimea e exact un rand de banda fara gap (20 - 3), ca lucrarile
     de sub ea sa cada pe randurile lor. */
  /* 5px de aer sub muchia cutiei si 8 de la marginea celulei (3 cutie + 5 aer);
     bordura de 1px a cutiei e deja inauntru, deci marja scrisa e 4. Eticheta sta
     in coltul cutiei, cu 3px deasupra primei bare — geometria C10. */
  .chenar-et { pointer-events: auto; display: inline-flex; align-items: center; gap: 4px;
               max-width: calc(100% - 10px); height: 17px; margin: 4px 0 0 4px; padding: 0 4px;
               border: none; background: none; cursor: grab;
               font-size: var(--font-label); font-weight: var(--fw-semibold);
               letter-spacing: var(--tracking-label); color: var(--accent-deep);
               overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chenar-et:active { cursor: grabbing; }
  .chenar-et:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
  /* Sediul nu e o deplasare, deci nici eticheta lui nu striga: chenarul lui e
     punctat, iar numele trece pe cerneala neutra. */
  .chenar-et.sediu { color: var(--text-secondary); }
  /* Text pe tenta ia varianta adanca — cutia e deja in `--danger-subtle`. */
  .chenar-et.decizie { color: var(--danger-deep); }
  /* Durata e cifra, nu nume: mono, greutate normala, fara tracking de eticheta. */
  .et-zile { font-family: var(--font-mono); font-weight: var(--fw-normal);
             letter-spacing: var(--tracking-normal); }

  /* `.nr-lucrari` a plecat cu C6 — motivul e scris in markup, langa cifra zilei. */

  /* ===== agenda ferestrei (telefon) ===== */
  /* Agenda sta pe FUNDALUL paginii, nu in cardul grilei (M5) — de aceea n-are
     nici fond, nici umbra: e o lista, nu o a doua suprafata sub prima.
     `gap: 0`: randurile se despart prin linia lor, nu prin spatiu; cu amandoua,
     linia ar fi plutit la mijlocul unui gol. */
  .agenda { display: none; flex-direction: column; gap: 0; margin-top: var(--space-md); }
  .ag-cap { display: flex; align-items: center; gap: var(--space-sm);
    padding: 12px 2px 6px; border-top: 1px solid var(--border);
    font-family: var(--font-mono); font-size: var(--font-label);
    letter-spacing: var(--tracking-label); text-transform: uppercase; color: var(--text-faint); }
  .ag-linie { flex: 1; height: 1px; background: var(--border-subtle); }
  .ag-n { font-variant-numeric: tabular-nums; }
  /* RANDURILE NU SUNT CARDURI (M5). Erau fill tentat plus chenar de 1px — pe
     fundalul paginii, una sub alta, faceau o coloana de cutii in care ochiul
     numara cutii, nu iesiri. Acum sunt transparente si se despart printr-o linie;
     singura care poarta o haina e cea care cere ceva: „de clarificat".
     Fara `--c`: identitatea nu se mai codeaza cromatic, deci fillul era aceeasi
     tenta de accent pe toate randurile. */
  .ag-rand { position: relative; display: flex; flex-direction: column; gap: 4px; width: 100%;
    min-height: var(--tap-sheet); justify-content: center;
    padding: 8px 10px; text-align: left; border-radius: var(--radius-sm);
    background: none; border: none;
    cursor: pointer;
    transition: var(--transition-colors); }
  /* Linia dintre randuri e RETRASA 10px de fiecare parte (desen 6c) — separa fara
     sa inchida randul intr-o cutie. `::before`, nu `box-shadow`: umbra interioara
     mergea dintr-o muchie in cealalta. */
  .ag-rand + .ag-rand::before { content: ''; position: absolute; top: 0;
    left: 10px; right: 10px; height: 1px; background: var(--border); }
  /* Atingi o zi -> se aprinde iesirea ei, nu se schimba un panou. */
  .ag-rand.aprins { background: var(--accent-subtle); }
  /* Singura haina din lista: iesirea care asteapta un raspuns. */
  .ag-rand.rau { background: var(--danger-subtle);
                 box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--danger) 30%, transparent); }
  .ag-rand.rau .ag-titlu, .ag-rand.rau .ag-ico { color: var(--danger-deep); }
  .ag-sus { display: flex; align-items: center; gap: 6px; min-height: 20px; }
  .ag-ico { display: inline-flex; color: var(--text-dim); flex: none; }
  /* Clientul la 15: e numele iesirii, nu o metadata. 600 doar cand e o urgenta —
     altfel 500, ca lista sa nu strige toata deodata. */
  .ag-titlu { flex: 1; min-width: 0; font-size: var(--font-body); font-weight: var(--fw-medium);
    color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .ag-rand.rau .ag-titlu { font-weight: var(--fw-semibold); }
  .ag-cand { flex: none; font-family: var(--font-mono); font-size: var(--font-small); color: var(--text-dim); }
  .ag-lucrari { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
  .ag-l { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-small); color: var(--text-secondary); }
  .ag-l.pregatire { color: var(--text-faint); }
  .ag-l.facuta { color: var(--success-deep); }
  .ag-faza { color: var(--text-faint); }
  .ag-intrebare { font-size: var(--font-small); color: var(--danger-deep); }

  .side { display: flex; flex-direction: column; gap: var(--space-md); }
  .pan { background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); padding: var(--space-md); }
  /* In foaie, cardul il deseneaza `Modal` — panoul isi scoate propriul fond, umbra
     si padding, altfel ar iesi o suprafata in suprafata, cu doua raze si doua
     umbre una peste alta. */
  .pan.in-foaie { background: none; border-radius: 0; box-shadow: none; padding: 0; }
  /* Titlul zilei e treapta de PANOU (21/600), nu 13 ca metadatele de sub el (C12).
     La `--font-small` statea pe acelasi nivel cu „3 lucrări · Site" de dedesubt,
     deci panoul se deschidea fara sa spuna, dintr-o privire, CE zi ai deschis —
     tocmai lucrul pe care l-ai schimbat cu clicul. */
  .pan-zi { font-size: var(--font-h2); font-weight: var(--fw-semibold); color: var(--text);
            letter-spacing: var(--tracking-tight); line-height: var(--lh-tight); }
  .pan-sub { display: flex; align-items: center; gap: 5px; font-size: var(--font-small); color: var(--text-dim); margin: 3px 0 10px; }
  .pan-h { display: flex; align-items: center; gap: 8px; font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-faint); }
  /* Cifra e MONO simplu, nu o pastila (desen C14): antetul are deja greutatea lui. */
  .cnt { font-family: var(--font-mono); color: var(--text-secondary); letter-spacing: 0; font-variant-numeric: tabular-nums; }
  /* Linia mica de pe manerul foii taca — titlul zilei se scrie in corp, la 21/600
     (M9). `:has` pe clasa din corp, ca Modal sa nu invete despre Calendar. */
  :global(.modal:has(.pan.in-foaie) .modal-title) { display: none; }
  .pan-hint { font-size: var(--font-small); color: var(--text-faint); margin: 4px 0 8px; }
  .gol { font-size: var(--font-small); color: var(--text-dim); }

  .urm { display: flex; flex-direction: column; gap: 3px; width: 100%; text-align: left; margin-top: 10px;
         padding: 9px 11px; border-radius: var(--radius-md); border: 1px solid var(--border);
         background: var(--bg-elevated); cursor: pointer; }
  .urm:hover { border-color: var(--accent); }
  .urm-h { font-size: var(--font-label); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-faint); }
  .urm-d { display: flex; align-items: center; gap: 5px; font-size: var(--font-small); color: var(--text); }
  .urm-l { font-size: var(--font-small); color: var(--text-dim); line-height: var(--lh-normal); }

  /* PUNCTUL DE IDENTITATE A PLECAT (C13). Avea rost cat timp lista era „mixta, cu
     culori diferite" — dar `culoareLucrare` intoarce accentul pentru ORICE
     lucrare de cand identitatea nu se mai codeaza cromatic in Calendar, deci
     punctul era acelasi pe toate randurile: un semn care nu deosebea nimic.
     Numele urca la 15/500: e obiectul randului, nu o metadata. */
  .it { padding: 6px 8px; margin: 0 -8px 8px; border-radius: var(--radius-sm); }
  /* ACTIUNILE SUNT PERMANENTE (Ion, 2026-08-10: „nu are sens sa fie cu hover
     cele trei butoane, fa-le permanente deja"). Desenul (C13) le aprindea la
     hover, si asta avea sens cat timp stateau pe LINIA TITLULUI: acolo aparitia
     lor fura latime de la nume. De cand au randul lor (si locul rezervat),
     ascunderea nu mai cumpara nimic — doar cere o descoperire in plus pentru
     trei actiuni pe care le folosesti tot timpul.
     Randul de sub cursor ramane evidentiat: el spune PE CARE lucrare apesi,
     ceea ce conteaza cu atat mai mult cand butoanele se vad pe toate. */
  @media (hover: hover) {
    .pan:not(.in-foaie) .it:hover, .pan:not(.in-foaie) .it:focus-within { background: var(--bg-elevated); }
  }
  /* Titlul are randul lui, pe toata latimea: nu mai imparte linia cu actiunile. */
  .it-cap { display: flex; align-items: center; gap: 8px; }
  .it-t { display: flex; align-items: center; gap: 5px; font-size: var(--font-body);
          font-weight: var(--fw-medium); color: var(--text); text-align: left; cursor: pointer;
          min-width: 0; }
  .it-t:hover { color: var(--accent); }
  /* CINCI RANDURI, IN ORDINEA CERUTA DE ION (2026-08-10):
       1 titlu · 2 descriere · 3 chipuri · 4 actiuni · 5 stare + data.
     Fiecare rand raspunde la o singura intrebare, si de aceea nu se mai
     imbulzesc doua pe aceeasi linie. */
  /* Actiuni ca TEXT cu iconita, 13/600, fara chenar — randul lor. */
  .it-act { display: flex; align-items: center; gap: 14px; min-width: 0; margin-top: 6px; }
  /* Piciorul: starea la stanga, data impinsa la dreapta (`.it-data` are
     `margin-left: auto`, deci data sta la dreapta si cand nu exista bifa). */
  .it-jos { display: flex; align-items: center; gap: 8px; margin-top: 6px; min-height: 20px; }
  .ia { display: inline-flex; align-items: center; gap: 4px;
        font-size: var(--font-control); font-weight: var(--fw-semibold);
        color: var(--text-secondary); background: none; border: none; padding: 2px 0;
        cursor: pointer; white-space: nowrap; }
  .ia:hover:not(:disabled) { color: var(--accent); }
  .ia.del:hover:not(:disabled) { color: var(--danger); }
  .ia:disabled { opacity: 0.5; cursor: default; }
  /* RANDUL 2 — descrierea lucrarii. Text, nu chip: ea spune CE faci acolo, si e
     singurul rand care se poate rupe pe doua linii. */
  .it-et { margin-top: 3px; font-size: var(--font-small); color: var(--text-dim);
           line-height: var(--lh-snug); }
  /* RANDUL 3 — cele trei chipuri, toate in aceeasi cutie. */
  .it-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-top: 5px; }
  /* Chipurile sunt suprafata a doua cu inel, nu pastile pe `--bg-hover`: la 20px
     si cu raza `--radius-xs` se citesc ca etichete, iar `--radius-full` le facea
     sa semene cu numaratorile de peste tot. */
  .loc { display: inline-flex; align-items: center; gap: 4px; height: 20px; padding: 0 7px;
         border-radius: var(--radius-xs); background: var(--bg-elevated);
         box-shadow: inset 0 0 0 1px var(--border); white-space: nowrap;
         font-size: var(--font-label); font-weight: var(--fw-semibold); color: var(--text-secondary); }
  /* Faza preia limbajul barelor: palid = pregatire, plin = implementare. */
  .it-chips .faza { background: var(--accent-subtle); box-shadow: none; color: var(--accent-deep); }
  .it-chips .faza.pal { background: var(--bg-elevated); box-shadow: inset 0 0 0 1px var(--border); color: var(--text-secondary); }
  /* Data ieșirii, pironita la dreapta: pe un panou deschis pe o zi anume, ea spune
     cat tine lucrarea din care ziua face parte. Mono, ca orice cifra comparabila. */
  .it-data { margin-left: auto; font-family: var(--font-mono); font-size: var(--font-small);
             color: var(--text-dim); white-space: nowrap; flex: none; }
  /* Verdele spune „s-a facut", nu „urgent" — e singurul loc din rand unde
     culoarea nu tine de identitatea proiectului, si de aia e conturat, nu plin. */
  .it-jos .fac { background: none; color: var(--success);
                 box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--success) 40%, transparent); }
  /* „niciun task" ia ACEEASI cutie ca vecinii lui (Ion: „toate 3 la fel") — se
     deosebeste doar prin TON: tenta si inel de restant, cu triunghi. Inainte isi
     scria singur inaltimea si raza, deci arata ca alt fel de obiect. */
  .it-chips .tk.warn { background: var(--danger-subtle); color: var(--danger-deep);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--danger) 30%, transparent); }

  /* Blocul de intrebare (M10): tenta si inel de restant, ca sa se citeasca drept
     ceva ce asteapta un raspuns — nu ca o eticheta de stare. */
  .dec { display: flex; flex-wrap: wrap; align-items: center; }
  .dec.intrebare { gap: 8px; margin-top: 10px; padding: 12px; border-radius: var(--radius-sm);
                   background: var(--danger-subtle);
                   box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--danger) 30%, transparent); }
  .dec-q { display: flex; align-items: center; gap: 6px;
           font-size: var(--font-body); font-weight: var(--fw-semibold); color: var(--danger-deep); width: 100%; }
  /* Raspunsurile sunt de 48px si impart randul: la 22px erau exact tipul de tinta
     pe care o ratezi, iar asta e o intrebare la care raspunzi o singura data.
     15/600 (desen); „Mută pe azi" sta pe SUPRAFATA cu inel, nu pe elevated. */
  .dec.intrebare .b { flex: 1; justify-content: center; min-height: var(--tap-sheet);
                      font-size: var(--font-rand); font-weight: var(--fw-semibold);
                      background: var(--bg-surface); border-color: var(--border-strong); }
  /* „Da" e raspunsul asteptat, deci e plin. Verdele ar fi spus „succes"; aici
     spune „asta e actiunea", si actiunea poarta accentul. */
  .dec.intrebare .b.ok { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }
  .dec.intrebare .b.ok:hover:not(:disabled) { background: var(--accent-deep); border-color: var(--accent-deep); color: var(--accent-text); }
  .mut { display: flex; align-items: flex-end; gap: 6px; width: 100%; margin-top: 4px; }
  /* Actiunile rare din FOAIE (M9): randuri de 48 cu chevron, nu pastile. */
  .f-act { display: flex; flex-direction: column; margin-top: 8px; }
  .fa-r { display: flex; align-items: center; gap: 10px; width: 100%;
          min-height: var(--tap-sheet); padding: 4px 2px; text-align: left;
          background: none; border: none; cursor: pointer;
          border-top: 1px solid var(--border);
          font-size: var(--font-rand); font-weight: var(--fw-medium); color: var(--text); }
  .fa-r:disabled { opacity: 0.5; }
  .fa-r > :global(svg:first-child) { color: var(--text-secondary); flex: none; }
  .fa-r :global(.fa-chev) { margin-left: auto; color: var(--text-dim); flex: none; }
  .fa-c { display: flex; flex-direction: column; min-width: 0; }
  .fa-hint { font-size: var(--font-small); color: var(--text-dim); }
  .b { display: inline-flex; align-items: center; gap: 4px; font-size: var(--font-small); padding: 3px 8px; border-radius: var(--radius-sm);
       border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-secondary); cursor: pointer; }
  .b:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .b:disabled { opacity: 0.5; cursor: default; }
  .b.ok { color: var(--success); border-color: color-mix(in srgb, var(--success) 45%, transparent); }
  /* `.b.del` a plecat: „Scoate" nu mai e o pastila in randul lucrarii — pe
     desktop e actiune-text (`.ia.del`), in foaie e rand de 48px (`.fa-r`). */

  .rail { display: flex; flex-direction: column; gap: 4px; max-height: 260px; overflow-y: auto; }
  /* Randul are 44px si doua linii (C14): numele si, sub el, clientul. La ~28px si
     o linie, sertarul arata ca o lista de etichete, desi fiecare rand e un obiect
     pe care il RIDICI si il pui pe o zi — adica exact tinta pe care trebuie s-o
     nimeresti cu degetul sau cu cursorul.
     Punctul de identitate a plecat: `--c` e accentul pe toate randurile. */
  /* Randurile stau TRANSPARENTE pe card (desen C14); doar cel ales poarta tenta.
     Hoverul aduce fondul, ca sa se vada ca e un obiect de ridicat. */
  .np { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 4px 8px;
        border-radius: var(--radius-sm);
        width: 100%; text-align: left; border: none;
        background: transparent; cursor: grab;
        transition: background-color var(--dur-fast) var(--ease); }
  @media (hover: hover) {
    .np:hover { background: var(--bg-hover); }
  }
  .np-c { display: flex; flex-direction: column; gap: 1px; min-width: 0; flex: 1; }
  .np:active { cursor: grabbing; }
  /* Ales, in asteptarea unei zile. Nu e „selectat" in sensul unei liste — e un
     obiect ridicat, care asteapta sa fie pus jos. De aceea si calendarul se
     schimba in acelasi timp (vezi `.zi.tinta`): daca doar chipul s-ar aprinde,
     n-ai sti ca urmatoarea atingere pe o zi INSEAMNA ceva. */
  .np.ales { background: var(--accent-subtle); box-shadow: inset 0 0 0 1px var(--accent); }
  .np.ales .np-t, .np.ales .np-s { color: var(--accent-deep); }
  .np-t { font-size: var(--font-body); font-weight: var(--fw-medium); color: var(--text);
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .np-s { font-size: var(--font-small); color: var(--text-dim);
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  /* „Atinge ziua" apare DOAR pe randul ales: e instructiunea pentru pasul
     urmator, iar pe celelalte randuri ar fi un indemn care nu se aplica. */
  .np-hint { flex: none; font-size: var(--font-label); font-weight: var(--fw-semibold);
             letter-spacing: var(--tracking-label); color: var(--accent-deep); white-space: nowrap; }

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
    /* `.wrap.cu-panou` (doua clase) BATE `.wrap` (una), deci regula de o coloana
       trebuie sa se adreseze si ei — altfel coloana de 330px a panoului ramanea si
       pe telefon, iar cele sapte zile se imparteau ce mai ramanea: 4px pe zi.
       Bug-ul exista dinainte, dar se vedea doar dupa ce atingeai o zi (panoul se
       deschidea), iar `audit_mobil` nu atinge zile — deci trecea verde. De cand
       pagina se deschide cu ziua de azi selectata, apare din prima. */
    .wrap, .wrap.cu-panou { grid-template-columns: minmax(0, 1fr); }
    .side { order: 0; }
    .page { display: flex; flex-direction: column; }
    .bar { order: 0; }
    .wrap { order: 1; }
    /* `.surse { order: 2 }` A PLECAT, si nu ca rafinare — devenise gresit.
       Cat timp sursele erau copil al `.page`, `order` le trimitea la coada
       paginii. Din C2 sunt copil al `.bar`, deci acelasi `order: 2` le impingea
       DUPA sageti, adica exact invers decat le-am asezat in DOM. */
  }
  /* `.bar-cap` a plecat odata cu standardizarea titlurilor: titlul + luna stau
     acum IN PAGINA pe orice latime, ca pe restul rutelor, deci bara de telefon
     nu mai are ce dubla. */
  @media (max-width: 620px) {
    .page { padding: var(--space-md); }
    /* ===== VARIANTA B, ALEASA DE ION DIN MOCHETE (2026-08-10): „dunga +
       agenda". Banda de telefon NU mai e o pastila cu iconita si nume (M1 din
       handoff — incercata, iesea inghesuita pe datele reale, vezi poza lui) —
       e o DUNGA de 4px care spune doar STAREA prin culoare. Grila redevine
       harta pura: unde esti si cat de plin e; CE faci acolo scrie in agenda
       „Iesirile lunii" de sub grila, care exista exact pentru asta.
       Pasul 6 = dunga 4 + gol 2. Antetul celulei ramane 21 (padding 4 + cifra
       15 + 2 aer). */
    .grid { --h-antet: 21px; --h-banda: 6px; }
    /* Celula ramane practic FIXA la 44 (mocheta B): cu pasul de 6, chiar si
       cinci dungi (plafonul MAX_BENZI) cer doar 54px — deci `max()` ramane ca
       plasa pentru cazul rar, fara sa mai schimbe ritmul grilei. */
    .zi { min-height: max(var(--tap-min), calc(21px + var(--benzi, 1) * 6px + 3px));
          padding: 4px 2px 0; }
    /* Cifra sta CENTRATA (M2): la 50px latime, aliniata la stanga cadea peste
       capatul benzii de dedesubt si se citeau ca un singur bloc. */
    .zi-h { justify-content: center; }
    /* FARA SEPARATOARE VERTICALE (M3). La ~50px pe coloana, sapte linii verticale
       plus sapte cifre fac un grilaj in care ziua nu se mai desprinde. Raman doar
       liniile orizontale, care despart SAPTAMANILE — singura impartire pe care o
       citesti cu adevarat pe telefon. */
    .zi, .zi.col-ultima { box-shadow: inset 0 -1px 0 var(--border-strong); }
    .zi.rand-ultim, .zi.col-ultima.rand-ultim { box-shadow: none; }
    /* DUNGA DE STARE (mocheta B): 4px, fara text si fara iconita — la latimea
       asta o litera oricum nu incapea intreaga, iar numele trunchiat („Config…")
       era zgomot, nu informatie. Culoarea spune tot ce poate spune o dunga:
       plin = implementare, palid = pregatire, verde = facuta, rosu = de
       clarificat. Raza 2: la 4px inaltime orice raza mai mare o face pastila. */
    .banda { min-height: 4px; padding: 0; gap: 0; border-radius: 2px; }
    .banda-t { display: none; }
    .banda-ico { display: none; }
    .banda :global(.banda-bifa) { display: none; }
    .banda.inceput { margin-left: 4px; padding-left: 0; border-top-left-radius: 2px; border-bottom-left-radius: 2px; }
    .banda.sfarsit { margin-right: 4px; border-top-right-radius: 2px; border-bottom-right-radius: 2px; }
    /* „Palid" la 4px inseamna FILL stins, nu contur: un inel de 1.5px pe o dunga
       de 4 ar fi doua linii lipite. Aceeasi logica la facuta — fill verde plin,
       bifa n-are unde sta. */
    .banda.pregatire { background: color-mix(in srgb, var(--accent) 38%, transparent);
                       box-shadow: none; }
    .banda.facuta { background: var(--success); box-shadow: none; }
    /* CHENARUL NU SE DESENEAZA PE TELEFON (M6). El spune „zilele astea sunt o
       singura iesire" — un fapt care, pe o celula de 50px, ar fi o rama in plus
       peste benzi deja inghesuite. Pe telefon iesirile se citesc SCRISE, in agenda
       de sub grila, unde au loc de nume si de durata.
       `display: none`, nu transparent: altfel ramanea un element care primeste
       tranzitii si inaltime degeaba in fiecare saptamana cu o iesire. */
    .chenar { display: none; }
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

    /* Antetul zilelor: 26px si o singura litera (M7). */
    .wd span { height: 26px; }
    .wd-lung { display: none; }
    .wd-scurt { display: inline; font-style: normal; }

    /* Navigarea si butoanele barei: erau de 28px inaltime. */
    .ico { width: var(--tap-min); height: var(--tap-min); }
    .b-azi { height: var(--tap-min); padding: 0 14px; font-size: var(--font-small); }
    /* `.ics` NU APARE PE TELEFON (M8). Descarci un fisier de abonament o data, de
       pe calculator; pe telefon te abonezi din aplicatia de calendar, nu dintr-un
       buton care ocupa un sfert din bara. */
    .ics { display: none; }
    .nav { gap: var(--space-xs); }
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

  /* BANDA APUCATA SE RIDICA — confirmarea vizuala a apasarii lungi, perechea
     lui `puls()` din gest. Fara ea, pe telefon nu se vede ca gestul a inceput.
     STA LA FINALUL FOII cu bunastiinta: `.banda.pregatire` si `.banda.facuta`
     din blocul de telefon pun `box-shadow: none` la ACEEASI specificitate
     (0,2,0), deci scrisa mai sus era anulata exact pe starile pe care le muti
     cel mai des. Un `@media` n-ar fi ajutat — nu adauga specificitate. */
  .banda.se-trage { box-shadow: var(--shadow-md); transform: scale(1.02); z-index: 6; }
</style>
