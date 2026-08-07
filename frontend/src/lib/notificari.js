// NOTIFICARILE DE DIMINEATA, PROGRAMATE PE TELEFON.
//
// DE CE EXISTA. Pana acum notificarea se DECIDEA si se TRIMITEA de pe server:
// o bucla la 300s in procesul Flask, la ora 8, prin VAPID -> Chrome -> service
// worker (`blueprints/push.py`). Lantul are patru locuri in care poate sa
// intarzie sau sa moara — serverul, reteaua, amanarea din Doze si managerul de
// baterie al producatorului — si pentru un PWA nu exista niciun remediu
// programatic pentru ultimele doua.
//
// Aici alarma o pune Android, pe telefon, din timp. Nu are nevoie nici de
// server, nici de retea in momentul in care suna. Asta e singura diferenta care
// conteaza intre „notificari de PWA" si „notificari de aplicatie".
//
// REGULA E ACEEASI ca pe server (`taskuri_de_notificat`), si trebuie sa ramana
// asa: task PERSONAL, nebifat, FARA data scadenta, mai vechi de doua zile.
// Cand se schimba una, se schimba amandoua.
//
// FEREASTRA RULANTA, nu o alarma pe zi. Programam ZILE_INAINTE dimineti in avans
// si le rescriem la fiecare deschidere a aplicatiei. Daca telefonul nu deschide
// aplicatia cateva zile, notificarile continua sa vina din ce era deja programat;
// se invechesc (un task bifat de pe PC ar mai suna o data), dar tacerea e mai rea
// decat o notificare in plus, iar deschiderea aplicatiei le reconciliaza.
//
// PE WEB NU FACE NIMIC. Acelasi bundle ruleaza si in browserul de pe PC, unde
// `isNativePlatform()` e fals si totul se opreste la prima linie.

import { Capacitor, registerPlugin } from '@capacitor/core'
import { LocalNotifications } from '@capacitor/local-notifications'

// PROGRAMAREA E NATIVA, NU A PLUGIN-ULUI.
// `@capacitor/local-notifications` ramane pentru ce face bine — permisiuni si
// comutatorul de alarma exacta — dar butoanele lui sunt construite ca
// `PendingIntent.getActivity` (LocalNotificationManager.java:264), deci ORICE
// apasare deschide aplicatia. Ion a cerut contrariul: „Facut" sa bifeze si sa
// inchida notificarea, atat. Un BroadcastReceiver poate; o activitate nu.
// Partea nativa: `android/app/src/main/java/org/iupif/pif/`.
const NotificariPif = registerPlugin('NotificariPif')

// SETARILE VIN DE PE SERVER, nu din constante.
// Erau scrise si aici, si in `blueprints/push.py`, cu un comentariu care cerea
// sa fie schimbate impreuna — o obligatie tinuta de disciplina, adica una care
// se rupe tacut: una se schimba, alta nu, si telefonul incepe sa creada altceva
// decat serverul despre aceeasi regula. Astea de mai jos sunt doar plasa de
// siguranta pentru cazul in care cererea de setari cade.
const IMPLICITE = { ora: 8, zileVechime: 2, scadente: true, faraTermen: true }
const ZILE_INAINTE = 7       // cate dimineti programam in avans
const CANAL = 'taskuri-personale'

export function esteNativ() {
  return Capacitor?.isNativePlatform?.() === true
}

/** Id numeric STABIL pentru (task, zi) — LocalNotifications cere int32, iar
 *  id-urile de task sunt UUID. Stabil inseamna ca reprogramarea suprascrie
 *  aceeasi alarma in loc sa adauge una noua langa ea. */
function idNotificare(taskId, zi) {
  let h = 2166136261
  for (const ch of `${taskId}:${zi}`) {
    h ^= ch.charCodeAt(0)
    h = Math.imul(h, 16777619)
  }
  return Math.abs(h % 2147483647)
}

function zileDeCand(createdAt, acum) {
  const d = new Date(String(createdAt).slice(0, 10))
  if (Number.isNaN(d.getTime())) return ZILE_VECHIME
  const zi = new Date(acum.getFullYear(), acum.getMonth(), acum.getDate())
  return Math.max(0, Math.round((zi - d) / 86400000))
}

