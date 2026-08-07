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

import { Capacitor } from '@capacitor/core'
import { LocalNotifications } from '@capacitor/local-notifications'

const ORA_TRIMITERE = 8      // ora locala, ca pe server
const ZILE_VECHIME = 2       // „sta fara termen de mai mult de N zile"
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
export function taskuriDeNotificat(items, zi) {
  const azi = ziISO(zi)
  const out = []
  for (const t of items || []) {
    if (t.sfera !== 'personal' || t.status === 'done') continue
    const scad = (t.data_scadenta || '').trim().slice(0, 10)
    if (scad) {
      if (scad === azi) out.push({ t, motiv: 'scadent' })
    } else if (zileDeCand(t.created_at, zi) >= ZILE_VECHIME) {
      out.push({ t, motiv: 'fara-termen', zile: zileDeCand(t.created_at, zi) })
    }
  }
  return out
}

async function pregatesteCanalul() {
  // Canal propriu: asa poti regla importanta si sunetul DOAR pentru astea, din
  // setarile Android, fara sa taci toata aplicatia.
  try {
    await LocalNotifications.createChannel({
      id: CANAL,
      name: 'Taskuri personale',
      description: 'Dimineata, taskurile personale ramase fara termen',
      importance: 4,               // HIGH — apare pe ecran, nu doar in sertar
      visibility: 1,
      lightColor: '#ffb454',
    })
  } catch (e) { /* canalele exista doar pe Android; pe rest, ignora */ }
}

async function pregatesteActiunile() {
  // Aceleasi doua iesiri ca in notificarea de push: „nu l-am facut" SAU „nu
  // i-am pus termen". Spre deosebire de service worker, aici handlerul ruleaza
  // in aplicatie, cu sesiunea ei — deci NU mai e nevoie de tokenul semnat.
  try {
    await LocalNotifications.registerActionTypes({
      types: [{
        id: 'task-personal',
        actions: [
          { id: 'done', title: 'Făcut' },
          { id: 'azi', title: 'Azi' },
        ],
      }],
    })
  } catch (e) { /* pe web nu exista tipuri de actiuni */ }
}

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
export async function reprogrameaza(items) {
  if (!esteNativ()) return 0
  const perm = await cerePermisiuni()
  if (!perm.notificari) return 0

  await pregatesteCanalul()
  await pregatesteActiunile()

  // Stergem DOAR ce am pus noi si mai e in viitor. `getPending` intoarce tot ce
  // e programat; fara curatare, un task bifat ar continua sa sune din alarma
  // veche, pentru ca reprogramarea nu suprascrie decat aceleasi id-uri.
  try {
    const { notifications } = await LocalNotifications.getPending()
    if (notifications?.length) {
      await LocalNotifications.cancel({ notifications: notifications.map((n) => ({ id: n.id })) })
    }
  } catch (_) { /* nimic de anulat */ }

  const acum = new Date()
  const deProgramat = []
  for (let d = 0; d < ZILE_INAINTE; d++) {
    const zi = new Date(acum.getFullYear(), acum.getMonth(), acum.getDate() + d, ORA_TRIMITERE, 0, 0, 0)
    if (zi <= acum) continue                       // dimineata de azi a trecut deja
    for (const { t, motiv, zile } of taskuriDeNotificat(items, zi)) {
      deProgramat.push({
        id: idNotificare(t.id, ziISO(zi)),
        title: t.titlu || 'Task personal',
        body: motiv === 'scadent'
          ? 'Scadent azi.'
          : `Fără termen de ${zile} zile — bifează sau pune-i o zi.`,
        schedule: { at: zi, allowWhileIdle: true },
        channelId: CANAL,
        actionTypeId: 'task-personal',
        extra: { taskId: t.id },
      })
    }
  }
  if (deProgramat.length) {
    await LocalNotifications.schedule({ notifications: deProgramat })
  }
  return deProgramat.length
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
  await pregatesteCanalul()
  await pregatesteActiunile()
  const cand = new Date(Date.now() + 40000)
  await LocalNotifications.schedule({
    notifications: [{
      id: 424242,
      title: 'Probă PIF',
      body: 'Dacă vezi asta, lanțul merge: permisiune, canal, alarmă, butoane.',
      schedule: { at: cand, allowWhileIdle: true },
      channelId: CANAL,
      // CU butoane, ca proba sa arate exact ce vezi dimineata. Nu poarta niciun
      // `taskId`, deci apasarea lor nu face nimic — ascultatorul iese din prima
      // linie. Asta e intentia: proba dovedeste ca butoanele APAR si ca sistemul
      // le accepta, nu inventeaza un task pe care sa-l bifeze.
      actionTypeId: 'task-personal',
      extra: {},
    }],
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

/** Leaga atingerea notificarii si cele doua actiuni de API. Se cheama O DATA,
 *  la pornirea aplicatiei. `peSchimbare` reincarca lista in aplicatie. */
export async function legaActiunile({ apiJson, navigate, peSchimbare }) {
  if (!esteNativ()) return
  await LocalNotifications.addListener('localNotificationActionPerformed', async (ev) => {
    const taskId = ev.notification?.extra?.taskId
    if (!taskId) return
    const azi = new Date()
    const zi = `${azi.getFullYear()}-${String(azi.getMonth() + 1).padStart(2, '0')}-${String(azi.getDate()).padStart(2, '0')}`
    try {
      if (ev.actionId === 'done') {
        await apiJson(`/api/global-tasks/${taskId}`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'done' }),
        })
      } else if (ev.actionId === 'azi') {
        await apiJson(`/api/global-tasks/${taskId}`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data_scadenta: zi }),
        })
      } else {
        // Atingerea corpului notificarii: doar deschide taskul.
        navigate?.(`/tasks?sfera=personal&focus=global:${taskId}`)
        return
      }
      await peSchimbare?.()
    } catch (e) {
      // Esecul nu are unde sa se vada (aplicatia poate fi in fundal), deci
      // ducem utilizatorul la task ca sa termine manual.
      navigate?.(`/tasks?sfera=personal&focus=global:${taskId}`)
    }
  })
}
