<script>
  // Linia de context de pe Acasa: „când ies data viitoare și unde".
  //
  // O LINIE, nu un card — pagina e pentru boardul de azi, iar asta n-are voie
  // s-o împingă în jos. Tot ce încape fără să devină aglomerat:
  //   stânga  — cât de curând (accent), unde, ce lucrare
  //   mijloc  — următoarele două ieșiri, discret, ca să vezi săptămâna
  //   dreapta — perioade trecute cu proiectul neînchis, doar dacă există
  //
  // Datele vin din /api/calendar, care le calculează deja pentru Calendar.
  import { onMount } from 'svelte'
  import { MapPin, Building2, AlertTriangle, ChevronRight } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { navigate } from '../lib/router.svelte.js'
  import { todayISO, addDays, diffDays, shortDate } from '../lib/calendarDates.js'

  let data = $state(null)
  const azi = todayISO()

  onMount(async () => {
    try {
      data = await apiJson(`/api/calendar?start=${azi}&zile=120`)
    } catch (_) { data = null }
  })

  function scurt(client) {
    const c = (client || '').trim()
    return c ? c.split(/\s+/)[0].replace(/[.,]$/, '') : 'Teren'
  }

  // Grupam pe (loc, client) si pe zile consecutive: trei lucrari intr-o zi la
  // acelasi client sunt O iesire, nu trei. Aceeasi regula ca in Calendar.
  const iesiri = $derived.by(() => {
    const per = (data?.perioade || [])
      // Un proiect finalizat nu mai e o ieșire care urmează. Backendul îi taie
      // deja perioada la ziua închiderii (v35), deci fără filtrul ăsta o zi
      // tăiată ar apărea aici ca „Acum".
      .filter(p => p.status !== 'finalizat')
      .filter(p => (p.data_sfarsit || p.data_start) >= azi)
      .sort((a, b) => a.data_start.localeCompare(b.data_start))
    const out = []
    for (const p of per) {
      const cheie = `${p.locatie === 'sediu' ? 'sediu' : 'site'}|${(p.client || '').trim().toLowerCase()}`
      const ultim = out[out.length - 1]
      if (ultim && ultim.cheie === cheie && diffDays(ultim.end, p.data_start) <= 1) {
        if ((p.data_sfarsit || p.data_start) > ultim.end) ultim.end = p.data_sfarsit || p.data_start
        ultim.lucrari.push(p)
      } else {
        out.push({
          cheie, client: (p.client || '').trim(), sediu: p.locatie === 'sediu',
          start: p.data_start, end: p.data_sfarsit || p.data_start, lucrari: [p],
        })
      }
    }
    return out
  })

  const acum = $derived(iesiri[0] || null)
  const apoi = $derived(iesiri.slice(1, 3))
  const deClarificat = $derived((data?.de_decis || []).length)
  const faraPerioada = $derived((data?.neplanificate || []).length)

  function cand(d) {
    const k = diffDays(azi, d.start)
    if (k <= 0) return d.end >= azi ? 'Acum' : 'Azi'
    if (k === 1) return 'Mâine'
    if (k <= 6) return `În ${k} zile`
    return shortDate(d.start)
  }
  function lucrarile(d) {
    return d.lucrari.map(p => (p.eticheta || p.nume || '').trim()).filter(Boolean).join(' · ')
  }
  function interval(d) {
    return d.start === d.end ? shortDate(d.start)
      : `${shortDate(d.start)}–${shortDate(d.end)}`
  }
  /** In „apoi", clientul apare DOAR daca difera de ieșirea curenta. Aproape tot
   *  e la acelasi client, deci repetat ar fi zgomot, nu informatie. */
  function undeApoi(d) {
    if (d.sediu) return 'sediu'
    return d.cheie === acum?.cheie ? '' : scurt(d.client)
  }
</script>

