<script>
  import Modal from './Modal.svelte'

  // CE SCRIE PE BUTON E SINGURUL LUCRU CITIT.
  //
  // Dialogul asta se citeste in doua secunde, iar unul dintre cele cinci locuri
  // care il folosesc sterge un proiect cu tot cu taskurile lui. Deci butonul
  // poarta VERBUL SI OBIECTUL („Sterge proiectul"), niciodata „OK" sau
  // „Confirma" — cuvinte care nu spun ce dispare.
  //
  // Si intrebarea se pune impreuna cu CE DISPARE ODATA CU EA: „7 taskuri si 2
  // perioade" e un numar care decide actiunea, deci are voie. Interdictia din
  // sistem e impotriva statisticilor de umplutura, nu impotriva consecintelor.
  //
  // Impartirea campurilor urmeaza asta: `title` e INTREBAREA (21/600), `message`
  // e ce dispare (15; 16 pe telefon, din `--font-body`). Fara iconita de alerta —
  // cuvintele o spun deja, iar un triunghi rosu langa un buton rosu e a doua oara
  // acelasi lucru.
  let {
    open = $bindable(false),
    title = 'Confirmare',
    message = 'Ești sigur?',
    confirmLabel = 'Confirmă',
    cancelLabel = 'Renunță',
    danger = true,
    onconfirm,
  } = $props()
  let busy = $state(false)

  async function confirm() {
    busy = true
    try {
      await onconfirm?.()
      open = false
    } finally { busy = false }
  }
</script>

<!-- `title` ramane dat lui Modal fiindca de acolo iese `aria-label`-ul dialogului;
     antetul VIZIBIL e ascuns mai jos, ca intrebarea sa nu se scrie de doua ori. -->
<Modal bind:open {title} size="sm">
  <div class="confirma">
    <h2 class="c-titlu">{title}</h2>
    <p class="c-msg">{message}</p>
    <div class="c-actiuni">
      <button class="c-b c-renunta" onclick={() => open = false}>{cancelLabel}</button>
      <button class="c-b c-confirma" class:neutru={!danger} class:lucreaza={busy}
              disabled={busy} aria-busy={busy} onclick={confirm}>
        {#if busy}<span class="c-rotita" aria-hidden="true"></span>{/if}
        <span class="c-eticheta">{confirmLabel}</span>
      </button>
    </div>
  </div>
</Modal>

<style>
  /* ANTETUL LUI MODAL NU SE RANDEAZA AICI — intrebarea E titlul.
     Modalul isi scrie titlul la 15/600 pe desktop si ca micro-eticheta majuscula
     pe telefon; amandoua ar fi a doua copie a intrebarii, cu alta greutate, la
     doi centimetri de prima. Se ascunde prin `:has()` (tehnica pe care Modal o
     foloseste deja intern pentru `.modal:has(.modal-footer)`), NU prin editarea
     lui: e o componenta partajata, iar aici e nevoie de o exceptie, nu de o
     regula noua pentru toata lumea.

     PE TELEFON SE ASCUNDE DOAR TITLUL, nu antetul: gestul de tragere al foii e
     legat de `.modal-header` (`trageJos`), deci un antet ascuns ar lasa manerul
     de sus promitand o miscare care nu se mai intampla — exact greseala pe care
     Modal si-o reproseaza in propriile comentarii. Pe desktop nu exista gest, si
     nici X in desen: iesirea sigura e „Renunta", langa actiune. */
  :global(.modal:has(.confirma) .modal-title) { display: none; }

  @media (min-width: 769px) {
    :global(.modal:has(.confirma)) { max-width: 460px; }
    :global(.modal:has(.confirma) .modal-header) { display: none; }
  }

  .confirma {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .c-titlu {
    font-size: var(--font-h2);
    font-weight: var(--fw-semibold);
    letter-spacing: var(--tracking-tight);
    line-height: var(--lh-tight);
    color: var(--text);
    text-wrap: pretty;
  }

  .c-msg {
    font-size: var(--font-body);
    line-height: var(--lh-normal);
    color: var(--text-secondary);
    text-wrap: pretty;
  }

  /* Butoanele sunt scrise aici, nu prin `<Button>`: nu sunt controale generice,
     sunt cele doua roluri fixe ale dialogului, si intre desktop si telefon li se
     schimba ORDINEA (distructivul urca), inaltimea (44 -> 48) si haina renuntarii
     (fantoma -> suprafata a doua). Niciuna din cele trei nu se poate exprima prin
     variantele lui `Button`, iar geometria ceruta de desen (44/48, raza 10,
     padding 18) nu e a lui. */
  .c-actiuni {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-sm);
    margin-top: var(--space-12);
  }

  .c-b {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 44px;
    padding: 0 18px;
    /* Raza de CONTROL (10), nu de suprafata. */
    border-radius: var(--radius-sm);
    font-size: var(--font-body);
    font-weight: var(--fw-semibold);
    white-space: nowrap;
    cursor: pointer;
    transition: var(--transition-pressable);
  }
  .c-b:active:not(:disabled) { transform: scale(var(--press-scale)); }
  .c-b:disabled { cursor: not-allowed; }

  .c-renunta { color: var(--text-secondary); }
  .c-renunta:hover { background: var(--bg-hover); color: var(--text); }

  .c-confirma {
    background: var(--danger);
    color: var(--accent-text);
  }
  /* Hoverul merge spre varianta ADANCA, nu pe opacitate: opacitatea s-ar inmulti
     peste o cerneala deja la limita. Aceeasi regula ca la `.btn-danger`. */
  .c-confirma:hover:not(:disabled) { background: var(--danger-deep); }
  .c-confirma.neutru { background: var(--accent); }
  .c-confirma.neutru:hover:not(:disabled) { background: var(--accent-deep); }

  /* Eticheta ramane in flux cat timp se lucreaza (doar invizibila), ca butonul sa
     nu-si schimbe latimea sub deget in clipa in care ai apasat pe el. */
  .lucreaza .c-eticheta { visibility: hidden; }
  .c-rotita {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 14px;
    height: 14px;
    margin: -7px 0 0 -7px;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: c-invarte 0.6s linear infinite;
  }
  @keyframes c-invarte { to { transform: rotate(360deg); } }

  @media (max-width: 768px) {
    /* ORDINEA SE INVERSEAZA: distructivul sus, „Renunta" jos — sub degetul mare
       ajunge cel din care nu pierzi nimic. `column-reverse` schimba doar ce vezi;
       markupul (si deci ordinea de Tab) ramane Renunta -> Sterge, ca pe desktop. */
    .c-actiuni {
      flex-direction: column-reverse;
      margin-top: var(--space-sm);
    }
    .c-b { height: var(--tap-sheet); }
    /* Pe foaie fantoma n-ar mai avea de la ce sa se deosebeasca: langa un buton
       plin, pe toata latimea, un dreptunghi fara fond se citeste ca text. */
    .c-renunta { background: var(--bg-elevated); }
  }
</style>
