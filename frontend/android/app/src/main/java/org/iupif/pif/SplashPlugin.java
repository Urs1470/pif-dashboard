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

    /**
     * Se cheama din JS cand pagina s-a asezat. Nu intoarce nimic de asteptat.
     *
     * NU RIDICA SPLASHUL IMEDIAT, si asta e tot rostul metodei.
     *
     * „Pagina s-a asezat" inseamna, in JS, ca datele au sosit si ca un `rAF` a
     * trecut. Dar intre cadrul pe care JS-ul il considera pictat si cadrul care
     * ajunge PE ECRAN mai e conducta de compozitare. Filmat pe telefon, la 60fps
     * (`scripts/filmeaza_pornirea.py`), asta se vedea asa:
     *
     *     2.217s  marca, pe fond
     *     2.233s  GOL — doar fondul
     *     2.250s  GOL — doar fondul
     *     2.267s  pagina, intreaga
     *
     * Doua cadre in care ecranul nu are nimic pe el. Ion, 2026-08-22: „tot cand
     * apare pagina mai exista o mica clipire". Nu era o animatie si nu era o
     * culoare gresita — era chiar golul dintre cele doua.
     *
     * `postVisualStateCallback` e API-ul facut pentru intrebarea asta: cheama
     * inapoi cand starea DOM de la momentul apelului a intrat intr-un cadru gata
     * de desenat. Mai asteptam un cadru dupa el, ca sa fie si pus pe ecran, si
     * abia atunci lasam splashul sa plece. Ordinea devine: pagina e pe ecran,
     * ACOPERITA de splash; splashul se scoate; dedesubt e deja tot.
     *
     * PLASA. Daca raportul nu vine niciodata (ecran stins, surprize de
     * producator), ridicam oricum dupa `RABDARE`. Fara ea am atarna pana la
     * plafonul din `MainActivity`, adica secunde bune de splash.
     */
    private static final long RABDARE = 500;

    @PluginMethod
    public void gata(PluginCall call) {
        call.resolve();
        final android.webkit.WebView web = getBridge().getWebView();
        web.post(new Runnable() {
            @Override
            public void run() {
                final Runnable ridica = new Runnable() {
                    @Override
                    public void run() {
                        paginaGata = true;
                    }
                };
                web.postDelayed(ridica, RABDARE);
                web.postVisualStateCallback(1, new android.webkit.WebView.VisualStateCallback() {
                    @Override
                    public void onComplete(long id) {
                        web.removeCallbacks(ridica);
                        // Inca un cadru: raportul spune „gata de desenat", nu
                        // „desenat". Diferenta dintre ele e chiar clipirea.
                        web.postOnAnimation(ridica);
                    }
                });
            }
        });
    }
}
