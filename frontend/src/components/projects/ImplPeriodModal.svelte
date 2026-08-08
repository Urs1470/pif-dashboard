<script>
  import { untrack } from 'svelte'
  import { MapPin, Building2, Trash2, Wrench, Hammer, Link as IcoLink, MoveRight } from '@lucide/svelte'
  import { apiJson } from '../../lib/api.js'
  import { toast } from '../../stores/ui.svelte.js'
  import { addDays, diffDays, isWeekend, parseISO, shortDate, todayISO } from '../../lib/calendarDates.js'
  import { isoWeek } from '../../lib/planDates.js'
  import { cheieDeplasare, seAting, deplasareaCu, rezolvaCiocniri } from '../../lib/deplasari.js'
  import Modal from '../ui/Modal.svelte'
  import ConfirmDialog from '../ui/ConfirmDialog.svelte'
  import DatePicker from '../ui/DatePicker.svelte'
  import Input from '../ui/Input.svelte'

  // period === null -> create; otherwise edit that period. onsaved() reloads the caller.
  let { open = $bindable(false), projectId, period = null, onsaved = () => {} } = $props()

  let dStart = $state('')
  let dEnd = $state('')
  let loc = $state('site')
  // Faza e independenta de locatie: PIF-ul poate fi si la sediu, si in site,
  // uneori in doua etape. Deci doua comutatoare, nu unul.
  let faza = $state('implementare')
  let eticheta = $state('')
  let busy = $state(false)
  let confirmSterge = $state(false)

  // ===== CONTEXTUL DIN CARE SE CITESC REGULILE =====
  // Modalul nu poate raspunde la „ce se intampla daca salvez" doar cu perioadele
  // proiectului asta: vecinul care te impinge e, de obicei, al ALTUI proiect.
  // Deci se cere fereastra din `/api/calendar` (singura ruta care intoarce
  // perioade CU `client`, adica exact ce trebuie ca sa se poata calcula cheia
  // `loc|client`), plus proiectul, pentru clientul perioadei pe care o scrii.
  let proiect = $state(null)
  let vecini = $state([])
  let fereastra = $state(null)     // { start, end } — ce s-a incarcat deja
  let cerere = null                // ultima cerere in zbor, asteptata la salvare

  const ZILE_FEREASTRA = 200       // maximul acceptat de /api/calendar

  async function asiguraFereastra(s, f) {
    // Se reincarca DOAR cand intervalul iese din ce s-a adus deja. Altfel fiecare
    // schimbare de zi ar fi o cerere, iar limita e 60/minut per IP (vezi app.py).
    if (fereastra && s >= fereastra.start && f <= fereastra.end) return cerere
    const start = addDays(s, -60)
    const end = addDays(start, ZILE_FEREASTRA)
    cerere = (async () => {
      try {
        const [cal, pr] = await Promise.all([
          apiJson(`/api/calendar?start=${start}&zile=${ZILE_FEREASTRA}`),
          proiect ? Promise.resolve(proiect) : apiJson(`/api/proiecte/${projectId}`),
        ])
        proiect = pr
        vecini = (cal?.perioade || []).filter((q) => q.id !== period?.id)
        fereastra = { start, end }
      } catch (_) {
        // Fara context nu se pot spune regulile — caseta pur si simplu nu se
        // randeaza. Formularul ramane folosibil: mai bine salvezi fara preaviz
        // decat sa nu poti salva deloc.
        vecini = []
        fereastra = null
      }
    })()
    return cerere
  }

  // Seed the form each time it opens.
  $effect(() => {
    if (open) {
      dStart = period?.data_start || ''
      dEnd = period?.data_sfarsit || ''
      loc = period?.locatie || 'site'
      faza = period?.faza || 'implementare'
      eticheta = period?.eticheta || ''
    }
  })

  // `untrack`: altfel efectul ar depinde de `fereastra`/`vecini`, pe care tot el
  // le scrie, si s-ar re-rula o data degeaba dupa fiecare incarcare.
  $effect(() => {
    if (!open) return
    const s = dStart || todayISO()
    const f = dEnd || s
    untrack(() => asiguraFereastra(s, f))
  })

  // ===== CE SE INTAMPLA DACA SALVEZ =====
  // Regulile exista deja in date; ce lipsea era sa fie SPUSE inainte, nu aflate
  // dupa. Se recalculeaza la fiecare schimbare de interval si se scriu intr-o
  // caseta; cand nu e nimic in jur, caseta nu se randeaza deloc.
  const intervalOk = $derived(!!dStart && !!dEnd && dEnd >= dStart)

  const ciorna = $derived({
    id: period?.id ?? null,
    data_start: dStart,
    data_sfarsit: dEnd,
    locatie: loc,
    client: proiect?.client || '',
  })

  // Fara proiect nu se stie clientul, iar `cheieDeplasare` ar da `site|` — care
  // s-ar potrivi cu orice alta perioada fara client. O alipire inventata e mai
  // rea decat niciun preaviz.
  const gata = $derived(intervalOk && !!proiect)

  const alipite = $derived(gata
    ? vecini.filter((q) => cheieDeplasare(q) === cheieDeplasare(ciorna) && seAting(q, dStart, dEnd))
    : [])

  const iesire = $derived(alipite.length ? deplasareaCu(vecini, ciorna) : null)
  const zileIesire = $derived(iesire ? (diffDays(iesire.start, iesire.end) ?? 0) + 1 : 0)

  const impinse = $derived(gata ? rezolvaCiocniri(vecini, ciorna) : [])
  // Prima zi in care ciocnirea chiar se vede — se scrie in propozitie ca sa stii
  // DE CE se muta ceva, nu doar CA se muta.
  const ziCiocnire = $derived.by(() => {
    if (!impinse.length) return ''
    const p = impinse[0].p
    const a = p.data_start
    const b = p.data_sfarsit || a
    return a > dStart ? a : (dStart > b ? b : dStart)
  })

  function zileLucratoare(a, b) {
    if (!a || !b || b < a) return 0
    let n = 0
    const total = diffDays(a, b) ?? 0
    for (let i = 0; i <= total; i++) if (!isWeekend(addDays(a, i))) n++
    return n
  }
  const nLucratoare = $derived(intervalOk ? zileLucratoare(dStart, dEnd) : 0)
  const saptamana = $derived.by(() => {
    if (!intervalOk) return ''
    const a = isoWeek(parseISO(dStart))
    const b = isoWeek(parseISO(dEnd))
    return a === b ? `S${a}` : `S${a}–S${b}`
  })

  const numeVecin = (q) => (q.nume || q.eticheta || q.client || 'o altă lucrare')
  const intervalScurt = (q) => {
    const a = q.data_start
    const b = q.data_sfarsit || a
    return a === b ? shortDate(a) : `${shortDate(a)}–${shortDate(b)}`
  }

  async function save() {
    if (busy) return
    if (!dStart || !dEnd) { toast('Alege început și sfârșit', 'error'); return }
    if (dEnd < dStart) { toast('Sfârșitul e înainte de început', 'error'); return }
    busy = true
    const body = { data_start: dStart, data_sfarsit: dEnd, locatie: loc, faza, eticheta: eticheta.trim() }
    try {
      // Fereastra se asteapta INAINTE de scriere: daca cererea e inca in zbor,
      // `impinse` ar fi gol si vecinii s-ar suprapune in tacere — exact ce
      // caseta promite ca nu se intampla.
      await cerere
      const muta = rezolvaCiocniri(vecini, { ...ciorna, data_start: dStart, data_sfarsit: dEnd })
      if (period?.id) await apiJson(`/api/implementari/${period.id}`, { method: 'PUT', body })
      else await apiJson(`/api/proiecte/${projectId}/implementari`, { method: 'POST', body })
      // Vecinii impinsi se scriu DUPA perioada ceruta: daca a doua scriere pica,
      // ai cerut-o pe prima si ea a intrat, nu invers.
      for (const m of muta) {
        await apiJson(`/api/implementari/${m.p.id}`, {
          method: 'PUT', body: { data_start: m.data_start, data_sfarsit: m.data_sfarsit },
        })
      }
      open = false
      onsaved()
      if (muta.length) {
        toast(muta.length === 1
          ? `S-a mutat o perioadă pe ${shortDate(muta[0].data_start)}`
          : `S-au mutat ${muta.length} perioade`, 'info')
      }
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = false }
  }

  async function remove() {
    if (!period?.id) return
    busy = true
    try { await apiJson(`/api/implementari/${period.id}`, { method: 'DELETE' }); open = false; onsaved() }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = false }
  }
