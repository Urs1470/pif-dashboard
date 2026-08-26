<script module>
  /** URL-ul perioadelor, exportat: il cere si componenta la montare, si
   *  preincalzirea de la hover pe tabul „Perioade" din pagina de proiect. Doua
   *  sabloane pentru acelasi raspuns n-ar nimeri aceeasi intrare in memorie,
   *  deci incalzirea n-ar scoate scheletul — si nimic n-ar da eroare. */
  export const urlPerioade = (id) => `/api/proiecte/${id}/implementari`
</script>

<script>
  import { onMount } from 'svelte'
  import { fade } from 'svelte/transition'
  import { MapPin, Building2, Plus, CalendarRange, Pencil, Check } from '@lucide/svelte'
  import { motionDuration, DUR_BASE, EASE } from '../../lib/motion.svelte.js'
  import { preia, dinCache, uita } from '../../lib/cache.js'
  import { shortDate } from '../../lib/calendarDates.js'
  import Skeleton from '../ui/Skeleton.svelte'
  import ImplPeriodModal from './ImplPeriodModal.svelte'
  import { toast } from '../../stores/ui.svelte.js'

  let { projectId } = $props()

  let periods = $state([])
  let loading = $state(true)
  let eroare = $state(false)
  let open = $state(false)
  let editing = $state(null)

  // TABUL SE DESCHIDE CU CE STIE. Era ultimul schelet din taburile paginii de
  // proiect: `periods` e stare de componenta, deci fiecare intrare pe tab
  // pornea de la zero. Ion: „taburile din proiecte se incarca tot cu schelete
  // de fiecare data."
  async function load() {
    const u = urlPerioade(projectId)
    const gata = dinCache(u)
    if (gata !== undefined) { periods = gata; loading = false }
    else loading = true
    eroare = false
    try { periods = await preia(u) }
    catch (e) {
      if (gata === undefined) { periods = []; eroare = true }
      toast(`Perioade: ${e.message}`, 'error')
    }
    finally { loading = false }
  }

  /** Dupa orice scriere pe perioade: ce stia memoria e vechi, iar perioadele se
   *  vad si in Calendar. Prefixul larg le acopera pe toate. */
  function uitaPerioadele() {
    uita(`/api/proiecte/${projectId}`)
    uita('/api/calendar')
  }
  onMount(load)

  function locLabel(l) { return l === 'sediu' ? 'Sediu EGB' : 'Site' }
  function days(p) {
    if (!p.data_start || !p.data_sfarsit) return 0
    const a = new Date(p.data_start), b = new Date(p.data_sfarsit)
    return Math.round((b - a) / 86400000) + 1
  }
  function interval(p) {
    const a = p.data_start
    const b = p.data_sfarsit || a
    return a === b ? shortDate(a) : `${shortDate(a)} – ${shortDate(b)}`
  }
  function add() { editing = null; open = true }
  function edit(p) { editing = p; open = true }
</script>

