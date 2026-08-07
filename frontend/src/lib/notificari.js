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

/** Taskurile care se califica LA O ANUMITA ZI. Vechimea se calculeaza fata de
 *  ziua notificarii, nu fata de azi: un task de o zi nu se califica azi, dar se
 *  califica poimaine — si tocmai de-asta programam in avans. */
export function taskuriDeNotificat(items, zi) {
  return (items || []).filter((t) => {
    if (t.sfera !== 'personal') return false
    if (t.status === 'done') return false
    if ((t.data_scadenta || '').trim()) return false
    return zileDeCand(t.created_at, zi) >= ZILE_VECHIME
  })
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
    for (const t of taskuriDeNotificat(items, zi)) {
      const zile = zileDeCand(t.created_at, zi)
      deProgramat.push({
        id: idNotificare(t.id, zi.toISOString().slice(0, 10)),
        title: t.titlu || 'Task personal',
        body: `Fără termen de ${zile} zile — bifează sau pune-i o zi.`,
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
