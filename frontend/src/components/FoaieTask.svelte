<script>
  // FOAIA UNUI RAND DE TASK — un singur loc in care traiesc actiunile lui.
  //
  // DE CE EXISTA. Aceleasi doua intrebari — „ce fac cu taskul asta?" si „pe ce
  // zi?" — aveau patru raspunsuri, cate unul per lista:
  //   „Astăzi"      glisarea la stanga planifica DIRECT
  //   /tasks        deschide foaia taskului cu panoul de termen desfacut
  //   proiect       deschide FORMULARUL de editare (Titlu, Descriere, Categorie —
  //                 cand tot ce voiai era o zi)
  //   Planificator  descopera un panou de 118px, singurul loc ramas pe modelul
  //                 scos din restul aplicatiei (vezi `.gl-pista-s` in global.css)
  // Patru gazde pentru acelasi verb inseamna ca gestul se invata de patru ori.
  //
  // SI O GAURA, gasita citind codul, nu desenul: PE TELEFON UN TASK NU SE PUTEA
  // STERGE DELOC. Randul isi ascunde actiunile (`.task-actions { display: none }`
  // sub 768px, si in /tasks si in pagina proiectului), iar foaia taskului n-are
  // „Șterge" — desi comentariul de la `.gl-pista-s` spunea ca stergerea „a ramas
  // in foaia taskului". Nu ramasese nicaieri. Singurul lucru stergibil cu degetul
  // era un SUBTASK. De asta „Șterge" e in foaia asta.
  //
  // DOUA MODURI, O SINGURA FOAIE:
  //   'plan'    — doar ziua. Aici ajunge GLISAREA la stanga, care are UN verb
  //               scris pe pista („Planifică"), deci nu are voie sa puna un meniu
  //               intre gest si rezultat.
  //   'actiuni' — cele cinci actiuni din handoff. Aici ajunge APASAREA LUNGA: ea
  //               nu declara dinainte ce vrei, deci are dreptul sa intrebe.
  import { ExternalLink, CalendarSearch, Sunrise, Clock, X } from '@lucide/svelte'
  import Modal from './ui/Modal.svelte'
  import SelectorZi from './ui/SelectorZi.svelte'
  import DatePicker from './ui/DatePicker.svelte'
  import SolidIcon from './ui/SolidIcon.svelte'

  let {
    open = $bindable(false),
    /** {id, tip, titlu, data_scadenta, status} — randul pe care s-a facut gestul. */
    task = null,
    /** 'plan' (doar ziua) | 'actiuni' (cele cinci actiuni) */
    mod = 'actiuni',
    /** (iso|null) — null inseamna „scoate din calendar" */
    onZi,
    onMaine,
    /** ('HH:MM'|'') — '' scoate ora. Lipsa lui ASCUNDE randul de ora. */
    onOra = null,
    onBifa,
    onDeschide,
    /** Lipsa lui ASCUNDE randul de stergere — o lista fara drum inapoi nu-l arata. */
    onSterge = null,
  } = $props()

  const gata = $derived(task?.status === 'done' || task?.status === 'finalizat')

  // ORA, DOAR PE TASKURILE PERSONALE (v41). Ion: „imi trebuie si ora sa pot seta
  // pentru taskuri, pana cand doar pentru cele personale." Coloana e pe
  // `global_tasks`, deci un task de proiect n-o are deloc; iar in sfera de munca
  // n-a fost cerută. Randul se randeaza doar cand apelantul da `onOra` SI taskul e
  // personal — doua conditii, fiindca ele spun lucruri diferite: prima „lista asta
  // stie sa salveze o ora", a doua „taskul asta are unde s-o ţină".
  const araOra = $derived(!!onOra && task?.sfera === 'personal')
  // `<input type="time">` prin `Input`, nu un widget propriu: selectorul nativ de
  // ora e cel pe care mana il stie deja din tot telefonul, iar `Input` aduce inelul
  // de focus si fontul de 16px (sub el Safari mareste pagina la focus).
  // Se scrie la `change`, nu la fiecare tasta: un `<input type="time">` gol trece
  // prin valori partiale, si fiecare ar fi un PUT.
  let oraLocal = $state('')
  $effect(() => { oraLocal = task?.ora || '' })

  // Orice actiune INCHIDE foaia inainte sa lucreze. Invers (lucrezi, apoi inchizi)
  // se vede ca o foaie care sta o clipa peste lista deja schimbata — si la
  // „Șterge", unde randul de dedesubt chiar dispare, se citeste ca o zvacnire.
  function apoi(fn) {
    open = false
    fn?.()
  }
</script>

<!-- `iesireGest`: foaia n-are niciun camp de text, deci gestul in jos plus butonul
     „inapoi" de pe Android sunt destule — coltul din dreapta sus e, pe un telefon
     inalt, singurul loc la care nu ajungi fara sa muti mana din priza. Aceeasi
     alegere ca la foaia taskului din /tasks.
     Titlul foii E TITLUL TASKULUI: foaia se deschide dintr-un gest facut pe un
     rand anume, deci primul lucru pe care trebuie sa-l confirme e PE CARE rand a
     prins gestul. -->