<section class="ip-sec">
  <div class="ip-head">
    <div class="ip-title"><CalendarRange size={16} strokeWidth={1.5} /> <h3>Perioade de implementare</h3></div>
    <button class="ip-add" onclick={add}><Plus size={14} strokeWidth={1.5} /> Adaugă</button>
  </div>

  {#if loading && periods.length === 0}
    <Skeleton varianta="rand" randuri={2} />
  {:else if eroare}
    <p class="ip-muted ip-eroare">Nu s-au putut încărca perioadele. <button class="ip-reinc" onclick={load}>Reîncearcă</button></p>
  {:else if periods.length === 0}
    <p class="ip-muted">Nicio perioadă. Adaugă una — de acolo se nasc benzile din Calendar și Planificator.</p>
  {:else}
    <!-- LISTA N-ARE RANDURI-CARD: un separator de 1px cu marja laterala.
         Fiecare rand conturat ar fi „cadre desenate din linii peste tot", exact
         ce sistemul scoate — si ar concura cu chenarul sectiunii care le tine. -->
    <div class="ip-list">
      {#each periods as p, i (p.id)}
        {#if i > 0}<span class="ip-sep"></span>{/if}
        <button class="ip-rand" onclick={() => edit(p)} transition:fade={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
          <span class="ip-ico">
            {#if p.locatie === 'sediu'}<Building2 size={15} strokeWidth={1.5} />{:else}<MapPin size={15} strokeWidth={1.5} />{/if}
          </span>
          <span class="ip-ce">
            <span class="ip-lucrare">{p.eticheta || 'Perioadă'}</span>
            <!-- Locul se SCRIE. Nu mai e codificat cromatic nicaieri: aceeasi
                 informatie, dar citibila fara sa fi invatat un cod de culoare. -->
            <span class="ip-unde">{locLabel(p.locatie)}{p.faza === 'pregatire' ? ' · pregătire' : ''}</span>
          </span>
          <!-- Doar semnul, nu si comutatorul: bifa se pune si se scoate din
               Calendar, pe ziua respectiva, unde te si intreaba. Aici ar fi un al
               doilea loc din care se schimba acelasi lucru. -->
          {#if p.confirmata}<span class="ip-fac"><Check size={12} strokeWidth={2} /> Făcut</span>{/if}
          <span class="ip-cand">
            <span class="ip-interval">{interval(p)}</span>
            {#if days(p)}<span class="ip-zile">{days(p)} {days(p) === 1 ? 'zi' : 'zile'}</span>{/if}
          </span>
          <Pencil size={13} strokeWidth={1.5} class="ip-edit" />
        </button>
      {/each}
    </div>
  {/if}
</section>

<ImplPeriodModal bind:open {projectId} period={editing} onsaved={() => { uitaPerioadele(); load() }} />

<style>
  .ip-sec { background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); padding: var(--card-pad, var(--space-md)); }
  .ip-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-sm); }
  .ip-title { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); }
  .ip-title h3 { font-size: var(--font-h3); font-weight: var(--fw-semibold); }
  .ip-add {
    display: inline-flex; align-items: center; gap: 5px;
    height: var(--ctrl-md); padding: 0 var(--space-12);
    border-radius: var(--radius-sm);
    background: var(--accent); color: var(--accent-text);
    font-size: var(--font-control); font-weight: var(--fw-semibold);
    cursor: pointer; transition: var(--transition-pressable);
  }
  .ip-add:hover { background: var(--accent-deep); }
  .ip-add:active { transform: scale(var(--press-scale)); }
  .ip-muted { color: var(--text-dim); font-size: var(--font-small); padding: var(--space-6) var(--space-2xs); text-wrap: pretty; }
  .ip-eroare { color: var(--danger); }
  .ip-reinc { color: var(--accent); font-size: var(--font-small); font-weight: var(--fw-semibold); cursor: pointer; background: none; border: none; padding: 0; text-decoration: underline; }

  .ip-list { display: flex; flex-direction: column; }
  .ip-sep { height: 1px; background: var(--border); margin: 0 var(--space-10); }

  .ip-rand {
    display: flex; align-items: center; gap: var(--space-12);
    min-height: var(--ctrl-lg); padding: 0 var(--space-10);
    border-radius: var(--radius-sm);
    color: var(--text); cursor: pointer; text-align: left;
    transition: var(--transition-colors);
  }
  .ip-rand:hover { background: var(--bg-hover); }

  .ip-ico { flex: none; display: grid; place-items: center; color: var(--text-dim); }
  .ip-ce { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .ip-lucrare {
    font-size: var(--font-body); font-weight: var(--fw-medium); color: var(--text);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .ip-unde { font-size: var(--font-small); color: var(--text-dim); }

  /* Cifrele se compara pe verticala -> mono, si tinute intr-o coloana la dreapta. */
  .ip-cand { flex: none; display: flex; flex-direction: column; align-items: flex-end; }
  .ip-interval { font-family: var(--font-mono); font-size: var(--font-small); color: var(--text-secondary); white-space: nowrap; }
  .ip-zile { font-size: var(--font-small); color: var(--text-dim); }

  /* Acelasi semn ca in panoul zilei din Calendar: verde conturat, nu plin. */
  .ip-fac {
    flex: none; display: inline-flex; align-items: center; gap: 3px;
    font-size: var(--font-small); color: var(--success-deep);
    padding: 1px var(--space-sm); border-radius: var(--radius-full);
    background: var(--success-subtle);
  }

  .ip-rand :global(.ip-edit) { flex: none; color: transparent; transition: var(--transition-colors); }
  .ip-rand:hover :global(.ip-edit) { color: var(--text-dim); }

  @media (max-width: 768px) {
    .ip-add { min-height: var(--tap-min); padding: 0 var(--space-md); }
    /* Randul de lista pe telefon: 52px. Locatia si intervalul incap unul sub
       altul in cele doua coloane, deci nu se mai rupe pe doua randuri. */
    .ip-rand { min-height: var(--row-h-mobile); }
    /* Creionul e afordanta de hover; pe deget nu exista hover, iar randul intreg
       e deja butonul care deschide editarea. */
    .ip-rand :global(.ip-edit) { display: none; }
  }
</style>
