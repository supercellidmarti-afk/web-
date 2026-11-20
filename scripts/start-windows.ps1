$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runtime = Join-Path $root '.runtime'
$pythonDir = Join-Path $runtime 'python'
$ffmpegDir = Join-Path $runtime 'ffmpeg'
$pythonExe = Join-Path $pythonDir 'python.exe'
$logDir = Join-Path $root 'data'
New-Item -ItemType Directory -Force -Path $runtime, $logDir | Out-Null

function Download-File([string]$Url, [string]$Destination) {
  Write-Host "Descargando $([IO.Path]::GetFileName($Destination))..."
  Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
}

try {
  if (-not [Environment]::Is64BitOperatingSystem) { throw 'Se requiere Windows de 64 bits.' }
  $healthUrl = 'http://127.0.0.1:8000/api/health'
  try {
    $existing = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($existing.ok) { Start-Process 'http://127.0.0.1:8000'; exit 0 }
  } catch { }

  if (-not (Test-Path $pythonExe)) {
    New-Item -ItemType Directory -Force -Path $pythonDir | Out-Null
    $pythonZip = Join-Path $runtime 'python-3.12.10-embed-amd64.zip'
    Download-File 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' $pythonZip
    Expand-Archive -LiteralPath $pythonZip -DestinationPath $pythonDir -Force
    Remove-Item $pythonZip -Force
    $pth = Join-Path $pythonDir 'python312._pth'
    $pthText = Get-Content -LiteralPath $pth -Raw
    if ($pthText -notmatch '(?m)^Lib\\site-packages\s*$') { $pthText += "`r`nLib\site-packages`r`n" }
    $pthText = $pthText -replace '(?m)^#import site\s*$', 'import site'
    Set-Content -LiteralPath $pth -Value $pthText -Encoding Ascii
    $getPip = Join-Path $runtime 'get-pip.py'
    Download-File 'https://bootstrap.pypa.io/get-pip.py' $getPip
    Write-Host 'Preparando el entorno Python portátil...'
    & $pythonExe $getPip --disable-pip-version-check --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar Python/pip.' }
    Remove-Item $getPip -Force
  }

  if (-not (Get-ChildItem -Path $ffmpegDir -Filter ffmpeg.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1)) {
    New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null
    $ffmpegZip = Join-Path $runtime 'ffmpeg-essentials.zip'
    Download-File 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' $ffmpegZip
    Expand-Archive -LiteralPath $ffmpegZip -DestinationPath $ffmpegDir -Force
    Remove-Item $ffmpegZip -Force
  }
  $ffmpegExe = Get-ChildItem -Path $ffmpegDir -Filter ffmpeg.exe -Recurse | Select-Object -First 1
  if (-not $ffmpegExe) { throw 'No se encontró ffmpeg.exe en la descarga de FFmpeg.' }
  $ffmpegBin = $ffmpegExe.Directory.FullName
  if (-not (Test-Path (Join-Path $ffmpegBin 'ffprobe.exe'))) { throw 'La descarga no incluye ffprobe.exe.' }
  $env:PATH = "$ffmpegBin;$pythonDir;$env:PATH"

  $requirements = Join-Path $root 'requirements.txt'
  Write-Host 'Comprobando dependencias de Frameforge (solo en el primer inicio)...'
  & $pythonExe -m pip install --disable-pip-version-check --no-warn-script-location -r $requirements
  if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias Python. Comprueba tu conexión e inténtalo otra vez.' }

  $stdout = Join-Path $logDir 'server.log'
  $stderr = Join-Path $logDir 'server-error.log'
  Write-Host 'Iniciando servidor local...'
  $server = Start-Process -FilePath $pythonExe -ArgumentList 'run.py' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  $ready = $false
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    try {
      $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
      if ($health.ok) { $ready = $true; break }
    } catch { }
    if ($server.HasExited) { break }
  }
  if (-not $ready) {
    $details = ''
    if (Test-Path $stderr) { $details = Get-Content $stderr -Tail 12 | Out-String }
    throw "El servidor no pudo iniciar. Consulta data\server-error.log. $details"
  }
  Start-Process 'http://127.0.0.1:8000'
  Write-Host 'Frameforge está abierto en http://127.0.0.1:8000'
  Write-Host 'Puedes cerrar esta ventana; el servidor seguirá funcionando.'
} catch {
  Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
