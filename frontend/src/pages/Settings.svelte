<script>
  import { Bell, BellRing, Info, AlarmClockOff, ExternalLink } from '@lucide/svelte'
  import { suportaPush, esteIosNeinstalat, stareAbonament, aboneaza, dezaboneaza } from '../lib/push.js'
  import { esteNativ, probeaza, reprogrameaza, alarmaExacta, deschideAlarmaExacta } from '../lib/notificari.js'
  import { apiJson } from '../lib/api.js'
  import { todayISO } from '../lib/calendarDates.js'
  import { toast } from '../stores/ui.svelte.js'
  import Button from '../components/ui/Button.svelte'
  import Input from '../components/ui/Input.svelte'
  import Select from '../components/ui/Select.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'

  let pushStatus = $state(null)
  let pushLocal = $state(null)
  let pushBusy = $state(false)
  let setari = $state(null)
  let setariEroare = $state('')
  let exacta = $state(null)

  const oreDisponibile = Array.from({ length: 24 }, (_, h) => ({
    value: h, label: `${String(h).padStart(2, '0')}:00`,
  }))

  const arataSetari = $derived(
    esteNativ() || (pushStatus?.disponibil && (pushLocal?.abonat || pushStatus?.abonamente > 0))
  )

  $effect(() => {
    if (pushStatus === null) {
      reincarcaPush().catch(() => {})
      apiJson('/api/push/setari').then((s) => { setari = s }).catch(() => {})
      alarmaExacta().then((v) => { exacta = v }).catch(() => {})
    }
  })

  async function reincarcaPush() {
    const [server, local] = await Promise.all([
      apiJson('/api/push/status'),
      suportaPush() ? stareAbonament() : Promise.resolve({ permisiune: 'unsupported', abonat: false }),
    ])
    pushStatus = server
    pushLocal = local
  }

  async function pornesteAlarma() {
    try {
      await deschideAlarmaExacta()
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function activeazaPush() {
    if (pushBusy) return
    pushBusy = true
    try {
      await aboneaza()
      await reincarcaPush()
      toast('Notificări activate pe dispozitivul ăsta.', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { pushBusy = false }
  }

  async function dezactiveazaPush() {
    if (pushBusy) return
    pushBusy = true
    try {
      await dezaboneaza()
      await reincarcaPush()
      toast('Notificări dezactivate pe dispozitivul ăsta.', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { pushBusy = false }
  }

  async function testPush() {
    if (pushBusy) return
    pushBusy = true
    try {
      const r = await apiJson('/api/push/test', { method: 'POST', body: {} })
      await reincarcaPush()
      toast(r.esuate ? (r.motiv || `Eșuate: ${r.esuate}`) : 'Notificare de test trimisă.',
            r.esuate ? 'error' : 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
    finally { pushBusy = false }
  }

  async function probaLocala() {
    if (pushBusy) return
    pushBusy = true
    try {
      toast(await probeaza(), 'success')
    } catch (e) { toast(e.message, 'error') }
    finally { pushBusy = false }
  }

  async function salveazaSetari() {
    if (pushBusy || !setari) return
    pushBusy = true
    setariEroare = ''
    try {
      const { programate, ...salvate } = await apiJson('/api/push/setari', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ora: Number(setari.ora), zileVechime: Number(setari.zileVechime),
          scadente: !!setari.scadente, faraTermen: !!setari.faraTermen,
          oreExacte: !!setari.oreExacte,
          deplasari: !!setari.deplasari, oraDeplasare: Number(setari.oraDeplasare),
        }),
      })
      setari = salvate
      let cate = programate ?? 0
      if (esteNativ()) {
        const [d, cal] = await Promise.all([
          apiJson('/api/global-tasks?sfera=personal'),
          apiJson(`/api/calendar?start=${todayISO()}&zile=60`).catch(() => null),
        ])
        cate = await reprogrameaza(Array.isArray(d) ? d : d.tasks || [], salvate,
                                   cal?.perioade || [])
      }
      await reincarcaPush()
      toast(`Salvat — ${cate} ${cate === 1 ? 'notificare programată' : 'notificări programate'}.`, 'success')
    } catch (e) {
      setariEroare = e.message
    } finally { pushBusy = false }
  }
</script>

<div class="page ruta-in">
  <div class="page-header">
    <h1>Setări</h1>
  </div>

  <section class="n-sectiune">
    <h2 class="n-titlu"><Bell size={18} strokeWidth={1.5} /> Notificări zilnice</h2>

    {#if esteNativ()}
      <p class="n-text">O notificare <strong>per task</strong>, nu un rezumat, cu „Făcut" și „Azi" pe
        ea. Aici alarma o pune telefonul, din timp — nu vine de pe server, deci nu depinde nici
        de rețea, nici de starea aplicației în momentul în care sună.</p>
    {:else if pushStatus === null}
      <div class="n-skel"><Skeleton width="80%" height="14px" /><Skeleton width="60%" height="14px" /></div>
    {:else if !pushStatus.disponibil}
      <p class="n-text">Notificările nu sunt disponibile pe server (lipsește pachetul
        <span class="n-mono">pywebpush</span>). Verifică logurile de deploy.</p>
    {:else if !suportaPush()}
      <p class="n-text">
        {#if esteIosNeinstalat()}
          Pe iPhone notificările merg doar din aplicația instalată: Distribuie →
          „Adaugă la ecranul principal", deschide-o de acolo și revino aici.
        {:else}
          Browserul ăsta nu suportă notificări push.
        {/if}
      </p>
    {:else if pushLocal?.permisiune === 'denied'}
      <p class="n-text">Notificările sunt blocate pentru site. Deblochează-le din setările
        browserului (lacătul din bara de adresă → Notificări) și revino aici.</p>
    {:else if !pushLocal?.abonat}
      <p class="n-text">Un task personal care stă fără termen mai mult de {'2'} zile îți trimite
        dimineața, la {pushStatus.ora}, o notificare proprie — cu titlul lui și cu butoanele
        „Făcut" și „Azi" direct pe notificare (pe Android; pe iPhone atingerea deschide taskul).</p>
      {#if pushStatus.last_error}<p class="n-eroare">{pushStatus.last_error}</p>{/if}
      <div class="n-actiuni-rand">
        <Button loading={pushBusy} onclick={activeazaPush}>Activează pe telefonul ăsta</Button>
      </div>
    {:else}
      <p class="n-text">O notificare <strong>per task</strong>, nu un rezumat, cu „Făcut" și „Azi" pe
        ea. Setările stau pe server, deci sunt aceleași de pe orice dispozitiv.</p>
      <div class="n-stare">
        <div class="n-rand">
          <span class="n-et">Dispozitive abonate</span>
          <span class="n-val">{pushStatus.abonamente}</span>
        </div>
        {#if pushStatus.last_error}<p class="n-eroare">{pushStatus.last_error}</p>{/if}
      </div>
      <button class="n-link" disabled={pushBusy} onclick={dezactiveazaPush}>Nu mai trimite pe dispozitivul ăsta</button>
    {/if}

    {#if arataSetari}
      {#if setari}
        <div class="n-setari">
          <Select label="Ora" bind:value={setari.ora} options={oreDisponibile} size="sm" />
          <Input label="Vechime (zile)" type="number" min="0" max="60"
                 bind:value={setari.zileVechime} />
        </div>
        <div class="n-feluri">
          <label class="n-comutator">
            <input type="checkbox" class="cbx" bind:checked={setari.scadente} />
            <span>Taskurile scadente în ziua respectivă</span>
          </label>
          <label class="n-comutator">
            <input type="checkbox" class="cbx" bind:checked={setari.faraTermen} />
            <span>Taskurile rămase fără termen</span>
          </label>
          <label class="n-comutator">
            <input type="checkbox" class="cbx" bind:checked={setari.oreExacte} />
            <span>La ora exactă a taskului</span>
          </label>
          <div class="n-comutator">
            <label class="n-com-et">
              <input type="checkbox" class="cbx" bind:checked={setari.deplasari} />
              <span>Seara dinaintea unei plecări pe site</span>
            </label>
            <Select bind:value={setari.oraDeplasare} options={oreDisponibile} size="sm" />
          </div>
        </div>
        <p class="n-nota">
          <Info size={15} strokeWidth={1.5} />
          <span>Cel puțin un fel trebuie să rămână pornit — altfel n-ar mai suna nimic, iar
            tăcerea nu se poate deosebi de o defecțiune.</span>
        </p>
        {#if exacta === false}
          <div class="n-alarma">
            <AlarmClockOff size={16} strokeWidth={1.5} />
            <div>
              <strong>Alarma exactă e oprită</strong>
              <p>Dimineața ar putea întârzia cu zeci de minute. Deschide comutatorul din
                sistem — nu-ți spunem calea, fiindcă diferă de la un telefon la altul.</p>
              <button class="n-alarma-b" onclick={pornesteAlarma}>
                <ExternalLink size={14} strokeWidth={1.5} />Deschide ecranul
              </button>
            </div>
          </div>
        {/if}
        {#if setariEroare}<p class="n-eroare">{setariEroare}</p>{/if}
      {:else}
        <div class="n-skel"><Skeleton width="70%" height="14px" /><Skeleton width="50%" height="14px" /></div>
      {/if}
    {/if}

    {#if arataSetari || (pushStatus?.disponibil && pushLocal?.abonat) || esteNativ()}
      <div class="n-foot">
        {#if esteNativ()}
          <Button variant="secondary" disabled={pushBusy} onclick={probaLocala}>
            <BellRing size={15} strokeWidth={1.5} />Notificare de probă
          </Button>
        {:else if pushStatus?.disponibil && pushLocal?.abonat}
          <Button variant="secondary" disabled={pushBusy} onclick={testPush}>
            <BellRing size={15} strokeWidth={1.5} />Notificare de probă
          </Button>
        {:else}
          <span></span>
        {/if}
        {#if arataSetari}
          <Button disabled={pushBusy || !setari} onclick={salveazaSetari}>Salvează</Button>
        {/if}
      </div>
    {/if}
  </section>
</div>

<style>
  .page { padding: var(--space-lg); }
  .page-header { margin-bottom: var(--space-md); }
  .page-header h1 { font-size: var(--font-title); font-weight: var(--w-title); letter-spacing: var(--tracking-title); }

  .n-sectiune { max-width: 560px; }
  .n-titlu { display: flex; align-items: center; gap: var(--space-sm);
    font-size: var(--font-h2); font-weight: var(--w-title); letter-spacing: var(--tracking-title);
    color: var(--text); margin-bottom: var(--space-md); }
  .n-titlu :global(svg) { color: var(--text-dim); }

  .n-skel { display: flex; flex-direction: column; gap: var(--space-sm); }
  .n-text { font-size: var(--font-body); color: var(--text-secondary); line-height: var(--lh-normal); text-wrap: pretty; }
  .n-mono { font-family: var(--font-mono); font-size: var(--font-small); color: var(--text); }

  .n-stare { display: flex; flex-direction: column; margin-top: var(--space-sm); }
  .n-rand { display: flex; align-items: center; justify-content: space-between; gap: var(--space-md);
    min-height: var(--ctrl-md); font-size: var(--font-body); color: var(--text-secondary); }
  .n-et { color: var(--text-secondary); }
  .n-val { color: var(--text); text-align: right; }

  .n-eroare { display: flex; gap: 9px; padding: 11px 13px; border-radius: var(--radius-sm);
    background: var(--danger-subtle); color: var(--danger-deep);
    font-family: var(--font-mono); font-size: var(--font-small); line-height: var(--lh-snug);
    overflow-wrap: anywhere; margin-top: var(--space-sm); }

  .n-link { font-size: var(--font-small); color: var(--text-dim); background: none; border: none;
    cursor: pointer; text-decoration: underline; padding: 0; margin-top: var(--space-sm); }
  .n-link:hover { color: var(--text); }
  .n-link:disabled { color: var(--text-dim); cursor: default; text-decoration: none; }

  .n-actiuni-rand { margin-top: var(--space-md); }

  .n-setari { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-sm) var(--space-md); margin-top: var(--space-lg); }
  .n-feluri { display: flex; flex-direction: column; margin-top: var(--space-12); }
  .n-feluri .n-comutator + .n-comutator { border-top: 1px solid var(--border); }
  .n-comutator { display: flex; align-items: center; gap: var(--space-12);
    font-size: var(--font-body); color: var(--text);
    min-height: 48px; padding: 0 var(--space-2xs); cursor: pointer; }
  .n-comutator input { width: 18px; height: 18px; flex: none; accent-color: var(--accent);
    cursor: pointer; }
  .n-com-et { flex: 1; min-width: 0; display: flex; align-items: center; gap: var(--space-12);
    cursor: pointer; }
  .n-comutator :global(.field) { flex: none; width: 96px; }

  .n-alarma { display: flex; gap: var(--space-12); margin-top: var(--space-12);
    padding: var(--space-12); border-radius: var(--radius-md);
    background: var(--danger-subtle); }
  .n-alarma :global(svg) { flex: none; margin-top: var(--space-2xs); color: var(--danger-deep); }
  .n-alarma strong { display: block; font-size: var(--font-body); font-weight: var(--fw-semibold);
    color: var(--text); }
  .n-alarma p { margin-top: var(--space-xs); font-size: var(--font-small); color: var(--text-secondary); }
  .n-alarma-b { display: inline-flex; align-items: center; gap: var(--space-6); margin-top: var(--space-sm);
    min-height: var(--tap-min); padding: 0 var(--space-12);
    border: 1px solid var(--border); border-radius: var(--radius-md);
    background: var(--bg-surface); color: var(--text);
    font-size: var(--font-control); font-weight: var(--fw-semibold); cursor: pointer;
    transition: var(--transition-colors); }
  .n-alarma-b:hover { border-color: var(--text-dim); }

  .n-nota { display: flex; align-items: flex-start; gap: var(--space-sm);
    margin-top: var(--space-12); font-size: var(--font-small);
    color: var(--text-secondary); }
  .n-nota :global(svg) { flex: none; margin-top: 1px; color: var(--text-dim); }

  .n-foot { display: flex; align-items: center; justify-content: space-between;
    gap: var(--space-sm); flex-wrap: wrap; margin-top: var(--space-lg); }
  @media (max-width: 768px) {
    .n-foot { flex-direction: column-reverse; align-items: stretch; flex-wrap: nowrap; }
    .n-foot > :global(.btn-secondary) { background: none; border: none; min-height: var(--tap-min); }
  }
  @media (max-width: 620px) {
    .n-setari { grid-template-columns: 1fr; }
  }
</style>
