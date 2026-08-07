package org.iupif.pif;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

import androidx.core.app.NotificationManagerCompat;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * „FACUT" / „AZI", FARA SA SE DESCHIDA APLICATIA.
 *
 * Un `BroadcastReceiver` ruleaza fara WebView si fara activitate, deci nu poate
 * folosi sesiunea din browser — si nici n-are de unde lua tokenul CSRF. Nu e o
 * problema noua: exact asta era si situatia service worker-ului, iar serverul
 * are deja raspunsul — `/api/push/action` se autentifica printr-un token semnat
 * HMAC care acopera UN task, doua actiuni, 48 de ore, si e scutit de CSRF
 * (`csrf.py`, `_EXEMPT_ENDPOINTS`). Tokenul vine in notificare si moare cu ea.
 *
 * `goAsync()` fiindca reteaua nu incape in cele ~10 secunde in care sistemul
 * lasa un receiver sa traiasca pe firul principal — fara el, apelul ar fi taiat
 * la jumatate exact cand telefonul e lent.
 */
public class ActiuneReceiver extends BroadcastReceiver {

    private static final String TAG = "PifActiune";

    @Override
    public void onReceive(Context ctx, Intent intent) {
        final int id = intent.getIntExtra("id", 0);
        final String actiune = intent.getStringExtra("actiune");
        final String token = intent.getStringExtra("token");
        final String server = intent.getStringExtra("server");

        // Notificarea dispare IMEDIAT, inainte de reteaua care poate dura.
        // Altfel ai apasa si n-ai vedea nimic intamplandu-se — si ai mai apasa
        // o data. Serverul e oricum idempotent pe `done` (`WHERE status != 'done'`).
        NotificationManagerCompat.from(ctx).cancel(id);

        if (token == null || token.isEmpty() || server == null || server.isEmpty()) return;

        final PendingResult rezultat = goAsync();
        new Thread(() -> {
            HttpURLConnection c = null;
            try {
                JSONObject corp = new JSONObject();
                corp.put("token", token);
                corp.put("action", actiune);
                c = (HttpURLConnection) new URL(server + "/api/push/action").openConnection();
                c.setRequestMethod("POST");
                c.setConnectTimeout(15000);
                c.setReadTimeout(15000);
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                c.setRequestProperty("User-Agent", "PIF-Android/1.0");
                try (OutputStream os = c.getOutputStream()) {
                    os.write(corp.toString().getBytes(StandardCharsets.UTF_8));
                }
                int cod = c.getResponseCode();
                if (cod >= 400) {
                    // 403 = token expirat (peste 48h). Nimic de reparat automat:
                    // taskul se bifeaza din aplicatie, care e la o atingere.
                    Log.w(TAG, "actiunea a fost refuzata: HTTP " + cod);
                }
            } catch (Exception e) {
                // Fara retea, actiunea se pierde — notificarea a disparut deja.
                // Alternativa (sa o punem la loc si sa reincercam) ar cere o coada
                // si un WorkManager; nu merita pentru „am bifat un task personal".
                Log.w(TAG, "actiunea nu a ajuns la server", e);
            } finally {
                if (c != null) c.disconnect();
                rezultat.finish();
            }
        }).start();
    }
}