<!-- Randul de ora, in AMBELE moduri: „la ce oră" e o intrebare despre CAND, exact
     ca ziua, deci sta langa ea si acolo unde gestul a cerut doar ziua, si in meniu.
     Foaia NU se inchide la alegerea orei (`apoi` nu se cheama): ora si ziua se pun
     de obicei una dupa alta, iar o foaie care pleaca dupa prima te pune s-o
     redeschizi pentru a doua. Se inchide cand alegi ZIUA — acolo gestul s-a
     incheiat. -->
{#snippet randOra()}
  {#if araOra}
    <label class="ft-ora">
      <Clock size={16} strokeWidth={1.5} />
      <span class="ft-ora-et">Ora</span>
      <input type="time" bind:value={oraLocal} onchange={() => onOra?.(oraLocal || '')} />
      {#if oraLocal}
        <button type="button" class="ft-ora-x" onclick={() => { oraLocal = ''; onOra?.('') }}
                aria-label="Scoate ora"><X size={14} strokeWidth={2.5} /></button>
      {/if}
    </label>
  {/if}
{/snippet}

{#if task}
  <Modal bind:open size="panou" iesireGest title={task.titlu || 'Task'}>
    {#if mod === 'plan'}
      <!-- Glisarea la stanga a spus deja verbul pe pista, deci foaia nu-l mai
           repeta: ce vine e direct setul de zile. `SelectorZi` e componenta pe
           care sistemul o cere in ORICE loc care replanifica. -->
      <div class="ft-plan">
        <span class="ft-sec">Planifică</span>
        <SelectorZi value={task.data_scadenta || ''} onalege={(v) => apoi(() => onZi?.(v))} />
        {@render randOra()}
      </div>
    {:else}
      <!-- CELE CINCI ACTIUNI, in ordinea din handoff: Bifează · Mută pe mâine ·
           Alege ziua · Deschide · Șterge. Ordinea e cea a frecventei, si de aceea
           „Șterge" e ultima — dar nu doar ultima, ci si SUB o linie (mai jos). -->
      <div class="ft-verbe">
        <button class="ft-rand" onclick={() => apoi(onBifa)}>
          <SolidIcon name="check" size={17} />
          {gata ? 'Redeschide' : 'Bifează'}
        </button>

        <button class="ft-rand" onclick={() => apoi(onMaine)}>
          <Sunrise size={16} strokeWidth={1.5} />
          Mută pe mâine
        </button>

        <!-- „Alege ziua" imprumuta declansatorul lui `DatePicker` pentru toata
             suprafata randului, exact ca al treilea slot din `SelectorZi` — deci
             calendarul se deschide de pe tot randul, nu doar de pe text. Foaia se
             inchide la ALEGERE, nu la atingerea randului: intre ele sta
             calendarul, si el are nevoie de foaie ca gazda. -->
        <span class="ft-rand ft-dp">
          <CalendarSearch size={16} strokeWidth={1.5} />
          <DatePicker value={task.data_scadenta || ''} eticheta="Alege ziua"
                      onchange={(v) => apoi(() => onZi?.(v || null))} />
        </span>

        {@render randOra()}

        {#if onDeschide}
          <button class="ft-rand" onclick={() => apoi(onDeschide)}>
            <ExternalLink size={16} strokeWidth={1.5} />
            Deschide
          </button>
        {/if}

        {#if onSterge}
          <!-- STERGEREA STA SINGURA SUB O LINIE. Nu e a cincea actiune egala: din
               ea pierzi ceva. Aceeasi ierarhie ca „Scoate din calendar" in
               `SelectorZi`, si acolo si aici din acelasi motiv.
               `--danger-deep`, cum cere handoff-ul: `-deep` inseamna „mai mult
               contrast" in AMBELE teme (pe intuneric mai deschis, pe lumina mai
               inchis — vezi nota de la `--accent-hover` in tokens.css), deci pe
               suprafata neutra a randului citeste mai tare decat `--danger`. -->
          <button class="ft-rand ft-sterge" onclick={() => apoi(onSterge)}>
            <SolidIcon name="trash" size={16} />
            Șterge
          </button>
        {/if}
      </div>
    {/if}
  </Modal>
{/if}

<style>
  /* Eticheta de sectiune: treapta de 12 majuscule a sistemului, aceeasi ca
     „SUBTASKURI" din foaia taskului si ca `.pan-sec` din panoul Planificatorului. */
  .ft-sec {
    display: block;
    font-size: var(--font-label);
    font-weight: var(--fw-semibold);
    text-transform: uppercase;
    letter-spacing: var(--tracking-label);
    color: var(--text-dim);
    padding-bottom: 6px;
  }

  /* NICI FOAIA ASTA NU E TEXT DE SELECTAT, si e a doua centura, nu prima: randul
     din care vine gestul are deja `user-select: none` (vezi global.css), iar pragul
     a urcat la 420ms. Ramane pentru cazul in care degetul ridicat pe foaie e
     interpretat oricum ca long-press pe ea — foaia soseste SUB deget, deci e
     singurul strat din aplicatie care primeste un gest pe care nu l-a pornit. */
  .ft-verbe,
  .ft-plan {
    display: flex;
    flex-direction: column;
    gap: 6px;
    -webkit-user-select: none;
    user-select: none;
    -webkit-touch-callout: none;
  }

  /* 48 = `--tap-sheet`, pragul de atingere DIN FOAIE (44 e podeaua de pe telefon,
     48 e cat cere o foaie — vezi tokens). Raza 10 = treapta de „control si rand",
     nu 14: astea sunt randuri intr-o suprafata, nu suprafete. */
  .ft-rand {
    display: flex;
    align-items: center;
    gap: 11px;
    min-height: var(--tap-sheet);
    padding: 0 14px;
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    color: var(--text);
    font-size: var(--font-body);
    font-weight: var(--fw-medium);
    text-align: left;
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .ft-rand :global(svg) { flex: none; color: var(--text-dim); }
  .ft-rand:hover { background: var(--accent-subtle); color: var(--accent-deep); }
  .ft-rand:hover :global(svg) { color: var(--accent-deep); }
  .ft-rand:active { transform: scale(var(--press-scale)); }

  /* Randul cu calendar: declansatorul lui `DatePicker` se intinde pe tot randul si
     isi pierde haina proprie (are deja una de la `.ft-rand`). Aceeasi retusare ca
     `.sz-dp` din `SelectorZi` — inclusiv iconita lui, care ar fi al doilea
     calendar langa al nostru. */
  .ft-dp { position: relative; padding: 0 14px; }
  .ft-dp :global(.dp) { flex: 1; min-width: 0; }
  .ft-dp :global(.dp-trigger) {
    width: 100%;
    min-height: var(--tap-sheet);
    padding: 0;
    gap: 0;
    background: none;
    border: none;
    box-shadow: none;
    color: inherit;
    font-family: inherit;
    font-size: var(--font-body);
    font-weight: var(--fw-medium);
  }
  .ft-dp :global(.dp-trigger svg) { display: none; }
  .ft-dp :global(.dp-trigger:hover) { background: none; color: inherit; }

  /* RANDUL DE ORA. Aceeasi cutie ca `.ft-rand` — 48 inalt, raza 10, suprafata 2 —
     fiindca e acelasi fel de obiect: un rand din foaie. Ce difera e ca el nu
     EXECUTA, ci ţine o valoare, deci nu are `:active` care sa-l stranga.
     `<input type="time">` brut, cu bunastiinta si contrar regulii „NU input brut in
     formulare": aici nu e un formular, e un rand de control, iar `Input` ar aduce
     eticheta si cutia LUI peste cea de aici. Ce trebuia luat de la `Input` — 16px,
     ca Safari sa nu mareasca pagina la focus — se scrie explicit mai jos. */
  .ft-ora {
    display: flex;
    align-items: center;
    gap: 11px;
    min-height: var(--tap-sheet);
    padding: 0 14px;
    border-radius: var(--radius-sm);
    background: var(--bg-elevated);
    color: var(--text);
    font-size: var(--font-body);
    font-weight: var(--fw-medium);
    cursor: pointer;
  }
  .ft-ora :global(svg) { flex: none; color: var(--text-dim); }
  .ft-ora-et { flex: 1; min-width: 0; }
  .ft-ora input {
    flex: none;
    background: none;
    border: none;
    outline: none;
    color: var(--text);
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    /* 16px: sub atat Safari mareste pagina la focus si foaia sare. */
    font-size: var(--font-input-mobile);
    text-align: right;
  }
  .ft-ora input:focus-visible { box-shadow: var(--focus-ring); border-radius: var(--radius-xs); }
  /* Ora goala: WebView-ul deseneaza „--:--" palid, dar declansatorul de ceas al
     lui poate lipsi — de asta randul intreg e `<label>`, deci atingerea oriunde pe
     el deschide selectorul. */
  .ft-ora-x {
    display: grid;
    place-items: center;
    flex: none;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-full);
    color: var(--text-dim);
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .ft-ora-x:hover { background: var(--danger-subtle); color: var(--danger-deep); }

  /* Un rand ca celelalte patru, deosebit DOAR de cerneala — nu de o linie sau de
     un spatiu in plus. Asa cere handoff-ul, si e si regula sistemului: cand doua
     lucruri se deosebesc prin inteles, nu prin clasa, diferenta o duce culoarea. */
  .ft-sterge { color: var(--danger-deep); }
  .ft-sterge :global(svg) { color: var(--danger-deep); }
  .ft-sterge:hover { background: var(--danger-subtle); color: var(--danger-deep); }
  .ft-sterge:hover :global(svg) { color: var(--danger-deep); }
</style>
