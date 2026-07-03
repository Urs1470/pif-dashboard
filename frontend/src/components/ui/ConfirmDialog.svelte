<script>
  import Modal from './Modal.svelte'
  import Button from './Button.svelte'

  let { open = $bindable(false), title = 'Confirmare', message = 'Ești sigur?', confirmLabel = 'Confirmă', danger = true, onconfirm } = $props()
  let busy = $state(false)

  async function confirm() {
    busy = true
    try {
      await onconfirm?.()
      open = false
    } finally { busy = false }
  }
</script>

<Modal bind:open {title} size="sm">
  <p class="msg">{message}</p>
  {#snippet footer()}
    <div class="modal-actions">
      <Button variant="secondary" onclick={() => open = false}>Anulează</Button>
      <Button variant={danger ? 'danger' : 'primary'} loading={busy} onclick={confirm}>{confirmLabel}</Button>
    </div>
  {/snippet}
</Modal>

<style>
  .msg { font-size: var(--font-body); color: var(--text-secondary); line-height: var(--lh-normal); }
</style>
