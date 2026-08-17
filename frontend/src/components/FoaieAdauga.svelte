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
  import { tick } from 'svelte'
  import { Search, Mic, Plus, X, ChevronDown } from '@lucide/svelte'
  import Modal from './ui/Modal.svelte'
  import Skeleton from './ui/Skeleton.svelte'
  import Select from './ui/Select.svelte'
  import Input from './ui/Input.svelte'
  import ContorPasi from './ui/ContorPasi.svelte'
  import { loadCandidates, scheduleForToday, moveToDate, removeFromToday, loadAgendaToday } from '../stores/agenda.svelte.js'
  import { createGlobalTask, createTask } from '../stores/tasks.svelte.js'
  import { projects, loadProjects } from '../stores/projects.svelte.js'
  import { grupeazaDupaTermen, ORDINE_GRUPE, etichetaTermenScurt } from '../lib/grupare.js'
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

  // Aceeasi mecanica de deschidere ca la vechiul TaskPicker: foaia se ridica DOAR
  // cu lista in mana, altfel se dimensioneaza dupa o linie de text si SARE la
  // inaltimea reala cat e inca pe la opacitate 0,2 (masurat: 228 -> 374px).
  let deschis = $state(false)
  const PLAFON_DESCHIDERE = 250

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
      deschis = true
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
    const ceas = setTimeout(() => { deschis = true }, PLAFON_DESCHIDERE)
    return () => clearTimeout(ceas)
  })

  // FOCUSUL NU CHEAMA TASTATURA SINGUR PE TELEFON — aceeasi decizie ca la vechea
  // foaie de cautare, si din acelasi motiv masurat: foaia se aseaza in ~250ms,
  // apoi tastatura o smulge in urmatoarele 160. Doua sosiri pentru un singur gest,
  // si exact asa se citeste „parca se reincarca pagina" (Ion, 2026-08-17).
  //
  // DAR AICI E ALTFEL DECAT LA CAUTARE, si merita spus: foaia asta e in primul
  // rand pentru SCRIS (butonul din care vine se numeste „+"), deci pe DESKTOP
  // focusul cade in camp. Pe telefon randul de sus rămâne la indemana: cine vrea
  // sa scrie il atinge, si atunci saltul e raspunsul la gestul lui.
  $effect(() => { if (deschis && !esteTelefon()) tick().then(() => campEl?.focus()) })

  function esteTelefon() {
    try { return window.matchMedia('(max-width: 768px)').matches } catch { return false }
  }

  const grupe = $derived(grupeazaDupaTermen(items))

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
      if (proiectAles?.id) await createTask(proiectAles.id, comun)
      else await createGlobalTask({
        ...comun,
        categorie: categorie || 'General',
        sfera,
        ...(oraAleasa ? { ora: oraAleasa } : {}),
      }, { sfera: 'toate' })
      open = false
      onSchimbare()
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

