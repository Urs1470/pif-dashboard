# Pornirea rece se filmează, nu se deduce

*2026-08-22. Scris după trei runde de reparații pe splash făcute pe deducție, și una făcută
pe un film — care a găsit cauza în cinci minute.*

## Regula

Pornirea rece e singura secvență a aplicației care **nu se poate observa din afară**. Sonda
injectată prin CDP moare odată cu WebView-ul vechi; o captură prin USB sosește la ~1,8 s, adică
după ce s-a terminat tot. Deci orice afirmație despre ea, făcută din cod, e o ipoteză.

`adb shell screenrecord` rulează **pe telefon** și filmează la rata ecranului. Vede și splashul
de sistem (desenat înainte ca WebView-ul să existe), și clipa în care el se scoate.
`scripts/filmeaza_pornirea.py` face filmul, taie cadrele și le măsoară.

**Lansează prin atingere adevărată pe pictogramă, nu cu `am start`.** Lansatorul își pune
propria animație de deschidere, iar cusătura despre care se plânge omul e chiar acolo. Cu
`am start` defectul nu apărea deloc: primul film a ieșit curat, al doilea l-a arătat imediat.

## Ce a găsit filmul

Ion, de trei ori la rând: „parcă se reîncarcă", „pulsația aceasta", „tot mai există o mică
clipire". Jurnalul de pornire dovedea că **pagina nu se schimbă** după 742 ms — deci nu ea
clipea. Filmul a arătat, la 60 fps:

    2,217 s   marca, pe fond
    2,233 s   GOL — doar fondul
    2,250 s   GOL — doar fondul
    2,267 s   pagina, întreagă

Două cadre de ecran gol. Splashul se ridica **înainte** ca WebView-ul să fi apucat să pună
pagina pe ecran.

## Cauza, și de ce poarta veche nu era destul

Poarta din `frontend/src/lib/splash.js` întreabă pagina: date sosite, fonturi așezate, niciun
schelet. Toate adevărate — în JS. Dar între cadrul pe care JS-ul îl consideră pictat și cadrul
care ajunge pe ecran mai e conducta de compozitare.

`WebView.postVisualStateCallback` e API-ul făcut pentru fix întrebarea asta: cheamă înapoi când
starea DOM de la momentul apelului a intrat într-un cadru gata de desenat. Cu el, plus încă un
cadru, ordinea devine: pagina e pe ecran, **acoperită** de splash; splashul se scoate; dedesubt
e deja tot. Vezi `SplashPlugin.gata`.

## Două piste testate și respinse, ca să nu se refacă

**Ieșirea sistemului** (fără `setOnExitAnimationListener`) e mult mai rea: 183 ms de ecran gol,
măsurat. Ieșirea rămâne a noastră.

**Culorile** nu erau vinovate — splashul și pagina sunt amândouă `#f4f5f7` pe temă deschisă. Dar
fondul ferestrei și al WebView-ului au fost puse tot pe `@color/splash_bg`, fiindcă implicit sunt
**albe**: pe temă închisă orice cadru fără conținut ar fi fost un flash orbitor.

## Ce rămâne, și cum se citește

După reparație, filmul mai arată un cadru ciudat la tăietură — dar el conține **marca**, nu golul.
Marca nu poate reveni pe ecran după ce vederea a fost scoasă: nimic n-o mai adaugă înapoi. Deci
acel cadru e al camerei, nu al aplicației.

Regula de citire, generală: **un cadru care arată o stare care a existat înainte poate fi artefact
de captură; un cadru care arată o stare care n-a existat niciodată e real.** Cele două cadre goale
erau reale exact pe criteriul ăsta — ecranul nu fusese gol în niciun moment anterior.
