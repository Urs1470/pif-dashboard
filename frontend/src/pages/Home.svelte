<script>
  // Acasa = „cu ce incep ziua", atat.
  //
  // Aici au stat patru contoare (proiecte active, urgente, finalizate in 7 zile,
  // ce aluneca) si o lista de taskuri urgente. Ion, 2026-07-27: „cardurile astea
  // sincer nu am nevoie de ele" si „partea de jos cu taskuri urgente nu am nevoie
  // de ea". Ce foloseste e boardul de azi: „este comod pentru a ma concentra pe
  // anumite taskuri si asa imi incep eu ziua."
  //
  // Nu se pierde niciun semnal: „ce aluneca" traieste in Calendar ca „de
  // clarificat", pe ziua respectiva, unde poti si actiona; „ce urmeaza" e tot
  // acolo. Contorul de proiecte active devenise oricum „cate nu sunt inchise"
  // dupa ce statusurile s-au redus la doua (v31).
  //
  // Fara contoare, pagina nu mai are ce cere de la API: TodayBoard isi incarca
  // singur datele din stores/agenda. Asa ca /api/dashboard/home nu se mai apeleaza
  // de nicaieri.
  import { onMount, onDestroy } from 'svelte'
  import TodayBoard from '../components/TodayBoard.svelte'
  import { ui } from '../stores/ui.svelte.js'

  function greeting() {
    const h = new Date().getHours()
    if (h < 12) return 'Bună dimineața'
    if (h < 18) return 'Bună ziua'
    return 'Bună seara'
  }

  function todayRO() {
    return new Date().toLocaleDateString('ro-RO', {
      weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
    })
  }

  onMount(() => {
    // Salutul sta in bara de sus (header) — nu avem banda separata pe pagina.
    ui.pageHeader = { title: `${greeting()}, Ion`, subtitle: todayRO() }
  })
  onDestroy(() => { ui.pageHeader = { title: '', subtitle: '' } })
</script>

<div class="page">
  <TodayBoard />
</div>

<style>
  .page { padding: var(--space-lg); }

  @media (max-width: 620px) {
    .page { padding: var(--space-md); }
  }
</style>
