<#
  LoNo launcher for Windows (also works with PowerShell 7 on macOS/Linux).
    .\start.cmd            run locally with Python on http://localhost:8001 (no database needed)
    .\start.cmd -Docker    run the full stack with Docker on http://localhost:8080
    .\start.cmd -Port 9000 use another port
#>
param([switch]$Docker, [int]$Port = 8001, [switch]$NoBrowser, [switch]$Broadcast)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$OnWindows = ($env:OS -eq "Windows_NT")

function Say($msg) { Write-Host "[lono] $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "[lono] $msg" -ForegroundColor Red; exit 1 }
function NewSecret { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object { [char]$_ }) }
function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function PortBusy($p) {
  $c = New-Object System.Net.Sockets.TcpClient
  try { $c.Connect("127.0.0.1", $p); $true } catch { $false } finally { $c.Close() }
}

# ---------------- Docker mode ----------------
if ($Docker) {
  if (-not (Have "docker")) { Fail "Docker isn't installed. Install Docker Desktop, start it, then run this again." }
  docker info *> $null
  if ($LASTEXITCODE -ne 0) { Fail "Docker is installed but not running. Open Docker Desktop, wait for 'Engine running', then try again." }
  $envDocker = Join-Path $Backend ".env.docker"
  if (-not (Test-Path $envDocker)) {
    (Get-Content (Join-Path $Backend ".env.docker.example")) -replace "^JWT_SECRET=.*", "JWT_SECRET=$(NewSecret)" | Set-Content $envDocker
    Say "Created backend\.env.docker with a fresh JWT secret."
  }
  Say "Building and starting containers. The first run takes 5-10 minutes."
  Say "When the logs settle, open http://localhost:8080  (Ctrl+C to stop)"
  Push-Location $Root; try { docker compose up --build } finally { Pop-Location }
  exit $LASTEXITCODE
}

# ---------------- Local (Python) mode ----------------
# 1. Find Python 3.10+ (skips the Microsoft Store stub that only prints nothing)
$py = $null
# Prefer versions LoNo's packages are tested on; very new Pythons can lack prebuilt packages.
foreach ($cand in @(@("py", "-3.12"), @("py", "-3.13"), @("py", "-3.11"), @("py", "-3"), @("python"), @("python3"))) {
  if (-not (Have $cand[0])) { continue }
  $args_ = @(); if ($cand.Count -gt 1) { $args_ = $cand[1..($cand.Count - 1)] }
  # try/catch: Windows PowerShell 5.1 can turn a probe's error output into a fatal error
  $ver = $null
  try { $ver = & $cand[0] @args_ -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null } catch { $ver = $null }
  if ($ver -match "^3\.(\d+)$" -and [int]$Matches[1] -ge 10) { $py = $cand; break }
}
if (-not $py) { Fail "Python 3.10 or newer wasn't found. Install it from python.org and tick 'Add python.exe to PATH', then open a new window and run this again." }
Say "Using Python $ver"
if ([int]($ver.Split(".")[1]) -gt 13) {
  Write-Host "[lono] Python $ver is newer than LoNo is tested with (3.11-3.13). If package installs fail, install Python 3.12 from python.org and run this again." -ForegroundColor Yellow
}

# 2. Virtual environment + dependencies (reinstalled only when requirements.txt changes)
$venv = Join-Path $Backend ".venv"
$vpy = if ($OnWindows) { Join-Path $venv "Scripts\python.exe" } else { Join-Path $venv "bin/python" }
if (-not (Test-Path $vpy)) {
  Say "Creating virtual environment..."
  $args_ = @(); if ($py.Count -gt 1) { $args_ = $py[1..($py.Count - 1)] }
  & $py[0] @args_ -m venv $venv
  if ($LASTEXITCODE -ne 0) { Fail "Couldn't create the virtual environment." }
}
$req = Join-Path $Backend "requirements.txt"
$stamp = Join-Path $venv ".requirements.sha"
$hash = (Get-FileHash $req -Algorithm SHA256).Hash
if (-not (Test-Path $stamp) -or (Get-Content $stamp) -ne $hash) {
  Say "Installing Python packages (first run takes a minute or two)..."
  & $vpy -m pip install --disable-pip-version-check -q -r $req
  if ($LASTEXITCODE -ne 0) { Fail "Package install failed. Check your internet connection and try again." }
  Set-Content $stamp $hash
}

