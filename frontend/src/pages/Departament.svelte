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
  import { onMount, onDestroy } from 'svelte'
  import { ExternalLink, Link2, Save, X } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { ui, toast } from '../stores/ui.svelte.js'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ErrorState from '../components/ui/ErrorState.svelte'

  let url = $state('')
  let host = $state('')
  let loading = $state(true)
  let error = $state(null)
  let editeaza = $state(false)
  let ciorna = $state('')
  let salvez = $state(false)

  async function load() {
    loading = true; error = null
    try {
      const d = await apiJson('/api/settings/plan-departament')
      url = d.url || ''
      host = d.host || ''
      editeaza = !url
      ciorna = url
    } catch (e) {
      error = e.message
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
      toast(url ? 'Link salvat' : 'Link șters', 'success')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      salvez = false
    }
  }

  onMount(() => {
    ui.pageHeader = { title: 'Departament', subtitle: 'Planul întregii echipe' }
    load()
  })
  onDestroy(() => { ui.pageHeader = { title: '', subtitle: '' } })
</script>

<div class="page">
  {#if loading}
    <Skeleton height="420px" />
  {:else if error}
    <ErrorState message={error} onretry={load} />
  {:else}
    <div class="bara">
      {#if url && !editeaza}
        <span class="sursa" title={host}>{host}</span>
        <span class="spatiu"></span>
        <a class="b" href={url} target="_blank" rel="noopener noreferrer">
          <ExternalLink size={13} /> Deschide în tab nou
        </a>
        <button class="b" onclick={() => { ciorna = url; editeaza = true }}>
          <Link2 size={13} /> Schimbă linkul
        </button>
      {/if}
    </div>

    {#if editeaza}
      <div class="config">
        <h2>Linkul planului de departament</h2>
        <p>
          Din aplicația de plan, ia linkul de partajare și lipește-l aici. Se acceptă
          doar adrese <code>https://{host}</code>.
        </p>
        <p class="atentie">
          Linkul conține cheia de acces la plan — cine îl are, intră. Se salvează în
          baza de date a Dashboard-ului, care nu ajunge în git.
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
  /* Pagina se incadreaza EXACT in fereastra: nu vrem scroll pe toata aplicatia,
     ci doar in interiorul planului.

     `.app-content` rezerva jos loc pentru dock (--dock-h + spatiu), pentru toate
     paginile. Aici il anulam cu o margine negativa si rezervam noi cat trebuie:
     pe DESKTOP dock-ul e ascuns si apare doar cand impingi cursorul in marginea
     de jos, deci 10px ajung; pe telefon e fix si vizibil, deci ii lasam tot locul.
     Asa planul castiga vreo 80px de inaltime pe desktop. */
  .page { --rezerva: 10px;
          padding: var(--space-md) var(--space-lg);
          display: flex; flex-direction: column;
          height: calc(100dvh - var(--header-height) - var(--rezerva));
          margin-bottom: calc(-1 * (var(--dock-h) + var(--space-lg) + var(--safe-bottom)));
          min-height: 380px; overflow: hidden; }

  .bara { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-sm); min-height: 28px; }
  .spatiu { flex: 1; }
  .sursa { font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text-faint); }

  .b { display: inline-flex; align-items: center; gap: 5px; height: 28px; padding: 0 10px;
       font-size: var(--font-tiny); border: 1px solid var(--border); background: var(--bg-surface);
       color: var(--text-secondary); border-radius: var(--radius-sm); cursor: pointer; }
  .b:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .b:disabled { opacity: 0.5; cursor: default; }
  .b.ok { color: var(--success); border-color: color-mix(in srgb, var(--success) 45%, transparent); }

  /* Fundal alb sub cadru: aplicatia lor e pe tema deschisa, iar pe fundalul
     nostru cald-inchis marginile ar aparea ca o rama murdara in timpul incarcarii. */
  iframe { flex: 1; width: 100%; border: 1px solid var(--border); border-radius: var(--radius-lg);
           background: #fff; min-height: 0; }

  .config { max-width: 640px; background: var(--bg-surface); border: 1px solid var(--border);
            border-radius: var(--radius-lg); padding: var(--space-lg); }
  .config h2 { font-family: var(--font-heading); font-size: 1.05rem; margin-bottom: var(--space-sm); }
  .config p { font-size: var(--font-small); color: var(--text-dim); margin-bottom: var(--space-sm); line-height: 1.5; }
  .config code { font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text-secondary); }
  .atentie { border-left: 3px solid var(--danger); padding-left: 10px; }

  .rand { display: flex; gap: var(--space-sm); flex-wrap: wrap; margin-top: var(--space-md); }
  .rand input { flex: 1; min-width: 260px; height: 32px; padding: 0 10px; font-family: var(--font-mono);
                font-size: var(--font-micro); color: var(--text); background: var(--bg-elevated);
                border: 1px solid var(--border); border-radius: var(--radius-sm); }
  .rand input:focus { outline: none; border-color: var(--accent); }

  @media (max-width: 768px) {
    /* Pe telefon dock-ul e fix si mereu vizibil — ii lasam tot locul. */
    .page { --rezerva: calc(var(--dock-h) + var(--space-sm) + var(--safe-bottom));
            padding: var(--space-md); }
    .b { height: var(--tap-min); padding: 0 14px; font-size: var(--font-small); }
    .bara { min-height: var(--tap-min); }
    /* Campul primeste linkul de partajare — se lipeste, deci trebuie sa fie usor
       de atins si de golit; 32px inaltime cu font de 16px taia si textul. */
    .rand input { height: var(--tap-min); min-width: 0; font-size: var(--font-small); }
    .rand { gap: var(--space-xs); }
    .rand :global(.b) { flex: 1; justify-content: center; }
  }
</style>
