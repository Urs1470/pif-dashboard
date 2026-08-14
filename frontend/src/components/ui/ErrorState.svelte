<script>
  import { TriangleAlert, RotateCcw } from '@lucide/svelte'

  // DOUA MARIMI, fiindca sunt doua situatii diferite.
  //
  // `pagina` (implicit): tot ecranul n-a venit. Patrat cu iconita in tenta de
  // restant, o propozitie, UN drum inapoi, plus ora ultimei incarcari reusite —
  // fara ea nu stii daca te uiti la ceva vechi de un minut sau de o ora.
  //
  // `sectiune`: o bucata a picat, restul paginii e in regula. O SECTIUNE CAZUTA
  // NU GOLESTE PAGINA — deci aici starea e o linie, nu un ecran gol de 200px
  // care impinge in jos continutul care chiar a sosit.
  let {
    title = 'Ceva n-a mers',
    message = '',
    onretry = undefined,
    marime = 'pagina',
    /** ISO sau text: cand a fost ultima incarcare reusita. */
    ultima = '',
    children,
  } = $props()

  // CE SCRIE BROWSERUL NU E CE CITESTE OMUL.
  // Cand pica reteaua, `fetch` respinge cu un mesaj propriu, in engleza si
  // diferit de la un browser la altul: „Failed to fetch" (Chrome), „Load failed"
  // (Safari), „NetworkError when attempting to fetch resource." (Firefox). El
  // ajungea ca atare sub „Ceva n-a mers" — singurul sir netradus ramas la vedere
  // in aplicatie, si tocmai in ecranul in care omul e deja contrariat.
  // Se traduce AICI, nu la fiecare apelant: toate cele cinci pagini trec pe aici.
  const RETEA = /failed to fetch|load failed|networkerror|network request failed|err_internet_disconnected/i
  const mesajRo = (m) => {
    const s = (m || '').toString().trim()
    if (!s) return ''
    if (RETEA.test(s)) return 'Pare că nu e rețea. Verifică semnalul și încearcă din nou.'
    if (/^unauthorized$/i.test(s)) return 'Sesiunea a expirat. Intră din nou cu PIN-ul.'
    return s
  }
  const mesaj = $derived(mesajRo(message))

  function ora(v) {
    if (!v) return ''
    const d = v instanceof Date ? v : new Date(v)
    if (Number.isNaN(d.getTime())) return String(v)
    return d.toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit' })
  }
</script>

{#if marime === 'sectiune'}
  <div class="er-linie" role="alert">
    <span class="er-ico-mic"><TriangleAlert size={16} strokeWidth={1.5} /></span>
    <span class="er-text">
      {mesaj || title}
      {#if ultima}<span class="er-vechi">informația de mai jos e de la {ora(ultima)}</span>{/if}
    </span>
    {#if onretry}
      <button class="er-btn" onclick={onretry}><RotateCcw size={14} strokeWidth={1.5} /> Reîncearcă</button>
    {/if}
  </div>
{:else}
  <div class="er" role="alert">
    <!-- Patrat in TENTA de restant, cu cerneala adanca — nu iconita rosie plina
         pe fond gol. Tenta spune „aici e o problema" fara sa tipe, si e acelasi
         obiect ca patratul neutru al starii goale, doar cu alt rol. -->
    <span class="er-patrat"><TriangleAlert size={22} strokeWidth={1.5} /></span>
    <h3>{title}</h3>
    {#if mesaj}<p>{mesaj}</p>{/if}
    {#if onretry || children}
      <div class="er-actiuni">
        {#if onretry}
          <button class="er-btn" onclick={onretry}><RotateCcw size={14} strokeWidth={1.5} /> Reîncearcă</button>
        {/if}
        {#if children}{@render children()}{/if}
      </div>
    {/if}
    {#if ultima}<p class="er-vechi">Ultima încărcare reușită: {ora(ultima)}</p>{/if}
  </div>
{/if}

<style>
  .er {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-2xl) var(--space-lg);
    color: var(--text-dim);
    text-align: center;
  }
  .er-patrat {
    display: grid;
    place-items: center;
    width: 48px;
    height: 48px;
    border-radius: var(--radius-md);
    background: var(--danger-subtle);
    color: var(--danger-deep);
    margin-bottom: var(--space-xs);
  }
  h3 {
    font-size: var(--font-body);
    font-weight: var(--fw-semibold);
    color: var(--text);
  }
  p {
    font-size: var(--font-small);
    max-width: 360px;
    color: var(--text-dim);
  }
  .er-actiuni {
    margin-top: var(--space-sm);
    display: flex;
    gap: var(--space-sm);
  }
  .er-vechi { font-size: var(--font-small); color: var(--text-dim); }

  /* ---- o sectiune cazuta: o linie, nu un ecran ---- */
  .er-linie {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    padding: 0 var(--space-12);
    border-radius: var(--radius-sm);
    background: var(--danger-subtle);
    color: var(--danger-deep);
    font-size: var(--font-small);
  }
  .er-ico-mic { display: inline-flex; flex: none; }
  .er-text { flex: 1; min-width: 0; display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: baseline; }
  .er-vechi { color: var(--text-dim); }
  .er-linie .er-vechi { color: inherit; opacity: 0.85; }

  .er-btn {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 12px;
    border: none;
    border-radius: var(--radius-xs);
    background: var(--bg-surface);
    box-shadow: var(--shadow-sm);
    color: var(--text-secondary);
    font-family: inherit;
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .er-btn:hover { background: var(--bg-hover); color: var(--text); }
  .er-btn:active { transform: scale(var(--press-scale)); }

  @media (max-width: 768px) {
    .er-btn { height: var(--tap-min); padding: 0 14px; }
    .er-linie { min-height: 56px; padding: 8px var(--space-12); }
  }
</style>
