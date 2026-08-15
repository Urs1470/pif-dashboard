# Un task are O SINGURA data (v33, 2026-07-27)

Ion: *„mi-am luat un task fara deadline in ziua de astazi (…) dupa am vazut ca nu se poate
si (…) deja stiu cand l-as putea face. Deci mutarea este practic un deadline. Si trebuie
sa fie adaugat ca deadline pur, sa nu mai dublam atat notiunile."*

Datele confirmau ca distinctia era fictiva. Din 37 de taskuri de proiect: **6 aveau ambele
date si EGALE, 3 le aveau diferite — toate cu exact o zi** (semnatura butonului „mâine" de
pe vechea regula), iar 16 aveau doar una din doua. La cele globale, 1 rand din 15.

`data_planificata` a plecat. Ramane `data_scadenta` — termenul.

- **Boardul „Astazi"** = ce e scadent azi SAU restant. Regula avea trei ramuri si o
  exceptie (fiindca planul si termenul se puteau contrazice); acum are o linie.
- **A pune un task pe azi** = a-i da termenul de azi. **A-l muta** = a-i muta termenul.
  **A-l scoate de pe board** = a-i sterge data; se intoarce in sertarul „fara termen".
- **In Planificator** fiecare task e un semn de o ZI, nu un interval. Mânerele de
  redimensionare au plecat: nu mai exista span de intins.
- Backfill: unde exista doar `data_planificata`, ea a DEVENIT termenul (12 randuri).
  Unde existau amandoua si difereau (4 randuri), am pastrat `data_scadenta` — a lua data
  de plan ar fi amanat in tacere un termen deja depasit.
- **Capcana:** self-heal-ul care re-rula v20->v21 cand lipsea `data_planificata` a fost
  restrans la `ordine_agenda`. Fara asta, coloana revenea la prima pornire.
