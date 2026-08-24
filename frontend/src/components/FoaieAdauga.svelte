<script>
  // O SINGURA FOAIE DE ADAUGARE, PENTRU TOATE CELE TREI DRUMURI.
  //
  // Erau trei, si fiecare cerea altceva pentru acelasi lucru:
  //   „Astăzi"   „Adaugă task în Astăzi" — o CAUTARE prin taskuri existente, fara
  //              nicio cale de a crea unul nou de acolo (scriai un titlu care nu
  //              exista si primeai „Niciun task găsit", punct)
  //   /tasks     „Task Nou" — un FORMULAR cu patru campuri (Titlu, Categorie,
  //              Termen, Recurență) peste tastatura, fara sa-ti spuna daca taskul
  //              exista deja
  //   proiect    o linie inline cu chipuri de zi, a treia gramatica
  // Deci: pe un ecran puteai doar sa cauti, pe altul doar sa creezi, si niciunul
  // nu stia ce face celalalt — se puteau naste duplicate fara ca nimic sa spuna
  // nimic.
  //
  // Acum: UN camp. Ce scrii e in acelasi timp cautare SI titlu.
  //   · primul rand e „Creează «…»", pe tenta de accent
  //   · dedesubt, „EXISTĂ DEJA" — aceleasi randuri ca in lista, cu potrivirea
  //     ingrosata; o atingere pe unul il PLANIFICA in loc sa creeze un al doilea
  //   · ce a inteles din text (ziua, proiectul) se arata ca CHIPURI, deci nu se
  //     ghiceste in tacere
  //
  // „EXISTĂ DEJA" NU E MONO, desi handoff-ul scrie „cap mono 12". Regula
  // sistemului se verifica singura: „daca textul se poate traduce, nu e mono"
  // (tokens.css), iar DM Mono e pentru cifre care se compara pe verticala. Ce
  // ramane din intentia handoff-ului e treapta: 12, majuscule, 600, ls .05em —
  // adica exact clasa de eticheta din propria lui secțiune de tipografie.
  import { marcheazaAterizarea } from '../lib/focus.js'
  import { tick, untrack } from 'svelte'
  import { motion, motionDuration, DUR_SLOW } from '../lib/motion.svelte.js'
  import { Search, Mic, Plus, X, ChevronDown, Check } from '@lucide/svelte'
  import Modal from './ui/Modal.svelte'
  import Skeleton from './ui/Skeleton.svelte'
  import Select from './ui/Select.svelte'
  import Input from './ui/Input.svelte'
  import ContorPasi from './ui/ContorPasi.svelte'
  import { loadCandidates, scheduleForToday, moveToDate, removeFromToday } from '../stores/agenda.svelte.js'
  import { createGlobalTask, createTask } from '../stores/tasks.svelte.js'
  import { projects, loadProjects } from '../stores/projects.svelte.js'
  import { grupeazaDupaTermen, ORDINE_GRUPE, etichetaTermen } from '../lib/grupare.js'
  import { dueRing } from '../lib/formatters.js'
  import { culoareProiect } from '../lib/culori.js'
  import { parseTask } from '../lib/parserTask.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'

  let {
    open = $bindable(false),
    /** Proiectul paginii curente, cand foaia se deschide dintr-un proiect. */
    proiect = null,
    /** 'munca' | 'personal' — sfera in care cade un task global nou. */
    sfera = 'munca',
    /** Se cheama dupa orice scriere reusita, ca pagina sa-si reincarce lista. */
    onSchimbare = () => {},
    // ===== MODUL DE EDITARE =====
    //
    // Ion, 2026-08-17: „editeaza, care redeschide modalul de creare task cu textul
    // introdus curent si selectat pentru editare."
    //
    // Aceeasi foaie, nu un al doilea formular — si nu doar din economie: intrebarea
    // e identica („cum se numeste si cand?"), deci si parserul trebuie sa fie
    // identic. Asa „mâine la 8" scris la EDITARE face exact ce face la creare, in
    // loc sa rămână text in titlu.
    /** Taskul editat, sau `null` pentru creare. */
    editeaza = null,
    /** async (dateNoi) => {} — pagina isi salveaza taskul cu functia ei, cu
     *  reload-ul si undo-ul ei. Foaia nu stie pe ce ruta trăiește taskul. */
    onSalveaza = null,
  } = $props()

  let q = $state('')
  let items = $state([])
  let total = $state(0)
  let loading = $state(false)
  let searchTimer = null
  let campEl = $state(null)
  let creating = $state(false)
  let maiMulte = $state(false)
  let categorie = $state('')
  let recurenta = $state('')
  /** Chipul de zi/proiect scos de utilizator rămâne scos cat timp foaia e deschisa. */
  let refuzZi = $state(false)
  let refuzProiect = $state(false)
  let refuzOra = $state(false)

  // FOAIA SE RIDICA IMEDIAT — si asta e o schimbare de contract, nu o scurtatura.
  //
  // Pana acum aștepta lista („se ridica DOAR cu lista in mana"), fiindca altfel se
  // dimensiona dupa o linie de text si SAREA la inaltimea reala cat era inca la
  // opacitate 0,2 — masurat: 228 -> 374px. Motivul ala a DISPARUT: de cand corpul
  // are inaltime fixa (`.fa { flex-basis: 58dvh }`), nu exista salt de dimensionat,
  // fiindca nu exista dimensionare dupa conţinut.
  // Ce a rămas era doar o intarziere de pana la 250ms intre atingere si foaie, si
  // ea se vedea: Ion, 2026-08-17: „animatia de adaugare task mai fluida, acum e
  // sacadata." O foaie care porneste tarziu si peste care mai vine si tastatura nu
  // se citeste ca o miscare, se citeste ca doua care se calca.
  let deschis = $state(false)

  // NUMELE PROIECTELOR, PENTRU PARSER. Foaia si le aduce singura: altfel fiecare
  // dintre cele trei pagini care o deschid ar trebui sa tina minte sa incarce
  // lista, iar cea care uita ar avea un parser care nu recunoaste proiecte —
  // adica aceeasi foaie purtandu-se diferit in functie de unde ai deschis-o.
  // Lista poate fi filtrata de pagina Proiecte (`projects.filters`); atunci un
  // proiect ascuns de filtru nu se recunoaste din text, dar se poate scrie oricum
  // in titlu si taskul se creeaza global — nu se pierde nimic tacit.
  $effect(() => {
    if (open && !projects.incarcat) loadProjects().catch(() => {})
  })

  // CE A INTELES DIN TEXT, IN DOUA TRECERI.
  //
  // De ce doua, si nu una: ora se poate SALVA doar pe un task personal fara proiect
  // (v41 a adus `global_tasks.ora`; taskurile de proiect n-au coloana, iar pentru
  // sfera de munca Ion n-a cerut-o — „pana cand doar pentru cele personale").
  // Deci decizia „tai ora din titlu?" depinde de daca s-a recunoscut un proiect, iar
  // proiectul se afla din parsare. O singura trecere ar fi circulara: `cuOra` ->
  // `proiectAles` -> `citit` -> `cuOra`. Svelte ar semnala-o, dar mai important e ca
  // n-ar exista ordine corecta — intrebarea chiar depinde de propriul raspuns.
  //
  // Deci: prima trecere afla proiectul si NU atinge ora; a doua taie ora, dar numai
  // cand exista unde s-o punem. Doua regexuri pe un titlu, la fiecare tasta —
  // nimic, si ne scapa de o stare intermediara pe care ar trebui s-o sincronizam.
  const brut = $derived(parseTask(q, { proiecte: projects.items }))
  // Proiectul paginii curente e implicit; unul scris in text il bate, fiindca e
  // mai recent si mai explicit decat contextul.
  const proiectAles = $derived(refuzProiect ? null : (brut.proiect || proiect))
  const oraSePoate = $derived(sfera === 'personal' && !proiectAles)
  const citit = $derived(oraSePoate ? parseTask(q, { proiecte: projects.items, cuOra: true }) : brut)

  const ziAleasa = $derived(refuzZi ? null : citit.zi)
  const oraAleasa = $derived(refuzOra ? null : (oraSePoate ? citit.ora : null))
  const titluCurat = $derived(citit.titlu)

  // A DOUA LINIE A RANDULUI-EROU: „task nou · mâine · Stație Biochem" (handoff „1a").
  // O propozitie linistita in loc de un rand de cipuri — spune acelasi lucru (ce s-a
  // inteles), dar sub titlu, ca metadata, nu ca butoane. La editare nu e „task nou".
  const metaCreare = $derived([
    editeaza ? null : 'task nou',
    ziAleasa && citit.etichetaZi ? citit.etichetaZi : null,
    oraAleasa || null,
    proiectAles?.nume || null,
  ].filter(Boolean).join(' · '))

  async function runSearch() {
    loading = true
    try {
      items = await loadCandidates(q)
      if (!q) total = items.length
    } catch (e) {
      items = []
      toast(`Eroare: ${e.message}`, 'error')
    } finally {
      loading = false
    }
  }

  $effect(() => {
    if (!open) return
    const query = q
    clearTimeout(searchTimer)
    searchTimer = setTimeout(runSearch, query ? 200 : 0)
    return () => clearTimeout(searchTimer)
  })

  $effect(() => {
    if (!open) {
      deschis = false
      q = ''
      maiMulte = false
      categorie = ''
      recurenta = ''
      refuzZi = false
      refuzProiect = false
      refuzOra = false
      return
    }
    // La EDITARE campul porneste cu titlul curent — asta e tot rostul randului
    // „Editează": rescrii ce era, nu scrii de la zero.
    if (editeaza) q = editeaza.titlu || ''
    deschis = true
  })

  // TASTATURA URCA ODATA CU FOAIA, NU DUPA EA — inclusiv pe telefon.
  //
  // Regula de dinainte era „o foaie din care ALEGI nu-si cheama singura tastatura",
  // si era corecta pentru ce era foaia atunci: o CAUTARE prin taskuri existente.
  // Foaia de acum e in primul rand pentru SCRIS — vine din butonul „+" — iar Ion a
  // masurat consecinta cu degetul: „cand dau adaugare task si vreau sa tastez,
  // tastatura ridica mai sus, dar animatia nu este fluida deloc; mai bine fa direct
  // cu tastatura deschisa."
  //
  // Si e acelasi defect ca inainte, doar mutat: DOUA sosiri. Inainte veneau foaia
  // apoi tastatura chemata automat; dupa ce am scos focusul, veneau foaia, apoi
  // atingerea ta, apoi tastatura — trei. Cand tastatura urca in acelasi timp cu
  // foaia, ele se termina impreuna si se citesc ca o singura miscare.
  // Focusul se pune la primul cadru in care campul exista (`tick`), nu pe un
  // cronometru: un `setTimeout` ar nimeri mereu putin dupa, si exact decalajul ala
  // se vede ca sacadare.
  // LA EDITARE, FOCUS SI SELECTIE — INCLUSIV PE TELEFON.
  //
  // Regula „o foaie din care ALEGI nu-si cheama singura tastatura" rămâne pentru
  // creare: acolo randul de sus e o cautare, si tastatura ar fi a doua sosire peste
  // foaia care tocmai s-a asezat. La editare intrebarea e inversa — ai cerut
  // explicit sa scrii, iar Ion a cerut si textul SELECTAT („selectat pentru
  // editare"), fiindca de cele mai multe ori rescrii randul, nu adaugi la el.
  // Deci un `select()`, nu doar `focus()`.
  // FOCUSUL VINE DUPA CE FOAIA S-A ASEZAT, nu odata cu ea. Foaia e o foaie
  // normala de jos (ca modalul de detalii task); daca am focaliza campul in
  // aceeasi clipa cu deschiderea, tastatura ar urca PESTE alunecarea foii — doua
  // miscari care se calca, exact „haotic". Asa, intai aluneca foaia (o singura
  // miscare, lina), apoi — dupa ce s-a asezat — vine tastatura si o ridica lin
  // deasupra ei (a doua miscare, curata). Sub reduced-motion nu exista alunecare,
  // deci focusul e imediat.
  $effect(() => {
    if (!deschis) return
    // `untrack`: `motion.reduced` e stare reactiva, iar ca dependenta ar re-porni
    // efectul la orice comutare a setarii de sistem (vezi nota din ProjectFormModal).
    const dupaAsezare = untrack(() => (motion.reduced ? 0 : motionDuration(DUR_SLOW) + 40))
    const t = setTimeout(() => {
      campEl?.focus()
      if (editeaza) campEl?.select()
    }, dupaAsezare)
    return () => clearTimeout(t)
  })

  // `esteTelefon()` a plecat odata cu excepţia pe care o pazea: focusul se pune
  // acum pe orice latime, deci nu mai exista doua comportamente de deosebit.

  const grupe = $derived(grupeazaDupaTermen(items))

  /** UNDE traieste taskul, pentru randurile din „Există deja": proiectul, daca
   *  vine dintr-unul; altfel categoria — dar niciodata „General", implicitul care
   *  apare pe jumatate din randuri fara sa deosebeasca nimic de nimic.
   *
   *  ACEEASI REGULA SI ACELASI TEXT CA PE BOARD (`contextRand` in TodayBoard):
   *  randul de aici si randul de acolo sunt acelasi task, deci nu au voie sa
   *  raspunda diferit la „unde e?".
   *
   *  Ion, 2026-08-21: „cand adaug taskuri in pagina acasa nu stiu care task de la
   *  ce proiect e." Lista de candidati aduna taskurile din TOATE proiectele plus
   *  cele globale de munca, sortate alfabetic dupa titlu — deci doua „Verificare
   *  protecţii" de la doua lucrari diferite cadeau una langa alta ca doua randuri
   *  identice. Nu era o ambiguitate rara: fisele de punere in functiune au aceleasi
   *  capitole la fiecare statie, deci titlurile SE REPETA prin constructie. */
  function undeE(it) {
    if (it.tip === 'proiect' && it.proiect_nume) return it.proiect_nume
    if (it.categorie && it.categorie !== 'General') return it.categorie
    return ''
  }

  /** A doua linie a unui rand din „Există deja". Coloana de termen din dreapta a
   *  plecat (randurile sunt grupate pe zi acum), deci pentru grupele care se intind
   *  pe mai multe zile — „Zilele astea", „Mai târziu" — ziua se muta AICI, langa
   *  proiect: „Hala 2 · vineri". Pentru „Azi"/„Mâine"/„Restante" capul grupei spune
   *  deja ziua, deci n-o repetam. */
  function contextRand(it, gid) {
    const unde = undeE(it)
    const zi = (gid === 'saptamana' || gid === 'tarziu') ? etichetaTermen(it.data_scadenta) : ''
    if (unde && zi) return `${unde} · ${zi}`
    return unde || zi || ''
  }

  /** Titlul taiat in bucati, ca potrivirea sa se poata ingrosa fara sa se
   *  coloreze fundalul randului. Fara `q`, o singura bucata. */
  function bucati(titlu, cauta) {
    const t = String(titlu || '')
    const c = String(cauta || '').trim()
    if (!c) return [{ text: t, m: false }]
    const out = []
    const jos = t.toLowerCase()
    const cjos = c.toLowerCase()
    let i = 0
    for (;;) {
      const k = jos.indexOf(cjos, i)
      if (k === -1) { if (i < t.length) out.push({ text: t.slice(i), m: false }); break }
      if (k > i) out.push({ text: t.slice(i, k), m: false })
      out.push({ text: t.slice(k, k + c.length), m: true })
      i = k + c.length
    }
    return out
  }

  // ===== CREAREA =====
  //
  // Un task cu proiect e task DE PROIECT (`/api/proiecte/:id/tasks`), unul fara e
  // global. Decizia se ia din chipul de proiect — adica din ce VEZI, nu din unde
  // ai deschis foaia: daca ai scris alt proiect in titlu, acela cantareste.
  // LA EDITARE se SCRIE peste task, nu se creeaza al doilea. Pagina primeste doar
  // ce s-a schimbat; ea decide pe ce ruta merge (global vs proiect) si cum
  // reincarca — foaia nu stie unde trăiește taskul, si nu are de ce sa stie.
  async function salveaza() {
    const titlu = titluCurat.trim()
    if (!titlu || creating) return
    creating = true
    try {
      await onSalveaza?.({
        titlu,
        ...(ziAleasa ? { data_scadenta: ziAleasa } : {}),
        ...(oraAleasa ? { ora: oraAleasa } : {}),
      })
      open = false
      onSchimbare()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { creating = false }
  }

  async function creeaza() {
    const titlu = titluCurat.trim()
    if (!titlu || creating) return
    creating = true
    try {
      const comun = {
        titlu,
        status: 'to_do',
        data_scadenta: ziAleasa || undefined,
        recurenta: recurenta || undefined,
      }
      // `ora` merge DOAR pe ramura globala, si numai cand `oraSePoate` — coloana
      // exista pe `global_tasks`, nu pe `tasks`. Pe ramura de proiect nici nu se
      // trimite: un câmp pe care ruta il ignora arata ca o promisiune.
      let facut
      if (proiectAles?.id) facut = await createTask(proiectAles.id, comun)
      else facut = await createGlobalTask({
        ...comun,
        categorie: categorie || 'General',
        sfera,
        ...(oraAleasa ? { ora: oraAleasa } : {}),
      }, { sfera: 'toate' })
      open = false
      onSchimbare()
      // UNDE A CAZUT. Masurat: apesi „creeaza", randul apare la 1857ms, iar foaia
      // se inchide abia la 2100ms — deci intrarea lui se joaca IN SPATELE foii, si
      // cand foaia pleaca randul e deja asezat. Faci un task si nu vezi unde s-a
      // dus; intr-o lista de 133 il cauti.
      // Acelasi semn ca la aterizarea de pe Acasa (inelul in doua batai), fiindca
      // e aceeasi intrebare: „pe care dintre ele". Cheia se pune ACUM, chiar daca
      // randul inca nu s-a montat — actiunea si-o citeste la montare.
      const idNou = facut?.id || facut?.task?.id
      if (idNou) marcheazaAterizarea(proiectAles?.id ? 'task' : 'global', idNou)
      toast(ziAleasa ? `Adăugat pe ${citit.etichetaZi || ziAleasa}` : 'Adăugat', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { creating = false }
  }

  // O ATINGERE PE UN TASK EXISTENT IL PLANIFICA — nu creeaza al doilea. Ziua e
  // cea citita din text, daca s-a scris una; altfel azi, ca la vechiul picker.
  // Fara buton de confirmare: e o singura scriere si se poate da inapoi din toast.
  async function alege(it) {
    const inainte = it.data_scadenta || ''
    const zi = ziAleasa
    open = false
    try {
      if (zi) await moveToDate(it.tip, it.id, zi)
      else await scheduleForToday(it.tip, it.id)
      items = items.filter(x => !(x.tip === it.tip && x.id === it.id))
      onSchimbare()
      toastUndo(zi ? `Mutat pe ${citit.etichetaZi || zi}` : 'Adăugat în Astăzi', {
        onUndo: async () => {
          try {
            if (inainte) await moveToDate(it.tip, it.id, inainte)
            else await removeFromToday(it.tip, it.id)
            onSchimbare()
          } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
        },
      })
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  // ===== DICTAREA =====
  //
  // Scrie in ACELASI camp si trece prin acelasi parser — deci „mâine revizie
  // pompa Biochem" dictat produce exact ce produce scris. Butonul se randeaza
  // DOAR daca motorul exista: in WebView-ul Capacitor `SpeechRecognition` poate
  // lipsi, si un buton care nu face nimic e mai rau decat unul absent.
  const Motor = typeof window !== 'undefined'
    ? (window.SpeechRecognition || window.webkitSpeechRecognition)
    : null
  let asculta = $state(false)
  let recunoastere = null

  function dicteaza() {
    if (!Motor) return
    if (asculta) { try { recunoastere?.stop() } catch (_) {} return }
    try {
      recunoastere = new Motor()
      recunoastere.lang = 'ro-RO'
      recunoastere.interimResults = true
      recunoastere.continuous = false
      // Rezultatele intermediare se scriu in camp cat vorbesti: altfel stai cu
      // butonul roșu si campul gol si nu stii dacă te aude.
      recunoastere.onresult = (e) => {
        let text = ''
        for (const r of e.results) text += r[0].transcript
        q = text.trim()
      }
      recunoastere.onerror = () => { asculta = false }
      recunoastere.onend = () => { asculta = false }
      recunoastere.start()
      asculta = true
    } catch (_) { asculta = false }
  }
</script>

<!-- `md` (~520), nu `lg` (720). Redesignul „1a" (handoff 2026-08-24) scoate coloana
     de termen din randurile „există deja" (acum grupate pe zi), deci cele doua lucruri
     lungi — titlul si numele lucrarii — nu mai impart latimea cu o a treia coloana si
     incap intr-un modal calm de creare, centrat pe desktop. (Rastoarna cererea de `lg`
     din 2026-08-21, care era pentru randul cu trei coloane de atunci.) -->
<!-- Foaie NORMALA de jos, ca modalul de detalii task si ca foaia de la apasarea
     lunga — o singura alunecare; tastatura vine DUPA ce s-a asezat (efectul de focus,
     secventiat), deci nu concureaza cu deschiderea. -->
<Modal bind:open={deschis} onclose={() => open = false} title={editeaza ? 'Editează task' : 'Adaugă task'} size="md">
  <div class="fa">
    <!-- RANDUL DE SUS *ESTE* CAMPUL: 56px, lupa 17, text 16 (sub 16 Safari face
         zoom la focus), si contorul „N din M" in mono la dreapta — cifre care se
         compara, deci exact cazul pentru DM Mono. -->
    <div class="fa-cauta">
      <span class="fa-lupa"><Search size={17} strokeWidth={1.5} /></span>
      <input type="text" placeholder="Ce ai de făcut?" bind:value={q} bind:this={campEl}
             onkeydown={(e) => { if (e.key === 'Enter' && titluCurat.trim()) { e.preventDefault(); editeaza ? salveaza() : creeaza() } }} />
      {#if q.trim() && items.length}<span class="fa-nr">{items.length} din {total}</span>{/if}
      {#if Motor}
        <button class="fa-mic" class:asculta onclick={dicteaza}
                aria-label={asculta ? 'Oprește dictarea' : 'Dictează'}>
          <Mic size={17} strokeWidth={1.5} />
        </button>
      {/if}
    </div>

    <!-- CE A INTELES, CA O PROPOZITIE LINISTITA — nu un rand de cipuri (handoff „1a").
         „Se planifică mâine · ● Stație Biochem": ziua in cerneala de accent (varianta
         adanca, cum cere regula: text pe tenta/langa accent ia `-deep`), proiectul cu
         punctul lui de culoare. Fiecare are un `×` mic: ce a ghicit aplicatia trebuie
         sa se poata refuza, altfel parserul devine o surpriza. -->
    {#if (ziAleasa && citit.etichetaZi) || oraAleasa || proiectAles}
      <div class="fa-linie">
        {#if (ziAleasa && citit.etichetaZi) || oraAleasa}<span class="fa-l-lead">Se planifică</span>{/if}
        {#if ziAleasa && citit.etichetaZi}
          <span class="fa-cheie">{citit.etichetaZi}
            <button onclick={() => refuzZi = true} aria-label="Scoate ziua"><X size={11} strokeWidth={3} /></button>
          </span>
        {/if}
        <!-- Ora, pe aceeasi cerneala ca ziua: acelasi fel de fapt („cand"). Cifrele
             sunt mono — se compara pe verticala cu termenele din lista de dedesubt. -->
        {#if oraAleasa}
          <span class="fa-cheie"><span class="fa-ora">{oraAleasa}</span>
            <button onclick={() => refuzOra = true} aria-label="Scoate ora"><X size={11} strokeWidth={3} /></button>
          </span>
        {/if}
        {#if proiectAles}
          {#if (ziAleasa && citit.etichetaZi) || oraAleasa}<span class="fa-l-pct">·</span>{/if}
          <span class="fa-cheie-proj">
            <span class="fa-dot" style="background: {culoareProiect(proiectAles.id)}"></span>
            {proiectAles.nume}
            <button onclick={() => refuzProiect = true} aria-label="Scoate proiectul"><X size={11} strokeWidth={3} /></button>
          </span>
        {/if}
      </div>
    {/if}

    <div class="fa-list">
      <!-- RANDUL-EROU E PRIMUL, dinadins: cel mai des chiar vrei un task nou.
           Cerc plin de accent cu „+", titlul pe un rand, iar dedesubt propozitia
           „task nou · mâine · Stație Biochem" (handoff „1a"). `↵` la dreapta spune
           ca Enter creeaza; pe telefon dispare (nu exista Enter fizic — vezi CSS). -->
      {#if titluCurat.trim()}
        <button class="fa-creeaza" onclick={editeaza ? salveaza : creeaza} disabled={creating}>
          <span class="fa-plus">
            {#if editeaza}<Check size={17} strokeWidth={2.5} />{:else}<Plus size={17} strokeWidth={2.5} />{/if}
          </span>
          <span class="fa-ct-wrap">
            <span class="fa-ct">{editeaza ? 'Salvează' : 'Creează'} „{titluCurat}"</span>
            {#if metaCreare}<span class="fa-meta">{metaCreare}</span>{/if}
          </span>
          <span class="fa-enter" aria-hidden="true">↵</span>
        </button>
      {/if}

      {#if loading && items.length === 0}
        <div class="fa-schelet"><Skeleton varianta="rand" randuri={3} /></div>
      {:else if items.length > 0 && !editeaza}
        <div class="fa-cap">Există deja</div>
        <!-- GRUPAT PE ZI, cu cap de grup — nu o coloana de termen la dreapta (handoff
             „1a"). Capul zilei poarta ziua; randul poarta titlul si proiectul. Pentru
             grupele care se intind pe mai multe zile, `contextRand` muta ziua pe rand. -->
        {#each ORDINE_GRUPE as gid (gid)}
          {#if grupe[gid]?.items.length}
            <div class="fa-subcap" class:azi={grupe[gid].ton === 'accent'} class:rest={grupe[gid].ton === 'danger'}>{grupe[gid].titlu}</div>
            {#each grupe[gid].items as it (it.tip + ':' + it.id)}
              <button class="fa-rand" style="--ring: {dueRing(it.data_scadenta)}" onclick={() => alege(it)}>
                <span class="check-empty"></span>
                <span class="fa-titlu">
                  <span class="fa-t1">
                    <span class="fa-tx">{#each bucati(it.titlu, q) as b}{#if b.m}<mark>{b.text}</mark>{:else}{b.text}{/if}{/each}</span>
                    <ContorPasi gata={it.subtask_done || 0} total={it.subtask_total || 0} />
                  </span>
                  {#if contextRand(it, gid)}<span class="fa-unde">{contextRand(it, gid)}</span>{/if}
                </span>
              </button>
            {/each}
          {/if}
        {/each}
      {:else if !titluCurat.trim()}
        <div class="fa-hint">Scrie ce ai de făcut. Poți spune și când: „mâine", „vineri".</div>
      {/if}
    </div>

    <!-- CATEGORIA SI RECURENTA INTRA DIN FOAIE, nu stau permanent pe ecran: pe
         formularul vechi ocupau doua randuri din patru, iar Ion le foloseste rar.
         Nu se arata deloc cand taskul merge intr-un proiect — acolo categoria n-are
         inteles (proiectul E categoria). -->
    {#if !proiectAles}
      <div class="fa-jos">
        <button class="fa-mai" onclick={() => maiMulte = !maiMulte} aria-expanded={maiMulte}>
          <ChevronDown size={15} strokeWidth={2} class={maiMulte ? 'fa-chev deschis' : 'fa-chev'} />
          Categorie și recurență
        </button>
        {#if maiMulte}
          <div class="fa-extra">
            <Input label="Categorie" bind:value={categorie} placeholder="General" />
            <Select label="Recurență" size="sm" bind:value={recurenta}
                    options={[{ value: '', label: 'Fără' }, { value: 'zilnic', label: 'Zilnic' }, { value: 'saptamanal', label: 'Săptămânal' }, { value: 'lunar', label: 'Lunar' }]} />
          </div>
        {/if}
      </div>
    {/if}
  </div>
</Modal>

<style>
  /* Campul e primul rand al foii, deci corpul n-are padding — randurile se
     lipesc de muchii, ca in paleta de comenzi. Pe desktop titlul se ascunde
     (repeta ce spune butonul din care ai venit); pe telefon rămâne, fiindca
     antetul poarta gestul de tragere al foii. */
  /* Corpul e coloana flex, ca `.fa` sa se poata STRANGE: cu tastatura sus foaia
     e plafonata (`max-height` scade `--kb`) si, cu o inaltime fixa in `dvh`,
     `.fa` iesea din corp — corpul derula, lista din el derula si ea, iar randul
     „Categorie și recurență" cadea sub pliu. Masurat la 844 cu tastatura de
     312: corp 424, `.fa` 490. */
  :global(.modal:has(.fa) .modal-body) { padding: 0; display: flex; flex-direction: column; }
  /* PE TELEFON TITLUL SE ARATA — „ADAUGĂ TASK" / „EDITEAZĂ TASK", eticheta mica
     din capul foii, exact ca la editorul de note (`.modal-doc`). Fara el, cu
     `justify-content: space-between` si un singur copil, `X`-ul ramanea singur in
     coltul din STANGA-sus, cu spatiu mort deasupra campului (Ion: „x-ul asta din
     sus stanga nu-mi place"). Cu titlul la stanga, `X`-ul trece la dreapta si
     antetul redevine o bara, nu un buton ratacit.
     Pe DESKTOP tot antetul se ascunde (titlul repeta butonul din care ai venit,
     iar campul „Ce ai de făcut?" spune singur ce e). */
  @media (min-width: 769px) {
    :global(.modal:has(.fa) .modal-header) { display: none; }
  }

  /* INALTIME FIXA SI PE DESKTOP, nu doar pe telefon — vezi nota lunga de la
     `@media (max-width: 768px)` de mai jos: motivul (foaia nu se dimensioneaza
     dupa continut cat timp scrii) n-a fost niciodata unul de telefon.
     `min(680px, 70dvh)`: pe un ecran de 900 da 630px de foaie, adica ~10 randuri
     in lista, fata de 6 cat incapeau in cei 340px scrisi de mana; pe un ecran
     inalt se opreste la 680, ca foaia sa ramana o caseta, nu o pagina. Plafonul
     `85dvh` de pe `.modal` ramane paza. */
  .fa { display: flex; flex-direction: column; min-height: 0; flex: 0 1 min(680px, 70dvh); }

  .fa-cauta {
    display: flex;
    align-items: center;
    gap: 11px;
    height: 56px;
    padding: 0 var(--space-20);
    border-bottom: 1px solid var(--border);
    color: var(--text-dim);
    flex: none;
  }
  /* Lupa e in ACCENT (handoff „1a"): campul de scriere e inima foii, iar accentul
     spune „aici incepe". Singura iconita de accent din foaie. */
  .fa-lupa { display: flex; flex: none; color: var(--accent); }
  .fa-cauta input {
    flex: 1;
    min-width: 0;
    align-self: stretch;
    background: none;
    border: none;
    outline: none;
    color: var(--text);
    font-family: inherit;
    /* 16px: sub atat Safari mareste pagina la focus si foaia sare. */
    font-size: var(--font-input-mobile);
  }
  /* FARA CHENAR LA FOCUS. Ion: „este un chenar la campul «ce ai de făcut»? albastru,
     nu-mi place, nu trebuie sa fie vreun chenar."
     Venea din regula globala `input:focus { box-shadow: var(--focus-ring) }` —
     un inel de 3px in accent, potrivit pentru un camp care ARE cutie (acolo inelul
     urmareste o muchie care exista deja). Randul asta n-are cutie: e prima linie a
     foii, lipita de muchii, cu un separator dedesubt. Un inel in jurul unui rand
     fara chenar deseneaza o cutie care nu exista — de aceea se citea ca un chenar
     aparut din nimic.
     `outline: none` singur nu era de ajuns: inelul e `box-shadow`, nu `outline`.
     Nu se pierde niciun semnal de focus: cand campul e focalizat, tastatura e pe
     ecran si cursorul clipeste in el. */
  .fa-cauta input:focus { box-shadow: none; border-color: transparent; }
  .fa-cauta input::placeholder { color: var(--text-dim); }
  /* Cifre care se compara — singurul caz pentru mono pe randul asta. */
  .fa-nr {
    flex: none;
    font-family: var(--font-mono);
    font-size: var(--font-label);
    color: var(--text-dim);
    font-variant-numeric: tabular-nums;
  }
  /* 48 = `--tap-sheet`. Iese din randul de 56 doar cu 4px de fiecare parte, deci
     nu-l umfla, dar e o tinta intreaga de foaie. */
  .fa-mic {
    flex: none;
    display: grid;
    place-items: center;
    width: var(--tap-sheet);
    height: var(--tap-sheet);
    margin-right: calc(var(--space-20) * -1 + var(--space-xs));
    border-radius: var(--radius-sm);
    color: var(--text-dim);
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .fa-mic:hover { background: var(--bg-elevated); color: var(--text); }
  /* Cat asculta, butonul e plin: e singura stare a aplicatiei in care microfonul
     e deschis, deci trebuie sa se vada fara sa cauti. */
  .fa-mic.asculta { background: var(--accent); color: var(--accent-text); }

  /* CE A INTELES, CA O LINIE (nu cipuri): „Se planifică mâine · ● Biochem". */
  .fa-linie {
    display: flex;
    flex: none;
    align-items: center;
    flex-wrap: wrap;
    gap: 7px;
    padding: var(--space-10) var(--space-20);
    border-bottom: 1px solid var(--border);
    font-size: var(--font-small);
    color: var(--text-dim);
  }
  .fa-l-lead { color: var(--text-dim); }
  .fa-l-pct { color: var(--text-dim); opacity: .5; }
  /* Ziua/ora — cerneala de accent adanca (text langa accent ia `-deep`). */
  .fa-cheie {
    display: inline-flex;
    align-items: center;
    gap: var(--space-xs);
    color: var(--accent-deep);
    font-weight: var(--fw-medium);
  }
  .fa-cheie-proj {
    display: inline-flex;
    align-items: center;
    gap: var(--space-6);
    color: var(--text-secondary);
    font-weight: var(--fw-medium);
  }
  /* Cifrele orei sunt mono si tabulare: se compara pe verticala cu termenele. */
  .fa-ora { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .fa-dot { width: 7px; height: 7px; border-radius: var(--radius-full); flex: none; }
  .fa-cheie button,
  .fa-cheie-proj button {
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    margin-left: -2px;
    border-radius: var(--radius-full);
    color: inherit;
    opacity: .55;
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .fa-cheie button:hover,
  .fa-cheie-proj button:hover { opacity: 1; background: color-mix(in oklab, currentColor 14%, transparent); }

  /* Si pe desktop lista are inaltime FIXA, din acelasi motiv: caseta e centrata,
     deci cand se scurteaza se muta si sus si jos — de doua ori mai mult decat pe
     telefon, unde foaia e lipita de baza si creste doar intr-o directie. */
  /* Lista ia ce ramane, pe orice ecran: cele trei benzi fixe (cautarea, chipurile,
     subsolul) isi tin inaltimea, iar restul e lista si deruleaza inauntru. */
  .fa-list { overflow-y: auto; flex: 1; min-height: 0; padding: var(--space-6); }

  /* RANDUL-EROU (~66), cerc plin de accent cu „+", doua linii de text. Tenta de
     accent-subtle + cerneala adanca — nu fill saturat pe TOT randul: un rand de
     lista colorat plin ar striga mai tare decat titlul paginii. Raza 14 (rand/camp):
     cei 18 din macheta nu sunt pe scara sistemului. */
  .fa-creeaza {
    display: flex;
    align-items: center;
    gap: var(--space-14);
    width: 100%;
    min-height: 66px;
    padding: 0 var(--space-md);
    border-radius: var(--radius-sm);
    background: var(--accent-subtle);
    color: var(--accent-deep);
    text-align: left;
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .fa-creeaza:hover { background: color-mix(in oklab, var(--accent) 18%, var(--bg-surface)); }
  .fa-creeaza:active { transform: scale(var(--press-scale)); }
  .fa-creeaza:disabled { opacity: .6; cursor: default; }
  /* Cercul plin de accent — singurul fill saturat din foaie, ca „+" sa fie eroul
     randului. Cerneala pe fill ia `--accent-text`. */
  .fa-plus {
    display: grid;
    place-items: center;
    flex: none;
    width: var(--ctrl-sm);
    height: var(--ctrl-sm);
    border-radius: var(--radius-full);
    background: var(--accent);
    color: var(--accent-text);
  }
  .fa-ct-wrap { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
  .fa-ct {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--font-body);
    font-weight: var(--fw-semibold);
  }
  /* A doua linie: ce s-a inteles, ca metadata sub titlu. Aceeasi cerneala ca titlul,
     doar mai stinsa — pe tenta, `--accent-deep` are contrast de sus, deci .72 ramane
     lizibil (secundar). */
  .fa-meta {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--font-small);
    opacity: .72;
  }
  /* „Enter creeaza". Pe telefon dispare — nu exista Enter fizic (vezi media). */
  .fa-enter {
    flex: none;
    font-family: var(--font-mono);
    font-size: var(--font-label);
    opacity: .7;
    border: 1px solid currentColor;
    border-radius: var(--radius-celula);
    padding: 1px var(--space-6);
  }

  /* Eticheta de sectiune: 12 majuscule 600, ls .05em — clasa de eticheta a
     sistemului. NU mono: textul se poate traduce (vezi nota din <script>). */
  .fa-cap {
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    color: var(--text-secondary);
    padding: var(--space-14) var(--space-12) var(--space-xs);
  }
  /* Cap de ZI in „Există deja": aceeasi treapta de eticheta, mai stinsa decat capul
     mare. „Azi" pe cerneala de accent, restantele pe pericol, restul stins — capul
     poarta ziua, deci randul n-o mai repeta la dreapta. */
  .fa-subcap {
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    color: var(--text-dim);
    padding: var(--space-sm) var(--space-12) var(--space-2xs);
  }
  .fa-subcap.azi { color: var(--accent-deep); }
  .fa-subcap.rest { color: var(--danger-deep); }

  /* ACELASI RAND CA IN LISTE: bifa la stanga, titlu plus contor de pasi, termen
     pironit la 46px in mono. `--ring` vine de pe element si coloreaza si inelul
     bifei si termenul — o singura sursa pentru severitate, ca peste tot. */
  .fa-rand {
    display: flex;
    align-items: center;
    gap: var(--space-12);
    width: 100%;
    min-height: var(--row-h-mobile);
    padding: 0 var(--space-12);
    border-radius: var(--radius-sm);
    background: none;
    text-align: left;
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .fa-rand:hover { background: var(--bg-elevated); }
  .fa-rand:active { transform: scale(var(--press-scale)); }
  /* COLOANA, nu rand: titlul sus, „unde" dedesubt. `gap: 1px` si nu un token de
     spatiu — aceeasi treapta ca `.amain` de pe board, unde cele doua linii trebuie
     sa se citeasca drept UN bloc, nu doua randuri.
     Randul NU creste: doua linii fac ~37px, sub cei 52 (`--row-h-mobile`) pe care
     ii tine `min-height`. Deci lista are aceeasi geometrie ca inainte — conteaza,
     fiindca foaia are inaltime fixa si numarul de randuri vizibile e masurat. */
  .fa-titlu { flex: 1; min-width: 0; display: flex; flex-direction: column;
    justify-content: center; gap: 1px; }
  .fa-t1 { display: flex; align-items: center; gap: var(--space-sm);
    min-width: 0; max-width: 100%; }
  .fa-unde {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--font-small);
    color: var(--text-dim);
  }
  .fa-tx {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--font-rand);
    color: var(--text);
  }
  /* Potrivirea se ingroasa in accent ADANC. Un fundal colorat pe rand ar fi a doua
     codificare peste ceva ce textul spune deja. */
  .fa-tx mark { background: none; color: var(--accent-deep); font-weight: var(--fw-semibold); }

  .fa-hint { padding: 18px var(--space-12); font-size: var(--font-small); color: var(--text-dim); }
  .fa-schelet { padding: var(--space-sm) var(--space-12); }

  .fa-jos { border-top: 1px solid var(--border); padding: var(--space-6) var(--space-md) var(--space-12); flex: none; }
  .fa-mai {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: var(--tap-min);
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
    color: var(--text-dim);
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .fa-mai:hover { color: var(--text-secondary); }
  .fa-mai :global(.fa-chev) { transition: transform var(--dur-fast) var(--ease); }
  .fa-mai :global(.fa-chev.deschis) { transform: rotate(180deg); }
  .fa-extra { display: flex; flex-direction: column; gap: var(--space-12); padding-top: var(--space-xs); }

  @media (max-width: 768px) {
    /* ===== FOAIA NU-SI SCHIMBA INALTIMEA CAT TIMP SCRII =====
       Ion, 2026-08-17: „cand tastez ceva in taskuri modalul isi schimba dimensiunea
       la orice tastare, este aiurea (…) schimbarea se poate face exact in momentul
       cand vrei sa adaugi ceva si ratezi."
       Ultima jumatate de propozitie e problema adevarata, si nu e de confort: foaia
       creste sau scade DUPA ce degetul a plecat spre ecran, deci apesi unde era
       randul, nu unde a ajuns. O interfata care se muta singura in mijlocul unui
       gest transforma fiecare atingere in pariu.
       Se muta din trei cauze deodata, si `max-height` nu apara de niciuna: lista se
       scurteaza pe masura ce cautarea filtreaza, randul „Creează" apare la prima
       litera, iar randul de chipuri apare cand parserul recunoaste o zi. Un plafon
       lasa CONTINUTUL sa dea inaltimea cat timp e sub el — adica exact cazul.
       Deci inaltime FIXA pe corp, iar lista ia ce rămâne (`flex: 1`) si deruleaza
       inauntru. De la deschidere pana la inchidere foaia are o singura dimensiune,
       si tot ce se schimba se schimba SUB ea.
       58dvh: cu tastatura sus rămân ~5 randuri vizibile — masurat la fel ca la
       vechiul plafon de 46dvh — iar fara ea foaia nu ajunge sa para un ecran plin.
       Regula e acum a foii, nu a telefonului (vezi `.fa` mai sus): aici ramane
       doar TREAPTA, fiindca pe telefon peste foaie mai vine si tastatura. */
    /* `flex-basis`, NU `height`. `.fa` e element flex intr-o coloana
       (`.modal-body` e `display: flex; flex-direction: column`), iar cand
       `flex-basis` e altceva decat `auto` el ia locul lui `height` pe axa
       principala — deci `height: 58dvh` nu se citeste NICIODATA. Masurat:
       foaia se deschidea la 591px in loc de 489, adica se stangea cu 207px
       cand venea tastatura in loc de ~100. Exact asta se vedea ca „se rupe
       animatia". Valoarea e cea dinainte de experimentul cu pagina. */
    .fa { flex-basis: 58dvh; }
    /* Indiciul „Enter creeaza" n-are cui — tastatura de telefon n-are Enter fizic. */
    .fa-enter { display: none; }
    .fa-creeaza { min-height: 62px; }
  }
</style>
