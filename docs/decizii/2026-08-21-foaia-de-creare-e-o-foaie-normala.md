# 2026-08-21 — Foaia de creare redevine o foaie normală de jos (secvență, nu coregrafie)

Ion, după a treia încercare: „nu e ok modalul de creare … este foarte haotică ca animație",
apoi referința decisivă: **„vreau să fie o animație lină precum este la modalul detalii task
sau la atingere lungă."**

## Ce s-a înțeles greșit de trei ori

Toate cele trei forme încercate porneau de la premisa „foaia trebuie să se descurce cu
tastatura": (1) prevedere + coregrafie în doi timpi; (2) pagină ancorată sus, ca să nu se
miște nimic; (3) pagină cu deschidere vâscoasă și fundal dimat. Fiecare a adăugat un
mecanism peste altul, și fiecare a fost respinsă — pentru că toate puneau **două mișcări pe
aceiași pixeli, în același interval**: foaia care sosește și tastatura care urcă.

Referința lui Ion e o foaie care **nu are** problema asta: modalul de detalii task nu are
câmp focalizat automat, deci are o singură mișcare. Concluzia nu era „găsește o coregrafie
mai bună", ci **desparte cele două mișcări în timp**.

## Ce e acum

- Foaia de creare (și „Proiect nou") sunt **foi normale de jos**, exact ca modalul de detalii
  task: `size="lg"` / `size="md"`, aceeași durată (DUR_SLOW 280) și aceeași curbă (`--ease`).
- **Focusul e secvențiat**: câmpul primește focus după `DUR_SLOW + 40 ms`, adică *după* ce
  foaia s-a așezat. Deci: mișcarea 1 — foaia alunecă și se oprește; mișcarea 2 — tastatura
  urcă și o ridică. Niciodată simultan. (Sub `prefers-reduced-motion`, focus imediat.)
- Tot ce ținea de forma „pagină" a fost **șters**, nu lăsat pe lângă: propul `pagina`, clasa,
  regula de înălțime, `DUR_PAGINA`/`EASE_PAGINA`, tokenul `--scrim-plin`, regula
  `:has(.modal.pagina) .app-main`. Un mecanism nefolosit se reîntoarce singur în cod.

## Măsurat (audit_tastatura, secțiunea 1 rescrisă)

Contractul verificat nu mai e o geometrie, ci **o secvență**, la două latențe de tastatură
(420 și 900 ms):
- faza 1 urcă monoton, fără oscilație, și **se așază** — 266 ms (referința, foaia de detalii
  task: 249 ms);
- faza 2 (tastatura) începe **abia după** ce faza 1 s-a terminat (măsurat: 835 ms și 1341 ms
  față de așezare la 350 / 372 ms);
- după ce tastatura a urcat, foaia stă pe loc; câmpul și marginea de jos rămân deasupra ei;
  nici când scrii nu se mișcă nimic.

## Aterizarea Acasă → task nu mai întârzie

Ion: „tranziția … este lentă, întârziată parcă." Măsurat: ruta se schimba la 128 ms (bine),
dar apoi `scrollIntoView({behavior:'smooth'})` mai adăuga ~400 ms de listă care glisează
*după* ce pagina sosise. Acum derularea e `auto`: aterizarea se face în callbackul tranziției
de rută, deci **pagina sosește cu rândul deja centrat**, iar semnalul „pe ăsta ai apăsat" îl
dă inelul care pulsează.
