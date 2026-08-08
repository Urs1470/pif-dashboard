package org.iupif.pif;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Color;
import android.os.Build;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

/**
 * A SUNAT ORA: construieste si afiseaza notificarea.
 *
 * Butoanele merg la `ActiuneReceiver` prin `getBroadcast`, NU la activitate:
 * asta e toata diferenta fata de plugin-ul de Capacitor si tot motivul pentru
 * care exista clasele astea. Apesi „Facut", taskul se bifeaza, notificarea
 * dispare, si aplicatia nu se deschide.
 *
 * Atingerea CORPULUI notificarii deschide aplicatia — acolo chiar vrei sa vezi
 * taskul, deci acolo activitatea e raspunsul corect.
 */
public class AlarmaReceiver extends BroadcastReceiver {

    static final String CANAL = "taskuri-personale";
    /** Plecarile pe teren (turul 15). Canal separat fiindca se poate refuza
     *  separat: „nu vreau sa ma anunte seara ca plec maine" si „nu vreau
     *  taskurile de dimineata" sunt doua decizii diferite, iar canalul e exact
     *  unitatea pe care Android o da utilizatorului ca s-o ia. */
    static final String CANAL_DEPLASARI = "deplasari";

    /** Accentul, pe tema deschisa si pe cea intunecata (vezi tokens.css). */
    static final String ACCENT_DESCHIS = "#5980a6";
    static final String ACCENT_INTUNECAT = "#8ab2d9";

    /**
     * TENTA URMEAZA TEMA SISTEMULUI, si se citeste LA FIECARE NOTIFICARE.
     *
     * Nu se poate citi o singura data si tine minte: alarma sună dimineața, iar
     * telefonul poate fi trecut pe temă închisă între programare si sunet
     * (programul de noapte face exact asta). Cardul e desenat de sistem in
     * momentul afisarii, deci si culoarea trebuie decisa atunci.
     */
    static int accent(Context ctx) {
        int mod = ctx.getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK;
        boolean noapte = mod == Configuration.UI_MODE_NIGHT_YES;
        return Color.parseColor(noapte ? ACCENT_INTUNECAT : ACCENT_DESCHIS);
    }

    static void creeazaCanalul(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        if (nm == null) return;

        NotificationChannel c = new NotificationChannel(
                CANAL, "Taskuri personale", NotificationManager.IMPORTANCE_HIGH);
        c.setDescription("Dimineața, taskurile personale scadente sau rămase fără termen");
        // LUMINA LED-ULUI E O SINGURA VALOARE, cu buna stiinta: se fixeaza la
        // CREAREA canalului si Android nu o mai schimba dupa aceea, oricat ai
        // rescrie-o. Deci aici nu are sens sa urmeze tema — ar fi doar tema din
        // clipa primei porniri, inghetata pentru totdeauna.
        c.setLightColor(Color.parseColor(ACCENT_DESCHIS));
        c.setShowBadge(true);
        nm.createNotificationChannel(c);

        NotificationChannel d = new NotificationChannel(
                CANAL_DEPLASARI, "Deplasări", NotificationManager.IMPORTANCE_HIGH);
        d.setDescription("Seara dinaintea unei plecări pe teren");
        d.setLightColor(Color.parseColor(ACCENT_DESCHIS));
        d.setShowBadge(true);
        nm.createNotificationChannel(d);
    }

    @Override
    public void onReceive(Context ctx, Intent intent) {
        creeazaCanalul(ctx);

        int id = intent.getIntExtra("id", 0);
        String titlu = intent.getStringExtra("titlu");
        String corp = intent.getStringExtra("corp");
        String token = intent.getStringExtra("token");
        String url = intent.getStringExtra("url");
        String server = intent.getStringExtra("server");
        boolean actiuni = intent.getBooleanExtra("actiuni", true);
        String canal = intent.getStringExtra("canal");
        if (canal == null || canal.isEmpty()) canal = CANAL;

        Intent deschide = new Intent(ctx, MainActivity.class);
        deschide.setAction(Intent.ACTION_MAIN);
        deschide.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (url != null) deschide.putExtra("pif_url", url);
        PendingIntent piDeschide = PendingIntent.getActivity(
                ctx, id, deschide,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        NotificationCompat.Builder b = new NotificationCompat.Builder(ctx, canal)
                .setSmallIcon(R.drawable.ic_stat_pif)
                .setColor(accent(ctx))
                .setContentTitle(titlu == null ? "Task personal" : titlu)
                .setContentText(corp == null ? "" : corp)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(corp == null ? "" : corp))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_REMINDER)
                .setContentIntent(piDeschide)
                .setAutoCancel(true);

        // Butoanele depind DOAR de `actiuni`, nu si de token: proba le pune fara
        // token, ca sa se vada ca sistemul le accepta pe canalul nostru, iar
        // `ActiuneReceiver` stie sa doar inchida notificarea cand n-are ce bifa.
        if (actiuni) {
            String a2id = intent.getStringExtra("a2id");
            String a2text = intent.getStringExtra("a2text");
            if (a2id == null || a2id.isEmpty()) { a2id = "azi"; a2text = "Azi"; }
            b.addAction(0, "Făcut", actiune(ctx, id, "done", token, server));
            b.addAction(0, a2text, actiune(ctx, id, a2id, token, server));
        }

        try {
            NotificationManagerCompat.from(ctx).notify(id, b.build());
        } catch (SecurityException e) {
            // POST_NOTIFICATIONS retrasa intre programare si sunet: nu e nimic
            // de reparat aici, notificarea pur si simplu nu se arata.
        }
    }

    /** `getBroadcast`, nu `getActivity` — aici e toata poanta. */
    private PendingIntent actiune(Context ctx, int id, String ce, String token, String server) {
        Intent i = new Intent(ctx, ActiuneReceiver.class);
        i.setAction("org.iupif.pif.ACTIUNE." + id + "." + ce);
        i.putExtra("id", id);
        i.putExtra("actiune", ce);
        i.putExtra("token", token);
        i.putExtra("server", server);
        return PendingIntent.getBroadcast(ctx, (id * 31) + ce.hashCode(), i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
}
