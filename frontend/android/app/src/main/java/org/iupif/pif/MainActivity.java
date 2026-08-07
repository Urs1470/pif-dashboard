package org.iupif.pif;

import android.os.Bundle;
import android.webkit.CookieManager;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Inregistrarea trebuie sa fie INAINTE de `super.onCreate`: acolo se
        // construieste puntea, iar un plugin inregistrat dupa nu mai e vazut de
        // JS si apelul cade cu „plugin not implemented".
        registerPlugin(InstalarePlugin.class);
        super.onCreate(savedInstanceState);
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
