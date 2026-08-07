// ACTUALIZAREA CARCASEI NATIVE.
//
// Interfata se actualizeaza singura: WebView-ul incarca aplicatia LIVE de pe
// server, deci un `git push` ajunge pe telefon la urmatoarea pornire. Carcasa —
// permisiuni, plugin-uri, versiune de Capacitor — nu: ea e in APK.
//
// Fara modulul asta, singurul mecanism prin care afli ca APK-ul tau e vechi e
// „isi aminteste cineva sa verifice", adica exact felul de intretinere care nu
// se face. Si nu se vede: aplicatia merge mai departe, doar ca fara ce s-a
// adaugat in carcasa.
//
// CE NU FACE: nu instaleaza in tacere. Android nu permite unei aplicatii
// instalate lateral sa se actualizeze fara confirmare, si e bine ca e asa. Ce
// se automatizeaza aici e tot restul: aflatul, descarcatul, si predarea
// fisierului catre instalatorul de sistem. Ramane o apasare, nu un drum la PC.
//
// PE WEB NU FACE NIMIC — `esteNativ()` e fals si totul se opreste la prima linie.

import { App } from '@capacitor/app'
import { Directory, Filesystem } from '@capacitor/filesystem'
import { registerPlugin } from '@capacitor/core'

import { esteNativ } from './notificari.js'

const Instalare = registerPlugin('Instalare')

const FISIER = 'pif-update.apk'

/** Versiunea instalata acum. `build` e `versionCode`-ul din build.gradle —
 *  numarul crescator din care e facuta comparatia; `version` e doar eticheta. */
async function versiuneaMea() {
  const info = await App.getInfo()
  return { cod: parseInt(info.build, 10) || 0, nume: info.version || '?' }
}

/** { nou: bool, cod, nume, size } sau null daca nu se poate raspunde. */
export async function verifica(apiJson) {
  if (!esteNativ()) return null
  try {
    const [mea, server] = await Promise.all([versiuneaMea(), apiJson('/api/app/version')])
    if (!server?.disponibil) return null
    return {
      nou: Number(server.versionCode) > mea.cod,
      cod: Number(server.versionCode),
      nume: server.versionName,
      size: Number(server.size) || 0,
      acum: mea,
    }
  } catch (e) {
    return null                    // fara retea nu e o eroare, e doar „nu acum"
  }
}

function base64Din(blob) {
  return new Promise((rezolva, respinge) => {
    const fr = new FileReader()
    fr.onerror = () => respinge(new Error('Nu am putut citi fișierul descărcat.'))
    // `result` e un data: URL; plugin-ul vrea doar partea de dupa virgula.
    fr.onload = () => rezolva(String(fr.result).split(',', 2)[1] || '')
    fr.readAsDataURL(blob)
  })
}

/** Descarca APK-ul si deschide instalatorul. Arunca cu mesaj citibil.
 *  `peProgres(procent)` e optional. */
export async function descarcaSiInstaleaza(peProgres) {
  if (!esteNativ()) throw new Error('Merge doar în aplicația de pe telefon.')

  const { permis } = await Instalare.poateInstala()
  if (!permis) {
    await Instalare.cerePermisiuni?.().catch(() => {})
    await Instalare.cerePermisiunea?.().catch(() => {})
    throw new Error('Dă-i voie să instaleze aplicații („Surse necunoscute"), apoi încearcă din nou.')
  }

  // Descarcarea trece prin `fetch`, nu prin plugin: asa merge pe cookie-ul de
  // sesiune al WebView-ului si nu trebuie sa plimbam niciun token pe alt drum.
  const r = await fetch('/api/app/apk', { credentials: 'include' })
  if (!r.ok) throw new Error(`Serverul a răspuns ${r.status} la descărcare.`)

  let blob
  const total = Number(r.headers.get('Content-Length')) || 0
  if (peProgres && r.body && total) {
    const cititor = r.body.getReader()
    const bucati = []
    let luat = 0
    for (;;) {
      const { done, value } = await cititor.read()
      if (done) break
      bucati.push(value)
      luat += value.length
      peProgres(Math.round((luat / total) * 100))
    }
    blob = new Blob(bucati)
  } else {
    blob = await r.blob()
  }

  // In CACHE, nu in Documents: e un fisier de unica folosinta, iar
  // `res/xml/file_paths.xml` publica deja `cache-path`, deci FileProvider are
  // voie sa-l dea instalatorului.
  await Filesystem.writeFile({
    path: FISIER,
    data: await base64Din(blob),
    directory: Directory.Cache,
  })
  const { uri } = await Filesystem.getUri({ path: FISIER, directory: Directory.Cache })
  await Instalare.instaleaza({ path: uri })
}
