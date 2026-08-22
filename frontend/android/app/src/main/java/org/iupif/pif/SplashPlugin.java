package org.iupif.pif;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * CAND E PAGINA GATA SA FIE VAZUTA.
 *
 * DE CE EXISTA. Pana acum erau DOUA splashuri puse cap la cap: cel al
 * sistemului (Android 12+ il deseneaza intotdeauna) si un val propriu, desenat
 * de pagina in `index.html`. Le-am facut sa arate aceeasi marca, la aceeasi
 * marime si in acelasi loc — si tot se citeau ca doua etape, fiindca splashul de
 * sistem isi face IESIREA lui inainte ca pagina sa apuce sa deseneze ceva. Ion,
 * 2026-08-22: „mai intai porneste nativ apoi apare cea web, tot se primeste in
 * doua parti".
 *
 * Doua splashuri nu se pot cusuta. Deci a ramas UNUL: cel al sistemului, tinut pe
 * ecran pana cand pagina e chiar gata, si scos de noi, cu o singura miscare. In
 * aplicatie pagina nu mai deseneaza niciun val (vezi `html.din-nativ` in
 * `frontend/index.html`).
 *
 * CE ANUNTA ACEST PLUGIN e exact raspunsul pe care doar pagina il stie: „datele
 * au sosit, fonturile s-au asezat, nu mai e niciun schelet pe ecran" — vezi
 * `frontend/src/lib/splash.js`, unde intrebarea asta era deja pusa si raspunsul
 * mergea catre valul web. Acum merge incoace.
 *
 * Fara plugin n-ar merge: `onPageLoaded` spune doar ca s-a incarcat documentul,
 * nu ca lista lui are randuri. Diferenta dintre cele doua e chiar scheletul pe
 * care valul exista sa-l acopere.
 */
@CapacitorPlugin(name = "Splash")
public class SplashPlugin extends Plugin {

    /**
     * Pusa de pagina, citita de `MainActivity` la fiecare cadru desenat.
     * `volatile`: se scrie din firul puntii si se citeste din cel de desenare.
     * `static`: activitatea intreaba starea inainte ca plugin-ul sa aiba o
     * instanta legata de ea, iar pentru un singur ecran nu exista ambiguitate.
     */
    public static volatile boolean paginaGata = false;

    /** Se cheama din JS cand pagina s-a asezat. Nu intoarce nimic de asteptat. */
    @PluginMethod
    public void gata(PluginCall call) {
        paginaGata = true;
        call.resolve();
    }
}
