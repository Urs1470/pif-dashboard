# Banda de pregătire a plecat din Planificator (2026-08-15)

> Intrarea din `docs/memory/MEMORY.md` care acopera si aceasta decizie (2026-08-15 (7))
> a fost arhivata in [2026-08-15-sfera-gest-toata-pagina.md](2026-08-15-sfera-gest-toata-pagina.md),
> fiindca acolo trateaza amandoua cererile din aceeasi tura.

Ion: *„scoate din planificator banda de pregătire, e clar că este în pregătire fără
să văd pe planificator, dar acum arată straniu cu banda de pregătire."*

Era un obiect **derivat**, nu unul introdus: `segmentePregatire()` calcula
complementul etapelor — golul de dinaintea primei implementări și golurile dintre
ele — și îl desena ca o spălătură pe toată pista. Două lucruri nu se puteau apăra:

- **Spunea ceva ce se știe deja.** Un proiect care nu e `finalizat` e în pregătire;
  statusul o zice, iar Planificatorul e despre **când** ești undeva, nu despre în ce
  stare e proiectul.
- **Capătul ei își recunoștea singur că e inventat.** Nu există o zi „de când se
  pregătește" (`data_incepere` a plecat în v36), deci banda pornea de la marginea
  ferestrei cu stânga estompată — adică ocupa toată lățimea ca să spună „nu știu de
  când". După ce perioada a devenit o șină de 4px la baza rândului, banda rămăsese
  singurul lucru lat de pe pistă, și de aceea „arăta straniu": fundalul era mai
  prezent decât datele.

Ce **rămâne**, și nu trebuie confundat cu ea: **faza `pregatire` a unei PERIOADE
reale** (`implementari.faza`) — aia e o perioadă pe care ai pus-o tu în Calendar, cu
zile adevărate, și se desenează în continuare pe șină, palid (`.impl-band.pregatire`).
La fel `.banda.pregatire` din Calendar. Numele se suprapun; obiectele nu.

Prins în aceeași trecere: keyframe-ul `pregatireIn` **nu** a plecat cu ea — îl
folosea și `.impl-band.clipL`, o perioadă tăiată de marginea ferestrei, care n-are
nici ea un început vizibil din care să crească. S-a redenumit **`apareIn`**, ca
numele să spună ce face, nu cine îl folosea prima dată.
