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

## Greșeala de măsurare care a costat o rundă întreagă

Prima citire a filmului spunea „două cadre goale **înainte** de pagină", și pe ea am construit o
reparație. Era falsă. Extrăgeam cadrele cu `ffmpeg -vf fps=60`, iar filmul nu are 60 de cadre pe
secundă uniforme — are goluri. **`fps=N` umple golurile duplicând cadre**, și așa apar în analiză
cadre care n-au existat niciodată pe ecran.

Citite corect (`-vsync 0`, doar cadrele stocate, cu `pts_time`), ambele versiuni arătau aceeași
formă: `pagina → un cadru străin → pagina`. Adică reparația nu rezolvase nimic, iar eu raportasem
că da.

**Regula:** la analiza unui film, extrage cadrele **stocate**, nu unele reeșantionate. Și verifică
intervalele: dacă nu sunt uniforme, orice concluzie despre „un cadru" e despre unul inventat.

A doua regulă, pentru cadre ciudate: **un cadru care arată o stare ce a existat înainte poate fi
artefact; unul care arată o stare ce n-a existat niciodată e real.** Am folosit-o ca să resping
o clipire — greșit, fiindcă mai întâi trebuia să am cadrele adevărate.

## Unde era, de fapt

Splash-ul de sistem nu e o vedere în fereastra aplicației. **Până la ieșire e o fereastră a
sistemului, peste tot ce ai tu** — de aceea o acoperire proprie, oricât de identică, nu ajută cu
nimic: e invizibilă sub ea. La ieșire sistemul îți *predă* conținutul ca vedere obișnuită, și
atunci apar două cusături, una după alta:

1. între „fereastra sistemului a plecat" și „vederea predată s-a desenat la tine" se vede pagina;
2. vederea predată se desface pe bucăți — icoana pleacă cu un cadru înaintea fondului ei.

Reglajele din `setOnExitAnimationListener` nu le pot prinde: prima bucată s-a întâmplat deja
când ești chemat. Ce funcționează e să nu mai alergi cursa — voalul propriu, ridicat
`bringToFront` peste vederea predată, ascunde toată desfacerea ei. Măsurat: 2/3 porniri clipeau
cu voalul dedesubt, 1/4 cu `setVisibility(GONE)`, **0 din 11** cu voalul deasupra.

## Capcana care a făcut două build-uri să pară că „nu se aplică"

Am încercat, la un moment dat, să iau marca de la sistem cu totul, dându-i o icoană goală: un
`<vector>` fără niciun `<path>`. Android nu o consideră validă și pune **pictograma aplicației**
— 144dp, cu culorile ei fixe, deci și pe temă închisă arată paleta deschisă. Două build-uri la
rând au părut că nu-și fac efectul: schimbam mărimea și culorile voalului, iar măsurătoarea nu se
mișca, fiindcă ce măsuram nu era desenul nostru deloc.

Semnul după care se recunoaște: **o măsurătoare care nu se schimbă când schimbi ceea ce ar trebui
s-o schimbe nu e o valoare greșită, e alt obiect.**

Și încă una, mai banală, care a dat o măsurătoare veche fără nicio eroare: în Git Bash pe Windows,
`adb shell screencap -p /sdcard/x.png` primește calea **convertită** într-una Windows dacă nu pui
`MSYS_NO_PATHCONV=1`. Captura eșuează, `pull` eșuează, și citești fișierul de data trecută.
