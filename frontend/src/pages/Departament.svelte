<script module>
  import { preia as _preia, dinCache as _dinCache, uita as _uita } from '../lib/cache.js'

  const URL_SETARE = '/api/settings/plan-departament'

  /** Chemata de router inainte de a intra pe ruta (vezi App). Linkul se schimba
   *  o data la cateva luni, deci pagina asta e cea mai buna candidata la cache:
   *  fara el, un `<iframe>` de 420px era precedat de fiecare data de un schelet
   *  de 420px, pentru o cerere care intoarce un singur camp. */
  export function pregateste() {
    return _preia(URL_SETARE, { proaspat: 5000 })
  }
</script>

<script>
  // Planul intregului departament SRP — o aplicatie externa, incorporata aici.
  //
  // De ce incorporat si nu doar un link: intrebarea „cine e unde saptamana asta"
  // se pune imediat dupa „unde sunt eu", iar un tab separat inseamna sa iesi din
  // context. Nu importam datele lor — e o plansa, nu o structura cu API.
  //
  // Linkul contine cheia de acces in fragment (dupa #), deci NU ajunge la
  // serverul lor prin cererea HTTP si nu apare in logurile nimanui. Il tinem in
  // app_settings (baza de date e gitignored), niciodata in cod sau in wiki.
  import { onMount } from 'svelte'
  import { ExternalLink, Link2, Save, X, TriangleAlert } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { toast } from '../stores/ui.svelte.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'

  let url = $state('')
  let host = $state('')
  let loading = $state(true)
  let error = $state(null)
  let editeaza = $state(false)
  let ciorna = $state('')
  let salvez = $state(false)

  function aseaza(d) {
    url = d.url || ''
    host = d.host || ''
    editeaza = !url
    ciorna = url
  }

  async function load() {
    // Ce stim deja se pune INAINTE de primul cadru, ca revenirea pe tab sa nu
    // mai treaca printr-un schelet de 420px. Cererea se face oricum dupa.
    const gata = _dinCache(URL_SETARE)
    const dinMemorie = gata !== undefined
    if (dinMemorie) { aseaza(gata); loading = false; error = null }
    else { loading = true; error = null }
    try {
      aseaza(await _preia(URL_SETARE))
    } catch (e) {
      if (!dinMemorie) error = e.message
    } finally {
      loading = false
    }
  }

  async function salveaza() {
    salvez = true
    try {
      const d = await apiJson('/api/settings/plan-departament', {
        method: 'PUT', body: { url: ciorna.trim() },
      })
      url = d.url || ''
      editeaza = !url
      // Ce stia cache-ul e acum gresit, iar `load()` nu se mai cheama — starea
      // locala e deja corecta. Fara asta, urmatoarea intrare pe tab s-ar deschide
      // cu LINKUL VECHI pentru cateva cadre, adica exact ce tocmai ai schimbat.
      // Nu scriem noua valoare in cache: raspunsul lui PUT n-are `host`, deci
      // ar intra o intrare incompleta.
      _uita(URL_SETARE)
      toast(url ? 'Link salvat' : 'Link șters', 'success')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      salvez = false
    }
  }

  onMount(load)
</script>

