<script>
  import Modal from '../ui/Modal.svelte'
  import Input from '../ui/Input.svelte'
  import Select from '../ui/Select.svelte'
  import Button from '../ui/Button.svelte'
  import { createEquipment, updateEquipment } from '../../stores/projects.svelte.js'
  import { toast } from '../../stores/ui.svelte.js'

  let { open = $bindable(false), projectId, equipment = null, onsaved } = $props()

  const PRODUCATORI = ['ABB', 'Siemens', 'Danfoss', 'Lenze', 'Altul']

  let form = $state({ nume: '', producator: 'ABB', model: '', serial_number: '', params_text: '' })
  let saving = $state(false)

  const isEdit = $derived(!!equipment?.id)

  $effect(() => {
    if (open) {
      if (equipment?.id) {
        let paramsText = ''
        try {
          const params = typeof equipment.params_json === 'string' ? JSON.parse(equipment.params_json || '{}') : (equipment.params_json || {})
          paramsText = Object.entries(params).map(([k, v]) => `${k} = ${v}`).join('\n')
        } catch (_) {}
        form = {
          nume: equipment.nume || '',
          producator: equipment.producator || 'Altul',
          model: equipment.model || '',
          serial_number: equipment.serial_number || '',
          params_text: paramsText,
        }
      } else {
        form = { nume: '', producator: 'ABB', model: '', serial_number: '', params_text: '' }
      }
    }
  })

  async function save() {
    if (!form.nume.trim()) return
    saving = true
    try {
      if (isEdit) {
        await updateEquipment(equipment.id, form)
        toast('Echipament actualizat', 'success')
      } else {
        await createEquipment(projectId, form)
        toast('Echipament adaugat', 'success')
      }
      open = false
      onsaved?.()
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { saving = false }
  }
</script>

<Modal bind:open title={isEdit ? 'Editeaza Echipament' : 'Echipament Nou'} size="md">
  <form onsubmit={(e) => { e.preventDefault(); save() }}>
    <div class="grid">
      <Input label="Nume *" bind:value={form.nume} placeholder="Ex: ACS880-01" />
      <Select label="Producator" bind:value={form.producator} options={PRODUCATORI} />
      <Input label="Model" bind:value={form.model} placeholder="Model" />
      <Input label="Serial number" bind:value={form.serial_number} placeholder="S/N" />
    </div>
    <label class="ta-field">
      <span class="ta-label">Parametri modificati (PARAM = VALOARE, unul pe linie)</span>
      <textarea rows="6" bind:value={form.params_text} placeholder="99.04 = Vector&#10;20.01 = 1500 rpm"></textarea>
    </label>
  </form>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => open = false}>Anuleaza</Button>
      <Button loading={saving} disabled={!form.nume.trim()} onclick={save}>{isEdit ? 'Salveaza' : 'Adauga'}</Button>
    </div>
  {/snippet}
</Modal>

<style>
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-md); margin-bottom: var(--space-md); }
  .ta-field { display: flex; flex-direction: column; gap: 4px; }
  .ta-label { font-size: var(--font-tiny); font-weight: var(--fw-medium); color: var(--text-secondary); text-transform: uppercase; letter-spacing: var(--tracking-wide); }
  textarea { padding: 10px 12px; background: var(--bg-input); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); font-family: var(--font-mono); resize: vertical; }

  @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
</style>
