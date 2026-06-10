<script>
  import Modal from './Modal.svelte'
  import Button from './Button.svelte'

  let { open = $bindable(false), title = 'Confirmare', message = 'Esti sigur?', confirmLabel = 'Confirma', danger = true, onconfirm } = $props()
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
  <div class="actions">
    <Button variant="secondary" onclick={() => open = false}>Anuleaza</Button>
    <Button variant={danger ? 'danger' : 'primary'} loading={busy} onclick={confirm}>{confirmLabel}</Button>
  </div>
</Modal>

<style>
  .msg { font-size: var(--font-body); color: var(--text-secondary); line-height: 1.55; }
  .actions { display: flex; gap: var(--space-sm); justify-content: flex-end; margin-top: var(--space-lg); }
</style>