</script>

<Modal bind:open title={period ? 'Editează perioada' : 'Perioadă nouă'} size="sm">
  <div class="ip">
    <div class="ip-cap">
      <span class="ip-titlu">Perioadă de implementare</span>
      {#if proiect}<span class="ip-sub">{proiect.client ? `${proiect.client} · ` : ''}{proiect.nume}</span>{/if}
    </div>

    <div class="ip-grup">
      <span class="ip-h">Unde</span>
      <div class="ip-doua">
        <button class="ip-opt" class:on={loc === 'site'} onclick={() => loc = 'site'}><MapPin size={15} strokeWidth={1.5} />Site</button>
        <button class="ip-opt" class:on={loc === 'sediu'} onclick={() => loc = 'sediu'}><Building2 size={15} strokeWidth={1.5} />Sediu EGB</button>
      </div>
    </div>

    <div class="ip-grup ip-cand">
      <span class="ip-h">Când</span>
      <div class="ip-interval">
        <DatePicker bind:value={dStart} placeholder="început" />
        <span class="ip-sageata" aria-hidden="true">→</span>
        <DatePicker bind:value={dEnd} placeholder="sfârșit" />
      </div>
      <!-- Acelasi numar care apare si pe banda: cate zile de lucru sunt in
           interval, nu cate casute a acoperit. -->
      {#if intervalOk}
        <span class="ip-nota"><span class="ip-n">{nLucratoare}</span>&nbsp;{nLucratoare === 1 ? 'zi lucrătoare' : 'zile lucrătoare'} · {saptamana}</span>
      {/if}
    </div>

    <div class="ip-grup">
      <span class="ip-h">Ce lucrare</span>
      <Input bind:value={eticheta} placeholder="ex. Punere în funcțiune" />
    </div>

    <div class="ip-grup">
      <span class="ip-h">Ce fază</span>
      <div class="ip-doua">
        <button class="ip-opt" class:on={faza === 'pregatire'} onclick={() => faza = 'pregatire'}><Wrench size={15} strokeWidth={1.5} />Pregătire</button>
        <button class="ip-opt" class:on={faza === 'implementare'} onclick={() => faza = 'implementare'}><Hammer size={15} strokeWidth={1.5} />Implementare</button>
      </div>
    </div>

    <!-- REGULILE SE SPUN INAINTE DE SALVARE, NU CA EROARE DUPA.
         Doua cazuri care nu seamana deloc, deci doua case-te diferite ca ton:
         alipirea nu e conflict, e continuare (tenta de accent); ciocnirea e o
         mutare pe care o produci tu si trebuie s-o vezi (tenta de restant). -->
    {#if iesire && zileIesire}
      <div class="ip-casa ip-lipire">
        <IcoLink size={15} strokeWidth={1.5} />
        <span>
          {#if alipite.length === 1}
            Atinge perioada de pe <span class="ip-m">{intervalScurt(alipite[0])}</span>, la același loc și client.
          {:else}
            Atinge {alipite.length} perioade la același loc și client.
          {/if}
          Devine <strong>o ieșire de {zileIesire} {zileIesire === 1 ? 'zi' : 'zile'}</strong>; lucrările rămân separate.
        </span>
      </div>
    {/if}

    {#if impinse.length}
      <div class="ip-casa ip-impinge">
        <MoveRight size={15} strokeWidth={1.5} />
        <span>
          Peste <span class="ip-m">{shortDate(ziCiocnire)}</span> e o zi la {numeVecin(impinse[0].p)}.
          Nu poți fi în două locuri deodată, deci
          {#if impinse.length === 1}
            <strong>ea se mută pe {shortDate(impinse[0].data_start)}</strong>, prima zi lucrătoare liberă.
          {:else}
            <strong>se mută {impinse.length} perioade</strong>, fiecare la prima zi lucrătoare liberă.
          {/if}
        </span>
      </div>
    {/if}

    <button class="ip-salveaza" onclick={save} disabled={busy}>Salvează</button>

    {#if period?.id}
      <div class="ip-rar">
        <span class="ip-linie"></span>
        <button class="ip-sterge" onclick={() => confirmSterge = true} disabled={busy}>
          <Trash2 size={15} strokeWidth={1.5} />Șterge perioada
        </button>
      </div>
    {/if}
  </div>
</Modal>

<ConfirmDialog bind:open={confirmSterge}
               title={period ? `Ștergi perioada ${intervalScurt(period)}?` : 'Ștergi perioada?'}
               message="Dispare din Calendar și din Planificator. Nu se poate anula."
               confirmLabel="Șterge perioada" onconfirm={remove} />

<style>
  /* Antetul lui Modal RAMANE (X-ul e singura iesire de aici — desenul n-are
     „Renunță"), dar isi pierde titlul si linia: panoul isi scrie singur titlul,
     la 21/600, cu proiectul sub el. Doua titluri la doi centimetri distanta, cu
     doua greutati, se citesc ca doua lucruri. */
  :global(.modal:has(.ip) .modal-title) { display: none; }
  @media (min-width: 769px) {
    :global(.modal:has(.ip) .modal-header) { border-bottom: none; padding-bottom: 0; }
    :global(.modal:has(.ip) .modal-body) { padding-top: var(--space-12); }
  }

  .ip { display: flex; flex-direction: column; gap: var(--space-md); }

  .ip-cap { display: flex; flex-direction: column; gap: 3px; }
  .ip-titlu {
    font-size: var(--font-h2);
    font-weight: var(--fw-semibold);
    letter-spacing: var(--tracking-tight);
    line-height: var(--lh-tight);
    color: var(--text);
  }
  .ip-sub { font-size: var(--font-small); color: var(--text-dim); }

  .ip-grup { display: flex; flex-direction: column; gap: 7px; }
  .ip-h {
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    color: var(--text-dim);
  }

  /* DOUA BUTOANE EGALE, nu un selector: sunt doua, se vad amandoua, iar alegerea
     se face dintr-o atingere. Alesul poarta tenta + muchie de 1,5px + cerneala
     ADANCA — text pe tenta nu ia niciodata culoarea plina. */
  .ip-doua { display: flex; gap: 6px; }
  .ip-opt {
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    height: var(--tap-min);
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    color: var(--text-secondary);
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .ip-opt:hover { color: var(--text); }
  .ip-opt:active { transform: scale(var(--press-scale)); }
  .ip-opt.on {
    background: var(--accent-subtle);
    box-shadow: inset 0 0 0 1.5px var(--accent);
    color: var(--accent-deep);
  }

  /* Cele doua capete si sageata dintre ele sunt UN singur camp cu doua valori,
     nu doua campuri cu doua etichete: intervalul se citeste dintr-o privire. */
  .ip-interval { display: flex; align-items: center; gap: var(--space-sm); }
  .ip-interval :global(.dp) { flex: 1; min-width: 0; }
  .ip-sageata { flex: none; color: var(--text-dim); font-size: var(--font-body); }
  /* Datele sunt cifre care se compara pe verticala -> mono. */
  .ip-cand :global(.dp-trigger) { font-family: var(--font-mono); }

  .ip-nota { font-size: var(--font-small); color: var(--text-dim); }
  .ip-n { font-family: var(--font-mono); color: var(--text-secondary); }

  .ip-casa {
    display: flex;
    gap: 9px;
    padding: 11px 13px;
    border-radius: var(--radius-sm);
    font-size: var(--font-small);
    line-height: var(--lh-snug);
    text-wrap: pretty;
  }
  .ip-casa :global(svg) { flex: none; margin-top: 2px; }
  .ip-casa strong { font-weight: var(--fw-semibold); }
  .ip-m { font-family: var(--font-mono); }
  .ip-lipire { background: var(--accent-subtle); color: var(--accent-deep); }
  .ip-impinge { background: var(--danger-subtle); color: var(--danger-deep); }

  .ip-salveaza {
    display: flex;
    align-items: center;
    justify-content: center;
    height: var(--tap-min);
    border-radius: var(--radius-sm);
    background: var(--accent);
    color: var(--accent-text);
    font-size: var(--font-body);
    font-weight: var(--fw-semibold);
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .ip-salveaza:hover:not(:disabled) { background: var(--accent-deep); }
  .ip-salveaza:active:not(:disabled) { transform: scale(var(--press-scale)); }
  .ip-salveaza:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Stergerea sta sub o linie, ca orice actiune rara: text + iconita, cerneala
     adanca de restant, fara fill. Un buton plin rosu langa „Salvează" ar fi doua
     actiuni la fel de tari pentru doua lucruri de importanta foarte diferita. */
  .ip-rar { display: flex; flex-direction: column; gap: 10px; }
  .ip-linie { height: 1px; background: var(--border); }
  .ip-sterge {
    display: inline-flex;
    align-items: center;
    align-self: flex-start;
    gap: 7px;
    height: 38px;
    color: var(--danger-deep);
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .ip-sterge:disabled { opacity: 0.5; cursor: not-allowed; }

  @media (max-width: 768px) {
    /* In foaie randurile si butoanele urca la 48: degetul are alt prag decat
       cursorul, iar aici se apasa cu telefonul in mana, pe teren. */
    .ip-opt, .ip-salveaza { height: var(--tap-sheet); }
    .ip-cand :global(.dp-trigger) { min-height: var(--tap-sheet); }
    .ip-sterge { height: var(--tap-min); }
  }
</style>
