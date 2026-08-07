package org.iupif.pif;

import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;

/**
 * PREDAREA UNUI APK CATRE INSTALATORUL DE SISTEM.
 *
 * Aplicatia nu vine dintr-un magazin, deci nimeni nu o actualizeaza in locul ei.
 * Restul lantului (afla ca exista versiune noua, o descarca) se face din JS;
 * pasul asta nu se poate: deschiderea instalatorului cere un `Intent` si un
 * `content://` produs de FileProvider — un `file://` arunca FileUriExposedException
 * din Android 7 incoace.
 *
 * CE NU FACE, cu buna stiinta: nu instaleaza. Android nu permite unei aplicatii
 * instalate lateral sa actualizeze in tacere — dialogul de confirmare il apasa
 * utilizatorul, si asta e o granita, nu o lipsa. Aici doar i se pune fisierul in
 * fata.
 */
@CapacitorPlugin(name = "Instalare")
public class InstalarePlugin extends Plugin {

    /**
     * Are aplicatia voie sa ceara instalari? Permisiunea
     * `REQUEST_INSTALL_PACKAGES` e declarata in manifest, dar din Android 8 e
     * si un COMUTATOR per aplicatie, pe care utilizatorul il da separat. Fara
     * verificarea asta, apasarea pe „Actualizeaza" ar deschide un instalator
     * care refuza, fara sa spuna de ce.
     */
    @PluginMethod
    public void poateInstala(PluginCall call) {
        JSObject r = new JSObject();
        boolean ok = Build.VERSION.SDK_INT < Build.VERSION_CODES.O
                || getContext().getPackageManager().canRequestPackageInstalls();
        r.put("permis", ok);
        call.resolve(r);
    }

    /** Deschide ecranul de unde se da permisiunea, daca lipseste. */
    @PluginMethod
    public void cerePermisiunea(PluginCall call) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Intent i = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getContext().getPackageName()));
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(i);
        }
        call.resolve();
    }

    /**
     * @param path calea nativa a APK-ului descarcat (din Filesystem.getUri).
     */
    @PluginMethod
    public void instaleaza(PluginCall call) {
        String cale = call.getString("path");
        if (cale == null || cale.isEmpty()) {
            call.reject("Lipseste calea fisierului.");
            return;
        }
        // `file://` vine de la Filesystem.getUri; instalatorul vrea o cale reala.
        if (cale.startsWith("file://")) {
            cale = Uri.parse(cale).getPath();
        }
        File f = new File(cale);
        if (!f.isFile()) {
            call.reject("Fisierul nu exista: " + cale);
            return;
        }
        try {
            Uri uri = FileProvider.getUriForFile(
                    getContext(), getContext().getPackageName() + ".fileprovider", f);
            Intent i = new Intent(Intent.ACTION_VIEW);
            i.setDataAndType(uri, "application/vnd.android.package-archive");
            // Prima e obligatorie: fara ea instalatorul primeste un URI pe care
            // n-are dreptul sa-l citeasca si esueaza cu „fisier corupt".
            i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(i);
            call.resolve();
        } catch (IllegalArgumentException e) {
            // FileProvider refuza caile care nu sunt in `res/xml/file_paths.xml`.
            call.reject("Calea nu e publicabila prin FileProvider: " + cale, e);
        } catch (Exception e) {
            call.reject("Nu am putut deschide instalatorul: " + e.getMessage(), e);
        }
    }
}
