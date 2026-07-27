<script>
  import { onMount } from 'svelte'
  import { fade } from 'svelte/transition'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../lib/motion.svelte.js'
  import { Settings, Download, Upload, Database, BookOpen, Save, AlertTriangle, HardDriveDownload, RefreshCw } from '@lucide/svelte'
  import { apiJson, apiFetch } from '../lib/api.js'
  import { toast } from '../stores/ui.svelte.js'
  import Card from '../components/ui/Card.svelte'
  import Button from '../components/ui/Button.svelte'
  import Input from '../components/ui/Input.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'

  let restoreInput = $state(null)
  let restoreData = $state(null)
  let showRestoreConfirm = $state(false)
  let dbInput = $state(null)
  let dbFile = $state(null)
  let showDbConfirm = $state(false)

  let obsConfig = $state({ vault_path: '', valid: false, note_count: 0, configured: false })
  let obsSaving = $state(false)

  let activeTab = $state('export')

  onMount(async () => {
    try {
      const c = await apiJson('/api/obsidian/config')
      obsConfig = { vault_path: c.vault_path || '', valid: !!c.valid, note_count: c.note_count || 0, configured: !!c.configured }
    } catch (_) {}
  })

  async function downloadBackup() {
    try {
      const res = await apiFetch('/api/backup')
      const data = await res.json()
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `pif_backup_${new Date().toISOString().split('T')[0]}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast('Backup descarcat', 'success')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    }
  }

  function onRestoreFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        restoreData = JSON.parse(reader.result)
        showRestoreConfirm = true
      } catch (_) {
        toast('Fisier JSON invalid', 'error')
      }
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  async function doRestore() {
    await apiJson('/api/restore', { method: 'POST', body: restoreData })
    restoreData = null
    toast('Baza de date restaurata', 'success')
  }

  function onDbFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    dbFile = file
    showDbConfirm = true
    e.target.value = ''
  }

  async function doDbUpload() {
    const fd = new FormData()
    fd.append('db', dbFile)
    await apiJson('/api/admin/db-upload', { method: 'POST', body: fd })
    dbFile = null
    toast('Baza de date inlocuita', 'success')
  }

  async function saveObsidian() {
    obsSaving = true
    try {
      await apiJson('/api/obsidian/config', { method: 'PUT', body: { vault_path: obsConfig.vault_path } })
      const c = await apiJson('/api/obsidian/config')
      obsConfig = { vault_path: c.vault_path || '', valid: !!c.valid, note_count: c.note_count || 0, configured: !!c.configured }
      toast(obsConfig.valid ? `Vault valid — ${obsConfig.note_count} notite` : 'Salvat, dar calea nu e valida', obsConfig.valid ? 'success' : 'error')
    } catch (e) {
      toast(`Eroare: ${e.message}`, 'error')
    } finally { obsSaving = false }
  }

  async function clearLocalCache() {
    try {
      localStorage.clear()
      const dbs = await (indexedDB.databases ? indexedDB.databases() : Promise.resolve([]))
      for (const d of dbs) { if (d.name && d.name.startsWith('pif')) indexedDB.deleteDatabase(d.name) }
      const keys = await caches.keys()
      for (const k of keys) { if (k.startsWith('pif')) await caches.delete(k) }
      const reg = await navigator.serviceWorker?.getRegistration()
      if (reg?.waiting) reg.waiting.postMessage('skipWaiting')
      toast('Cache curatat. Reincarca pagina (Ctrl+Shift+R).', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

  async function forceSWUpdate() {
    try {
      const reg = await navigator.serviceWorker?.getRegistration()
      if (!reg) { toast('Niciun service worker activ', 'info'); return }
      await reg.update()
      toast('Service worker actualizat. Reincarca pagina.', 'success')
    } catch (e) { toast(`Eroare: ${e.message}`, 'error') }
  }

</script>

<div class="page">
  <div class="page-header"><Settings size={22} /><h1>Admin</h1></div>
  <p class="hint-sub" style="margin-bottom: var(--space-md)">Sertar de întreținere. Importul de debrief se face direct prin API (<code>POST /api/import/debrief</code>), din Claude Code — nu mai are formular aici.</p>

  <div class="tabs">
    <button class="tab" class:active={activeTab === 'export'} onclick={() => activeTab = 'export'}><Database size={14} /> Export &amp; Backup</button>
    <button class="tab" class:active={activeTab === 'integrare'} onclick={() => activeTab = 'integrare'}><BookOpen size={14} /> Integrare</button>
  </div>

  {#key activeTab}
  <div class="tab-pane" in:fade={{ duration: motionDuration(DUR_FAST) }}>
  {#if activeTab === 'export'}
    <h2 class="sec-title"><Download size={16} /> Export</h2>
    <Card>
      <div class="actions">
        <Button variant="secondary" size="sm" onclick={() => window.open('/api/export/ics', '_blank')}><Download size={14} /> Calendar (.ics)</Button>
      </div>
      <p class="hint-sub">Perioadele de implementare, deadline-urile și scadențele, ca fișier de calendar. Abonează-te la el din Google/Apple Calendar ca să-l ai pe telefon.</p>
    </Card>

    <h2 class="sec-title"><Database size={16} /> Backup &amp; Restore</h2>
    <Card>
      <div class="actions">
        <Button variant="secondary" size="sm" onclick={downloadBackup}><Download size={14} /> Backup JSON</Button>
        <Button variant="secondary" size="sm" onclick={() => restoreInput?.click()}><Upload size={14} /> Restaureaza JSON</Button>
        <Button variant="secondary" size="sm" onclick={() => window.open('/api/admin/db-dump', '_blank')}><Download size={14} /> Descarca DB</Button>
        <Button variant="secondary" size="sm" onclick={() => dbInput?.click()}><Upload size={14} /> Incarca DB</Button>
      </div>
      <p class="hint"><AlertTriangle size={12} /> Restaurarea suprascrie datele curente. Serverul face si backup-uri automate.</p>
      <input type="file" accept=".json,application/json" hidden bind:this={restoreInput} onchange={onRestoreFile} />
      <input type="file" accept=".db" hidden bind:this={dbInput} onchange={onDbFile} />
    </Card>
  {/if}

  {#if activeTab === 'integrare'}
    <h2 class="sec-title"><BookOpen size={16} /> Integrare Obsidian</h2>
    <Card>
      <div class="obs-form">
        <Input label="Cale vault" bind:value={obsConfig.vault_path} placeholder="/home/ion-ursu/Projects/Knowledge" />
        <p class="hint-sub">Calea vaultului clonat pe server. Alimentează tabul <b>Wiki</b> din pagina proiectului și write-back-ul de frontmatter (status/deadline → README-ul din wiki).</p>
        <div class="actions">
          <Button size="sm" loading={obsSaving} onclick={saveObsidian}><Save size={14} /> Salveaza</Button>
          {#if obsConfig.configured}
            <span class="obs-status" class:ok={obsConfig.valid}>
              {obsConfig.valid ? `Valid · ${obsConfig.note_count} notite` : 'Cale invalida'}
            </span>
          {/if}
        </div>
      </div>
    </Card>

    <h2 class="sec-title"><HardDriveDownload size={16} /> Cache &amp; Service Worker</h2>
    <Card>
      <div class="actions">
        <Button variant="secondary" size="sm" onclick={clearLocalCache}><HardDriveDownload size={14} /> Curata Cache Local</Button>
        <Button variant="secondary" size="sm" onclick={forceSWUpdate}><RefreshCw size={14} /> Actualizeaza Service Worker</Button>
      </div>
      <p class="hint"><AlertTriangle size={12} /> Curatarea cache-ului sterge localStorage, IndexedDB (pif*) si SW cache. Necesita reincarcarea paginii.</p>
    </Card>
  {/if}
  </div>
  {/key}
</div>

<ConfirmDialog bind:open={showRestoreConfirm} title="Restaureaza backup" message="Restaurarea SUPRASCRIE toate datele curente cu cele din fisierul JSON. Continui?" confirmLabel="Restaureaza" onconfirm={doRestore} />
<ConfirmDialog bind:open={showDbConfirm} title="Inlocuieste baza de date" message={`Inlocuiesti baza de date cu "${dbFile?.name}"? Cea curenta va fi salvata ca backup pe server.`} confirmLabel="Inlocuieste" onconfirm={doDbUpload} />

<style>
  .page { padding: var(--space-lg); }
  .page-header { display: flex; align-items: center; gap: var(--space-sm); color: var(--text); margin-bottom: var(--space-md); }
  .page-header h1 { font-size: var(--font-h1); font-weight: var(--fw-bold); }
  .sec-title { display: flex; align-items: center; gap: var(--space-xs); font-size: var(--font-body); font-weight: var(--fw-semibold); color: var(--text); margin-top: var(--space-xl); margin-bottom: var(--space-sm); }
  .tab-pane .sec-title:first-child { margin-top: 0; }
  .actions { display: flex; gap: var(--space-sm); flex-wrap: wrap; align-items: center; }
  .hint { display: flex; align-items: center; gap: 4px; font-size: var(--font-tiny); color: var(--text-dim); margin-top: var(--space-sm); }
  .hint-sub { font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; }
  .obs-form { display: flex; flex-direction: column; gap: var(--space-md); }
  .obs-status { font-size: var(--font-tiny); color: var(--danger); }
  .obs-status.ok { color: var(--success); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
  }
</style>
