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
  // SALUTUL A PLECAT DIN BARA, IAR ZIUA S-A MUTAT PE BOARD.
  //
  // Statea in `ui.pageHeader`, deci in bara de sus: `position: absolute;
  // left: 50%`, la o marime pe care n-o numea niciun token, si `display: none`
  // sub 768px. Trei lucruri nu mergeau deodata:
  //   — pe telefon nu se vedea nimic din el, deci Acasa era singurul ecran care
  //     nu spunea CE ZI E (celelalte pagini au titlu propriu; Acasa nu are,
  //     tocmai ca sa nu existe o banda in plus — cele doua reguli se anulau);
  //   — era scris o data, la montare: dashboardul deschis dimineata scria „Bună
  //     dimineața" si la sapte seara;
  //   — „Bună dimineața, Ion" e singurul titlu al paginii, dar nu e un titlu:
  //     nu spune nimic despre ce urmeaza sa faci.
  //
  // Bara ramane ce e — identitate si tema. Ziua trece pe capul boardului, unde
  // scria deja „Astăzi": zero randuri in plus, aceeasi informatie pe ambele
  // ecrane, si se recalculeaza singura (vezi TodayBoard).
  import TodayBoard from '../components/TodayBoard.svelte'
  import UrmatoareaIesire from '../components/UrmatoareaIesire.svelte'
</script>

<!-- `ruta-in`: ecranul SOSESTE, nu apare intre doua cadre. Aveau
     animatia doar Calendar, Planificator si Taskuri, deci jumatate din
     taburi se deschideau taiat si jumatate lin — raportat de Ion („nu
     toate taburile au animatii de deschidere"). Regula traieste in
     global.css, deci aici nu se adauga niciun CSS. -->
<div class="page lista-ingusta ruta-in">
  <UrmatoareaIesire />
  <TodayBoard />
</div>

<style>
  .page { padding: var(--space-lg); }

  @media (max-width: 620px) {
    .page { padding: var(--space-md); }
  }
</style>
