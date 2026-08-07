<script>
  import { MapPin, Building2, Trash2, Wrench, Hammer } from '@lucide/svelte'
  import { apiJson } from '../../lib/api.js'
  import { toast } from '../../stores/ui.svelte.js'
  import Modal from '../ui/Modal.svelte'
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

  async function save() {
    if (busy) return
    if (!dStart || !dEnd) { toast('Alege început și sfârșit', 'error'); return }
    if (dEnd < dStart) { toast('Sfârșitul e înainte de început', 'error'); return }
    busy = true
    const body = { data_start: dStart, data_sfarsit: dEnd, locatie: loc, faza, eticheta: eticheta.trim() }
    try {
      if (period?.id) await apiJson(`/api/implementari/${period.id}`, { method: 'PUT', body })
      else await apiJson(`/api/proiecte/${projectId}/implementari`, { method: 'POST', body })
      open = false
      onsaved()
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = false }
  }
  async function remove() {
    if (!period?.id || busy) return
    if (!confirm('Ștergi această perioadă?')) return
    busy = true
    try { await apiJson(`/api/implementari/${period.id}`, { method: 'DELETE' }); open = false; onsaved() }
    catch (e) { toast(`Eroare: ${e.message}`, 'error') } finally { busy = false }
  }
</script>

<Modal bind:open title={period ? 'Editează perioada' : 'Perioadă nouă'} size="sm">
  <div class="ip">
    <div class="ip-grup">
      <span class="ip-h">Unde</span>
      <div class="ip-loc">
        <button class="loc-btn" class:on={loc === 'site'} onclick={() => loc = 'site'}><MapPin size={15} /> Site (șantier)</button>
        <button class="loc-btn" class:on={loc === 'sediu'} onclick={() => loc = 'sediu'}><Building2 size={15} /> Sediu EGB</button>
      </div>
    </div>
    <div class="ip-grup">
      <span class="ip-h">Ce fază</span>
      <div class="ip-loc">
        <button class="loc-btn" class:on={faza === 'pregatire'} onclick={() => faza = 'pregatire'}><Wrench size={15} /> Pregătire</button>
        <button class="loc-btn" class:on={faza === 'implementare'} onclick={() => faza = 'implementare'}><Hammer size={15} /> Implementare</button>
      </div>
    </div>
    <div class="ip-dates">
      <label class="ip-field"><span>Început</span><DatePicker bind:value={dStart} placeholder="alege" /></label>
      <label class="ip-field"><span>Sfârșit</span><DatePicker bind:value={dEnd} placeholder="alege" /></label>
    </div>
    <label class="ip-field"><span>Etichetă (opțional)</span><Input bind:value={eticheta} placeholder="ex. Punere în funcțiune" /></label>
  </div>
  {#snippet footer()}
    <div class="ip-actions">
      {#if period?.id}<button class="btn-del" onclick={remove} disabled={busy}><Trash2 size={14} /> Șterge</button>{/if}
      <span class="sp"></span>
      <button class="btn-ghost" onclick={() => open = false} disabled={busy}>Anulează</button>
      <button class="btn-primary" onclick={save} disabled={busy}>Salvează</button>
    </div>
  {/snippet}
</Modal>

<style>
  .ip { display: flex; flex-direction: column; gap: 14px; }
  .ip-grup { display: flex; flex-direction: column; gap: 6px; }
  .ip-h { font-size: var(--font-label); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); font-family: var(--font-mono); }
  .ip-loc { display: flex; gap: 8px; }
  .loc-btn { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 9px; border-radius: var(--radius-md); background: var(--bg-panel); border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; font-size: var(--font-small); }
  .loc-btn:hover { border-color: var(--border-strong); color: var(--text); }
  .loc-btn.on { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 50%, transparent); background: var(--accent-subtle); }
  .ip-dates { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .ip-field { display: flex; flex-direction: column; gap: 5px; }
  .ip-field span { font-size: var(--font-label); text-transform: uppercase; letter-spacing: var(--tracking-label); color: var(--text-dim); font-family: var(--font-mono); }
  .ip-actions { display: flex; align-items: center; gap: var(--space-sm); width: 100%; }
  .ip-actions .sp { flex: 1; }
  .btn-del { display: inline-flex; align-items: center; gap: 5px; padding: 8px 12px; border-radius: var(--radius-md); background: none; border: 1px solid var(--border); color: var(--danger); cursor: pointer; font-size: var(--font-small); }
  .btn-del:hover { background: var(--danger-subtle); }
  .btn-ghost { padding: 8px 16px; border-radius: var(--radius-md); background: none; border: 1px solid var(--border); color: var(--text-secondary); cursor: pointer; font-size: var(--font-small); }
  .btn-ghost:hover { border-color: var(--border-strong); color: var(--text); }
  .btn-primary { padding: 8px 16px; border-radius: var(--radius-md); background: var(--accent); border: none; color: var(--accent-text); cursor: pointer; font-size: var(--font-small); font-weight: var(--fw-semibold); }
  .btn-primary:disabled, .btn-del:disabled { opacity: 0.5; cursor: not-allowed; }

  @media (max-width: 768px) {
    .loc-btn { min-height: var(--tap-min); }
    /* „Șterge" nu se aliniaza cu „Anulează/Salvează": e alta clasa de actiune si,
       pe un sheet unde butoanele se intind, ar ajunge lipit de Salvează. Randul
       lui, la stanga. */
    .ip-actions { flex-wrap: wrap; }
    .ip-actions .sp { display: none; }
    .btn-del { order: 3; flex: 1 0 100%; justify-content: center; min-height: var(--tap-min); }
    .btn-ghost, .btn-primary { flex: 1; min-height: var(--tap-min); }
  }
</style>
