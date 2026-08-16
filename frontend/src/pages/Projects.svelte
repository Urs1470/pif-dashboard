<script module>
  import { urlProiecte as _url } from '../stores/projects.svelte.js'
  import { preia as _preia } from '../lib/cache.js'

  /** Chemata de router la hover pe tabul din Doc, INAINTE de schimbarea rutei.
   *  Fara ea, hoverul aducea doar chunkul paginii, iar cererea de date pornea
   *  abia la montare — deci prima intrare pe tab in fiecare sesiune trecea
   *  printr-un schelet, oricat de repede venea codul.
   *  URL-ul vine din store, unde il construieste si `loadProjects`: doua sabloane
   *  ale aceluiasi raspuns n-ar mai nimeri aceeasi intrare in cache, si atunci
   *  preincarcarea ar face o cerere in plus fara sa scoata scheletul. */
  export function pregateste() {
    return _preia(_url(), { proaspat: 5000 })
  }
</script>

<script>
  import { onMount } from 'svelte'
  import { fly, slide } from 'svelte/transition'
  import { flip } from 'svelte/animate'
  import { FolderKanban, Plus, ChevronDown, Archive, ArrowUpDown, Zap, Wrench, ArrowRightLeft } from '@lucide/svelte'
  import { projects, loadProjects, updateProject } from '../stores/projects.svelte.js'
  import { PROJECT_STATUS_LABELS, STATUS_COLORS, formatDate } from '../lib/formatters.js'
  import { navigate, preincarca } from '../lib/router.svelte.js'
  import { motionDuration, DUR_FAST, DUR_BASE, EASE, sosire } from '../lib/motion.svelte.js'
  import { ecran } from '../lib/ecran.svelte.js'
  import { toast, toastUndo } from '../stores/ui.svelte.js'
  import Badge from '../components/ui/Badge.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import EmptyState from '../components/ui/EmptyState.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  import ProjectFormModal from '../components/projects/ProjectFormModal.svelte'
  import Modal from '../components/ui/Modal.svelte'

  // CHIPURILE DE FILTRU AU PLECAT. Grila separa deja finalizatele in „Arhivă"
  // pliabila; „Finalizat" ca chip arata exact acel continut, dar in grila, iar
  // „Toate" le arata pe amandoua. Acelasi continut, trei drumuri, trei asezari —
  // aceeasi decizie ca la „Active" din /tasks, care era un filtru mereu pornit.
  // Ce ramane in bara: cautarea, sortarea si arhiva.

  const sortOptions = [
    { value: 'nume', label: 'Nume' },
    { value: 'client', label: 'Client' },
    { value: 'tip', label: 'Tip' },
    { value: 'status', label: 'Status' },
    { value: 'urmatoarea', label: 'Următoarea ieșire' },
  ]

  function daysUntil(zi) {
    if (!zi) return null
    const d = new Date(zi)
    if (isNaN(d)) return null
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    d.setHours(0, 0, 0, 0)
    return Math.round((d - today) / 86400000)
  }

  // Deadline-ul a plecat in v30 (nu se lua nimeni dupa el). Ce conteaza aici e
  // urmatoarea perioada: cand iesi efectiv pe teren sau te pregatesti.
  //
  // RANDUL DE JOS, DESFACUT IN TREI. Era un singur sir la 10.4px monospace —
  // „pregătire · 12.08.2026 — 5 zile" — adica faza, data plina si o socoteala
  // relativa, toate la cea mai mica treapta din scara; iar la ≤2 zile se inrosea
  // TOT sirul, inclusiv faza, care nu e urgenta. Acum: faza e eticheta micro,
  // socoteala urca la --font-small si poarta SINGURA culoarea, data plina trece
  // in `title` — o verifici cand o cauti.
  const FAZA_SCURT = { pregatire: 'Pregătire', implementare: 'Implementare' }
  function urmatoarea(p) {
    const zi = p.urmatoarea
    if (!zi) return { faza: '', cand: 'fără perioadă', data: '', urgent: false }
    const days = daysUntil(zi)
    const cand = days === null ? formatDate(zi)
      : days === 0 ? 'azi'
      : days === 1 ? 'mâine'
      : days < 0 ? `acum ${-days} zile`
      : `peste ${days} zile`
    return {
      faza: FAZA_SCURT[p.urmatoarea_faza] || '',
      cand, data: formatDate(zi),
      urgent: days !== null && days <= 2,
    }
  }

  // PASTILA ARATA O STARE, DAR APASAREA PRODUCE O ACTIUNE — si actiunea aia
  // scoate cardul din grila. Scria „pregătire" (unde esti) si facea „finalizat"
  // (ce urmeaza), fara ca nimic sa spuna care e a doua. `toastUndo` era un
  // plasture peste un design care invita greseala; acum greseala nu se mai
  // intampla, iar undo-ul ramane pentru razgandire — sunt lucruri diferite.
  // (Observat de Ion, 2026-08-14.)
  //
  // ASIMETRIC CU INTENTIE: doar INCHIDEREA cere confirmare. Redeschiderea aduce
  // cardul inapoi in grila, deci se vede imediat ca s-a intamplat si n-are
  // nevoie de poarta. O confirmare pusa si acolo ar fi ceremonie fara miza.
  // Doua stari, nu una: `open` al lui ConfirmDialog e `$bindable` si se stinge
  // singur la Renunta, deci trebuie legat. Proiectul se tine separat, ca titlul
  // sa nu clipeasca in „proiectul" cat timp dialogul se inchide cu animatie.
  let deInchis = $state(null)
  let confirmDeschis = $state(false)

  async function cycleProjectStatus(e, p) {
    e.stopPropagation()
    if ((p.status || 'pregatire') !== 'finalizat') {
      deInchis = p
      confirmDeschis = true
      return
    }
    await schimbaStatus(p, 'pregatire')
  }

  async function schimbaStatus(p, next) {
    const cur = p.status || 'pregatire'
    try {
      await updateProject(p.id, { status: next })
      toastUndo(`Status: ${PROJECT_STATUS_LABELS[next] || next}`, {
        onUndo: async () => {
          try { await updateProject(p.id, { status: cur }); await loadProjects() }
          catch (err) { toast(`Eroare: ${err.message}`, 'error') }
        },
      })
    } catch (err) { toast(`Eroare: ${err.message}`, 'error') }
  }

  let showNewModal = $state(false)
  let showArchive = $state(false)
  let sort = $state({ key: 'nume', dir: 1 })

  // MODUL „SELECTEAZA" A PLECAT (N7, decis de Ion pe 2026-08-08).
  //
  // Desenul il scosese la cererea lui; codul il pastra. Era o stare intreaga —
  // buton in antet, bara de actiuni in masa pe tenta de accent, casuta pe fiecare
  // card, o a doua semnificatie pentru click si pentru Enter — pentru douazeci si
  // ceva de proiecte si o singura actiune in masa: stergerea. Iar stergerea in
  // masa a mai multor proiecte, fiecare cu taskurile si perioadele lui, e exact
  // genul de actiune pe care nu vrei s-o poti face din doua atingeri distrate.
  // Se sterg unul cate unul, prin confirmarea din pagina proiectului.

  let sortOpen = $state(false)
  let sortEl = $state(null)
  const sortLabel = $derived(sortOptions.find((o) => o.value === sort.key)?.label || 'Nume')

  function pickSort(v) {
    if (sort.key === v) sort = { key: v, dir: -sort.dir } // aceeasi optiune = inverseaza
    else sort = { key: v, dir: 1 }
    sortOpen = false
  }
  function onDocClick(e) {
    // Pe telefon meniul e o FOAIE, cu voalul ei — inchiderea vine de acolo.
    // Regula de aici ar inchide-o si la o atingere pe un loc gol DIN foaie:
    // foaia se randeaza in `body` (portal), deci tot ce e in ea e „in afara"
    // declansatorului.
    if (ecran.telefon) return
    if (sortOpen && sortEl && !sortEl.contains(e.target)) sortOpen = false
  }

  function cardKeydown(e, p) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openProject(p)
    }
  }

  function sortItems(items) {
    const { key, dir } = sort
    return [...items].sort((a, b) => {
      const av = (a[key] ?? '').toString().toLowerCase()
      const bv = (b[key] ?? '').toString().toLowerCase()
      if (av < bv) return -dir
      if (av > bv) return dir
      return 0
    })
  }

  function openProject(p) {
    try {
      const recents = JSON.parse(localStorage.getItem('recent_projects') || '[]')
      const fresh = [{ id: p.id, nume: p.nume, client: p.client, tip: p.tip },
        ...recents.filter(r => r.id !== p.id)].slice(0, 6)
      localStorage.setItem('recent_projects', JSON.stringify(fresh))
    } catch (_) {}
    navigate(`/projects/${p.id}`)
  }

  onMount(() => { loadProjects() })

  const activeItems = $derived(sortItems(projects.items.filter(p => p.status !== 'finalizat')))
  const archivedItems = $derived(sortItems(projects.items.filter(p => p.status === 'finalizat')))
