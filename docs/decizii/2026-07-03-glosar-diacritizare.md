# 2026-07-03 — Glosar Rich/Extra: diacritizare completă + fix cheie BVR

- **2026-07-03 — Glosar Rich/Extra: diacritizare completă + fix cheie BVR** (SW v61): agenții
  read-and-rewrite (unul per fișier) au produs în final versiuni curate și mai complete pentru
  `glossaryRich.json` (13558 diac vs ~9838 la pasa scriptată) și `glossaryExtra.json` (3807), cu
  diacritizatoare care tokenizează pe cuvinte (protejează `$...$` byte-for-byte și NU ating cheile).
  Verificat: formule identice (3614/101 segmente `$...$`), chei identice, JSON valid, 0 sedile, 0
  cuvinte lipite. **Bugfix:** v59 livrase din greșeală cheia `BVR__TESTMARKER` (probe de persistență
  scăpată de un agent, prinsă de `git add -A`) în loc de `BVR` — parametrul BVR nu avea detaliu în
  glosar; corectat. (Gotcha: nu face `git add -A` cât rulează agenți în background pe aceleași
  fișiere — pot lăsa artefacte. Verifică `git diff --cached` înainte de commit.)