function ziISO(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** Taskurile care se califica LA O ANUMITA ZI, si DE CE — motivul da textul.
 *
 *  Doua feluri, care nu se suprapun niciodata (unul cere data, celalalt cere
 *  lipsa ei):
 *    'scadent' — are termen exact in ziua aia. Notificarea vine dimineata, cand
 *                mai poti face ceva; Google Calendar NU poate acoperi cazul asta
 *                (mementoul unui eveniment all-day se numara inainte de miezul
 *                noptii, deci cel mai tarziu suna seara dinainte).
 *    'fara-termen' — sta nebifat si fara data de peste ZILE_VECHIME zile.
 *                Aceeasi regula ca `taskuri_de_notificat` de pe server.
 *
 *  Vechimea se masoara fata de ziua NOTIFICARII, nu fata de azi: un task de o zi
 *  nu se califica azi, dar se califica poimaine — de-asta programam in avans. */
export function taskuriDeNotificat(items, zi, setari = IMPLICITE) {
  const s = { ...IMPLICITE, ...(setari || {}) }
  const azi = ziISO(zi)
  const out = []
  for (const t of items || []) {
    if (t.sfera !== 'personal' || t.status === 'done') continue
    const scad = (t.data_scadenta || '').trim().slice(0, 10)
    if (scad) {
      if (s.scadente && scad === azi) out.push({ t, motiv: 'scadent' })
    } else if (s.faraTermen && zileDeCand(t.created_at, zi) >= s.zileVechime) {
      out.push({ t, motiv: 'fara-termen', zile: zileDeCand(t.created_at, zi) })
    }
  }
  return out
}

// Canalul il creeaza partea NATIVA (`AlarmaReceiver.creeazaCanalul`), acolo unde
// se si afiseaza notificarile — un canal creat din doua locuri ar diverge tacut
// la prima schimbare de importanta.

/** Permisiunea de notificari (Android 13+ o cere explicit) + alarme exacte.
 *  Intoarce ce s-a obtinut, ca apelantul sa poata spune ce s-a pierdut. */
export async function cerePermisiuni() {
  const out = { notificari: false, exacte: false }
  const p = await LocalNotifications.checkPermissions()
  out.notificari = p.display === 'granted'
  if (!out.notificari) {
    const r = await LocalNotifications.requestPermissions()
    out.notificari = r.display === 'granted'
  }
  // Android 12+: fara SCHEDULE_EXACT_ALARM alarma e „inexacta" si poate aluneca
  // cu zeci de minute. Utilizatorul o poate opri oricand din setari, iar cand o
  // opreste, sistemul reporneste aplicatia SI STERGE alarmele exacte deja puse —
  // de aceea se verifica la fiecare pornire, nu o singura data.
  try {
    const e = await LocalNotifications.checkExactNotificationSetting()
    out.exacte = e.exact_alarm === 'granted'
  } catch (_) { out.exacte = false }
  return out
}

/** Rescrie fereastra de notificari din lista de taskuri primita.
 *  Intoarce cate alarme au ramas programate. */
export async function reprogrameaza(items, setari = IMPLICITE) {
  if (!esteNativ()) return 0
  const s = { ...IMPLICITE, ...(setari || {}) }
  const perm = await cerePermisiuni()
  if (!perm.notificari) return 0

  const acum = new Date()
  const deProgramat = []
  for (let d = 0; d < ZILE_INAINTE; d++) {
    const zi = new Date(acum.getFullYear(), acum.getMonth(), acum.getDate() + d, s.ora, 0, 0, 0)
    if (zi <= acum) continue                       // ora de azi a trecut deja
    for (const { t, motiv, zile } of taskuriDeNotificat(items, zi, s)) {
      deProgramat.push({
        id: idNotificare(t.id, ziISO(zi)),
        taskId: t.id,
        at: zi.getTime(),
        titlu: t.titlu || 'Task personal',
        corp: motiv === 'scadent'
          ? 'Scadent azi.'
          : `Fără termen de ${zile} zile — bifează sau pune-i o zi.`,
        url: `/#/tasks?sfera=personal&focus=global:${t.id}`,
        server: window.location.origin,
        actiuni: true,
        // AL DOILEA BUTON DEPINDE DE MOTIV.
        // Pe „fara termen", iesirea e sa-i dai o zi: „Azi".
        // Pe „scadent azi", „Azi" ar scrie data pe care taskul o are DEJA — un
        // buton care pare ca amana si nu face nimic e mai rau decat niciunul.
        // Acolo singura amanare cu inteles e „Maine".
        a2id: motiv === 'scadent' ? 'maine' : 'azi',
        a2text: motiv === 'scadent' ? 'Mâine' : 'Azi',
      })
    }
  }

  // TOKENURILE DE ACTIUNE. Receiverul nativ care trateaza „Facut"/„Azi" nu are
  // WebView, deci nici cookie de sesiune, nici token CSRF — la fel ca service
  // worker-ul, pentru care `/api/push/action` a fost deja construita. Cerem de
  // aici cate un token semnat per task si il punem in alarma; moare cu ea.
  const idsUnice = [...new Set(deProgramat.map((n) => n.taskId))]
  if (idsUnice.length) {
    try {
      const tokenuri = await apiJsonIntern('/api/push/tokens', { ids: idsUnice })
      for (const n of deProgramat) n.token = tokenuri[n.taskId] || ''
    } catch (e) {
      // Fara tokenuri programam oricum, dar FARA butoane: o notificare care
      // arata „Facut" si nu face nimic e mai rea decat una fara buton.
      for (const n of deProgramat) { n.token = ''; n.actiuni = false }
    }
  }

  // `programeaza` INLOCUIESTE tot ce era pus. Nu adaugam: un task bifat intre
  // timp trebuie sa dispara, iar alarma lui veche ar suna mai departe.
  const { programate } = await NotificariPif.programeaza({ notificari: deProgramat })
  return programate ?? deProgramat.length
}

/** POST minimal, ca modulul sa nu depinda de `lib/api.js` (care aduce toast-uri
 *  si stare de UI intr-un fisier care trebuie sa ramana pur). */
async function apiJsonIntern(cale, corp) {
  const csrf = document.cookie.match(/csrf_token=([^;]+)/)
  const r = await fetch(cale, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrf ? { 'X-CSRF-Token': csrf[1] } : {}),
    },
    body: JSON.stringify(corp),
  })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

