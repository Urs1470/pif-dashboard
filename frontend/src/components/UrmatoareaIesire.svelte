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
  import { MapPin, Building2, AlertTriangle, ChevronRight, CalendarX2 } from '@lucide/svelte'
  import { apiJson } from '../lib/api.js'
  import { navigate } from '../lib/router.svelte.js'
  import { todayISO, addDays, diffDays, shortDate } from '../lib/calendarDates.js'

  let data = $state(null)
  // EROAREA NU E ACELASI LUCRU CU „NIMIC PLANIFICAT". Inainte, orice esec de
  // retea lasa `data = null` si componenta disparea FARA NICIUN SEMN — adica
  // exact lectia scrisa la v29 in CLAUDE.md: o absenta tacuta te invata sa nu
  // te bazezi pe restul. Linia ramane pe ecran si spune ca nu stie, cu drum
  // de reincercare.
  let eroare = $state(false)
  const azi = todayISO()

  async function incarca() {
    eroare = false
    try {
      data = await apiJson(`/api/calendar?start=${azi}&zile=120`)
    } catch (_) { data = null; eroare = true }
  }
  onMount(incarca)

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

  // `de_decis` vine sortat dupa `data_start`, deci prima e cea mai veche. Chipul
  // nu mai duce in Calendar „undeva", ci exact pe ziua ei — de aceea scrie „1 / N":
  // spune si cate au ramas, si pe a cata te duce. Un contor care spune doar „3"
  // te lasa sa le cauti singur prin luni.
  const primaDeClarificat = $derived((data?.de_decis || [])[0]?.data_start || '')

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
      <!-- LOCATIA ISI FOLOSESTE TOKENUL. Aici scria `--purple` pentru sediu si
           `--accent` pentru teren — adica un fapt binar imprumuta cerneala
           IDENTITATII aplicatiei, si inca violetul pe care tura 1 tocmai il
           scosese de pe antetul „Personal". Comentariul din tokens.css spune de
           ce exista perechea: „erau opt valori scrise de mana in patru fisiere,
           cu TREI ambere diferite pentru acelasi «sediu»". Linia asta era al
           cincilea fisier. Acum e aceeasi pereche ca in Calendar si Planificator. -->
      <!-- LOCUL SE SCRIE, NU SE COLOREAZA (redesign 2026-08-08). Perechea
           `--loc-site`/`--loc-sediu` era a doua axa cromatica de pe linie, langa
           accent — iar diferenta „teren vs sediu" e deja spusa de iconita si de
           cuvantul de langa ea. Ce ramane colorat e CAND, fiindca doar asta
           decide daca te uiti mai departe. -->
      <button class="pr"
              onclick={() => navigate(`/calendar?zi=${acum.start}`)}
              title="Vezi în Calendar">
        <span class="ico">
          {#if acum.sediu}<Building2 size={15} />{:else}<MapPin size={15} />{/if}
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
      </span>
    {/if}

    <span class="spatiu"></span>

    <!-- Cele doua contoare stau impreuna, in capatul din dreapta, si se deosebesc
         prin TON: rosu pentru ce e gresit acum, neutru pentru ce lipseste.
         „Fara perioada" aparea doar in ramura goala — adica exact cand n-aveai
         nimic de facut. Dar un proiect fara nicio zi planificata e o scapare mai
         ales cand ai altele in derulare: atunci se pierde, nu cand ecranul e gol. -->
    {#if faraPerioada}
      <button class="ct-nr" onclick={() => navigate('/calendar')}
              title="{faraPerioada} {faraPerioada === 1 ? 'proiect activ fără nicio zi planificată' : 'proiecte active fără nicio zi planificată'}">
        <CalendarX2 size={13} /> <span class="ct-n">{faraPerioada}</span> fără perioadă
      </button>
    {/if}

    {#if deClarificat}
      <button class="ct-nr rau" onclick={() => navigate(`/calendar?zi=${primaDeClarificat}`)}
              title="Perioade trecute, cu proiectul neînchis — te duce la cea mai veche">
        <AlertTriangle size={13} /> <span class="ct-n">1 / {deClarificat}</span> de clarificat <ChevronRight size={13} />
      </button>
    {/if}
  </div>
{:else if eroare}
  <div class="ctx">
    <span class="gol eroare">
      <AlertTriangle size={14} /> Ieșirile nu s-au putut încărca
    </span>
    <button class="reinc" onclick={incarca}>Reîncearcă</button>
  </div>
{:else}
  <!-- LINIA ISI TINE LOCUL CAT TIMP SE INCARCA. Pana raspundea API-ul componenta
       nu randa NIMIC, deci boardul „Astazi" statea lipit de bara si sarea in jos
       cu ~46px in clipa in care sosea raspunsul — fix cand incepeai sa citesti
       primul task, si fix pe ecranul cu care incepi ziua. Nu e un schelet cu
       continut fals: e aceeasi caseta, goala, ca sa nu se miste nimic sub ochi. -->
  <div class="ctx" aria-hidden="true">
    <span class="pr fantoma"></span>
  </div>
{/if}

<style>
  .ctx {
    display: flex; align-items: center; gap: var(--space-md);
    padding: 0 2px var(--space-md); flex-wrap: wrap;
  }
  .spatiu { flex: 1; }

  /* Ieșirea următoare — singurul lucru cu greutate vizuală din linie. */
  /* Haina din desen (3a): pastila de 36, padding 0 14, gap 9, iconita pe accent. */
  .pr {
    display: inline-flex; align-items: center; gap: 9px; min-width: 0;
    min-height: 36px; padding: 0 14px; border-radius: var(--radius-sm);
    background: var(--bg-surface); box-shadow: var(--shadow-sm);
    cursor: pointer; text-align: left;
    transition: var(--transition-pressable);
  }
  .pr:hover { background: var(--bg-hover); }
  .pr:active { transform: scale(var(--press-scale)); }
  .ico { color: var(--accent); align-self: center; display: inline-flex; }
  /* Fara Space Grotesk: „În 3 zile" e o propozitie scurta, nu numele unui lucru,
     iar fontul de titlu nu coboara sub 17px — aici e la 13. */
  .cand { font-weight: var(--fw-semibold);
          font-size: var(--font-small); color: var(--accent-deep); white-space: nowrap; }
  .unde { font-size: var(--font-small); color: var(--text); white-space: nowrap; }
  .sep { color: var(--text-faint); }
  .ce { font-size: var(--font-small); color: var(--text-secondary); min-width: 0;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 34ch; }
  /* dim, nu faint: intervalul e raspunsul la „cand pleci" — informatie, nu
     eticheta; masurat 3.18:1 la 10.4px, sub AA. Mono 12, ca in desen. */
  .zile { font-family: var(--font-mono); font-size: var(--font-label); color: var(--text-dim);
          white-space: nowrap; letter-spacing: var(--tracking-normal); }

  /* Următoarele două — text simplu, fără cadru: context, nu obiect. */
  .apoi { font-size: var(--font-small); color: var(--text-faint); white-space: nowrap; }
  /* Intervalul e informatie (dim); cuvantul de legatura „apoi" ramane faint. */
  .ap { font-family: var(--font-mono); color: var(--text-dim); }
  /* Spatiul dintre interval si loc vine din CSS, nu dintr-un caracter scris in
     markup: acolo era `<span class="apc"> {…}</span>`, iar spatiul de dinaintea
     expresiei se pierdea la compilare — pe ecran scria „31 iulsediu". */
  .apc { color: var(--text-dim); margin-left: 5px; }
  .pt { margin: 0 5px; }

  .gol { display: inline-flex; align-items: center; gap: 7px;
         font-size: var(--font-small); color: var(--text-dim); }
  /* Eroarea foloseste limbajul semantic, nu pe cel de „gol": danger pe semn,
     ca sa nu se citeasca drept o zi libera. */
  .gol.eroare :global(svg) { color: var(--danger); }
  .reinc { padding: 3px 12px; border-radius: var(--radius-xs);
    border: 1px solid var(--border); background: var(--bg-surface);
    color: var(--text-secondary); font-size: var(--font-small);
    font-weight: var(--fw-medium); cursor: pointer;
    transition: var(--transition-colors); min-height: 26px; }
  .reinc:hover { border-color: var(--accent); color: var(--accent); }

  /* Doua contoare, aceeasi haina, tonul e singura diferenta: neutru = ce
     lipseste, rosu = ce e gresit acum. Cifra e mono si tabulara — se compara de
     la o zi la alta. */
  .ct-nr {
    display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;
    font-size: var(--font-small); padding: 4px 8px 4px 10px; border-radius: var(--radius-xs);
    background: var(--bg-surface); box-shadow: var(--shadow-sm);
    color: var(--text-dim); cursor: pointer;
    transition: var(--transition-pressable);
  }
  .ct-nr:hover { background: var(--bg-hover); color: var(--text-secondary); }
  .ct-nr:active { transform: scale(var(--press-scale)); }
  .ct-n { font-family: var(--font-mono); font-variant-numeric: tabular-nums; color: var(--text-secondary); }

  /* Tenta de restant poarta cerneala ADANCA, niciodata culoarea plina. */
  .ct-nr.rau { background: var(--danger-subtle); color: var(--danger-deep); box-shadow: none; }
  .ct-nr.rau:hover { background: color-mix(in oklab, var(--danger) 22%, var(--bg-surface)); }
  .ct-nr.rau .ct-n { color: var(--danger-deep); }

  /* Casuta care tine locul liniei cat timp se incarca — aceeasi inaltime, fara
     chenar si fara puls: nu anunta continut, doar nu lasa pagina sa sara. */
  .pr.fantoma {
    background: transparent; box-shadow: none; min-height: 30px; width: 220px;
    pointer-events: none;
  }

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
      border-radius: var(--radius-sm);
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

    /* Amandoua contoarele la 44px, pe acelasi rand — sunt tinte, nu etichete. */
    .ct-nr { min-height: var(--tap-min); padding: 4px 12px; }
    .gol { min-height: var(--tap-min); }
    .pr.fantoma { min-height: var(--tap-min); width: 100%; }
  }
</style>
