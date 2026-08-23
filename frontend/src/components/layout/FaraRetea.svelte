<script>
  // „FARA RETEA" STA IN CADRU, NU INTR-UN TOAST.
  //
  // Un toast confirma o actiune si pleaca dupa patru secunde; asta e o STARE
  // care tine pana se schimba semnalul, si care schimba intelesul a tot ce vezi
  // sub ea (listele vin din cache, salvarile nu pleaca). Deci sta acolo unde
  // stau faptele permanente ale aplicatiei, langa marca: in antet pe telefon, in
  // piciorul barei laterale pe desktop. Doua locuri, o singura componenta —
  // altfel textul explicativ ar exista in doua variante.
  //
  // `role="status"` + `aria-live` fiindca apare fara ca tu sa fi facut ceva.
  import { CloudOff } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import { reteaua } from '../../lib/retea.svelte.js'
  import { motionDuration, DUR_BASE, EASE } from '../../lib/motion.svelte.js'

  // 'chip' — bucata scurta din antet; 'rand' — de latimea barei laterale.
  let { varianta = 'chip' } = $props()
</script>

{#if !reteaua.online}
  <span class="fara-retea" class:rand={varianta === 'rand'} role="status" aria-live="polite"
        title="Ce vezi vine din memoria telefonului. Ce salvezi nu pleacă până revine semnalul."
        transition:fly={{ y: -6, duration: motionDuration(DUR_BASE), easing: EASE }}>
    <CloudOff size={15} strokeWidth={1.5} />
    <span class="fr-text">Fără rețea</span>
  </span>
{/if}

<style>
  /* Chip de STARE, deci in tenta de restant cu cerneala adanca — nu fill plin:
     nu e o eroare care tocmai s-a intamplat, e o conditie in care lucrezi.
     Treapta de control (13/600), ca orice altceva asezat in rand cu marca. */
  .fara-retea {
    display: inline-flex;
    align-items: center;
    gap: var(--space-6);
    flex: none;
    height: var(--ctrl-xs);
    padding: 0 var(--space-10);
    margin-right: var(--space-sm);
    border-radius: var(--radius-xs);
    background: var(--danger-subtle);
    color: var(--danger-deep);
    font-size: var(--font-control);
    font-weight: var(--fw-semibold);
    white-space: nowrap;
  }
  /* In bara laterala chipul tine toata latimea si nu mai are margine la dreapta:
     acolo e un rand intre alte randuri, nu o bucata asezata langa altceva. */
  .fara-retea.rand {
    display: flex;
    width: 100%;
    height: var(--ctrl-sm);
    margin-right: 0;
    border-radius: var(--radius-sm);
  }

  @media (max-width: 768px) {
    /* Chipul NU se scurteaza la iconita pe telefon: telefonul e exact locul in
       care ramai fara semnal, deci acolo cuvintele conteaza cel mai mult. Daca
       nu incape pe un rand, bara are voie sa se rupa — asta si face antetul
       (`flex-wrap: wrap`), iar o bara mai inalta e un semn in plus, nu o
       problema. */
    .fara-retea { height: var(--ctrl-sm); }
  }
</style>