{#if data}
  <div class="ctx">
    {#if acum}
      <button class="pr" style="--c: {acum.sediu ? 'var(--purple)' : 'var(--accent)'}"
              onclick={() => navigate(`/calendar?zi=${acum.start}`)}
              title="Vezi în Calendar">
        <span class="ico">
          {#if acum.sediu}<Building2 size={14} />{:else}<MapPin size={14} />{/if}
        </span>
        <span class="cand">{cand(acum)}</span>
        <span class="unde">{acum.sediu ? 'Sediu' : scurt(acum.client)}</span>
        <span class="sep">·</span>
        <span class="ce">{lucrarile(acum) || 'fără etichetă'}</span>
        <span class="zile">{interval(acum)}</span>
      </button>

      {#if apoi.length}
        <span class="apoi">
          apoi
          {#each apoi as d, i (d.start + d.cheie)}{#if i}<span class="pt">·</span>{/if}<span class="ap">{interval(d)}</span>{#if undeApoi(d)}<span class="apc">{undeApoi(d)}</span>{/if}{/each}
        </span>
      {/if}
    {:else}
      <span class="gol">
        <MapPin size={14} /> Nicio ieșire planificată
        {#if faraPerioada}<span class="sep">·</span>{faraPerioada} {faraPerioada === 1 ? 'proiect' : 'proiecte'} fără perioadă{/if}
      </span>
    {/if}

    <span class="spatiu"></span>

    {#if deClarificat}
      <button class="dec" onclick={() => navigate('/calendar')}
              title="Perioade trecute, cu proiectul neînchis">
        <AlertTriangle size={13} /> {deClarificat} de clarificat <ChevronRight size={13} />
      </button>
    {/if}
  </div>
{/if}

<style>
  .ctx {
    display: flex; align-items: center; gap: var(--space-md);
    padding: 0 2px var(--space-md); flex-wrap: wrap;
  }
  .spatiu { flex: 1; }

  /* Ieșirea următoare — singurul lucru cu greutate vizuală din linie. */
  .pr {
    display: inline-flex; align-items: baseline; gap: 8px; min-width: 0;
    padding: 5px 12px 5px 10px; border-radius: var(--radius-full);
    border: 1px solid var(--border); background: var(--bg-surface);
    border-left: 3px solid var(--c); cursor: pointer; text-align: left;
    transition: border-color var(--dur-fast) var(--ease);
  }
  .pr:hover { border-color: var(--c); }
  .ico { color: var(--c); align-self: center; display: inline-flex; }
  .cand { font-family: var(--font-heading); font-weight: var(--fw-semibold);
          font-size: var(--font-small); color: var(--c); white-space: nowrap; }
  .unde { font-size: var(--font-small); color: var(--text); white-space: nowrap; }
  .sep { color: var(--text-faint); }
  .ce { font-size: var(--font-tiny); color: var(--text-dim); min-width: 0;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 34ch; }
  .zile { font-family: var(--font-mono); font-size: var(--font-micro); color: var(--text-faint);
          white-space: nowrap; }

  /* Următoarele două — text simplu, fără cadru: context, nu obiect. */
  .apoi { font-size: var(--font-micro); color: var(--text-faint); white-space: nowrap; }
  .ap { font-family: var(--font-mono); }
  /* Spatiul dintre interval si loc vine din CSS, nu dintr-un caracter scris in
     markup: acolo era `<span class="apc"> {…}</span>`, iar spatiul de dinaintea
     expresiei se pierdea la compilare — pe ecran scria „31 iulsediu". */
  .apc { color: var(--text-dim); margin-left: 5px; }
  .pt { margin: 0 5px; }

  .gol { display: inline-flex; align-items: center; gap: 7px;
         font-size: var(--font-tiny); color: var(--text-dim); }

  .dec {
    display: inline-flex; align-items: center; gap: 5px; white-space: nowrap;
    font-size: var(--font-micro); padding: 4px 8px 4px 10px; border-radius: var(--radius-full);
    border: 1px solid color-mix(in srgb, var(--danger) 35%, transparent);
    background: var(--danger-subtle); color: var(--danger); cursor: pointer;
  }
  .dec:hover { border-color: var(--danger); }

  @media (max-width: 760px) {
    .ctx { gap: var(--space-sm); }
    /* Pe telefon rămâne doar ieșirea următoare — restul e context de desktop. */
    .apoi { display: none; }

    /* Prima linie a ecranului „Acasă" e si prima tinta. Era o pastila de 34px
       inalta si intinsa pe toata latimea — destul de lata cat s-o vezi, prea joasa
       cat s-o atingi. Trece pe doua randuri (cand+unde sus, lucrarea si intervalul
       dedesubt): incape numele intreg al lucrarii, care la 20ch se taia mereu. */
    .pr {
      display: grid;
      grid-template-columns: auto auto minmax(0, 1fr) auto;
      align-items: center;
      row-gap: 2px; column-gap: 7px;
      width: 100%; min-height: var(--tap-min);
      padding: 8px 12px 8px 10px;
      border-radius: var(--radius-md);
    }
    .sep { display: none; }
    /* Pozitiile sunt EXPLICITE, nu lasate pe seama ordinii din DOM: `.ce` vine
       inaintea lui `.zile` in markup, deci auto-plasarea umplea randul 2 cu
       eticheta si impingea intervalul pe un al treilea rand.
       Sus: cand · unde ... interval. Jos: ce lucrare, pe toata latimea — la 20ch
       eticheta se taia mereu, iar exact ea spune ce faci acolo. */
    .ico  { grid-area: 1 / 1; }
    .cand { grid-area: 1 / 2; }
    .unde { grid-area: 1 / 3; justify-self: start; overflow: hidden; text-overflow: ellipsis; }
    .zile { grid-area: 1 / 4; justify-self: end; }
    .ce {
      grid-area: 2 / 1 / 3 / -1;
      max-width: none; white-space: normal;
      display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical;
    }

    .dec { min-height: var(--tap-min); padding: 4px 12px; font-size: var(--font-tiny); }
    .gol { min-height: var(--tap-min); }
  }
</style>
