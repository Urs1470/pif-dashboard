package org.iupif.pif;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * PROGRAMAREA ALARMELOR, cu lista lor pastrata pe disc.
 *
 * DE CE NU `@capacitor/local-notifications`. Plugin-ul programeaza si afiseaza
 * bine, dar butoanele de pe notificare le construieste ca
 * `PendingIntent.getActivity(...)` (LocalNotificationManager.java:264) — adica
 * ORICE apasare deschide aplicatia, fara optiune. Ion a cerut exact contrariul:
 * „Facut" trebuie sa bifeze si sa inchida notificarea, atat. Un `BroadcastReceiver`
 * poate face asta fara WebView; o activitate nu.
 *
 * DE CE LISTA SE SALVEAZA. Alarmele puse cu `AlarmManager` NU supravietuiesc
 * repornirii telefonului — sistemul le sterge pe toate. Fara lista de aici,
 * prima repornire ar taia notificarile in tacere si ai afla abia cand n-ar mai
 * suna nimic intr-o dimineata. `RepornireReceiver` le pune la loc din ea.
 */
public class Programator {

    private static final String TAG = "PifProgramator";
    private static final String PREFS = "pif_notificari";
    private static final String CHEIE = "lista";

    static SharedPreferences prefs(Context ctx) {
        return ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** Inlocuieste TOT ce era programat cu lista primita. */
    static void pune(Context ctx, JSONArray lista) {
        anuleazaTot(ctx);
        prefs(ctx).edit().putString(CHEIE, lista.toString()).apply();
        armeaza(ctx, lista);
    }

    /**
     * O SINGURA alarma, FARA sa atinga lista salvata.
     *
     * Proba foloseste drumul asta: `pune()` inlocuieste tot ce era programat, deci
     * o apasare pe „Notificare de probă" ar fi sters in tacere diminetile deja
     * puse, iar Ion ar fi aflat abia a doua zi ca n-a mai sunat nimic. O proba
     * n-are voie sa strice lucrul pe care il verifica.
     */
    static void punaSingura(Context ctx, JSONObject n) {
        JSONArray una = new JSONArray();
        una.put(n);
        armeaza(ctx, una);
    }

    static void armeaza(Context ctx, JSONArray lista) {
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        long acum = System.currentTimeMillis();
        for (int i = 0; i < lista.length(); i++) {
            JSONObject n = lista.optJSONObject(i);
            if (n == null) continue;
            long cand = n.optLong("at", 0);
            if (cand <= acum) continue;              // ora a trecut deja
            PendingIntent pi = PendingIntent.getBroadcast(
                    ctx, n.optInt("id"), intentAlarma(ctx, n),
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            try {
                // `setExactAndAllowWhileIdle`: fara el, Android aduna alarmele si
                // le livreaza cand se trezeste din Doze — o notificare de
                // dimineata care vine la 8:40 nu mai e o notificare de dimineata.
                // Cand permisiunea de alarma exacta lipseste, `canScheduleExactAlarms`
                // e fals si cadem pe varianta inexacta: mai bine tarziu decat deloc.
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && !am.canScheduleExactAlarms()) {
                    am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cand, pi);
                } else {
                    am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cand, pi);
                }
            } catch (SecurityException e) {
                // Permisiunea poate fi retrasa intre verificare si apel.
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cand, pi);
            }
        }
    }

    static void anuleazaTot(Context ctx) {
        JSONArray veche = lista(ctx);
        AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
        for (int i = 0; i < veche.length(); i++) {
            JSONObject n = veche.optJSONObject(i);
            if (n == null) continue;
            PendingIntent pi = PendingIntent.getBroadcast(
                    ctx, n.optInt("id"), intentAlarma(ctx, n),
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            am.cancel(pi);
        }
        prefs(ctx).edit().remove(CHEIE).apply();
    }

    static JSONArray lista(Context ctx) {
        try {
            return new JSONArray(prefs(ctx).getString(CHEIE, "[]"));
        } catch (Exception e) {
            Log.w(TAG, "lista de notificari e stricata, o iau de la zero", e);
            return new JSONArray();
        }
    }

    /** Intentul care ajunge la `AlarmaReceiver`. Aceleasi extras la anulare ca
     *  la armare — altfel `PendingIntent` nu se recunoaste si nu se anuleaza. */
    private static Intent intentAlarma(Context ctx, JSONObject n) {
        Intent i = new Intent(ctx, AlarmaReceiver.class);
        i.setAction("org.iupif.pif.ALARMA." + n.optInt("id"));
        i.putExtra("id", n.optInt("id"));
        i.putExtra("titlu", n.optString("titlu"));
        i.putExtra("corp", n.optString("corp"));
        i.putExtra("token", n.optString("token"));
        i.putExtra("url", n.optString("url"));
        i.putExtra("server", n.optString("server"));
        i.putExtra("actiuni", n.optBoolean("actiuni", true));
        // Canalul: „taskuri-personale" implicit, „deplasari" pentru alarma de
        // plecare pe teren. Canalul e unitatea pe care o poate opri utilizatorul
        // din setarile Android, deci doua feluri de notificare care se pot refuza
        // separat trebuie sa stea pe canale separate.
        i.putExtra("canal", n.optString("canal", AlarmaReceiver.CANAL));
        // Al doilea buton difera dupa motivul notificarii (vezi `notificari.js`):
        // „Azi" pe un task fara termen, „Maine" pe unul deja scadent azi.
        i.putExtra("a2id", n.optString("a2id", "azi"));
        i.putExtra("a2text", n.optString("a2text", "Azi"));
        return i;
    }
}
