<script>
  import { FileText, Image, Mail, FileSpreadsheet, FileArchive, File, Download, Upload } from '@lucide/svelte'
  import SolidIcon from '../ui/SolidIcon.svelte'
  import { loadAttachments, uploadAttachment, deleteAttachment } from '../../stores/projects.svelte.js'
  import { toast } from '../../stores/ui.svelte.js'
  import { formatFileSize } from '../../lib/exportMd.js'
  import { formatDate } from '../../lib/formatters.js'
  import Button from '../ui/Button.svelte'
  import ConfirmDialog from '../ui/ConfirmDialog.svelte'
  import AttachmentPreview from '../ui/AttachmentPreview.svelte'

  let { projectId } = $props()

  let attachments = $state([])
  let loading = $state(true)
  let uploading = $state(false)
  let fileInput = $state(null)
  let confirmOpen = $state(false)
  let toDelete = $state(null)
  let previewOpen = $state(false)
  let previewAtt = $state(null)

  const TYPE_ICONS = { PDF: FileText, IMG: Image, EMAIL: Mail, DOC: FileText, XLS: FileSpreadsheet, ZIP: FileArchive }

  async function load() {
    loading = true
    try {
      const data = await loadAttachments(projectId)
      attachments = Array.isArray(data) ? data : data.atasamente || []
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { loading = false }
  }

  async function onFileChange(e) {
    const files = e.target.files
    if (!files?.length) return
    uploading = true
    try {
      for (const file of files) {
        await uploadAttachment(projectId, file)
      }
      toast(files.length > 1 ? `${files.length} fisiere incarcate` : 'Fisier incarcat', 'success')
      await load()
    } catch (err) {
      toast(`Eroare la upload: ${err.message}`, 'error')
    } finally {
      uploading = false
      e.target.value = ''
    }
  }

  function openPreview(att) {
    previewAtt = att
    previewOpen = true
  }

  function askDelete(att) {
    toDelete = att
    confirmOpen = true
  }

  async function doDelete() {
    if (!toDelete) return
    await deleteAttachment(toDelete.id)
    toast('Atasament sters', 'success')
    toDelete = null
    await load()
  }

  $effect(() => { if (projectId) load() })
</script>

<div class="attachments">
  <div class="att-header">
    <span class="att-count">{attachments.length} fisiere</span>
    <Button size="sm" variant="secondary" loading={uploading} onclick={() => fileInput?.click()}>
      <Upload size={14} /> Incarca
    </Button>
    <input type="file" multiple hidden bind:this={fileInput} onchange={onFileChange} />
  </div>

  {#if loading}
    <p class="empty">Se incarca...</p>
  {:else if attachments.length === 0}
    <p class="empty">Niciun atasament. Incarca fisiere cu butonul de mai sus.</p>
  {:else}
    <div class="att-list">
      {#each attachments as att (att.id)}
        {@const TypeIcon = TYPE_ICONS[att.tip_fisier] || File}
        <div class="att-row">
          <button class="att-main" title="Previzualizeaza" onclick={() => openPreview(att)}>
            <TypeIcon size={18} />
            <div class="att-text">
              <div class="att-name">{att.nume_fisier}</div>
              <div class="att-meta">{att.tip_fisier} · {formatFileSize(att.dimensiune)} · {formatDate(att.data)}</div>
            </div>
          </button>
          <a class="att-btn" title="Descarca" href={`/api/atasamente/${att.id}/download`} download={att.nume_fisier}><Download size={15} /></a>
          <button class="att-btn danger" title="Sterge" onclick={() => askDelete(att)}><SolidIcon name="trash" size={15} /></button>
        </div>
      {/each}
    </div>
  {/if}
</div>

<ConfirmDialog bind:open={confirmOpen} title="Sterge atasament" message={`Stergi "${toDelete?.nume_fisier}"? Fisierul va fi sters definitiv.`} confirmLabel="Sterge" onconfirm={doDelete} />
<AttachmentPreview bind:open={previewOpen} attachment={previewAtt} ondelete={askDelete} />

<style>
  .att-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-sm); }
  .att-count { font-size: var(--font-tiny); color: var(--text-dim); }
  .att-list { display: flex; flex-direction: column; gap: var(--space-xs); }
  .att-row { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) var(--space-md); background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-dim); transition: border-color var(--dur-fast) var(--ease); }
  .att-row:hover { border-color: var(--text-dim); }
  .att-main { flex: 1; min-width: 0; display: flex; align-items: center; gap: var(--space-sm); text-align: left; cursor: pointer; color: var(--text-dim); border-radius: var(--radius-xs); transition: color var(--dur-fast) var(--ease); }
  .att-main:hover { color: var(--accent); }
  .att-text { flex: 1; min-width: 0; }
  .att-name { font-size: var(--font-small); font-weight: var(--fw-medium); color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .att-meta { font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; }
  .att-btn { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); color: var(--text-dim); cursor: pointer; flex-shrink: 0; text-decoration: none; transition: all var(--dur-fast) var(--ease); }
  .att-btn:hover { background: var(--bg-hover); color: var(--text); }
  .att-btn.danger:hover { background: var(--danger-subtle); color: var(--danger); }
  .empty { color: var(--text-dim); font-size: var(--font-small); padding: var(--space-lg) 0; text-align: center; }
</style>
