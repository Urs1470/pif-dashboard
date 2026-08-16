<script>
  import { tick } from 'svelte'
  import { Search } from '@lucide/svelte'
  import Modal from './ui/Modal.svelte'
  import Skeleton from './ui/Skeleton.svelte'
  import { loadCandidates, scheduleForToday, moveToDate, removeFromToday } from '../stores/agenda.svelte.js'
  import { grupeazaDupaTermen, ORDINE_GRUPE, etichetaTermenScurt } from '../lib/grupare.js'
  import { dueRing } from '../lib/formatters.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'

  let { open = $bindable(false) } = $props()

  let q = $state('')
  let items = $state([])
  let total = $state(0)
  let loading = $state(false)
  let searchTimer = null
  let campEl = $state(null)

  // CASETA SE DESCHIDE CU DATELE IN MANA.
  //
  // Masurat: se deschidea la 228px si SAREA la 374 dupa 16ms, cat era inca la
  // opacitate 0,19. Cauza: `open` randa imediat, cu `items` gol, deci caseta se
  // dimensiona dupa o singura linie de text („Niciun task disponibil"), iar lista
  // venea dupa. Scalarea de intrare (0,96 -> 1) misca vreo 15px; saltul era de
  // zece ori mai mare si se juca peste ea. Ce vedeai nu era un modal care
  // soseste, era unul care se corecteaza — si sarea si pe verticala, fiindca e
  // centrat (top 361 -> 288).
  //
  // Aceeasi regula ca la `desfacere` din motion.svelte.js, unde e scrisa deja:
  // un panou se deschide numai cu continutul masurabil, altfel tranzitia
  // animeaza spre o tinta care se schimba sub ea.
  //
  // `deschis` e ce vede <Modal>; `open` ramane intentia parintelui. Inchiderea
  // pornita de utilizator se intoarce prin `onclose`, singurul drum pe care
  // Modal il semnaleaza in afara.
  let deschis = $state(false)

  // Plafon, ca butonul sa nu para stricat daca API-ul intarzie: peste atat
  // deschidem oricum, cu schelet in loc de lista. Scheletul tine locul listei,
  // deci umplerea de dupa e o inlocuire, nu un salt. Sub plafon (cazul normal)
  // nu se vede niciodata.
  const PLAFON_DESCHIDERE = 250

  async function runSearch() {
    loading = true
    try {
      items = await loadCandidates(q)
      // Totalul e cel al listei NEFILTRATE — „3 din 24" spune cat ai ingustat.
      // Se retine de la incarcarea fara cautare, nu se cere separat.
      if (!q) total = items.length
    } catch (e) {
      items = []
      toast(`Eroare: ${e.message}`, 'error')
    } finally {
      loading = false
      deschis = true
    }
  }

  // Load on open and on (debounced) query change. The modal stays mounted, so
  // this effect re-runs whenever `open` or `q` changes.
  $effect(() => {
    if (!open) return
    const query = q
    clearTimeout(searchTimer)
    searchTimer = setTimeout(runSearch, query ? 200 : 0)
    return () => clearTimeout(searchTimer)
  })

  // Citeste DOAR `open`, ca sa nu se rearmeze la fiecare tasta.
  $effect(() => {
    if (!open) { deschis = false; q = ''; return }
    const ceas = setTimeout(() => { deschis = true }, PLAFON_DESCHIDERE)
    return () => clearTimeout(ceas)
  })

  // RANDUL DE SUS E CAMPUL, deci el ia focusul: ai deschis o cautare, nu o lista.
  $effect(() => { if (deschis) tick().then(() => campEl?.focus()) })

  // ACELEASI GRUPE CA IN PAGINA TASKURI, in aceeasi ordine. Erau „Taskuri
  // globale" + cate una per proiect — o a doua taxonomie, care raspundea la
  // „de unde vine taskul" cand intrebarea de aici e „cand il fac".
  // (Candidatii sunt doar cei fara termen sau cu termen in VIITOR — vezi
  // `/api/agenda/candidates` — deci „Restante" si „Azi" nu pot aparea aici.)
  const grupe = $derived(grupeazaDupaTermen(items))

  /** Titlul taiat in bucati, ca potrivirea sa poata fi ingrosata fara sa se
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

  // O ATINGERE ADAUGA SI INCHIDE. Fara buton de confirmare: actiunea e o singura
  // scriere si se poate da inapoi din toast, deci un pas in plus n-ar apara
  // nimic — ar cere doar inca o atingere de fiecare data.
  //
  // „Inapoi" NU inseamna „scoate data": taskul putea avea deja un termen in
  // viitor, iar adaugarea pe azi l-a suprascris. Anularea il pune la loc pe cel
  // vechi; abia cand n-a avut niciunul, il scoate.
  async function pick(it) {
    const inainte = it.data_scadenta || ''
    open = false
    try {
      await scheduleForToday(it.tip, it.id)
      items = items.filter(x => !(x.tip === it.tip && x.id === it.id))
      toastUndo('Adăugat în Astăzi', {
        onUndo: async () => {
          try {
            if (inainte) await moveToDate(it.tip, it.id, inainte)
            else await removeFromToday(it.tip, it.id)
          } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
        },
      })
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }
</script>

<Modal bind:open={deschis} onclose={() => open = false} title="Adaugă task în Astăzi" size="md">
  <div class="pk">
    <!-- RANDUL DE SUS *ESTE* CAMPUL DE CAUTARE, ca in paleta de comenzi. Era o
         pastila cu chenar asezata INAUNTRUL panoului: un chenar in chenar nu
         adauga niciun inteles, doar inca o muchie de urmarit. -->
    <div class="pk-cauta">
      <Search size={17} strokeWidth={1.5} />
      <input type="text" placeholder="Caută în taskuri…" bind:value={q} bind:this={campEl} />
      {#if q.trim()}<span class="pk-nr">{items.length} din {total}</span>{/if}
    </div>

    <!-- Schelet DOAR la prima incarcare (`items` inca gol) — regula din sistemul
         de design. Cand tastezi o cautare peste o lista deja adusa, randurile
         vechi RAMAN pe ecran cat vin cele noi: altfel caseta s-ar strange la
         inaltimea scheletului si s-ar umfla inapoi la fiecare tasta. -->
    {#if loading && items.length === 0}
      <div class="pk-schelet"><Skeleton varianta="rand" randuri={4} /></div>
    {:else if items.length === 0}
      <div class="pk-hint">{q ? 'Niciun task găsit.' : 'Niciun task disponibil de adăugat.'}</div>
    {:else}
      <div class="pk-list">
        {#each ORDINE_GRUPE as gid (gid)}
          {#if grupe[gid]?.items.length}
            <div class="pk-cap">{grupe[gid].titlu}</div>
            {#each grupe[gid].items as it, i (it.tip + ':' + it.id)}
              {#if i > 0}<span class="pk-sep"></span>{/if}
              <button class="pk-rand" style="--ring: {dueRing(it.data_scadenta)}" onclick={() => pick(it)}>
                <span class="check-empty"></span>
                <span class="pk-titlu">
                  <!-- Potrivirea se ingroasa in accent ADANC. Un fundal colorat pe
                       rand ar fi a doua codificare peste ceva ce textul spune deja,
                       si ar concura cu tenta de selectie. -->
                  {#each bucati(it.titlu, q) as b}{#if b.m}<mark>{b.text}</mark>{:else}{b.text}{/if}{/each}
                </span>
                <span class="pk-termen">{etichetaTermenScurt(it.data_scadenta)}</span>
              </button>
            {/each}
          {/if}
        {/each}
      </div>
    {/if}
  </div>
</Modal>

<style>
  /* Campul e primul rand al PANOULUI, deci corpul modalului nu mai are padding —
     randul se lipeste de muchii, ca in paleta. Antetul lui Modal se ascunde pe
     desktop (titlul lui repeta ce spune butonul din care ai venit); pe telefon
     ramane, fiindca el poarta gestul de tragere al foii. */
  :global(.modal:has(.pk) .modal-body) { padding: 0; }
  :global(.modal:has(.pk) .modal-title) { display: none; }
  @media (min-width: 769px) {
    :global(.modal:has(.pk) .modal-header) { display: none; }
  }

  .pk { display: flex; flex-direction: column; min-height: 0; }

  .pk-cauta {
    display: flex;
    align-items: center;
    gap: 11px;
    height: 56px;
    padding: 0 var(--space-20);
    border-bottom: 1px solid var(--border);
    color: var(--text-dim);
    flex: none;
  }
  .pk-cauta input {
    flex: 1;
    min-width: 0;
    align-self: stretch;
    background: transparent;
    border: none;
    outline: none;
    box-shadow: none;
    color: var(--text);
    font-family: inherit;
    font-size: var(--font-body);
  }
  .pk-cauta input::placeholder { color: var(--text-dim); }
  .pk-nr { flex: none; font-family: var(--font-mono); font-size: var(--font-label); color: var(--text-dim); }

  .pk-hint { font-size: var(--font-small); color: var(--text-dim); padding: var(--space-lg); text-align: center; }
  .pk-schelet { padding: 10px 8px 12px; }

  .pk-list {
    display: flex;
    flex-direction: column;
    padding: 10px 8px 12px;
    max-height: 52dvh;
    overflow-y: auto;
    scrollbar-width: thin;
  }
  /* Capul de grupa, ca in pagina Taskuri: mono 12 majuscule. */
  .pk-cap {
    padding: 8px 10px 6px;
    font-family: var(--font-mono);
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    color: var(--text-dim);
  }
  .pk-cap:not(:first-child) { padding-top: 14px; }
  .pk-sep { height: 1px; background: var(--border); margin: 0 12px; }

  /* RANDUL DE TASK, ACELASI OBIECT CA IN CELELALTE TREI LISTE: 46px, gap 12,
     cerc, titlu care cedeaza latimea, termen pironit intr-o coloana de 46px cu
     valoare pe FIECARE rand. Daca se schimba forma, se schimba in toate patru —
     sursa e `Tasks.svelte`. */
  .pk-rand {
    display: flex;
    align-items: center;
    gap: var(--space-12);
    min-height: 46px;
    padding: 0 12px;
    border-radius: var(--radius-sm);
    text-align: left;
    cursor: pointer;
    transition: background-color var(--dur-fast) var(--ease);
  }
  .pk-rand:hover { background: var(--bg-hover); }
  .pk-titlu {
    flex: 1;
    min-width: 0;
    font-size: var(--font-body);
    font-weight: var(--fw-medium);
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .pk-titlu mark { background: none; color: var(--accent-deep); font-weight: var(--fw-semibold); }
  .pk-termen {
    flex: none;
    width: 46px;
    text-align: right;
    font-family: var(--font-mono);
    font-size: var(--font-small);
    color: var(--text-dim);
  }

  @media (max-width: 768px) {
    .pk-rand { min-height: var(--row-h-mobile); }
    .pk-list {
      max-height: 46dvh;
      overscroll-behavior: contain;
      /* Corpul modalului si-a pierdut padding-ul, deci insetul de jos il poarta
         lista: ultimul rand n-are voie sa cada sub bara de gesturi. */
      padding-bottom: calc(12px + var(--safe-bottom));
    }
  }
</style>