<Modal bind:open={deschis} onclose={() => open = false} title="Adaugă task" size="md">
  <div class="fa">
    <!-- RANDUL DE SUS *ESTE* CAMPUL: 56px, lupa 17, text 16 (sub 16 Safari face
         zoom la focus), si contorul „N din M" in mono la dreapta — cifre care se
         compara, deci exact cazul pentru DM Mono. -->
    <div class="fa-cauta">
      <Search size={17} strokeWidth={1.5} />
      <input type="text" placeholder="Ce ai de făcut?" bind:value={q} bind:this={campEl}
             onkeydown={(e) => { if (e.key === 'Enter' && titluCurat.trim()) { e.preventDefault(); creeaza() } }} />
      {#if q.trim() && items.length}<span class="fa-nr">{items.length} din {total}</span>{/if}
      {#if Motor}
        <button class="fa-mic" class:asculta onclick={dicteaza}
                aria-label={asculta ? 'Oprește dictarea' : 'Dictează'}>
          <Mic size={17} strokeWidth={1.5} />
        </button>
      {/if}
    </div>

    <!-- CE A INTELES, CA CHIPURI. Ziua pe tenta de accent (cerneala `-deep`, cum
         cere regula: text pe tenta ia varianta adanca), proiectul pe suprafata 2
         cu punctul lui de culoare — deci se deosebesc dintr-o privire, fara sa
         citesti. Fiecare are `×`: ce a ghicit aplicaţia trebuie sa se poata
         refuza, altfel parserul devine o surpriza. -->
    {#if (ziAleasa && citit.etichetaZi) || oraAleasa || proiectAles}
      <div class="fa-chipuri">
        {#if ziAleasa && citit.etichetaZi}
          <span class="fa-chip zi">
            {citit.etichetaZi}
            <button onclick={() => refuzZi = true} aria-label="Scoate ziua"><X size={12} strokeWidth={2.5} /></button>
          </span>
        {/if}
        <!-- Ora, pe aceeasi tenta ca ziua: sunt acelasi fel de fapt („cand"), deci
             n-au voie sa se citeasca drept doua clase de informatie. Cifrele sunt
             mono — se compara pe verticala cu termenele din lista de dedesubt. -->
        {#if oraAleasa}
          <span class="fa-chip zi">
            <span class="fa-ora">{oraAleasa}</span>
            <button onclick={() => refuzOra = true} aria-label="Scoate ora"><X size={12} strokeWidth={2.5} /></button>
          </span>
        {/if}
        {#if proiectAles}
          <span class="fa-chip proj">
            <span class="fa-dot" style="background: {culoareProiect(proiectAles.id)}"></span>
            {proiectAles.nume}
            <button onclick={() => refuzProiect = true} aria-label="Scoate proiectul"><X size={12} strokeWidth={2.5} /></button>
          </span>
        {/if}
      </div>
    {/if}

    <div class="fa-list">
      <!-- PRIMUL RAND E CREAREA, si e primul dinadins: cel mai des chiar vrei un
           task nou. 52px (`--row-h-mobile`) — aceeasi inaltime ca randurile de
           dedesubt, ca lista sa fie o lista, nu un buton plus o lista. -->
      {#if titluCurat.trim()}
        <button class="fa-creeaza" onclick={creeaza} disabled={creating}>
          <span class="fa-plus"><Plus size={17} strokeWidth={2} /></span>
          <span class="fa-ct">Creează „{titluCurat}"</span>
          {#if ziAleasa && citit.etichetaZi}<span class="fa-cz">{citit.etichetaZi}</span>{/if}
        </button>
      {/if}

      {#if loading && items.length === 0}
        <div class="fa-schelet"><Skeleton varianta="rand" randuri={3} /></div>
      {:else if items.length > 0}
        <div class="fa-cap">Există deja</div>
        {#each ORDINE_GRUPE as gid (gid)}
          {#if grupe[gid]?.items.length}
            {#each grupe[gid].items as it, i (it.tip + ':' + it.id)}
              {#if i > 0}<span class="fa-sep"></span>{/if}
              <button class="fa-rand" style="--ring: {dueRing(it.data_scadenta)}" onclick={() => alege(it)}>
                <span class="check-empty"></span>
                <span class="fa-titlu">
                  <span class="fa-tx">{#each bucati(it.titlu, q) as b}{#if b.m}<mark>{b.text}</mark>{:else}{b.text}{/if}{/each}</span>
                  <ContorPasi gata={it.subtask_done || 0} total={it.subtask_total || 0} />
                </span>
                <span class="fa-termen">{etichetaTermenScurt(it.data_scadenta)}</span>
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
  :global(.modal:has(.fa) .modal-body) { padding: 0; }
  :global(.modal:has(.fa) .modal-title) { display: none; }
  @media (min-width: 769px) {
    :global(.modal:has(.fa) .modal-header) { display: none; }
  }

  .fa { display: flex; flex-direction: column; min-height: 0; }

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
    margin-right: calc(var(--space-20) * -1 + 4px);
    border-radius: var(--radius-sm);
    color: var(--text-dim);
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .fa-mic:hover { background: var(--bg-elevated); color: var(--text); }
  /* Cat asculta, butonul e plin: e singura stare a aplicatiei in care microfonul
     e deschis, deci trebuie sa se vada fara sa cauti. */
  .fa-mic.asculta { background: var(--accent); color: var(--accent-text); }

  .fa-chipuri {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 10px var(--space-20);
    border-bottom: 1px solid var(--border);
  }
  /* Raza 8 = treapta de chip. */
  .fa-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 26px;
    padding: 0 4px 0 9px;
    border-radius: var(--radius-xs);
    font-size: var(--font-small);
    font-weight: var(--fw-medium);
  }
  /* Text pe tenta ia varianta adanca — regula scrisa in tokens.css. */
  .fa-chip.zi { background: var(--accent-subtle); color: var(--accent-deep); }
  /* Cifrele orei sunt mono si tabulare: se compara pe verticala cu coloana de
     termene din lista, si nu au voie sa-si schimbe latimea la fiecare tasta. */
  .fa-ora { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
  .fa-chip.proj { background: var(--bg-elevated); color: var(--text-secondary); }
  .fa-dot { width: 7px; height: 7px; border-radius: var(--radius-full); flex: none; }
  .fa-chip button {
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    border-radius: var(--radius-full);
    color: inherit;
    opacity: .65;
    cursor: pointer;
  }
  .fa-chip button:hover { opacity: 1; background: color-mix(in oklab, currentColor 14%, transparent); }

  /* Si pe desktop lista are inaltime FIXA, din acelasi motiv: caseta e centrata,
     deci cand se scurteaza se muta si sus si jos — de doua ori mai mult decat pe
     telefon, unde foaia e lipita de baza si creste doar intr-o directie. */
  .fa-list { overflow-y: auto; height: 340px; padding: 6px; }

  /* CREAREA: 52 = `--row-h-mobile`, aceeasi inaltime ca randurile de dedesubt.
     Tenta de accent plus cerneala adanca — nu fill saturat: un rand de lista
     colorat plin ar striga mai tare decat titlul paginii. */
  .fa-creeaza {
    display: flex;
    align-items: center;
    gap: 11px;
    width: 100%;
    min-height: var(--row-h-mobile);
    padding: 0 12px;
    border-radius: var(--radius-sm);
    background: var(--accent-subtle);
    color: var(--accent-deep);
    font-size: var(--font-rand);
    font-weight: var(--fw-medium);
    text-align: left;
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .fa-creeaza:hover { background: color-mix(in oklab, var(--accent) 18%, var(--bg-surface)); }
  .fa-creeaza:active { transform: scale(var(--press-scale)); }
  .fa-creeaza:disabled { opacity: .6; cursor: default; }
  .fa-plus { display: grid; place-items: center; flex: none; width: 20px; height: 20px; }
  .fa-ct { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  /* Ziua citita din text, la dreapta — in coloana in care randurile de dedesubt
     isi tin termenul, deci se citeste pe verticala cu ele. */
  .fa-cz {
    flex: none;
    width: 46px;
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-label);
  }

  /* Eticheta de sectiune: 12 majuscule 600, ls .05em — clasa de eticheta a
     sistemului. NU mono: textul se poate traduce (vezi nota din <script>). */
  .fa-cap {
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    color: var(--text-secondary);
    padding: 14px 12px 4px;
  }

  /* ACELASI RAND CA IN LISTE: bifa la stanga, titlu plus contor de pasi, termen
     pironit la 46px in mono. `--ring` vine de pe element si coloreaza si inelul
     bifei si termenul — o singura sursa pentru severitate, ca peste tot. */
  .fa-rand {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    min-height: var(--row-h-mobile);
    padding: 0 12px;
    border-radius: var(--radius-sm);
    background: none;
    text-align: left;
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .fa-rand:hover { background: var(--bg-elevated); }
  .fa-rand:active { transform: scale(var(--press-scale)); }
  .fa-titlu { flex: 1; min-width: 0; display: flex; align-items: center; gap: var(--space-sm); }
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
  .fa-termen {
    flex: none;
    width: 46px;
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-label);
    color: var(--ring, var(--text-dim));
    font-variant-numeric: tabular-nums;
  }
  .fa-sep { display: block; height: 1px; background: var(--border); margin: 0 12px; }

  .fa-hint { padding: 18px 12px; font-size: var(--font-small); color: var(--text-dim); }
  .fa-schelet { padding: 8px 12px; }

  .fa-jos { border-top: 1px solid var(--border); padding: 6px var(--space-md) var(--space-12); flex: none; }
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
  .fa-extra { display: flex; flex-direction: column; gap: var(--space-12); padding-top: 4px; }

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
       vechiul plafon de 46dvh — iar fara ea foaia nu ajunge sa para un ecran plin. */
    .fa { height: 58dvh; }
    .fa-list { flex: 1; min-height: 0; }
    .fa-cauta, .fa-chipuri, .fa-jos { flex: none; }
  }
</style>
