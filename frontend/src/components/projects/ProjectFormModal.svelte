<script>
  import Modal from '../ui/Modal.svelte'
  import Input from '../ui/Input.svelte'
  import Select from '../ui/Select.svelte'
  import Button from '../ui/Button.svelte'
  import DatePicker from '../ui/DatePicker.svelte'
  import { createProject, updateProject, loadClients } from '../../stores/projects.svelte.js'
  import { toast } from '../../stores/ui.svelte.js'

  let { open = $bindable(false), project = null, onsaved } = $props()

  const PRODUCATORI = ['ABB', 'Siemens', 'Danfoss', 'Lenze', 'Altul']
  const STATUSES = [
    { value: 'in_lucru', label: 'În Lucru' },
    { value: 'in_asteptare', label: 'În Așteptare' },
    { value: 'blocat', label: 'Blocat' },
    { value: 'finalizat', label: 'Finalizat' },
  ]

  let form = $state(emptyForm())
  let saving = $state(false)
  let clients = $state([])

  function emptyForm() {
    return {
      tip: 'PIF', nume: '', client: '', locatie: '', echipament_principal: '',
      producator: 'ABB', cod_proiect: '', pm: '', data_incepere: '', deadline: '',
      status: 'in_lucru', nr_comanda: '', nr_contract: '',
    }
  }

  const isEdit = $derived(!!project?.id)

  $effect(() => {
    if (open) {
      if (project?.id) {
        form = {
          tip: project.tip || 'PIF',
          nume: project.nume || '',
          client: project.client || '',
          locatie: project.locatie || '',
          echipament_principal: project.echipament_principal || '',
          producator: project.producator || 'Altul',
          cod_proiect: project.cod_proiect || '',
          pm: project.pm || '',
          data_incepere: project.data_incepere || '',
          deadline: project.deadline || '',
          status: project.status || 'in_lucru',
          nr_comanda: project.nr_comanda || '',
          nr_contract: project.nr_contract || '',
        }
      } else {
        form = emptyForm()
      }
      loadClients().then(c => { clients = Array.isArray(c) ? c : c.clienti || [] }).catch(() => {})
    }
  })

  async function save() {
    if (!form.nume.trim()) return
    saving = true
    try {
      if (isEdit) {
        await updateProject(project.id, form)
        toast('Proiect actualizat', 'success')
      } else {
        await createProject(form)
        toast('Proiect creat', 'success')
      }
      open = false
      onsaved?.()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { saving = false }
  }
</script>

<Modal bind:open title={isEdit ? 'Editează Proiect' : 'Proiect Nou'} size="lg">
  <form onsubmit={(e) => { e.preventDefault(); save() }}>
    <div class="grid">
      <div class="tip-row">
        <span class="tip-label">Tip</span>
        <div class="tip-toggle">
          <button type="button" class="tip-btn" class:active-pif={form.tip === 'PIF'} onclick={() => form.tip = 'PIF'}>PIF</button>
          <button type="button" class="tip-btn" class:active-service={form.tip === 'Service'} onclick={() => form.tip = 'Service'}>Service</button>
        </div>
      </div>
      <div class="full"><Input label="Nume *" bind:value={form.nume} placeholder="Numele proiectului" /></div>
      <Input label="Client" bind:value={form.client} placeholder="Client" list="clients-list" />
      <Input label="Locație" bind:value={form.locatie} placeholder="Locație" />
      <Input label="Echipament principal" bind:value={form.echipament_principal} placeholder="Ex: ACS880" />
      <Select label="Producător" bind:value={form.producator} options={PRODUCATORI} />
      <Input label="Cod proiect" bind:value={form.cod_proiect} placeholder="Ex: P-042" />
      <Input label="PM" bind:value={form.pm} placeholder="Project manager" />
      <DatePicker label="Data începere" bind:value={form.data_incepere} />
      <DatePicker label="Deadline" bind:value={form.deadline} />
      <Input label="Nr. comandă" bind:value={form.nr_comanda} />
      <Input label="Nr. contract" bind:value={form.nr_contract} />
      {#if isEdit}
        <Select label="Status" bind:value={form.status} options={STATUSES} />
      {/if}
    </div>
    <datalist id="clients-list">
      {#each clients as c}<option value={c.nume}></option>{/each}
    </datalist>
  </form>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => open = false}>Anulează</Button>
      <Button loading={saving} disabled={!form.nume.trim()} onclick={save}>{isEdit ? 'Salvează' : 'Creează'}</Button>
    </div>
  {/snippet}
</Modal>

<style>
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-md); }
  .full { grid-column: 1 / -1; }
  .tip-row { grid-column: 1 / -1; display: flex; flex-direction: column; gap: 4px; }
  .tip-label { font-size: var(--font-tiny); font-weight: var(--fw-medium); color: var(--text-secondary); text-transform: uppercase; letter-spacing: var(--tracking-wide); }
  .tip-toggle { display: flex; gap: var(--space-xs); }
  .tip-btn { flex: 1; padding: 10px; min-height: 46px; border-radius: var(--radius-md); background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); font-weight: var(--fw-semibold); cursor: pointer; transition: all var(--dur-fast) var(--ease); }
  .tip-btn.active-pif { background: var(--accent-subtle); border-color: var(--accent); color: var(--accent); }
  .tip-btn.active-service { background: var(--service-subtle); border-color: var(--service-accent); color: var(--service-accent); }

  @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
</style>
