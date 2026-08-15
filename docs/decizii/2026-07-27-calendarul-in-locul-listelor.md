# Cum arata o zi in Calendar (2026-07-27)

## Din CLAUDE.md

Prima versiune desena UN bloc per client, etichetat „Continental · 4 lucrari". Datele reale
au aratat de ce e gresit: din 12 perioade ale anului, **11 sunt la Continental**. Codam prin
culoare si grupare exact dimensiunea care nu variaza, si ascundeam dupa un click singura care
variaza — ce lucrare faci. Acum:

- **O bara per lucrare**, cu numele lucrarii (`implementari.eticheta`), nu al clientului.
- **Culoarea urmareste proiectul**, ca aceeasi lucrare sa fie acelasi lucru de la o zi la alta.
- **O lucrare de N zile e UN element de N zile latime**, nu N bucati. Vezi mai jos.
- **Banda (randul) e stabila pe toata durata lucrarii** — impachetare clasica pe intervale.
  Fara asta, o lucrare de doua zile apare pe randul 1 luni si pe randul 2 marti, iar bara nu
  mai citeste ca un singur lucru.
- **Antetul zilei are inaltime FIXA** (numar + captura deplasarii). Captura a stat initial pe
  rand propriu si impingea barele in jos doar in zilele de plecare — un rand in plus intr-o
  singura celula desincronizeaza toata saptamana.
- Captura deplasarii apare **doar in ziua in care incepe** si e manerul cu care muti toata
  iesirea; bara mutata singura muta doar lucrarea ei.
- Inaltimea celulei urmeaza numarul real de benzi din fereastra, ca lunile rare sa nu aiba
  jumatate de celula goala.
- Pe telefon (sub 620px) nu incape text intr-o celula de ~48px: raman barele colorate si
  numarul de lucrari, iar detaliul e in panoul de deasupra.
- Cand ziua selectata e goala, panoul arata **„Urmeaza"** — altfel ai naviga luni intregi
  goale ca sa afli cand iesi data viitoare.

## Din MEMORY.md

- **2026-07-27 (3) — Calendar, in locul celor trei liste.** Feedback Ion: „nu prea inteleg sensul,
  nu se poate mai elegant si mai interactiv?" — avea dreptate. Raspunsesem la o intrebare SPATIALA
  („unde sunt marti") cu trei liste de text (rand de cifre in Planificator, card pe Acasa, pagina
  /review). Aplicatia avea deja destule liste.
  **Inlocuite toate trei cu `/calendar`** (`Calendar.svelte` + `lib/calendarDates.js`, `GET /api/calendar`):
  grila lunara sau 2 saptamani, culoarea codeaza **clientul** (unitatea reala e DEPLASAREA, nu
  lucrarea), blocuri continue pe zile multiple, azi si zilele care cer o decizie marcate pe zi.
  Interactiune: click pe zi -> panou cu lucrarile si actiunile; **drag** unei perioade pe alta zi =
  replanificare cu pastrarea duratei; **drag** dintr-un proiect din banda „Fara data" pe o zi = creeaza
  perioada; buton „Muta" cu DatePicker pentru mobil (drag HTML5 nu merge la atingere).
  „Deplasari" = zile CONSECUTIVE la acelasi client (28-29-30 la Continental = 1 iesire, nu 3).
  Home pastreaza doar KPI-ul „Ce alunecă" (numar), care duce in calendar — detaliul sta pe ziua lui.
  Sterse: `Review.svelte`, `/api/review`, randul „Pe teren" din Plan.svelte, `client`/`locatie` de pe
  lane-urile `/api/plan` (calendarul are endpointul lui).
  **Lectie:** cand intrebarea e „unde/cand", raspunsul trebuie sa fie o harta sau un calendar, nu o
  lista. Verificat inainte de a construi cu un mockup pe date reale, aprobat de Ion.