# 3. Settings file for local use (in-memory database, random secret).
#    Fills in any essential setting that's missing, without touching ones you've set.
$envFile = Join-Path $Backend ".env"
$defaults = [ordered]@{
  "MONGO_URL" = "mongomock://"; "DB_NAME" = "lono"; "JWT_SECRET" = (NewSecret); "CORS_ORIGINS" = "*"
  "PUBLIC_ORIGIN" = "http://localhost:$Port"; "STORAGE_BACKEND" = "local"
  "ADMIN_EMAILS" = "msf@ciu.edu.lr"; "SUPPORT_EMAIL" = "lono@ciu.edu.lr"
}
$existing = @()
if (Test-Path $envFile) { $existing = @(Get-Content $envFile) }
$missing = @($defaults.Keys | Where-Object { $k = $_; -not ($existing | Where-Object { $_ -match "^\s*$k\s*=" }) })
if ($missing.Count -gt 0) {
  $lines = @()
  if ($existing.Count -eq 0) {
    $lines += "# Local settings. See .env.example for every option."
    $lines += "# mongomock:// = in-memory database that resets on restart. Use mongodb://localhost:27017 to keep data."
  }
  foreach ($k in $missing) { $lines += "$k=$($defaults[$k])" }
  Add-Content -Path $envFile -Value $lines
  if ($existing.Count -eq 0) { Say "Created backend\.env (in-memory database)." }
  else { Say "Added missing settings to backend\.env: $($missing -join ', ')" }
}

