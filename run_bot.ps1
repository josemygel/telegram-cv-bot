# Arranca josembot de forma autónoma. Pensado para la Tarea Programada (al iniciar sesión)
# o a mano (clic derecho -> "Ejecutar con PowerShell"). Deja la ventana/proceso vivo.
# Solo levanta LM Studio si el backend es LOCAL; con Groq u otro hosted, lanza solo el bot.
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot
$env:PYTHONUTF8 = "1"
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# ¿Backend local? (OPENAI_BASE_URL apunta a localhost/127.0.0.1)
$useLocal = $false
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    $line = Select-String -Path $envFile -Pattern '^\s*OPENAI_BASE_URL\s*=\s*(\S+)' | Select-Object -Last 1
    if ($line -and $line.Matches[0].Groups[1].Value -match 'localhost|127\.0\.0\.1') { $useLocal = $true }
}
$lms = Join-Path $env:USERPROFILE ".lmstudio\bin\lms.exe"
if ($useLocal -and (Test-Path $lms)) {
    Write-Host "Backend local: arrancando LM Studio + modelo..."
    & $lms server start *> $null
    & $lms load "qwen/qwen3-vl-4b" -y -c 16384 *> $null
} else {
    Write-Host "Backend hosted (p.ej. Groq): no hace falta LM Studio."
}

Write-Host "Arrancando josembot (log en logs\bot.log)..."
python -u -m src.bot 2>&1 | Tee-Object -FilePath (Join-Path $logDir "bot.log")
