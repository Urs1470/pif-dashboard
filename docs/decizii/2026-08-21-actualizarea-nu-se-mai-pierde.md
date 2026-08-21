# 2026-08-21 — O actualizare gata de aplicat nu mai poate fi pierdută

Ion: „am închis întâmplător pentru actualizare service worker și nu mai vine."

## De ce era un drum înfundat, nu ghinion

`updatefound` se declanșează **o singură dată** per worker nou. Lanțul era:

1. Se instalează un worker nou → `updatefound` → toastul „Versiune nouă a interfeței".
2. Închizi toastul (din greșeală, sau fiindcă erai în mijlocul a ceva).
3. Workerul rămâne în `waiting` — dar `reg.update()`, care rulează din 15 în 15 minute și
   la revenirea în aplicație, **nu mai găsește nimic nou de instalat**: cel instalat deja *e*
   cel mai recent. Deci niciun `updatefound`, deci niciun toast.
4. Punctul (1) din `main.js` (care arată bannerul dacă există deja un worker în așteptare)
   rulează la `load` — dar pe telefon aplicația nu se închide niciodată complet, deci `load`
   nu mai rulează.

Rezultat: rămâi pe versiunea veche **la nesfârșit**, fără niciun semn. Exact modul de eșec pe
care service-worker.js îl descrie în comentariul lui de sus („pe telefon … rămâi pe versiunea
veche la nesfârșit") — doar că pe alt drum decât cel prevăzut acolo (VERSION nebumpat).

## Ce s-a schimbat

Verificarea periodică nu mai doar *verifică*, ci și **re-oferă**: `oferaDacaAsteapta(reg)`
rulează la pornire, la revenirea în aplicație și la fiecare tur de 15 minute, și arată
toastul dacă — și numai dacă — chiar există un worker în `waiting`.

Ca să nu devină un toast care sare la fiecare comutare de aplicație, oferta are o
**răsuflare de 3 minute**. Un worker *chiar* nou (`updatefound`) resetează răsuflarea, deci
el se anunță imediat.

Ce **nu** s-a schimbat: nu se aplică singur. Rămâne decizia utilizatorului — vezi nota din
`service-worker.js` despre reload-urile care păreau că „reîncarcă pagina" în timp ce lucrai.

## Cum se iese din situație o singură dată (pentru workerul deja blocat)

Fixul de aici ajunge pe telefon abia *după* ce workerul blocat activează — deci pentru cel
deja în așteptare rămâne o singură cale: închiderea completă a aplicației din multitasking.
Când nu mai există niciun client, workerul în așteptare activează singur, iar la următoarea
deschidere pornește versiunea nouă.