</script>

<svelte:document onclick={onDocClick} />

<!-- `ruta-in`: ecranul SOSESTE, nu apare intre doua cadre. Aveau
     animatia doar Calendar, Planificator si Taskuri, deci jumatate din
     taburi se deschideau taiat si jumatate lin — raportat de Ion („nu
     toate taburile au animatii de deschidere"). Regula traieste in
     global.css, deci aici nu se adauga niciun CSS. -->
<div class="page ruta-in">
  <div class="page-header">
    <!-- Titlu FARA iconita si cu SUBTITLU text, ca in desen (3a: „7 active ·
         3 finalizate") — si la aceeasi pozitie ca pe toate rutele
         (standardizarea titlurilor, cerinta lui Ion). -->
    <div class="page-title-row">
      <h1>Proiecte</h1>
      <span class="page-sub">{activeItems.length} {activeItems.length === 1 ? 'activ' : 'active'} · {archivedItems.length} {archivedItems.length === 1 ? 'finalizat' : 'finalizate'}</span>
    </div>
    <!-- ANTETUL NU MAI ARE BUTON DE ADAUGARE. O singura cale per ecran: pe
         desktop cardul punctat din grila (e chiar in locul unde ar aparea
         proiectul nou), pe telefon butonul mare cu plus de jos. Erau amandoua,
         pe amandoua ecranele. -->
  </div>

  <div class="toolbar">
    <!-- PAGINA PROIECTE NU ARE CAMP DE CAUTARE.
         Sunt 21 de proiecte si se vad TOATE, in grila de sub bara asta. Un camp
         de cautare peste o lista pe care o cuprinzi din ochi nu scurteaza nimic
         — te pune sa scrii ca sa ajungi unde ajungeai uitandu-te. Cautarea care
         chiar cauta (peste note, taskuri, clienti) traieste in paleta din dock. -->
    <div class="sort-box" bind:this={sortEl}>
      <button class="sort-trigger" class:on={sortOpen} onclick={() => sortOpen = !sortOpen} title="Sortare: {sortLabel} {sort.dir === 1 ? '\u2191' : '\u2193'}" aria-haspopup="listbox" aria-expanded={sortOpen}>
        <ArrowUpDown size={ecran.telefon ? 18 : 15} />
        {#if !ecran.telefon}
          <span>{sortLabel}</span>
          <span class="sort-dir-ind">{sort.dir === 1 ? '\u2191' : '\u2193'}</span>
        {/if}
      </button>
      <!-- PE TELEFON MENIUL E O FOAIE, NU UN DROPDOWN (vezi foaia de mai jos).
           Un panou de 150px agatat de coltul din dreapta sus are randuri de 30px
           \u2014 sub jumatate din `--tap-min` \u2014 si sta exact acolo unde degetul
           acopera ce citeste. `DatePicker` primise deja tratamentul asta; meniul
           ramasese singurul strat plutitor din aplicatie desenat pentru cursor. -->
      {#if sortOpen && !ecran.telefon}
        <div class="sort-menu" role="listbox"
             onkeydown={(e) => {
               const opts = [...e.currentTarget.querySelectorAll('[role="option"]')]
               const idx = opts.indexOf(document.activeElement)
               if (e.key === 'ArrowDown') { e.preventDefault(); opts[(idx + 1) % opts.length]?.focus() }
               else if (e.key === 'ArrowUp') { e.preventDefault(); opts[(idx - 1 + opts.length) % opts.length]?.focus() }
               else if (e.key === 'Escape') { e.preventDefault(); sortOpen = false }
             }}
             transition:fly={{ y: -4, duration: motionDuration(DUR_BASE), easing: EASE }}>
          {@render optiuniSortare()}
        </div>
      {/if}
    </div>
    <!-- Arhiva e o DESTINATIE rara, nu un filtru — deci aceeasi haina de
         actiune-fantoma ca sortarea de langa ea, si ca „Arhivă" din /tasks. -->
    {#if archivedItems.length > 0}
      <button class="a-ico" class:on={showArchive} onclick={() => showArchive = !showArchive}
              title="Arhivă ({archivedItems.length} finalizate)" aria-pressed={showArchive}>
        <Archive size={ecran.telefon ? 18 : 14} />
        {#if !ecran.telefon}<span>Arhivă</span>{/if}
        <span class="a-n">{archivedItems.length}</span>
      </button>
    {/if}
  </div>

  <!-- SCHELETELE SUNT PENTRU PRIMA INCARCARE, NU PENTRU FIECARE ACTIUNE —
       aceeasi regula pe care o au deja Taskuri, boardul „Astăzi" si
       Planificatorul. `loadProjects()` se cheama dupa comutarea statusului de pe
       card, dupa stergere si la fiecare filtru, iar fara garda toata grila era
       inlocuita cu sase schelete si reconstruita la fiecare atingere. -->
  <!-- `!incarcat`, fara `loading`: daca n-avem inca un raspuns, ASTEPTAM — prin
       definitie. Cu `loading &&` in fata, primul cadru (inainte ca incarcarea sa
       apuce sa porneasca) cadea pe ramura urmatoare si arata STAREA GOALA, apoi
       scheletul, apoi raspunsul: trei forme pentru un board gol. -->
  {#if !projects.incarcat && !projects.error}
    <div class="cards-grid asteptare">
      {#each Array(6) as _}
        <div class="pcard skeleton-card"><Skeleton width="40%" height="14px" /><Skeleton width="70%" height="18px" /><Skeleton width="50%" height="12px" /></div>
      {/each}
    </div>
  {:else if projects.error}
    <ErrorState message={projects.error} onretry={() => loadProjects()} />
  {:else if activeItems.length === 0 && archivedItems.length === 0}
    <EmptyState icon={FolderKanban} title="Niciun proiect" description="Nu există proiecte cu filtrele selectate." />
  {:else}
    <div class="cards-grid">
      {#each activeItems as p, i (p.id)}
        {@const urm = urmatoarea(p)}
        <!-- `onpointerenter`/`onpointerdown`: cardul nu e `use:link` (cheama
             `navigate` de mana, ca sa scrie intai lista de recente), deci nu
             primeste preincarcarea de acolo. Pagina de proiect e cea mai scumpa
             din aplicatie — doua cereri si un modul de 63 KB — deci tocmai ea
             are cel mai mult de castigat din cele ~150ms dintre hover si click.

             `in:sosire|local` in loc de scara de celule pentru cardul NOU.
             `.cell-in` se joaca doar la prima incarcare de acum (vezi
             global.css), iar aici asta ar fi insemnat ca un proiect tocmai
             creat APARE intre doua cadre. `sosire` e primitiva scrisa exact
             pentru „un rand pe care l-ai nascut tu", si e si mai corecta decat
             ce era: intarzierea lui `.cell-in` venea din INDEXUL in lista, deci
             un card aparut pe pozitia a zecea astepta 240ms degeaba.
             `|local` — la deschiderea paginii blocul `{#each}` se creeaza
             intreg, iar acolo sosirea o face tranzitia de ruta. -->
        <div class="pcard cell-in" style="--celula: {i}" role="button" tabindex="0" animate:flip={{ duration: motionDuration(DUR_BASE) }} in:sosire|local onclick={() => openProject(p)} onkeydown={(e) => cardKeydown(e, p)} onpointerenter={() => preincarca(`/projects/${p.id}`)} onpointerdown={() => preincarca(`/projects/${p.id}`)}>
          <div class="card-top">
            <!-- TIPUL, SPUS O SINGURA DATA. Era un fulger amber intr-un chip
                 patrat PLUS cuvantul „PIF" — doua obiecte pentru un fapt care nu
                 se schimba niciodata, chiar langa pastila de status, care se
                 schimba. Iconita ramane, fara fill: linie subtire, gri, lipita de
                 cuvant. Culoarea din coltul de sus ramane DOAR la status.
                 Asta stinge si defectul „un fapt, doua culori": „Service" era
                 verde pe card (--success) si amber in arhiva (--service-accent). -->
            {#if p.tip}
              <span class="tip-ico">{#if p.tip === 'PIF'}<Zap size={13} strokeWidth={1.7} />{:else}<Wrench size={13} strokeWidth={1.7} />{/if}</span>
              <span class="tip-label">{p.tip}</span>
            {:else}<span class="tip-label">—</span>{/if}
            <!-- PE TOUCH E ETICHETA, NU BUTON. Pastila are 22px si sta in
                 interiorul zonei de atingere a cardului: o atingere usor deviata
                 ori deschide proiectul, ori ii schimba statusul, si nu se poate
                 sti dinainte care. Un card = o tinta; statusul se schimba din
                 pagina proiectului. Pe desktop ramane control — dar unul care
                 ARATA ca un control: fill discret + semnul de comutare.
                 NU chevron (raportat de Ion: „pare un dropdown cand de fapt nu
                 este"). Statusurile sunt DOUA de la v31, deci apasarea comuta
                 intre ele — nu deschide o lista. Un chevron promite un meniu, si
                 promisiunea aia se plateste la fiecare apasare care nu-l da. -->
            {#if ecran.telefon}
              <span class="status-pill" style="--st: {STATUS_COLORS[p.status] || 'var(--text-dim)'}">{PROJECT_STATUS_LABELS[p.status] || p.status || '—'}</span>
            {:else}
              <!-- Tooltipul spune CE URMEAZA, nu ce e. „Schimbă statusul" era
                   adevarat si inutil: nu te ajuta sa decizi daca apesi. -->
              <button class="status-pill act" style="--st: {STATUS_COLORS[p.status] || 'var(--text-dim)'}" onclick={(e) => cycleProjectStatus(e, p)}
                      title={p.status === 'finalizat' ? 'Redeschide proiectul' : 'Finalizează proiectul'}>
                {PROJECT_STATUS_LABELS[p.status] || p.status || '—'}<ArrowRightLeft size={11} strokeWidth={2.2} />
              </button>
            {/if}
          </div>
          <div class="card-name">{p.nume || '—'}</div>
          <div class="card-client">{p.client || '—'}</div>
          <div class="card-foot" title={urm.data}>
            {#if urm.faza}<span class="foot-faza">{urm.faza}</span>{/if}
            <span class="foot-cand" class:urgent={urm.urgent}>{urm.cand}</span>
          </div>
        </div>
      {/each}
      <!-- Cardul punctat e calea de pe DESKTOP: sta chiar in locul in care va
           aparea proiectul. Pe telefon grila e o coloana si cardul ar cadea sub
           tot — la capatul unei derulari — deci acolo calea e butonul mare cu
           plus, la indemana degetului mare. Una pe ecran, nu amandoua. -->
      {#if !ecran.telefon}
        <button class="pcard new-card cell-in" style="--celula: {activeItems.length}" onclick={() => showNewModal = true}>
          <!-- ICONITA, NU CARACTERUL „+”. Un plus tipografic la 21px are alta
               greutate si alta forma decat plusul Lucide de pe butonul mare de pe
               telefon si de pe restul aplicatiei — acelasi gest, doua desene. -->
          <Plus size={24} strokeWidth={1.5} />
          <span class="new-label">Proiect nou</span>
        </button>
      {/if}
    </div>

    <!-- Arhiva se deschide din bara de sus; aici ramane doar continutul, cu un
         cap de sectiune care spune unde esti. -->
    {#if archivedItems.length > 0 && showArchive}
      <div class="archive" transition:slide={{ duration: motionDuration(DUR_BASE), easing: EASE }}>
        <div class="arch-cap"><Archive size={13} /><span>Arhivă · finalizate</span><span class="grup-n">{archivedItems.length}</span></div>
        <div class="arch-list">
          {#each archivedItems as p (p.id)}
            <button class="arch-row archived" animate:flip={{ duration: motionDuration(DUR_BASE) }} onclick={() => openProject(p)}>
              <span class="arch-name">{p.nume || '—'}</span>
              <span class="dim arch-client">{p.client || '—'}</span>
              <!-- Acelasi tip, aceeasi haina ca pe card: linie subtire + cuvant.
                   Aici statea ca pastila colorata — a doua definitie a aceluiasi
                   fapt, si tocmai cea care nu se potrivea cu prima.
                   COLOANA SE RANDEAZA SI GOALA, cand proiectul n-are tip: o coloana
                   care dispare de pe un rand muta data si badge-ul fata de randurile
                   de deasupra, adica exact alinierea pentru care exista latimi fixe. -->
              <span class="ptip">{#if p.tip}<span class="tip-ico">{#if p.tip === 'PIF'}<Zap size={12} strokeWidth={1.7} />{:else}<Wrench size={12} strokeWidth={1.7} />{/if}</span>{p.tip}{/if}</span>
              <span class="dim arch-urm">{p.urmatoarea ? formatDate(p.urmatoarea) : '—'}</span>
              <span class="arch-badge"><Badge label="Finalizat" color="var(--success)" small /></span>
            </button>
          {/each}
        </div>
      </div>
    {/if}
  {/if}

  <!-- BUTONUL MARE CU PLUS — singura cale de adaugare de pe telefon, acelasi
       obiect ca in Taskuri (`Tasks.svelte`), la aceleasi coordonate: peste dock,
       in dreapta, unde ajunge degetul mare fara sa muti telefonul in mana.
       Ascuns in arhiva: acolo te uiti la ce s-a terminat, nu adaugi. -->
  {#if ecran.telefon && !showArchive}
    <button class="fab" onclick={() => showNewModal = true} aria-label="Proiect nou">
      <Plus size={25} strokeWidth={1.5} />
    </button>
  {/if}
</div>

<!-- Optiunile de sortare, o singura data pentru amandoua suprafetele: dropdown
     pe desktop, foaie pe telefon. Duplicate, cele doua liste s-ar desincroniza
     exact la a sasea optiune adaugata. -->
{#snippet optiuniSortare()}
  {#each sortOptions as opt (opt.value)}
    <button class="sort-opt" class:sel={sort.key === opt.value} role="option"
            aria-selected={sort.key === opt.value} onclick={() => pickSort(opt.value)}>
      <span>{opt.label}</span>
      {#if sort.key === opt.value}<span class="sort-dir-ind">{sort.dir === 1 ? '↑' : '↓'}</span>{/if}
    </button>
  {/each}
{/snippet}

{#if ecran.telefon}
  <!-- `iesireGest`: pe o foaie de meniu `X`-ul din colt e drumul cel mai lung
       pentru degetul mare, iar iesirea exista deja de trei ori — voalul, gestul
       in jos, si alegerea insasi. -->
  <Modal bind:open={sortOpen} title="Sortează după" iesireGest>
    <div class="meniu-foaie" role="listbox">{@render optiuniSortare()}</div>
  </Modal>
{/if}

<ProjectFormModal bind:open={showNewModal} onsaved={() => loadProjects()} />

<!-- `danger={false}`: finalizarea nu distruge nimic, e un pas normal din viata
     proiectului — proiectul ramane in arhiva si se poate redeschide. Rosul
     ramane pentru stergere, altfel isi pierde intelesul. -->
<ConfirmDialog
  bind:open={confirmDeschis}
  title={`Finalizezi „${deInchis?.nume || 'proiectul'}”?`}
  message="Trece în arhivă și dispare din grilă. Îl poți redeschide de acolo oricând."
  confirmLabel="Finalizează proiectul"
  danger={false}
  onconfirm={async () => { if (deInchis) await schimbaStatus(deInchis, 'finalizat') }}
/>

<style>
  .page { padding: var(--space-lg); }
  /* `flex-wrap` a ramas desi antetul nu mai are butoane de adaugare: titlul plus
     numarul tot pot depasi un ecran ingust, iar `.app-main { overflow-x: clip }`
     le-ar taia in tacere. */
  .page-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); flex-wrap: wrap; margin-bottom: var(--space-md); }
  .page-title-row { min-width: 0; }
  .page-title-row h1 { overflow-wrap: anywhere; }
  .page-title-row { display: flex; align-items: baseline; gap: var(--space-sm); color: var(--text); }
  .page-title-row h1 { font-size: var(--font-title); font-weight: var(--fw-semibold); }
  .page-sub { font-size: var(--font-small); font-weight: var(--fw-medium);
    color: var(--text-secondary); white-space: nowrap; }

  .toolbar { display: flex; gap: var(--space-md); align-items: center; margin-bottom: var(--space-md); flex-wrap: wrap; }

  /* „Arhivă": actiune-fantoma. Nu e filtru, deci nu poarta chip.
     Inaltimea urca la 36, cat sortarea de langa ea — doua controale pe acelasi
     rand nu se pot deosebi prin sase pixeli pe care nu i-a ales nimeni. Haina
     insa NU se schimba pe desktop: e aceeasi cu „Arhivă" din /tasks, si daca se
     muta pe suprafata, se muta acolo, in amandoua locurile odata. Pe telefon
     primeste suprafata (vezi blocul de 768). */
  .a-ico { display: inline-flex; align-items: center; gap: 6px;
    min-height: 36px; padding: 0 10px; border-radius: var(--radius-sm);
    background: transparent; border: 1px solid transparent;
    font-size: var(--font-small); font-weight: var(--fw-medium);
    color: var(--text-dim); cursor: pointer; transition: var(--transition-colors); }
  .a-ico:hover { color: var(--text); background: var(--bg-hover); }
  .a-ico.on { background: var(--accent-subtle); color: var(--accent-on-subtle); }
  .a-n { font-family: var(--font-mono); color: var(--text-dim); font-variant-numeric: tabular-nums; }
  .a-ico.on .a-n { color: inherit; }

  /* Sortare — control + meniu custom; click pe optiunea activa inverseaza
     directia (sageata arata directia curenta).
     SUPRAFATA SE DESPRINDE PRIN UMBRA, NU PRIN CHENAR. Sortarea ramasese in
     haina veche (30px, contur, rază plină) dupa ce Calendarul (M3) si
     Departamentul (C2) au primit-o pe cea din sistem: 36px, fond de suprafata,
     `--shadow-sm`, raza de control (10). */
  .sort-box { position: relative; }
  .sort-trigger { display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 12px; font-size: var(--font-control); font-weight: var(--fw-semibold); color: var(--text-secondary); background: var(--bg-surface); box-shadow: var(--shadow-sm); border: none; border-radius: var(--radius-sm); cursor: pointer; transition: var(--transition-colors); }
  .sort-trigger:hover { color: var(--text); background: var(--bg-hover); }
  /* Meniul deschis: tenta poarta cerneala ADANCA (`--accent-on-subtle` e literal
     `--accent-deep`), iar umbra pleaca — o suprafata tentata nu mai e ridicata. */
  .sort-trigger.on { color: var(--accent-on-subtle); background: var(--accent-subtle); box-shadow: none; }
  /* Sageata directiei e semn, nu cuvant — mono, ca in desen (R6). */
  .sort-dir-ind { font-family: var(--font-mono); font-size: var(--font-small); opacity: .8; }
  /* SUPRAFATA PLUTITOARE SE DESPRINDE PRIN UMBRA, NU PRIN CHENAR (nota A5 din
     Modal.svelte): chenarul a iesit din sistem odata cu redesignul, iar aici
     statea peste `--shadow-lg` — doua semnale pentru acelasi lucru.
     `var(--z-dropdown)` fara rezerva: un `, 50` scris de mana mascheaza exact
     cazul in care tokenul lipseste, adica singurul in care ai vrea sa afli. */
  .sort-menu { position: absolute; top: calc(100% + 5px); right: 0; z-index: var(--z-dropdown); min-width: 150px; background: var(--bg-overlay); border-radius: var(--radius-md); box-shadow: var(--shadow-md); padding: 4px; }
  .sort-opt { display: flex; align-items: center; justify-content: space-between; gap: var(--space-sm); width: 100%; padding: 7px 10px; border-radius: var(--radius-sm); color: var(--text-secondary); font-size: var(--font-small); background: transparent; border: none; text-align: left; cursor: pointer; }
  .sort-opt:hover { background: var(--bg-hover); color: var(--text); }
  .sort-opt.sel { background: var(--accent-subtle); color: var(--accent-on-subtle); }

  /* Aceleasi optiuni, pe foaie: randul creste de la 30 la `--tap-sheet` si textul
     de la meta (13) la corp, fiindca aici nu mai e un panou pe langa cursor, ci
     lista principala a ecranului. Marginile negative anuleaza padding-ul foii pe
     laterale, ca randul atins sa mearga de la o margine la alta — pe telefon o
     tinta care se opreste la 16px de marginea ecranului rateaza degetul mare. */
  .meniu-foaie { display: flex; flex-direction: column; gap: 2px; margin: 0 calc(var(--space-md) * -1 + 4px); }
  .meniu-foaie .sort-opt {
    min-height: var(--tap-sheet);
    padding: 0 var(--space-12);
    font-size: var(--font-body);
  }
  .meniu-foaie .sort-opt:active { background: var(--bg-active); }

  .cards-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: var(--space-md); }
  /* HOVERUL RIDICA UMBRA, NU CARDUL (T13).
     `.pcard` era singurul obiect din aplicatie care se MUTA la hover (4px in
     sus). Dockul scosese exact asta, cu motivul scris in cod: o suprafata care
     isi schimba locul cand treci cursorul peste ea muta si tot ce citeai langa
     ea, iar intr-o grila de carduri asta inseamna ca randul respira sub mouse.
     Elevatia se citeste din UMBRA — deci hoverul o adanceste, si atat.
     Raspunsul ramane pe `--dur-fast`: hoverul ajunge inaintea deciziei. */
  .pcard { position: relative; display: flex; flex-direction: column; min-height: 142px; background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-md); padding: var(--space-md) var(--space-20); cursor: pointer; text-align: left; transition: box-shadow var(--dur-fast) var(--ease), transform var(--dur-press) var(--ease); }
  /* Doar unde exista cursor. Pe touch, cardul atins ramanea ridicat cu 4px si cu
     umbra pana atingeai altceva — parea selectat, desi nu era. */
  @media (hover: hover) {
    .pcard:hover:not(.new-card) {
      box-shadow: var(--shadow-md), 0 0 0 1px var(--border-strong);
    }
  }
  .pcard:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  /* Conturul e SCRIS, nu mostenit: `.pcard` n-are bordura (suprafata se desprinde
     prin umbra), deci `border-style: dashed` singur cadea pe implicite — 3px in
     currentColor. Desenul cere 1.5px `--border-strong`. Umbra pleaca: cardul asta
     nu e o suprafata, e un loc gol conturat.
     Cerneala e `--text-secondary`, nu `--text-dim`: „Proiect nou" e o actiune de
     citit, la 15px, si e singurul text de pe card. */
  .pcard.new-card { border: 1.5px dashed var(--border-strong); box-shadow: none; align-items: center; justify-content: center; gap: 6px; color: var(--text-secondary); background: transparent; }
  .pcard.new-card:hover { color: var(--accent); border-color: var(--accent); box-shadow: none; }
  .new-label { font-size: var(--font-body); font-weight: var(--fw-semibold); }
  /* Regula era scrisa de doua ori la rand, a doua fara `gap` si fara marja — deci
     `gap` ramanea 4 (mostenit din prima) si `margin-bottom` 10. Una singura, cu
     valorile din desen: 7 intre iconita si cuvant, 12 pana la numele proiectului. */
  .card-top { display: flex; align-items: center; gap: 7px; margin-bottom: 12px; }
  .card-top .status-pill { margin-left: auto; }
  /* `.card-check` a plecat: era casuta de selectie a modului „Selectează", scos
     din Proiecte la feedbackul lui Ion (N7). Clasa nu mai apare in markup, deci
     Svelte taia oricum regula din build — un rand care nu putea ajunge niciodata
     pe ecran. */
  /* Numele proiectului urca pe `--font-h2`: e numele unui lucru, deci poarta
     fontul de titlu la o treapta care EXISTA. Era la 1.05rem — o marime pe care
     n-o numea niciun token, intre h3 si body, aleasa o data si ramasa acolo. */
  .card-name { font-family: var(--font-heading); font-size: var(--font-h2); font-weight: var(--fw-semibold); letter-spacing: var(--tracking-tight); color: var(--text); line-height: var(--lh-snug); overflow-wrap: anywhere; }
  /* --text-dim, nu faint: numele clientului e INFORMATIE, nu eticheta —
     iar faint e documentat „doar etichete/large" (3:1). Masurat: 3.18:1 la
     11.2px, sub pragul AA de 4.5 pentru text mic. */
  .card-client { font-size: var(--font-small); color: var(--text-dim); margin-top: 2px; }
  /* Doua trepte, nu una: faza e ETICHETA (micro, uppercase, faint), socoteala e
     INFORMATIE (tiny, mono) si poarta singura culoarea. Data plina sta in
     `title` — nu ocupa un rand pentru ceva ce verifici cand cauti. */
  .card-foot { margin-top: auto; padding-top: 14px; display: flex; align-items: baseline; gap: 7px; }
  .foot-faza { font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); }
  .foot-cand { font-family: var(--font-mono); font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text-secondary); }
  .foot-cand.urgent { color: var(--danger); font-weight: var(--fw-semibold); }
  .skeleton-card { gap: 8px; cursor: default; }

  .dim { color: var(--text-secondary); }
  /* Tipul e o LINIE, nu un fill: aceeasi definitie pe card si in arhiva. */
  .tip-ico { display: inline-flex; align-items: center; color: var(--text-dim); flex-shrink: 0; }
  .ptip { width: 74px; flex: none; display: inline-flex; align-items: center; gap: 5px; font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); }
  /* Fara `margin-left`: distanta pana la iconita o da `gap`-ul lui `.card-top`.
     Erau amandoua — 4 din gap plus 7 din marja, adica 11 in loc de 7. */
  .tip-label { font-size: var(--font-label); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); }

  .archive { margin-top: var(--space-lg); }
  /* DM Mono e doar pentru cifre si coduri. „Arhivă · finalizate" e text — deci
     fontul paginii; cifra de langa el ramane mono. */
  /* Cerneala din desen: eticheta pe `--text-secondary` (treapta a doua), nu pe
     faint — e titlul sectiunii, nu o nota. */
  .arch-cap { display: flex; align-items: center; gap: var(--space-xs);
    padding: 0 2px var(--space-sm); color: var(--text-secondary);
    font-size: var(--font-label);
    font-weight: var(--fw-semibold); text-transform: uppercase;
    letter-spacing: var(--tracking-label); }
  /* Cifra sta pe FUNDAL, nu pe tenta de „facut". Tenta ar fi cerut cerneala
     adanca (`--success-deep`, nu `--success` plin, cum era) — dar aici nu spune
     nimic in plus: lista de dedesubt e numai finalizate, verdele ar repeta-o. */
  .grup-n { font-family: var(--font-mono); font-size: var(--font-label);
    color: var(--text-secondary); font-variant-numeric: tabular-nums; }
  /* NICIO OPACITATE PE UN RAND DE TEXT (regula sistemului). Ca e arhivat o spune
     ANTETUL sectiunii, sub care randul chiar sta — nu o stingere care se inmulteste
     peste tokenuri deja la limita si scoate randul sub AA. */
  .archived .arch-name { color: var(--text-secondary); }
  .arch-list { display: flex; flex-direction: column; background: var(--bg-surface); border-radius: var(--radius-md); box-shadow: var(--shadow-md); overflow: hidden; }
  /* COLOANE FIXE, NU FLEX CU GAP. Cu `gap` + `margin-left: auto` pe coada,
     clientul incepea imediat dupa nume — adica pe fiecare rand in alt loc — si
     lista se citea ca trei propozitii, nu ca un tabel. Latimile sunt cele din
     desen; intr-o lista de trei randuri clientii stau unul sub altul.
     Randul e 44 (randul de lista pe desktop), nu 34, iar numele urca la treapta
     lui: la 13 era aceeasi marime ca metadatele de langa el. */
  .arch-row { position: relative; display: flex; align-items: center; gap: var(--space-md);
    width: 100%; min-height: 44px; padding: 0 18px; font-size: var(--font-small);
    color: var(--text); text-align: left; cursor: pointer; background: transparent;
    border: none; transition: background-color var(--dur-fast) var(--ease); }
  /* Separatorul e RETRAS 18px de fiecare parte, exact cat paddingul randului —
     nu merge dintr-o muchie a suprafetei in cealalta. Din `::before` pe randurile
     2..n (aceeasi reteta ca `.arow` din TodayBoard), nu din `border-bottom` pe
     fiecare rand plus o exceptie pe ultimul. */
  .arch-row + .arch-row::before { content: ''; position: absolute; top: 0;
    left: 18px; right: 18px; height: 1px; background: var(--border); }
  .arch-row:hover { background: var(--bg-hover); opacity: 1; }
  .arch-name { flex: 1; min-width: 0; font-size: var(--font-body); font-weight: var(--fw-medium);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .arch-client { width: 120px; flex: none; font-size: var(--font-small);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .arch-urm { width: 52px; flex: none; text-align: right; font-size: var(--font-small); font-family: var(--font-mono); }
  .arch-badge { width: 82px; flex: none; display: inline-flex; justify-content: center; }

  /* Butonul mare cu plus (doar telefon). Valorile din desen (T4): 58×58, raza 18,
     plusul 25/1.5, cu 24px deasupra dockului (dockul randat are 72 = 68 + 4).
     Cel mai mare obiect plutitor din aplicatie — daca se schimba, se schimba si
     perechea lui din `Tasks.svelte`. */
  /* Geometria butonului plutitor, o singura data: o citesc si butonul, si
     rezerva de sub lista (`--fab-loc` mai jos). */
  .fab { --fab-size: 58px;
    position: fixed; right: calc(var(--space-md) + var(--safe-right));
    bottom: calc(var(--dock-h) + 4px + 24px + var(--safe-bottom));
    width: var(--fab-size); height: var(--fab-size); display: grid; place-items: center;
    border-radius: var(--radius-lg); border: none;
    background: var(--accent); color: var(--accent-text);
    box-shadow: var(--shadow-md); z-index: calc(var(--z-sticky) - 1);
    cursor: pointer; transition: var(--transition-pressable); }
  .fab:active { transform: scale(var(--press-scale)); }
  /* Fill discret in loc de contur gol: o pastila conturata se citeste ca eticheta,
     iar asta comuta statusul. Chevronul o spune fara `title`. Culoarea vine din
     `--st` (STATUS_COLORS), deci fondul se deduce din ea — o singura regula
     pentru amandoua statusurile, nu doua tokenuri scrise de mana. */
  /* CHIP CU COLTURI DE 8, NU CERC. Scara de raze e „8 chip · 10 control · 14
     suprafata · 20 foaia · cerc doar bifa"; `--radius-full` facea din status
     singurul obiect rotund de pe ecran care nu e o bifa.
     Si cerneala: era `--st` PLIN peste propria tenta. Text pe tenta ia
     intotdeauna adancul — cum `--st` vine din `STATUS_COLORS` si nu are treapta
     `-deep`, adancul se DERIVA, aceeasi formula ca in `Badge.svelte`. */
  .status-pill { display: inline-flex; align-items: center; gap: 4px;
    margin-left: auto; font-size: var(--font-small); font-weight: var(--fw-semibold);
    padding: 0 10px; min-height: 24px; border-radius: var(--radius-xs);
    color: color-mix(in oklab, var(--st) 72%, var(--text));
    background: color-mix(in oklab, var(--st) 13%, transparent);
    border: 1px solid transparent; white-space: nowrap; }
  .status-pill.act { padding: 0 8px 0 11px; cursor: pointer;
    transition: border-color var(--dur-fast) var(--ease), transform var(--dur-press) var(--ease); }
  .status-pill.act :global(svg) { opacity: .6; }
  @media (hover: hover) {
    .status-pill.act:hover { border-color: var(--st); }
  }
  .status-pill.act:active { transform: scale(var(--press-scale-sm)); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md);
      /* BUTONUL PLUTITOR ISI FACE LOC. `.app-content` rezerva doar cat dockul
         (`--dock-h + 24`), dar butonul sta cu 28px peste dock si e inalt de 58 —
         deci ultimul rand al listei ajungea sub el, cu tot cu coloana termenului,
         si nici nu se mai putea atinge. 58 + 16 acopera banda cu 12px de scapare. */
      padding-bottom: calc(58px + var(--space-md)); }
    /* ACELASI RITM CA /tasks (decizia din 2026-07-30: „aceleasi elemente, ~30px
       mai sus"). Masurat aici inainte: primul card incepea la y=314 pe 390×844 —
       37% din ecran, exact procentul pentru care /tasks a fost strans; pagina
       asta ramasese in urma. Nimic nu dispare, doar distantele. */
    .page { padding-top: var(--space-12); }
    .page-header, .toolbar { margin-bottom: 10px; }
    /* UN RAND DE BARA, NU TREI. Reparatia de dinainte a scazut doar marginile de
       la 16 la 10 — dar cei 37% pana la primul card erau ELEMENTELE, nu
       distantele: cautare, trei chipuri si sortare, fiecare pe randul lui, ~150px.
       Cu chipurile scoase si cu sortarea si arhiva ca iconite de 44px, totul intra
       pe un rand: primul card urca de la y≈314 la y≈224 — un card intreg castigat. */
    .toolbar { flex-direction: row; align-items: center; gap: var(--space-sm); }
    /* Caseta are 44px, dar inputul dinauntru avea 25 — iar el e singurul care
       primeste focus (caseta e un <div>, nu un <label>), deci tinta reala era de
       25px. `align-self: stretch` il face sa umple caseta. */
    /* Iconite patrate de 48px: eticheta e in `title`, forma o spune. NU 44:
       `--tap-min` e minimul pentru un control asezat INTR-UN RAND CU ALTCEVA;
       aici cele doua stau singure pe un rand sub titlu, deci sunt tinte
       principale, nu accesorii. Amandoua poarta haina de suprafata (fond +
       umbra, fara chenar) — pe telefon se vede mai tare decat pe desktop,
       fiindca butoanele sunt izolate. */
    .sort-trigger, .a-ico {
      width: 48px; height: 48px; min-height: 48px;
      padding: 0; justify-content: center; flex-shrink: 0;
      border-radius: var(--radius-sm);
      background: var(--bg-surface); box-shadow: var(--shadow-sm); border: none;
      color: var(--text-secondary); }
    /* Contorul arhivei ar dubla latimea iconitei; numarul se citeste oricum din
       lista cand o deschizi. */
    .a-n { display: none; }
    .arch-badge { display: none; }
    .arch-client { width: 80px; }
    /* PASTILA DE STATUS E ETICHETA PE TOUCH (vezi markup: nici nu mai e <button>),
       deci stratul invizibil de 44px din jurul ei — care fura atingeri de la card
       — a plecat cu totul. Un card = o tinta. */
    /* Antetul nu mai are butoane: adaugarea e butonul mare cu plus de jos, iar
       „Selectează" a plecat cu tot cu modul (N7). */
  }

  @media (max-width: 560px) {
    .cards-grid { grid-template-columns: 1fr; }
    /* PE O COLOANA CARDUL SE STRANGE PE CONTINUT. `min-height: 142` si
       `margin-top: auto` au rost cat timp cardurile stau umar la umar si trebuie
       sa se termine la aceeasi linie; pe o coloana umflau fiecare card pana la
       142 si lasau un gol intre client si picior. Piciorul primeste distanta lui
       (14) ca MARJA, si atunci `padding-top` ar dubla-o. */
    .pcard { min-height: 0; padding: 16px 18px; }
    .card-foot { margin-top: 14px; padding-top: 0; }
    /* Desenul 3c: capul cardului la 10 de nume pe telefon (12 pe desktop). */
    .card-top { margin-bottom: 10px; }
  }
</style>
