# Construieste APK-ul Android (shell Capacitor peste aplicatia live).
#
#   powershell -ExecutionPolicy Bypass -File scripts\build-apk.ps1            # debug
#   powershell -ExecutionPolicy Bypass -File scripts\build-apk.ps1 -Release   # release nesemnat
#
# DE CE EXISTA SCRIPTUL, si nu doar `gradlew assembleDebug`:
#
# 1. TEMP. Pe masina asta, `Selector.open()` din Java CRAPA daca TEMP e cel
#    implicit (`%LOCALAPPDATA%\Temp`): AF_UNIX-ul pe care JDK-ul il foloseste
#    pentru „pipe"-ul selectorului da `SocketException: Invalid argument: connect`.
#    Gradle il raporteaza ca „Unable to establish loopback connection" si NICIO
#    sarcina nu poate rula — nici macar `gradlew help`. Nu e Gradle, nu e
#    Capacitor si nu e versiunea de JDK (17 si 21 pica identic): orice program
#    Java cu NIO selectors pica la fel. Cu TEMP mutat in `Tools\caches\tmp`
#    merge. Diagnosticul complet: references/pc-config.md.
# 2. Toolchain-ul e PORTABIL, in `Repos\Tools\` — nu e in PATH-ul mostenit de
#    orice proces, deci caile se pun aici, explicit.
# 3. Cache-urile Gradle/Android stau tot in `Tools\caches\`, ca sa nu creasca
#    `~\.gradle` si `~\.android` in folderul de user.

param([switch]$Release, [switch]$Upload, [string]$Server = 'https://pif.iupif.org')

$ErrorActionPreference = 'Stop'
$rad = Split-Path -Parent $PSScriptRoot
$T = "C:\Users\Ion Ursu\Repos\Tools"

if (-not (Test-Path "$T\jdk-21")) { throw "JDK lipseste in $T\jdk-21 — vezi references/pc-config.md" }
if (-not (Test-Path "$T\android-sdk\platforms")) { throw "Android SDK incomplet in $T\android-sdk" }

$env:JAVA_HOME        = "$T\jdk-21"
$env:ANDROID_HOME     = "$T\android-sdk"
$env:ANDROID_SDK_ROOT = "$T\android-sdk"
$env:ANDROID_USER_HOME= "$T\caches\android"
$env:GRADLE_USER_HOME = "$T\caches\gradle"
New-Item -ItemType Directory -Path "$T\caches\tmp" -Force | Out-Null
$env:TMP  = "$T\caches\tmp"      # vezi (1) — fara asta, build-ul nici nu porneste
$env:TEMP = "$T\caches\tmp"

$sarcina = if ($Release) { 'assembleRelease' } else { 'assembleDebug' }
Push-Location "$rad\frontend\android"
try {
    & ".\gradlew.bat" $sarcina
    if ($LASTEXITCODE -ne 0) { throw "gradlew $sarcina a esuat (cod $LASTEXITCODE)" }
} finally { Pop-Location }

$apk = Get-ChildItem "$rad\frontend\android\app\build\outputs\apk" -Recurse -Filter *.apk -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $apk) {
    "Build terminat, dar nu am gasit niciun .apk in app\build\outputs\apk"
    exit 0
}
"APK: {0} ({1:N1} MB, {2})" -f $apk.FullName, ($apk.Length / 1MB), $apk.LastWriteTime

if (-not $Upload) { exit 0 }

# ---------------------------------------------------------------- publicare
# Doar RELEASE se urca. Un APK de debug e semnat cu cheia masinii; daca ar
# ajunge pe server, telefonul l-ar refuza la actualizare (alta semnatura) sau,
# mai rau, l-ar accepta si ar rupe lantul pentru toate versiunile de dupa.
if (-not $Release) { throw "Se urca doar build-uri de release: adauga -Release." }

$token = $env:PIF_API_TOKEN
if (-not $token) { throw "PIF_API_TOKEN nu e setat in mediu — fara el nu pot urca pe server." }

# Versiunea o citim din APK-ul CONSTRUIT, nu din build.gradle: acolo e calculata
# la rulare din data curenta, deci fisierul e singura sursa care stie sigur ce
# s-a produs.
$bt = (Get-ChildItem "$T\android-sdk\build-tools" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
$badging = & "$bt\aapt2.exe" dump badging $apk.FullName 2>$null | Select-String -Pattern "^package:" | Select-Object -First 1
if ($badging -match "versionCode='(\d+)'" ) { $cod = $Matches[1] } else { throw "Nu pot citi versionCode din APK." }
if ($badging -match "versionName='([^']+)'") { $nume = $Matches[1] } else { throw "Nu pot citi versionName din APK." }

Add-Type -AssemblyName System.Net.Http
$client = New-Object System.Net.Http.HttpClient
$client.Timeout = [TimeSpan]::FromMinutes(10)
$client.DefaultRequestHeaders.Add('User-Agent', 'Cowork-PIF/1.0')
$client.DefaultRequestHeaders.Add('Authorization', "Bearer $token")
$continut = New-Object System.Net.Http.MultipartFormDataContent
$fs = [System.IO.File]::OpenRead($apk.FullName)
try {
    $parte = New-Object System.Net.Http.StreamContent($fs)
    $parte.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse('application/vnd.android.package-archive')
    $continut.Add($parte, 'apk', 'pif.apk')
    $continut.Add((New-Object System.Net.Http.StringContent($cod)), 'versionCode')
    $continut.Add((New-Object System.Net.Http.StringContent($nume)), 'versionName')
    $r = $client.PostAsync("$Server/api/app/upload", $continut).Result
    $corp = $r.Content.ReadAsStringAsync().Result
    if (-not $r.IsSuccessStatusCode) { throw "Urcarea a esuat ($($r.StatusCode)): $corp" }
    "Urcat pe $Server — versiunea $nume ($cod)"
} finally { $fs.Dispose(); $client.Dispose() }
