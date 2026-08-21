# Verifică instrumentul înainte de subiect

*2026-08-21. Scris după o zi în care **trei din patru** „defecte găsite" pe interfața mobilă
s-au dovedit defecte ale sondei, nu ale aplicației.*

## Regula

O măsurătoare care contrazice codul e, până la proba contrarie, o măsurătoare greșită.
Înainte să raportezi că aplicația face ceva rău, dovedește că unealta ta *poate vedea* lucrul
despre care vorbești — cu un control care are răspunsul cunoscut dinainte.

Costul e mic (o pagină de test, două minute). Costul greșelii e mare în ambele sensuri:
raportezi defecte inexistente, sau — mai rău — „repari" ceva ce funcționa.

## Cele patru care m-au prins

**1. `:active` nu se poate observa prin atingere sintetică.** Sonda a raportat „niciun feedback
la apăsare, pe nicio pagină". Aplicația are **79** de reguli `:active`. Cauza: evenimentele
injectate cu `Input.dispatchTouchEvent` (CDP) nu declanșează starea activă în Chromium — ea
vine din conducta de gesturi a browserului, nu din evenimentele brute. Am prins-o cu o pagină
de control de opt rânduri: un `<button>` cu `:active { background: red }`, aceeași atingere,
zero schimbare. **Verificarea corectă e statică** — se caută în `document.styleSheets` regulile
care conțin `:active` și se testează cu `el.matches(selectorFărăActive)`.

**2. `:active` se aplică și strămoșilor.** Prima verificare statică, per element, a raportat
că rândurile de task n-au semn de apăsare. Aveau: `.arow:active` e pe părinte, iar pseudo-clasa
urcă pe lanț. Verificarea trebuie să urce și ea.

**3. Orice regulă CSS are `cssRules` adevărat.** În Chrome modern (CSS imbricat), un
`CSSStyleRule` obișnuit are `cssRules` — o listă **goală, dar truthy**. O recursie scrisă ca
`if (r.cssRules) { recurge; continue }` sare peste *toate* regulile reale. Simptom: „0 reguli
`:active` în tot proiectul", când sunt 79.

**4. `goto` către același hash nu reîncarcă.** E navigare în același document, deci o foaie
rămasă deschisă din proba dinainte supraviețuiește. Prima măsurătoare a raportat „foaia sosește
în 0 cadre" — era deja pe ecran.

## Alte două, despre metrici

**Un elan intenționat arată ca o ezitare.** Proiectul folosește dinadins `--ease-arc-elan`, care
depășește ținta cu 3.8% și se așază înapoi. O metrică binară „schimbă direcția → palpăie" a
raportat exact intenția, pe dos.

**Împărțirea la un drum nul.** O tranziție `in:` pleacă dintr-un decalaj și se așază la locul ei,
deci primul și ultimul eșantion coincid. Procentul de depășire a ieșit **1000%** pe o alunecare
perfect sănătoasă (grila de luni: 8 cadre, pas maxim 10px). Când nu există drum net, singura
mărime cu înțeles e amplitudinea în pixeli.

**Două animații legitime una după alta arată identic cu una care palpăie**, și asta nicio
metrică nu poate deosebi. Verdictul se citește, nu se crede.

## Ce se măsoară, de fapt

**Apăsarea și acțiunea sunt două numere diferite.** Degetul așteaptă două lucruri: confirmarea
că atingerea a fost primită (o tentă, o umbră — asta e `:active`, și lipsa ei se simte ca „nu
reacționează"), și fapta propriu-zisă. O sondă care pornește cronometrul înainte de degetul jos
le amestecă pe amândouă cu două drumuri CDP — și măsoară sonda, nu aplicația.

**Un control care răspunde sub ~25 ms nu are nevoie de semn de apăsare: acțiunea *e* semnul.**
Măsurat: segmentul Muncă/Personal 17 ms, sortarea din Proiecte 22 ms, capul de secțiune din
Plan 16 ms. Adăugarea unui strat de feedback acolo ar fi fost zgomot.

## Și ce nu se poate măsura pe masa de lucru

Emularea reproduce un aparat care nu există. Trei runde de reparații la tastatură au trecut de
toate probele și n-au schimbat nimic pe telefon. Prima măsurătoare pe aparatul real a găsit în
cinci minute un cadru fantomă de 17 ms — `innerHeight` deja micșorat, `vv.height` încă nu, deci
`--kb` sărea la 306 și foaia se turtea la 123px pentru un cadru. Nicio emulare nu-l putea arăta,
fiindcă emularea presupunea tocmai ce trebuia verificat.

Uneltele: `scripts/aparat.py` + `scripts/masoara_tastatura_reala.py` (adb + CDP în WebView-ul
real), `scripts/proba_mobil.py` (bancul de pe masă). Capcana lor cea mai urâtă: **pe ecran stins
WebView-ul nu randează**, deci `requestAnimationFrame` nu se declanșează și urma iese goală, iar
`input tap` nu trezește aparatul — atingerea se pierde. Ambele eșuează arătând exact ca „foaia
nu s-a deschis", fără nicio eroare.

## Corolar

Caută întâi în ce a scris proiectul. Am pierdut o oră redescoperind de la zero un bug de mediu
(`Selector.open()` din Java crapă fiindcă numele scurt 8.3 al lui `%TEMP%` rupe AF_UNIX) care era
deja documentat, cu diagnostic complet, în `scripts/build-apk.ps1` și `references/pc-config.md`.