# 4. Website build. Rebuilds when the website's code is newer than the last build
#    (for example after git pull). Needs Node.js 20+ for that step.
$index = Join-Path $Frontend "build\index.html"
$built = if (Test-Path $index) { (Get-Item $index).LastWriteTimeUtc } else { [datetime]::MinValue }
$sources = @(Get-ChildItem -Recurse -File (Join-Path $Frontend "src")) + @(Get-Item (Join-Path $Frontend "package.json"))
$newest = ($sources | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum
$stale = $newest -gt $built
if ($stale) {
  if (-not (Have "node")) {
    if (Test-Path $index) {
      Write-Host "[lono] The website code changed but Node.js isn't installed, so it can't be rebuilt." -ForegroundColor Yellow
      Write-Host "[lono] You'll see the OLD website until you install Node.js 20 LTS from nodejs.org and run this again." -ForegroundColor Yellow
    } else {
      Fail "The website hasn't been built yet and Node.js isn't installed. Install Node.js 20 LTS from nodejs.org, then run this again."
    }
  } else {
    Say "Building the website (2-5 minutes; only when its code has changed)..."
    Push-Location $Frontend
    try {
      & npx --yes yarn@1.22.22 install --frozen-lockfile --network-timeout 600000
      if ($LASTEXITCODE -ne 0) { Fail "Installing website packages failed." }
      $env:CI = "false"
      & npx --yes yarn@1.22.22 build
      if ($LASTEXITCODE -ne 0) { Fail "The website build failed." }
    } finally { Pop-Location }
  }
}

# 4b. Live broadcasting (optional: .\start.cmd -Broadcast)
#     Downloads the MediaMTX media server (checksum-verified) and makes sure ffmpeg is available.
$mtxProc = $null
if ($Broadcast) {
  $MtxVersion = "v1.9.3"
  # SHA-256 of each release file, pinned here (this MediaMTX release publishes no checksum file).
  $MtxSha = @{
    "mediamtx_v1.9.3_windows_amd64.zip"    = "af2ce0dce3201e10c39dae4e6d8e52c983d6940b1fa0fdd7f3d16c87ac764626"
    "mediamtx_v1.9.3_linux_amd64.tar.gz"   = "0b885dbfa4ef9c14cd00191c57d90d804255ff50403a28b85ceee7988c535b60"
    "mediamtx_v1.9.3_linux_arm64v8.tar.gz" = "f2f02109dd3d88773d7de5ae84385d41041bc9d60d0459eb6c61462cb2da0d1e"
    "mediamtx_v1.9.3_darwin_amd64.tar.gz"  = "935ed174245004b425a93f6b7c1eac52310d833d4ebbca041d0f19195291eaf6"
    "mediamtx_v1.9.3_darwin_arm64.tar.gz"  = "562b7f8fe24d9005510efe1d15589119a2bf4e77e6a4d3fe35b1d3f55c75263c"
  }
  $Tools = Join-Path $Root "tools"
  $mtxDir = Join-Path $Tools "mediamtx"
  $arch = if ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture -match "Arm64") { "arm64" } else { "amd64" }
  if ($OnWindows) { $asset = "mediamtx_${MtxVersion}_windows_amd64.zip"; $mtxExe = Join-Path $mtxDir "mediamtx.exe" }
  elseif ($IsMacOS) { $asset = "mediamtx_${MtxVersion}_darwin_$arch.tar.gz"; $mtxExe = Join-Path $mtxDir "mediamtx" }
  else { $larch = if ($arch -eq "arm64") { "arm64v8" } else { "amd64" }; $asset = "mediamtx_${MtxVersion}_linux_$larch.tar.gz"; $mtxExe = Join-Path $mtxDir "mediamtx" }
  if (-not (Test-Path $mtxExe)) {
    Say "Downloading the MediaMTX media server $MtxVersion..."
    New-Item -ItemType Directory -Force -Path $mtxDir | Out-Null
    $base = "https://github.com/bluenviron/mediamtx/releases/download/$MtxVersion"
    $file = Join-Path $mtxDir $asset
    $ProgressPreference = "SilentlyContinue"
    try { Invoke-WebRequest "$base/$asset" -OutFile $file -UseBasicParsing }
    catch { Fail "Couldn't download MediaMTX. Check your internet connection." }
    $expected = $MtxSha[$asset]
    $actual = (Get-FileHash $file -Algorithm SHA256).Hash.ToLower()
    if (-not $expected -or $expected -ne $actual) { Remove-Item $file -Force; Fail "The MediaMTX download didn't match LoNo's pinned checksum, so it was deleted. Try again, or report it." }
    if ($asset.EndsWith(".zip")) { Expand-Archive $file -DestinationPath $mtxDir -Force } else { tar -xzf $file -C $mtxDir }
    Remove-Item $file -Force
  }

  # ffmpeg: use one on PATH; on Windows install it with winget if needed.
  $ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
  if (-not $ffmpeg -and $OnWindows) {
    $found = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $found -and (Have "winget")) {
      Say "Installing ffmpeg with winget (Gyan.FFmpeg)..."
      winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements | Out-Host
      $found = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    }
    if ($found) { $ffmpeg = $found.FullName }
  }
  if (-not $ffmpeg) { Fail "ffmpeg is needed for broadcasting. Install it (Windows: winget install Gyan.FFmpeg; macOS: brew install ffmpeg; Linux: sudo apt install ffmpeg) and run this again." }
  Say "Using ffmpeg: $ffmpeg"

  # This PC's address on the local network, so OBS or other computers here can send to it.
  $lan = "127.0.0.1"
  try {
    if ($OnWindows) {
      $lan = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop | Where-Object { $_.IPAddress -notmatch "^(127\.|169\.254\.)" -and $_.PrefixOrigin -ne "WellKnown" } |
              Sort-Object -Property InterfaceMetric | Select-Object -First 1).IPAddress
    } else {
      $lan = (hostname -I 2>$null).Split(" ")[0]
    }
  } catch { }
  if (-not $lan) { $lan = "127.0.0.1" }

  $env:MEDIA_ENABLED = "true"
  $env:FFMPEG_BIN = $ffmpeg
  $env:INGEST_RTMP_URL = "rtmp://${lan}:1935/live"
  $env:INGEST_SRT_URL = "srt://${lan}:8890"
  $env:MTX_AUTHHTTPADDRESS = "http://127.0.0.1:$Port/api/broadcast/mtx/auth"
  $env:MTX_WEBRTCADDITIONALHOSTS = $lan
  foreach ($p in 1935, 8889, 8888, 9997) { if (PortBusy $p) { Fail "Port $p is in use; broadcasting needs it. Close the program using it and try again." } }
  Say "Starting the media server (allow it through the firewall on private networks if Windows asks)..."
  $mtxProc = Start-Process -FilePath $mtxExe -ArgumentList @((Join-Path $Root "media/mediamtx.yml")) -WorkingDirectory $mtxDir -NoNewWindow -PassThru
  Start-Sleep -Seconds 1
  if ($mtxProc.HasExited) { Fail "The media server stopped during startup. Scroll up for its message." }
  Say "Broadcasting on. Encoder server: rtmp://${lan}:1935/live (stream key in Creator Studio > Live Studio)"
}

# 5. Run
if (PortBusy $Port) { Fail "Port $Port is already in use. Close the other program, or run: .\start.cmd -Port 8002" }
$env:FRONTEND_DIR = (Join-Path $Frontend "build")
$url = "http://localhost:$Port"
Say "Starting LoNo at $url  (keep this window open; Ctrl+C to stop)"
$proc = Start-Process -FilePath $vpy -ArgumentList @("-m", "uvicorn", "server:app", "--port", "$Port") `
  -WorkingDirectory $Backend -NoNewWindow -PassThru
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Milliseconds 500
  if ($proc.HasExited) { Fail "The server stopped during startup. Scroll up for the error." }
  if (PortBusy $Port) { break }
}
Say "Ready: $url"
if (-not $NoBrowser) { try { Start-Process $url } catch { } }
try { $proc.WaitForExit() } finally {
  if (-not $proc.HasExited) { $proc.Kill() }
  if ($mtxProc -and -not $mtxProc.HasExited) { $mtxProc.Kill() }
}
