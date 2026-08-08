<script>
  import { onMount } from 'svelte'
  import { CalendarRange, ChevronRight, CalendarDays, ListChecks, ArrowRight, X, CheckCircle2, Repeat, ExternalLink, Check, FileDown, Inbox, GripVertical, MapPin, Building2, Calendar } from '@lucide/svelte'
  import {
    plan, loadPlan, moveTaskDate, moveTaskTomorrow, toggleTaskDone,
    setTaskDates, setHorizon, toggleShowDone, toggleWeekends, scheduleBacklog,
  } from '../stores/plan.svelte.js'
  import { loadSubtasks, updateSubtask } from '../stores/tasks.svelte.js'
  import { buildColumns, grupeazaColoane, numeLuna, ziLuna, spanRect, dayDiff, addDays, clampNum } from '../lib/planDates.js'
  import { formatDate, formatDateShort, dueRing } from '../lib/formatters.js'
  import { toast } from '../stores/ui.svelte.js'
  import { morphNavigate } from '../lib/focus.js'
  import { glisare } from '../lib/glisare.js'
  import { motion, panou } from '../lib/motion.svelte.js'
  import { navigate } from '../lib/router.svelte.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import SelectorZi from '../components/ui/SelectorZi.svelte'
  import { culoareProiect, CULOARE_NEUTRA } from '../lib/culori.js'

  // Praguri pentru continutul unei benzi de perioada, in PROCENTE din fereastra —
  // nu in zile: la 6 luni o zi are 6px, la 7 zile are 165. Sub primul prag ramane
  // doar icoana (o litera taiata nu spune nimic, icoana spune „teren" / „sediu");
  // sub al doilea, durata ar manca eticheta, deci o lasam doar in tooltip.
  const BANDA_TEXT_MIN = 6.5
  const BANDA_ZILE_MIN = 14
  // La orizont lung banda nu mai are latime de citit: o perioada de o zi are
  // 0,55% din 180, adica 5px. Sub 11px n-o mai poti nici vedea, nici apuca.
  const BANDA_MIN_PX = 11
  const HORIZONS = [
    { d: 7, l: '7z', cat: '7 zile' }, { d: 14, l: '14z', cat: '14 zile' }, { d: 30, l: '30z', cat: '30 zile' },
    { d: 90, l: '3L', cat: '3 luni' }, { d: 180, l: '6L', cat: '6 luni' },
  ]

  // Culoarea benzii vine din lib/culori.js, aceeasi sursa ca in Calendar. Inainte
  // fiecare pagina isi tinea paleta ei si ordinea difera pe ultimele trei pozitii,
  // deci 43% dintre proiecte aveau o culoare aici si alta in Calendar.
  /* IDENTITATEA RAMANE UN PUNCT, NU O BANDA.
     `--lane` colora si punctul din eticheta, si FONDUL benzii de pregatire —
     deci pe acelasi ecran culoarea insemna si „proiectul X", si (prin
     palid/plin) „in ce faza esti". Doua intelesuri pe acelasi canal, exact
     abaterea pe care sistemul o interzice.
     Acum banda e in accent, iar forma spune faza: palid+contur = pregatire,
     plin = implementare. Culoarea de proiect ramane doar pe `.lane-dot` si pe
     punctele din sertar/export, unde e o LISTA MIXTA si punctul e singurul
     lucru care deosebeste doua randuri altfel identice — cazul in care
     sistemul chiar permite un punct de identitate. */
  function laneColor(id) {
    return id === '__global__' ? CULOARE_NEUTRA : culoareProiect(id)
  }

  // Severitatea termenului, ca in celelalte liste. `plan.today` vine de la server,
  // deci comparatia se face pe ACEEASI zi ca restul planului — nu pe ceasul
  // browserului, care poate fi in alt fus.
  const esteRestant = (d) => !!d && !!plan.today && String(d).slice(0, 10) < plan.today
  const esteAzi = (d) => !!d && !!plan.today && String(d).slice(0, 10) === plan.today

  // ANTETUL DE TIMP ARE O SINGURA STRUCTURA: grosier peste fin.
  // Pana la 30 de zile — saptamani peste zile. La 3L si 6L ziua ar avea 10px,
  // respectiv 5: structura nu se rupe, urca un nivel — LUNI peste SAPTAMANI.
  // De aceea fereastra lunga cere explicit `week`: implicitul lui `buildColumns`
  // ar da luni la 6L, iar peste luni n-are ce sa mai urce, si numarul de taskuri
  // pe saptamana n-ar avea coloana pe care sa stea.
  const unitCerut = $derived(plan.days <= 31 ? 'day' : 'week')
  const columns = $derived(buildColumns(plan.start, plan.days, unitCerut))
  const unit = $derived(columns.unit)
  const lung = $derived(unit !== 'day')
  const antet = $derived(grupeazaColoane(columns.cols))
  // Latimea REALA a pistei, masurata din antet (aceeasi coloana ca `.lane-track`).
  // Impachetarea are nevoie de ea ca sa stie cati pixeli inseamna o eticheta in
  // procente — vezi `intinderea`. Pana la prima masuratoare cade pe latimea minima,
  // adica pe cazul cel mai inghesuit.
  let pistaMasurata = $state(0)
  const todayIdx = $derived(plan.start && plan.today ? dayDiff(plan.start, plan.today) : null)
  const todayPct = $derived(todayIdx != null ? (todayIdx / plan.days) * 100 : null)
  // AZI E O COLOANA, NU O LINIE — deci se cauta coloana care il CONTINE, nu cea
  // cu `iso === today`: la orizont lung coloana e o saptamana intreaga si n-are
  // un `iso` de comparat. (Fereastra pornind din azi, raspunsul e mereu prima
  // coloana; se calculeaza oricum, ca sa nu depinda de o presupunere.)
  const contineAzi = (c) => todayPct != null && todayPct >= c.leftPct - 1e-9 && todayPct < c.leftPct + c.widthPct - 1e-9
  const coloanaAzi = $derived(columns.cols.findIndex(contineAzi))
  // Pe telefon scara arata unitatea care se poate CITI la 350px: zilele pana la
  // 30z, iar la 3L/6L grupele — douazeci si sase de saptamani ar fi 13px fiecare,
  // adica o dunga fara cifre. E acelasi rand de sus din antetul de pe desktop.
  const mCols = $derived(lung
    ? antet.grupe.map(g => ({ key: g.key, main: g.eticheta, sub: '', leftPct: g.leftPct, widthPct: g.widthPct, isWeekend: false }))
    : columns.cols)
  // Per-column min width by granularity, so a 6-month (weekly) view doesn't force
  // a 26-cell scroll. Daily view stays readable down to ~34px/day; „S44" in mono
  // la 12px are ~22px, deci si saptamana suporta 34.
  const colMin = $derived(unit === 'day' ? (plan.days <= 7 ? 74 : plan.days <= 14 ? 48 : 34) : (plan.days > 92 ? 34 : 66))
  const pistaMin = $derived(colMin * columns.cols.length)
  const pistaPx = $derived(pistaMasurata || pistaMin)
  // lane-w(240) + coloana de restante (78, doar cand exista) + cols
  const contentMin = $derived(240 + (areRestante ? 78 : 0) + pistaMin)

  // LUNA NU STA IN ANTET — o spune subtitlul paginii. In antet ar fi un al
  // treilea nivel peste saptamani si zile, si tot ar trebui scrisa de doua ori
  // cand fereastra trece dintr-o luna in alta.
  const subtitlu = $derived.by(() => {
    if (!plan.start) return ''
    const h = HORIZONS.find(x => x.d === plan.days)
    const ultima = addDays(plan.start, plan.days - 1)
    const l1 = numeLuna(plan.start)
    const l2 = numeLuna(ultima)
    const interval = lung
      ? (l1 === l2 ? l1 : `${l1}–${l2}`)
      : (l1 === l2 ? `${ziLuna(plan.start)}–${ziLuna(ultima)} ${l2}`
                   : `${ziLuna(plan.start)} ${l1} – ${ziLuna(ultima)} ${l2}`)
    return `de azi, ${h ? h.cat : plan.days + ' zile'} · ${interval}`
  })

  function isActive(s) { return s === 'in_progress' || s === 'in_lucru' }
  function isDone(s) { return s === 'done' || s === 'finalizat' }
  function effDue(t) { return t.data_scadenta || (isDone(t.status) ? t.data_finalizare : '') }

  // IMPACHETAREA MASOARA CE SE DESENEAZA, NU ZIUA.
  // Din v33 un task e o ZI, deci bara lui are latimea unei coloane — dar titlul
  // sta IN AFARA ei, la dreapta (`left: 100%`). La 14 zile, 220px de eticheta
  // inseamna patru zile. O impachetare care compara cutiile de o zi lasa cinci
  // repere dintr-o saptamana pe acelasi rand si le scrie titlurile unul peste
  // altul — impachetarea reuseste, ecranul nu. Se masoara bara PLUS titlul.
  const ETICHETA_MAX = 220     // `.bar-txt` max-width
  const ETICHETA_PAD = 7       // golul dintre bara si titlul ei
  // Latimea unui titlu, aproximata: Gabarito semibold la --font-small (13px) are
  // ~0.45em pe caracter. Nu masuram in DOM — ar insemna un layout pass per task
  // la fiecare re-randare, iar o eroare de cateva procente doar imparte doua
  // etichete pe randuri diferite, ceea ce oricum voiai.
  function latimeTitlu(s) { return Math.min(ETICHETA_MAX, (s || '').length * 5.8) }
  function inProcente(px, pistaPx) { return (px / Math.max(1, pistaPx)) * 100 }

  /** Intinderea DESENATA a unui reper, in procente din pista: bara plus titlul. */
  function intinderea(t, pistaPx) {
    const et = inProcente(latimeTitlu(t.titlu) + ETICHETA_PAD, pistaPx)
    // `.flip`: in ultima treime titlul se intoarce spre STANGA barei, deci si
    // intinderea lui e in partea cealalta. Fara asta, doua repere lipite de
    // marginea din dreapta ar parea ca nu se ating si ar cadea pe acelasi rand.
    if (t.flip) return { de: t.rect.left - et, la: t.rect.left + t.rect.width }
    return { de: t.rect.left, la: t.rect.left + t.rect.width + et }
  }

  const seSuprapun = (a, b) => a.de < b.la - 0.001 && b.de < a.la - 0.001

  /** Primul rand liber, cu ce se deseneaza acolo — nu cu ziua.
   *
   *  `blocate` sunt spanurile pe care ETICHETA UNEI PERIOADE le tine pe randul
   *  intai: ea se scrie pe latimea benzii (sau, la orizont lung, langa bara), deci
   *  un reper care cade acolo trebuie sa coboare. Fara asta, singurul lucru care
   *  se vedea peste banda era titlul taiat al perioadei.
   *
   *  Suprapunerea se testeaza cu TOT randul, nu doar cu ultimul asezat: randul
   *  intai porneste deja ocupat pe mijloc, iar un reper mai timpuriu decat banda
   *  are voie sa incapa inaintea ei. Cu testul „dupa ultimul" ar fi cazut mereu
   *  pe randul doi, si banda ar fi impins in jos exact reperele pe care nu le
   *  atinge. Sunt zeci de elemente pe rand, deci n^2 nu costa nimic. */
  function packRows(repere, blocate) {
    const randuri = []
    const ocupat = []
    if (blocate.length) { randuri.push([]); ocupat.push([...blocate]) }
    for (const t of repere) {
      let pus = false
      for (let i = 0; i < randuri.length; i++) {
        if (!ocupat[i].some(o => seSuprapun(o, t.span))) {
          randuri[i].push(t); ocupat[i].push(t.span); pus = true; break
        }
      }
      if (!pus) { randuri.push([t]); ocupat.push([t.span]) }
    }
    return randuri
  }

  // INALTIMEA RANDULUI URMEAZA CE A IESIT DIN IMPACHETARE.
  // 14 sus (marginea benzii + aerul de deasupra primului reper), n randuri de
  // 20 cu 4 intre ele, 6 jos. Minimul de 48 tine un rand de proiect apucabil si
  // cand n-are decat o banda. 1 reper 48 · 2 repere 64 · 3 repere 88.
  const H_REPER = 20
  const H_GOL = 4
  function geometrieBanda(n) {
    const r = Math.max(1, n)
    const stiva = r * H_REPER + (r - 1) * H_GOL
    // `min-height`, nu `height`: coloana de nume poate cere mai mult (numele de
    // proiect se scriu pe doua randuri, ca sa nu iasa noua trunchieri identice).
    // De aceea randul intai nu se calculeaza din inaltimea ASTA, ci din stiva —
    // ea e centrata in pista, deci `50% - stiva/2` ramane adevarat si cand banda
    // creste sub eticheta.
    return { inaltime: Math.max(48, 14 + stiva + 6), stiva }
  }

  /** La orizont lung reperele se strang intr-un numar pe saptamana.
   *  Intrebarea nu mai e „ce am de facut joi", e „cand sunt plecat si cat" —
   *  iar numarul spune in ce saptamana se ingramadesc, deci unde cobori la 14z. */
  const PASTILA_PX = 28
  function numerePeSaptamana(tasks, cols, pistaPx) {
    const pe = new Map()
    for (const t of tasks) {
      if (!t.rect) continue
      const i = cols.findIndex(c => t.rect.left >= c.leftPct - 1e-9 && t.rect.left < c.leftPct + c.widthPct - 1e-9)
      if (i < 0) continue
      pe.set(i, (pe.get(i) || 0) + 1)
    }
    return [...pe.entries()].sort((a, b) => a[0] - b[0]).map(([i, n]) => {
      const c = cols[i]
      const lat = Math.max(c.widthPct, inProcente(PASTILA_PX, pistaPx))
      return { cheie: 'w' + c.key, numar: n, leftPct: c.leftPct, widthPct: c.widthPct,
               eticheta: c.sub, span: { de: c.leftPct, la: c.leftPct + lat } }
    })
  }

  // PREGATIREA NU SE INTRODUCE — E GOLUL.
  // Ion: „perioada pana la implementare este perioada de pregatire (…) apoi de la
  // o etapa de implementare la alta la fel este pregatire."
  // Deci nu e un lucru pe care il tastezi, e complementul etapelor: golul de
  // dinaintea primei etape si golurile DINTRE etape. Ion, 2026-07-30: „dupa ultima
  // perioada de implementare nu mai exista perioada de pregatire" — banda nu mai
  // curge pana la marginea ferestrei. Segment DESCHIS la dreapta rămâne un singur
  // caz: nicio etapa fixata, deci tot ce se vede e pregatire pentru o implementare
  // pe care inca n-o sti.
  function segmentePregatire(lane) {
    // Un proiect inchis nu mai pregateste nimic.
    if (lane.tip !== 'proiect' || lane.status === 'finalizat') return []
    // Golul e rupt DOAR de implementari. O zi de pregatire blocata explicit
    // (ex. „Parametrizare atelier", la sediu) face parte din pregatire, nu o
    // intrerupe — se deseneaza peste banda, ca bara plina.
    const etape = (lane.implementari || [])
      .filter(im => im.data_start && (im.faza || 'implementare') === 'implementare')
      .map(im => ({ a: im.data_start.slice(0, 10), b: (im.data_sfarsit || im.data_start).slice(0, 10) }))
      .sort((x, y) => x.a.localeCompare(y.a))
    // De cand se pregateste, nu se mai sti: `data_incepere` a plecat in v36, iar
    // `prima_zi` (min al perioadelor) e chiar prima etapa — pornind de acolo,
    // pregatirea dinaintea primei implementari ar avea latime zero. Deci pornim de
    // la marginea ferestrei: pregatirea e in curs, chiar daca nu stim de cand —
    // iar banda taiata la stanga spune exact asta.
    const inceput = plan.start
    if (!inceput) return []
    const out = []
    let cursor = inceput
    for (const e of etape) {
      // Capatul nesigur e cel din STANGA, nu cel din dreapta: ziua in care s-a
      // apucat de pregatire nu se sti, in timp ce ziua din dreapta e o data reala
      // — prima zi de implementare. Un gol DINTRE doua etape are amandoua capetele
      // sigure (a doua zi dupa etapa precedenta), deci nu se estompeaza.
      if (cursor < e.a) out.push({ de: cursor, la: addDays(e.a, -1), deschis: false, nesigurStart: cursor === plan.start })
      if (e.b >= cursor) cursor = addDays(e.b, 1)
    }
    // Nicio etapa fixata: toata fereastra e pregatire — nesigura la ambele capete.
    // Cand exista etape, ultima INCHEIE pregatirea: nu mai desenam nimic dupa ea.
    if (etape.length === 0) out.push({ de: cursor, la: '', deschis: true, nesigurStart: true })
    return out
  }

  // DOUA PERIOADE LIPITE, DE ACEEASI CATEGORIE, SUNT UNA.
  // Ion, 2026-07-30: „daca sunt doua perioade de implementare de aceeasi categorie
  // pe acelasi proiect, adica doua de site sau doua de birou, sa se contopeasca.
  // Daca sunt diferite atunci trebuie sa se deosebeasca."
  // Contopim doar ce se ATINGE (sau se suprapune): un gol intre doua perioade e
  // pregatire, deci nu poate fi inghitit de banda. „Categorie" = locatie SI faza:
  // o zi de pregatire la sediu si o etapa de implementare la sediu arata diferit
  // (palid vs plin), deci nu pot fi acelasi bloc.
  function contopeste(impls) {
    const ord = (impls || [])
      .filter(im => im.data_start)
      .map(im => ({
        ...im,
        faza: im.faza || 'implementare',
        a: im.data_start.slice(0, 10),
        b: (im.data_sfarsit || im.data_start).slice(0, 10),
      }))
      .sort((x, y) => x.a.localeCompare(y.a) || x.b.localeCompare(y.b))
    const out = []
    for (const im of ord) {
      const last = out[out.length - 1]
      if (last && last.locatie === im.locatie && last.faza === im.faza && im.a <= addDays(last.b, 1)) {
        if (im.b > last.b) last.b = im.b
        last.parti.push(im)
      } else {
        out.push({ ...im, parti: [im] })
      }
    }
    // O singura eticheta per banda, chiar cand s-au contopit mai multe perioade:
    // etichetele distincte, in ordine, separate ca in restul aplicatiei.
    return out.map(im => ({
      ...im,
      eticheta: [...new Set(im.parti.map(p => p.eticheta).filter(Boolean))].join(' · '),
      zile: (dayDiff(im.a, im.b) || 0) + 1,
    }))
  }

  const views = $derived(plan.lanes.map((lane) => {
    const color = laneColor(lane.id)
    // Segmentele de pregatire, decupate pe fereastra vizibila. Cele deschise se
    // intind pana la marginea din dreapta si primesc muchie estompata.
    const pregatire = segmentePregatire(lane)
      .map(seg => {
        const capat = seg.deschis ? addDays(plan.start, plan.days) : seg.la
        const rect = spanRect(seg.de, capat, plan.start, plan.days)
        return rect ? { ...seg, rect } : null
      })
      .filter(Boolean)
    const tasks = lane.tasks.map(t => {
      const rect = spanRect(effDue(t), effDue(t), plan.start, plan.days)
      // TITLUL SE INTOARCE DOAR CAND N-AR INCAPEA LA DREAPTA.
      // Pragul era un procent fix (62), ales cand titlul avea alta geometrie —
      // si intorcea repere care aveau loc berechet: un reper la 64% cu titlu de
      // 15% se masura spre STANGA, peste banda de pregatire, si cadea trei
      // randuri mai jos degeaba. Acum se compara chiar ce se deseneaza cu
      // marginea pistei.
      // `flip` se calculeaza O SINGURA DATA, aici: impachetarea si desenul
      // trebuie sa fie de acord in ce parte iese titlul, altfel un reper se
      // masoara spre dreapta si se scrie spre stanga.
      const et = rect ? inProcente(latimeTitlu(t.titlu) + ETICHETA_PAD, pistaPx) : 0
      return { ...t, rect, flip: !!rect && rect.left + rect.width + et > 100, cheie: t.tip + ':' + t.id }
    })
    const impl = contopeste(lane.implementari)
      .map(im => ({ ...im, rect: spanRect(im.a, im.b, plan.start, plan.days) }))
      .filter(im => im.rect)
      .map(im => {
        const etichetaLunga = `${locLabel(im.locatie)}${im.eticheta ? ' · ' + im.eticheta : ''} · ${im.zile} ${im.zile === 1 ? 'zi' : 'zile'}`
        // La orizont lung eticheta iese din bara, deci se intoarce dupa aceeasi
        // regula ca titlul unui reper: numai cand n-ar incapea la dreapta. Fara
        // ea, o perioada de la capatul ferestrei si-ar scrie numele in afara
        // pistei si ar creste latimea derulabila cu 200px de gol.
        const lat = Math.max(im.rect.width, inProcente(BANDA_MIN_PX, pistaPx))
        const et = inProcente(latimeTitlu(etichetaLunga) + ETICHETA_PAD, pistaPx)
        return { ...im, etichetaLunga, flip: lung && im.rect.left + lat + et > 100 }
      })
    // ETICHETA PERIOADEI TINE RANDUL INTAI.
    // La orizont scurt se scrie in banda, deci ocupa exact latimea ei; la orizont
    // lung banda e o bara de 20px si eticheta iese pe langa ea, deci ocupa bara
    // (minim 11px) plus textul. In ambele cazuri e primul lucru de pe rand, si
    // reperele care cad peste ea coboara.
    const benzi = impl.map(im => {
      if (!lung) return { de: im.rect.left, la: im.rect.left + im.rect.width }
      const lat = Math.max(im.rect.width, inProcente(BANDA_MIN_PX, pistaPx))
      const et = inProcente(latimeTitlu(im.etichetaLunga) + ETICHETA_PAD, pistaPx)
      return im.flip
        ? { de: im.rect.left - et, la: im.rect.left + lat }
        : { de: im.rect.left, la: im.rect.left + lat + et }
    })
    const repere = lung
      ? numerePeSaptamana(tasks, columns.cols, pistaPx)
      : tasks.filter(t => t.rect)
          .map(t => ({ ...t, span: intinderea(t, pistaPx) }))
          .sort((a, b) => a.span.de - b.span.de || a.span.la - b.span.la)
    const packed = packRows(repere, benzi)
    // Restantele vin de la server ca lista proprie: sunt INAINTEA ferestrei, deci
    // n-au geometrie si nu pot sta pe pista. Vezi `.rest-col`.
    const restante = lane.restante || []
    return { ...lane, color, pregatire, tasks, packed, geo: geometrieBanda(packed.length), impl, restante }
  }))
  // Coloana „Restante" apare doar cand are ce arata. O coloana mereu goala e exact
  // felul de gol rezervat pe care il repara restul turei.
  const areRestante = $derived(views.some(l => l.restante.length > 0))

  // ACEEASI ORDINE SUS SI JOS (telefon).
  // Reperele din banda stau dupa data; randurile de dedesubt veneau in ordinea din
  // `lane.tasks`, adica a serverului. Atingeai primul reper din stanga si `arata()`
  // te derula la al saptelea rand. Acum lista se asaza pe zile, cu trei capete de
  // grup — iar restantele, care n-au unde sa stea pe o banda ce incepe azi, devin
  // primul grup.
  //
  // NU folosim `grupeazaDupaTermen` din /tasks: acolo grupele sunt Azi / Mâine /
  // Zilele astea / Mai târziu, potrivite unei liste deschise. Aici fereastra e
  // aleasa de tine si poate fi de 6 luni — „Mai târziu" ar fi chiar fereastra.
  function grupeazaBanda(lane) {
    const dupaZi = (a, b) => String(a.data_scadenta || '').slice(0, 10)
      .localeCompare(String(b.data_scadenta || '').slice(0, 10))
    const azi = lane.tasks.filter(t => esteAzi(t.data_scadenta)).sort(dupaZi)
    const restul = lane.tasks.filter(t => !esteAzi(t.data_scadenta)).sort(dupaZi)
    const capAzi = plan.today ? `Azi · ${formatDateShort(plan.today)}` : 'Azi'
    return [
      { id: 'restant', titlu: 'Restante', ton: 'danger', items: lane.restante },
      { id: 'azi', titlu: capAzi, ton: 'accent', items: azi },
      { id: 'urmeaza', titlu: 'Zilele următoare', ton: 'normal', items: restul },
    ].filter(g => g.items.length > 0)
  }

  // PERIOADA, SCRISA O SINGURA DATA.
  // Era desenata in banda (unde e decor) si repetata dedesubt ca `.mimpl` — un rand
  // intreg de 44px per perioada, deci un proiect cu trei perioade primea trei
  // randuri INAINTEA primului task. Ramane cea in curs (sau urmatoarea), cu „+N".
  function perioadaDeAratat(lane) {
    if (!lane.impl.length) return null
    const azi = plan.today || ''
    const inCurs = lane.impl.find(im => im.a <= azi && azi <= im.b)
    const urmatoarea = lane.impl.find(im => im.a > azi)
    return { im: inCurs || urmatoarea || lane.impl[0], rest: lane.impl.length - 1 }
  }
  function locLabel(l) { return l === 'sediu' ? 'Sediu EGB' : 'Site' }

  // --- TASKUL DESCHIS: PANOU LATERAL, NU POPOVER (4e) ---
  //
  // Era un popover plutitor de 256px, ancorat la bara apasata, cu patru linii de
  // actiuni. Trei lucruri nu mergeau:
  //   · ACOPEREA. Sistemul cere „panoul face loc, nu acopera": coloana lui apare
  //     odata cu el si continutul se stramteaza. Un popover peste pista ascunde
  //     exact zilele din jurul taskului pe care tocmai l-ai deschis.
  //   · ERA AL TREILEA TIPAR pentru acelasi lucru. „Un detaliu, o componenta":
  //     panou lateral pe desktop, foaie de jos pe telefon — nu si popover.
  //   · NU ARATA TASKUL, doar verbe. Termenul, perioada peste care cade, nota si
  //     pasii nu se vedeau nicaieri, desi ei sunt motivul pentru care il deschizi.
  //
  // Pe telefon panoul nu se randeaza deloc: acolo `.chart` e ascuns, iar reperul
  // duce la randul din lista, care are deja foaia lui de actiuni.
  let sel = $state(null)
  let anchorEl = null
  let pasi = $state([])
  let pasiSeIncarca = $state(false)

  async function deschideTask(task, lane, el) {
    anchorEl = el || null
    sel = { ...task, laneNume: lane?.nume, laneId: lane?.id, laneImpl: lane?.impl || [] }
    pasi = []
    if (!task.subtask_total) return
    pasiSeIncarca = true
    try { pasi = await loadSubtasks(task.id) } catch { pasi = [] }
    finally { pasiSeIncarca = false }
  }
  function closePop() { sel = null; anchorEl = null; pasi = [] }

  async function comutaPas(p) {
    // Optimist, ca in /tasks: fractia din antet se recalculeaza din lista.
    pasi = pasi.map(x => x.id === p.id ? { ...x, done: p.done ? 0 : 1 } : x)
    try { await updateSubtask(p.id, { done: p.done ? 0 : 1 }) }
    catch (e) { pasi = pasi.map(x => x.id === p.id ? { ...x, done: p.done } : x); toast(`Eroare: ${e.message}`, 'error') }
  }

  /** Perioada peste care cade termenul taskului — randul „Perioadă" din panou.
   *  Nu e o cautare noua: benzile lane-ului sunt deja contopite si decupate pe
   *  fereastra, deci raspunsul e chiar banda pe care se deseneaza reperul. */
  function perioadaTaskului(t) {
    const zi = (t?.data_scadenta || '').slice(0, 10)
    if (!zi || !sel?.laneImpl) return null
    return sel.laneImpl.find(im => im.a <= zi && zi <= im.b) || null
  }

  function openTask(t, srcEl) {
    const el = srcEl || anchorEl
    const task = t || sel
    if (!task) return
    closePop()
    if (task.tip === 'proiect' && task.proiect_id) morphNavigate(el, `/projects/${task.proiect_id}`, 'task', task.id)
    else morphNavigate(el, '/tasks', 'global', task.id)
  }

  async function onMove(t, v) {
    if (!v) return
    try {
      await moveTaskDate(t.tip, t.id, v)
      toast(`Mutat pe ${formatDate(v)}`, 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    closePop()
  }
  async function onTomorrow(t) {
    try { await moveTaskTomorrow(t.tip, t.id); toast('Mutat pe mâine', 'success') }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    closePop()
  }
  async function onDone(t) {
    try {
      const res = await toggleTaskDone(t.tip, t.id, t.status)
      if (res?.recurring_spawned) toast(`Finalizat ✓ — următoarea: ${formatDate(res.recurring_next)}`, 'success')
      else toast(isDone(t.status) ? 'Redeschis' : 'Finalizat ✓', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    closePop()
  }

  function onKey(e) { if (e.key === 'Escape') closePop() }

  /** Punct din banda -> randul lui din lista de dedesubt.
   *  Pe desktop, clickul pe o bara deschide un popover cu actiuni. Pe telefon
   *  actiunile sunt DEJA pe rand, iar un popover peste o banda de 22px ar fi al
   *  treilea loc in care apare acelasi task. Deci punctul nu deschide nimic: te
   *  duce la rand si il aprinde scurt, ca sa vezi care e (`focus-flash` e aceeasi
   *  animatie folosita cand aterizezi pe un task venind din alta pagina). */
  function arata(t) {
    const el = document.querySelector(`.mrow[data-rand="${t.tip}:${t.id}"]`)
    if (!el) return
    el.style.scrollMarginTop = 'calc(var(--header-height) + 46px)'
    el.scrollIntoView({ behavior: motion.reduced ? 'auto' : 'smooth', block: 'center' })
    el.classList.remove('focus-flash')
    void el.offsetWidth   // reporneste animatia daca atingi acelasi punct de doua ori
    el.classList.add('focus-flash')
    setTimeout(() => el.classList.remove('focus-flash'), 1700)
  }

  // --- drag / resize (desktop swimlane) ---
  let drag = null
  let dragLabel = $state(null)

  function startDrag(e, t, mode, lane) {
    if (e.button != null && e.button !== 0) return
    if (isDone(t.status)) return // finished tasks are read-only on the timeline
    const barEl = e.currentTarget.closest('.bar')
    const trackEl = barEl?.closest('.lane-track')
    if (!barEl || !trackEl) return
    const w = trackEl.getBoundingClientRect().width
    drag = {
      t, mode, barEl, lane,
      startX: e.clientX,
      dayW: w / plan.days,
      unit: 100 / plan.days,
      origLeft: parseFloat(barEl.style.left) || 0,
      origWidth: parseFloat(barEl.style.width) || 0,
      effDelta: 0, moved: false,
    }
    barEl.setPointerCapture?.(e.pointerId)
    document.body.classList.add('plan-dragging')
    window.addEventListener('pointermove', onDragMove)
    window.addEventListener('pointerup', onDragUp)
    e.preventDefault(); e.stopPropagation()
  }

  // Un task e o ZI, nu un interval (v33): la tragere se muta termenul.
  function previewText(d) {
    const base = (d.t.data_scadenta || '').slice(0, 10)
    return base ? `termen ${formatDateShort(addDays(base, d.effDelta))}` : ''
  }

  function onDragMove(e) {
    if (!drag) return
    const dx = e.clientX - drag.startX
    if (Math.abs(dx) > 3) drag.moved = true
    const dd = Math.round(dx / drag.dayW)
    const u = drag.unit
    const el = drag.barEl
    if (drag.mode === 'move') {
      const want = clampNum(drag.origLeft + dd * u, 0, 100 - drag.origWidth)
      el.style.left = want + '%'
      drag.effDelta = Math.round((want - drag.origLeft) / u)
    }
    dragLabel = { x: e.clientX, y: e.clientY, text: previewText(drag) }
  }

  function commitBody(d) {
    const base = (d.t.data_scadenta || '').slice(0, 10)
    const body = {}
    if (base) body.data_scadenta = addDays(base, d.effDelta)
    return body
  }

  async function onDragUp() {
    window.removeEventListener('pointermove', onDragMove)
    window.removeEventListener('pointerup', onDragUp)
    document.body.classList.remove('plan-dragging')
    const d = drag
    drag = null
    dragLabel = null
    if (!d) return
    if (!d.moved || d.effDelta === 0) {
      d.barEl.style.left = d.origLeft + '%'
      d.barEl.style.width = d.origWidth + '%'
      deschideTask(d.t, d.lane, d.barEl)
      return
    }
    try {
      await setTaskDates(d.t.tip, d.t.id, commitBody(d))
      toast('Reprogramat', 'success')
    } catch (err) {
      toast(`Eroare: ${err.message}`, 'error')
      await loadPlan()
    }
  }

  // --- backlog rail + drag-to-schedule (HTML5 DnD onto the timeline) ---
  let backlogOpen = $state(true)
  let dragTask = null
  let dropDay = $state(null) // {idx, pct, iso} live indicator while dragging

  function backlogDragStart(e, t) {
    dragTask = t
    e.dataTransfer.effectAllowed = 'move'
    try { e.dataTransfer.setData('text/plain', t.id) } catch (_) {}
  }
  function backlogDragEnd() { dragTask = null; dropDay = null }

  function dayFromEvent(e) {
    const body = e.currentTarget
    const rect = body.getBoundingClientRect()
    const cs = getComputedStyle(body)
    // Cele DOUA coloane fixe din stanga pistei. Fara `--rest-w` aici, un drop ar
    // cadea cu 78px mai la dreapta decat ziua pe care o vezi sub cursor.
    const laneW = (parseFloat(cs.getPropertyValue('--lane-w')) || 240)
      + (parseFloat(cs.getPropertyValue('--rest-w')) || 0)
    const trackW = rect.width - laneW
    if (trackW <= 0) return null
    const x = e.clientX - rect.left - laneW
    const frac = clampNum(x / trackW, 0, 0.9999)
    const idx = Math.floor(frac * plan.days)
    return { idx, pct: (idx / plan.days) * 100, iso: addDays(plan.start, idx) }
  }
  function onBodyDragOver(e) {
    if (!dragTask) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    dropDay = dayFromEvent(e)
  }
  async function onBodyDrop(e) {
    if (!dragTask) return
    e.preventDefault()
    const d = dayFromEvent(e)
    const t = dragTask
    dragTask = null; dropDay = null
    if (!d) return
    try { await scheduleBacklog(t.tip, t.id, d.iso); toast(`Planificat pe ${formatDate(d.iso)}`, 'success') }
    catch (err) { toast(`Eroare: ${err.message}`, 'error') }
  }
  async function scheduleFromPicker(t, v) {
    if (!v) return
    try { await scheduleBacklog(t.tip, t.id, v); toast(`Planificat pe ${formatDate(v)}`, 'success') }
    catch (err) { toast(`Eroare: ${err.message}`, 'error') }
  }

  // --- PDF export via the browser's print-to-PDF ---
  let showExport = $state(false)
  let exportSel = $state(new Set()) // lane ids to include
  let exportPageBreak = $state(false)
  let savedTheme = null

  const projectLanes = $derived(plan.lanes)

  function openExport() {
    exportSel = new Set(plan.lanes.map(l => l.id)) // default: all
    showExport = true
  }
  function toggleExportLane(id) {
    const next = new Set(exportSel)
    if (next.has(id)) next.delete(id); else next.add(id)
    exportSel = next
  }
  function toggleExportAll() {
    exportSel = exportSel.size === plan.lanes.length ? new Set() : new Set(plan.lanes.map(l => l.id))
  }

  function runExport() {
    showExport = false
    const root = document.documentElement
    savedTheme = root.getAttribute('data-theme')
    root.setAttribute('data-theme', 'light') // print on paper-light regardless of app theme
    document.body.classList.add('plan-printing')
    if (exportPageBreak) document.body.classList.add('plan-pagebreak')
    // let the DOM settle (theme + hide classes) before opening the dialog
    setTimeout(() => window.print(), 80)
  }
  function afterPrint() {
    document.body.classList.remove('plan-printing', 'plan-pagebreak')
    const root = document.documentElement
    if (savedTheme) root.setAttribute('data-theme', savedTheme)
    else root.removeAttribute('data-theme')
    savedTheme = null
  }

  const exportRange = $derived(
    plan.start ? `${formatDate(plan.start)} – ${formatDate(addDays(plan.start, plan.days - 1))}` : ''
  )

  onMount(() => {
    loadPlan()
    window.addEventListener('keydown', onKey)
    window.addEventListener('afterprint', afterPrint)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('afterprint', afterPrint)
    }
  })
</script>

<!-- Ca in Calendar: invelisul urca, apoi celulele. Antetul paginii nu e celula,
     e cadrul — urca odata cu invelisul. `.chart` si `.mlist` nu se vad niciodata
     impreuna (820px le comuta), dar indicii merg mai departe prin `.backlog`, ca
     pe telefon — unde sertarul sta DEASUPRA listei — capul sa nu soseasca dupa
     coada. -->
<div class="page ruta-in">
  <div class="page-header">
    <div class="page-title-row">
      <CalendarRange size={22} />
      <h1>Planificator</h1>
      <!-- Ce fereastra vezi, scris o data. Antetul de timp n-o mai spune: acolo
           luna ar fi un al treilea nivel peste saptamani si zile. -->
      {#if subtitlu}<span class="page-sub">{subtitlu}</span>{/if}
    </div>
    <div class="controls">
      <div class="seg" role="group" aria-label="Orizont">
        {#each HORIZONS as h}
          <button class="seg-btn" class:active={plan.days === h.d} onclick={() => setHorizon(h.d)}>{h.l}</button>
        {/each}
      </div>
      <button class="toggle" class:on={plan.showWeekends} disabled={unit !== 'day'} onclick={toggleWeekends} title={unit === 'day' ? 'Evidențiază weekendurile' : 'Weekendurile apar doar în vederea pe zile'}>
        <span class="tk-box">{#if plan.showWeekends}<Check size={12} />{/if}</span> Weekend
      </button>
      <button class="toggle" class:on={plan.showDone} onclick={toggleShowDone} title="Arată taskurile finalizate">
        <span class="tk-box">{#if plan.showDone}<Check size={12} />{/if}</span> Finalizate
      </button>
      <button class="toggle export" onclick={openExport} disabled={plan.lanes.length === 0} title="Exportă ca PDF (print)">
        <FileDown size={14} /> <span class="tg-lung">Export </span>PDF
      </button>
    </div>
  </div>

  {#if plan.loading && plan.lanes.length === 0}
    <div class="skel">{#each Array(4) as _}<Skeleton height="72px" />{/each}</div>
  {:else if plan.error}
    <ErrorState message={plan.error} onretry={loadPlan} />
  {:else if views.length === 0}
    <EmptyState icon={CalendarRange} title="Nimic în această fereastră" description="Planifică taskuri (din Astăzi sau din proiecte) ca să apară aici pe zile." />
  {:else}
    <!-- ===== Desktop swimlane ===== -->
    <div class="print-title">Planificator · {exportRange}</div>
    <!-- PANOUL FACE LOC, NU ACOPERA: coloana lui apare odata cu el si pista se
         stramteaza. Cand nu e nimic deschis — starea implicita la incarcare —
         grila are o singura coloana si pagina e pe toata latimea. -->
    <div class="lucru" class:cu-panou={!!sel}>
    <div class="chart cell-in" style="--celula: 0">
      <div class="chart-scroll">
        <div class="inner" style="min-width: {contentMin}px; --rest-w: {areRestante ? 78 : 0}px">
          <!-- ANTETUL DE TIMP, O SINGURA STRUCTURA: grosier peste fin.
               Randul de sus aduna coloanele de dedesubt (saptamani peste zile,
               luni peste saptamani) si e centrat pe ELE, nu recalculat — vezi
               `grupeazaColoane`. Separatorul e `--border` intre coloane si
               `--border-strong` la granita grupei, iar linia groasa coboara
               continuu prin toate benzile (aceleasi clase in `.overlay`).
               AZI are aceeasi forma ca orice coloana, doar ca scrie „azi" in loc
               de initiala, in accent, pe tenta. Fara inel: inelul e rezervat
               zilei de sub cursor cand tragi. -->
          <div class="p-head">
            <div class="lane-label head">Proiect</div>
            {#if areRestante}<div class="rest-head">Restante</div>{/if}
            <div class="days" class:lung bind:clientWidth={pistaMasurata}>
              <div class="hd-grupe">
                {#each antet.grupe as g (g.key)}
                  <span class="hd-g" class:ultima={g.ultima} style="left:{g.leftPct}%; width:{g.widthPct}%">{g.eticheta}</span>
                {/each}
              </div>
              <div class="hd-fine">
                {#each columns.cols as c, i (c.key)}
                  <div class="col-head" class:we={unit === 'day' && plan.showWeekends && c.isWeekend}
                       class:today={i === coloanaAzi} class:granita={antet.granite.has(i)}
                       class:ultima={i === columns.cols.length - 1}
                       style="left:{c.leftPct}%; width:{c.widthPct}%">
                    <span class="ch-sub">{i === coloanaAzi ? 'azi' : c.sub}</span>
                    {#if !lung}<span class="ch-main">{c.main}</span>{/if}
                  </div>
                {/each}
              </div>
            </div>
          </div>

          <div class="p-body" class:drop-active={!!dragTask} ondragover={onBodyDragOver} ondrop={onBodyDrop} role="presentation">
            <!-- Linia de granita a antetului COBOARA prin toate benzile: fara
                 ea, randul de saptamani ar fi o eticheta care nu imparte nimic.
                 De aceea muchia se ia din acelasi `antet.granite` — o singura
                 socoteala pentru amandoua. Linia de „azi" a plecat: coloana
                 tentata o spune deja, iar fereastra pornind mereu din azi, linia
                 statea lipita de cusatura si citea ca bordura de tabel. -->
            <div class="overlay">
              {#each columns.cols as c, i (c.key)}
                <!-- `.col-line` sta pe muchia din STANGA coloanei, iar `granite`
                     tine indicele coloanei care INCHIDE o grupa (acolo se
                     ingroasa `border-right` in antet). Deci linia lui `i` e
                     granita cand `i-1` a inchis grupa — altfel linia groasa ar
                     cobori cu o coloana mai la stanga decat cea din antet. -->
                <div class="col-line" class:granita={antet.granite.has(i - 1)} style="left:{c.leftPct}%"></div>
                {#if unit === 'day' && plan.showWeekends && c.isWeekend}<div class="col-we" style="left:{c.leftPct}%; width:{c.widthPct}%"></div>{/if}
                {#if i === coloanaAzi}<div class="col-today" style="left:{c.leftPct}%; width:{c.widthPct}%"></div>{/if}
              {/each}
              {#if dropDay}
                <div class="drop-line" style="left:{dropDay.pct}%"></div>
                <div class="drop-tag" style="left:{dropDay.pct}%">{formatDateShort(dropDay.iso)}</div>
              {/if}
            </div>

            <!-- `--rand` e indicele randului, si se mosteneste in tot lane-ul:
                 benzile si reperele din el isi iau de aici decalajul de 40ms.
                 NU se numeste `--celula` (acela e pasul de 32ms al celulelor de
                 pagina, si s-ar mosteni peste orice `.cell-in` de dedesubt) si
                 nici `--i` (acela inseamna deja „randul benzii" in Calendar). -->
            {#each views as lane, li (lane.tip + ':' + lane.id)}
              <!-- Inaltimea vine din impachetare, nu invers: banda are exact
                   atatea randuri cate au iesit (vezi `geometrieBanda`). -->
              <div class="lane" style="--lane:{lane.color}; --rand:{li}; --h-lane:{lane.geo.inaltime}px; --h-stiva:{lane.geo.stiva}px" class:print-hide={exportSel.size > 0 && !exportSel.has(lane.id)}>
                <div class="lane-label">
                  {#if lane.tip === 'proiect'}
                    <button class="lane-name" onclick={(e) => morphNavigate(e.currentTarget, `/projects/${lane.id}`, 'project', lane.id)} title={lane.nume}>
                      <span class="lane-dot"></span>
                      <span class="lane-col">
                        <span class="lane-txt">{lane.nume}</span>
                        <span class="lane-contor">{lane.tasks.length}{#if lane.restante.length}{' · '}<span class="lc-rest">{lane.restante.length} {lane.restante.length === 1 ? 'restant' : 'restante'}</span>{/if}</span>
                      </span>
                    </button>
                    {#if lane.tip_proiect}<span class="tip-chip" class:svc={lane.tip_proiect === 'Service'}>{lane.tip_proiect}</span>{/if}
                  {:else}
                    <span class="lane-name static">
                      <span class="lane-dot"></span>
                      <span class="lane-col">
                        <span class="lane-txt">{lane.nume}</span>
                        <span class="lane-contor">{lane.tasks.length}{#if lane.restante.length}{' · '}<span class="lc-rest">{lane.restante.length} {lane.restante.length === 1 ? 'restant' : 'restante'}</span>{/if}</span>
                      </span>
                    </span>
                  {/if}
                </div>
                <!-- CE A SCAPAT, INTR-O COLOANA PROPRIE.
                     Un restant e inaintea ferestrei, deci `spanRect` ii da `null` si
                     nu se poate desena pe pista — pana acum asta insemna ca nu se
                     desena NICAIERI. Coloana nu costa coloane de zi, deci se poarta
                     la fel la 7 zile si la 6 luni. Clickul duce la task. -->
                {#if areRestante}
                  <div class="rest-col" class:are={lane.restante.length > 0}>
                    {#each lane.restante as t (t.tip + ':' + t.id)}
                      <!-- CU DATA SCRISA, nu un romb cu data in tooltip.
                           Un restant n-are geometrie pe pista, deci coloana asta e
                           singurul loc unde poate spune CAND a fost termenul — iar
                           „cand" e chiar informatia pentru care exista coloana.
                           Rombul o ascundea intr-un `title`, adica intr-un gest. -->
                      <button class="rest-zi" onclick={(e) => deschideTask(t, lane, e.currentTarget)}
                              title="{t.titlu} · termen {formatDateShort(t.data_scadenta)} — restant"
                              aria-label="{t.titlu} — restant din {formatDateShort(t.data_scadenta)}">{formatDateShort(t.data_scadenta)}</button>
                    {/each}
                    {#if !lane.restante.length}<span class="rest-gol" aria-hidden="true">—</span>{/if}
                  </div>
                {/if}
                <div class="lane-track">
                  {#each lane.pregatire as seg, i (i)}
                    <div class="band" class:clipL={seg.rect.clippedLeft} class:clipR={seg.rect.clippedRight}
                         class:deschis={seg.deschis} class:deschisL={seg.nesigurStart}
                         style="left:{seg.rect.left}%; width:{seg.rect.width}%"
                         title="Pregătire{seg.deschis ? ' — următoarea etapă nu e încă fixată' : ` · ${formatDateShort(seg.de)} – ${formatDateShort(seg.la)}`}"></div>
                  {/each}
                  <!-- Perioada nu e un rand pe langa taskuri — e banda randului, pe
                       toata inaltimea, ca pregatirea (Ion, 2026-07-30). Cele doua
                       benzi paveaza acelasi rand: gol = pregatire, plin = pe teren.
                       Taskurile se deseneaza PESTE. Perioadele se EDITEAZA in
                       Calendar, nu aici — clickul te duce la ziua ei. -->
                  <!-- LA ORIZONT LUNG PERIOADA E O BARA PE RANDUL INTAI.
                       La 6L cinci zile inseamna 25px: eticheta nu mai incape in
                       banda, deci iese la dreapta ei — ca titlul unui reper — iar
                       bara primeste latime minima de 11px, ca o perioada de o zi
                       sa ramana vizibila si apucabila. Nu e o exceptie de stil:
                       eticheta scoasa afara are nevoie de un RAND pe care sa stea,
                       si acela e primul (vezi `benzi` din `views`). -->
                  {#each lane.impl as im (im.id)}
                    <button class="impl-band loc-{im.locatie}" style="left:{im.rect.left}%; width:{im.rect.width}%"
                         class:pregatire={im.faza === 'pregatire'} class:doar-ico={!lung && im.rect.width < BANDA_TEXT_MIN}
                         class:lung class:flip={im.flip}
                         class:clipL={im.rect.clippedLeft} class:clipR={im.rect.clippedRight}
                         onclick={() => navigate(`/calendar?zi=${im.a}`)}
                         title="{locLabel(im.locatie)}{im.eticheta ? ' · ' + im.eticheta : ''} · {im.faza === 'pregatire' ? 'pregătire' : 'implementare'} · {formatDateShort(im.a)} → {formatDateShort(im.b)} · {im.zile} {im.zile === 1 ? 'zi' : 'zile'}{im.parti.length > 1 ? ` · ${im.parti.length} perioade lipite` : ''} · click pentru a o vedea în Calendar">
                      {#if im.locatie === 'sediu'}<Building2 size={12} class="ib-ico" />{:else}<MapPin size={12} class="ib-ico" />{/if}
                      {#if lung}
                        <span class="ib-out">{im.etichetaLunga}</span>
                      {:else}
                        {#if im.rect.width >= BANDA_TEXT_MIN}
                          <span class="ib-txt">{locLabel(im.locatie)}{im.eticheta ? ' · ' + im.eticheta : ''}</span>
                        {/if}
                        {#if im.rect.width >= BANDA_ZILE_MIN}<span class="ib-zile">{im.zile} {im.zile === 1 ? 'zi' : 'zile'}</span>{/if}
                      {/if}
                    </button>
                  {/each}
                  <div class="rows">
                    {#each lane.packed as row, ri (ri)}
                      <div class="t-row">
                        {#each row as it (it.cheie)}
                          {#if it.numar != null}
                            <!-- Numarul nu e statistica si nu deschide nimic: la
                                 orizontul asta nu exista o zi pe care sa aterizezi
                                 (fereastra porneste mereu din azi). Spune doar in ce
                                 saptamana se ingramadesc, ca sa sti unde cobori la 14z. -->
                            <span class="wk" style="left:{it.leftPct}%; width:{it.widthPct}%"
                                  title="{it.numar} {it.numar === 1 ? 'task' : 'taskuri'} în {it.eticheta}">
                              <span class="count accent">{it.numar}</span>
                            </span>
                          {:else}
                            <!-- FORMA POARTA STAREA: contur = de facut, plin = in lucru,
                                 bifa = facut. Erau trei nuante ale ACELEIASI culori de
                                 proiect (55% / 100% / 30%) — o scara pe care n-o poti
                                 citi fara sa ai toate trei alaturi, si care pe telefon
                                 spunea altceva. Contur / plin / bifa e aceeasi gramatica
                                 cu cercul gol si `CheckCircle2` din liste.
                                 `urgent` a plecat de aici: fereastra porneste din azi,
                                 deci un task de pe pista nu POATE fi restant. Rosul e
                                 acum doar in coloana din stanga, unde chiar are pe cine
                                 marca.
                                 BARA E ZIUA, TITLUL IESE DIN EA. Reperul nu mai e un
                                 romb langa un text: e chiar coloana termenului, la
                                 inaltimea randului, iar titlul incepe unde se termina
                                 ziua. De aceea impachetarea masoara suma lor. -->
                            <div
                              class="bar"
                              class:active={isActive(it.status)}
                              class:done={isDone(it.status)}
                              class:flip={it.flip}
                              class:draggable={!isDone(it.status)}
                              style="left:{it.rect.left}%; width:{it.rect.width}%"
                              role="button"
                              tabindex="0"
                              onpointerdown={(e) => startDrag(e, it, 'move', lane)}
                              onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); deschideTask(it, lane, e.currentTarget) } }}
                              title="{it.titlu}{it.data_scadenta ? ' · termen ' + formatDateShort(it.data_scadenta) : ''}"
                            >
                              <span class="bar-box">{#if isDone(it.status)}<Check size={12} strokeWidth={3} />{/if}</span>
                              <span class="bar-txt">{it.titlu}{#if it.recurenta}<Repeat size={11} class="bar-rep" />{/if}</span>
                            </div>
                          {/if}
                        {/each}
                      </div>
                    {/each}
                  </div>
                </div>
              </div>
            {/each}
          </div>
        </div>
      </div>
      <!-- „trage marginile ca să întinzi intervalul" a plecat: din v33 un task are
           O SINGURA data, deci nu are margini de tras — instructiunea promitea un
           gest care nu mai exista. Ion, intrebat: termenul ramane pur. -->
      <!-- La 3L/6L nu mai exista repere de tras: taskurile se strang intr-un
           numar pe saptamana. O indicatie care promite un gest inexistent e mai
           rea decat niciuna — te pune sa-l cauti. -->
      {#if lung}
        <p class="hint">Numărul spune câte taskuri cad în acea săptămână · coboară la 14z ca să le vezi pe zile</p>
      {:else}
        <p class="hint">Trage un reper ca să-i muți termenul · click îl deschide în panou · benzile de perioadă se editează în Calendar</p>
      {/if}
    </div>

    <!-- ===== Taskul deschis · panou lateral (4e) ===== -->
    {#if sel}
      {@const per = perioadaTaskului(sel)}
      {@const gata = pasi.filter(p => p.done).length}
      <aside class="panou" transition:panou aria-label="Detaliu task">
        <header class="pan-cap">
          <span class="pan-proiect"><span class="pan-dot" style="--lane:{laneColor(sel.laneId)}"></span>{sel.laneNume}</span>
          <button class="pan-x" onclick={closePop} aria-label="Închide"><X size={17} /></button>
        </header>

        <div class="pan-corp">
          <h2 class="pan-titlu">{sel.titlu}</h2>

          <div class="pan-fapte">
            <div class="fapt">
              <span class="fapt-et">Termen</span>
              <span class="fapt-val" class:sev={dueRing(sel.data_scadenta) !== 'var(--border)'}
                    style="--ring: {dueRing(sel.data_scadenta)}">
                {sel.data_scadenta ? formatDate(sel.data_scadenta) : 'fără termen'}
              </span>
              <Calendar size={16} class="fapt-ico" />
            </div>
            <!-- Perioada peste care cade termenul. E un CHEVRON, nu un buton de
                 editare: perioadele se schimba in Calendar, iar clicul te duce
                 chiar in ziua ei. -->
            {#if per}
              <button class="fapt link" onclick={() => navigate(`/calendar?zi=${per.a}`)}>
                <span class="fapt-et">Perioadă</span>
                <span class="fapt-val">{locLabel(per.locatie)}{per.eticheta ? ' · ' + per.eticheta : ''} · {formatDateShort(per.a)}–{formatDateShort(per.b)}</span>
                <ChevronRight size={16} class="fapt-ico" />
              </button>
            {/if}
            <div class="fapt">
              <span class="fapt-et">Repetare</span>
              <span class="fapt-val slab">{sel.recurenta || 'nu se repetă'}</span>
            </div>
          </div>

          {#if sel.nota}
            <div class="pan-sec">Notă</div>
            <p class="pan-nota">{sel.nota}</p>
          {/if}

          {#if sel.subtask_total}
            <div class="pan-sec">Pași <span class="pan-frac">{gata}/{pasi.length || sel.subtask_total}</span></div>
            {#if pasiSeIncarca && pasi.length === 0}
              <Skeleton height="30px" varianta="rand" />
            {:else}
              <ul class="pasi">
                {#each pasi as p (p.id)}
                  <li>
                    <button class="pas" class:gata={p.done} onclick={() => comutaPas(p)}>
                      <span class="pas-bifa">{#if p.done}<Check size={12} strokeWidth={3} />{:else}<span class="check-empty"></span>{/if}</span>
                      <span class="pas-txt">{p.titlu}</span>
                    </button>
                  </li>
                {/each}
              </ul>
            {/if}
          {/if}
        </div>

        <!-- „Planifică" e SelectorZi, acelasi set ca in orice foaie sau panou care
             replanifica ceva: Azi · Mâine · Alege, plus Scoate. -->
        <div class="pan-plan">
          <span class="pan-sec">Planifică</span>
          <SelectorZi value={sel.data_scadenta || ''} onalege={(v) => onMove(sel, v)} />
        </div>

        <footer class="pan-actiuni">
          <button class="pan-b prim" onclick={() => onDone(sel)}>
            <CheckCircle2 size={16} /> {isDone(sel.status) ? 'Redeschide' : 'Bifează'}
          </button>
          <button class="pan-b" onclick={() => openTask(sel)}><ExternalLink size={15} /> Deschide</button>
        </footer>
      </aside>
    {/if}
    </div>

    <!-- ===== Backlog (taskuri fără termen) ===== -->
    {#if plan.backlog.length > 0}
      <section class="backlog cell-in" style="--celula: 1" class:open={backlogOpen}>
        <button class="bl-head" onclick={() => backlogOpen = !backlogOpen} aria-expanded={backlogOpen}>
          <Inbox size={16} />
          <h2>Taskuri fără termen</h2>
          <span class="count accent" title="{plan.backlog.length} în backlog">{plan.backlog.length}</span>
          <span class="bl-hint">trage pe o zi ca să planifici</span>
          <ChevronRight size={16} class="bl-chev" />
        </button>
        {#if backlogOpen}
          <div class="bl-items">
            {#each plan.backlog as t (t.tip + ':' + t.id)}
              <div class="bl-chip"
                   draggable="true" ondragstart={(e) => backlogDragStart(e, t)} ondragend={backlogDragEnd}
                   title={t.titlu}>
                <GripVertical size={13} class="bl-grip" />
                <!-- Chipul n-are bifa si n-are chip de termen, deci severitatea
                     n-are alt canal aici: primeste punctul, ca in selectorul de
                     taskuri. Se randeaza DOAR cand spune ceva — pe neutru ar fi
                     un punct de culoarea bordurii, pe fiecare chip din sertar. -->
                {#if dueRing(t.data_scadenta) !== 'var(--border)'}
                  <span class="bl-sev" style="background: {dueRing(t.data_scadenta)}"></span>
                {/if}
                <span class="bl-txt">{t.titlu}</span>
                {#if t.proiect_nume}<span class="bl-proj">{t.proiect_nume}</span>{:else if t.categorie}<span class="bl-proj glob">{t.categorie}</span>{/if}
                <span class="bl-date"><DatePicker value="" placeholder="Planifică" onchange={(v) => scheduleFromPicker(t, v)} /></span>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    <!-- ===== Mobile grouped list ===== -->
    <div class="mlist cell-in" style="--celula: 2">
      <!-- ANTETUL DE ZILE, COMUN SI LIPICIOS.
           Fara el, benzile de mai jos ar fi N grafice fara legatura: fiecare
           frumoasa in sine, niciuna comparabila cu vecina. Fiind acelasi interval
           si aceeasi scara pentru toate, o coloana inseamna aceeasi zi peste tot,
           iar derularea pe verticala devine exact ce facea ochiul pe desktop cand
           coborai de la un lane la altul. -->
      <!-- SCARA SPUNE SI CE ZI E, NU DOAR A CATA.
           Erau paisprezece cifre la rand, fara nicio initiala: weekendul se vedea
           doar daca „Weekend" era pornit — un comutator dintr-o bara care pe 390px
           se rupe pe trei randuri. Initiala exista deja in `buildColumns` (`c.sub`),
           deci nu e un calcul nou: douazeci si sase de pixeli in loc de paisprezece,
           o singura data pe ecran. Doar la orizonturile pe ZILE — pe saptamani si
           luni `sub` e „S32" / anul, care n-ar spune ce zi e. -->
      <div class="m-scale" class:cu-wd={unit === 'day'}>
        <div class="ms-cols">
          {#each mCols as c (c.key)}
            <span class="ms-c" class:we={unit === 'day' && plan.showWeekends && c.isWeekend}
                  class:today={contineAzi(c)}
                  style="left:{c.leftPct}%; width:{c.widthPct}%">
              <span class="ms-n">{c.main}</span>
              {#if unit === 'day'}<span class="ms-wd">{c.sub}</span>{/if}
            </span>
          {/each}
        </div>
      </div>

      <!-- `.band` si `.impl-band` sunt aceleasi clase ca pe desktop, deci pista
           mobila mosteneste sosirea din 13e fara nicio regula in plus — ii trebuie
           doar indicele randului, ca decalajul sa urmeze grupurile. -->
      {#each views as lane, li (lane.tip + ':' + lane.id)}
        {@const per = perioadaDeAratat(lane)}
        <section class="mgroup" style="--lane:{lane.color}; --rand:{li}">
          <header class="mg-head">
            <span class="lane-dot"></span>
            <h2>{lane.nume}</h2>
            {#if lane.tip_proiect}<span class="tip-chip" class:svc={lane.tip_proiect === 'Service'}>{lane.tip_proiect}</span>{/if}
            <!-- Doua pastile, nu un sir „5 · 2": tonul spune care e care, ca peste tot. -->
            <span class="count" title="{lane.tasks.length} taskuri">{lane.tasks.length}</span>
            {#if lane.restante.length}<span class="count danger" title="{lane.restante.length} restante">{lane.restante.length}</span>{/if}
          </header>

          <!-- BANDA = LANE-UL DE PE DESKTOP, INTORS LA LATIME PLINA.
               Pe desktop numele sta la STANGA si timpul se intinde in dreapta lui;
               pe un ecran de 375px coloana de nume ar manca doua treimi, de aceea
               swimlane-ul era pur si simplu ascuns si ramanea o lista fara timp.
               Numele urca deasupra, banda ia toata latimea, iar grupurile se
               stivuiesc pe verticala — directia in care telefonul chiar are loc.
               Geometria e aceeasi: `spanRect` da procente, deci merge la orice
               latime, fara niciun calcul nou. -->
          <div class="m-track">
            {#each columns.cols as c (c.key)}
              {#if unit === 'day' && plan.showWeekends && c.isWeekend}
                <div class="mt-we" style="left:{c.leftPct}%; width:{c.widthPct}%"></div>
              {/if}
            {/each}
            {#each lane.pregatire as seg, i (i)}
              <div class="band" class:clipL={seg.rect.clippedLeft} class:clipR={seg.rect.clippedRight}
                   class:deschis={seg.deschis} class:deschisL={seg.nesigurStart}
                   style="left:{seg.rect.left}%; width:{seg.rect.width}%"></div>
            {/each}
            {#each lane.impl as im (im.id)}
              <button class="impl-band loc-{im.locatie}" style="left:{im.rect.left}%; width:{im.rect.width}%"
                      class:pregatire={im.faza === 'pregatire'}
                      class:clipL={im.rect.clippedLeft} class:clipR={im.rect.clippedRight}
                      onclick={() => navigate(`/calendar?zi=${im.a}`)}
                      title="{locLabel(im.locatie)}{im.eticheta ? ' · ' + im.eticheta : ''} · {formatDateShort(im.a)} → {formatDateShort(im.b)}">
                {#if im.locatie === 'sediu'}<Building2 size={11} class="ib-ico" />{:else}<MapPin size={11} class="ib-ico" />{/if}
                {#if im.rect.width >= BANDA_TEXT_MIN}
                  <span class="ib-txt">{im.eticheta || locLabel(im.locatie)}</span>
                {/if}
              </button>
            {/each}
            <!-- Un task e un REPER de o zi (v33), deci un punct — nu o bara pe
                 care s-o intinzi. Atingerea nu deschide un al treilea meniu: te
                 duce la randul lui din lista de dedesubt, unde stau deja toate
                 actiunile. Punctul spune CAND, randul spune CE si CU CE butoane. -->
            <!-- Aceeasi gramatica ca pe desktop: gol = de facut, plin = in lucru,
                 bifa = facut. Aici „facut" era VERDE, deci acelasi task avea o
                 stare pe telefon si alta pe ecranul mare. `urgent` a plecat: pe o
                 banda care incepe azi nu poate exista reper restant — restantele
                 sunt primul GRUP din lista de dedesubt. -->
            {#each lane.tasks as t (t.tip + ':' + t.id)}
              {#if t.rect}
                <button class="mt-pin" class:done={isDone(t.status)} class:lucru={isActive(t.status)}
                        style="left:{t.rect.left}%"
                        onclick={() => arata(t)}
                        title="{t.titlu}{t.data_scadenta ? ' · termen ' + formatDateShort(t.data_scadenta) : ''}"
                        aria-label="{t.titlu} — vezi în listă">{#if isDone(t.status)}<Check size={11} strokeWidth={3.2} />{/if}</button>
              {/if}
            {/each}
            {#if todayPct != null && todayPct >= 0 && todayPct < 100}
              <div class="mt-azi" style="left:{todayPct}%"></div>
            {/if}
          </div>

          <!-- Randul perioadei e si tinta ei: in banda de 26px un bloc de doua
               zile are 23×20px, adica prea putin ca sa-l nimeresti. Aici are
               latimea intreaga si duce in Calendar, unde perioadele se editeaza.
               UN SINGUR RAND, nu cate unul per perioada — vezi `perioadaDeAratat`. -->
          {#if per}
            <button class="mimpl loc-{per.im.locatie}" class:pregatire={per.im.faza === 'pregatire'}
                    onclick={() => navigate(`/calendar?zi=${per.im.a}`)}
                    title="{lane.impl.length > 1 ? `${lane.impl.length} perioade în fereastră — ` : ''}vezi în Calendar">
              <span class="mimpl-loc">{locLabel(per.im.locatie)}{per.im.eticheta ? ' · ' + per.im.eticheta : ''}</span>
              <span class="mimpl-range">
                {formatDateShort(per.im.a)} – {formatDateShort(per.im.b)}
                {#if per.rest > 0}<span class="mimpl-plus">+{per.rest}</span>{/if}
              </span>
            </button>
          {/if}

          {#each grupeazaBanda(lane) as g (g.id)}
            <div class="mgrup-cap ton-{g.ton}"><span>{g.titlu}</span><span class="grup-n">{g.items.length}</span></div>
            {#each g.items as t (t.tip + ':' + t.id)}
            <!-- Acelasi rand ca pe „Astazi": o linie, bifa in stanga, actiunile
                 in panoul de sub el (glisare spre stanga). Doua liste care arata
                 acelasi lucru trebuie sa se poarte la fel — altfel inveti gestul
                 de doua ori. -->
            <div class="mrow" data-rand="{t.tip}:{t.id}" style="--ring: {dueRing(t.data_scadenta)}"
                 class:done={isDone(t.status)}
                 use:glisare={{ latime: 118, activ: true, onBifa: isDone(t.status) ? null : () => onDone(t) }}>
              <div class="gl-pista" aria-hidden="true"><span class="gl-ico"><Check size={17} strokeWidth={3} /></span><span class="gl-et">Făcut</span></div>
              <div class="gl-actiuni">
                <button class="glb" onclick={() => onTomorrow(t)} title="Mută pe mâine"><ArrowRight size={17} /><span>Mâine</span></button>
                <span class="glb datewrap" title="Mută pe altă zi">
                  <DatePicker value={t.data_scadenta} placeholder="Dată" onchange={(v) => onMove(t, v)} />
                  <span>Dată</span>
                </span>
              </div>
              <div class="gl-fata">
                <button class="mcheck" onclick={() => onDone(t)} title="Bifează">
                  {#if isDone(t.status)}<CheckCircle2 size={18} />{:else}<span class="check-empty"></span>{/if}
                </button>
                <button class="mrow-main" onclick={(e) => openTask(t, e.currentTarget)}>
                  <span class="mrow-title">{t.titlu}</span>
                  <!-- ADAPTAT, nu copiat. Ordinea si semnele sunt cele din /tasks
                       si de pe „Astăzi" — intai CAND, apoi CAT — dar data ramane
                       ABSOLUTA („27.07"), nu relativa („acum 4 zile"): randul sta
                       lipit de o grila de zile, iar o data relativa langa o coloana
                       care arata ziua exacta te pune sa faci conversia in cap.
                       Ce se aliniaza cu restul e CULOAREA: termenul se coloreaza
                       dupa severitate, nu mereu amber, ca peste tot. -->
                  <span class="mrow-meta">
                    {#if t.data_scadenta}
                      <!-- Conditia vine din ACEEASI functie care da `--ring`, nu
                           din `esteAzi`/`esteRestant` (care se raporteaza la
                           `plan.today`, ziua serverului): altfel chipul se putea
                           colora cand inelul nu era colorat, si invers. -->
                      <span class="chip due" class:sev={dueRing(t.data_scadenta) !== 'var(--border)'}>
                        <CalendarDays size={10} />{formatDateShort(t.data_scadenta)}
                      </span>
                    {/if}
                    {#if t.subtask_total}
                      <span class="tsub-chip" class:gata={t.subtask_done === t.subtask_total}
                            title="{t.subtask_done || 0} din {t.subtask_total} subtaskuri făcute">
                        <ListChecks size={10} />{t.subtask_done || 0}/{t.subtask_total}
                      </span>
                    {/if}
                    {#if t.recurenta}<span class="chip"><Repeat size={10} /> {t.recurenta}</span>{/if}
                  </span>
                </button>
                <div class="mrow-actions">
                  <button class="mbtn" onclick={() => onTomorrow(t)} title="Mută pe mâine"><ArrowRight size={15} /></button>
                  <span class="mrow-date"><DatePicker value={t.data_scadenta} placeholder="Mută" onchange={(v) => onMove(t, v)} /></span>
                  <button class="mbtn" onclick={() => onDone(t)} title="Bifează"><CheckCircle2 size={16} /></button>
                </div>
              </div>
            </div>
            {/each}
          {/each}
        </section>
      {/each}
    </div>
  {/if}
</div>

{#if dragLabel}
  <div class="drag-label" style="left:{dragLabel.x + 14}px; top:{dragLabel.y - 34}px">{dragLabel.text}</div>
{/if}

<Modal bind:open={showExport} title="Export PDF" size="sm">
  <div class="exp">
    <p class="exp-note">Se deschide dialogul de printare al browserului — alege <b>„Salvează ca PDF"</b>. Fereastra exportată: <b>{exportRange}</b>.</p>
    <div class="exp-scope">
      <div class="exp-scope-head">
        <span>Proiecte</span>
        <button class="exp-all" onclick={toggleExportAll}>{exportSel.size === plan.lanes.length ? 'Deselectează' : 'Toate'}</button>
      </div>
      <div class="exp-list">
        {#each plan.lanes as l (l.tip + ':' + l.id)}
          <label class="exp-row">
            <input type="checkbox" checked={exportSel.has(l.id)} onchange={() => toggleExportLane(l.id)} />
            <span class="exp-dot" style="background:{laneColor(l.id)}"></span>
            <span class="exp-name">{l.nume}</span>
          </label>
        {/each}
      </div>
    </div>
    <label class="exp-opt">
      <input type="checkbox" bind:checked={exportPageBreak} />
      <span>Câte un proiect pe pagină</span>
    </label>
  </div>
  {#snippet footer()}
    <div class="modal-actions">
      <button class="btn-ghost" onclick={() => showExport = false}>Anulează</button>
      <button class="btn-primary" onclick={runExport} disabled={exportSel.size === 0}><FileDown size={14} /> Exportă</button>
    </div>
  {/snippet}
</Modal>

<style>
  .page { padding-bottom: 96px; }
  .page-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); margin-bottom: var(--space-md); flex-wrap: wrap; }
  /* Subtitlul sta pe LINIA DE BAZA a titlului, nu pe mijlocul lui: e continuarea
     propozitiei „Planificator", nu o eticheta pusa alaturi. Iconita se recentreaza
     singura — baza unui svg e muchia lui de jos, deci s-ar fi infipt in text. */
  .page-title-row { display: flex; align-items: baseline; gap: var(--space-sm); color: var(--text); }
  .page-title-row :global(svg) { align-self: center; }
  .page-title-row h1 { font-size: var(--font-title); font-weight: var(--fw-semibold); font-family: var(--font-heading); letter-spacing: var(--tracking-tight); }
  .page-sub { font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-secondary); white-space: nowrap; }
  .controls { display: flex; align-items: center; gap: var(--space-sm); }
  .seg { display: inline-flex; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 2px; }
  .seg-btn { padding: 5px 11px; border-radius: var(--radius-sm); font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-dim); background: none; border: none; cursor: pointer; transition: color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease); }
  .seg-btn:hover { color: var(--text); }
  .seg-btn.active { background: var(--accent); color: var(--accent-text); }
  .toggle { display: inline-flex; align-items: center; gap: 7px; padding: 6px 12px; font-size: var(--font-small); font-weight: var(--fw-medium); border-radius: var(--radius-md); background: var(--bg-panel); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; }
  .toggle:hover { border-color: var(--border-strong); color: var(--text); }
  .toggle.on { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 45%, transparent); }
  .toggle:disabled { opacity: 0.4; cursor: not-allowed; }
  /* 4px nu e o treapta din scara (8 chip · 10 control · 14 suprafata · 20 foaie).
     Cercul e rezervat bifei de task; asta e o casuta de filtru, deci ramane
     patrata si ia treapta cea mai mica. */
  .tk-box { width: 16px; height: 16px; border-radius: var(--radius-xs); border: 1.5px solid var(--border-strong); display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .toggle.on .tk-box { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }
  .skel { display: flex; flex-direction: column; gap: var(--space-sm); }

  /* ===== chart shell ===== */
  /* `--row-h` e inaltimea unui RAND DE REPERE, si e chiar 20-ul din formula de
     inaltime a benzii (`geometrieBanda`). Se schimba impreuna. */
  .chart { --lane-w: 240px; --rest-w: 0px; --day-min: 48px; --row-h: 20px;
    background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); overflow: hidden; }
  .chart-scroll { overflow-x: auto; }
  .inner { position: relative; }

  /* ===== ANTETUL DE TIMP: GROSIER PESTE FIN =====
     Doua randuri intr-o singura structura, 52px. Cele trei celule din capul
     tabelului (Proiect · Restante · pista) se aliniaza LA BAZA, ca eticheta lor
     sa stea pe aceeasi linie cu randul de zile, nu la mijlocul a doua randuri. */
  .p-head { display: flex; border-bottom: 1px solid var(--border); background: var(--bg-overlay); position: sticky; top: 0; z-index: 3; }
  .lane-label { width: var(--lane-w); flex-shrink: 0; box-sizing: border-box; }
  .lane-label.head { padding: 0 14px 8px; font-size: var(--font-label); font-weight: var(--fw-semibold); letter-spacing: var(--tracking-label); text-transform: uppercase; color: var(--text-dim); display: flex; align-items: flex-end; }
  /* Coloana restantelor: lipita la stanga pistei, latime fixa, nu costa zile.
     Antetul ei e singurul loc din grafic unde a mai ramas rosu. */
  .rest-head { width: var(--rest-w); flex: none; box-sizing: border-box;
    display: flex; align-items: flex-end; justify-content: center;
    padding: 0 6px 8px; border-left: 1px solid var(--border);
    background: var(--danger-subtle); color: var(--danger);
    font-family: var(--font-mono); font-size: var(--font-label);
    letter-spacing: var(--tracking-label); text-transform: uppercase; }
  .days { flex: 1; position: relative; min-width: 0; height: 52px; display: flex; flex-direction: column; }
  /* Randul grosier. Nu-si calculeaza singur muchiile: le mosteneste din coloanele
     fine (vezi `grupeazaColoane`), altfel doua socoteli ale aceleiasi margini se
     despart la a treia zecimala — si se vede, fiindca linia groasa coboara prin
     toate benzile de dedesubt. */
  .hd-grupe { position: relative; height: 20px; flex: none; }
  .hd-g { position: absolute; top: 0; bottom: 0; box-sizing: border-box;
    display: flex; align-items: center; justify-content: center;
    border-right: 1px solid var(--border-strong);
    font-size: var(--font-label); font-weight: var(--fw-semibold);
    letter-spacing: var(--tracking-label); text-transform: uppercase;
    color: var(--text-dim); white-space: nowrap; overflow: hidden; }
  .hd-g.ultima { border-right: 0; }
  /* Codurile de saptamana sunt cifre care se compara pe verticala, deci mono;
     numele de luna e un cuvant care s-ar putea traduce, deci nu. */
  .days:not(.lung) .hd-g { font-family: var(--font-mono); }
  .hd-fine { position: relative; flex: 1; min-height: 0; }
  .col-head { position: absolute; top: 0; bottom: 0; box-sizing: border-box; padding: 0 2px;
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1px;
    border-right: 1px solid var(--border); overflow: hidden; }
  .col-head.granita { border-right-color: var(--border-strong); }
  .col-head.ultima { border-right: 0; }
/* WEEKENDUL E O SUPRAFATA, NU O CULOARE.
     Tinta era `--purple` — adica movul decorativ, care a iesit din sistem si e
     acum un alias catre accent. Cu el, sambata si duminica ar fi purtat exact
     cerneala pe care grila o foloseste ca sa spuna „aici e ceva planificat":
     doua zile libere colorate ca o zi de lucru. Weekendul nu e o stare, e o
     absenta — deci se deseneaza cu suprafata a doua, nu cu o culoare. */
  .col-head.we { background: var(--bg-elevated); }
  /* AZI ARE ACEEASI FORMA CA ORICE COLOANA — scrie doar „azi" in loc de
     initiala, in accent, pe tenta. Fara inel: inelul e rezervat zilei de sub
     cursor cand tragi, si daca l-ar purta si azi n-ai mai sti care e care. */
  .col-head.today { background: var(--accent-subtle); }
  .ch-sub { font-size: var(--font-label); color: var(--text-dim); text-transform: uppercase; letter-spacing: var(--tracking-label); white-space: nowrap; }
  .days.lung .ch-sub { font-family: var(--font-mono); }
  .col-head.today .ch-sub { color: var(--accent-on-subtle); font-weight: var(--fw-semibold); }
  .ch-main { font-family: var(--font-mono); font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-secondary); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .col-head.we .ch-main { color: var(--text-dim); }
  .col-head.today .ch-main { color: var(--accent-on-subtle); font-weight: var(--fw-semibold); }

  .p-body { position: relative; }
  .overlay { position: absolute; top: 0; bottom: 0; left: calc(var(--lane-w) + var(--rest-w)); right: 0; pointer-events: none; z-index: 0; }
  .col-line { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--border-subtle); }
  /* Granita de grupa coboara din antet prin toate benzile — altfel randul de
     saptamani ar fi o eticheta care nu imparte nimic. */
  .col-line.granita { background: var(--border-strong); }
  .col-we { position: absolute; top: 0; bottom: 0; background: var(--bg-elevated); }
  /* AZI E O COLOANA, NU O LINIE: aceeasi forma ca in antet, un nivel mai jos —
     tenta, cu doua muchii de accent. Linia de 2px a plecat fiindca fereastra
     porneste mereu din azi, deci statea la `left: 0`, lipita de cusatura, unde
     citea ca bordura de tabel. */
  .col-today { position: absolute; top: 0; bottom: 0;
    background: color-mix(in srgb, var(--accent) 6%, transparent);
    box-shadow: inset 1px 0 0 var(--accent-ring), inset -1px 0 0 var(--accent-ring); }

  /* Inaltimea vine din impachetare (`--h-lane`, pusa din markup): 14 sus,
     n randuri de 20 cu 4 intre ele, 6 jos, minim 48. */
  .lane { display: flex; border-bottom: 1px solid var(--border); min-height: var(--h-lane, 48px); }
  .lane:last-child { border-bottom: 0; }
  /* COLOANA DE NUME TREBUIE SA INCAPA IN RANDUL FORMULEI.
     Numele statea pe DOUA randuri (fix pentru „toate 9 erau taiate"), plus randul
     contorului: 73px. Cu `min-height: 48px` pe banda, inaltimea nu mai venea din
     impachetare, ci din eticheta — deci o banda cu un reper si una cu trei aratau
     la fel, si tocmai asta trebuia sa spuna inaltimea.
     Numele revine pe UN rand, ca in fisierul de design, si asta nu reintoarce
     problema veche: numele reale se despart de la primele caractere („Migrare
     CU240S…", „Contrapanou A12…", „Parametrizare 3WA…"), iar partea care se
     repeta e SUFIXUL de client („— Continental"), adica exact ce pierde o
     trunchiere la dreapta. */
  .lane-label { padding: 0 12px; display: flex; align-items: center; gap: 8px; border-right: 1px solid var(--border); background: var(--bg-surface); z-index: 1; }
  .lane-name { display: flex; align-items: center; gap: 8px; min-width: 0; color: var(--text); cursor: pointer; background: none; border: none; text-align: left; font-size: var(--font-body); font-weight: var(--fw-medium); }
  .lane-name.static { cursor: default; }
  .lane-name:not(.static):hover .lane-txt { color: var(--accent); }
  .lane-col { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
  /* Cate taskuri are banda in fereastra si cate au scapat inaintea ei. Numarul de
     restante e singurul lucru colorat: e cel care cere ceva. */
  .lane-contor { font-family: var(--font-mono); font-size: var(--font-small); color: var(--text-faint); font-variant-numeric: tabular-nums; }
  .lc-rest { color: var(--danger); }
  /* PUNCT PLAT, FARA HALO. Glowul colorat e interzis explicit — si aici statea pe
     identitatea de proiect, adica stralucea exact lucrul care nu cere nimic.
     Punctul spune „care proiect", nu „uita-te la mine". */
  .lane-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--lane); flex-shrink: 0; }
  .lane-txt { min-width: 0; line-height: var(--lh-snug); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* CHIP NEUTRU PENTRU AMANDOUA. PIF si Service se deosebeau prin doua cerneli
     inrudite pe acelasi fundal (`--accent` vs `--accent-deep`) — o diferenta care
     pur si simplu nu se citeste, iar prima incalca si regula cernelii pe tenta.
     Tipul e SCRIS in chip, deci cuvantul il spune; culoarea n-are ce adauga.
     (In Proiecte tipul e deja o iconita gri, fara fill — aceeasi solutie.) */
  .tip-chip { font-size: var(--font-small); padding: 1px 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-secondary); flex-shrink: 0; }

  /* Jgheabul restantelor. Reperele stau centrate si se inghesuie cand sunt multe:
     numarul exact e scris in coloana de nume, aici conteaza ca EXISTA. */
  .rest-col { width: var(--rest-w); flex: none; box-sizing: border-box;
    display: flex; align-items: center; justify-content: center; gap: 6px;
    flex-wrap: wrap; padding: 6px 8px; border-right: 1px solid var(--border);
    background: var(--bg-surface); z-index: 1; }
  .rest-col.are { background: color-mix(in srgb, var(--danger) 6%, var(--bg-surface)); }
  /* Data scrisa, ca un chip de termen — nu un romb care o ascunde in tooltip.
     Cerneala e `--danger-deep`, fiindca sta pe tenta de restant. */
  .rest-zi { flex: none; padding: 0 7px; height: 19px; border-radius: var(--radius-xs);
    background: var(--danger-subtle); color: var(--danger-deep);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--danger) 34%, transparent);
    border: none; font-family: var(--font-mono); font-size: var(--font-label);
    font-weight: var(--fw-medium); font-variant-numeric: tabular-nums; white-space: nowrap;
    cursor: pointer; transition: var(--transition-pressable); }
  .rest-zi:hover { box-shadow: inset 0 0 0 1px var(--danger); }
  .rest-zi:active { transform: scale(var(--press-scale)); }
  .rest-gol { font-size: var(--font-small); color: var(--text-faint); }

  /* STIVA DE REPERE E CENTRATA IN CHENARUL PERIOADEI, CU ACELEASI MARGINI.
     Benzile stau la 7px sus si jos; daca stiva ar avea alt inset, ultimul reper
     ar iesi sub chenarul benzii pe care se sprijina — si atunci banda n-ar mai
     citi ca fundalul randului, ci ca inca un obiect care se intampla sa fie pe
     acolo. `justify-content: center` distribuie surplusul de 6px al formulei
     egal sus si jos. */
  .lane-track { flex: 1; position: relative; min-width: 0; padding: 7px 0;
    display: flex; flex-direction: column; justify-content: center; }

  /* ===== SOSIREA PISTEI (tura 13e) =====
     CE ARE INCEPUT, CRESTE DIN EL. CE DOAR ACOPERA UN INTERVAL, APARE.
     Pe un rand stau trei lucruri, si pana acum toate trei apareau intre doua
     cadre. Dar nu sunt de acelasi fel, deci nu pot sosi la fel:
       · `.impl-band` — o perioada cu o zi de start REALA. Se descopera de la
         stanga la dreapta, adica dinspre ziua in care incepe: miscarea spune
         chiar lucrul pe care banda il codifica prin pozitie.
       · `.band` (pregatirea) — NU are inceput. `segmentePregatire` porneste de
         la marginea ferestrei fiindca „de cand se pregateste" nu se sti, si
         capatul stang e estompat tocmai ca sa spuna asta. Daca ar creste din
         stanga, miscarea ar afirma o zi de start pe care desenul o neaga la un
         centimetru mai jos. Deci doar se stinge in ecran — e fundal.
       · `.bar` — un reper de o zi (v33). N-are latime de intins, deci creste
         PE LOC, din punctul lui: `transform-origin: left` e chiar ziua lui.

     `backwards`, nu `forwards`: `clip-path` se intoarce la `none` cand animatia
     se termina. Cu `forwards` ar ramane inghetat pe `inset(0 0 0 0)`, care taie
     la border-box — adica ar sterge definitiv umbra exterioara a blocului.
     `backwards` tine doar cadrul de start pe durata intarzierii, ca banda sa nu
     clipeasca la latime plina inainte sa-i vina randul.

     Decalajul e pe RAND, nu pe banda: doua perioade ale aceluiasi proiect sunt
     acelasi lucru vazut de doua ori pe axa timpului, nu doua sosiri. */
  @keyframes benziIn {
    from { opacity: 0; clip-path: inset(0 100% 0 0); }
    to { opacity: 1; clip-path: inset(0 0 0 0); }
  }
  @keyframes pregatireIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes reperIn {
    from { opacity: 0; transform: scale(0.62); }
    to { opacity: 1; transform: none; }
  }
  /* Anularea la reduced-motion sta LA SFARSITUL foii, dupa `.bar` — media query-ul
     nu adauga specificitate, deci ar fi pierdut aici in fata regulii de mai jos. */

  .band { position: absolute; top: 7px; bottom: 7px; border-radius: var(--radius-xs);
    background: color-mix(in oklab, var(--accent) 10%, transparent);
    border: 1px solid color-mix(in oklab, var(--accent) 26%, transparent); z-index: 0;
    animation: pregatireIn var(--dur-base) var(--ease) backwards;
    animation-delay: min(var(--rand, 0) * 40ms, 280ms); }
  .band.clipL { border-top-left-radius: 0; border-bottom-left-radius: 0; border-left: 0; }
  .band.clipR { border-top-right-radius: 0; border-bottom-right-radius: 0; border-right: 0; }
  /* CAPATUL NESIGUR SE STINGE, CEL SIGUR RAMANE NET.
     Nesigur e START-ul: nu exista o zi „de cand se pregateste" (v36). Capatul din
     dreapta e prima zi de implementare — data reala, deci muchie clara. Cand nu e
     fixata nicio etapa, si dreapta e nesigura, deci se sting amandoua. Estomparea
     e pe o distanta FIXA, ca sa arate la fel si pe o banda de trei zile si pe una
     de trei luni. */
  .band.deschisL { border-left: 0; border-top-left-radius: 0; border-bottom-left-radius: 0;
    -webkit-mask-image: linear-gradient(to right, transparent 0, #000 56px);
    mask-image: linear-gradient(to right, transparent 0, #000 56px); }
  .band.deschis { border-right: 0; border-top-right-radius: 0; border-bottom-right-radius: 0;
    -webkit-mask-image: linear-gradient(to left, transparent 0, #000 56px);
    mask-image: linear-gradient(to left, transparent 0, #000 56px); }
  .band.deschis.deschisL {
    -webkit-mask-image: linear-gradient(to right, transparent 0, #000 56px, #000 calc(100% - 56px), transparent 100%);
    mask-image: linear-gradient(to right, transparent 0, #000 56px, #000 calc(100% - 56px), transparent 100%); }
  /* Taskurile stau peste benzi, deci randurile lasa clickul sa treaca prin golul
     dintre bare pana la banda de dedesubt. */
  .rows { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 4px; pointer-events: none; }
  .t-row { position: relative; height: var(--row-h); }
  /* Perioada de implementare (Site / Sediu EGB) — banda pe toata inaltimea randului,
     exact insetul benzii de pregatire, ca cele doua sa se imbine fara decalaj.
     FORMA spune faza: palid = pregatire, plin = implementare. Locul NU se
     codifica cromatic (se scrie, cu iconita si eticheta) — aceeasi gramatica ca
     in Calendar si in Ganttul de proiect.
     Inelul interior tine despartite doua benzi lipite de categorii diferite;
     doua perioade de aceeasi categorie sunt deja UN element (vezi `contopeste`),
     deci n-au cusatura. Inceputul se citeste din raza si din marginea benzii. */
  /* Eticheta sta LA CAPUL benzii, nu la mijlocul ei: ea ocupa randul intai al
     impachetarii (vezi `benzi` din `views`), deci trebuie sa fie chiar acolo
     unde impachetarea o crede — altfel reperele coboara pentru un text care
     pluteste cu doua randuri mai jos. */
  /* BANDA E O SUPRAFATA IN ACCENT, NU UN BLOC LUCIOS.
     Era desenata ca un bloc cu degrade pe verticala, inel alb si umbra proprie,
     in tokenurile de locatie — care dupa redesign sunt GRI NEUTRU.
     Deci pe ecran iesea o pastila gri-metalica: un gradient (interzis explicit),
     o umbra care o ridica peste randul ei, si singura culoare din pista care nu
     spunea nimic. Locul nu se mai codifica cromatic — se SCRIE, cu iconita si
     eticheta („Sediu EGB · 3 zile"). Ce ramane e tenta de accent cu inelul ei. */
  .impl-band { position: absolute; top: 7px; bottom: 7px; display: flex; align-items: flex-start; gap: 5px;
    padding: 3px 9px 0 11px; border-radius: var(--radius-sm); overflow: hidden; z-index: 0; text-align: left;
    color: var(--accent-deep); border: none;
    background: color-mix(in srgb, var(--accent) 10%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 32%, transparent);
    cursor: pointer; pointer-events: auto; transition: var(--transition-colors);
    /* Se descopera, nu se intinde: `scaleX` ar turti textul dinauntru la jumatate
       de latime pe la mijlocul miscarii, iar o eticheta care se lateste inapoi la
       normal se citeste ca elastic, nu ca o perioada care incepe. */
    animation: benziIn var(--dur-base) var(--ease) backwards;
    animation-delay: min(var(--rand, 0) * 40ms, 280ms); }
  /* FORMA spune faza, o singura axa de culoare: implementarea e tenta plina de
     mai sus, pregatirea e mai palida, cu inelul ei. Amandoua pe accent. */
  .impl-band.pregatire { background: color-mix(in srgb, var(--accent) 5%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 22%, transparent); }
  /* Taiata de fereastra: muchie dreapta, fara bara de intrare — ziua de start nu e
     acolo, e mai devreme. Deci nici sosirea nu poate porni de acolo: descoperirea
     din stanga ar arata un inceput fix in locul in care muchia dreapta spune
     „continua din afara ecranului". Ramane stingerea, ca la pregatire. */
  .impl-band.clipL { border-top-left-radius: 0; border-bottom-left-radius: 0; border-left-width: 0;
    animation-name: pregatireIn; }
  .impl-band.clipR { border-top-right-radius: 0; border-bottom-right-radius: 0; }
  .impl-band:hover { background: color-mix(in srgb, var(--accent) 16%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 48%, transparent); }
  .impl-band :global(.ib-ico) { flex: none; opacity: 0.72; margin-top: 2px; }
  /* LA ORIZONT LUNG, O BARA PE RANDUL INTAI.
     `50% - stiva/2` e chiar coordonata randului intai: stiva de repere e
     centrata in pista, iar pista are acelasi inset sus si jos (7px). Se
     calculeaza asa, si nu din inaltimea benzii, fiindca banda poate creste sub
     coloana de nume — vezi `geometrieBanda`. */
  .impl-band.lung { top: calc(50% - var(--h-stiva, 20px) / 2); bottom: auto; height: var(--row-h);
    min-width: 11px; padding: 0; gap: 0; align-items: center; justify-content: center;
    border-radius: var(--radius-xs); overflow: visible; }
  .impl-band.lung :global(.ib-ico) { margin-top: 0; }
  /* Eticheta iese la dreapta barei, ca titlul unui reper — la 6L nici cinci zile
     n-au latime de text. Ea E ce tine randul intai in impachetare, deci se
     masoara si acolo (`benzi`). */
  .ib-out { position: absolute; left: 100%; top: 0; height: var(--row-h);
    display: flex; align-items: center; padding-left: 7px; white-space: nowrap;
    font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text-secondary);
    text-shadow: 0 0 3px var(--bg-surface), 0 0 6px var(--bg-surface); }
  .impl-band.flip .ib-out { left: auto; right: 100%; padding-left: 0; padding-right: 7px; }
  /* O zi, la 30 de zile fereastra, are 38px: nu incape nici „Si…". Ramane icoana,
     centrata, si tot tooltipul. */
  .impl-band.doar-ico { padding: 0 2px; justify-content: center; }
  .ib-txt { font-size: var(--font-small); font-weight: var(--fw-semibold); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* NUMARUL DE ZILE STA LIPIT DE TITLU, NU LA MARGINEA DIN DREAPTA.
     Avea `margin-left: auto`, adica exact ce interzice regula: impins in capatul
     benzii, cadea peste eticheta reperului care incepe imediat dupa ea. Lipit de
     titlu, ocupa spatiul pe care impachetarea l-a rezervat deja pentru banda.
     Fara `opacity` (regula sistemului): tonul il da culoarea, nu stingerea. */
  .ib-zile { flex: none; padding-left: 2px; font-family: var(--font-mono);
    font-size: var(--font-small); font-variant-numeric: tabular-nums;
    color: color-mix(in srgb, var(--on-color) 62%, transparent); white-space: nowrap; }
  /* Dunga de identitate a plecat: randul e DEJA umplut cu aceeasi culoare si are
     si eticheta de locatie colorata in ea. Cei 3px se intorc in padding. */
  .mimpl { display: flex; align-items: center; justify-content: space-between; gap: 8px; width: 100%; text-align: left; border: none; cursor: pointer; padding: 6px 10px 6px 13px; border-radius: var(--radius-md); background: color-mix(in srgb, var(--accent) 10%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 32%, transparent); margin-bottom: 6px; }
  /* Aceeasi a doua axa ca pe desktop: pregatirea e conturata, nu plina. */
  .mimpl.pregatire { background: color-mix(in srgb, var(--accent) 5%, transparent); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 22%, transparent); }
  .mimpl-loc { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--accent-deep); }
  .mimpl-range { display: inline-flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: var(--font-small); color: var(--text-dim); }
  /* „+N" = restul perioadelor din fereastra, care inainte ocupau cate un rand de
     44px fiecare, inaintea primului task. Duc toate in acelasi loc — Calendar. */
  .mimpl-plus { padding: 0 5px; border-radius: var(--radius-full);
    background: var(--accent-subtle); color: var(--accent-on-subtle); }

  /* Capetele de grup din lista mobila. Aceeasi haina si acelasi limbaj de culoare
     ca `.grup-cap` din /tasks — o singura gramatica pentru „ce urmeaza". */
  .mgrup-cap { display: flex; align-items: center; gap: var(--space-xs);
    padding: 10px 4px 5px; font-family: var(--font-mono); font-size: var(--font-label);
    font-weight: var(--fw-semibold); text-transform: uppercase;
    letter-spacing: var(--tracking-label); color: var(--text-faint); }
  .grup-n { display: inline-flex; align-items: center; justify-content: center;
    min-width: 17px; height: 17px; padding: 0 5px; border-radius: var(--radius-full);
    background: var(--bg-elevated); color: var(--text-dim);
    font-size: var(--font-small); line-height: 1; font-variant-numeric: tabular-nums; }
  .mgrup-cap.ton-danger { color: var(--danger); }
  .mgrup-cap.ton-danger .grup-n { background: var(--danger-subtle); color: var(--danger); }
  .mgrup-cap.ton-accent { color: var(--accent); }
  .mgrup-cap.ton-accent .grup-n { background: var(--accent-subtle); color: var(--accent-on-subtle); }
  /* UN TASK E UN REPER, NU O CUTIE.
     Din v33 `rect.single` e mereu adevarat, deci regulile de cutie (`.bar.todo`,
     `.bar.active` cu fundal si rama, animatia `barIn` care scala o latime) erau
     scrise pentru ceva ce nu se mai randeaza. Au plecat. Ce ramane e reperul:
     romb + eticheta lui, amandoua in aceeasi tinta. */
  /* SOSIREA REPERULUI — vezi blocul de la `.lane-track`.
     13e pornea de la premisa ca reperul creste deja din ziua lui si cerea doar
     ca benzile sa i se potriveasca. Nu mai crestea: `barIn` scala o LATIME, si a
     plecat odata cu cutia, in aceeasi tura in care taskul a devenit un punct.
     Daca lasam doar benzile sa se miste, inconsecventa din 13e nu disparea, se
     intorcea pe dos — un rand plin de miscare cu reperele inghetate deasupra.
     Un punct nu are latime de intins, deci creste PE LOC. `transform-origin:
     left` = ziua lui: eticheta se desface spre dreapta, de la reper incolo,
     adica in aceeasi directie ca banda de sub ea. Scalare uniforma, nu pe X:
     `scaleX` ar turti si rombul, si scrisul. */
  .bar { position: absolute; top: 0; bottom: 0; background: none; border: none; box-shadow: none; padding: 0;
    font-size: var(--font-small); font-weight: var(--fw-semibold);
    white-space: nowrap; cursor: pointer; text-align: left; touch-action: none;
    pointer-events: auto; transform-origin: left center;
    animation: reperIn var(--dur-base) var(--ease) backwards;
    animation-delay: min(var(--rand, 0) * 40ms, 280ms); }
  /* Reperul din ultima treime isi scrie titlul spre STANGA, deci si desfacerea
     merge intr-acolo — altfel jumatate din randuri cresc dinspre ziua lor, iar
     cealalta jumatate spre ea. */
  .bar.flip { transform-origin: right center; }
  .bar.draggable { cursor: grab; }
  .bar.done { cursor: default; }

  /* BARA E ZIUA. Umple coloana termenului, la inaltimea randului — deci pozitia
     ei nu mai e un punct pe care sa-l cauti, e chiar celula.
     FORMA POARTA STAREA: contur = de facut · plin = in lucru · tenta cu bifa =
     facut. Aceeasi gramatica cu cercul gol si `CheckCircle2` din liste. */
  .bar-box { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    border-radius: var(--radius-xs); background: var(--bg-surface);
    box-shadow: inset 0 0 0 1.5px var(--accent);
    transition: var(--transition-colors); }
  .bar.active .bar-box { background: var(--accent); box-shadow: none; }
  .bar.done .bar-box { background: var(--success-subtle); color: var(--success-deep);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--success) 40%, transparent); }
  /* Haloul se ADAUGA, nu rescrie cutia: `box-shadow` la hover ar sterge conturul
     starii, si un reper facut ar redeveni unul de facut cat tii cursorul pe el —
     exact greseala reparata la muchia de severitate din liste. */
  @media (hover: hover) {
    .bar:hover .bar-box { outline: 2px solid var(--accent-ring); outline-offset: 1px; }
  }

  /* TITLUL IESE DIN BARA, la dreapta ei — deci impachetarea masoara suma lor
     (`intinderea`), nu ziua. Ramane apasabil: cuvintele sunt singurul lucru care
     spune ce e taskul, iar o zi are 34px la orizontul de 30.
     Haloul de text il desprinde de ce e dedesubt (poate fi banda plina a unei
     perioade). */
  .bar-txt { position: absolute; left: 100%; top: 0; bottom: 0;
    display: inline-flex; align-items: center; gap: 4px; max-width: 220px;
    padding-left: 7px; overflow: hidden; color: var(--text); pointer-events: auto;
    text-shadow: 0 0 3px var(--bg-surface), 0 0 6px var(--bg-surface), 0 0 9px var(--bg-surface);
    transition: var(--transition-colors); }
  .bar.flip .bar-txt { left: auto; right: 100%; padding-left: 0; padding-right: 7px; justify-content: flex-end; }
  @media (hover: hover) {
    .bar:hover .bar-txt { color: var(--accent); }
  }
  .bar.done .bar-txt { color: var(--text-dim); text-decoration: line-through; }
  .bar :global(.bar-rep) { flex: none; opacity: 0.7; }

  /* NUMARUL PE SAPTAMANA (3L/6L). Aceeasi pastila ca peste tot in aplicatie
     (`.count` din global.css) — „cate" se scrie intr-un singur fel. */
  .wk { position: absolute; top: 0; bottom: 0; display: flex; align-items: center; justify-content: center;
    pointer-events: auto;
    animation: reperIn var(--dur-base) var(--ease) backwards;
    animation-delay: min(var(--rand, 0) * 40ms, 280ms); }

  /* dim, nu faint: indicatiile de gest sunt text de citit (masurat 3.18:1 la
     10.4px, sub AA) — faint e doar pentru etichete/large. */
  .hint { text-align: center; font-size: var(--font-small); color: var(--text-dim); padding: 8px; border-top: 1px solid var(--border-subtle); }

  .drag-label { position: fixed; z-index: var(--z-tooltip); pointer-events: none; background: var(--bg-overlay);
    border: 1px solid var(--border-strong); border-radius: var(--radius-sm); padding: 3px 8px;
    font-family: var(--font-mono); font-size: var(--font-small); color: var(--text); box-shadow: var(--shadow-md); white-space: nowrap; }

  /* ===== mobile grouped list ===== */
  .mlist { display: none; flex-direction: column; gap: var(--space-md); }

  /* ANTETUL DE ZILE — lipit sub bara aplicatiei.
     Trebuie sa rămână vizibil cat derulezi, altfel benzile de mai jos nu mai au
     scara si redevin decor. `--m-pad` e insetul lateral al benzii dintr-un grup
     (marginea grupului + paddingul lui), ca sa cada coloana peste coloana. */
  /* `--m-pad` = rama grupului (1) + paddingul lui (8) + marginea benzii (3).
     Cele trei numere trebuie sa rămână in acord cu `.mgroup` si `.m-track`:
     daca antetul si banda nu incep exact in acelasi x, coloana „marti" cade
     langa ziua de marti, si tot graficul minte cu o zi. */
  .m-scale { --m-pad: 12px;
    position: sticky; top: var(--header-height); z-index: 4;
    padding: 6px var(--m-pad) 5px;
    /* Fond OPAC, fara blur: sticla a iesit din sistem. Semitransparentul cerea
       blurul ca sa nu se vada benzile trecand pe sub cifre. */
    background: var(--bg);
    border-bottom: 1px solid var(--border); border-radius: var(--radius-sm); }
  .ms-cols { position: relative; height: 14px; }
  .m-scale.cu-wd .ms-cols { height: 26px; }
  .ms-c { position: absolute; top: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 0;
    height: 100%; font-family: var(--font-mono); font-size: var(--font-small);
    color: var(--text-dim); font-variant-numeric: tabular-nums;
    overflow: hidden; white-space: nowrap; border-left: 1px solid var(--border-subtle); }
  .ms-wd { font-size: var(--font-label); line-height: var(--lh-tight); color: var(--text-faint); text-transform: uppercase; letter-spacing: var(--tracking-label); }
  .ms-c.we { color: var(--text-dim); }
  .ms-c.we .ms-wd { color: var(--text-dim); }
  .ms-c.today { color: var(--accent); font-weight: var(--fw-semibold); }
  .ms-c.today .ms-wd { color: var(--accent); }

  /* BANDA PROIECTULUI — acelasi continut ca lane-ul de pe desktop.
     Inaltimea e mica intentionat: e context, nu suprafata de lucru. Ce faci cu un
     task faci pe randul lui, dedesubt. */
  .m-track { position: relative; height: 26px; margin: 0 3px 8px; border-radius: var(--radius-sm);
    background: var(--bg-panel); box-shadow: inset 0 0 0 1px var(--border-subtle); overflow: hidden; }
  .mt-we { position: absolute; top: 0; bottom: 0; background: color-mix(in srgb, var(--text) 5%, transparent); }
  /* Amber, ca pe desktop: rosul e „intarziat", nu „acum". */
  .mt-azi { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--accent); opacity: 0.85; z-index: 3; }
  /* Reperele stau PESTE benzi si sunt singurul lucru din banda pe care il atingi
     des, deci primesc o caseta transparenta de 26px in jurul punctului de 9px.
     Fara ea ai avea de nimerit un punct cat gamalia acului.
     26, NU 44, si ramane asa cu buna stiinta: pe un orizont de 14 zile o zi are
     ~22px, deci doua repere in zile alaturate ar ajunge sa se acopere unul pe
     altul — ai schimba o tinta mica pe una GRESITA, care deschide alt task. Iar
     pretul unei ratari e zero: reperul nu face decat sa te duca la randul
     taskului din lista de dedesubt, iar acel rand e cat toata latimea. */
  /* Acelasi `reperIn` ca `.bar` de pe desktop — pista mobila foloseste aceleasi
     benzi, deci trebuie sa aiba si aceleasi repere deasupra lor, altfel 13e ar fi
     rezolvat pe un ecran si rupt pe celalalt.
     Animatia sta pe BUTON, nu pe `::before`: rombul isi tine forma dintr-un
     `rotate(45deg)`, iar `to { transform: none }` i-ar sterge rotatia si l-ar lasa
     patrat. Butonul n-are transform propriu, deci nu are ce sa piarda. Creste din
     centru fiindca punctul E centrul lui (`margin-left: -13px` peste 26px). */
  .mt-pin { position: absolute; top: 0; bottom: 0; width: 26px; margin-left: -13px;
    display: flex; align-items: center; justify-content: center;
    background: none; border: none; padding: 0; cursor: pointer; z-index: 2;
    color: var(--text-dim);
    animation: reperIn var(--dur-base) var(--ease) backwards;
    animation-delay: min(var(--rand, 0) * 40ms, 280ms); }
  /* Aceeasi forma ca pe desktop: contur = de facut, plin = in lucru, bifa = facut.
     `done` era VERDE aici si o nuanta palida a culorii de proiect dincolo — acelasi
     task, doua limbaje, in functie de latimea ecranului. */
  .mt-pin::before { content: ''; width: 9px; height: 9px; border-radius: 2px;
    background: transparent; border: 1.5px solid var(--accent); transform: rotate(45deg);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--bg-panel) 85%, transparent); }
  .mt-pin.lucru::before { background: var(--accent); }
  .mt-pin.done::before { display: none; }
  /* APASAREA STRANGE, NU CRESTE. Era `scale(1.25)` — adica reperul se umfla cu un
     sfert sub deget, exact invers fata de token (`--press-scale`, 0.965 in 90ms).
     `rotate(45deg)` RAMANE scris: rombul isi tine forma din el, iar o valoare care
     nu-l repeta l-ar lasa patrat fix in timpul apasarii. */
  .mt-pin:active::before { transform: rotate(45deg) scale(var(--press-scale)); }

  /* Benzile refolosesc reteta de pe desktop (aceleasi clase, aceeasi gramatica:
     palid = pregatire, plin = pe teren, teal = site, gold = sediu). Se schimba
     doar dimensiunile, fiindca aici randul are 26px, nu 42. */
  .m-track .band { top: 3px; bottom: 3px; border-radius: var(--radius-xs); }
  .m-track .impl-band { top: 3px; bottom: 3px; gap: 4px; padding: 0 6px; border-radius: var(--radius-xs);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 32%, transparent); }
  .m-track .impl-band.pregatire { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 22%, transparent); }
  .m-track .ib-txt { font-size: var(--font-small); }
  /* In banda, perioada e DESEN, nu buton: un bloc de doua zile are ~23×20px.
     Cine vrea s-o deschida o atinge pe randul ei, de sub banda (`.mimpl`), unde
     are latimea intreaga. */
  .m-track .impl-band { pointer-events: none; cursor: default; }

  .mgroup { background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); padding: var(--space-sm) var(--space-sm) var(--space-xs); }
  .mg-head { display: flex; align-items: center; gap: 7px; padding: 4px 6px 8px; }
  .mg-head h2 { font-size: var(--font-body); font-weight: var(--fw-semibold); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* `.mg-count` a plecat — sunt doua `.count` din global.css (vezi markup).
     Prima impinge perechea in capatul din dreapta al antetului. */
  .mg-head :global(.count:first-of-type) { margin-left: auto; }
  /* MUCHIA DE 3px A PLECAT, SI AICI ERA CEA MAI INCURCATA: aceeasi bordura din
     stanga spunea si „proiectul X" (`--lane`), si „intarziat" (`.urgent`) — deci
     un rand restant isi PIERDEA identitatea ca sa arate severitatea. Acum sunt
     doua canale separate: identitatea e un fill tentat din culoarea benzii (ca la
     vecinii ei din aceeasi pagina), severitatea e pe inelul bifei si pe chip. */
  .mrow { position: relative; display: flex; align-items: center; gap: var(--space-xs); padding: 8px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: 6px; }
  /* NICIO OPACITATE PE UN RAND DE TEXT. „Facut" se spune prin taierea titlului si
     prin rolul de culoare, nu prin `opacity: .6` — care se inmulteste peste tokenuri
     deja la limita de contrast si scoate randul sub AA. */
  .mrow.done .mrow-title { text-decoration: line-through; color: var(--text-dim); }
  .mrow-main { flex: 1; min-width: 0; text-align: left; background: none; border: none; cursor: pointer; display: flex; flex-direction: column; gap: 3px; }
  .mrow-title { font-size: var(--font-small); color: var(--text); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .mrow-meta { display: flex; flex-wrap: wrap; gap: 4px; }
  .chip { font-size: var(--font-small); padding: 1px 6px; border-radius: var(--radius-xs); background: var(--bg-elevated); color: var(--text-dim); display: inline-flex; align-items: center; gap: 3px; }
  .chip.due { color: var(--text-dim); background: var(--bg-elevated); }
  /* O SINGURA GRAMATICA PENTRU „AZI". Erau doua clase („azi", „restant") cu doua
     harti de culoare proprii, pe langa inca una pe muchia randului. Acum chipul
     citeste ACELASI `--ring` ca inelul bifei de langa el, deci cele doua canale
     nu se pot desincroniza. */
  .chip.due.sev { color: var(--ring); background: color-mix(in srgb, var(--ring) 14%, transparent); }
  .mrow-actions { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
  /* Pe desktop invelisul de glisare nu exista pentru layout, iar panoul lui e
     ascuns: acolo actiunile stau la vedere in rand. */
  .gl-fata { display: contents; }
  .gl-actiuni { display: none; }
  .mcheck { display: none; }
  .mbtn { width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-faint); cursor: pointer; background: none; border: none; }
  .mbtn:hover { background: var(--bg-hover); color: var(--text); }
  .mrow-date { width: 34px; flex-shrink: 0; }
  .mrow-date :global(.dp-trigger) { width: 34px; min-height: 34px; padding: 0; justify-content: center; background: transparent; border: none; box-shadow: none; color: var(--text-faint); }
  .mrow-date :global(.dp-trigger:hover) { background: var(--bg-hover); color: var(--text); }
  .mrow-date :global(.dp-value) { display: none; }

  /* ===== TASKUL DESCHIS · PANOU LATERAL (4e) =====
     Panoul are COLOANA lui in grila de lucru, deci pista se stramteaza cand se
     deschide. `minmax(0, 1fr)` pe prima coloana: cu `1fr` (adica `minmax(auto,
     1fr)`) pista, care are latime minima proprie (`contentMin`), ar refuza sa se
     micsoreze si ar impinge panoul in afara ecranului. */
  .lucru { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--space-md); align-items: start; }
  .lucru.cu-panou { grid-template-columns: minmax(0, 1fr) 320px; }

  .panou { background: var(--bg-surface);
    border-radius: var(--radius-md); box-shadow: var(--shadow-md);
    display: flex; flex-direction: column; overflow: hidden;
    position: sticky; top: calc(var(--header-height) + var(--space-md));
    max-height: calc(100dvh - var(--header-height) - var(--space-lg)); }
  .pan-cap { display: flex; align-items: center; gap: var(--space-xs);
    padding: 10px 8px 10px 14px; border-bottom: 1px solid var(--border); }
  .pan-proiect { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;
    font-size: var(--font-small); color: var(--text-secondary);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pan-dot { width: 9px; height: 9px; border-radius: 50%; background: var(--lane); flex: none; }
  .pan-x { width: 32px; height: 32px; flex: none; display: flex; align-items: center; justify-content: center;
    border-radius: var(--radius-sm); background: none; border: none; color: var(--text-dim); cursor: pointer;
    transition: var(--transition-colors); }
  .pan-x:hover { background: var(--bg-hover); color: var(--text); }

  .pan-corp { padding: 14px; overflow-y: auto; flex: 1; min-height: 0; }
  .pan-titlu { font-size: var(--font-h2); font-weight: var(--fw-semibold);
    line-height: var(--lh-tight); color: var(--text); margin-bottom: var(--space-md); overflow-wrap: anywhere; }

  /* Faptele taskului: eticheta la stanga, valoarea la dreapta, iconita la capat.
     Randul care DUCE undeva e buton si poarta chevron; celelalte sunt text. */
  .pan-fapte { display: flex; flex-direction: column; }
  .fapt { display: flex; align-items: center; gap: var(--space-sm); width: 100%;
    padding: 9px 2px; border-bottom: 1px solid var(--border); text-align: left;
    background: none; border-left: 0; border-right: 0; border-top: 0; color: var(--text); }
  .fapt:last-child { border-bottom: 0; }
  .fapt.link { cursor: pointer; transition: var(--transition-colors); }
  .fapt.link:hover { color: var(--accent); }
  .fapt-et { flex: none; width: 74px; font-size: var(--font-label); font-weight: var(--fw-semibold);
    text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); }
  .fapt-val { flex: 1; min-width: 0; font-size: var(--font-small); color: var(--text); overflow-wrap: anywhere; }
  .fapt-val.slab { color: var(--text-dim); }
  /* Severitatea termenului citeste ACELASI `--ring` ca inelul bifei din liste. */
  .fapt-val.sev { color: var(--ring); font-weight: var(--fw-medium); }
  .fapt :global(.fapt-ico) { flex: none; color: var(--text-dim); }

  .pan-sec { display: flex; align-items: center; gap: var(--space-xs);
    margin: var(--space-md) 0 var(--space-xs); font-size: var(--font-label);
    font-weight: var(--fw-semibold); text-transform: uppercase;
    letter-spacing: var(--tracking-label); color: var(--text-dim); }
  .pan-frac { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .pan-nota { font-size: var(--font-small); color: var(--text-secondary);
    line-height: var(--lh-relaxed); white-space: pre-wrap; overflow-wrap: anywhere; }

  .pasi { display: flex; flex-direction: column; list-style: none; }
  .pas { display: flex; align-items: center; gap: var(--space-sm); width: 100%;
    padding: 7px 2px; background: none; border: none; text-align: left; cursor: pointer;
    font-size: var(--font-small); color: var(--text); transition: var(--transition-colors); }
  .pas-bifa { flex: none; width: 18px; height: 18px; display: flex; align-items: center;
    justify-content: center; border-radius: 50%; color: var(--success-deep); }
  .pas.gata .pas-bifa { background: var(--success-subtle); }
  /* Fara `opacity` pe randul facut — rolul de culoare si taierea o spun. */
  .pas.gata .pas-txt { color: var(--text-dim); text-decoration: line-through; }
  .pas-txt { min-width: 0; overflow-wrap: anywhere; }

  .pan-plan { padding: 0 14px 12px; }
  .pan-plan .pan-sec { margin-top: 0; }
  .pan-actiuni { display: flex; gap: var(--space-xs); padding: 10px 14px;
    border-top: 1px solid var(--border); background: var(--bg-elevated); }
  .pan-b { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
    min-height: 38px; padding: 0 12px; border-radius: var(--radius-sm);
    background: var(--bg-surface); border: 1px solid var(--border); color: var(--text-secondary);
    font-size: var(--font-control); font-weight: var(--fw-semibold); cursor: pointer;
    transition: var(--transition-pressable); }
  .pan-b:hover { border-color: var(--border-strong); color: var(--text); }
  .pan-b:active { transform: scale(var(--press-scale)); }
  .pan-b.prim { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }


  /* ===== Telefon =====
     Bara de controale avea 502px intr-un ecran de 375: `.page-header` are
     `flex-wrap`, dar `.controls` era un singur bloc `flex` fara wrap, deci nu
     putea fi rupt si impingea TOATA pagina la 502px latime. Rezultatul: fiecare
     ecran din Planificator se derula si lateral, iar barele de zile nu se mai
     aliniau cu ce vedeai. */

  :global(body.plan-dragging) { user-select: none; cursor: grabbing; }
  :global(body.plan-dragging) .bar { cursor: grabbing; }

  /* ===== drop indicator (backlog -> timeline) ===== */
  .p-body.drop-active { outline: 2px dashed color-mix(in srgb, var(--accent) 45%, transparent); outline-offset: -2px; border-radius: var(--radius-sm); }
  .drop-line { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--accent); z-index: 6; }
  .drop-tag { position: absolute; top: 2px; transform: translateX(-50%); background: var(--accent); color: var(--accent-text); font-size: var(--font-small); padding: 1px 6px; border-radius: var(--radius-xs); z-index: 7; white-space: nowrap; }

  /* ===== backlog rail ===== */
  .backlog { margin-top: var(--space-md); background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); overflow: hidden; }
  .bl-head { width: 100%; display: flex; align-items: center; gap: var(--space-sm); padding: 12px 16px; background: none; border: none; cursor: pointer; color: var(--text); }
  .bl-head h2 { font-size: var(--font-body); font-weight: var(--fw-semibold); }
  /* `.bl-count` a plecat — e `.count accent` din global.css. */
  .bl-hint { font-size: var(--font-small); color: var(--text-dim); margin-left: 4px; }
  .bl-head :global(.bl-chev) { margin-left: auto; color: var(--text-faint); transition: transform var(--dur-fast) var(--ease); }
  .backlog.open .bl-head :global(.bl-chev) { transform: rotate(90deg); }
  .bl-items { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 16px 16px; }
  /* Dunga era `var(--text-faint)` — o linie gri care nu codifica nimic. Se sterge
     fara inlocuitor; severitatea acestui chip o poarta chipul lui de termen. */
  .bl-chip { display: flex; align-items: center; gap: 6px; padding: 6px 8px 6px 7px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-md); cursor: grab; max-width: 320px; }
  .bl-chip:hover { border-color: var(--border-strong); }
  .bl-chip:active { cursor: grabbing; }
  .bl-chip :global(.bl-grip) { color: var(--text-faint); flex-shrink: 0; }
  .bl-sev { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  .bl-txt { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; }
  .bl-proj { font-size: var(--font-small); color: var(--accent); background: var(--accent-subtle); padding: 1px 6px; border-radius: var(--radius-xs); white-space: nowrap; max-width: 120px; overflow: hidden; text-overflow: ellipsis; }
  .bl-proj.glob { color: var(--text-dim); background: var(--bg-elevated); }
  .bl-date { width: 30px; flex-shrink: 0; }
  .bl-date :global(.dp-trigger) { width: 30px; min-height: 30px; padding: 0; justify-content: center; background: transparent; border: none; box-shadow: none; color: var(--text-faint); }
  .bl-date :global(.dp-trigger:hover) { background: var(--bg-hover); color: var(--accent); }
  .bl-date :global(.dp-value) { display: none; }

  /* ===== export modal ===== */
  .exp { display: flex; flex-direction: column; gap: 14px; }
  .exp-note { font-size: var(--font-small); color: var(--text-secondary); margin: 0; }
  .exp-note b { color: var(--text); }
  .exp-scope-head { display: flex; align-items: center; justify-content: space-between; font-size: var(--font-label); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); font-family: var(--font-mono); margin-bottom: 6px; }
  .exp-all { background: none; border: none; color: var(--accent); font-size: var(--font-small); cursor: pointer; }
  .exp-list { display: flex; flex-direction: column; gap: 2px; max-height: 240px; overflow-y: auto; }
  .exp-row { display: flex; align-items: center; gap: 9px; padding: 7px 8px; border-radius: var(--radius-sm); cursor: pointer; }
  .exp-row:hover { background: var(--bg-hover); }
  .exp-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
  .exp-name { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .exp-opt { display: flex; align-items: center; gap: 9px; font-size: var(--font-small); color: var(--text-secondary); cursor: pointer; padding-top: 6px; border-top: 1px solid var(--border); }
  .modal-actions { display: flex; justify-content: flex-end; gap: var(--space-sm); }
  .btn-ghost { padding: 8px 16px; border-radius: var(--radius-md); background: none; border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; font-size: var(--font-small); }
  .btn-ghost:hover { border-color: var(--border-strong); color: var(--text); }
  .btn-primary { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: var(--radius-md); background: var(--accent); border: none; color: var(--accent-text); cursor: pointer; font-size: var(--font-small); font-weight: var(--fw-semibold); }
  .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ===== telefon =====
     ULTIMELE in fisier, cu buna stiinta. Un `@media` NU adauga specificitate: la
     specificitate egala castiga regula scrisa mai jos. Blocurile astea stateau la
     mijlocul fisierului, inaintea sectiunilor „backlog rail" si „controls" — deci
     `.bl-chip { max-width: none }` de aici era anulat de `.bl-chip { max-width: 320px }`
     de mai incolo, si la fel `.bl-txt`, `.bl-proj`, `.bl-date`, `.page`, `.page-header`,
     `.controls`. Douasprezece reguli scrise pentru telefon care nu se aplicau nici
     pe telefon: masurat in pagina, chipul din „Taskuri fără termen" avea tot
     `max-width: 320px` si butonul de data tot 30px in loc de 44.
     Daca adaugi sectiuni noi de baza, adauga-le DEASUPRA acestui punct. */

  @media (max-width: 820px) {
    .chart { display: none; }
    .mlist { display: flex; }
    /* Pe telefon pista nu se randeaza, deci nici panoul ei: acolo reperul duce la
       randul din lista, care are deja foaia lui. Regula e si o plasa — daca
       micsorezi fereastra cu panoul deschis, el nu ramane atarnat singur. */
    .panou { display: none; }
    .lucru, .lucru.cu-panou { display: block; }
  }

  @media (max-width: 768px) {
    .page { padding-left: var(--space-md); padding-right: var(--space-md); }
    .page-header { align-items: stretch; }
    .controls { flex-wrap: wrap; width: 100%; }
    /* Orizontul e alegerea principala — ia randul lui, cu cele cinci trepte
       impartite egal. */
    .seg { display: flex; width: 100%; }
    .seg-btn { flex: 1; min-height: var(--tap-min); font-size: var(--font-body); }
    /* `nowrap` + eticheta scurtata: „Export PDF" se rupea pe doua randuri si facea
       butonul cu 10px mai inalt decat vecinii lui, adica un rand strâmb. */
    .toggle { flex: 1 1 0; min-height: var(--tap-min); justify-content: center; white-space: nowrap; padding: 6px 8px; }
    .tg-lung { display: none; }

    /* Randurile listei: butoanele erau de 34px, adica sub pragul la care nimeresti
       din prima. Aici bifezi taskuri cu manusa de lucru pe mana. */
    .mbtn { width: var(--tap-min); height: var(--tap-min); }
    .mrow-date { width: var(--tap-min); }
    .mrow-date :global(.dp-trigger) { width: var(--tap-min); min-height: var(--tap-min); }
    /* Ca pe „Astazi": o linie, bifa la vedere, restul in panoul de sub rand.
       Randul era pe doua linii, cu trei butoane de 44px pe a doua — pe o lista de
       noua proiecte asta inseamna sa derulezi mult ca sa vezi putin. */
    .mrow { padding: 0; overflow: hidden; position: relative; touch-action: pan-y; }
    .gl-fata { display: flex; align-items: center; gap: var(--space-xs); width: 100%;
               padding: 5px 8px; background: var(--bg-panel); position: relative; z-index: 1;
               border-radius: var(--radius-md); will-change: transform; }
    /* `:global(...)` pe clasa pusa din JS, NU pe intreg selectorul.
       Svelte NU se multumeste sa avertizeze „Unused CSS selector": TAIE regula din
       build. Iar `gl-tras`/`gl-bifa` sunt puse la RULARE de `lib/glisare.js`, deci
       nu apar in markup si compilatorul le crede moarte. Efectul, verificat in CSS-ul
       livrat: din toate regulile de gest ale aplicatiei supravietuise UNA. Adica
       glisai spre dreapta si nu vedeai verdele care spune „ai trecut pragul" —
       exact semnalul fara de care gestul e o loterie.
       Ancora (`.arow`/`.trow`/`.mrow`) ramane scoped, deci regula nu scapa in alte
       componente. */
    .mrow:global(.gl-tras) .gl-fata { box-shadow: -6px 0 12px -8px rgba(0,0,0,0.55); }
    .mrow-main { flex: 1 1 0; min-width: 0; padding: 0; min-height: var(--tap-min); justify-content: center; }
    .mrow-title { white-space: nowrap; }
    .mimpl { min-height: var(--tap-min); }
    .mrow-meta { flex-wrap: nowrap; overflow: hidden; }
    .mrow-meta > * { flex-shrink: 0; }
    .mrow-actions { display: none; }
    .mcheck { display: flex; width: var(--tap-min); height: var(--tap-min); flex-shrink: 0;
              align-items: center; justify-content: center; background: none; border: none;
              color: var(--text-dim); cursor: pointer; }
    /* `.mcheck-gol` era acelasi obiect ca `.check-empty`, sub alt nume — al
       cincilea loc in care se definea bifa. Traieste acum in global.css. */
    .mrow.done .mcheck { color: var(--success); }
    .mcheck { display: flex; }

    .gl-actiuni { display: flex; position: absolute; top: 0; right: 0; bottom: 0; z-index: 0; align-items: stretch; }
    .glb { width: 58px; display: flex; flex-direction: column; align-items: center; justify-content: center;
           gap: 3px; border: none; background: var(--bg-elevated); color: var(--text-secondary);
           font-size: var(--font-small); cursor: pointer; }
    .glb span { line-height: 1; }
    .glb.datewrap { position: relative; }
    .glb.datewrap :global(.dp) { position: absolute; inset: 0; width: auto; }
    .glb.datewrap :global(.dp-trigger) { width: 100%; height: 100%; min-height: 0; padding: 0 0 14px;
      justify-content: center; background: none; border: none; box-shadow: none; color: inherit; }
    .glb.datewrap :global(.dp-value) { display: none; }
    .glb.datewrap > span { position: absolute; left: 0; right: 0; bottom: 11px; text-align: center; pointer-events: none; }
    .mrow:global(.gl-bifa) { background: var(--success-subtle); box-shadow: inset 0 0 0 1px var(--success); }

    .bl-head { min-height: var(--tap-min); }
    .bl-hint { display: none; }
    /* DOUA RANDURI, NU DOUA JUMATATI.
       Pe o linie, titlul si numele proiectului isi imparteau latimea si ieseau
       doua fragmente egale — „Backup paramet…" langa „Interventie avar…" — din
       care nu se intelege niciunul. Nu e o lista de taskuri de bifat (acolo un
       rand = o linie, vezi TodayBoard), e un sertar din care alegi ce planifici:
       aici numele intreg valoreaza mai mult decat inaltimea economisita.
       Titlul ia tot randul, proiectul sta dedesubt, manerul si data prind
       amandoua randurile. */
    .bl-chip { max-width: none; width: 100%; padding: 4px 6px 4px 4px;
               display: grid; grid-template-columns: auto minmax(0, 1fr) auto;
               column-gap: 6px; row-gap: 1px; align-items: center; }
    .bl-chip :global(.bl-grip) { grid-row: 1 / -1; }
    .bl-txt { max-width: none; grid-column: 2; }
    .bl-proj { grid-column: 2; justify-self: start; max-width: 100%; }
    .bl-date { grid-column: 3; grid-row: 1 / -1; width: var(--tap-min); }
    .bl-date :global(.dp-trigger) { width: var(--tap-min); min-height: var(--tap-min); }
  }

  /* Plasa globala din global.css scurteaza DURATA la ~0, dar nu atinge
     `animation-delay` — iar cu `backwards` intarzierea tine cadrul de start, adica
     `opacity: 0`. Randul sase ar sta 240ms invizibil si pe urma ar pocni pe ecran:
     acelasi stagger, doar fara partea care il facea lizibil. Se scot de tot.
     Aici, la sfarsit: media query-ul nu adauga specificitate, deci scris mai sus
     ar fi fost anulat de `.band` / `.impl-band` / `.bar`. */
  @media (prefers-reduced-motion: reduce) {
    .band, .impl-band, .bar, .wk, .mt-pin { animation: none; }
  }

  /* ===== print (browser print-to-PDF) ===== */
  .print-title { display: none; }
  @media print {
    .page { padding: 0 !important; }
    .page-header, .controls, .hint, .mlist, .backlog, .drag-label, .panou { display: none !important; }
    /* Fara panou, grila de lucru redevine o coloana — altfel PDF-ul ar pastra
       cei 320px de gol in dreapta pistei. */
    .lucru, .lucru.cu-panou { display: block !important; }
    .print-title { display: block; font-family: var(--font-heading); font-size: var(--font-h2); font-weight: var(--fw-semibold); color: #1a1206; margin-bottom: 8px; }
    /* Force the swimlane on: A4 portrait (~794px) is under the 820px mobile
       breakpoint, which would otherwise hide .chart and blank the page. */
    .chart { display: block !important; overflow: visible !important; border: none !important; box-shadow: none !important; background: #fff !important; }
    .chart-scroll { overflow: visible !important; }
    .inner { min-width: 0 !important; width: 100% !important; }
    .lane.print-hide { display: none !important; }
    /* Aceeasi grija ca la `.cell-in` in global.css: sosirile astea pornesc de la
       `opacity: 0`, iar la print animatia nu se joaca — fara `none` explicit,
       benzile ar lipsi din PDF si ar ramane un grafic cu randuri goale. */
    .bar, .wk, .band, .impl-band { animation: none !important; opacity: 1 !important; }
    .bar { box-shadow: none !important; }
  }
  :global(body.plan-pagebreak) .lane { break-after: page; }
  :global(body.plan-pagebreak) .lane:last-of-type { break-after: auto; }
</style>
