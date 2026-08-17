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
  import { ExternalLink, CalendarSearch, Sunrise } from '@lucide/svelte'
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
    onBifa,
    onDeschide,
    /** Lipsa lui ASCUNDE randul de stergere — o lista fara drum inapoi nu-l arata. */
    onSterge = null,
  } = $props()

  const gata = $derived(task?.status === 'done' || task?.status === 'finalizat')

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
{#if task}
  <Modal bind:open size="panou" iesireGest title={task.titlu || 'Task'}>
    {#if mod === 'plan'}
      <!-- Glisarea la stanga a spus deja verbul pe pista, deci foaia nu-l mai
           repeta: ce vine e direct setul de zile. `SelectorZi` e componenta pe
           care sistemul o cere in ORICE loc care replanifica. -->
      <div class="ft-plan">
        <span class="ft-sec">Planifică</span>
        <SelectorZi value={task.data_scadenta || ''} onalege={(v) => apoi(() => onZi?.(v))} />
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

  .ft-verbe,
  .ft-plan { display: flex; flex-direction: column; gap: 6px; }

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

  /* Un rand ca celelalte patru, deosebit DOAR de cerneala — nu de o linie sau de
     un spatiu in plus. Asa cere handoff-ul, si e si regula sistemului: cand doua
     lucruri se deosebesc prin inteles, nu prin clasa, diferenta o duce culoarea. */
  .ft-sterge { color: var(--danger-deep); }
  .ft-sterge :global(svg) { color: var(--danger-deep); }
  .ft-sterge:hover { background: var(--danger-subtle); color: var(--danger-deep); }
  .ft-sterge:hover :global(svg) { color: var(--danger-deep); }
</style>
