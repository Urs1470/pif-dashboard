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
  import { Clock, CheckCircle2 } from '@lucide/svelte'
  import Modal from './ui/Modal.svelte'
  import SelectorZi from './ui/SelectorZi.svelte'
  import SelectorOra from './ui/SelectorOra.svelte'
  import SolidIcon from './ui/SolidIcon.svelte'
  import { dueRing, esteDepasit, esteAzi } from '../lib/formatters.js'
  import { etichetaTermen } from '../lib/grupare.js'

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
    /** Redeschide foaia de adaugare pe taskul asta. Lipsa lui ASCUNDE randul. */
    onEditeaza = null,
    /** Lipsa lui ASCUNDE randul de stergere — o lista fara drum inapoi nu-l arata. */
    onSterge = null,
  } = $props()

  // ORA, DOAR PE TASKURILE PERSONALE (v41). Ion: „imi trebuie si ora sa pot seta
  // pentru taskuri, pana cand doar pentru cele personale." Coloana e pe
  // `global_tasks`, deci un task de proiect n-o are deloc; iar in sfera de munca
  // n-a fost cerută. Randul se randeaza doar cand apelantul da `onOra` SI taskul e
  // personal — doua conditii, fiindca ele spun lucruri diferite: prima „lista asta
  // stie sa salveze o ora", a doua „taskul asta are unde s-o ţină".
  const araOra = $derived(!!onOra && task?.sfera === 'personal')
  // `SelectorOra`, nu `<input type="time">`. Prima varianta folosea campul nativ, cu
  // argumentul c-ar fi „selectorul pe care mana il stie din tot telefonul". Ion:
  // „trebuie ora sa pot selecta cu un ceas, tot omogen cu designul" — si avea
  // dreptate: selectorul nativ vine cu fundalul, colturile si tipografia
  // sistemului, deci era singurul loc din aplicatie in care alegerea unei valori
  // arata ca alt program. Ceasul propriu e pe aceeasi carcasa ca `DatePicker`.
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
<!-- Randul de ora ARATA CA CELELALTE RANDURI. Ion: „butonul sa nu se deosebeasca de
     celelalte." Prima varianta lasa `SelectorOra` sa-si aduca propriul camp — cu
     eticheta deasupra, muchie interioara si 46px — deci intre randuri de 48 fara
     chenar sta un camp de formular: aceeasi actiune, alta clasa de obiect.
     Acum declansatorul lui se dezbraca si imprumuta `.ft-rand`, exact ca al lui
     `DatePicker` la „Alege ziua" (`.ft-dp`). Un singur fel de rand in foaie. -->
{#snippet randOra()}
  {#if araOra}
    <span class="ft-rand ft-ora">
      <Clock size={16} strokeWidth={1.5} />
      <span class="ft-ora-et">Ora</span>
      <SelectorOra value={oraLocal} eticheta={oraLocal || 'Setează'}
                   onchange={(v) => { oraLocal = v; onOra?.(v) }} />
    </span>
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
      <!-- „hold·1a". Taskul e REPERUL din capul foii (bifa + titlu + termen curent),
           dedesubt un SINGUR rand de replanificare, apoi actiunile, iar „Șterge"
           izolat sub o linie ca sa nu fie atins din greseala.
           CE N-A RAMAS: „Bifează" (o face glisarea si bifa din rand — Ion: „am
           destule locuri de unde pot face asta") si „Deschide" (o face atingerea
           randului). Un meniu care repeta ce e pe ecran e mai lung, nu mai capabil,
           iar aici lungimea costa: foaia soseste sub deget. -->
      <!-- Reperul poarta `--ring` pe bifa si pe termen: aceeasi severitate ca in
           lista din care ai prins gestul, ca sa stii pe CARE rand a prins. Bifa e
           DOAR reper (nu se bifeaza de aici — vezi mai sus). -->
      <div class="ft-referinta" style="--ring: {dueRing(task.data_scadenta)}">
        {#if task.status === 'done'}
          <CheckCircle2 size={20} class="ft-ref-bifat" />
        {:else}
          <span class="check-empty"></span>
        {/if}
        <span class="ft-ref-titlu">{task.titlu}</span>
        {#if task.data_scadenta}
          <span class="ft-ref-termen" class:sev={esteDepasit(task.data_scadenta) || esteAzi(task.data_scadenta)}>{etichetaTermen(task.data_scadenta)}</span>
        {/if}
      </div>

      <!-- UN SINGUR RAND DE ZILE, nu doua. „Mută pe mâine" + „Alege ziua" (doua
           randuri) se strang in `SelectorZi` — acelasi set ca in orice foaie sau
           panou care replanifica, cu ziua curenta aprinsa. Foaia se inchide la
           ALEGERE (`apoi`), fiindca gestul s-a incheiat; „Alege" deschide
           calendarul, care are foaia ca gazda. `aratScoate` e stins: reperul arata
           deja termenul, iar golirea lui se face din calendar. -->
      <div class="ft-replan">
        <span class="ft-sec">Replanifică</span>
        <SelectorZi value={task.data_scadenta || ''} aratScoate={false}
                    onalege={(v) => apoi(() => onZi?.(v || null))} />
      </div>

      <div class="ft-verbe">
        {#if onEditeaza}
          <!-- „Editează" redeschide FOAIA DE ADAUGARE cu titlul curent, selectat —
               aceeasi foaie care creeaza, fiindca e aceeasi intrebare („cum se
               numeste si cand?"). -->
          <button class="ft-rand" onclick={() => apoi(onEditeaza)}>
            <SolidIcon name="pencil" size={16} />
            Editează
          </button>
        {/if}

        {@render randOra()}
      </div>

      {#if onSterge}
        <!-- STERGEREA STA IZOLATA SUB O LINIE. Nu e o actiune egala cu celelalte:
             din ea pierzi ceva, si sta acolo unde se odihneste degetul pe o foaie.
             `--danger-deep`: `-deep` inseamna „mai mult contrast" in AMBELE teme,
             deci pe suprafata neutra a randului citeste mai tare decat `--danger`. -->
        <div class="ft-sterge-zona">
          <button class="ft-rand ft-sterge" onclick={() => apoi(onSterge)}>
            <SolidIcon name="trash" size={16} />
            Șterge
          </button>
        </div>
      {/if}
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
    padding-bottom: var(--space-6);
  }

  /* NICI FOAIA ASTA NU E TEXT DE SELECTAT, si e a doua centura, nu prima: randul
     din care vine gestul are deja `user-select: none` (vezi global.css), iar pragul
     a urcat la 420ms. Ramane pentru cazul in care degetul ridicat pe foaie e
     interpretat oricum ca long-press pe ea — foaia soseste SUB deget, deci e
     singurul strat din aplicatie care primeste un gest pe care nu l-a pornit. */
  .ft-verbe,
  .ft-plan,
  .ft-replan,
  .ft-referinta,
  .ft-sterge-zona {
    -webkit-user-select: none;
    user-select: none;
    -webkit-touch-callout: none;
  }
  .ft-verbe,
  .ft-plan {
    display: flex;
    flex-direction: column;
    gap: var(--space-2xs);
  }
  .ft-plan { gap: var(--space-6); }

  /* REPERUL: bifa (reper, nu buton) + titlu + termen curent. `--ring` de pe rand
     coloreaza si inelul si termenul — o singura sursa de severitate, ca in lista. */
  .ft-referinta {
    display: flex;
    align-items: center;
    gap: 11px;
    padding-bottom: var(--space-14);
    margin-bottom: var(--space-sm);
    border-bottom: 1px solid var(--border);
  }
  .ft-referinta :global(svg) { flex: none; color: var(--success); }
  .ft-ref-titlu {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--font-body);
    font-weight: var(--fw-semibold);
    color: var(--text);
  }
  /* Termenul, mono ca peste tot; `.sev` il aprinde din acelasi `--ring` ca bifa —
     exact reteta lui `.ts-val.sev` din foaia de detalii. */
  .ft-ref-termen {
    flex: none;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: var(--font-small);
    color: var(--text-dim);
  }
  .ft-ref-termen.sev { color: var(--ring); }

  /* Un SINGUR rand de replanificare, cu eticheta lui. `SelectorZi` isi aduce
     pastilele; aici doar asezarea si spatiul pana la actiuni. */
  .ft-replan {
    display: flex;
    flex-direction: column;
    gap: var(--space-sm);
    margin-bottom: var(--space-sm);
  }

  /* Stergerea, izolata sub o linie. */
  .ft-sterge-zona {
    margin-top: var(--space-6);
    padding-top: var(--space-6);
    border-top: 1px solid var(--border);
  }

  /* 48 = `--tap-sheet`, pragul de atingere DIN FOAIE (44 e podeaua de pe telefon,
     48 e cat cere o foaie — vezi tokens). Raza 10 = treapta de „control si rand",
     nu 14: astea sunt randuri intr-o suprafata, nu suprafete. */
  /* RANDURILE DE ACTIUNE SUNT CALME — fara fond, doar text + iconita, pe suprafata
     foii (handoff „hold·1a"). Reperul si pastilele de replanificare poarta suprafata;
     actiunile nu concureaza cu ele. Fondul apare la hover/apasare. */
  .ft-rand {
    display: flex;
    align-items: center;
    gap: 11px;
    min-height: var(--tap-sheet);
    padding: 0 var(--space-12);
    border-radius: var(--radius-sm);
    background: none;
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

  /* RANDUL DE ORA: se dezbraca la fel ca declansatorul de calendar, ca sa nu se deosebeasca de
     celelalte randuri (Ion). Ce rămâne din `SelectorOra` e doar declansatorul lui,
     fara cutie, fara eticheta si fara iconita proprie — iconita si cuvantul „Ora"
     le pune randul, in aceeasi ordine ca la vecinii lui. Valoarea sta la dreapta,
     in mono, unde stau toate valorile din foaie. */
  .ft-ora { padding: 0 var(--space-14); }
  .ft-ora-et { flex: 1; min-width: 0; }
  .ft-ora :global(.so) { width: auto; flex: none; gap: 0; }
  .ft-ora :global(.so-trigger) {
    width: auto;
    min-height: var(--tap-sheet);
    padding: 0;
    gap: 0;
    background: none;
    box-shadow: none;
    color: inherit;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-size: var(--font-body);
    font-weight: var(--fw-medium);
  }
  /* Ceasul lui ar fi al doilea langa cel al randului. */
  .ft-ora :global(.so-trigger svg) { display: none; }
  .ft-ora :global(.so-trigger:hover) { background: none; box-shadow: none; color: inherit; }

  /* Aici stateau `.ft-ora*` — cutia randului de ora, cu un `<input type="time">`
     inauntru. Au plecat odata cu el: `SelectorOra` isi aduce propriul declansator,
     in aceeasi reteta de camp ca `DatePicker`, deci o a doua cutie in jurul lui ar
     fi un chenar in chenar. */

  /* Un rand ca celelalte patru, deosebit DOAR de cerneala — nu de o linie sau de
     un spatiu in plus. Asa cere handoff-ul, si e si regula sistemului: cand doua
     lucruri se deosebesc prin inteles, nu prin clasa, diferenta o duce culoarea. */
  .ft-sterge { color: var(--danger-deep); }
  .ft-sterge :global(svg) { color: var(--danger-deep); }
  .ft-sterge:hover { background: var(--danger-subtle); color: var(--danger-deep); }
  .ft-sterge:hover :global(svg) { color: var(--danger-deep); }
</style>