/** PROBA. Programeaza o notificare peste ~40 de secunde, pe acelasi canal si cu
 *  aceleasi doua actiuni ca cele adevarate.
 *
 *  De ce nu e de prisos: singurul moment in care lantul se vede lucrand e la 08:00,
 *  iar daca ceva din el e rupt — permisiunea refuzata, alarma exacta oprita din
 *  setari, canalul tacut — afli abia a doua zi dimineata, si nu afli CE anume.
 *  Proba trece exact prin acelasi drum: permisiuni, canal, alarma, butoane.
 *
 *  Nu e „instant": o notificare pusa pe loc n-ar demonstra ca ALARMA merge, doar
 *  ca API-ul raspunde. Intarzierea e mica, dar reala — inchide aplicatia dupa ce
 *  o pornesti, ca s-o vezi cum o vezi dimineata.
 *
 *  Intoarce mesajul de aratat, sau arunca cu un motiv citibil. */
export async function probeaza() {
  if (!esteNativ()) throw new Error('Proba merge doar în aplicația de pe telefon.')
  const perm = await cerePermisiuni()
  if (!perm.notificari) throw new Error('Permisiunea pentru notificări e refuzată — dă-o din setările aplicației.')
  // `proba`, nu `programeaza`: a doua INLOCUIESTE fereastra programata, deci o
  // apasare pe butonul de probă ar fi șters în tăcere diminețile deja puse.
  await NotificariPif.proba({
    id: 424242,
    at: Date.now() + 40000,
    titlu: 'Probă PIF',
    corp: 'Dacă vezi asta, lanțul merge: permisiune, canal, alarmă, butoane.',
    server: window.location.origin,
    // FARA token: butoanele APAR (asta se probează — că sistemul le acceptă pe
    // canalul nostru), dar n-au ce bifa, iar receiverul doar închide notificarea.
    // Un token fals ar fi mai rău: ar părea că merge și ar eșua tăcut pe server.
    token: '',
    actiuni: true,
  })
  if (perm.exacte) {
    return 'Programată peste 40 de secunde, cu alarmă exactă. Închide aplicația.'
  }
  // NU-L TRIMITE PRIN MENIURI — DESCHIDE-I ECRANUL.
  // Calea difera de la un producator la altul („Alarme si mementouri" e sub
  // Aplicatii la unii, sub Acces special la altii), iar o instructiune care nu
  // se potriveste cu ce vede pe ecran e mai rea decat niciuna: te face sa crezi
  // ca ai gresit tu. Sistemul stie unde e comutatorul, deci il lasam pe el.
  try {
    await LocalNotifications.changeExactNotificationSetting()
    return 'Programată, dar alarma EXACTĂ e oprită — dimineața ar putea întârzia. '
         + 'Ți-am deschis ecranul: pornește comutatorul, apoi repetă proba.'
  } catch (e) {
    return 'Programată peste ~40 de secunde, dar alarma EXACTĂ e oprită — poate întârzia. '
         + 'Setări → Aplicații → PIF → Alarme și mementouri.'
  }
}

// ASCULTATORUL DE ACTIUNI A DISPARUT, si asta e tot rostul turei.
//
// Butoanele „Facut"/„Azi" sunt tratate acum NATIV, de `ActiuneReceiver`, care
// ruleaza fara WebView: apesi, taskul se bifeaza pe server, notificarea dispare
// si aplicatia nu se deschide. Cat timp trecea prin JS, orice apasare TREBUIA sa
// porneasca aplicatia — ascultatorul n-avea unde sa ruleze altfel.
//
// Atingerea CORPULUI notificarii deschide in continuare aplicatia. Acolo chiar
// vrei sa vezi taskul, iar aterizarea implicita pe telefon e oricum
// Taskuri/Personal (vezi `lib/router.svelte.js`), deci ajungi unde trebuie.
