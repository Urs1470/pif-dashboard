# 2026-07-03 — Diacritice subsistem Calculator (partea 2)

- **2026-07-03 — Diacritice subsistem Calculator (partea 2)** (SW v59): completat diacriticele
  în `pages/Calculator.svelte`, `CalcApp.svelte`, `App.svelte` (404), `pages/Notes.svelte`,
  `lib/driveCalc.js` (1719 diac) și cele 3 overlay-uri de glosar `lib/glossary{Rich,Extra,Teorie}.json`
  (proza detaliată din modalul de termen). **Gotcha metodă:** agenții de tip read-and-rewrite pe
  fișiere JSON MARI (glossaryRich 1937L, Extra 2407L) au (a) intrat în buclă / s-au împărțit singuri
  în „segment files" throwaway fără reasamblare, și (b) au introdus MANGLE de spațiere („în acest"→
  „înacest", 287 în Rich!). Soluția fiabilă: `git checkout HEAD -- glossary*.json` (revert la ASCII
  curat) + o **pasă scriptată deterministă, space-safe** (regex pe valorile `def/teorie/practic/ia`,
  protejează `$...$` KaTeX, `WORD.sub` nu atinge spațiile) cu reguli de terminație (-ție/-ată/-ează/
  -ață) + map explicit de vocabular + conectori (in→în, si→și). **Gotcha unelte:** `grep -P "[\x{219}]"`
  și `\b` pe caractere unicode dau REZULTATE FALSE (zero-uri) pe acest build de grep — folosește
  ÎNTOTDEAUNA Python (`re` + `io.open(encoding='utf-8')`) pentru scanări de diacritice/mangle.
  Verificare: `json.loads` valid + 0 sedile (ş/ţ U+015E-0163) + 0 „în"+cuvânt lipite. Search-ul din
  Calculator are `fold()` insensibil la diacritice (map cu ș/ț/ş/ţ→ASCII) — cele 8 „sedile" din
  Calculator.svelte sunt acolo intenționat, nu text afișat.
