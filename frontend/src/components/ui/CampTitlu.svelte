<script>
  // CAMPUL PRINCIPAL AL UNUI FORMULAR — titlul lucrului pe care il creezi.
  //
  // Ion: „modalul de creare task nu are nevoie de descriere, nu folosesc
  // niciodata acel camp; in schimb putem lucra la campul cel mai important,
  // adica titlul taskului."
  //
  // Pana acum titlul era un `<Input>` ca oricare altul: aceeasi inaltime,
  // acelasi 15px, aceeasi eticheta de 12px deasupra ca „Categorie" sau
  // „Recurență". Adica singurul camp fara de care butonul „Creează" nici nu se
  // aprinde arata exact ca cele trei pe care le lasi goale de fiecare data.
  // Ierarhia dintr-un formular nu se face din ordine, se face din MARIME.
  //
  // Trei lucruri care il despart de un `<Input>`, si niciunul nu e decor:
  //
  //  1. E MARE (`--font-h2`, treapta „numele lucrului deschis" din tokens) si
  //     n-are eticheta. Un camp de 21px cu un indiciu scris in el nu mai are
  //     nevoie sa i se spuna „TITLU" deasupra: e evident ce e, si o eticheta in
  //     plus doar impinge campul mai jos, sub tastatura.
  //  2. CRESTE IN INALTIME. E un `<textarea>` tocmai pentru asta: „Verificat
  //     tensiunile pe contrapanoul A12 inainte de PIF" are 58 de caractere, iar
  //     pe un ecran de 390px la 21px intra vreo 18 — intr-un `<input>` restul
  //     pleaca lateral, deci scrii un titlu pe care nu-l poti CITI in timp ce-l
  //     scrii. Aici randurile se aduna sub deget.
  //  3. ENTER TRIMITE, nu face rand nou. Un titlu n-are randuri; `<textarea>` e
  //     ales pentru cum se aseaza textul, nu ca sa se scrie poezii in el.
  //     `enterkeyhint="done"` schimba si tasta de pe tastatura telefonului, ca
  //     sa scrie ce face.
  //
  // `ref` e legabil din acelasi motiv ca la `Input`: cine deschide formularul
  // trebuie sa poata pune focusul pe campul care conteaza.
  let {
    value = $bindable(''),
    ref = $bindable(null),
    placeholder = '',
    randMax = 4,
    onenter = null,
    ...rest
  } = $props()

  // INALTIMEA SE MASOARA, NU SE GHICESTE. `rows` ar fi o inaltime fixa (deci
  // sau un gol sub un titlu scurt, sau o taietura la unul lung); aici campul are
  // exact cate randuri are textul, pana la `randMax` — peste atat derulezi,
  // fiindca un camp care creste la nesfarsit impinge butoanele afara din foaie.
  //
  // `height = 'auto'` INAINTE de citire nu e o superstitie: fara el `scrollHeight`
  // ramane la inaltimea deja setata si campul nu se mai poate MICSORA cand stergi
  // un rand — creste o data si ramane crescut.
  function creste(el) {
    if (!el) return
    el.style.height = 'auto'
    const rand = parseFloat(getComputedStyle(el).lineHeight) || 28
    const captuseala = el.offsetHeight - el.clientHeight + 20   // 10px sus + 10px jos
    el.style.height = Math.min(el.scrollHeight, rand * randMax + captuseala) + 'px'
  }

  // Se re-masoara si cand valoarea vine din AFARA (formularul se deschide cu un
  // titlu existent, sau `resetForm` il goleste), nu doar cand tastezi.
  $effect(() => {
    value
    creste(ref)
  })

  function laTasta(e) {
    if (e.key !== 'Enter') return
    e.preventDefault()
    onenter?.()
  }
</script>

<textarea
  class="camp-titlu"
  bind:this={ref}
  bind:value
  {placeholder}
  rows="1"
  enterkeyhint="done"
  autocapitalize="sentences"
  autocomplete="off"
  spellcheck="false"
  oninput={(e) => creste(e.currentTarget)}
  onkeydown={laTasta}
  {...rest}
></textarea>

<style>
  /* Aceeasi reteta de camp ca `Input`/`Textarea` (suprafata a doua, muchie
     interioara de 1px, raza de control, focus la 1,5px accent) — schimba doar
     treapta de text si faptul ca inaltimea o scrie JS-ul. Un al doilea desen de
     camp ar fi exact felul de incoerenta pe care o prinde `audit_design.py`. */
  .camp-titlu {
    padding: 10px 12px;
    background: var(--bg-elevated);
    border: none;
    border-radius: var(--radius-sm);
    box-shadow: inset 0 0 0 1px var(--border);
    color: var(--text);
    font-family: inherit;
    font-size: var(--font-h2);
    font-weight: var(--fw-semibold);
    line-height: var(--lh-snug);
    /* Manerul de redimensionare al lui `<textarea>` n-are ce cauta pe un camp
       care isi masoara singur inaltimea — ar promite un reglaj care se pierde
       la prima tasta apasata. */
    resize: none;
    overflow-y: auto;
    min-height: var(--tap-sheet);
    transition: box-shadow var(--dur-fast) var(--ease);
  }
  .camp-titlu:hover:not(:disabled):not(:focus) {
    box-shadow: inset 0 0 0 1px var(--border-strong);
  }
  .camp-titlu:focus {
    outline: none;
    box-shadow: inset 0 0 0 1.5px var(--accent);
  }
  /* Indiciul NU ia greutatea titlului: la 600 un placeholder arata ca un titlu
     deja scris, si nu se mai vede daca ai completat sau nu. */
  .camp-titlu::placeholder {
    color: var(--text-dim);
    font-weight: var(--fw-normal);
  }
</style>
