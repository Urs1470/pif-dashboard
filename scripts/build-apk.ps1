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

# UNDE E TOOLCHAIN-UL. Era scris literal `C:\Users\Ion Ursu\Repos\Tools`, adica
# numele de utilizator al UNEI masini — deci scriptul nu putea rula pe cealalta,
# desi acolo se dezvolta mai des. Acum se deduce din profil, si iese exact aceeasi
# cale pe PC-ul vechi.
# `$env:PIF_TOOLS` il muta oriunde (alt disc, folder partajat), fara sa atinga
# scriptul.
#
# ATENTIE: `app/build.gradle` citeste cheile ca
# `${user.home}/Repos/Tools/keys/keystore.properties` — deci daca muti Tools cu
# `PIF_TOOLS`, cheile TREBUIE sa ramana totusi sub profil, la calea aia. Gradle
# n-are de unde sti de variabila.
$T = if ($env:PIF_TOOLS) { $env:PIF_TOOLS } else { "$env:USERPROFILE\Repos\Tools" }

if (-not (Test-Path "$T\jdk-21")) { throw "JDK lipseste in $T\jdk-21 — ruleaza scripts\setup-apk-toolchain.ps1" }
if (-not (Test-Path "$T\android-sdk\platforms")) { throw "Android SDK incomplet in $T\android-sdk — ruleaza scripts\setup-apk-toolchain.ps1" }

# SEMNATURA SE VERIFICA INAINTE DE BUILD, nu dupa — si aici, langa celelalte doua
# porti de masina, nu mai jos: toate trei raspund la „pot construi de pe PC-ul
# asta?", iar raspunsul trebuie sa vina inainte de zece minute de Gradle.
#
# `app/build.gradle` aplica `signingConfig` DOAR daca gaseste fisierul, si trece
# mai departe in TACERE daca lipseste. Deci pe o masina cu toolchain dar fara chei
# iese un release nesemnat, care pe disc arata identic cu unul bun. Urcat pe
# server, telefonul ori il refuza (alta semnatura decat a aplicatiei instalate),
# ori — mai rau — rupe lantul pentru toate versiunile de dupa, si nu mai iesi din
# asta decat cu o reinstalare de la zero. Acelasi motiv pentru care mai jos se
# refuza urcarea unui build de debug; acolo era pazit, aici nu.
#
# Calea e cea pe care o citeste `build.gradle` — `${user.home}/Repos/Tools/keys/`
# — scrisa din profil, NU din `$T`: Gradle nu stie de `PIF_TOOLS`, deci daca am
# lua-o din `$T` si toolchain-ul ar fi mutat, poarta ar cauta cheile in alt loc
# decat cel in care Gradle le cauta, si ar trece un build nesemnat exact pe drumul
# pe care vrea sa-l pazeasca.
$CHEI = "$env:USERPROFILE\Repos\Tools\keys\keystore.properties"
if ($Release -and -not (Test-Path $CHEI)) {
    throw "Cheile de semnare lipsesc ($CHEI). Un release fara ele iese NESEMNAT si rupe actualizarea pe telefon — construieste pe masina care le are."
}

$env:JAVA_HOME        = "$T\jdk-21"
$env:ANDROID_HOME     = "$T\android-sdk"
$env:ANDROID_SDK_ROOT = "$T\android-sdk"
$env:ANDROID_USER_HOME= "$T\caches\android"
$env:GRADLE_USER_HOME = "$T\caches\gradle"
New-Item -ItemType Directory -Path "$T\caches\tmp" -Force | Out-Null
$env:TMP  = "$T\caches\tmp"      # vezi (1) — fara asta, build-ul nici nu porneste
$env:TEMP = "$T\caches\tmp"

