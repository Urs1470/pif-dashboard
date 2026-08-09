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

  // ===== BARA DE JOS STA DEASUPRA TASTATURII (telefon) =====
  //
  // Pe telefon modalul e foaie pe tot ecranul (100dvh), iar `dvh` urmareste bara
  // de adresa, NU tastatura: cand tastatura se ridica, footerul cu „Salvează"
  // ramane sub ea si nu poti salva fara sa inchizi intai tastatura.
  //
  // Aceeasi masuratoare ca bara de unelte din `RichTextEditor` (care se ridica
  // deja): `visualViewport` e singura sursa care stie CAT acopera tastatura.
  // Cele doua folosesc aceeasi formula, deci nu se pot desincroniza — iar bara
  // de jos se aseaza DEASUPRA barei de unelte (ea vrea sa fie langa tastatura,
  // langa deget), la `kb + inaltimea ei`. Inaltimea se MASOARA, nu se scrie de
  // mana: paddingul barei se schimba cu tastatura (isi pierde `--safe-bottom`).
  //
  // Unde `visualViewport` lipseste (browsere vechi), `kb` ramane 0 si nu se
  // schimba nimic fata de inainte.
  let kb = $state(0)
  let hBara = $state(0)
  let pagEl = $state(null)
  $effect(() => {
    if (!open) { kb = 0; return }
    const vv = window.visualViewport
    if (!vv) return
    const masoara = () => {
      // Rotunjit si prins la 0: valoarea oscileaza cu subpixeli la derulare.
      const acoperit = window.innerHeight - vv.height - vv.offsetTop
      kb = acoperit > 24 ? Math.round(acoperit) : 0
      // `.rte-toolbar` e fixata la `bottom: kb` (vezi RichTextEditor); bara de
      // jos trebuie sa inceapa exact unde se termina ea.
      if (kb > 0) hBara = pagEl?.querySelector('.rte-toolbar')?.offsetHeight || 0
    }
    masoara()
    vv.addEventListener('resize', masoara)
    vv.addEventListener('scroll', masoara)
    return () => {
      vv.removeEventListener('resize', masoara)
      vv.removeEventListener('scroll', masoara)
    }
  })
</script>

<Modal bind:open title={titlu} size="doc" onclose={comite}>
  <div class="ed-pagina" bind:this={pagEl}>
    {#if open}
      <RichTextEditor bind:value={ciorna} {tools} {placeholder} {stare} onsave={comite} />
    {/if}
  </div>
  {#snippet footer()}
    <!-- `onmousedown|preventDefault` (pe wrapper, ca la butoanele din bara
         editorului): fara el, atingerea pe „Salvează" ar lua intai focusul din
         editor — tastatura ar porni sa coboare si bara s-ar muta de sub deget
         inainte sa se inregistreze clicul. -->
    <div class="ed-foot" class:ridicat={kb > 0}
      style:--kb="{kb}px" style:--h-bara="{hBara}px"
      onmousedown={(e) => e.preventDefault()} role="presentation">
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

    /* CU TASTATURA RIDICATA, „Salvează" vine deasupra ei — fix peste bara de
       unelte a editorului (fixata la `bottom: --kb`), deci stiva de langa deget
       e: tastatura, unelte, salvare. Bara isi aduce fundal si linie proprii:
       iese din `.modal-footer` (care ramane sub tastatura) si altfel textul
       editorului s-ar citi prin ea. Indiciul se ascunde: cat timp scrii, tot
       ecranul ramas e al textului, iar „închiderea salvează" e lectia gestului
       de tras foaia — gest pe care nu-l faci cu tastatura ridicata. */
    .ed-foot.ridicat {
      position: fixed;
      left: 0;
      right: 0;
      /* --kb (inaltimea tastaturii) si --h-bara (bara de unelte a editorului)
         vin din `style:` pe invelis, masurate la rulare; implicitele de aici
         exista doar ca variabilele sa fie DEFINITE si in CSS, nu numai din JS
         (auditul de design cere o definitie pentru orice token folosit). */
      --kb: 0px;
      --h-bara: 0px;
      bottom: calc(var(--kb) + var(--h-bara));
      z-index: 3;   /* acelasi strat ca `.rte-toolbar` — nu se suprapun */
      margin: 0;
      padding: var(--space-xs) var(--space-md);
      background: var(--bg-surface);
      border-top: 1px solid var(--border);
    }
    .ed-foot.ridicat .ed-hint { display: none; }
  }
</style>
