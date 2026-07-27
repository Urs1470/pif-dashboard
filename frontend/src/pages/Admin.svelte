<script>
  import { onMount } from 'svelte'
  import { fade } from 'svelte/transition'
  import { motionDuration, DUR_FAST, DUR_BASE } from '../lib/motion.svelte.js'
  import { Settings, Download, Upload, Database, BarChart3, FileJson, BookOpen, Save, AlertTriangle, HardDriveDownload, RefreshCw } from '@lucide/svelte'
  import { apiJson, apiFetch } from '../lib/api.js'
  import { PROJECT_STATUS_LABELS } from '../lib/formatters.js'
  import { toast } from '../stores/ui.svelte.js'
  import Card from '../components/ui/Card.svelte'
  import Button from '../components/ui/Button.svelte'
  import Input from '../components/ui/Input.svelte'
  import Skeleton from '../components/ui/Skeleton.svelte'
  import ConfirmDialog from '../components/ui/ConfirmDialog.svelte'
  import BreakdownBars from '../components/admin/BreakdownBars.svelte'

  let stats = $state(null)
  let extended = $state(null)
  let loading = $state(true)

  let restoreInput = $state(null)
  let restoreData = $state(null)
  let showRestoreConfirm = $state(false)
  let dbInput = $state(null)
  let dbFile = $state(null)
  let showDbConfirm = $state(false)

  let debriefText = $state('')
  let debriefBusy = $state(false)
  let debriefResult = $state(null)

  let obsConfig = $state({ vault_path: '', valid: false, note_count: 0, configured: false })
  let obsSaving = $state(false)

  let activeTab = $state('stats')

  const STAT_LABELS = { total: 'Total proiecte', active: 'Active', finished: 'Finalizate' }

  onMount(async () => {
    try { stats = await apiJson('/api/stats') } catch (_) {}
    try { extended = await apiJson('/api/stats/extended') } catch (_) {}
    try {
      const c = await apiJson('/api/obsidian/config')
      obsConfig = { vault_path: c.vault_path || '', valid: !!c.valid, note_count: c.note_count || 0, configured: !!c.configured }
    } catch (_) {}
    loading = false
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

  async function importDebrief() {
    if (!debriefText.trim()) return
    debriefBusy = true
    debriefResult = null
    try {
      const data = JSON.parse(debriefText)
      const result = await apiJson('/api/import/debrief', { method: 'POST', body: data })
      debriefResult = result
      debriefText = ''
      toast('Debrief importat', 'success')
    } catch (e) {
      toast(e instanceof SyntaxError ? 'JSON invalid' : `Eroare: ${e.message}`, 'error')
    } finally { debriefBusy = false }
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

  <div class="tabs">
    <button class="tab" class:active={activeTab === 'stats'} onclick={() => activeTab = 'stats'}><BarChart3 size={14} /> Statistici</button>
    <button class="tab" class:active={activeTab === 'export'} onclick={() => activeTab = 'export'}><Database size={14} /> Export &amp; Backup</button>
    <button class="tab" class:active={activeTab === 'import'} onclick={() => activeTab = 'import'}><FileJson size={14} /> Import Debrief</button>
    <button class="tab" class:active={activeTab === 'integrare'} onclick={() => activeTab = 'integrare'}><BookOpen size={14} /> Integrare</button>
  </div>

  {#key activeTab}
  <div class="tab-pane" in:fade={{ duration: motionDuration(DUR_FAST) }}>
  {#if activeTab === 'stats'}
    {#if loading}
      <div class="grid">{#each Array(3) as _}<Skeleton height="80px" />{/each}</div>
    {:else}
      <h2 class="sec-title"><BarChart3 size={16} /> Statistici</h2>
      {#if stats}
        <div class="grid cell-in" in:fade={{ duration: motionDuration(DUR_BASE) }}>
          {#each Object.entries(stats) as [key, val]}
            <Card>
              <div class="stat-label">{STAT_LABELS[key] || key.replace(/_/g, ' ')}</div>
              <div class="stat-value">{typeof val === 'number' ? val.toLocaleString('ro-RO') : val}</div>
            </Card>
          {/each}
        </div>
      {/if}

      {#if extended}
        <div class="two-col cell-in" in:fade={{ duration: motionDuration(DUR_BASE) }}>
          <Card>
            <h3 class="card-title">Dupa status</h3>
            <BreakdownBars items={(extended.by_status || []).map(s => ({ label: s.status, count: s.count }))} labelMap={PROJECT_STATUS_LABELS} color="var(--accent)" />
          </Card>
          <Card>
            <h3 class="card-title">Dupa producator</h3>
            <BreakdownBars items={(extended.by_manufacturer || []).map(m => ({ label: m.producator, count: m.count }))} color="var(--info)" />
          </Card>
        </div>
      {/if}
    {/if}

  {/if}

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

  {#if activeTab === 'import'}
    <h2 class="sec-title"><FileJson size={16} /> Import Debrief</h2>
    <Card>
      <textarea rows="5" bind:value={debriefText} placeholder={'{"proiect": {...}, "tasks": [...], ...}'}></textarea>
      <p class="hint-sub">Se importă clientul, proiectul și taskurile. Un <code>echipamente[]</code> din JSON e acceptat dar ignorat (v28) — parametrii de drive se pun în wiki cu skill-ul <code>drive-backup</code>.</p>
      <div class="actions" style="margin-top: var(--space-sm)">
        <Button size="sm" loading={debriefBusy} disabled={!debriefText.trim()} onclick={importDebrief}><Upload size={14} /> Importa</Button>
        {#if debriefResult?.id || debriefResult?.proiect_id}
          <a class="result-link" href="#/projects/{debriefResult.id || debriefResult.proiect_id}" transition:fade={{ duration: motionDuration(DUR_BASE) }}>Vezi proiectul creat →</a>
        {/if}
      </div>
      {#if debriefResult?.sumar?.echipamente_ignorate}
        <p class="hint-sub">{debriefResult.sumar.echipamente_ignorate} echipamente din JSON au fost ignorate.</p>
      {/if}
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
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--space-sm); margin-bottom: var(--space-md); }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-sm); margin-bottom: var(--space-sm); }
  .stat-label { font-size: var(--font-micro); font-weight: var(--fw-semibold); text-transform: uppercase; letter-spacing: var(--tracking-wider); color: var(--text-secondary); margin-bottom: 4px; }
  .stat-value { font-size: var(--font-display); font-family: var(--font-mono); font-variant-numeric: tabular-nums; font-weight: var(--fw-semibold); color: var(--text); font-feature-settings: "tnum"; }
  .card-title { font-size: var(--font-small); font-weight: var(--fw-semibold); color: var(--text); margin-bottom: var(--space-sm); }
  .actions { display: flex; gap: var(--space-sm); flex-wrap: wrap; align-items: center; }
  .hint { display: flex; align-items: center; gap: 4px; font-size: var(--font-tiny); color: var(--text-dim); margin-top: var(--space-sm); }
  .hint-sub { font-size: var(--font-tiny); color: var(--text-dim); margin-top: 2px; }
  textarea { width: 100%; padding: 10px 12px; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-md); color: var(--text); font-size: var(--font-small); font-family: var(--font-mono); resize: vertical; transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
  textarea:focus { border-color: var(--accent); box-shadow: var(--focus-ring); outline: none; }
  .result-link { font-size: var(--font-small); color: var(--accent); }
  .issues { display: flex; flex-direction: column; gap: var(--space-xs); }
  .issue { display: flex; align-items: center; gap: var(--space-sm); font-size: var(--font-small); }
  .issue-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .issue-label { flex: 1; color: var(--text-secondary); }
  .issue-count { font-weight: var(--fw-semibold); color: var(--text); font-feature-settings: "tnum"; }
  .obs-form { display: flex; flex-direction: column; gap: var(--space-md); }
  .obs-status { font-size: var(--font-tiny); color: var(--danger); }
  .obs-status.ok { color: var(--success); }

  @media (max-width: 768px) {
    .page { padding: var(--space-md); }
    .grid { grid-template-columns: repeat(2, 1fr); }
    .two-col { grid-template-columns: 1fr; }
  }
</style>
