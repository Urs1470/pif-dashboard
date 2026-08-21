<script>
  import { tick } from 'svelte'
  import { Zap, Wrench } from '@lucide/svelte'
  import Modal from '../ui/Modal.svelte'
  import Input from '../ui/Input.svelte'
  import Select from '../ui/Select.svelte'
  import DatePicker from '../ui/DatePicker.svelte'
  import { createProject, updateProject, loadClients } from '../../stores/projects.svelte.js'
  import { toast } from '../../stores/ui.svelte.js'

  let { open = $bindable(false), project = null, onsaved } = $props()

  const PRODUCATORI = ['ABB', 'Siemens', 'Danfoss', 'Lenze', 'Altul']
  const STATUSES = [
    { value: 'pregatire', label: 'În pregătire' },
    { value: 'finalizat', label: 'Finalizat' },
  ]

  let form = $state(emptyForm())
  let saving = $state(false)
  let clients = $state([])
  let numeEl = $state(null)
  // EROAREA STA PE CAMP, NU INTR-UN TOAST DIN COLT.
  // `<Input>` are de la inceput prop `error` cu tot desenul lui (muchie de
  // restant, mesaj sub camp, `aria-invalid`) — si nu-l folosea nimeni, nicaieri.
  // Un toast se stinge in patru secunde, apare in coltul opus (pe telefon:
  // PESTE foaia formularului) si nu lasa niciun semn pe campul care trebuie
  // reparat. Aici lasa.
  let eroareNume = $state('')

  function emptyForm() {
    return {
      tip: 'PIF', nume: '', client: '', locatie: '', echipament_principal: '',
      producator: 'ABB', cod_proiect: '',
      status: 'pregatire', data_finalizare: '', nr_comanda: '', vault_folder: '',
    }
  }

  const isEdit = $derived(!!project?.id)

  // Muchia de restant pleaca in clipa in care incepi sa repari, nu la urmatoarea
  // apasare pe „Creează": altfel scrii numele si campul ramane rosu sub degete.
  $effect(() => {
    if (form.nume.trim() && eroareNume) eroareNume = ''
  })

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
          status: project.status || 'pregatire',
          data_finalizare: project.data_finalizare || '',
          nr_comanda: project.nr_comanda || '',
          vault_folder: project.vault_folder || '',
        }
      } else {
        form = emptyForm()
      }
      eroareNume = ''
      loadClients().then(c => { clients = Array.isArray(c) ? c : c.clienti || [] }).catch(() => {})
      // NUMELE PRIMESTE FOCUSUL, nu primul buton. Modal focalizeaza singur primul
      // element focalizabil, iar acela e acum „PIF" — deci deschiderea ar fi
      // aterizat pe o alegere care are deja un raspuns bun, in loc sa te lase sa
      // scrii. Tipul e sus fiindca e o RAMIFICATIE, nu fiindca e primul pas.
      tick().then(() => numeEl?.focus())
    }
  })

  async function save() {
    if (!form.nume.trim()) {
      eroareNume = 'Scrie un nume — restul se poate completa mai târziu.'
      numeEl?.focus()
      return
    }
    eroareNume = ''
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

<!-- `cuTastatura`: numele primeste focusul la deschidere (mai sus), deci
     tastatura vine sigur — foaia se naste deja ridicata deasupra ei. -->
<Modal bind:open title={isEdit ? 'Editează proiectul' : 'Proiect nou'} size="md" cuTastatura>
  <!-- `id` + `form="pf-form"` pe butonul din subsol: ENTER TREBUIE SA SALVEZE.
       Butonul de salvare e randat de `Modal` in slotul `footer`, deci in AFARA
       elementului `<form>`. Fara el, formularul ramane fara `type="submit"`, iar
       HTML blocheaza trimiterea implicita cand sunt mai multe campuri — masurat:
       Enter in „Nume" dadea ZERO cereri catre API, modalul ramanea deschis si nu
       aparea niciun mesaj. Iar aplicatia te invata exact gestul care nu mergea:
       campul rapid de pe Acasa scrie „Task rapid pentru azi, apoi Enter".
       Atributul `form` leaga un buton de un formular oriunde ar sta el in pagina;
       asa nu trebuie mutat subsolul in interiorul formei. -->
  <form class="pf" id="pf-form" onsubmit={(e) => { e.preventDefault(); save() }}>
    <span class="pf-titlu">{isEdit ? 'Editează proiectul' : 'Proiect nou'}</span>

    <!-- TIPUL NU E O ETICHETA, E O RAMIFICATIE: PIF si Service au sectiuni de
         camp diferite in pagina proiectului. De aceea sta sus, ca pereche de
         butoane, nu intr-un meniu — alegi inainte sa scrii, nu dupa.
         Cele doua nu se mai deosebesc prin CULOARE (erau amber vs accent, adica
         a doua culoare de brand): sistemul are un singur accent, deci alegerea o
         face SELECTIA, iar care e care scrie pe ele. -->
    <div class="pf-tip">
      <button type="button" class="pf-opt" class:on={form.tip === 'PIF'} onclick={() => form.tip = 'PIF'}>
        <Zap size={16} strokeWidth={1.5} />PIF
      </button>
      <button type="button" class="pf-opt" class:on={form.tip === 'Service'} onclick={() => form.tip = 'Service'}>
        <Wrench size={16} strokeWidth={1.5} />Service
      </button>
    </div>

    <Input label="Nume" bind:value={form.nume} placeholder="ex. CU240S linia 3" bind:ref={numeEl}
           error={eroareNume} />

    <div class="pf-doua">
      <Input label="Client" bind:value={form.client} placeholder="ex. Continental" list="clients-list" />
      <Input label="Locație" bind:value={form.locatie} placeholder="ex. Timișoara" />
    </div>

    <!-- IDENTIFICAREA NU SE CERE LA CREARE. Cod, comanda, producator, folderul de
         wiki — niciunul nu se stie in clipa in care deschizi proiectul, iar un
         formular de creare cu noua campuri goale te invata sa-l inchizi.
         La EDITARE raman toate: bara laterala a paginii de proiect le AFISEAZA
         (`ProjectDetail`, „Producător / Cod proiect / Nr. comandă"), dar nu le
         scrie nicaieri — scoase de tot, ar fi ramas necompletabile din interfata,
         iar `vault_folder` e chiar cel pe care pagina de wiki iti spune sa-l
         setezi „prin editare proiect". -->
    {#if isEdit}
      <span class="pf-linie"></span>
      <div class="pf-doua">
        <Input label="Echipament principal" bind:value={form.echipament_principal} placeholder="ex. ACS880" />
        <Select label="Producător" bind:value={form.producator} options={PRODUCATORI} />
        <Input label="Cod proiect" bind:value={form.cod_proiect} placeholder="ex. P-042" />
        <Input label="Nr. comandă" bind:value={form.nr_comanda} />
      </div>
      <Input label="Folder wiki (vault)" bind:value={form.vault_folder} placeholder="wiki/job/projects/<slug>" />
      <div class="pf-doua">
        <Select label="Status" bind:value={form.status} options={STATUSES} />
        <!-- Ziua închiderii, nu ziua în care ai apăsat butonul: Calendarul taie
             perioadele proiectului aici (v35). Dacă închizi acum o lucrare
             terminată săptămâna trecută, o corectezi de aici. -->
        {#if form.status === 'finalizat'}
          <DatePicker label="Finalizat pe" bind:value={form.data_finalizare} />
        {/if}
      </div>
    {/if}

    <datalist id="clients-list">
      {#each clients as c}<option value={c.nume}></option>{/each}
    </datalist>
  </form>
  {#snippet footer()}
    <div class="modal-actions">
      <button type="button" class="pf-b pf-renunta" onclick={() => open = false}>Renunță</button>
      <!-- ACTIUNEA PRINCIPALA SPUNE CE FACE. „Creează" singur e un verb fara
           obiect; pe un buton citit intr-o secunda, obiectul e jumatate din sens.
           NU MAI E STINS CAND LIPSESTE NUMELE. Un buton stins nu spune de ce e
           stins: te uitai la el, la formular, si nu scria nicaieri ca numele e
           obligatoriu. Acum apesi (sau dai Enter) si afli — pe campul care
           trebuie reparat, nu intr-un toast care pleaca. `disabled` ramane doar
           cat tine salvarea, unde chiar previne o a doua trimitere. -->
      <button type="submit" form="pf-form" class="pf-b pf-creeaza" disabled={saving}>
        {isEdit ? 'Salvează proiectul' : 'Creează proiectul'}
      </button>
    </div>
  {/snippet}
</Modal>

<style>
  /* Titlul e in CORP, la 21/600, nu in antetul lui Modal (unde e 15/600 pe
     desktop si micro-eticheta majuscula pe telefon). Antetul ramane pentru X si
     — pe telefon — pentru gestul de tragere al foii; titlul lui se ascunde ca sa
     nu se scrie acelasi lucru de doua ori. */
  :global(.modal:has(.pf) .modal-title) { display: none; }
  @media (min-width: 769px) {
    :global(.modal:has(.pf)) { max-width: 480px; }
    :global(.modal:has(.pf) .modal-header) { border-bottom: none; padding-bottom: 0; }
    :global(.modal:has(.pf) .modal-body) { padding-top: var(--space-12); }
  }

  .pf { display: flex; flex-direction: column; gap: var(--space-md); }
  .pf-titlu {
    font-size: var(--font-h2);
    font-weight: var(--fw-semibold);
    letter-spacing: var(--tracking-tight);
    line-height: var(--lh-tight);
    color: var(--text);
  }

  .pf-tip { display: flex; gap: var(--space-6); }
  .pf-opt {
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    min-height: var(--ctrl-lg);
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    color: var(--text-secondary);
    font-size: var(--font-body);
    font-weight: var(--fw-semibold);
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .pf-opt:hover { color: var(--text); }
  .pf-opt:active { transform: scale(var(--press-scale)); }
  /* Text pe tenta ia intotdeauna varianta ADANCA. */
  .pf-opt.on {
    background: var(--accent-subtle);
    box-shadow: inset 0 0 0 1.5px var(--accent);
    color: var(--accent-deep);
  }

  .pf-doua { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-12); }
  .pf-linie { height: 1px; background: var(--border); }

  .pf-b {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: var(--ctrl-lg);
    padding: 0 var(--space-20);
    border-radius: var(--radius-sm);
    font-size: var(--font-body);
    font-weight: var(--fw-semibold);
    white-space: nowrap;
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .pf-b:active:not(:disabled) { transform: scale(var(--press-scale)); }
  .pf-b:disabled { opacity: 0.5; cursor: not-allowed; }
  .pf-renunta { color: var(--text-secondary); padding: 0 18px; }
  .pf-renunta:hover { background: var(--bg-hover); color: var(--text); }
  .pf-creeaza { background: var(--accent); color: var(--accent-text); }
  .pf-creeaza:hover:not(:disabled) { background: var(--accent-deep); }

  @media (max-width: 600px) { .pf-doua { grid-template-columns: 1fr; } }
  @media (max-width: 768px) {
    .pf-opt { min-height: var(--tap-sheet); }
    /* Prin `.modal-actions`, nu direct pe `.pf-b`: Modal pune pe copiii bareii
       `min-height: var(--tap-min)` cu aceeasi specificitate, deci fara parinte
       cine castiga ar depinde de ordinea foilor in bundle. */
    .modal-actions .pf-b { min-height: var(--tap-sheet); }
    .pf-renunta { background: var(--bg-elevated); }
  }
</style>
