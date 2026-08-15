# Un singur editor pentru toate câmpurile lungi (Proiecte 5a, 2026-08-08)

Observații tehnice, Constatări, Acțiuni și rezultat, nota unui task: patru drumuri către
același lucru, și nu se purtau la fel. Notele salvau la închidere cu toast de anulare;
câmpurile de proiect aveau „Anulează" și „Salvează", dar X / fundal / Escape **aruncau
în tăcere** ce scriseseși. Același gest, două înțelesuri opuse, în aceeași pagină.

`components/ui/EditorLung.svelte` e acum shell-ul unic: Modal `doc` + editor + o bară de
jos cu indiciul la stânga și „Salvează" la dreapta. **Închiderea COMITE**, cu „Anulează"
în toast; nu există buton care aruncă.

- **`$effect.pre` + `untrack`, nu `$effect`.** `RichTextEditor` își umple contenteditable-ul
  **la montare**, din valoarea de atunci; un efect obișnuit rulează după montare, deci
  editorul s-ar deschide cu textul dinainte. `untrack` fiindcă singura dependență e `open`:
  dacă părintele reîncarcă datele cât scrii, ciorna nu are voie să fie înlocuită sub degete.
- **Funcția de scriere se capturează la comitere** (`const scrie = salveaza`). Toastul
  trăiește 4s, timp în care poți deschide alt câmp — iar `salveaza` e o proprietate, deci
  citită la apăsarea pe „Anulează" ar fi cea a câmpului NOU: textul vechi al observațiilor
  s-ar scrie peste nota altui task. Din același motiv fiecare `open*` construiește
  închiderea cu ținta în ea, nu citește starea curentă.
- **Pe eroare modalul se REDESCHIDE** cu ciorna intactă: `Modal.inchide()` face `open = false`
  *înainte* de `onclose`, deci fără asta pagina dispărea cu tot cu textul.
- `RichTextEditor` a rămas cu o singură formă. Varianta `box` (casetă cu chenar, numărător de
  caractere) n-avea niciun consumator după unificare, iar `backdrop-filter: blur(14px)` de pe
  pilula plutitoare a plecat: sticla e scoasă din sistem, și aici nici nu era decor — pilula
  plutește **peste** textul pe care-l editezi, deci rândurile de dedesubt se citeau prin ea.
