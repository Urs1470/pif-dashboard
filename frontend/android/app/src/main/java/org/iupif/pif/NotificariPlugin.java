package org.iupif.pif;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import org.json.JSONArray;
import org.json.JSONException;

/**
 * Puntea dintre JS si programatorul nativ de notificari.
 *
 * JS decide CE si CAND (regula taskurilor traieste in `lib/notificari.js`, langa
 * cea de pe server, ca sa se poata compara), iar partea nativa se ocupa de ce nu
 * se poate face din WebView: alarme care supravietuiesc aplicatiei inchise si
 * butoane care lucreaza fara s-o deschida.
 */
@CapacitorPlugin(name = "NotificariPif")
public class NotificariPlugin extends Plugin {

    /**
     * Inlocuieste TOT ce era programat. Nu „adauga": reprogramarea se face din
     * lista completa de fiecare data, iar un task bifat intre timp trebuie sa
     * dispara — daca am adauga, alarma lui veche ar suna mai departe.
     */
    @PluginMethod
    public void programeaza(PluginCall call) {
        JSONArray lista = call.getArray("notificari");
        if (lista == null) lista = new JSONArray();
        try {
            Programator.pune(getContext(), lista);
        } catch (Exception e) {
            call.reject("Nu am putut programa notificările: " + e.getMessage(), e);
            return;
        }
        JSObject r = new JSObject();
        r.put("programate", numarViitoare(lista));
        call.resolve(r);
    }

    @PluginMethod
    public void anuleazaTot(PluginCall call) {
        Programator.anuleazaTot(getContext());
        call.resolve();
    }

    /** O singura alarma, care NU atinge fereastra programata — vezi
     *  `Programator.punaSingura`. */
    @PluginMethod
    public void proba(PluginCall call) {
        try {
            Programator.punaSingura(getContext(), call.getData());
        } catch (Exception e) {
            call.reject("Nu am putut programa proba: " + e.getMessage(), e);
            return;
        }
        call.resolve();
    }

    /**
     * STAREA PENTRU ECRANUL „FARA RETEA".
     *
     * Ecranul ala (`fara-retea.html`) e servit din asset-urile aplicatiei, de pe
     * `https://localhost` — alt origin decat site-ul, deci nu poate citi nimic din
     * ce a lasat aplicatia in `localStorage`. Singurul lucru pe care il poate
     * intreba e partea nativa, care stie doua fapte utile: cand a mers ultima
     * oara si cate alarme sunt puse. Amandoua contrazic exact frica pe care o are
     * cineva cand vede ecranul: „s-a stricat si nu mai stiu nimic".
     */
    @PluginMethod
    public void stare(PluginCall call) {
        JSObject r = new JSObject();
        r.put("ultimaVizita", Programator.prefs(getContext()).getLong("ultima_vizita", 0));
        r.put("programate", numarViitoare(Programator.lista(getContext())));
        call.resolve(r);
    }

    /**
     * Reincarca site-ul. Adresa o stie puntea (din `capacitor.config.json`), deci
     * ecranul de „fara retea" nu trebuie s-o mai scrie o data — o a doua copie a
     * unei adrese e cea care ramane in urma cand se schimba.
     */
    @PluginMethod
    public void reincarca(PluginCall call) {
        final String url = getBridge().getServerUrl();
        getActivity().runOnUiThread(() -> {
            if (url != null && !url.isEmpty()) getBridge().getWebView().loadUrl(url);
            else getBridge().getWebView().reload();
        });
        call.resolve();
    }

    /** Cate sunt efectiv in viitor — ce raportam trebuie sa fie ce va suna. */
    private int numarViitoare(JSONArray lista) {
        long acum = System.currentTimeMillis();
        int n = 0;
        for (int i = 0; i < lista.length(); i++) {
            try {
                if (lista.getJSONObject(i).optLong("at", 0) > acum) n++;
            } catch (JSONException ignored) { }
        }
        return n;
    }
}
