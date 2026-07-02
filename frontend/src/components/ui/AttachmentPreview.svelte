<script>
  import { FileText, Image, Mail, FileSpreadsheet, FileArchive, File, Download, ExternalLink } from '@lucide/svelte'
  import SolidIcon from './SolidIcon.svelte'
  import Modal from './Modal.svelte'
  import Button from './Button.svelte'

  // attachment: { id, nume_fisier, tip_fisier, ... }
  // ondelete (optional): called with the attachment after closing the preview;
  // the parent runs its own confirm flow.
  let { open = $bindable(false), attachment = null, ondelete = null } = $props()

  const TYPE_ICONS = { PDF: FileText, IMG: Image, EMAIL: Mail, DOC: FileText, XLS: FileSpreadsheet, ZIP: FileArchive }

  const url = $derived(attachment ? `/api/atasamente/${attachment.id}/download` : '')
  const isImage = $derived(attachment?.tip_fisier === 'IMG')
  const isPdf = $derived(attachment?.tip_fisier === 'PDF')
  const Icon = $derived(TYPE_ICONS[attachment?.tip_fisier] || File)

  function requestDelete() {
    if (!ondelete || !attachment) return
    const a = attachment
    open = false
    ondelete(a)
  }
</script>

<Modal bind:open title={attachment?.nume_fisier || 'Atasament'} size="wide">
  <div class="ap">
    {#if isImage}
      <div class="ap-stage"><img class="ap-img" src={url} alt={attachment.nume_fisier} /></div>
    {:else if isPdf}
      <iframe class="ap-pdf" src={url} title={attachment.nume_fisier}></iframe>
    {:else}
      <div class="ap-none">
        <Icon size={48} />
        <p class="ap-name">{attachment?.nume_fisier}</p>
        <p class="ap-hint">Acest tip de fisier nu poate fi previzualizat in browser. Descarca-l pentru a-l deschide.</p>
      </div>
    {/if}
  </div>

  {#snippet footer()}
    <div class="ap-actions">
      {#if ondelete}
        <Button variant="ghost" onclick={requestDelete}><SolidIcon name="trash" size={14} /> Sterge</Button>
      {/if}
      <span class="ap-spacer"></span>
      <a class="ap-link" href={url} target="_blank" rel="noopener"><ExternalLink size={14} /> Deschide in tab nou</a>
      <a class="ap-link primary" href={url} download={attachment?.nume_fisier}><Download size={14} /> Descarca</a>
    </div>
  {/snippet}
</Modal>

<style>
  .ap { display: flex; flex-direction: column; }
  .ap-stage { display: flex; align-items: center; justify-content: center; background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius-md); padding: var(--space-sm); }
  .ap-img { max-width: 100%; max-height: 64vh; object-fit: contain; border-radius: var(--radius-xs); }
  .ap-pdf { width: 100%; height: 68vh; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg); }
  .ap-none { display: flex; flex-direction: column; align-items: center; gap: var(--space-sm); padding: var(--space-xl) var(--space-md); color: var(--text-dim); text-align: center; }
  .ap-name { font-size: var(--font-body); font-weight: var(--fw-semibold); color: var(--text); word-break: break-all; }
  .ap-hint { font-size: var(--font-small); color: var(--text-dim); max-width: 420px; }
  .ap-actions { display: flex; align-items: center; gap: var(--space-sm); }
  .ap-spacer { flex: 1; }
  .ap-link { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: var(--radius-md); border: 1px solid var(--border); background: var(--bg-elevated); color: var(--text-secondary); font-size: var(--font-small); cursor: pointer; transition: all var(--dur-fast) var(--ease); }
  .ap-link:hover { background: var(--bg-hover); color: var(--text); border-color: var(--text-dim); }
  .ap-link.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-text); font-weight: var(--fw-semibold); }
  .ap-link.primary:hover { opacity: 0.9; color: var(--accent-text); }
  @media (max-width: 768px) {
    .ap-actions { flex-wrap: wrap; }
    .ap-pdf { height: 60vh; }
  }
</style>
