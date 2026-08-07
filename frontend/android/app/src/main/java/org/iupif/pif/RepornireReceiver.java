package org.iupif.pif;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * ALARMELE NU SUPRAVIETUIESC REPORNIRII.
 *
 * Android sterge toate alarmele din `AlarmManager` la oprirea telefonului. Fara
 * receiverul asta, prima repornire ar taia notificarile in TACERE — n-ar da
 * nicio eroare, pur si simplu n-ar mai suna nimic, iar tu ai afla peste cateva
 * zile ca ai ratat lucruri. Lista programata e pastrata de `Programator`, deci
 * se pun la loc exact aceleasi.
 */
public class RepornireReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context ctx, Intent intent) {
        String a = intent.getAction();
        if (a == null) return;
        if (Intent.ACTION_BOOT_COMPLETED.equals(a)
                || Intent.ACTION_MY_PACKAGE_REPLACED.equals(a)
                || "android.intent.action.QUICKBOOT_POWERON".equals(a)) {
            // Si dupa ACTUALIZAREA aplicatiei: inlocuirea pachetului anuleaza
            // la fel alarmele, iar o actualizare tacuta care opreste
            // notificarile e exact felul de regresie care nu se observa.
            Programator.armeaza(ctx, Programator.lista(ctx));
        }
    }
}
