# Instaleaza toolchain-ul portabil pentru build-ul APK, in `~\Repos\Tools`.
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup-apk-toolchain.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\setup-apk-toolchain.ps1 -Verifica
#
# DE CE PORTABIL, si nu Android Studio: `build-apk.ps1` tine tot (JDK, SDK,
# cache-urile Gradle si Android) intr-un singur folder, ca sa nu creasca `~\.gradle`
# si `~\.android` in profil si ca doua masini sa aiba exact aceeasi asezare.
#
# CE NU FACE SCRIPTUL ASTA: nu creeaza cheile de semnare. Un APK semnat cu ALTA
# cheie decat cea a aplicatiei deja instalate nu se poate instala peste ea — Android
# il refuza, si singura iesire e dezinstalare + reinstalare, adica pierzi datele
# locale ale aplicatiei. Deci cheile se COPIAZA de pe masina care le are, nu se
# regenereaza. Vezi mesajul de la final.
#
# Nu cere drepturi de administrator si nu atinge PATH-ul de sistem: tot ce pune e
# sub `~\Repos\Tools`, iar `build-apk.ps1` isi seteaza singur variabilele.

param(
    [switch]$Verifica,
    # Numarul de build al uneltelor de linie de comanda Google. Se schimba in timp;
    # daca descarcarea da 404, ia-l pe cel curent de la
    # https://developer.android.com/studio#command-line-tools-only
    [string]$CmdlineTools = '13114758'
)

$ErrorActionPreference = 'Stop'
$T = if ($env:PIF_TOOLS) { $env:PIF_TOOLS } else { "$env:USERPROFILE\Repos\Tools" }

# Versiunile vin din proiect, nu din memorie: `variables.gradle` e sursa.
$rad  = Split-Path -Parent $PSScriptRoot
$vars = Get-Content "$rad\frontend\android\variables.gradle" -Raw
if ($vars -match 'compileSdkVersion\s*=\s*(\d+)') { $SDK = $Matches[1] }
else { throw "Nu pot citi compileSdkVersion din variables.gradle" }
$PACHETE = @('platform-tools', "platforms;android-$SDK", "build-tools;$SDK.0.0")

function Stare {
    [pscustomobject]@{
        Jdk    = Test-Path "$T\jdk-21\bin\java.exe"
        Sdkman = Test-Path "$T\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat"
        Platf  = Test-Path "$T\android-sdk\platforms\android-$SDK"
        Build  = Test-Path "$T\android-sdk\build-tools\$SDK.0.0"
        Chei   = Test-Path "$env:USERPROFILE\Repos\Tools\keys\keystore.properties"
    }
}

function Raport($s) {
    $bif = { param($b) if ($b) { '  [x]' } else { '  [ ]' } }
    "$(& $bif $s.Jdk)    JDK 21              $T\jdk-21"
    "$(& $bif $s.Sdkman) unelte SDK          $T\android-sdk\cmdline-tools\latest"
    "$(& $bif $s.Platf)  platforms;android-$SDK"
    "$(& $bif $s.Build)  build-tools;$SDK.0.0"
    "$(& $bif $s.Chei)   chei de semnare     `$env:USERPROFILE\Repos\Tools\keys\keystore.properties"
}

if ($Verifica) { Raport (Stare); exit 0 }

New-Item -ItemType Directory -Path $T, "$T\caches\tmp" -Force | Out-Null
# Acelasi motiv ca in `build-apk.ps1`: pe masinile astea `Selector.open()` din Java
# crapa cu TEMP-ul implicit, si sdkmanager E un program Java.
$env:TMP = "$T\caches\tmp"; $env:TEMP = "$T\caches\tmp"
$env:ANDROID_USER_HOME = "$T\caches\android"

function Ia($url, $catre, $eticheta) {
    if (Test-Path $catre) { "  $eticheta - deja descarcat"; return }
    "  $eticheta - descarc..."
    $vechi = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
    try { Invoke-WebRequest -Uri $url -OutFile $catre -UseBasicParsing }
    finally { $ProgressPreference = $vechi }
    "  $eticheta - {0:N0} MB" -f ((Get-Item $catre).Length / 1MB)
}

$dl = "$T\caches\descarcari"
New-Item -ItemType Directory -Path $dl -Force | Out-Null

# ---- JDK 21 (Temurin) ------------------------------------------------------
if (-not (Stare).Jdk) {
    $zip = "$dl\jdk21.zip"
    Ia 'https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse' $zip 'JDK 21'
    "  despachetez JDK..."
    $tmp = "$T\.jdk-tmp"; Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
    Expand-Archive $zip -DestinationPath $tmp -Force
    # Arhiva are un singur folder radacina, cu versiunea in nume; il redenumim, ca
    # `build-apk.ps1` sa gaseasca mereu `jdk-21`, indiferent de patch-level.
    $r = Get-ChildItem $tmp -Directory | Select-Object -First 1
    Move-Item $r.FullName "$T\jdk-21"
    Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
}
$env:JAVA_HOME = "$T\jdk-21"

# ---- unelte SDK ------------------------------------------------------------
if (-not (Stare).Sdkman) {
    $zip = "$dl\cmdline-tools.zip"
    Ia "https://dl.google.com/android/repository/commandlinetools-win-${CmdlineTools}_latest.zip" $zip 'unelte SDK'
    "  despachetez uneltele SDK..."
    $tmp = "$T\.cmdt-tmp"; Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
    Expand-Archive $zip -DestinationPath $tmp -Force
    # sdkmanager cere EXACT asezarea `cmdline-tools/latest/...`; arhiva vine cu
    # `cmdline-tools/` la radacina, deci se muta un nivel.
    New-Item -ItemType Directory -Path "$T\android-sdk\cmdline-tools" -Force | Out-Null
    Move-Item "$tmp\cmdline-tools" "$T\android-sdk\cmdline-tools\latest"
    Remove-Item $tmp -Recurse -Force -EA SilentlyContinue
}

$env:ANDROID_HOME = "$T\android-sdk"; $env:ANDROID_SDK_ROOT = "$T\android-sdk"
$sdkman = "$T\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat"

# ---- licente + pachete -----------------------------------------------------
# Licentele se accepta o data; fara ele `sdkmanager` refuza orice instalare.
"  accept licentele..."
$y = ("y`n" * 40)
$y | & $sdkman --licenses --sdk_root="$T\android-sdk" 2>&1 | Select-String -Pattern 'accepted|All SDK' | Select-Object -Last 1

"  instalez: $($PACHETE -join ', ')"
& $sdkman --sdk_root="$T\android-sdk" @PACHETE 2>&1 | Select-String -Pattern 'done|Warning|Error' | Select-Object -Last 5

""
"Stare:"
$s = Stare
Raport $s

if (-not $s.Chei) {
    ""
    "CHEILE DE SEMNARE LIPSESC — build-ul de release se va opri inainte de Gradle."
    "Nu se pot genera aici: o cheie noua inseamna alta semnatura, iar Android"
    "refuza sa instaleze peste aplicatia existenta (ai pierde datele locale)."
    "Copiaza de pe masina care le are, pastrand aceeasi asezare:"
    "    %USERPROFILE%\Repos\Tools\keys\keystore.properties"
    "    %USERPROFILE%\Repos\Tools\keys\<fisierul .jks la care trimite storeFile>"
    "Sunt SECRETE: nu intra in git (repo-ul nici nu le vede, sunt in afara lui)."
}
