# Un proiect inchis se opreste in ziua inchiderii (v35, 2026-07-30)

## Din CLAUDE.md

Ion: *„eu am finalizat un proiect de ieri dar a mai aparut si pe azi proiectul cu motoare
extruder."*

Prima incercare taia perioadele unui proiect `finalizat` la **ziua de azi**. Reperul e insa
ziua in care ai INCHIS, nu ziua in care te uiti: proiectul avea perioada 29->30, inchisa pe
29, iar 30 rămânea afisat. Diferenta se vede doar cand inchizi inainte de vreme — exact
cazul care conteaza.

`proiecte.data_finalizare` (v35) e acel reper. Backfill din `updated_at` pentru cele deja
inchise — cea mai buna dovada disponibila si s-a potrivit (proiectul cu motoare avea
`updated_at = 2026-07-29T16:19`).

**Invariantul:** data exista daca si numai daca statusul e `finalizat`. Se pune automat la
inchidere (azi), se STERGE la redeschidere. Fara invariant, formularul tine data agatata
cand redeschizi — `DatePicker`-ul se ascunde, dar valoarea rămâne in `form` — si la o
re-inchidere ai reveni in tacere la ziua veche.

Se poate corecta: cand inchizi acum o lucrare terminata saptamana trecuta, campul
**„Finalizat pe"** apare in formularul de proiect (doar la status `finalizat`). In bara
laterala a paginii de proiect, celula „Urmatoarea perioada" — care pentru un proiect inchis
n-avea decat „Neplanificat" de spus — arata **„Finalizat · <data> · ieri"**. Un camp care
decide ce vezi in Calendar nu are voie sa fie invizibil.

Taierea e doar la CITIRE (`/api/calendar`, `/api/export/ics`); baza rămâne neatinsa, iar
Ganttul propriu al proiectului arata toate perioadele.

## Din MEMORY.md

- **2026-07-30 — Un proiect inchis se opreste in ziua INCHIDERII, nu azi (v35).** Prima
  incercare taia perioadele proiectelor `finalizat` la `date('now')`. Ion: „am finalizat un
  proiect de ieri dar a mai aparut si pe azi". Perioada era 29->30, inchisa pe 29 — deci
  ziua 30 rămânea. Reperul corect e `proiecte.data_finalizare` (v35), backfill din
  `updated_at` (a nimerit: proiectul cu motoare avea `updated_at = 2026-07-29T16:19`).
  **Invariant:** data exista daca si numai daca statusul e `finalizat` — se pune la
  inchidere, se sterge la redeschidere. Fara el, formularul trimite data veche la
  redeschidere (DatePicker-ul se ascunde, valoarea rămâne in `form`) si o re-inchidere ar
  reveni in tacere la ziua veche. Corectabila din „Finalizat pe" in formularul de proiect;
  vizibila in bara laterala, in locul celulei „Urmatoarea perioada" (care pentru un proiect
  inchis n-avea decat „Neplanificat" de spus). Taierea e doar la citire — `/api/calendar` si
  `/api/export/ics`; DB neatins, Ganttul proiectului arata tot.
  **Lectia:** „scoate-l din calendar cand il inchid" nu e acelasi lucru cu „taie la azi";
  diferenta apare doar cand inchizi inainte de vreme, adica in cazul care l-a deranjat.
