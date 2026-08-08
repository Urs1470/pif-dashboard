package org.iupif.pif;

import android.app.AlarmManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.webkit.CookieManager;
import android.webkit.WebView;

import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.WebViewListener;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Inregistrarea trebuie sa fie INAINTE de `super.onCreate`: acolo se
        // construieste puntea, iar un plugin inregistrat dupa nu mai e vazut de
        // JS si apelul cade cu „plugin not implemented".
        registerPlugin(InstalarePlugin.class);
        registerPlugin(NotificariPlugin.class);
        super.onCreate(savedInstanceState);

        bareDeSistem();

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
                String url = webView.getUrl();
                if (server == null || url == null || !url.startsWith(server)) return;
                Programator.prefs(MainActivity.this).edit()
                        .putLong("ultima_vizita", System.currentTimeMillis()).apply();
            }
        });
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
