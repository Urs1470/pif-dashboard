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

param([switch]$Release)

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
if ($apk) {
    "APK: {0} ({1:N1} MB, {2})" -f $apk.FullName, ($apk.Length / 1MB), $apk.LastWriteTime
} else {
    "Build terminat, dar nu am gasit niciun .apk in app\build\outputs\apk"
}
