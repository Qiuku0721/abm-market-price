# ABM Auto-Build watcher
# Watches android/ app sources + build config and pc/ sources.
# On change: rebuilds the debug APK (android) and runs PC syntax/pytest checks.
# Logs to auto-build.log next to this script. Press Ctrl+C to stop.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logPath = Join-Path $root 'auto-build.log'

function Log([string]$msg) {
  $line = ('[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg)
  Write-Host $line
  try { Add-Content -Path $logPath -Value $line } catch { }
}

# ---------- locate JDK (prefer 17/21 under ~\.jdks) ----------
$javaHome = ''
if ($env:JAVA_HOME -and (Test-Path (Join-Path $env:JAVA_HOME 'bin\java.exe'))) {
  $javaHome = $env:JAVA_HOME
} else {
  $jdks = Get-ChildItem (Join-Path $env:USERPROFILE '.jdks') -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path (Join-Path $_.FullName 'bin\java.exe') }
  $pref = $jdks | Where-Object { $_.Name -match '21|17' } | Select-Object -First 1
  if (-not $pref) { $pref = $jdks | Select-Object -First 1 }
  if ($pref) { $javaHome = $pref.FullName }
}
if (-not $javaHome) {
  Log 'ERROR: no JDK found (set JAVA_HOME or install a JDK under ~\.jdks)'
  exit 1
}
Log "JDK: $javaHome"

# ---------- locate python ----------
function Get-PythonExe {
  $venvPy = Join-Path $root 'pc\.venv\Scripts\python.exe'
  if (Test-Path $venvPy) { return $venvPy }
  $launcher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
  if ($launcher) {
    foreach ($v in @('-3.12', '-3')) {
      $out = & py $v -c 'import sys; print(sys.executable)' 2>$null
      if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Select-Object -Last 1).Trim() }
    }
  }
  $hit = Get-Item (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python3*\python.exe') -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if ($hit) { return $hit.FullName }
  return $null
}
$pyExe = Get-PythonExe
if ($pyExe) { Log "Python: $pyExe" } else { Log 'WARN: python not found - PC checks disabled' }

# ---------- watch paths ----------
$androidWatch = @(
  (Join-Path $root 'android\app\src'),
  (Join-Path $root 'android\app\build.gradle.kts'),
  (Join-Path $root 'android\build.gradle.kts'),
  (Join-Path $root 'android\settings.gradle.kts'),
  (Join-Path $root 'android\gradle.properties'),
  (Join-Path $root 'android\gradle\wrapper')
)
$pcWatch = @((Join-Path $root 'pc'))

function Get-LatestWrite([string[]]$paths) {
  $t = [datetime]'2000-01-01'
  foreach ($p in $paths) {
    if (Test-Path $p) {
      $f = Get-ChildItem -Path $p -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\(build|\.gradle|\.venv|__pycache__)\\' } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
      if ($f -and $f.LastWriteTime -gt $t) { $t = $f.LastWriteTime }
    }
  }
  return $t
}

# ---------- build actions ----------
function Invoke-AndroidBuild {
  $env:JAVA_HOME = $javaHome
  $env:Path = "$javaHome\bin;$env:Path"
  $gradlew = Join-Path $root 'android\gradlew.bat'
  Log '=== ANDROID BUILD START ==='
  try {
    & $gradlew -p (Join-Path $root 'android') assembleDebug --console=plain 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -eq 0) {
      Log '=== ANDROID BUILD OK -> android\app\build\outputs\apk\debug\app-debug.apk ==='
    } else {
      Log '=== ANDROID BUILD FAILED (see output above / auto-build.log) ==='
    }
  } catch {
    Log "BUILD exception: $_"
  }
}

function Invoke-PcCheck {
  if (-not $pyExe) { return }
  Log '=== PC CHECK START ==='
  try {
    $venvPy = Join-Path $root 'pc\.venv\Scripts\python.exe'
    if (Test-Path $venvPy) {
      Push-Location (Join-Path $root 'pc')
      & $venvPy -m pytest -q 2>&1 | ForEach-Object { Write-Host $_ }
      Pop-Location
      Log '=== PC CHECK DONE (pytest) ==='
    } else {
      Get-ChildItem -Path (Join-Path $root 'pc') -Recurse -Filter '*.py' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '\\.venv\\' } |
        ForEach-Object { & $pyExe -m py_compile $_.FullName }
      Log '=== PC CHECK DONE (py_compile syntax only; run pc\scripts\start.bat once to enable pytest) ==='
    }
  } catch {
    Log "PC check exception: $_"
  }
}

# ---------- main loop (poll every 2s) ----------
Log 'Watching for changes (android app/src + build config + pc). Press Ctrl+C to stop.'
$lastA = Get-LatestWrite $androidWatch
$lastP = Get-LatestWrite $pcWatch
$busy = $false
while ($true) {
  Start-Sleep -Seconds 2
  if ($busy) { continue }
  $a = Get-LatestWrite $androidWatch
  $p = Get-LatestWrite $pcWatch
  if ($a -gt $lastA -or $p -gt $lastP) {
    $busy = $true
    if ($a -gt $lastA) {
      Invoke-AndroidBuild
      $lastA = Get-LatestWrite $androidWatch
    }
    if ($p -gt $lastP) {
      Invoke-PcCheck
      $lastP = Get-LatestWrite $pcWatch
    }
    $busy = $false
  }
}