# SINCRONIZAREA CAPACITOR, INAINTE DE GRADLE.
#
# `frontend/android/capacitor-cordova-android-plugins/` e GENERAT si gitignorat,
# iar `app/capacitor.build.gradle` (comis) il include neconditionat. Deci intr-o
# clona proaspata Gradle pica cu „Could not read script … cordova.variables.gradle
# as it does not exist" — dupa ce si-a descarcat cele ~700 MB si a compilat patru
# minute. Pe masina veche nu se vedea, fiindca folderul era acolo dintr-un `sync`
# de acum cateva luni.
#
# `sync` dureaza sub o secunda si e idempotent, deci se ruleaza mereu: pe langa
# scheletul de plugin-uri, el duce si `static/dist` in asset-urile aplicatiei —
# de unde vine `fara-retea.html`, singura pagina servita local (`server.errorPath`).
# Fara sync dupa un build de web, ecranul „fara retea" din APK ar ramane cel vechi.
#
# Rescrie `capacitor.build.gradle` si `capacitor.settings.gradle` cu LF, deci
# `git status` le arata modificate desi continutul e identic — `git diff` iese gol.
# E zgomot de sfarsit de linie, nu o schimbare.
Push-Location "$rad\frontend"
try {
    $cap = ".\node_modules\.bin\cap.cmd"
    if (-not (Test-Path $cap)) { throw "Lipseste $cap — ruleaza `npm install` in frontend\." }
    & $cap sync android
    if ($LASTEXITCODE -ne 0) { throw "cap sync android a esuat (cod $LASTEXITCODE)" }
} finally { Pop-Location }

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

# SEMNATURA SE COMPARA CU CEA DE PE TELEFON, NU DOAR „exista o cheie".
#
# Poarta de mai sus verifica doar ca fisierul cu chei EXISTA. Dar o cheie gresita
# — alta copiata, alta regenerata, sau un keystore cu mai multe aliasuri din care
# Gradle il ia pe altul — produce un APK perfect valid, semnat cu altceva. Android
# refuza sa-l instaleze peste aplicatia existenta, si afli abia pe telefon, dupa ce
# l-ai publicat pentru toate dispozitivele.
#
# Amprenta de mai jos e a APK-ului chiar acum publicat (`GET /api/app/apk`,
# `versionCode 1367786`, 7 aug 2026). NU e un secret: e certificatul PUBLIC, prezent
# in fiecare copie a aplicatiei. De aceea poate sta in git — secreta e cheia
# PRIVATA din `.jks`, care nu intra niciodata aici.
#
# Daca vreodata schimbi intentionat cheia de semnare, valoarea asta se schimba
# odata cu ea — si abia dupa ce ai acceptat ca toti utilizatorii dezinstaleaza.
$AMPRENTA = '753182ea0825c9766885c922092fb826b28d075a2815fde38e5f7efec38ecbf0'

if ($Release) {
    $bt2 = (Get-ChildItem "$T\android-sdk\build-tools" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
    $certs = & "$bt2\apksigner.bat" verify --print-certs $apk.FullName 2>&1
    $m = $certs | Select-String -Pattern 'certificate SHA-256 digest:\s*([0-9a-f]{64})'
    if (-not $m) { throw "Nu pot citi semnatura APK-ului construit — apksigner n-a intors nicio amprenta." }
    $amp = $m.Matches[0].Groups[1].Value
    if ($amp -ne $AMPRENTA) {
        $dn = ($certs | Select-String -Pattern 'certificate DN:\s*(.+)$').Matches[0].Groups[1].Value
        throw @"
SEMNATURA NU SE POTRIVESTE — NU se urca nimic.
  construit : $amp
              $dn
  asteptat  : $AMPRENTA
Un APK semnat altfel nu se poate instala peste aplicatia de pe telefon. Ori ai
copiat alt keystore, ori Gradle a folosit alt alias din el, ori build-ul a iesit
nesemnat (debug). Verifica `~\Repos\Tools\keys\keystore.properties`.
"@
    }
    "Semnatura: se potriveste cu aplicatia publicata."
}

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
