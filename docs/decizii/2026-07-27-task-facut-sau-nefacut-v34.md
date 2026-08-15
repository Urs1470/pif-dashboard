# Taskul e facut sau nu (v34, 2026-07-27)

Ion: *„in general as scapa si as sterge statusul taskurilor si prioritatea."*
Ales explicit: doar facut / nefacut.

**Statusul era deja mort.** In baza reala existau DOAR `to_do` si `done`, in ambele tabele.
`in_lucru`, `in_asteptare` si `blocat` erau in selector si in `labels.py` — pe zero randuri.

**Prioritatea era completata, dar saturata.** 20 din 37 de taskuri de proiect si 12 din 15
globale erau „urgent" — 54% si 80%. Cand majoritatea e urgenta, cuvantul nu mai selecteaza
nimic. (Aparea si `Normal` cu majuscula langa `normal`, semn ca era bifata mecanic.) De
aceea a plecat, desi — spre deosebire de celelalte curatenii — chiar era folosita.
Arhiva: `raw/pif-dashboard/2026-07-27-inainte-de-v34/`.

Severitatea unui task se citeste acum din **termen**, nu din prioritate: `dueRing()` in
`formatters.js` da rosu pentru depasit si amber pentru azi. Se vede pe **inelul bifei** si
pe **textul termenului** — nu pe bordura randului (vezi tura 9 mai jos). Sortarea din
exportul .md merge tot pe termen.
