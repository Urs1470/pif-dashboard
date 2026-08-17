<script module>
  import { urlPlan as _url } from '../stores/plan.svelte.js'
  import { preia as _preia } from '../lib/cache.js'

  /** Chemata de router la hover pe tabul din Doc, INAINTE de schimbarea rutei.
   *  Fara ea, hoverul aducea doar chunkul paginii, iar cererea de date pornea
   *  abia la montare — deci prima intrare pe tab in fiecare sesiune trecea
   *  printr-un schelet, oricat de repede venea codul.
   *  URL-ul vine din store, unde il construieste si `loadPlan`: doua sabloane
   *  ale aceluiasi raspuns n-ar mai nimeri aceeasi intrare in cache, si atunci
   *  preincarcarea ar face o cerere in plus fara sa scoata scheletul. */
  export function pregateste() {
    return _preia(_url(), { proaspat: 5000 })
  }
</script>

<script>
  import { onMount, tick } from 'svelte'
  import { CalendarRange, ChevronRight, CalendarDays, ArrowRight, X, CheckCircle2, Repeat, ExternalLink, Check, FileDown, Inbox, GripVertical, MapPin, Building2, Calendar } from '@lucide/svelte'
  import {
    plan, loadPlan, moveTaskDate, moveTaskTomorrow, toggleTaskDone,
    setTaskDates, setHorizon, toggleShowDone, toggleWeekends, scheduleBacklog,
    deleteTaskPlan,
  } from '../stores/plan.svelte.js'
  import { loadSubtasks, updateSubtask } from '../stores/tasks.svelte.js'
  import { buildColumns, grupeazaColoane, numeLuna, ziLuna, spanRect, dayDiff, addDays, clampNum, buildDays, parseISO, localToday } from '../lib/planDates.js'
  import { formatDate, formatDateShort, dueRing, RING_NEUTRU } from '../lib/formatters.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import { apiJson } from '../lib/api.js'
  import { incepeTragere } from '../lib/tragere.js'
  import { tragePeZile } from '../lib/tragereTimeline.js'
  import { ecran } from '../lib/ecran.svelte.js'
  import { morphNavigate } from '../lib/focus.js'
  import { glisare } from '../lib/glisare.js'
  import { apasareLunga } from '../lib/apasareLunga.js'
  import FoaieTask from '../components/FoaieTask.svelte'
  import { motion, panou, motionDuration, aterizare } from '../lib/motion.svelte.js'
  import { navigate } from '../lib/router.svelte.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ContorPasi from '../components/ui/ContorPasi.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import DatePicker from '../components/ui/DatePicker.svelte'
  import Modal from '../components/ui/Modal.svelte'
  import SelectorZi from '../components/ui/SelectorZi.svelte'
  import { culoareProiect, CULOARE_NEUTRA } from '../lib/culori.js'

  // PERIOADA E O SINA LA BAZA RANDULUI, NU FUNDALUL LUI.
  //
  // Pana acum banda tinea toata inaltimea randului si isi scria numele INAUNTRU,
  // pe aceiasi pixeli orizontali pe care ii voiau titlurile taskurilor. De acolo
  // veneau trei defecte masurate pe aplicatie (14z, pista 1034px):
  //   · 4 din 6 etichete TAIATE — „Sediu EGB · Verificare parametri" primea 36px
  //     din 183, adica 20% din nume;
  //   · la 30z patru benzi ramaneau MUTE (doar iconita, niciun nume);
  //   · la 3L/6L doua etichete se tipareau UNA PESTE ALTA, ilizibil, fiindca
  //     `.ib-out` iesea din banda fara sa se uite daca locul de afara e liber.
  // Plus: inaltimea randului venea din COLIZIUNI, nu din continut — eticheta
  // benzii tinea randul intai al impachetarii, deci un proiect cu patru taskuri
  // ajungea la 112px.
  //
  // Perioada e CONTEXT („unde esti"), taskul e CONTINUT („ce ai de facut"), deci
  // contextul coboara intr-o sina de 4px la baza randului — conventia baseline
  // din Gantt, unde bara subtire e contextul si cea groasa e subiectul. Taskurile
  // primesc toata inaltimea si toata latimea, iar impachetarea nu mai are ce
  // bloca.
  //
  // Iar fasia de jos ramane GOALA, deci o eticheta acolo are loc pana la perioada
  // urmatoare — sute de pixeli, nu 37 dintr-o banda de o zi. De aceea locul se
  // scrie intr-o pastila la capul sinei, si se scrie INTREG sau deloc.

  // Cat cere pastila peste latimea cuvantului: iconita 10 + gap 3 + padding 4+6,
  // plus 6 aer pana la sina urmatoare. Se compara cu golul REAL pana la perioada
  // de dupa, deci pastila ori incape intreaga, ori nu se randeaza — nu exista
  // stare in care se taie.
  // (Latimea minima a sinei — 11px, fiindca o perioada de o zi are 5,7px la 6L —
  // e acum regula CSS pe `.impl-band`, nu o constanta de aici: se aplica la toate
  // orizonturile, fiindca sina are aceeasi forma peste tot.)
  const PASTILA_CHROME = 29
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
  // `mCols` a plecat odata cu `.m-scale` (V11): aplatiza antetul mobil la UN
  // singur rand, alegand intre zile si grupe dupa orizont. Pista comuna are acum
  // aceeasi structura ca desktopul — `antet.grupe` peste `columns.cols` — iar
  // randul fin se randeaza doar cand se poate CITI (pana la 30z). La 3L/6L
  // douazeci si sase de saptamani ar fi 13px fiecare, adica o dunga fara cifre:
  // acolo ramane doar randul grosier, exact cat arata si scara veche.
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
  // In bucati, nu un singur string: desenul (4c) cere CIFRELE in mono, restul in
  // text — deci numarul si intervalul se randeaza in span-uri separate.
  const subtitlu = $derived.by(() => {
    if (!plan.start) return null
    const h = HORIZONS.find(x => x.d === plan.days)
    const cat = h ? h.cat : plan.days + ' zile'
    const [catN, ...catRest] = cat.split(' ')
    const ultima = addDays(plan.start, plan.days - 1)
    const l1 = numeLuna(plan.start)
    const l2 = numeLuna(ultima)
    const interval = lung
      ? (l1 === l2 ? l1 : `${l1}–${l2}`)
      : (l1 === l2 ? `${ziLuna(plan.start)}–${ziLuna(ultima)} ${l2}`
                   : `${ziLuna(plan.start)} ${l1} – ${ziLuna(ultima)} ${l2}`)
    return { catN, catRest: catRest.join(' '), interval }
  })

  // PE TELEFON SUBTITLUL SPUNE ALTCEVA, fiindca ecranul arata altceva.
  //
  // Ion, 2026-08-17: „pe mobil nu mai are sens alegerea perioadei de sus, arata
  // aceeasi perioada tot timpul, nu?" — exact. Grila e fixa: patru saptamani de
  // luni. Orizontul (`plan.days`) a devenit o unealta INTERNA, urcata la 30 doar ca
  // sa acopere grila, iar segmentul din care se alegea e ascuns sub 768px.
  // Subtitlul insa continua sa citeasca orizontul, deci scria „de azi, 30 zile ·
  // 17 aug – 15 sep" peste o grila care arata 17 aug – 13 sep. Nu doar fara sens:
  // GRESIT cu doua zile, si dintr-o sursa pe care n-o poti corecta din ecran.
  // Deci pe telefon spune ce se vede: intervalul grilei, si nimic despre alegeri.
  const subtitluGrila = $derived.by(() => {
    if (!gridStart) return ''
    const ultima = addDays(gridStart, ZILE_GRILA - 1)
    const l1 = numeLuna(gridStart)
    const l2 = numeLuna(ultima)
    return l1 === l2
      ? `${ziLuna(gridStart)}–${ziLuna(ultima)} ${l2}`
      : `${ziLuna(gridStart)} ${l1} – ${ziLuna(ultima)} ${l2}`
  })

  /** Interval compact: aceeasi luna se scrie O data — „17–18 aug", nu
   *  „17 aug. – 18 aug." (raportat de Ion, cu poza). O zi = o zi. */
  function intervalScurt(a, b) {
    if (!b || b === a) return formatDateShort(a)
    const l1 = numeLuna(a)
    const l2 = numeLuna(b)
    return l1 === l2 ? `${ziLuna(a)}–${ziLuna(b)} ${l2}`
      : `${formatDateShort(a)} – ${formatDateShort(b)}`
  }

  // ===== INTINDEREA PERIOADEI DIN PISTA (raportat de Ion: „nu apar barele
  // verticale... la fel si pe planificator"). Desenul Planificatorului are
  // intinderea in turele 4-6; pana acum banda doar naviga la Calendar.
  // Aceeasi gramatica de gest ca in Calendar (lib/tragere.js), dar FARA
  // impingerea vecinilor: aici randul e al unui singur proiect, deci capatul se
  // OPRESTE la perioada vecina — coliziunile intre proiecte nu exista pe pista.
  // O banda LIPITA din mai multe perioade (im.parti > 1) nu se intinde de aici:
  // capatul ei apartine altei perioade din spate, si l-ar rescrie pe al primeia.
  let intindere = $state(null) // { id, a, b } — previzualizarea cat timp tragi
  function apucaCapatImpl(e, lane, im, capat) {
    // GARDA A PLECAT (T8). `ecran.grosier` e `(hover: none)`, deci oprea gestul
    // si pe un laptop cu ecran tactil. Ce tine locul e apasarea lunga din
    // `incepeTragere`: la deget gestul incepe dupa 300ms fara miscare si se
    // anuleaza la 10px — deci o glisare verticala ramane derulare.
    e.stopPropagation()
    const pista = e.currentTarget.closest('.lane-track')
    if (!pista) return
    const ziDinX = (x) => {
      const r = pista.getBoundingClientRect()
      const p = Math.min(1, Math.max(0, (x - r.left) / r.width))
      return addDays(plan.start, Math.min(plan.days - 1, Math.floor(p * plan.days)))
    }
    const s0 = im.a
    const f0 = im.b
    const vecinStanga = lane.impl.filter((x) => x.id !== im.id && x.b < s0).sort((a, b) => b.b.localeCompare(a.b))[0]
    const vecinDreapta = lane.impl.filter((x) => x.id !== im.id && x.a > f0).sort((a, b) => a.a.localeCompare(b.a))[0]
    // CAPATUL URMARESTE DEGETUL, CUANTIZAREA DOAR SE COMITE.
    // Pana acum previzualizarea se desena din ziua cuantizata, deci trasul arata
    // asa: ~700ms in care nu se misca NIMIC, apoi un salt de o zi intreaga (masurat:
    // +84px, +76px, +75px la 14z). E exact defectul reparat pentru repere, unde
    // `tragereTimeline` scrie un `--dx` continuu si lasa cuantizarea doar pentru ce
    // se COMITE — perioadele n-au primit niciodata tratamentul ala.
    // Limitele se calculeaza O DATA, la apucare: pana unde are voie sa ajunga
    // capatul, ca sina sa nu treaca peste vecin si sa fie smucita inapoi.
    const zMin = vecinStanga ? addDays(vecinStanga.b, 1) : plan.start
    const zMax = vecinDreapta ? addDays(vecinDreapta.a, -1) : addDays(plan.start, plan.days - 1)
    const limSt = spanRect(zMin, f0, plan.start, plan.days)
    const limDr = spanRect(s0, zMax, plan.start, plan.days)
    const stMin = limSt ? limSt.left : 0
    const drMax = limDr ? limDr.left + limDr.width : 100
    const pctDinX = (x) => {
      const r = pista.getBoundingClientRect()
      return Math.min(100, Math.max(0, ((x - r.left) / r.width) * 100))
    }
    const MIN_LAT = 0.4  // sub asta sina ar disparea de sub cursor
    incepeTragere(e, {
      laInceput: () => { intindere = { id: im.id, a: s0, b: f0, viu: im.rect } },
      laMiscare: (x) => {
        const zi = ziDinX(x)
        let a = s0
        let b = f0
        if (capat === 'start') {
          a = zi > f0 ? f0 : zi
          if (vecinStanga && a <= vecinStanga.b) a = addDays(vecinStanga.b, 1)
        } else {
          b = zi < s0 ? s0 : zi
          if (vecinDreapta && b >= vecinDreapta.a) b = addDays(vecinDreapta.a, -1)
        }
        // Geometria VIE, in procente din pista — continua, nu pe zile.
        const p = pctDinX(x)
        const l0 = im.rect.left
        const dr0 = im.rect.left + im.rect.width
        let viu
        if (capat === 'start') {
          const st = Math.min(Math.max(p, stMin), dr0 - MIN_LAT)
          viu = { left: st, width: dr0 - st }
        } else {
          const dr = Math.max(Math.min(p, drMax), l0 + MIN_LAT)
          viu = { left: l0, width: dr - l0 }
        }
        intindere = { id: im.id, a, b, viu }
      },
      laFinal: async () => {
        const v = intindere
        if (!v || (v.a === s0 && v.b === f0)) { intindere = null; return }
        // PREVIZUALIZAREA SE TINE PANA CAND SOSESC DATELE NOI.
        // Stearsa aici, banda se randa un cadru din `im.rect` — geometria VECHE —
        // si abia apoi din raspuns: masurat, un salt inapoi de 235px chiar in
        // clipa in care ridici degetul. `finally` o scoate si pe eroare, unde
        // `loadPlan()` readuce oricum starea de pe server.
        try {
          await apiJson(`/api/implementari/${im.id}`, {
            method: 'PUT', body: { data_start: v.a, data_sfarsit: v.b },
          })
          toastUndo(`Perioadă: ${intervalScurt(v.a, v.b)}`, {
            onUndo: async () => {
              await apiJson(`/api/implementari/${im.id}`, {
                method: 'PUT', body: { data_start: s0, data_sfarsit: f0 },
              })
              await loadPlan()
            },
          })
          await loadPlan()
        } catch (e2) {
          toast(`Eroare: ${e2.message}`, 'error')
          await loadPlan()
        } finally {
          intindere = null
        }
      },
      laAnulare: () => { intindere = null },
    })
  }

  // `mpContext` a plecat odata cu pista de perioade: era propozitia din capul ei
  // („14–15 aug: două în paralel"), si n-are gazda in grila de luna — acolo o zi
  // spune cate TASKURI are, nu cate perioade se suprapun. Coliziunea de perioade
  // rămâne vizibila pe swimlane-ul de desktop, unde benzile stau una sub alta.

  // CLIENTUL E SUFIXUL NUMELUI, SI E SINGURUL CARE SPUNE UNDE DUCE BANDA.
  // Proiectele se cheama „Migrare CU240S — Continental": partea dinaintea liniutei
  // se deosebeste de la primele caractere, cea de dupa e clientul — adica exact ce
  // manca trunchierea la dreapta a unui nume de 240px. Desenat (5a): titlul pe
  // randul intai, „Continental · 5 taskuri" pe al doilea.
  // Se taie DOAR pe liniuta lunga sau medie, cu spatii in jur. Cratima simpla nu:
  // „Revizie - hala 3" ar pierde jumatate de nume si ar castiga un client inventat.
  // Fara liniuta, proiectul n-are client scris in nume si randul al doilea ramane
  // doar numarul („2 taskuri", ca banda generala din desen).
  // `numeIntreg` ramane pentru `title` si pentru cautare: pe ecran numele se scurteaza,
  // in tooltip nu — altfel doua proiecte cu acelasi inceput devin imposibil de deosebit
  // fara sa le deschizi.
  function despartClient(nume) {
    const m = String(nume || '').match(/^(.+?)\s+[—–]\s+(.+)$/)
    return m ? { nume: m[1], client: m[2], numeIntreg: nume } : { nume, client: '', numeIntreg: nume }
  }

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
  // 6 sus, n randuri de 20 cu 4 intre ele, si FASIA SINEI jos.
  // Fasia e 20: sina de 4 la `bottom: 6`, iar pastila de 16 o incaleca centrat,
  // deci ii trebuie exact atat cat sa nu atinga ultimul reper.
  // 1 reper 46 · 2 repere 70 · 3 repere 94 (era 48 · 64 · 88, dar acolo randul
  // intai era mancat de eticheta benzii).
  const H_REPER = 20
  const H_GOL = 4
  const H_SINA = 20
  function geometrieBanda(n) {
    const r = Math.max(1, n)
    const stiva = r * H_REPER + (r - 1) * H_GOL
    // `min-height`, nu `height`: coloana de nume poate cere mai mult (numele de
    // proiect plus contorul plus chipul de tip). De aceea stiva se ANCOREAZA SUS
    // (`.lane-track` are `justify-content: flex-start`) si nu se centreaza: altfel
    // surplusul cerut de coloana din stanga ar cobora reperele in fasia sinei —
    // masurat, exact asa aparea o suprapunere intre eticheta perioadei si titlul
    // unui task.
    return { inaltime: Math.max(44, 6 + stiva + H_SINA), stiva }
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

  // BANDA DE PREGATIRE A PLECAT (Ion, 2026-08-15): „e clar ca este in pregatire
  // fara sa vad pe planificator". Era un lucru DERIVAT — complementul etapelor,
  // nu o data introdusa de cineva — desenat cu capatul stang estompat fiindca
  // „de cand se pregateste" nu se stie. Adica o banda care ocupa toata pista ca
  // sa spuna ceva ce statusul proiectului spune deja, si al carei capat isi
  // recunostea singur ca e inventat. `.impl-band` (perioadele reale, cu zile
  // reale) ramane; faza `pregatire` a unei PERIOADE ramane si ea — aceea e o
  // perioada pe care ai pus-o tu in Calendar, nu un gol.

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
    // PASTILA INCAPE SAU NU SE RANDEAZA — nu se taie niciodata.
    // Golul se masoara pana la INCEPUTUL perioadei urmatoare, nu pana la sfarsitul
    // celei de fata: pastila sta la capul sinei si se intinde la dreapta peste ea,
    // deci ce o poate lovi e vecina, nu propria durata. De asta o perioada de o zi
    // isi poate scrie locul intreg daca dupa ea urmeaza o saptamana goala — exact
    // cazul pe care vechea regula (prag in procente din fereastra) il rata.
    const impl = contopeste(lane.implementari)
      .map(im => ({ ...im, rect: spanRect(im.a, im.b, plan.start, plan.days) }))
      .filter(im => im.rect)
      .sort((a, b) => a.rect.left - b.rect.left)
      .map((im, i, toate) => {
        const urm = toate[i + 1]
        const golPct = (urm ? urm.rect.left : 100) - im.rect.left
        const golPx = (golPct / 100) * pistaPx
        return { ...im, pastila: latimeTitlu(locLabel(im.locatie)) + PASTILA_CHROME <= golPx }
      })
    // IMPACHETAREA NU MAI ARE CE BLOCA.
    // `blocate` exista fiindca eticheta benzii se scria peste rand si trebuia sa
    // impinga reperele in jos. Sina sta sub ei, in fasia ei, deci randul intai e
    // liber — de aici vine si scaderea de inaltime: 112px -> 95px pe banda cea
    // mai incarcata, fara sa se piarda nimic de pe ecran.
    const repere = lung
      ? numerePeSaptamana(tasks, columns.cols, pistaPx)
      : tasks.filter(t => t.rect)
          .map(t => ({ ...t, span: intinderea(t, pistaPx) }))
          .sort((a, b) => a.span.de - b.span.de || a.span.la - b.span.la)
    const packed = packRows(repere, [])
    // Restantele vin de la server ca lista proprie: sunt INAINTEA ferestrei, deci
    // n-au geometrie si nu pot sta pe pista. Vezi `.rest-col`.
    const restante = lane.restante || []
    return { ...lane, ...despartClient(lane.nume), color, tasks, packed, geo: geometrieBanda(packed.length), impl, restante }
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
  // `grupeazaBanda` a plecat: imparțea fereastra in „Restante / Azi / Zilele
  // următoare", iar lista mobila arata acum o SINGURA zi — deci n-ar avea ce sa
  // imparta. Aceeasi grupare traieste in /tasks (`lib/grupare.js`), unde lista
  // chiar acopera mai multe zile.

  // PERIOADA, SCRISA O SINGURA DATA.
  // Era desenata in banda (unde e decor) si repetata dedesubt ca `.mimpl` — un rand
  // intreg de 44px per perioada, deci un proiect cu trei perioade primea trei
  // randuri INAINTEA primului task. Ramane cea in curs (sau urmatoarea), cu „+N".
  function perioadaDeAratat(lane) {
    // `?? []`, nu `lane.impl.length` direct: functia se cheama acum si din lista
    // de pe telefon, pe benzi care trec prin `laneuriZiua`. Cand aceea citea
    // benzile brute (fara `impl`), linia asta arunca si BLOCA pagina — raportat de
    // Ion. Sursa s-a reparat, dar garda rămâne: e o functie chemata din doua locuri.
    if (!(lane.impl || []).length) return null
    const azi = plan.today || ''
    const inCurs = lane.impl.find(im => im.a <= azi && azi <= im.b)
    const urmatoarea = lane.impl.find(im => im.a > azi)
    return { im: inCurs || urmatoarea || lane.impl[0], rest: lane.impl.length - 1 }
  }
  function locLabel(l) { return l === 'sediu' ? 'Sediu EGB' : 'Site' }

  /** Adresa Calendarului pentru o perioada: ziua ei SI cine e.
   *
   *  Pana acum se trimitea doar `?zi=`, deci ajungeai pe ziua buna si trebuia sa
   *  cauti singur care dintre benzile de acolo e cea pe care ai apasat — intr-o zi
   *  cu trei lucrari, click-ul nu mai avea raspuns. Cu `?per=` Calendarul stie pe
   *  cine sa aprinda.
   *
   *  `parti`, nu `id`: o banda din Planificator poate fi mai multe perioade
   *  CONTOPITE (vezi `contopeste` — zile consecutive la acelasi loc sunt un singur
   *  obiect pe ecran). Trimise toate, se aprind toate; trimis doar id-ul benzii,
   *  s-ar aprinde prima si restul deplasarii ar ramane stinsa, chiar daca pe ecran
   *  arata ca un intreg. */
  function linkCalendar(im) {
    const ids = (im.parti?.length ? im.parti : [im]).map(p => p.id).filter(Boolean).join(',')
    return `/calendar?zi=${im.a}${ids ? `&per=${encodeURIComponent(ids)}` : ''}`
  }

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

  // PANOUL SE DESCHIDE CU DATELE IN MANA (regula deja scrisa in aplicatie —
  // vezi `desfacere` din `motion.svelte.js` si TaskPickerModal).
  //
  // Ion: „parca ceva vine de jos... e rupta animatia". Masurat cadru cu cadru:
  // panoul se deschidea la 493px si se stangea la 404 in timpul propriei
  // intrari, fiindca `sel` se punea INAINTE ca subtaskurile sa soseasca —
  // deci marginea lui de jos matura in sus peste animatie. O tranzitie care
  // anima spre o tinta ce se schimba sub ea nu se poate citi ca o sosire.
  //
  // Plafon de 250ms, ca la selectorul de taskuri: peste atat panoul se deschide
  // oricum, cu SCHELET in locul pasilor — un loc tinut e o inlocuire, nu un
  // salt. Sub plafon nu se vede niciodata.
  async function deschideTask(task, lane, el) {
    anchorEl = el || null
    const baza = { ...task, laneNume: lane?.nume, laneId: lane?.id, laneImpl: lane?.impl || [] }
    pasi = []
    if (!task.subtask_total) { pasiSeIncarca = false; sel = baza; return }

    let sosit = false
    const cerere = loadSubtasks(task.id)
      .then((r) => { pasi = r })
      .catch(() => { pasi = [] })
      .finally(() => { sosit = true })
    await Promise.race([cerere, new Promise((r) => setTimeout(r, 250))])
    // Scheletul se arata DOAR daca datele chiar intarzie; altfel panoul se
    // deschide direct cu lista, la inaltimea ei finala.
    pasiSeIncarca = !sosit
    sel = baza
    if (!sosit) await cerere.finally(() => { pasiSeIncarca = false })
  }
  function closePop() { sel = null; anchorEl = null; pasi = [] }

  async function comutaPas(p) {
    // Optimist, ca in /tasks: fractia din antet se recalculeaza din lista.
    pasi = pasi.map(x => x.id === p.id ? { ...x, done: p.done ? 0 : 1 } : x)
    try {
      await updateSubtask(p.id, { done: p.done ? 0 : 1 })
      // SI RANDUL DE DEDESUBT ISI SCRIE FRACTIA de la 2026-08-15 incoace, dar el
      // o ia din `t.subtask_done`, adica din raspunsul /api/plan. Fara
      // reincarcare, panoul ar arata „3/5" si randul din spatele lui „2/5" —
      // aceeasi intrebare cu doua raspunsuri, pe acelasi ecran. `updateSubtask`
      // a invalidat deja cache-ul, deci asta chiar ajunge la server.
      await loadPlan()
      if (sel) {
        let found = null
        for (const lane of views) {
          const t = lane.tasks.find(t => t.id === sel.id)
          if (t) { found = { ...t, laneNume: lane.nume, laneId: lane.id, laneImpl: lane.impl || [] }; break }
        }
        sel = found
      }
    } catch (e) {
      pasi = pasi.map(x => x.id === p.id ? { ...x, done: p.done } : x)
      toast(`Eroare: ${e.message}`, 'error')
    }
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
  // ===== FOAIA RANDULUI DE PE TELEFON =====
  //
  // Doua guri, aceeasi foaie (`components/FoaieTask.svelte`): glisarea la stanga
  // o deschide pe „Planifică" (verbul e deja scris pe pista, deci nu se mai
  // repeta), apasarea lunga o deschide pe actiuni. Panoul de detaliu de pe
  // DESKTOP (`.panou`, mai jos) ramane cum era — acolo exista loc pentru el si nu
  // se acopera nimic.
  let foaieTask = $state(null)
  let foaieMod = $state('actiuni')
  let foaieDeschisa = $state(false)

  function deschideFoaia(t, mod) {
    foaieTask = t
    foaieMod = mod
    foaieDeschisa = true
  }

  // `onMove` se opreste la o data goala (e scris pentru `DatePicker`, care nu
  // trimite niciodata null). Foaia POATE trimite null — „Scoate din calendar" din
  // `SelectorZi` — deci cazul are nevoie de propriul drum, altfel butonul acela
  // ar fi mut exact aici.
  async function planificaDinFoaie(t, v) {
    if (!t) return
    try {
      if (v) { await moveTaskDate(t.tip, t.id, v); toast(`Mutat pe ${formatDate(v)}`, 'success') }
      else { await setTaskDates(t.tip, t.id, { data_scadenta: null }); toast('Scos din calendar', 'success') }
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    closePop()
  }

  // STERGEREA E REVERSIBILA, SI DE ASTA E ACCEPTABILA DINTR-UN GEST.
  //
  // Aceeasi mecanica ca la subtaskuri in /tasks si in pagina proiectului: randul
  // pleaca din `plan.lanes` pe loc, iar scrierea pe server se face abia cand
  // toastul expira (`onCommit`). „Anulează" nu cheama nimic pe server — pune
  // randul la loc exact acolo unde era, fiindca nici n-a plecat vreodata.
  function stergeDinPlan(t) {
    const cheie = t.tip + ':' + t.id
    let loc = null
    for (const lane of plan.lanes) {
      const i = (lane.tasks || []).findIndex(x => x.tip + ':' + x.id === cheie)
      if (i !== -1) { loc = { lane, i, task: lane.tasks[i] }; break }
    }
    if (!loc) return
    loc.lane.tasks = loc.lane.tasks.filter(x => x.tip + ':' + x.id !== cheie)
    closePop()
    toastUndo('Task șters', {
      onUndo: () => {
        const cur = [...(loc.lane.tasks || [])]
        cur.splice(Math.min(loc.i, cur.length), 0, loc.task)
        loc.lane.tasks = cur
      },
      onCommit: async () => {
        try { await deleteTaskPlan(t.tip, t.id) }
        catch (e) { toast(`Eroare: ${e.message}`, 'error'); await loadPlan() }
      },
    })
  }

  // ===== GRILA DE LUNA (telefon) =====
  //
  // A INLOCUIT PISTA DE PERIOADE (`.mpiste`). Pista raspundea la „cand sunt pe
  // teren"; grila raspunde la „cat am de facut, si cand" — iar pe telefon a doua
  // intrebare e cea cu care deschizi Planificatorul. Perioadele n-au dispărut din
  // aplicatie: stau pe randul lor din fiecare card (`.mimpl`, cu interval si
  // chevron catre Calendar) si pe swimlane-ul de desktop, unde au latime.
  //
  // PATRU SAPTAMANI, LUNI-PRIMA, incepand de LUNI SAPTAMANA ASTA — nu de azi.
  // O grila care porneste de la ziua curenta are prima linie strambă si nu se mai
  // citeste ca un calendar; iar zilele DINAINTE de azi din saptamana curenta sunt
  // exact cele care pot avea restante, adica singurul lucru din grila care cere
  // actiune imediata.
  const gridStart = $derived.by(() => {
    const azi = plan.today || localToday()
    const d = parseISO(azi)
    if (!d) return azi
    // getDay(): 0 = duminica. Luni-prima => duminica e a 7-a zi, deci 6 in urma.
    const inapoi = d.getDay() === 0 ? 6 : d.getDay() - 1
    return addDays(azi, -inapoi)
  })

  const SAPT_GRILA = 4
  const ZILE_GRILA = SAPT_GRILA * 7

  // ORIZONTUL TREBUIE SA ACOPERE GRILA, altfel densitatea MINTE: `/api/plan`
  // intoarce taskuri doar in fereastra cerută, iar la 14 zile ultimele doua
  // saptamani ar arata goale — adica „n-ai nimic", cand de fapt „nu s-a cerut".
  // 30 e o valoare care exista deja in `HORIZONS`, deci nu se inventeaza niciun
  // mod nou; iar grila se termina cel mai tarziu la azi+27 (cand azi E luni).
  // Segmentul de orizont e ascuns pe telefon (`.seg { display: none }`), deci
  // nimeni nu se lupta cu alegerea asta.
  //
  // O SINGURA DATA, prin steag, si nu doar din condiţie. Efectul CITESTE `plan.days`
  // si cheama ceva care il SCRIE (`setHorizon` -> `loadPlan` -> `plan.days =
  // data.days || plan.days`). Condiţia singura ar fi de ajuns cat timp serverul
  // intoarce exact ce a primit — si chiar face asta, `days` e plafonat la [1, 370],
  // deci 30 trece intreg. Dar asta e o proprietate a CELEILALTE parti, la un capat
  // de care efectul n-are control: daca plafonul de acolo s-ar strange vreodata sub
  // 30, efectul ar cere 30, ar primi mai putin, si ar cere din nou — la infinit,
  // adica exact felul de blocare pe care pagina asta a avut-o deja o data astazi.
  let orizontUrcat = false
  $effect(() => {
    if (orizontUrcat || !ecran.telefon) return
    if (plan.days < ZILE_GRILA + 2) {
      orizontUrcat = true
      setHorizon(30)
    }
  })

  /** Toate taskurile ferestrei, cu restantele lor, intr-o singura lista plata.
   *
   *  DIN `views`, NU din `plan.lanes`. Prima versiune citea benzile BRUTE, si de
   *  acolo venea o blocare a paginii raportata de Ion: `views` e cel care adauga
   *  `color`, numele despartit de client si — critic — `impl` (perioadele contopite
   *  si decupate pe fereastra). Pe o banda bruta `impl` nu exista, iar
   *  `perioadaDeAratat` face `lane.impl.length` pe fiecare card: prima randare
   *  arunca `TypeError`, iar pagina rămâne goala.
   *  `views` e un superset, nu un filtru — mapeaza TOATE taskurile benzii si le
   *  adauga geometrie — deci si numaratoarea din grila e completa. */
  const toateTaskurile = $derived.by(() => {
    const out = []
    for (const lane of views) {
      for (const t of lane.tasks || []) out.push(t)
      for (const t of lane.restante || []) out.push(t)
    }
    return out
  })

  /** Cate taskuri si cate restante cad pe fiecare zi. Se socoteste O DATA pentru
   *  toata grila, nu per celula: 28 de celule × N taskuri ar fi o parcurgere
   *  pentru fiecare zi, la fiecare randare. */
  const GOL_ZI = () => ({ n: 0, restante: 0, gata: 0, impl: false, pregatire: false })

  const perZi = $derived.by(() => {
    const m = new Map()
    const ia = (zi) => {
      let c = m.get(zi)
      if (!c) { c = GOL_ZI(); m.set(zi, c) }
      return c
    }
    for (const t of toateTaskurile) {
      const zi = String(t.data_scadenta || '').slice(0, 10)
      if (!zi) continue
      const c = ia(zi)
      c.n++
      if (isDone(t.status)) c.gata++
      else if (esteRestant(t.data_scadenta)) c.restante++
    }
    // PERIOADELE DE IMPLEMENTARE, PE ZILE. Ion: „ar trebui segmente de implementare
    // sa se deosebeasca de taskuri." Ele nu sunt taskuri si nu se numara cu ele: un
    // task e un lucru de bifat, o perioada e o fasie de timp in care ESTI undeva.
    // De asta nu intra in `n` — ar amesteca doua unitati intr-o singura cifra — ci
    // primesc doua steaguri, iar celula le deseneaza cu alta FORMA (banda continua
    // sub segmente; vezi CSS).
    // Faza pastreaza regula sistemului: plin = implementare, contur/palid =
    // pregatire (aceeasi ca pe swimlane si in Calendar).
    for (const lane of views) {
      for (const im of lane.impl || []) {
        if (!im.a || !im.b) continue
        for (let z = im.a; z <= im.b; z = addDays(z, 1)) {
          const c = ia(z)
          if (im.faza === 'pregatire') c.pregatire = true
          else c.impl = true
          if (z === im.b) break
        }
      }
    }
    return m
  })

  const celuleGrila = $derived.by(() =>
    buildDays(gridStart, ZILE_GRILA).map(z => ({
      ...z,
      ...(perZi.get(z.iso) || GOL_ZI()),
    }))
  )

  /** Ziua aleasa din grila. Implicit AZI — deschizi pagina si vezi ce ai azi, nu
   *  o lista goala care asteapta o atingere. */
  let ziAleasa = $state('')
  const ziActiva = $derived(ziAleasa || plan.today || localToday())

  /** CATE segmente se desenează intr-o celula, si de ce cifra asta.
   *
   *  Ion: „pe planificator nu ar trebui sa pot vedea cate intrari sunt? gen mai
   *  multe segmente unul langa altul." Avea dreptate, si nu doar ca preferinta:
   *  o bara a carei LATIME spune incarcarea se citeste comparativ („ziua asta are
   *  mai mult decat aia"), dar nu se poate NUMARA — iar cand te uiti la o zi vrei
   *  sa stii daca ai doua lucruri sau cinci.
   *  Deci: un segment per intrare, unul langa altul.
   *
   *  PLAFON 4, si se SPUNE cand s-a atins. Celula are ~48px pe 390: patru segmente
   *  de 7px cu 3px intre ele fac 37 — incap cu aer. La al cincilea ar trebui sa
   *  scad latimea segmentului, si atunci n-ar mai fi numarabil, care e tot rostul.
   *  Peste plafon, ultimul segment devine „mai mult" (vezi `.mg-seg.plus` in CSS):
   *  un plafon care nu se anunta arata ca o numaratoare exacta si minte. */
  const MAX_SEG = 4
  const segmente = (c) => {
    const total = c.n
    if (!total) return []
    const out = []
    // Ordinea in care se desenează spune severitatea, nu doar numarul: restantele
    // intai, apoi ce e de facut, apoi ce s-a facut. Ochiul citeste de la stanga.
    for (let i = 0; i < Math.min(total, MAX_SEG); i++) {
      const rest = i < c.restante
      const gata = !rest && i >= (total - c.gata)
      out.push({ rest, gata, plus: total > MAX_SEG && i === MAX_SEG - 1 })
    }
    return out
  }

  /** Capetele de zi ale grilei, luni-prima. Din ACELEASI initiale ca antetul de
   *  coloane al swimlane-ului (`buildDays().wd`), ca sa nu existe doua tabele. */
  const capeteZile = $derived.by(() => buildDays(gridStart, 7).map(z => z.wd))

  /** Taskurile zilei alese, grupate pe proiecte — carduri, ca pana acum. */
  const laneuriZiua = $derived.by(() => {
    const zi = ziActiva
    const out = []
    for (const lane of views) {
      const ale = [...(lane.tasks || []), ...(lane.restante || [])]
        .filter(t => String(t.data_scadenta || '').slice(0, 10) === zi)
      if (ale.length) out.push({ ...lane, tasksZi: ale })
    }
    return out
  })

  const numarZiua = $derived(perZi.get(ziActiva)?.n || 0)
  const restanteZiua = $derived(perZi.get(ziActiva)?.restante || 0)

  /** „marți 18 august" — capul zilei alese. */
  const etichetaZiua = $derived.by(() => {
    const d = parseISO(ziActiva)
    if (!d) return ''
    return d.toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'long' })
  })

  // Randul care isi joaca stampila chiar acum (`.bifare`, reguli in global.css).
  let bifatAcum = $state('')
  async function onDone(t, dinGest = false) {
    // Stampila + taietura inainte ca randul sa plece — nu si pe gest, unde
    // verdele pistei si zborul sunt deja raspunsul.
    if (!isDone(t.status) && !dinGest) {
      bifatAcum = t.tip + ':' + t.id
      await new Promise(r => setTimeout(r, motionDuration(400)))
      bifatAcum = ''
    }
    try {
      const res = await toggleTaskDone(t.tip, t.id, t.status)
      if (res?.recurring_spawned) toast(`Finalizat ✓ — următoarea: ${formatDate(res.recurring_next)}`, 'success')
      else toast(isDone(t.status) ? 'Redeschis' : 'Finalizat ✓', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    closePop()
  }

  function onKey(e) { if (e.key === 'Escape') closePop() }

  /* `arata()` a plecat odata cu reperele din pista mobila (V11): ducea de la un
     punct din banda la randul lui din lista. Pista comuna de sus arata perioade,
     nu taskuri — taskurile traiesc doar in listele din carduri, unde sunt deja
     la latime intreaga. `data-rand` ramane pe rand: il foloseste `lib/focus.js`
     cand aterizezi pe un task venind din alta pagina. */

  // --- drag / resize (desktop swimlane) ---
  let drag = null
  let dragLabel = $state(null)
  // Pozitia cursorului pentru eticheta de tragere. Se tine SEPARAT de gest:
  // `tragePeZile` raporteaza deplasarea in zile, nu coordonate de ecran, iar
  // eticheta trebuie sa stea langa deget.
  let pozLabel = $state({ x: 0, y: 0 })
  function urmarestePointer(e) { if (dragLabel) pozLabel = { x: e.clientX, y: e.clientY } }

  // REPERUL URMARESTE DEGETUL, NU SARE DIN ZI IN ZI (T7).
  // Vechea varianta scria `style.left` in procente, cuantizat cu
  // `Math.round(dx / dayW)`: pana treceai jumatate de zi (~32px la 14z) nu se
  // misca NIMIC pe ecran, apoi sarea o zi intreaga. Acum `--dx` e continuu, iar
  // rotunjirea se face doar pentru ziua care se aprinde si la commit.
  function startDrag(e, t, mode, lane) {
    if (isDone(t.status)) return // finished tasks are read-only on the timeline
    const barEl = e.currentTarget.closest('.bar')
    const trackEl = barEl?.closest('.lane-track')
    if (!barEl || !trackEl) return
    const baza = (t.data_scadenta || '').slice(0, 10)
    if (!baza) return
    e.stopPropagation()
    tragePeZile(e, {
      pista: trackEl, obiect: barEl,
      zile: plan.days, ziStart: plan.start, ziObiect: baza,
      laInceput: () => document.body.classList.add('plan-dragging'),
      laPreview: ({ zi, dx }) => { dragLabel = { dx, text: `termen ${formatDateShort(zi)}` } },
      laAtingere: () => {
        document.body.classList.remove('plan-dragging')
        dragLabel = null
        deschideTask(t, lane, barEl)
      },
      laAnulare: () => {
        document.body.classList.remove('plan-dragging')
        dragLabel = null
      },
      laCommit: async (zi) => {
        document.body.classList.remove('plan-dragging')
        dragLabel = null
        // O SINGURA REINCARCARE. `setTaskDates` cheama deja `loadPlan()` in el
        // (vezi `stores/plan.svelte.js`), deci un al doilea apel aici insemna ca
        // pista se reconstruia de DOUA ori dupa fiecare mutare — exact ce
        // raporteaza Ion: „se pare ca se reincarca pagina, apoi se pune".
        // Pe eroare se reincarca, fiindca atunci starea locala e cea gresita.
        //
        // `await tick()` la final NU e decor: `tragePeZile` tine reperul pe ziua
        // aleasa (prin `--dx`) pana cand functia asta se intoarce, si abia apoi
        // scoate offsetul. Daca ne-am intoarce inainte ca DOM-ul sa aiba noul
        // `left`, offsetul ar fi scos peste pozitia veche si reperul ar clipi
        // inapoi. Aterizarea (FLIP) a plecat de aici tocmai fiindca nu mai are
        // ce ateriza: obiectul nu pleaca niciodata de pe ziua pe care l-ai lasat.
        try {
          await setTaskDates(t.tip, t.id, { data_scadenta: zi })
          toast('Reprogramat', 'success')
        } catch (err) {
          toast(`Eroare: ${err.message}`, 'error')
          await loadPlan()
        }
        await tick()
      },
    })
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

<svelte:window onpointermove={urmarestePointer} />

<!-- Ca in Calendar: invelisul urca, apoi celulele. Antetul paginii nu e celula,
     e cadrul — urca odata cu invelisul. `.chart` si `.mlist` nu se vad niciodata
     impreuna (820px le comuta), dar indicii merg mai departe prin `.backlog`, ca
     pe telefon — unde sertarul sta DEASUPRA listei — capul sa nu soseasca dupa
     coada. -->
<div class="page ruta-in">
  <div class="page-header">
    <!-- Fara iconita in fata titlului: desenele n-o au, iar cu ea h1-ul cadea
         la alt `left` decat pe restul rutelor (standardizarea titlurilor). -->
    <div class="page-title-row">
      <h1>Planificator</h1>
      <!-- Ce fereastra vezi, scris o data. Antetul de timp n-o mai spune: acolo
           luna ar fi un al treilea nivel peste saptamani si zile. -->
      <!-- Doua subtitluri, fiindca sunt doua ecrane: pe desktop fereastra e ALEASA
           (de aici „de azi, 14 zile"), pe telefon e FIXA — grila de patru
           saptamani — deci se scrie doar ce interval vezi. -->
      {#if ecran.telefon}
        {#if subtitluGrila}<span class="page-sub"><span class="ps-n">{subtitluGrila}</span></span>{/if}
      {:else if subtitlu}
        <span class="page-sub">de azi, <span class="ps-n">{subtitlu.catN}</span>&nbsp;{subtitlu.catRest} · <span class="ps-n">{subtitlu.interval}</span></span>
      {/if}
    </div>
    <div class="controls">
      <div class="seg" role="group" aria-label="Orizont">
        {#each HORIZONS as h}
          <button class="seg-btn" class:active={plan.days === h.d} class:seg-6l={h.d === 180} onclick={() => setHorizon(h.d)}>{h.l}</button>
        {/each}
      </div>
      <button class="toggle" class:on={plan.showWeekends} disabled={unit !== 'day'} onclick={toggleWeekends} title={unit === 'day' ? 'Evidențiază weekendurile' : 'Weekendurile apar doar în vederea pe zile'}>
        <span class="tk-box">{#if plan.showWeekends}<Check size={11} strokeWidth={3} />{/if}</span> Weekend
      </button>
      <button class="toggle" class:on={plan.showDone} onclick={toggleShowDone} title="Arată taskurile finalizate">
        <span class="tk-box">{#if plan.showDone}<Check size={11} strokeWidth={3} />{/if}</span> Finalizate
      </button>
      <button class="toggle export" onclick={openExport} disabled={plan.lanes.length === 0} title="Exportă ca PDF (print)">
        <FileDown size={14} /> <span class="tg-lung">Export </span>PDF
      </button>
    </div>
  </div>

  <!-- `!incarcat`, fara `loading`: daca n-avem inca un raspuns, ASTEPTAM — prin
       definitie. Cu `loading &&` in fata, primul cadru (inainte ca incarcarea sa
       apuce sa porneasca) cadea pe ramura urmatoare si arata STAREA GOALA, apoi
       scheletul, apoi raspunsul: trei forme pentru un board gol. -->
  {#if !plan.incarcat && !plan.error}
    <div class="skel asteptare">{#each Array(4) as _}<Skeleton height="72px" />{/each}</div>
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
                    <button class="lane-name" onclick={(e) => morphNavigate(e.currentTarget, `/projects/${lane.id}`, 'project', lane.id)} title={lane.numeIntreg}>
                      <span class="lane-dot"></span>
                      <span class="lane-col">
                        <span class="lane-txt">{lane.nume}</span>
                        <!-- CLIENTUL, APOI CATE. Randul scria doar cifra, iar cifra
                             singura nu spune UNDE te duce banda — la fel arata trei
                             proiecte diferite. Numarul ramane mono (se compara pe
                             verticala cu vecinii), clientul e text.
                             Restantele NU se mai scriu aici: au coloana lor, cu ziua
                             scrisa in chip, iar inghesuite pe acelasi rand mancau
                             exact clientul pe care il aduce inapoi punctul asta. -->
                        <span class="lane-contor">{#if lane.client}{lane.client}{' · '}{/if}<span class="lc-n">{lane.tasks.length}</span> {lane.tasks.length === 1 ? 'task' : 'taskuri'}</span>
                      </span>
                    </button>
                    {#if lane.tip_proiect}<span class="tip-chip" class:svc={lane.tip_proiect === 'Service'}>{lane.tip_proiect}</span>{/if}
                  {:else}
                    <span class="lane-name static">
                      <span class="lane-dot"></span>
                      <span class="lane-col">
                        <span class="lane-txt">{lane.nume}</span>
                        <span class="lane-contor">{#if lane.client}{lane.client}{' · '}{/if}<span class="lc-n">{lane.tasks.length}</span> {lane.tasks.length === 1 ? 'task' : 'taskuri'}</span>
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
                    <!-- `div role="button"`, nu `<button>`: manerele de capat sunt
                         ele insele butoane, iar buton in buton e markup invalid —
                         aceeasi solutie ca la celula din Calendar. Previzualizarea
                         intinderii se deseneaza LIVE, din `intindere`, nu din rect. -->
                    <!-- Geometria VIE cat timp tragi: `viu` e continua (urmareste
                         degetul), nu cuantizata pe zi. Ce se COMITE ramane `a`/`b`,
                         adica zilele — vezi `apucaCapatImpl`. -->
                    {@const rct = intindere?.id === im.id ? (intindere.viu || im.rect) : im.rect}
                    <div class="impl-band loc-{im.locatie}" style="left:{rct.left}%; width:{rct.width}%"
                         class:pregatire={im.faza === 'pregatire'}
                         class:lat={im.rect.width >= inProcente(24, pistaPx)}
                         class:se-trage={intindere?.id === im.id}
                         class:clipL={im.rect.clippedLeft} class:clipR={im.rect.clippedRight}
                         role="button" tabindex="0"
                         onclick={() => { if (!intindere) navigate(linkCalendar(im)) }}
                         onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(linkCalendar(im)) } }}
                         title="{locLabel(im.locatie)}{im.eticheta ? ' · ' + im.eticheta : ''} · {im.faza === 'pregatire' ? 'pregătire' : 'implementare'} · {formatDateShort(im.a)} → {formatDateShort(im.b)} · {im.zile} {im.zile === 1 ? 'zi' : 'zile'}{im.parti.length > 1 ? ` · ${im.parti.length} perioade lipite` : ''} · click pentru a o vedea în Calendar">
                      <!-- PASTILA STA LA CAPUL VIZIBIL AL SINEI, NU LA ZIUA DE START.
                           Fereastra porneste mereu din azi, deci o deplasare in
                           CURS e taiata la stanga: inceputul ei e in trecut. Ancorata
                           la `left: 0` al benzii, pastila se aseaza atunci pe muchia
                           ferestrei si merge odata cu zilele, pe masura ce perioada
                           se scurteaza din stanga — adica ramane citibila exact cand
                           esti pe teren, cazul in care conteaza cel mai mult.
                           Ce NU are voie sa faca e sa para inceput: pe `clipL` sina
                           nu primeste terminator (vezi CSS), fiindca acolo ziua de
                           start nu e pe ecran. -->
                      {#if im.pastila}
                        <span class="ib-pastila">
                          {#if im.locatie === 'sediu'}<Building2 size={10} class="ib-ico" />{:else}<MapPin size={10} class="ib-ico" />{/if}
                          {locLabel(im.locatie)}
                        </span>
                      {/if}
                      <!-- Manerele de intindere — la hover, ca in Calendar. Nu si pe
                           benzile LIPITE (mai multe perioade): capatul lor apartine
                           altei perioade. Nu si pe capetele taiate de fereastra. -->
                      {#if im.parti.length === 1 && !ecran.telefon && !ecran.grosier}
                        {#if !im.rect.clippedLeft}
                          <button class="maner st" aria-label="Trage ca să schimbi începutul perioadei"
                                  onpointerdown={(e) => apucaCapatImpl(e, lane, im, 'start')}
                                  onclick={(e) => e.stopPropagation()}></button>
                        {/if}
                        {#if !im.rect.clippedRight}
                          <button class="maner dr" aria-label="Trage ca să schimbi sfârșitul perioadei"
                                  onpointerdown={(e) => apucaCapatImpl(e, lane, im, 'sfarsit')}
                                  onclick={(e) => e.stopPropagation()}></button>
                        {/if}
                      {/if}
                    </div>
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
                              data-task={it.id}
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
              <span class="fapt-val" class:sev={dueRing(sel.data_scadenta) !== RING_NEUTRU}
                    style="--ring: {dueRing(sel.data_scadenta)}">
                {sel.data_scadenta ? formatDate(sel.data_scadenta) : 'fără termen'}
              </span>
              <Calendar size={16} class="fapt-ico" />
            </div>
            <!-- Perioada peste care cade termenul. E un CHEVRON, nu un buton de
                 editare: perioadele se schimba in Calendar, iar clicul te duce
                 chiar in ziua ei. -->
            {#if per}
              <button class="fapt link" onclick={() => navigate(linkCalendar(per))}>
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
                {#if dueRing(t.data_scadenta) !== RING_NEUTRU}
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
      <!-- ===== PISTA COMUNA „PERIOADE" (turul 4c) =====
           O SINGURA PISTA, SUS. Erau doua obiecte care spuneau acelasi lucru: o
           scara proprie de 26px (cifra + initiala, inghesuite) SI cate o pista de
           26px in FIECARE card de proiect — adica aceeasi informatie desenata de N
           ori, fiecare cu antetul ei implicit si niciuna cu randul de saptamani.
           De aici venea si senzatia de „totul strans pe inaltime".
           Desenat: numele proiectelor intr-o coloana la stanga, pistele lor la
           dreapta, sub UN antet comun — saptamani peste cifre, aceeasi structura
           grosier-peste-fin ca pe desktop. Cardurile de dedesubt raman ce sunt:
           randul perioadei si taskurile.
           Geometria vine din aceleasi `columns` / `antet` ca pe desktop, deci nu e
           o a doua socoteala care sa se poata contrazice cu prima. -->
      <!-- ===== GRILA DE LUNA + DENSITATE =====
           Patru saptamani, luni-prima, celule de 52px. Cifra spune ZIUA, bara de
           sub ea spune CAT ai in ea — deci incarcarea saptamanii se citeste din
           forma, fara sa numeri nimic. Tenta spune STAREA: weekend (suprafata 2),
           zi cu restante (tenta de danger), ziua aleasa (fill de accent).
           A luat locul pistei de perioade: vezi nota de la `gridStart` in <script>. -->
      <section class="mgrila">
        <div class="mg-zile" aria-hidden="true">
          {#each capeteZile as z}<span class="mg-zi-cap">{z}</span>{/each}
        </div>
        <div class="mg-celule" role="group" aria-label="Alege ziua">
          {#each celuleGrila as c (c.iso)}
            <button class="mg-cel"
                    class:we={c.isWeekend}
                    class:azi={c.iso === plan.today}
                    class:rest={c.restante > 0}
                    class:activa={c.iso === ziActiva}
                    aria-pressed={c.iso === ziActiva}
                    aria-label="{c.dayNum} {c.month} — {c.n} {c.n === 1 ? 'task' : 'taskuri'}{c.restante ? `, ${c.restante} restante` : ''}{c.gata ? `, ${c.gata} făcute` : ''}{c.impl ? ', implementare' : c.pregatire ? ', pregătire' : ''}"
                    onclick={() => ziAleasa = c.iso}>
              <span class="mg-nr">{c.dayNum}</span>
              <!-- SEGMENTELE se randeaza DOAR cand exista ceva: 28 de urme de
                   lungime zero n-ar spune nimic si ar face grila sa arate ocupata. -->
              {#if c.n > 0}
                <span class="mg-seg-rand" aria-hidden="true">
                  {#each segmente(c) as s}
                    <span class="mg-seg" class:rest={s.rest} class:gata={s.gata} class:plus={s.plus}></span>
                  {/each}
                </span>
              {/if}
              <!-- PERIOADA E O BANDA, NU UN SEGMENT — si asta e toata deosebirea
                   cerută: taskurile sunt lucruri de bifat (bucati), o perioada e o
                   fasie de timp in care ESTI undeva (continua). Doua unitati
                   diferite n-au voie sa arate la fel, oricat de mica e celula.
                   Plin = implementare, contur = pregatire: aceeasi regula ca pe
                   swimlane si in Calendar, nu un al treilea cod de invatat. -->
              {#if c.impl || c.pregatire}
                <span class="mg-banda" class:pregatire={!c.impl} aria-hidden="true"></span>
              {/if}
            </button>
          {/each}
        </div>
        <!-- LEGENDA. Trei semne, si toate trei au nevoie de traducere: bara e o
             lungime (nu un numar), iar cele doua tente sunt culori de stare. -->
        <!-- LEGENDA. Patru semne, si fiecare are nevoie de traducere: trei sunt
             forme (segment / segment roșu / bandă) si unul e o tenta. Weekendul a
             plecat din ea — o zi de weekend se recunoaste din poziţia in
             saptamana, iar legenda nu e un inventar de culori, e pentru ce NU se
             deduce. -->
        <div class="mg-legenda">
          <span class="mgl"><span class="mgl-seg"></span>un task</span>
          <span class="mgl"><span class="mgl-seg rest"></span>restant</span>
          <span class="mgl"><span class="mgl-seg gata"></span>făcut</span>
          <span class="mgl"><span class="mgl-banda"></span>deplasare</span>
        </div>
      </section>

      <!-- CAPUL ZILEI ALESE. Tonul spune ce fel de zi e, cu aceeasi scara de
           severitate ca inelele si termenele din liste: restante -> danger,
           azi -> accent, altfel neutru. -->
      <div class="mg-cap-zi" class:danger={restanteZiua > 0} class:accent={restanteZiua === 0 && ziActiva === plan.today}>
        <span class="mg-cz-txt">{etichetaZiua}</span>
        <span class="mg-cz-n">{numarZiua}</span>
      </div>

      <!-- Aici stateau `.mpiste` si antetul ei comun de saptamani/zile — pista de
           perioade de pe telefon. A fost inlocuita de grila de luna de mai sus
           (decizia lui Ion, 2026-08-17): pe telefon Planificatorul se deschide cu
           intrebarea „cat am de facut si cand", nu „cand sunt pe teren".
           PERIOADELE NU S-AU PIERDUT: fiecare card isi are randul lui de perioada
           (`.mimpl`, cu interval si chevron catre Calendar), iar pe desktop
           swimlane-ul le arata la latime intreaga. -->

      <!-- TASKURILE ZILEI ALESE, GRUPATE PE PROIECTE, in cardurile existente.
           Lista arata acum O ZI, nu toata fereastra: grila de sus e cea care spune
           cat ai in fiecare zi, deci o lista care le-ar inșira pe toate ar fi a
           doua data aceeasi informatie, in forma pe care ochiul o citeste mai
           greu. Cine vrea alta zi o atinge in grila.
           `laneuriZiua` ii da doar proiectele care AU ceva in ziua aleasa, deci
           ramura „proiect gol" (`.mgol`) n-are ce sa mai acopere: un proiect fara
           taskuri in ziua asta pur si simplu nu apare. -->
      {#if laneuriZiua.length === 0}
        <p class="mg-liber">Nicio sarcină în ziua asta.</p>
      {/if}
      {#each laneuriZiua as lane, li (lane.tip + ':' + lane.id)}
        {@const per = perioadaDeAratat(lane)}
        {@const restZi = lane.tasksZi.filter(t => esteRestant(t.data_scadenta)).length}
        <section class="mgroup" style="--lane:{lane.color}; --rand:{li}">
          <header class="mg-head">
            <span class="lane-dot"></span>
            <h2>{lane.nume}</h2>
            {#if lane.tip_proiect}<span class="tip-chip" class:svc={lane.tip_proiect === 'Service'}>{lane.tip_proiect}</span>{/if}
            <!-- Doua pastile, nu un sir „5 · 2": tonul spune care e care, ca peste tot.
                 Zero nu se scrie (raportat de Ion): un „0" langa nume nu decide nimic,
                 iar langa pastila rosie de restante chiar deruteaza. -->
            <!-- Numerele sunt ale ZILEI ALESE, nu ale ferestrei: cardul arata o zi,
                 deci pastilele lui trebuie sa numere aceeasi multime pe care o vezi
                 dedesubt. Altfel un card cu doua randuri ar purta pastila „7". -->
            {#if lane.tasksZi.length}<span class="count" title="{lane.tasksZi.length} taskuri">{lane.tasksZi.length}</span>{/if}
            {#if restZi}<span class="count danger" title="{restZi} restante">{restZi}</span>{/if}
          </header>

          <!-- Pista proprie a plecat de aici (V11): era aceeasi informatie ca in
               pista comuna de sus, desenata inca o data pentru fiecare proiect —
               si a doua oara in 26px, adica prea strans ca sa se citeasca. Ce
               ramane in card e ce se face cu proiectul: perioada si taskurile.
               Randul perioadei e si tinta ei: are latimea intreaga si duce in
               Calendar, unde perioadele se editeaza. UN SINGUR RAND, nu cate unul
               per perioada — vezi `perioadaDeAratat`. -->
          {#if per}
            <button class="mimpl loc-{per.im.locatie}" class:pregatire={per.im.faza === 'pregatire'}
                    onclick={() => navigate(linkCalendar(per.im))}
                    title="{lane.impl.length > 1 ? `${lane.impl.length} perioade în fereastră — ` : ''}vezi în Calendar">
              {#if per.im.locatie === 'sediu'}<Building2 size={15} class="mimpl-ico" />{:else}<MapPin size={15} class="mimpl-ico" />{/if}
              <span class="mimpl-loc">{locLabel(per.im.locatie)}{per.im.eticheta ? ' · ' + per.im.eticheta : ''}</span>
              <!-- Interval compact, ca in desen: „17–18 aug", nu luna scrisa de
                   doua ori. O zi singura ramane o zi. -->
              <span class="mimpl-range">
                {intervalScurt(per.im.a, per.im.b)}
                {#if per.rest > 0}<span class="mimpl-plus">+{per.rest}</span>{/if}
              </span>
              <ChevronRight size={15} class="mimpl-chev" />
            </button>
          {/if}

          <!-- FARA CAPETE DE GRUPA. `grupeazaBanda` imparte fereastra in
               „Restante / Azi / Zilele următoare" — trei categorii care descriu
               CAND. Aici toate randurile sunt din aceeasi zi, deci cele trei capete
               ar fi ori toate goale in afara de unul, ori un titlu care repeta ce
               scrie deja capul zilei de deasupra grilei. Severitatea rămâne pe
               fiecare rand, in `--ring`, unde e si in celelalte trei liste. -->
            {#each lane.tasksZi as t (t.tip + ':' + t.id)}
            <!-- Acelasi rand ca pe „Astazi" SI ca in /tasks: o linie, bifa in
                 stanga, si DOUA piste — dreapta „Făcut", stanga „Planifică".
                 Aici era ultimul panou de actiuni din aplicatie (`latime: 118`,
                 doua butoane de 58px): 118px din 390 acopereau taskul pe care
                 actionai, iar celelalte trei liste trecuseră deja pe piste (vezi
                 nota lunga de la `.gl-pista-s` in global.css). Doua liste care
                 arata acelasi lucru trebuie sa se poarte la fel — altfel inveti
                 gestul de doua ori; cu patru liste il invatai de patru ori.
                 `activ: ecran.telefon`, nu `true`: era singurul `use:glisare` din
                 aplicatie care pornea si pe desktop. Cu mouse `glisare` iese
                 oricum din `onDown`, deci nu se vedea — dar pe un laptop cu ecran
                 tactil randul se lasa tras desi are butoanele la vedere. -->
            <div class="mrow" data-rand="{t.tip}:{t.id}" style="--ring: {dueRing(t.data_scadenta)}"
                 class:done={isDone(t.status)}
                 class:bifare={bifatAcum === t.tip + ':' + t.id}
                 use:glisare={{ activ: ecran.telefon, onBifa: isDone(t.status) ? null : () => onDone(t, true), onAmana: () => deschideFoaia(t, 'plan') }}
                 use:apasareLunga={{ activ: ecran.telefon, actiune: () => deschideFoaia(t, 'actiuni') }}>
              <div class="gl-pista" aria-hidden="true"><span class="gl-ico"><Check size={17} strokeWidth={3} /></span><span class="gl-et">Făcut</span></div>
              <div class="gl-pista-s" aria-hidden="true"><span class="gl-et-s">Planifică</span><span class="gl-ico-s"><CalendarDays size={17} strokeWidth={2.4} /></span></div>
              <div class="gl-fata">
                <button class="mcheck" onclick={() => onDone(t)} title="Bifează">
                  {#if isDone(t.status)}<CheckCircle2 size={18} />{:else}<span class="check-empty"></span>{/if}
                </button>
                <button class="mrow-main" onclick={(e) => openTask(t, e.currentTarget)}>
                  <!-- Contorul de pasi sta LANGA TITLU, ca in celelalte trei
                       liste — nu ca un al treilea chip in `.mrow-meta`, unde ar
                       fi purtat alta haina decat acelasi numar de pe „Astăzi".
                       Titlul spune ce si cat; chipurile de dedesubt spun cand. -->
                  <span class="mrow-titlu">
                    <span class="mrow-title">{t.titlu}</span>
                    <ContorPasi gata={t.subtask_done || 0} total={t.subtask_total || 0} />
                  </span>
                  <!-- ADAPTAT, nu copiat. Ordinea si semnele sunt cele din /tasks
                       si de pe „Astăzi" — intai CAND, apoi CAT — dar data ramane
                       ABSOLUTA („27.07"), nu relativa („acum 4 zile"): randul sta
                       lipit de o grila de zile, iar o data relativa langa o coloana
                       care arata ziua exacta te pune sa faci conversia in cap.
                       Ce se aliniaza cu restul e CULOAREA: termenul se coloreaza
                       dupa severitate, nu cu o culoare fixa, ca peste tot. -->
                  <span class="mrow-meta">
                    {#if t.data_scadenta}
                      <!-- Conditia vine din ACEEASI functie care da `--ring`, nu
                           din `esteAzi`/`esteRestant` (care se raporteaza la
                           `plan.today`, ziua serverului): altfel chipul se putea
                           colora cand inelul nu era colorat, si invers. -->
                      <!-- Pe „azi" chipul scrie CUVANTUL, nu data (desen 4c): data
                           de azi o stii; ce vrei sa vezi e ca a ajuns scadenta. -->
                      <span class="chip due" class:sev={dueRing(t.data_scadenta) !== RING_NEUTRU}>
                        <CalendarDays size={11} />{esteAzi(t.data_scadenta) ? 'azi' : formatDateShort(t.data_scadenta)}
                      </span>
                    {/if}
                    <!-- Interdictia E1 („fractia de pasi nu sta pe rand") s-a
                         ridicat pe 2026-08-15, la cererea lui Ion, si s-a ridicat
                         in toate cele patru liste deodata — vezi `.tpasi` in
                         global.css. Aici a urcat pe linia titlului, nu aici jos:
                         un chip in plus langa termen ar fi spus „cand", nu „cat". -->
                    {#if t.recurenta}<span class="chip"><Repeat size={11} /> {t.recurenta}</span>{/if}
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
        </section>
      {/each}
    </div>
  {/if}
</div>

<!-- Eticheta sta langa POINTER, pe pozitia raportata de gest. `pointer-events:
     none` in CSS, deci nu fura niciodata evenimentul de sub ea. -->
{#if dragLabel}
  <div class="drag-label" style="left:{pozLabel.x + 14}px; top:{pozLabel.y - 34}px">{dragLabel.text}</div>
{/if}

<!-- Foaia randului de pe telefon. „Deschide" duce unde ducea si atingerea randului
     (`openTask`): in /tasks sau in pagina proiectului, pe taskul lui. -->
<FoaieTask bind:open={foaieDeschisa} task={foaieTask} mod={foaieMod}
           onZi={(v) => planificaDinFoaie(foaieTask, v)}
           onMaine={() => onTomorrow(foaieTask)}
           onBifa={() => onDone(foaieTask)}
           onDeschide={() => openTask(foaieTask)}
           onSterge={() => stergeDinPlan(foaieTask)} />

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
  /* Acelasi padding ca restul rutelor (standardizarea titlurilor): h1 la
     aceeasi pozitie. 96 jos ramane — loc pentru dock peste sertar. */
  .page { padding: var(--space-lg) var(--space-lg) 96px; }
  /* `flex-start`, ca pe Calendar: cu controale de 38px alaturi, centrarea
     cobora h1 fata de rutele fara controale (standardizarea titlurilor). */
  .page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-sm); margin-bottom: var(--space-md); flex-wrap: wrap; }
  /* Subtitlul sta pe LINIA DE BAZA a titlului, nu pe mijlocul lui: e continuarea
     propozitiei „Planificator", nu o eticheta pusa alaturi. Iconita se recentreaza
     singura — baza unui svg e muchia lui de jos, deci s-ar fi infipt in text. */
  .page-title-row { display: flex; align-items: baseline; gap: var(--space-sm); color: var(--text); }
  .page-title-row :global(svg) { align-self: center; }
  .page-title-row h1 { font-size: var(--font-title); font-weight: var(--fw-semibold); font-family: var(--font-heading); letter-spacing: var(--tracking-tight); }
  .page-sub { font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-secondary); white-space: nowrap; }
  /* Cifrele subtitlului in mono (desen 4c): „14" si „8–21 aug" se compara de la
     o vizita la alta; cuvintele raman in fontul paginii. */
  .ps-n { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .controls { display: flex; align-items: center; gap: var(--space-sm); }
  /* CAPUL PLANIFICATORULUI POARTA ACEEASI HAINA DE CONTROL CA RESTUL APLICATIEI.
     Avea chenar + fond, cu hoverul pe `border-color` — a doua haina, scoasa deja
     din Calendar (M3) si din Departament (C2). Desenat (`Planificator.dc.html`,
     capul din 4a/6a): segmentul de orizont e o PASTILA pe suprafata a doua, fara
     chenar (activul ramane fill de accent, cum era), iar vecinii („Weekend",
     „Finalizate", „Export PDF") sunt 38px pe `--bg-surface` cu umbra, fara
     chenar. Treapta de text urca de la 13/500 la 15/600: sunt controale de cap
     de pagina, nu metadate. */
  .seg { display: inline-flex; background: var(--bg-elevated); border: none; border-radius: var(--radius-sm); padding: 3px; }
  /* Raza segmentului = raza capsulei minus paddingul ei (10 − 3 = 7), aceeasi
     formula ca la comutatorul de sfera din /tasks. */
  .seg-btn { height: 32px; padding: 0 11px; border-radius: calc(var(--radius-sm) - 3px); font-size: var(--font-body); font-weight: var(--fw-semibold); color: var(--text-dim); background: none; border: none; cursor: pointer; transition: color var(--dur-fast) var(--ease), background-color var(--dur-fast) var(--ease); }
  .seg-btn:hover { color: var(--text); }
  .seg-btn.active { background: var(--accent); color: var(--accent-text); }
  .toggle { display: inline-flex; align-items: center; gap: 7px; height: 38px; padding: 0 12px; font-size: var(--font-body); font-weight: var(--fw-semibold); border-radius: var(--radius-sm); background: var(--bg-surface); box-shadow: var(--shadow-sm); border: none; color: var(--text-secondary); cursor: pointer; transition: var(--transition-pressable); }
  .toggle:hover { background: var(--bg-hover); color: var(--text); }
  .toggle:active { transform: scale(var(--press-scale)); }
  /* Activul e TENTA CU CERNEALA ADANCA (regula sistemului: pe tenta se scrie
     mereu cu adancul) — nu `--accent` plin scris ca text pe fondul panoului.
     Umbra pleaca: obiectul nu mai e o suprafata care se ridica, ci o stare
     aprinsa. Model viu: `.seg-btn.active` de mai sus si `.tab.active` din
     global.css. */
  .toggle.on { background: var(--accent-subtle); color: var(--accent-on-subtle); box-shadow: none; }
  .toggle:disabled { opacity: 0.4; cursor: not-allowed; }
  /* 4px nu e o treapta din scara (8 chip · 10 control · 14 suprafata · 20 foaie).
     Cercul e rezervat bifei de task; asta e o casuta de filtru, deci ramane
     patrata si ia treapta cea mai mica. */
  /* Raza 5, din desen: la 16px un colt de 8 ar face casuta aproape rotunda. */
  .tk-box { width: 16px; height: 16px; border-radius: 5px; border: 1.5px solid var(--border-strong); display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; }
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
  /* „Restante" e un cuvant, nu o cifra — fontul paginii, la 12/600, ca orice
     eticheta majuscula. Mono era o abatere: DM Mono e doar pentru cifre. */
  .rest-head { width: var(--rest-w); flex: none; box-sizing: border-box;
    display: flex; align-items: flex-end; justify-content: center;
    padding: 0 6px 8px; border-left: 1px solid var(--border);
    background: var(--danger-subtle); color: var(--danger-deep);
    font-size: var(--font-label); font-weight: var(--fw-semibold);
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
  /* O SINGURA CONVENTIE PENTRU MUCHIA DINTRE COLOANE.
     Antetul deseneaza muchia cu `border-right` pe `.col-head` — cu `box-sizing:
     border-box`, adica pixelul `x−1`, ULTIMUL din coloana. Linia care coboara
     prin benzi sta la `left: x%`, adica pixelul `x`, PRIMUL din coloana
     urmatoare. Doua conventii pentru aceeasi muchie: imbinarea antet–corp iesea
     mereu decalata cu un pixel, iar cu procente fractionare rotunjirea o facea
     cand dubla, cand rupta — exact la granita. `margin-left: -1px` aduce linia
     din corp pe acelasi pixel ca separatorul din antet, la orice latime.
     `granite.has(i - 1)` ramane cum e: el spune CARE muchie, nu unde cade. */
  .col-line { position: absolute; top: 0; bottom: 0; width: 1px; margin-left: -1px; background: var(--border-subtle); }
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
  /* Clientul si cate taskuri are banda in fereastra. Desenat (5a): 13, `--tx2`,
     pe UN rand cu trunchiere — coloana are 240px si titlul e deasupra. Mono e doar
     cifra, fiindca doar ea se compara pe verticala cu vecinele ei; clientul e un
     cuvant, deci text. (Numarul de restante a plecat de aici in coloana lui.) */
  .lane-contor { font-size: var(--font-small); color: var(--text-secondary);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .lc-n { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
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
  /* Chipul de tip, ca in desen: 20px, 12/600, tracking usor — o eticheta, nu text. */
  .tip-chip { display: inline-flex; align-items: center; height: 20px;
    font-size: var(--font-label); font-weight: var(--fw-semibold); letter-spacing: var(--tracking-label);
    padding: 0 6px; border-radius: var(--radius-xs); background: var(--bg-elevated);
    color: var(--text-secondary); flex-shrink: 0; }

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
  .rest-gol { font-size: var(--font-small); color: var(--text-dim); }

  /* STIVA DE REPERE SE ANCOREAZA SUS, FASIA SINEI RAMANE A EI.
     Era centrata, fiindca banda era fundalul randului si stiva trebuia sa stea
     in chenarul ei. Acum jos e sina, iar inaltimea randului poate fi dictata de
     COLOANA DIN STANGA cand ea cere mai mult decat formula (nume + contor +
     chip). Centrata, surplusul acela cobora stiva cu jumatate din el, direct in
     fasia sinei — masurat, exact asa aparea o suprapunere intre eticheta unei
     perioade si titlul unui task. Ancorata sus, fasia de jos ramane a sinei
     orice s-ar intampla in stanga. */
  .lane-track { flex: 1; position: relative; min-width: 0; padding: 6px 0 20px;
    display: flex; flex-direction: column; justify-content: flex-start; }

  /* ===== SOSIREA PISTEI (tura 13e) =====
     CE ARE INCEPUT, CRESTE DIN EL. CE DOAR ACOPERA UN INTERVAL, APARE.
     Pe un rand stau trei lucruri, si pana acum toate trei apareau intre doua
     cadre. Dar nu sunt de acelasi fel, deci nu pot sosi la fel:
       · `.impl-band` — o perioada cu o zi de start REALA. Se descopera de la
         stanga la dreapta, adica dinspre ziua in care incepe: miscarea spune
         chiar lucrul pe care banda il codifica prin pozitie.
       · banda de pregatire a plecat (2026-08-15). Ea era singura de pe rand
         FARA zi de start, deci singura care doar se stingea in loc sa creasca;
         `apareIn` i-a supravietuit fiindca il foloseste `.impl-band.clipL` —
         o perioada taiata de marginea ferestrei n-are nici ea un inceput vizibil
         din care sa creasca.
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
  @keyframes apareIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes reperIn {
    from { opacity: 0; transform: scale(0.62); }
    to { opacity: 1; transform: none; }
  }
  /* Anularea la reduced-motion sta LA SFARSITUL foii, dupa `.bar` — media query-ul
     nu adauga specificitate, deci ar fi pierdut aici in fata regulii de mai jos. */

  /* PREGATIREA E O SPALATURA NEUTRA, NU O A DOUA BANDA DE ACCENT.
     Avea `accent 10% + chenar accent 26%`, adica exact intensitatea lui
     `.impl-band` (accent 10% + inel) — deci „plin = implementare, palid =
     pregatire" nu se mai citea: doua obiecte la aceeasi tarie, unul langa altul.
     Desenat (turul 4a, banda de 88px): golul de pregatire e o spalatura NEUTRA,
     fara inel; accentul ramane al implementarii, singur. Asa cele doua se
     deosebesc dintr-o privire, nu dintr-o masuratoare de procente.
     Raza urca la `--radius-sm`, ca sa se imbine fara decalaj cu `.impl-band`,
     care e pe aceeasi treapta. Animatiile raman: pregatirea NU creste din stanga
     (n-are zi de start), doar se stinge in ecran.
     Fondul e GRADIENTUL din desen, nu o spalatura plata: se stinge spre stanga
     chiar si cand ambele capete sunt fixe — „de cand se pregateste" nu se stie
     niciodata, iar desenul o spune prin insasi textura benzii. Mastile de capat
     nesigur raman peste el, pe distanta fixa. */
  /* Taskurile stau peste benzi, deci randurile lasa clickul sa treaca prin golul
     dintre bare pana la banda de dedesubt. */
  .rows { position: relative; z-index: 1; display: flex; flex-direction: column; gap: 4px; pointer-events: none; }
  .t-row { position: relative; height: var(--row-h); }
  /* Perioada de implementare (Site / Sediu EGB) — banda pe toata inaltimea randului,
     exact insetul benzii de pregatire, ca cele doua sa se imbine fara decalaj.
     ACCENTUL E AL IMPLEMENTARII, SINGUR — si de cand golul de pregatire a plecat
     (2026-08-15) e si singurul lucru desenat pe sina, deci nu mai are cu ce sa se
     compare. Inauntrul `.impl-band` faza se mai spune
     inca o data, mai fin: 10% pentru perioada inceputa, 5% + inel mai subtire
     pentru cea inca in pregatire — dar acolo obiectul are eticheta lui, deci
     nuanta e un adaos, nu singurul semnal. Locul NU se codifica cromatic (se
     scrie, cu iconita si eticheta) — aceeasi gramatica ca in Calendar si in
     Ganttul de proiect.
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
  /* SINA. Perioada e context, nu subiect: 4px la baza randului, in accent plin.
     Plina, nu tenta: pe 4px inaltime o tenta de 10% nu se mai vede — aceeasi
     regula de compensare care face ca pe pista mobila (34px) banda sa fie deja
     desenata mai tare decat pe desktop.
     `overflow: visible`: pastila iese din sina, si in sus, si la dreapta. */
  .impl-band { position: absolute; top: auto; bottom: 6px; height: 4px;
    min-width: 11px; border-radius: 2px; overflow: visible; z-index: 0;
    background: var(--accent); border: none; color: var(--accent-deep);
    cursor: pointer; pointer-events: auto; transition: var(--transition-colors);
    /* Se descopera de la stanga, dinspre ziua in care incepe — ca inainte. */
    animation: benziIn var(--dur-base) var(--ease) backwards;
    animation-delay: min(var(--rand, 0) * 40ms, 240ms); }
  /* Zona de atingere: sina are 4px, degetul si cursorul au nevoie de mai mult.
     Nu creste sina, creste doar tinta — si nu in sus peste ultimul reper. */
  .impl-band::after { content: ''; position: absolute; left: 0; right: 0; top: -6px; bottom: -6px; }
  /* FORMA spune faza: implementarea e sina plina, pregatirea e mai palida.
     O singura axa de culoare, ca peste tot. */
  .impl-band.pregatire { background: color-mix(in srgb, var(--accent) 42%, transparent); }
  /* TERMINATORUL — capatul care spune „de aici". Doar la stanga: ziua de start e
     informatia, sfarsitul se citeste din lungime. Pe `clipL` NU se deseneaza:
     acolo capatul sinei e muchia ferestrei, nu ziua de start (deplasarea e in
     curs, a inceput inainte de azi), iar un terminator ar afirma un inceput fals.
     Din acelasi motiv sosirea nu mai creste din stanga acolo. */
  .impl-band::before { content: ''; position: absolute; left: 0; top: -3px;
    width: 3px; height: 10px; border-radius: 2px; background: inherit; }
  .impl-band.clipL { border-top-left-radius: 0; border-bottom-left-radius: 0;
    animation-name: apareIn; }
  .impl-band.clipL::before { display: none; }
  .impl-band.clipR { border-top-right-radius: 0; border-bottom-right-radius: 0; }
  .impl-band:hover { background: var(--accent-deep); }
  .impl-band:hover .ib-pastila { background: var(--accent); color: var(--accent-text); }
  /* PASTILA DE LOC, la capul vizibil al sinei. Se randeaza doar cand incape
     INTREAGA pana la perioada urmatoare (vezi `pastila` in `views`), deci n-are
     nevoie de trunchiere si nu exista stare in care se taie. */
  .ib-pastila { position: absolute; left: -2px; bottom: -6px; height: 16px;
    display: inline-flex; align-items: center; gap: 3px; padding: 0 6px 0 4px;
    border-radius: var(--radius-full); background: var(--accent-subtle);
    color: var(--accent-on-subtle); font-size: var(--font-label);
    font-weight: var(--fw-semibold); line-height: 1; white-space: nowrap;
    box-shadow: 0 0 0 2px var(--bg-surface); pointer-events: none;
    transition: var(--transition-colors); }
  .impl-band.pregatire .ib-pastila { color: var(--text-secondary); }
  /* MANERELE DE INTINDERE — aceeasi gramatica ca in Calendar: doua bare subtiri,
     la hover. Pe sina se intind PESTE inaltimea ei (-5/+5), altfel un maner de
     4px n-ar avea de unde fi apucat; sina insasi ramane de 4px, doar tinta
     creste. Cat timp tragi, banda nu mai naviga la click si isi tine manerele
     aprinse. */
  .impl-band .maner { position: absolute; top: -5px; bottom: -5px; width: 9px; padding: 0;
    border: none; background: none; cursor: ew-resize; opacity: 0;
    transition: opacity var(--dur-fast) var(--ease); z-index: 2; }
  .impl-band .maner.st { left: 0; }
  .impl-band .maner.dr { right: 0; }
  .impl-band .maner::before { content: ''; position: absolute; inset: 0 -2px; }
  .impl-band .maner::after { content: ''; position: absolute; top: 3px; bottom: 3px;
    left: 50%; width: 2px; transform: translateX(-50%); border-radius: 1px;
    background: var(--accent); }
  .impl-band:hover .maner, .impl-band.se-trage .maner { opacity: 1; }
  /* OBIECTUL APUCAT SE RIDICA. Pe telefon nu exista cursor care sa confirme ca
     apasarea lunga a „prins", deci confirmarea trebuie sa fie a obiectului:
     umbra plus o crestere abia simtita. Cu `puls()` din gest, sunt doua
     semnale — unul care se vede, unul care se simte. */
  .impl-band.se-trage, .bar.se-trage {
    box-shadow: var(--shadow-md); transform: scale(1.02); z-index: 5;
  }
  /* MANERE DE DEGET, dupa ce gestul a inceput (T8, punctul 3).
     La hover raman subtiri: acolo cursorul e precis. Pe touch nu se arata
     niciodata „in repaus" — ar fi doua dungi permanente pe fiecare banda —
     ci doar cat tine tragerea, cand chiar ai ce apuca. */
  @media (hover: none) {
    .impl-band .maner { opacity: 0; }
    .impl-band.se-trage .maner { opacity: 1; width: var(--tap-min); }
    .impl-band.se-trage .maner::after { width: 3px; }
  }
  /* Sub 24px sina n-are de unde fi apucata de doua manere de 9 — la 6L o zi are
     5,7px. Intinsul ramane la 7z/14z/30z, ca si pana acum. */
  .impl-band:not(.lat) .maner { display: none; }
  /* ANIMATIA DE SOSIRE NU SE MAI STINGE CAT TIMP TRAGI — si asta o repara.
     `animation: none` parea o precautie („geometria se rescrie la fiecare pixel,
     n-o lasa sa reporneasca"), dar o animatie CSS nu reporneste de la schimbari
     de stil: reporneste cand `animation-name` se schimba. Adica exact ce facea
     regula asta in clipa in care ridicai degetul si clasa pica — masurat, banda
     sarea la opacitate 0 si `benziIn` o descoperea din nou de la stanga, 170ms.
     Ce ramane e oprirea tranzitiei de culoare, ca sa nu se aseze peste geometrie. */
  .impl-band.se-trage { transition: none; }
  .impl-band :global(.ib-ico) { flex: none; opacity: 0.85; }
  /* `.ib-out`, `.ib-txt`, `.ib-zile` si `.impl-band.lung` au plecat odata cu
     eticheta din banda: perioada nu mai scrie nimic in pista, ci in pastila de la
     capul sinei. Cu ele a plecat si bug-ul masurat la 3L/6L, unde doua `.ib-out`
     de pe acelasi rand se tipareau una peste alta — `.ib-out` iesea din banda
     fara sa verifice daca locul de afara e liber. */
  /* RANDUL PERIOADEI E NEUTRU, NU O A TREIA BANDA DE ACCENT (desen 4c).
     Purta `accent 10% + inel 32%` — exact haina benzii de implementare, repetata
     imediat sub pista care o desena deja. Doua obiecte identice cromatic, unul
     sub altul, pentru acelasi lucru. In desen randul e o SUPRAFATA A DOUA cu
     iconita, nume, data si chevron: accentul ramane sus, in pista, unde spune
     „aici e perioada pe axa timpului"; jos scrie ce e si unde duce.
     Locul se SCRIE (iconita + eticheta), nu se coloreaza — aceeasi gramatica ca
     in Calendar si in Ganttul de proiect. */
  /* FARA PULS (decizia lui Ion la verificarea finala, 2026-08-09). M7 din
     handoff-ul Planificator cerea o aprindere de 3.4s la infinit; contractul de
     miscare, mai nou, interzice pulsurile („fara glow, puls pe puncte, inele
     care respira") si a castigat arbitrajul. Ca randul duce undeva o spun
     chevronul si fondul de suprafata a doua — aceeasi afordanta ca `.mgol`. */
  .mimpl { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left;
    border: none; cursor: pointer; padding: 0 10px; border-radius: var(--radius-sm);
    background: var(--bg-elevated); margin-bottom: 6px; }
  /* Pregatirea ramane mai palida decat implementarea — doar ca acum diferenta e
     de CERNEALA, nu de procent de accent: randul e acelasi obiect, cu alt ton. */
  .mimpl.pregatire .mimpl-loc { color: var(--text-secondary); font-weight: var(--fw-medium); }
  .mimpl :global(.mimpl-ico) { flex: none; color: var(--text-secondary); }
  /* Numele ia randul, data si chevronul stau la dreapta — ca in desen. */
  .mimpl-loc { flex: 1; min-width: 0; font-size: var(--font-small); font-weight: var(--fw-semibold);
    color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  /* Chevronul spune ca randul DUCE undeva (in Calendar) — inainte nu se vedea
     din nimic ca perioada e o tinta. */
  .mimpl :global(.mimpl-chev) { flex: none; color: var(--text-dim); }
  .mimpl-range { display: inline-flex; align-items: center; gap: 6px; flex: none; font-family: var(--font-mono); font-size: var(--font-label); color: var(--text-secondary); }
  /* „+N" = restul perioadelor din fereastra, care inainte ocupau cate un rand de
     44px fiecare, inaintea primului task. Duc toate in acelasi loc — Calendar. */
  .mimpl-plus { padding: 0 5px; border-radius: var(--radius-full);
    background: var(--accent-subtle); color: var(--accent-on-subtle); }

  /* Aici stateau `.mgrup-cap` / `.grup-n` — capetele „RESTANTE / AZI / ZILELE
     URMĂTOARE" din lista mobila. Au plecat odata cu ele: lista arata acum O ZI,
     deci nu mai are ce sa imparta pe categorii de timp. Nu s-a lasat CSS-ul in
     urma: o regula fara consumator arata ca o unealta gata de folosit.
     `.grup-cap` din /tasks, de la care venea haina, e neatins. */

  /* Ziua fara nimic in ea. Nu `EmptyState`: acela e pentru o PAGINA goala, cu
     iconita si indemn; aici pagina e plina (grila e deasupra), doar celula pe care
     ai atins-o e libera — deci o propozitie, la treapta de metadata. */
  .mg-liber { padding: var(--space-md) 4px; font-size: var(--font-small); color: var(--text-dim); }
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
  /* `--dx` vine din `lib/tragereTimeline.js` si e CONTINUU: reperul urmareste
     degetul pixel cu pixel, pe compozitor, fara sa reaseze pagina.
     `touch-action: pan-y`, NU `none`: gestul incepe la apasare lunga si isi
     blocheaza singur derularea (`touchmove` non-passive din `tragere.js`), deci
     o glisare verticala pornita din greseala pe reper deruleaza normal. Regula
     veche mananca derularea fara sa ofere nimic in schimb (T8). */
  .bar { position: absolute; top: 0; bottom: 0; background: none; border: none; box-shadow: none; padding: 0;
    font-size: var(--font-small); font-weight: var(--fw-semibold);
    white-space: nowrap; cursor: pointer; text-align: left; touch-action: pan-y;
    translate: var(--dx, 0px) 0;
    pointer-events: auto; transform-origin: left center;
    animation: reperIn var(--dur-base) var(--ease) backwards;
    animation-delay: min(var(--rand, 0) * 40ms, 240ms); }
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
  /* REPERUL IN LUCRU E DECUPAT DIN PISTA, NU DOAR PLIN.
     Avea `box-shadow: none`, deci un reper plin de accent asezat peste banda de
     implementare — care e o tenta din ACELASI accent — se topea in ea: exact
     reperul care cere atentie era singurul care disparea. Desenat (5a): fill plin
     plus doua inele exterioare, unul de suprafata si unul de accent estompat, care
     il taie din orice ar fi dedesubt. Umbra e in AFARA cutiei (fara `inset`), deci
     nu concureaza cu conturul de 1.5px al reperului „de facut". */
  .bar.active .bar-box { background: var(--accent);
    box-shadow: 0 0 0 2px var(--bg-surface), 0 0 0 4px color-mix(in srgb, var(--accent) 45%, transparent); }
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
     FARA HALO DE TEXT. Avea trei straturi de `text-shadow` in culoarea suprafetei,
     ca sa se citeasca peste banda plina — un simptom tratat, nu cauza: in desen
     eticheta sta pe fundalul pistei, iar banda de pregatire de sub ea e o spalatura
     neutra, nu un bloc saturat. Cu P2 aplicat, cauza a plecat; haloul ramas doar
     ingrosa scrisul si il facea sa pluteasca. */
  .bar-txt { position: absolute; left: 100%; top: 0; bottom: 0;
    display: inline-flex; align-items: center; gap: 4px; max-width: 220px;
    padding-left: 7px; overflow: hidden; color: var(--text); pointer-events: auto;
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
    animation-delay: min(var(--rand, 0) * 40ms, 240ms); }

  /* dim, nu faint: indicatiile de gest sunt text de citit (masurat 3.18:1 la
     10.4px, sub AA) — faint e doar pentru etichete/large. */
  .hint { text-align: center; font-size: var(--font-small); color: var(--text-dim); padding: 8px; border-top: 1px solid var(--border-subtle); }

  .drag-label { position: fixed; z-index: var(--z-tooltip); pointer-events: none; background: var(--bg-overlay);
    border: 1px solid var(--border-strong); border-radius: var(--radius-sm); padding: 3px 8px;
    font-family: var(--font-mono); font-size: var(--font-small); color: var(--text); box-shadow: var(--shadow-md); white-space: nowrap; }

  /* ===== mobile grouped list ===== */
  .mlist { display: none; flex-direction: column; gap: var(--space-md); }

  /* ===== GRILA DE LUNA + DENSITATE (telefon) =====
     A luat locul blocului `.mpiste` (pista comuna de perioade) — vezi nota din
     markup. Ce era acolo: doua coloane-frate, un antet comun de saptamani peste
     zile, si cate o sina per proiect.

     PATRU SAPTAMANI × SAPTE COLOANE, celule de 52px cu gap 4 si raza 10. 52 e
     `--row-h-mobile`: aceeasi inaltime ca un rand de lista, deci grila si lista
     de dedesubt se citesc pe acelasi pas vertical. Raza 10 e treapta de „control
     si rand" — celula E un control, nu o suprafata.
     `grid-template-columns: repeat(7, 1fr)`: latimea o da ecranul, deci nu exista
     nicio valoare de latime scrisa aici care sa se rupa pe alt telefon. */
  .mgrila {
    background: var(--bg-surface);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
    padding: var(--space-12);
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
  }
  /* Capetele de zi: treapta de eticheta a sistemului (12/600/majuscule/ls .05em).
     Aceeasi grila ca celulele, deci fiecare cap sta exact peste coloana lui. */
  .mg-zile { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
  .mg-zi-cap {
    text-align: center;
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    letter-spacing: var(--tracking-label);
    text-transform: uppercase;
    color: var(--text-dim);
  }

  .mg-celule { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
  .mg-cel {
    position: relative;
    height: var(--row-h-mobile);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 5px;
    border: none;
    border-radius: var(--radius-sm);
    background: none;
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .mg-cel:active { transform: scale(var(--press-scale)); }
  /* CIFRA E MONO: cele 28 de zile stau in coloane si se citesc pe verticala —
     exact cazul pentru care DM Mono e in sistem. `tabular-nums` ca „9" si „28"
     sa nu mute bara de sub ele. */
  .mg-nr {
    font-family: var(--font-mono);
    font-size: var(--font-small);
    color: var(--text-secondary);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }
  /* SEGMENTELE: unul per task, ca sa se poata NUMARA. 7px lat × 3 inalt, 3px intre
     ele — patru incap in celula de ~48px cu aer, si la latimea asta doua segmente
     lipite se citesc ca doua, nu ca o bara. */
  .mg-seg-rand { display: flex; align-items: center; gap: 3px; height: 3px; }
  .mg-seg {
    width: 7px;
    height: 3px;
    border-radius: var(--radius-full);
    background: var(--border-strong);
  }
  /* Restantele si facutele NU sunt culori decorative, sunt aceleasi doua stari ale
     sistemului: rosu cere actiune, iar ce s-a facut se stinge (nu se coloreaza
     verde — pe randul de task verdele e rezervat confirmarii unui GEST, iar aici
     ar fi al treilea canal cromatic intr-o celula de 48px). */
  .mg-seg.rest { background: var(--danger); }
  .mg-seg.gata { background: var(--border); }
  /* PLAFONUL SE VEDE. Al patrulea segment, cand sunt mai multe de patru, se lungeste
     si se ascute la dreapta: „de aici incolo, mai mult". Fara semnul asta patru
     segmente ar insemna „exact patru", iar o zi cu nouă taskuri ar arata la fel ca
     una cu patru — adica exact minciuna pe care o repara numararea. */
  .mg-seg.plus {
    width: 12px;
    border-top-right-radius: 1px;
    border-bottom-right-radius: 1px;
  }

  /* BANDA DE PERIOADA: continua, pe toata latimea utila a celulei, lipita de baza.
     Deosebirea de segmente e de FORMA, nu de culoare — o fasie de timp vs. bucati
     de lucru. Plin = implementare, contur = pregatire (regula sistemului). */
  .mg-banda {
    position: absolute;
    left: 5px;
    right: 5px;
    bottom: 4px;
    height: 3px;
    border-radius: var(--radius-full);
    background: var(--accent);
  }
  .mg-banda.pregatire {
    background: color-mix(in srgb, var(--accent) 22%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent) 55%, transparent);
  }

  /* WEEKENDUL e suprafata 2: nu e o stare, e un fel de zi. */
  .mg-cel.we { background: var(--bg-elevated); }
  /* AZI: cifra in accent adanc si 500, ca in antetul swimlane-ului — acolo azi e
     deja „cifra accentuata cu subliniere", deci nu se inventeaza alt semn. */
  .mg-cel.azi .mg-nr { color: var(--accent-deep); font-weight: var(--fw-medium); }
  /* ZI CU RESTANTE: tenta de danger, si bara trece pe danger — restantele sunt
     singurul lucru din grila care cere actiune, deci se vad si din forma si din
     culoare. */
  .mg-cel.rest { background: var(--danger-subtle); }
  .mg-cel.rest .mg-nr { color: var(--danger-deep); }
  /* ZIUA ALEASA: fill saturat de accent cu cerneala pe el. Ultima regula, deci
     bate weekendul si restantele — ce ai atins tu e mai important decat ce e ziua
     de fel, si trebuie sa se vada dintr-o privire unde eşti in grila. */
  .mg-cel.activa { background: var(--accent); }
  .mg-cel.activa .mg-nr { color: var(--accent-text); font-weight: var(--fw-semibold); }
  /* Pe fillul de accent, TOT ce e desenat trece pe cerneala lui — inclusiv banda de
     perioada, care altfel ar fi accent peste accent, adica invizibila exact pe ziua
     la care te uiti. Segmentele isi pastreaza ierarhia prin opacitate: restant
     intreg, de facut mai palid, facut abia vizibil. */
  .mg-cel.activa .mg-seg { background: var(--accent-text); opacity: .55; }
  .mg-cel.activa .mg-seg.rest { opacity: 1; }
  .mg-cel.activa .mg-seg.gata { opacity: .3; }
  .mg-cel.activa .mg-banda { background: var(--accent-text); opacity: .9; }
  .mg-cel.activa .mg-banda.pregatire {
    background: transparent;
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent-text) 70%, transparent);
  }

  .mg-legenda {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-12);
    padding-top: 2px;
    font-size: var(--font-label);
    color: var(--text-dim);
  }
  .mgl { display: inline-flex; align-items: center; gap: 6px; }
  /* Semnele din legenda sunt ACELEASI obiecte ca in celula, la aceeasi marime — o
     legenda cu semne „aproximative" te pune sa faci potrivirea in cap. */
  .mgl-seg { width: 7px; height: 3px; border-radius: var(--radius-full); background: var(--border-strong); }
  .mgl-seg.rest { background: var(--danger); }
  .mgl-seg.gata { background: var(--border); }
  .mgl-banda { width: 16px; height: 3px; border-radius: var(--radius-full); background: var(--accent); }

  /* CAPUL ZILEI ALESE. `baseline`, ca numarul si textul sa stea pe aceeasi linie
     de scris — la fel ca in capul boardului „Astăzi" si al paginii Taskuri. */
  .mg-cap-zi {
    display: flex;
    align-items: baseline;
    gap: var(--space-sm);
    padding: var(--space-12) 2px 2px;
  }
  .mg-cz-txt {
    font-size: var(--font-h3);
    font-weight: var(--fw-semibold);
    color: var(--text-secondary);
    /* Ziua vine din `toLocaleDateString`, deci „marți" incepe cu litera mica —
       in romana ziua saptamanii chiar se scrie asa in mijlocul unei propozitii,
       dar asta e un TITLU. `capitalize` e sigur aici: prinde doar prima litera a
       fiecarui cuvant, iar „18 august" nu are ce sa strice ca cifra. */
    text-transform: capitalize;
  }
  .mg-cap-zi.danger .mg-cz-txt { color: var(--danger-deep); }
  .mg-cap-zi.accent .mg-cz-txt { color: var(--accent-deep); }
  /* Numarul e mono: e o cifra, si sta langa alte cifre de aceeasi clasa in pagina. */
  .mg-cz-n {
    font-family: var(--font-mono);
    font-size: var(--font-small);
    color: var(--text-dim);
    font-variant-numeric: tabular-nums;
  }

  .mgroup { background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); padding: var(--space-sm) var(--space-sm) var(--space-xs); }
  /* Pastila de restante din capul cardului poarta inelul de 34% din desen (M6):
     e o cifra care cere actiune, nu doar o numaratoare. Scoped aici, nu in
     global.css — restul `.count.danger` din aplicatie raman fara muchie. */
  .mgroup .mg-head :global(.count.danger) {
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--danger) 34%, transparent); }
  /* Aici stateau `.mgol*` — „cardul strans", randul unui proiect care n-avea nimic
     in fereastra. Nu mai are cine sa-l randeze: lista arata taskurile UNEI ZILE, iar
     un proiect fara nimic in ziua aleasa nu mai apare deloc (vezi `laneuriZiua`).
     Svelte NU avertizeaza pentru el — `:global(.mgol-chev)` din interior il tine
     „viu" in ochii compilatorului — deci ar fi rămas CSS mort fara nicio alarma. */
  .mg-head { display: flex; align-items: center; gap: 7px; padding: 4px 6px 8px; }
  /* --font-rand (15 fix): capul cardului e un titlu de RAND, nu corp — pe
     telefon corpul urca la 16, capul nu (mocheta A / desen 4c: nume 15/600). */
  .mg-head h2 { font-size: var(--font-rand); font-weight: var(--fw-semibold); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
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
  /* Randul de lista pe telefon: 52 inaltime, titlul 15 (regula din CLAUDE.md).
     Erau 44 si 13 — adica randul de ACTIUNE al unei bare de unelte, nu randul
     de CITIT al unei liste. */
  /* --font-rand: randul de lista ramane 15 si pe telefon (regula din sistem). */
  /* Prima linie: titlul plus contorul de pasi. `min-width: 0` pe amandoua, ca
     titlul sa fie cel care cedeaza latimea si sa se taie CU semn — `.tpasi` e
     `flex: none` (global.css). */
  .mrow-titlu { display: flex; align-items: center; gap: var(--space-sm); min-width: 0; }
  .mrow-title { font-size: var(--font-rand); line-height: var(--lh-snug); color: var(--text); font-weight: var(--fw-medium); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .mrow-meta { display: flex; flex-wrap: wrap; gap: 4px; }
  /* CHIPUL DE TERMEN E O CUTIE DE 22px CU CIFRE MONO (desen 4c).
     Avea `padding: 1px 6px` — deci inaltimea o dadea textul, si atat chipul cat si
     vecinul lui de recurenta ieseau cu 2-3px diferiti de la un rand la altul,
     langa un titlu de 15 care nu se misca. Data e o CIFRA care se compara pe
     verticala cu data randului urmator: mono, tabular, la treapta de 12. */
  .chip { height: 22px; padding: 0 7px; border-radius: var(--radius-xs);
    font-family: var(--font-mono); font-size: var(--font-label); font-weight: var(--fw-medium);
    font-variant-numeric: tabular-nums; background: var(--bg-elevated); color: var(--text-dim);
    display: inline-flex; align-items: center; gap: 4px; flex: none; white-space: nowrap; }
  .chip.due { color: var(--text-secondary); background: var(--bg-elevated); }
  /* O SINGURA GRAMATICA PENTRU „AZI". Erau doua clase („azi", „restant") cu doua
     harti de culoare proprii, pe langa inca una pe muchia randului. Acum chipul
     citeste ACELASI `--ring` ca inelul bifei de langa el, deci cele doua canale
     nu se pot desincroniza. Cerneala e varianta ADANCA a rolului din spatele inelului
     (reteta din `Badge.svelte`): pe tenta se scrie mereu cu adancul, iar aici rolul e
     dinamic — accent sau restant — deci se deriva, nu se numeste. */
  .chip.due.sev { color: color-mix(in oklab, var(--ring) 72%, var(--text)); background: color-mix(in srgb, var(--ring) 14%, transparent); }
  .mrow-actions { display: flex; align-items: center; gap: 2px; flex-shrink: 0; }
  /* Pe desktop invelisul de glisare nu exista pentru layout, iar panoul lui e
     ascuns: acolo actiunile stau la vedere in rand. */
  .gl-fata { display: contents; }
  .mcheck { display: none; }
  .mbtn { width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; background: none; border: none; }
  .mbtn:hover { background: var(--bg-hover); color: var(--text); }
  .mrow-date { width: 34px; flex-shrink: 0; }
  .mrow-date :global(.dp-trigger) { width: 34px; min-height: 34px; padding: 0; justify-content: center; background: transparent; border: none; box-shadow: none; color: var(--text-dim); }
  .mrow-date :global(.dp-trigger:hover) { background: var(--bg-hover); color: var(--text); }
  .mrow-date :global(.dp-value) { display: none; }

  /* ===== TASKUL DESCHIS · PANOU LATERAL (4e) =====
     Panoul are COLOANA lui in grila de lucru, deci pista se stramteaza cand se
     deschide. `minmax(0, 1fr)` pe prima coloana: cu `1fr` (adica `minmax(auto,
     1fr)`) pista, care are latime minima proprie (`contentMin`), ar refuza sa se
     micsoreze si ar impinge panoul in afara ecranului. */
  /* COLOANA PANOULUI EXISTA MEREU, la 0 cand e inchis (raportat de Ion: la
     inchidere „bara de jos cu taskuri fara perioade se strica si reapare").
     Mecanica bug-ului: clasa pica in clipa inchiderii, grila devenea o singura
     coloana, iar panoul — tinut in viata de tranzitia de iesire — era re-asezat
     ca AL DOILEA RAND al grilei: cadea sub grafic, peste sertar, 200ms.
     Cu doua piste mereu (0px <-> 320px, valori interpolabile), latimea se
     ANIMEAZA — graficul se strange si se destinde lin — iar panoul in iesire
     trece pe absolute, in coltul lui, fara loc in flux. */
  .lucru { position: relative; display: grid;
    grid-template-columns: minmax(0, 1fr) 0px; column-gap: 0; align-items: start;
    transition: grid-template-columns var(--dur-base) var(--ease),
                column-gap var(--dur-base) var(--ease); }
  .lucru.cu-panou { grid-template-columns: minmax(0, 1fr) 320px; column-gap: var(--space-md); }
  .lucru:not(.cu-panou) .panou { position: absolute; top: 0; right: 0; width: 320px; }
  /* PANOUL ISI TINE LATIMEA FINALA DIN PRIMUL CADRU.
     Coloana creste animat de la 0 la 320 (ca sa se stranga lin diagrama), iar
     panoul, daca si-o lua de la ea, isi RE-IMPACHETA textul la fiecare cadru:
     masurat cu `requestAnimationFrame`, inaltimea lui pornea de la 820px si
     cadea la 404 in ~85ms — adica marginea de jos matura 400px in sus. Exact
     „parca ceva vine de jos" (Ion). Latimea fixa scoate reflow-ul din animatie:
     coloana isi face loc, panoul doar apare. */
  .lucru .panou { width: 320px; }

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
  /* Aceeasi haina ca in capul paginii: suprafata + umbra, fara chenar, hoverul
     pe fond. `.prim` ramane fill de accent — el nu e o suprafata, e actiunea. */
  .pan-b { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
    min-height: 38px; padding: 0 12px; border-radius: var(--radius-sm);
    background: var(--bg-surface); border: none; box-shadow: var(--shadow-sm); color: var(--text-secondary);
    font-size: var(--font-body); font-weight: var(--fw-semibold); cursor: pointer;
    transition: var(--transition-pressable); }
  .pan-b:hover { background: var(--bg-hover); color: var(--text); }
  .pan-b:active { transform: scale(var(--press-scale)); }
  .pan-b.prim { background: var(--accent); color: var(--accent-text); }


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
  .bl-head :global(.bl-chev) { margin-left: auto; color: var(--text-dim); transition: transform var(--dur-press) var(--ease); }
  .backlog.open .bl-head :global(.bl-chev) { transform: rotate(90deg); }
  .bl-items { display: flex; flex-wrap: wrap; gap: 8px; padding: 4px 16px 16px; }
  /* Dunga era `var(--text-dim)` — o linie gri care nu codifica nimic. Se sterge
     fara inlocuitor; severitatea acestui chip o poarta chipul lui de termen. */
  .bl-chip { display: flex; align-items: center; gap: 6px; padding: 6px 8px 6px 7px; background: var(--bg-panel); border: 1px solid var(--border); border-radius: var(--radius-md); cursor: grab; max-width: 320px; }
  .bl-chip:hover { border-color: var(--border-strong); }
  .bl-chip:active { cursor: grabbing; }
  .bl-chip :global(.bl-grip) { color: var(--text-dim); flex-shrink: 0; }
  .bl-sev { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
  .bl-txt { font-size: var(--font-small); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; }
  .bl-proj { font-size: var(--font-small); color: var(--accent-on-subtle); background: var(--accent-subtle); padding: 1px 6px; border-radius: var(--radius-xs); white-space: nowrap; max-width: 120px; overflow: hidden; text-overflow: ellipsis; }
  .bl-proj.glob { color: var(--text-dim); background: var(--bg-elevated); }
  .bl-date { width: 30px; flex-shrink: 0; }
  .bl-date :global(.dp-trigger) { width: 30px; min-height: 30px; padding: 0; justify-content: center; background: transparent; border: none; box-shadow: none; color: var(--text-dim); }
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
  /* Aceeasi haina de control ca in capul paginii si in panou. */
  .btn-ghost { display: inline-flex; align-items: center; justify-content: center; height: 38px; padding: 0 16px;
    border-radius: var(--radius-sm); background: var(--bg-surface); border: none; box-shadow: var(--shadow-sm);
    color: var(--text-secondary); cursor: pointer; font-size: var(--font-body); font-weight: var(--fw-semibold);
    transition: var(--transition-pressable); }
  .btn-ghost:hover { background: var(--bg-hover); color: var(--text); }
  .btn-ghost:active { transform: scale(var(--press-scale)); }
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
    .seg { display: none; }
    .toggle { display: none; }
    .mlist { display: flex; }
    .panou { display: none; }
    .lucru, .lucru.cu-panou { display: block; }
    .page { display: flex; flex-direction: column; }
    .mlist { order: 1; }
    .backlog { order: 2; }
    .mbtn { width: var(--tap-min); height: var(--tap-min); }
  }

  @media (max-width: 768px) {
    .page { padding-left: var(--space-md); padding-right: var(--space-md); }
    .page-header { align-items: stretch; }
    .controls { flex-wrap: wrap; width: 100%; }
    /* Orizontul e alegerea principala — ia randul lui, cu treptele impartite egal. */
    /* `gap: 2px` (desen 4c): pe desktop treptele stau lipite, fiindca fillul
       activului e singurul lucru care le desparte si latimea o da textul. Aici sunt
       intinse egal pe toata latimea, deci doua trepte vecine ar fi un dreptunghi de
       340px taiat de o culoare — golul le face din nou butoane.
       Treapta ramane la `--tap-min` (deci cutia 50, nu 48 ca in desen): 44 e pragul
       de atins al sistemului, iar 2px de inaltime nu-l cumpara.
       PATRU trepte, nu cinci (desen 4c): 6L nu incape pe telefon — la 180 de zile
       coloanele oricum n-ar mai avea latime de citit pe 390px. Fillul activ ia
       raza 8 (desen), nu 7 ca pe desktop. */
    .seg { display: flex; width: 100%; gap: 2px; }
    .seg-btn { flex: 1; min-height: var(--tap-min); font-size: var(--font-rand); border-radius: var(--radius-xs); }
    .seg-btn.seg-6l { display: none; }
    /* `nowrap` + eticheta scurtata: „Export PDF" se rupea pe doua randuri si facea
       butonul cu 10px mai inalt decat vecinii lui, adica un rand strâmb. */
    .toggle { display: inline-flex; flex: 1 1 0; min-height: var(--tap-min); justify-content: center; white-space: nowrap; padding: 6px 8px; }
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
               min-height: var(--row-h-mobile); padding: 5px 8px;
               background: var(--bg-panel); position: relative; z-index: 1;
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
    .mrow:global(.gl-tras) .gl-fata { box-shadow: var(--shadow-glisare); }
    /* 52, nu 44: `--tap-min` e pragul de ATINS, iar aici bifa il asigura singura
       (`.mcheck` ramane 44). Randul de lista se citeste, deci ia `--row-h-mobile`. */
    .mrow-main { flex: 1 1 0; min-width: 0; padding: 0; min-height: var(--row-h-mobile); justify-content: center; }
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

    /* Aici stateau `.gl-actiuni` si `.glb` — panoul de doua butoane de 58px pe
       care il descoperea glisarea la stanga. A plecat odata cu `latime: 118` de
       pe rand: randul poarta acum ACELEASI doua piste ca in celelalte trei liste
       (`.gl-pista` / `.gl-pista-s`, in global.css), iar data exacta si stergerea
       trec prin foaia randului. Nu se sterg doar apelurile si se lasa stilurile:
       o regula fara consumator arata ca o unealta gata de folosit si cheama la loc
       exact ce s-a hotarat sa nu mai existe (aceeasi nota ca la pragurile
       gestului de comutare, in `lib/gesturi.js`). */
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
     ar fi fost anulat de `.impl-band` / `.bar`. */
  @media (prefers-reduced-motion: reduce) {
    .impl-band, .bar, .wk { animation: none; }
  }

  /* ===== print (browser print-to-PDF) ===== */
  .print-title { display: none; }
  @media print {
    .page { padding: 0 !important; }
    .page-header, .controls, .hint, .mlist, .backlog, .drag-label, .panou { display: none !important; }
    /* Fara panou, grila de lucru redevine o coloana — altfel PDF-ul ar pastra
       cei 320px de gol in dreapta pistei. */
    .lucru, .lucru.cu-panou { display: block !important; }
    /* Cerneala de hartie e `#1b1e23`, cea din direcție. Era `#1a1206` — maro, din
       paleta veche: singura culoare scrisa de mana ramasa pe iesirea tiparita,
       si tocmai pe titlu. Ramane scrisa literal (nu ca token) fiindca hartia e
       mereu tema deschisa, indiferent de tema din care tiparesti. */
    .print-title { display: block; font-family: var(--font-heading); font-size: var(--font-h2); font-weight: var(--fw-semibold); color: #1b1e23; margin-bottom: 8px; }
    /* Force the swimlane on: A4 portrait (~794px) is under the 820px mobile
       breakpoint, which would otherwise hide .chart and blank the page. */
    .chart { display: block !important; overflow: visible !important; border: none !important; box-shadow: none !important; background: #fff !important; }
    .chart-scroll { overflow: visible !important; }
    .inner { min-width: 0 !important; width: 100% !important; }
    .lane.print-hide { display: none !important; }
    /* Aceeasi grija ca la `.cell-in` in global.css: sosirile astea pornesc de la
       `opacity: 0`, iar la print animatia nu se joaca — fara `none` explicit,
       benzile ar lipsi din PDF si ar ramane un grafic cu randuri goale. */
    .bar, .wk, .impl-band { animation: none !important; opacity: 1 !important; }
    .bar { box-shadow: none !important; }
  }
  :global(body.plan-pagebreak) .lane { break-after: page; }
  :global(body.plan-pagebreak) .lane:last-of-type { break-after: auto; }
</style>
