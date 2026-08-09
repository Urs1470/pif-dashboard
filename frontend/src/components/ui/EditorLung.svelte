<script>
  // UN SINGUR EDITOR DE TEXT, PENTRU TOATE CAMPURILE LUNGI.
  //
  // Observatii tehnice, Constatari, Actiuni si rezultat, nota unui task: erau
  // patru drumuri catre acelasi lucru — „scrie un text lung" — si nu se purtau
  // la fel. Notitele salvau la inchidere, cu drum inapoi prin toast; campurile de
  // proiect aveau „Anulează" si „Salvează", dar un click pe fundal (sau Escape,
  // sau X) inchidea pur si simplu, aruncand in tacere tot ce scrisesei. Acelasi
  // gest, doua intelesuri opuse, in aceeasi pagina.
  //
  // Acum e un singur shell: aceeasi cutie, acelasi cap, aceeasi bara de actiuni.
  // Se schimba doar titlul, textul si ce se intampla la scriere.
  //
  // REGULA: INCHIDEREA COMITE. Nu exista „Anulează" care arunca ce ai scris —
  // drumul inapoi e cel pe care aplicatia il foloseste deja peste tot: un toast
  // cu „Anulează" (vezi bifarea unui task, mutarea unui termen).
  import { untrack } from 'svelte'
  import Modal from './Modal.svelte'
  import Button from './Button.svelte'
  import RichTextEditor from './RichTextEditor.svelte'
  import { toast, toastUndo } from '../../stores/ui.svelte.js'

  // `salveaza(text)` scrie si reincarca. E chemata si INAINTE (cu textul nou) si
  // INAPOI (cu cel vechi, din „Anulează"), deci parintele da o singura functie,
  // nu doua — asa nu poate exista un drum de intoarcere care scrie altundeva
  // decat cel de dus.
  let {
    open = $bindable(false),
    titlu = '',
    valoare = '',
    tools = 'complet',
    placeholder = 'Scrie aici…',
    salveaza,
  } = $props()

  let ciorna = $state('')
  let original = ''
  let seSalveaza = $state(false)
  // Redeschidere dupa o eroare de scriere: pastreaza ce ai tastat (vezi `comite`).
  let reia = false

  // CIORNA SE IA LA DESCHIDERE, INAINTE SA SE RANDEZE EDITORUL.
  // `$effect.pre` fiindca `RichTextEditor` isi umple continteditable-ul la montare,
  // din valoarea pe care o are ATUNCI; un `$effect` normal ar rula dupa montare si
  // editorul s-ar deschide cu textul dinainte. `untrack` fiindca singura
  // dependenta e `open`: daca parintele reincarca datele cat timp scrii, ciorna
  // ta nu are voie sa fie inlocuita de sub degete.
  $effect.pre(() => {
    if (!open) return
    if (reia) { reia = false; return }
    const v = untrack(() => valoare) || ''
    ciorna = v
    original = v
  })

  function scurt(s, n = 38) {
    const t = (s || '').trim()
    return t.length > n ? `${t.slice(0, n - 1)}…` : t
  }

  // CE SCRIE IN COLTUL BAREI — si de ce NU scrie „salvat".
  //
  // Desenul cerea „salvat" la dreapta barei. Cuvantul ala presupune AUTOSALVARE:
  // ceva a scris deja, si te anunta. Editorul asta comite la INCHIDERE (regula de
  // sus), iar Ctrl+S / Ctrl+Enter salveaza SI inchid — deci n-ar exista nici macar
  // o clipa in care sa vezi „salvat" pe un editor deschis. Ar fi un cuvant care nu
  // se aprinde niciodata, sau — mai rau — unul care minte cat timp scrii.
  //
  // Ce e adevarat si folositor in coltul ala: daca inchiderea chiar are ce scrie.
  // „modificat" raspunde exact la intrebarea pe care si-o pune cineva inainte sa
  // traga foaia in jos, si se potriveste cu indiciul din bara de jos
  // („Închiderea salvează"). Cand n-ai schimbat nimic, nu scrie nimic — o eticheta
  // permanenta ar fi decor.
  const stare = $derived(seSalveaza ? 'se salvează…' : (ciorna !== original ? 'modificat' : ''))

  async function comite() {
    if (seSalveaza) return
    const text = ciorna
    const vechi = original
    // `scrie` se CAPTUREAZA acum. Toastul traieste 4 secunde, timp in care poti
    // deschide alt camp — iar `salveaza` e o proprietate, deci citita la apasarea
    // pe „Anulează" ar fi cea a campului NOU: textul vechi al observatiilor s-ar
    // scrie peste nota altui task.
    const scrie = salveaza
    if (text === vechi) { open = false; return }   // nimic de salvat, niciun zgomot
    seSalveaza = true
    try {
      await scrie(text)
      original = text
      open = false
      toastUndo(titlu ? `Salvat · ${scurt(titlu)}` : 'Salvat', {
        onUndo: async () => {
          try { await scrie(vechi) }
          catch (e) { toast(`Eroare: ${e.message}`, 'error') }
        },
      })
    } catch (e) {
      // Modalul se inchide SINGUR cand utilizatorul apasa X / fundal / Escape
      // (`onclose` vine dupa `open = false`), deci pe eroare pagina ar disparea cu
      // tot cu textul. Se redeschide cu ciorna intacta: cine a scris trei randuri
      // in hala trebuie sa le mai aiba dupa ce pica reteaua.
      reia = true
      open = true
      toast(`Eroare: ${e.message}`, 'error')
    } finally { seSalveaza = false }
  }
</script>

<Modal bind:open title={titlu} size="doc" onclose={comite}>
  <div class="ed-pagina">
    {#if open}
      <RichTextEditor bind:value={ciorna} {tools} {placeholder} {stare} onsave={comite} />
    {/if}
  </div>
  {#snippet footer()}
    <div class="ed-foot">
      <!-- `&nbsp;` inainte de separator: Svelte taie spatiul de la inceputul unui
           element inline, deci „salvează· Ctrl+Enter" se lipea. -->
      <span class="ed-hint">Închiderea salvează<span class="ed-key">&nbsp;· Ctrl+Enter</span></span>
      <div class="modal-actions">
        <Button loading={seSalveaza} onclick={comite}>Salvează</Button>
      </div>
    </div>
  {/snippet}
</Modal>

<style>
  /* Pagina de scris ocupa tot corpul modalului (vezi `.modal-doc .modal-body`,
     care nu deruleaza si nu are padding — scroll-ul e al editorului). */
  .ed-pagina { display: flex; flex-direction: column; flex: 1; min-height: 0; }

  .ed-foot { display: flex; align-items: center; gap: var(--space-sm); }
  .ed-hint {
    flex: 1;
    min-width: 0;
    font-size: var(--font-small);
    color: var(--text-secondary);
  }
  .ed-key { font-weight: var(--fw-semibold); }

  @media (max-width: 768px) {
    /* Butonul ocupa latimea (reteta `.modal-actions` de pe telefon), deci indiciul
       urca deasupra lui. `Ctrl+Enter` pleaca: pe telefon nu exista tastatura cu
       Ctrl, dar „închiderea salvează" ramane — acolo inchizi tragand foaia in jos,
       deci tocmai acolo trebuie sa stii ce inseamna gestul. */
    .ed-foot { flex-direction: column; align-items: stretch; gap: var(--space-sm); }
    .ed-key { display: none; }
  }
</style>
