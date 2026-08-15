# „S-a facut" e despre PERIOADA, nu despre proiect (v39, 2026-08-07)

## Din CLAUDE.md

Ion: *„daca dau ca s-a facut in calendar la o implementare nu trebuie sa se marcheze
ca finalizat proiectul, trebuie sa ramana tot in perioada de pregatire. Dupa
implementare pot sa mai am de facut pv-uri sau altceva, sau poate va mai trebui de
facut vizita pe care nu stiu cand va fi."*

Panoul zilei intreba despre perioada („A trecut. S-a făcut?") si raspundea pe proiect:
butonul „Da" chema `PUT /api/proiecte/<id>` cu `status = 'finalizat'`. Doua obiecte
diferite pe acelasi buton.

Greseala se si auto-ascundea: un proiect inchis iese din „Proiecte fara perioada" (vezi
`neplanificate` in `/api/calendar`), deci exact vizita urmatoare — cea pe care n-o poti
inca data — nu mai avea de unde sa fie planificata. Deplasarea inchidea lucrarea.

`implementari.confirmata` (v39) tine raspunsul acolo unde s-a pus intrebarea.
`necesita_decizie` = a trecut **SI** `confirmata = 0` **SI** proiectul nu e inchis;
aceeasi conditie in `de_decis` (deciziile ramase in urma ferestrei) si in KPI-ul „de
clarificat". Statusul proiectului se schimba **doar** din formularul lui, langa
„Finalizat pe" — un singur loc, cu numele scris pe el.

Bifa se vede in panoul zilei ca eticheta verde „Făcut" (langa loc si faza — toate trei
sunt despre perioada) si in lista de perioade a proiectului. Anularea sta jos, intre
actiuni, si se numeste **„Nu s-a făcut"**: e raspunsul opus la aceeasi intrebare si nu
se poate confunda cu „Scoate", care scoate perioada din calendar.

Mutarea unei perioade **nu** reseteaza bifa: „am fost pe 5, nu pe 4" e o corectare de
consemnare, nu o replanificare.

## Din MEMORY.md

- **2026-08-07 — „S-a facut" e despre PERIOADA, nu despre proiect (v39).**
  Butonul „Da" din panoul zilei chema `PUT /api/proiecte {status:'finalizat'}`:
  intrebarea era despre perioada, raspunsul inchidea proiectul. Ion: dupa
  implementare mai raman PV-uri, si poate o vizita pe care inca n-o poti data.
  Greseala se auto-ascundea — proiectul inchis iese din `neplanificate`, deci
  exact vizita aia nu mai avea de unde sa fie planificata. Acum
  `implementari.confirmata`; `necesita_decizie` = trecut SI `confirmata=0` SI
  proiect nedeschis, aceeasi conditie in `de_decis`. Bifa se vede ca „Făcut"
  (panoul zilei + `ImplPeriods`), se scoate cu „Nu s-a făcut", si NU se pierde
  la mutarea perioadei. Statusul proiectului se schimba doar din formularul lui.
  Capcana obisnuita: `INSERT INTO implementari` din restore-ul de backup
  enumera coloanele explicit — fara `confirmata` acolo, un restore stergea
  bifele in tacere.
