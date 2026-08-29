param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$DefaultDatabasePort = if ($env:POSTGRES_HOST_PORT) { $env:POSTGRES_HOST_PORT } else { "5433" }
$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8001" }
$FrontendUrl = "http://127.0.0.1:3000"
$BackendUrl = "http://127.0.0.1:$BackendPort"
$env:UV_CACHE_DIR = Join-Path $RootDir ".uv-cache"

function Ensure-Command {
    param(
        [string]$Name,
        [string]$InstallHint
    )
    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        return
    }
    throw "Missing command: $Name. $InstallHint"
}

function Assert-LastCommandSucceeded {
    param(
        [string]$Action
    )
    if ($LASTEXITCODE -ne 0) {
        throw "$Action failed."
    }
}

function Test-DockerContainer {
    param(
        [string]$Name
    )
    docker inspect $Name *> $null
    return $LASTEXITCODE -eq 0
}

function Start-Database {
    Write-Host "Starting Docker database..."
    if (Test-DockerContainer "offermaster-postgres") {
        docker start offermaster-postgres | Out-Null
        Assert-LastCommandSucceeded "Starting existing Docker database"
        return $DefaultDatabasePort
    }

    Push-Location $RootDir
    try {
        docker compose up -d postgres
        Assert-LastCommandSucceeded "Starting Docker database"
    } finally {
        Pop-Location
    }
    return $DefaultDatabasePort
}

function Ensure-CopiedFile {
    param(
        [string]$Source,
        [string]$Target
    )
    if (Test-Path $Target) {
        return $false
    }
    Copy-Item -LiteralPath $Source -Destination $Target
    return $true
}

function Set-EnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )
    $lines = @()
    if (Test-Path $Path) {
        $lines = @(Get-Content -LiteralPath $Path -Encoding UTF8)
    }
    $pattern = "^$([regex]::Escape($Key))="
    $replacement = "$Key=$Value"
    $found = $false
    $nextLines = foreach ($line in $lines) {
        if ($line -match $pattern) {
            $found = $true
            $replacement
        } else {
            $line
        }
    }
    if (-not $found) {
        $nextLines += $replacement
    }
    Set-Content -LiteralPath $Path -Encoding UTF8 -Value $nextLines
}

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Key
    )
    if (-not (Test-Path $Path)) {
        return ""
    }
    $pattern = "^$([regex]::Escape($Key))=(.*)$"
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match $pattern) {
            return $Matches[1]
        }
    }
    return ""
}

Write-Host "Checking local tools..."
Ensure-Command "docker" "Install Docker Desktop first."
Ensure-Command "uv" "Install uv first."
Ensure-Command "node" "Install Node.js 20+ first."
Ensure-Command "npm" "Install npm first."

$DatabaseHostPort = Start-Database
$DockerDatabaseUrl = "postgresql://chat_resume:chat_resume_password@localhost:$DatabaseHostPort/chat_resume"

$BackendEnv = Join-Path $BackendDir ".env"
$BackendEnvExample = Join-Path $BackendDir ".env.example"
Ensure-CopiedFile $BackendEnvExample $BackendEnv | Out-Null
Set-EnvValue $BackendEnv "DATABASE_URL" $DockerDatabaseUrl
if ((Get-EnvValue $BackendEnv "SECRET_KEY") -eq "your-secret-key-here") {
    Set-EnvValue $BackendEnv "SECRET_KEY" "local-dev-secret"
}
Set-EnvValue $BackendEnv "FRONTEND_URL" $FrontendUrl
Set-EnvValue $BackendEnv "BACKEND_CORS_ORIGINS" "$FrontendUrl,http://localhost:3000"
Set-EnvValue $BackendEnv "GOOGLE_OAUTH_REDIRECT_URI" "$BackendUrl/api/auth/google/callback"

$FrontendEnv = Join-Path $FrontendDir ".env.local"
$FrontendEnvExample = Join-Path $FrontendDir ".env.example"
Ensure-CopiedFile $FrontendEnvExample $FrontendEnv | Out-Null
Set-EnvValue $FrontendEnv "NEXT_PUBLIC_API_URL" $BackendUrl
Set-EnvValue $FrontendEnv "NEXT_PUBLIC_APP_ENV" "development"

if (-not $SkipInstall) {
    Write-Host "Installing backend dependencies..."
    Push-Location $BackendDir
    uv sync --group dev
    Assert-LastCommandSucceeded "Installing backend dependencies"
    Pop-Location

    Write-Host "Installing frontend dependencies..."
    Push-Location $FrontendDir
    npm install
    Assert-LastCommandSucceeded "Installing frontend dependencies"
    Pop-Location
}

Write-Host "Migrating database..."
Push-Location $BackendDir
uv run alembic upgrade head
Assert-LastCommandSucceeded "Migrating database"
Pop-Location

Write-Host "Starting backend and frontend dev servers..."
$BackendLogDir = Join-Path $BackendDir "logs"
New-Item -ItemType Directory -Force -Path $BackendLogDir | Out-Null
$backendOutLog = Join-Path $BackendLogDir "dev-server.out.log"
$frontendOutLog = Join-Path $RootDir "frontend.dev.out.log"

$backendCommand = "Set-Location -LiteralPath '$BackendDir'; `$env:UV_CACHE_DIR='$env:UV_CACHE_DIR'; uv run uvicorn app.main:app --reload --host 127.0.0.1 --port $BackendPort *> '$backendOutLog'"
$frontendCommand = "Set-Location -LiteralPath '$FrontendDir'; npm run dev *> '$frontendOutLog'"
Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand) -WorkingDirectory $BackendDir
Start-Process -FilePath "powershell.exe" -WindowStyle Hidden -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand) -WorkingDirectory $FrontendDir

Write-Host ""
Write-Host "Done."
Write-Host "Frontend: $FrontendUrl"
Write-Host "Backend:  $BackendUrl"
Write-Host "Health:   $BackendUrl/health"
Write-Host "Backend logs:  $backendOutLog"
Write-Host "Frontend logs: $frontendOutLog"
