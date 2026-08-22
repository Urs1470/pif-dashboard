package org.iupif.pif;

import android.app.AlarmManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.WebView;

import androidx.annotation.NonNull;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsAnimationCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.WebViewListener;

import java.util.List;
import java.util.Locale;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Inregistrarea trebuie sa fie INAINTE de `super.onCreate`: acolo se
        // construieste puntea, iar un plugin inregistrat dupa nu mai e vazut de
        // JS si apelul cade cu „plugin not implemented".
        registerPlugin(InstalarePlugin.class);
        registerPlugin(NotificariPlugin.class);
        registerPlugin(SplashPlugin.class);
        // SPLASHUL, INAINTE DE `super.onCreate`.
        //
        // Pe Android 12+ platforma citeste singura `windowSplashScreen*` din tema
        // de lansare, deci pe telefonul lui Ion (API 36) linia asta n-ar fi
        // necesara. Sub API 31 insa atributele alea nu exista in platforma, si
        // fara biblioteca de compatibilitate splashul ar fi doar un fond gol —
        // adica tocmai aparatele mai vechi, unde pornirea dureaza mai mult si
        // valul conteaza cel mai tare, ar ramane fara marca. `minSdk` e 24.
        //
        // Trebuie chemata INAINTE de `super.onCreate` si e cea care aplica
        // `postSplashScreenTheme` (vezi `res/values/styles.xml`).
        splashUnic();
        super.onCreate(savedInstanceState);

        bareDeSistem();
        tastaturaPeCadre();

        // ULTIMA DATA CAND SITE-UL S-A INCARCAT.
        // Se scrie aici, nu din JS: cand ai nevoie de valoare (ecranul „fara
        // retea") JS-ul site-ului e tocmai ce lipseste. `onPageLoaded` vine si
        // pentru pagina locala de eroare, deci se filtreaza dupa adresa
        // serverului — altfel „ultima data vazut" ar fi mereu „acum", si ar
        // insemna „ultima data cand ai vazut ecranul asta".
        final String server = getBridge().getServerUrl();
        getBridge().addWebViewListener(new WebViewListener() {
            @Override
            public void onPageLoaded(WebView webView) {
                // SAFE-AREA SE REINJECTEAZA LA FIECARE INCARCARE.
                // Variabilele sunt stil INLINE pe `<html>`, deci o pagina noua
                // porneste fara ele. Prima scriere se face din `onCreate`, cand
                // WebView-ul inca n-are document — si se pierde. Capacitor rezolva
                // asta cu un `onDOMReady` propriu; noi, de aici. Cache-ul se
                // goleste intai, altfel a doua scriere ar fi considerata identica
                // si sarita. (Masurat: fara asta, `--safe-area-inset-*` raman
                // GOALE pe telefon, iar dockul urca sub bara de navigatie.)
                safeAreaScris = null;
                if (webView.getParent() instanceof View) {
                    ViewCompat.requestApplyInsets((View) webView.getParent());
                }
                String url = webView.getUrl();
                if (server == null || url == null || !url.startsWith(server)) return;
                Programator.prefs(MainActivity.this).edit()
                        .putLong("ultima_vizita", System.currentTimeMillis()).apply();
            }
        });
    }

    /** Peste atat, valul pleaca oricum. Perechea lui din `lib/splash.js` e 5000;
     *  aici marja e mai mare, ca poarta din pagina sa apuce sa se pronunte. */
    private static final long PLAFON_SPLASH = 6500;

    /** Cat tine desenarea undei: `startOffset` 120 + `duration` 600 din
     *  `splash_marca_anim.xml`, aceeasi valoare cu
     *  `windowSplashScreenAnimationDuration` din tema. Splashul NU pleaca inainte
     *  s-o termine — vezi `splashUnic`. */
    private static final long DESENUL_MARCII = 720;

    /**
     * UN SINGUR SPLASH, AL SISTEMULUI, TINUT PANA E PAGINA GATA.
     *
     * Aici au fost, pe rand, doua incercari gresite. Intai marca nativa a fost
     * facuta identica cu cea din pagina (aceeasi placa, 60dp, acelasi loc, aceeasi
     * culoare) — si tot se vedeau doua etape. Apoi placa din pagina a fost oprita
     * din a se re-desena — si tot doua. Ion, 2026-08-22: „mai intai porneste
     * nativ apoi apare cea web, tot se primeste in doua parti".
     *
     * Motivul nu e ca marcile difera, ci ca splashul de sistem isi face IESIREA
     * lui: o duce afara, si abia dupa aia pagina deseneaza. Doua suprafete care se
     * schimba una pe alta nu se pot cusuta, oricat de bine s-ar potrivi la desen.
     *
     * Deci a ramas unul. Sistemul il tine pe ecran cat spunem noi
     * (`setKeepOnScreenCondition`), iar cand pagina anunta ca s-a asezat
     * (`SplashPlugin`, chemat din `lib/splash.js`) il scoatem NOI, cu o singura
     * miscare — nu cu cea a sistemului, care era a doua etapa. In aplicatie
     * pagina nu mai deseneaza niciun val: `html.din-nativ` in `index.html`.
     *
     * PLAFONUL nu e o eleganta, e o plasa: daca pagina nu apuca sa anunte nimic
     * (retea moarta, eroare de import), un splash tinut la nesfarsit ar fi tot ce
     * mai ramane din aplicatie. Se numara de la `onCreate`, nu de la primul cadru:
     * asteptarea pe care o simte omul incepe cand a atins iconita.
     */
    private void splashUnic() {
        final androidx.core.splashscreen.SplashScreen splash =
                androidx.core.splashscreen.SplashScreen.installSplashScreen(this);
        final long pornit = android.os.SystemClock.uptimeMillis();

        // DOUA CONDITII, NU UNA. Pagina gata nu e de ajuns: pe o pornire calda ea
        // e gata inainte ca unda sa se termine de desenat, iar atunci iesirea
        // incepe PESTE desen — marca se stinge in timp ce inca se scrie. Ion,
        // 2026-08-22: „marca dupa cateva clipe se opreste". E exact defectul pe
        // care l-am reparat in valul web cu cateva ore inainte (poarta pleca la
        // 660ms peste o sosire de 760), refacut aici in nativ.
        // Deci: si pagina asezata, SI desenul terminat. Plafonul le taie pe
        // amandoua — o retea moarta n-are voie sa lase sigla pe ecran.
        splash.setKeepOnScreenCondition(() -> {
            final long trecut = android.os.SystemClock.uptimeMillis() - pornit;
            if (trecut >= PLAFON_SPLASH) return false;
            return !SplashPlugin.paginaGata || trecut < DESENUL_MARCII;
        });

        // IESIREA E A NOASTRA, SI E UNA SINGURA.
        //
        // Fara listenerul asta sistemul isi joaca propria plecare (ridica iconita
        // si descopera fereastra) — exact a doua etapa. Aici marca se stinge si se
        // DEPARTEAZA cu 4%, aceleasi valori ca vechiul val din pagina
        // (`#splash.pleaca`), ca miscarea sa ramana cea pe care Ion o stia.
        // Nu invers: o marca micsorata ar parea ca se retrage inapoi in ecran.
        // SPLASHUL SE TERMINA, SI ABIA APOI APARE PAGINA.
        //
        // Ion, 2026-08-22: „ideal as vrea ca animatia splash sa se termine
        // inainte sa apara pagina". Aici au fost, pe rand, doua iesiri gresite:
        //   1. se stingea doar ICOANA, iar fondul ramanea si disparea dupa ea —
        //      doua lucruri unul dupa altul;
        //   2. se stingea TOT, in fondu-incrucisat — si atunci pagina aparea PRIN
        //      splash cat timp marca inca se departa. Ion: „marca continua cand
        //      pagina a aparut... parca se reincarca odata".
        // Amandoua au aceeasi forma: doua lucruri se vad in acelasi timp.
        //
        // Deci nu mai exista nicio iesire. Unda se deseneaza intreaga (`splashUnic`
        // tine splashul pana la `DESENUL_MARCII`), pagina de dedesubt e deja
        // asezata si NU-si mai joaca sosirea (`splash-a-lucrat`, pus din
        // `index.html`), iar splashul se scoate dintr-o data. Ce se vede e: marca
        // se scrie, apoi aplicatia. Un lucru, apoi altul — niciodata amandoua.
        //
        // Fara listenerul asta sistemul si-ar juca propria plecare, care e tot un
        // fondu-incrucisat; deci el ramane, doar ca nu mai anima nimic.
        splash.setOnExitAnimationListener(vedere -> vedere.remove());
    }

    /**
     * BARELE SISTEMULUI IAU FONDUL PAGINII.
     *
     * Nu au culoare proprie: continutul urca sub ele, iar fondul care se vede
     * dedesubt e al paginii. Ce NU are voie sa treaca pe sub ele e TINTA — de
     * aceea dockul sta la `14px + safe-bottom`, iar CSS-ul are `--safe-*`.
     *
     * Doua lucruri trebuie sa fie amandoua adevarate ca sa mearga:
     *   `setDecorFitsSystemWindows(false)` — fereastra se intinde sub bare;
     *   `viewport-fit=cover` in `index.html` — abia atunci WebView-ul da valori
     *      reale in `env(safe-area-inset-*)`, din care ies `--safe-top/bottom`.
     * Fara a doua, continutul ar urca sub bare si ar ramane acolo, fara insetul
     * care il tine la vedere.
     *
     * Iconitele barelor comuta cu tema sistemului: pe fond deschis trebuie sa fie
     * inchise la culoare, altfel ceasul dispare in alb.
     */
    private void bareDeSistem() {
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Color.TRANSPARENT);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Fara asta Android deseneaza singur un „scrim" gri sub bara de
            // navigatie, adica exact culoarea proprie pe care n-o vrem.
            getWindow().setNavigationBarContrastEnforced(false);
        }
        boolean noapte = (getResources().getConfiguration().uiMode
                & android.content.res.Configuration.UI_MODE_NIGHT_MASK)
                == android.content.res.Configuration.UI_MODE_NIGHT_YES;
        WindowInsetsControllerCompat c =
                WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        c.setAppearanceLightStatusBars(!noapte);
        c.setAppearanceLightNavigationBars(!noapte);
    }

    /** Cat tine animatia IME-ului, paddingul e scris de cadre, nu de listener. */
    private boolean animatieIme = false;
    /** Ultimele `--safe-area-inset-*` trimise in pagina, ca sa nu le rescriem degeaba. */
    private String safeAreaScris = null;

    /**
     * TASTATURA MISCA WEBVIEW-UL CADRU CU CADRU, NU DINTR-UN SALT.
     *
     * CE FACE CAPACITOR SINGUR. Plugin-ul `SystemBars` (in core, inregistrat
     * automat) pune un `OnApplyWindowInsetsListener` pe PARINTELE WebView-ului si
     * acolo face `setPadding(0,0,0, imeInsets.bottom)` — `SystemBars.java:208`.
     * Listenerul ala primeste insets-urile o SINGURA data, cu valoarea FINALA.
     * Deci WebView-ul se micsoreaza dintr-un pas, in timp ce tastatura insasi
     * gliseaza ~250ms. Masurat prin USB pe telefonul lui Ion
     * (`scripts/masoara_tastatura_reala.py`): viewportul face 800 -> 493 intr-un
     * singur cadru, in amandoua sensurile.
     *
     * Din web nu se poate repara. Am incercat o zi: geometria veche a foii cade
     * in afara suprafetei desenabile dupa micsorare, deci orice „catch-up" o
     * deseneaza taiata (vezi nota lunga din `Modal.svelte`). Nu era o animatie
     * proasta — era informatie care lipsea.
     *
     * CE ADAUGA ASTA. `WindowInsetsAnimationCompat` (API 30+) da, la FIECARE cadru
     * al animatiei IME-ului, insetul INTERPOLAT. Punem paddingul din el, deci
     * WebView-ul se micsoreaza si creste odata cu tastatura, nu inaintea ei.
     * Layoutul web urmeaza singur: `100dvh` si foaia ancorata jos sunt deja
     * corecte la orice inaltime.
     *
     * DE CE PRELUAM INSETS-URILE CU TOTUL. Nu se poate imparti paddingul cu
     * Capacitor. Am incercat de doua ori si masuratoarea a aratat de fiecare data
     * acelasi lucru: `setPadding`-ul nostru cere layout, layoutul re-livreaza
     * insets-urile, listenerul lui scrie inapoi valoarea FINALA, iar cadrul
     * urmator o scriem noi pe cea interpolata. Rezultatul, masurat pe telefon:
     * 493 -> 800 -> 504 -> 800 -> 546 -> 800 ..., douazeci si una de trepte,
     * fiecare anulata de urmatoarea. Palpaire, adica mai rau decat saltul de
     * reparat. `DISPATCH_MODE_STOP` nu ajuta nici pe `parinte` (opreste
     * subarborele, nu view-ul insusi), nici pe bunic (livrarea provocata de
     * layout trece oricum).
     *
     * Deci `SystemBars` e pus pe `insetsHandling: "disable"` (vezi
     * `capacitor.config.json`) si facem aici tot ce facea el:
     *   1. paddingul de jos, din insetul IME (starea finala);
     *   2. `--safe-area-inset-*` injectate in pagina, cu `bottom` = 0 cat timp
     *      tastatura e sus, fiindca atunci insetul de jos e al ei, nu al barei;
     *   3. insets-urile trimise mai departe cu `systemBars|displayCutout` puse pe
     *      zero jos, ca sa nu se aplice de doua ori.
     * Peste ele vine ce nu avea Capacitor: paddingul pe CADRU, din animatia IME.
     *
     * Referinta, ca sa se vada daca s-a stricat ceva: pe telefonul lui Ion, cu
     * Capacitor la carma, iesea `--safe-area-inset-top: 40px`, `bottom: 22px`,
     * stanga/dreapta 0. Aceleasi valori trebuie sa iasa si acum.
     */
    private void tastaturaPeCadre() {
        final View parinte = (View) getBridge().getWebView().getParent();
        if (parinte == null) return;

        // (1) STAREA FINALA - la pornire, la rotire, si dupa fiecare animatie.
        ViewCompat.setOnApplyWindowInsetsListener(parinte, (v, insets) -> {
            boolean imeVizibil = insets.isVisible(WindowInsetsCompat.Type.ime());
            // Cat tine animatia, CADRELE conduc paddingul. Livrarea asta vine
            // chiar din layoutul provocat de ele, deci a o asculta ar insemna sa
            // ne suprascriem singuri - exact bucla care palpaia cu Capacitor.
            if (!animatieIme) {
                v.setPadding(0, 0, 0,
                        imeVizibil ? insets.getInsets(WindowInsetsCompat.Type.ime()).bottom : 0);
            }
            Insets bare = insets.getInsets(
                    WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            int jos = imeVizibil ? 0 : bare.bottom;
            scrieSafeArea(bare.top, bare.right, jos, bare.left);
            return new WindowInsetsCompat.Builder(insets)
                    .setInsets(
                        WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout(),
                        Insets.of(bare.left, bare.top, bare.right, jos))
                    .build();
        });
        ViewCompat.requestApplyInsets(parinte);

        // (2) ANIMATIA IME - un padding pe cadru. Exista doar de la API 30.
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return;
        ViewCompat.setWindowInsetsAnimationCallback(
            parinte,
            new WindowInsetsAnimationCompat.Callback(
                    WindowInsetsAnimationCompat.Callback.DISPATCH_MODE_CONTINUE_ON_SUBTREE) {

                @Override
                public void onPrepare(@NonNull WindowInsetsAnimationCompat animatie) {
                    if (esteIme(animatie)) animatieIme = true;
                }

                @NonNull
                @Override
                public WindowInsetsCompat onProgress(
                        @NonNull WindowInsetsCompat insets,
                        @NonNull List<WindowInsetsAnimationCompat> animatii) {
                    boolean ime = false;
                    for (WindowInsetsAnimationCompat a : animatii) {
                        if (esteIme(a)) { ime = true; break; }
                    }
                    // Animatiile barelor de sistem nu ne privesc: daca am muta
                    // WebView-ul la fiecare aparitie de bara, pagina ar tresari
                    // la fiecare intrare in modul imersiv.
                    if (ime) {
                        parinte.setPadding(0, 0, 0,
                                insets.getInsets(WindowInsetsCompat.Type.ime()).bottom);
                    }
                    return insets;
                }

                @Override
                public void onEnd(@NonNull WindowInsetsAnimationCompat animatie) {
                    if (!esteIme(animatie)) return;
                    animatieIme = false;
                    // Ultimul cadru interpolat e aproape valoarea finala, dar nu ea.
                    // „Aproape" e cel mai prost fel de gresit: nu se vede si ramane.
                    ViewCompat.requestApplyInsets(parinte);
                }
            });
    }

    private static boolean esteIme(WindowInsetsAnimationCompat a) {
        return (a.getTypeMask() & WindowInsetsCompat.Type.ime()) != 0;
    }

    /**
     * `--safe-area-inset-*` scrise in pagina, ca stil inline pe `<html>`.
     *
     * Acelasi lucru pe care-l facea `SystemBars.injectSafeAreaCSS`, cu aceeasi
     * conversie px -> dp. Se scrie doar cand valorile CHIAR se schimba: in timpul
     * animatiei IME layoutul se reface de zeci de ori, iar un `evaluateJavascript`
     * pe cadru ar concura cu exact randarea pe care incercam s-o facem lina.
     */
    private void scrieSafeArea(int top, int right, int bottom, int left) {
        float d = getResources().getDisplayMetrics().density;
        final String val = String.format(Locale.US, "%d,%d,%d,%d",
                (int) (top / d), (int) (right / d), (int) (bottom / d), (int) (left / d));
        if (val.equals(safeAreaScris)) return;
        safeAreaScris = val;
        final String[] q = val.split(",");
        final String js = String.format(Locale.US,
                "try{var s=document.documentElement.style;"
                + "s.setProperty('--safe-area-inset-top','%spx');"
                + "s.setProperty('--safe-area-inset-right','%spx');"
                + "s.setProperty('--safe-area-inset-bottom','%spx');"
                + "s.setProperty('--safe-area-inset-left','%spx');}catch(e){}",
                q[0], q[1], q[2], q[3]);
        runOnUiThread(() -> {
            WebView w = getBridge().getWebView();
            if (w != null) w.evaluateJavascript(js, null);
        });
    }

    /**
     * ALARMA EXACTA SE VERIFICA LA FIECARE PORNIRE.
     *
     * E o permisiune separata (Android 12+) pe care utilizatorul o poate retrage
     * oricand — iar cand o retrage, sistemul reporneste aplicatia SI STERGE
     * alarmele exacte deja puse. Fara verificarea asta, dimineata ar veni la 8:40
     * si n-ai avea de unde sti de ce.
     *
     * Cand lipseste, i se DESCHIDE ecranul de sistem, nu i se dau indicatii:
     * calea difera de la un producator la altul („Alarme si mementouri" e sub
     * Aplicatii la unii, sub Acces special la altii), iar o instructiune care nu
     * se potriveste cu ce vezi pe ecran te face sa crezi ca ai gresit tu.
     *
     * O SINGURA DATA per retragere, nu la fiecare pornire: un ecran de sistem
     * care se deschide singur de fiecare data e o capcana, nu un ajutor. Daca
     * refuzi, drumul ramane in fereastra de notificari (butonul „Deschide
     * ecranul"), unde il gasesti cand vrei. Steagul se reseteaza cand permisiunea
     * revine, deci a doua retragere intreaba din nou.
     */
    @Override
    public void onResume() {
        super.onResume();
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return;
        AlarmManager am = (AlarmManager) getSystemService(Context.ALARM_SERVICE);
        if (am == null) return;
        boolean are = am.canScheduleExactAlarms();
        boolean intrebat = Programator.prefs(this).getBoolean("exacte_intrebat", false);
        if (are) {
            if (intrebat) Programator.prefs(this).edit().putBoolean("exacte_intrebat", false).apply();
            return;
        }
        if (intrebat) return;
        Programator.prefs(this).edit().putBoolean("exacte_intrebat", true).apply();
        try {
            Intent i = new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM);
            i.setData(Uri.parse("package:" + getPackageName()));
            startActivity(i);
        } catch (Exception e) {
            // Unele carcase nu au ecranul; ramane butonul din fereastra de
            // notificari, care merge prin plugin-ul de Capacitor.
        }
    }

    /**
     * SESIUNEA TREBUIE SA SUPRAVIETUIASCA INCHIDERII APLICATIEI.
     *
     * WebView-ul Android tine cookie-urile in memorie si le scrie pe disc cand
     * are el chef. Daca inchizi aplicatia din multitasking inainte de scriere,
     * cookie-ul de sesiune se pierde — si la urmatoarea pornire aplicatia cere
     * PIN-ul din nou, desi serverul il considera logat inca 30 de zile si
     * cheia de semnare e persistata pe disc, deci nici deploy-urile nu-l
     * deconecteaza. Simptomul arata ca „expira sesiunea", dar nimic n-a expirat:
     * cookie-ul n-a ajuns niciodata pe disc.
     *
     * `flush()` il scrie ACUM. Se cheama in `onPause`, nu in `onDestroy`:
     * `onDestroy` nu e garantat cand sistemul omoara procesul, iar `onPause` e
     * ultimul moment sigur inainte ca aplicatia sa iasa din fata.
     */
    @Override
    public void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
    }
}