<!-- `ruta-in`: ecranul SOSESTE, nu apare intre doua cadre. Aveau
     animatia doar Calendar, Planificator si Taskuri, deci jumatate din
     taburi se deschideau taiat si jumatate lin — raportat de Ion („nu
     toate taburile au animatii de deschidere"). Regula traieste in
     global.css, deci aici nu se adauga niciun CSS. -->
<div class="page ruta-in">
  <!-- Titlul sta IN PAGINA, ca pe toate rutele (standardizat la cererea lui
       Ion) — `ui.pageHeader` scria in bara aplicatiei, la alta inaltime, si pe
       telefon disparea cu totul. -->
  <div class="page-header">
    <div class="page-title-row">
      <h1>Departament</h1>
      <span class="page-sub">Planul întregii echipe</span>
    </div>
    <!-- PE LINIA TITLULUI, nu pe un rand al lor (Ion, 2026-08-23: „ca sa incapa
         tot campul cu planner fara sa dau scroll"). Randul separat costa 38px de
         control plus doua margini, si mai rau: ramanea acolo si cand editai
         linkul, gol, fiindca doar CONTINUTUL lui era conditionat. Antetul avea
         deja `justify-content: space-between` — locul din dreapta il astepta. -->
    {#if url && !editeaza}
      <div class="actiuni">
        <a class="b" href={url} target="_blank" rel="noopener noreferrer">
          <ExternalLink size={13} /> Deschide în tab nou
        </a>
        <button class="b" onclick={() => { ciorna = url; editeaza = true }}>
          <Link2 size={13} /> Schimbă linkul
        </button>
      </div>
    {/if}
  </div>
  {#if loading}
    <div class="asteptare"><Skeleton height="420px" /></div>
  {:else if error}
    <ErrorState message={error} onretry={load} />
  {:else}
    {#if editeaza}
      <div class="config">
        <h2>Linkul planului de departament</h2>
        <p>
          Din aplicația de plan, ia linkul de partajare și lipește-l aici. Se acceptă
          doar adrese <code>https://{host}</code>.
        </p>
        <!-- AVERTISMENTUL E CONTINUT, NU DECOR. Era o dunga de 3px pe stanga
             — adica al saptelea inteles al aceleiasi muchii de 3px din
             aplicatie. Acum e o suprafata in tenta de restant, cu iconita: se
             citeste ca o casuta de atentie, nu ca un citat. -->
        <p class="atentie">
          <TriangleAlert size={16} strokeWidth={1.5} />
          <span>Linkul conține cheia de acces la plan — cine îl are, intră. Se salvează în
          baza de date a Dashboard-ului, care nu ajunge în git.</span>
        </p>
        <div class="rand">
          <input
            type="url"
            bind:value={ciorna}
            placeholder="https://{host}/#/?frame=1&…"
            spellcheck="false"
            autocomplete="off"
          />
          <button class="b ok" onclick={salveaza} disabled={salvez}>
            <Save size={13} /> Salvează
          </button>
          {#if url}
            <button class="b" onclick={() => { ciorna = url; editeaza = false }}>
              <X size={13} /> Renunță
            </button>
          {/if}
        </div>
      </div>
    {:else if url}
      <!-- allow-same-origin lipseste intentionat din sandbox? NU: aplicatia lor
           are nevoie de propriul origin (storage, cookies) ca sa functioneze.
           Nu punem sandbox deloc — CSP-ul nostru (frame-src) e cel care
           limiteaza CE poate fi incadrat, iar domeniul e verificat si pe server. -->
      <iframe title="Planul departamentului" src={url} allow="fullscreen"></iframe>
    {/if}
  {/if}
</div>

<style>
  /* MARJA NEGATIVA A PLECAT. Pagina isi lua ~80px inaltime in plus anuland
     rezerva pe care `.app-content` o pastreaza pentru dock — deci pe pagina
     asta, si numai pe ea, dockul plutea PESTE continut in loc sa stea sub el.
     Un plan de departament nu e destul de important cat sa mute navigatia
     aplicatiei; dockul sta unde sta peste tot. */
  /* Acelasi padding de sus ca restul rutelor (--space-lg): titlul sta acum in
     pagina si trebuie sa cada pe aceeasi linie ca pe /projects, /tasks, /plan. */
  .page { padding: var(--space-lg);
          display: flex; flex-direction: column;
          height: calc(100dvh - var(--header-height) - var(--dock-h) - var(--space-lg) - var(--safe-bottom));
          min-height: 380px; overflow: hidden; }
  .page-header { display: flex; align-items: center; justify-content: space-between;
    gap: var(--space-sm); flex-wrap: wrap; margin-bottom: var(--space-md); flex: none; }
  .page-title-row { display: flex; align-items: baseline; gap: var(--space-sm);
    color: var(--text); min-width: 0; }
  .page-title-row h1 { font-size: var(--font-title); font-weight: var(--fw-semibold); }
  .page-sub { font-size: var(--font-small); font-weight: var(--fw-medium);
    color: var(--text-secondary); white-space: nowrap; }

  /* Actiunile stau in antet, in capatul din dreapta. `flex: none` ca titlul sa
     cedeze primul cand se ingusteaza, nu ele. */
  .actiuni { display: flex; align-items: center; gap: var(--space-sm); flex: none; }

  /* Controlul in rand: 38px, 15/600, suprafata cu umbra fina — fara chenar, ca
     peste tot dupa redesign. Erau 28px si 13px fara greutate. */
  .b { display: inline-flex; align-items: center; gap: var(--space-6); height: var(--ctrl-md); padding: 0 13px;
       font-size: var(--font-body); font-weight: var(--fw-semibold); border: none;
       background: var(--bg-surface); box-shadow: var(--shadow-sm);
       color: var(--text-secondary); border-radius: var(--radius-sm); cursor: pointer;
       transition: var(--transition-pressable); }
  .b:hover:not(:disabled) { background: var(--bg-hover); color: var(--text); }
  .b:active:not(:disabled) { transform: scale(var(--press-scale)); }
  .b:disabled { opacity: 0.5; cursor: default; }
  .b.ok { color: var(--success); border-color: color-mix(in srgb, var(--success) 45%, transparent); }

  /* Fundal alb sub cadru: aplicatia lor e pe tema deschisa, iar pe fundalul
     nostru cald-inchis marginile ar aparea ca o rama murdara in timpul incarcarii. */
  /* CADRUL RAMANE ALB SI PE TEMA INTUNECATA: aplicatia dinauntru e desenata pe
     temă deschisă, deci un fundal inchis sub ea ar aparea ca o rama murdara —
     si in timpul incarcarii, si pe marginile pe care ea nu le acopera. */
  iframe { flex: 1; width: 100%; border: 0; border-radius: var(--radius-md);
           box-shadow: var(--shadow-md); background: #fff; min-height: 0; }

  .config { max-width: 640px; background: var(--bg-surface); border: 0;
            border-radius: var(--radius-md); box-shadow: var(--shadow-md);
            padding: var(--space-lg); }
  /* Greutatea, nu doar marimea: fara ea supravietuia `bold`-ul din foaia
     browserului, iar asta era singurul 700 randat din toata aplicatia — scara
     are 400, 500 si 600, si nimeni nu scrisese 700 nicaieri. */
  .config h2 { font-size: var(--font-h2); font-weight: var(--fw-semibold); margin-bottom: var(--space-sm); }
  .config p { font-size: var(--font-small); color: var(--text-dim); margin-bottom: var(--space-sm); line-height: var(--lh-normal); }
  .config code { font-family: var(--font-mono); font-size: var(--font-small); color: var(--text-secondary); }
  .atentie { display: flex; gap: var(--space-10); align-items: flex-start;
             background: var(--danger-subtle); color: var(--danger-deep);
             border-radius: var(--radius-xs); padding: var(--space-10) var(--space-12); }
  .atentie :global(svg) { flex: none; margin-top: 1px; }

  .rand { display: flex; gap: var(--space-sm); flex-wrap: wrap; margin-top: var(--space-md); }
  .rand input { flex: 1; min-width: 260px; height: var(--ctrl-sm); padding: 0 var(--space-10); font-family: var(--font-mono);
                font-size: var(--font-small); color: var(--text); background: var(--bg-elevated);
                border: 1px solid var(--border); border-radius: var(--radius-sm); }
  .rand input:focus { outline: none; border-color: var(--accent); }

  @media (max-width: 768px) {
    /* Pe telefon dock-ul e fix si mereu vizibil — ii lasam tot locul. */
    .page { --rezerva: calc(var(--dock-h) + var(--space-sm) + var(--safe-bottom));
            padding: var(--space-md); }
    .b { height: var(--tap-min); padding: 0 var(--space-14); font-size: var(--font-small); }
    /* Pe telefon actiunile trec sub titlu (antetul are deja `flex-wrap: wrap`) si
       isi iau latimea, ca sa ramana atins-abile la 44px. */
    .actiuni { width: 100%; }
    .actiuni :global(.b) { flex: 1; justify-content: center; }
    /* Campul primeste linkul de partajare — se lipeste, deci trebuie sa fie usor
       de atins si de golit; 32px inaltime cu font de 16px taia si textul. */
    .rand input { height: var(--tap-min); min-width: 0; font-size: var(--font-small); }
    .rand { gap: var(--space-xs); }
    .rand :global(.b) { flex: 1; justify-content: center; }
  }
</style>
