[CmdletBinding()]
param(
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$composeFile = Join-Path $repoRoot "infra\compose\docker-compose.local.yml"
$envFile = Join-Path $PSScriptRoot ".env.local"

function New-UrlSafeSecret {
    param([int]$ByteCount = 32)

    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }

    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Test-LocalPortFree {
    param([int]$Port)

    $listener = New-Object System.Net.Sockets.TcpListener -ArgumentList ([System.Net.IPAddress]::Loopback, $Port)
    try {
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        $listener.Stop()
    }
}

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Name
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $prefix = "$Name="
    $line = Get-Content -LiteralPath $Path | Where-Object { $_.StartsWith($prefix) } | Select-Object -First 1
    if ($null -eq $line) {
        return $null
    }
    return $line.Substring($prefix.Length)
}

function New-LocalEnvFile {
    param(
        [string]$Path,
        [int]$Port
    )

    $postgresPassword = New-UrlSafeSecret
    $redisPassword = New-UrlSafeSecret
    $jwtSecret = New-UrlSafeSecret -ByteCount 48
    $credentialKek = New-UrlSafeSecret
    $s3KeyId = New-UrlSafeSecret -ByteCount 18
    $s3ApplicationKey = New-UrlSafeSecret

    $lines = @(
        "ENV_FILE=../local/.env.local",
        "LOCAL_HTTP_PORT=$Port",
        "",
        "POSTGRES_USER=nfse",
        "POSTGRES_PASSWORD=$postgresPassword",
        "POSTGRES_DB=nfse",
        "REDIS_PASSWORD=$redisPassword",
        "",
        "API_ENVIRONMENT=development",
        "API_LOG_LEVEL=INFO",
        "LOG_LEVEL=INFO",
        "API_DATABASE_URL=postgresql+psycopg://nfse:$postgresPassword@postgres:5432/nfse",
        "API_MIGRATION_DATABASE_URL=postgresql+psycopg://nfse:$postgresPassword@postgres:5432/nfse",
        "WORKER_DATABASE_URL=postgresql+psycopg://nfse:$postgresPassword@postgres:5432/nfse",
        "API_REDIS_URL=redis://:$redisPassword@redis:6379/0",
        "API_QUEUE_NAME=nfse-executions",
        "API_JWT_SECRET=$jwtSecret",
        "API_CREDENTIAL_KEK_B64=$credentialKek",
        "API_ALLOW_LOCAL_DEMO_LOGIN=true",
        "API_SEED_ADMIN_PASSWORD=demo12345",
        "",
        "NEXT_PUBLIC_API_BASE_URL=/backend",
        "API_BASE_URL=http://api:8000",
        "",
        "S3_ENDPOINT=http://s3.localhost:$Port",
        "S3_REGION=us-east-1",
        "S3_BUCKET=nfse",
        "S3_KEY_ID=$s3KeyId",
        "S3_APPLICATION_KEY=$s3ApplicationKey",
        "S3_FORCE_PATH_STYLE=true",
        "S3_EXECUTIONS_PREFIX=tenants/",
        "S3_EXPORTS_PREFIX=tenants-exports/",
        "S3_CREDENTIALS_PREFIX=tenants-credentials/",
        "",
        "NFSE_AMBIENTE=HOMOLOGACAO",
        "NFSE_ADN_CONNECT_TIMEOUT_SECONDS=10",
        "NFSE_ADN_READ_TIMEOUT_SECONDS=60",
        "NFSE_ADN_RETRY_ATTEMPTS=5",
        "NFSE_ADN_RETRY_BACKOFF_MULTIPLIER=2",
        "NFSE_ADN_RETRY_BACKOFF_MIN_SECONDS=4",
        "NFSE_ADN_RETRY_BACKOFF_MAX_SECONDS=60",
        "API_JOB_TIMEOUT_SECONDS=3600",
        ""
    )

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, ($lines -join [Environment]::NewLine), $utf8NoBom)
}

function Invoke-Compose {
    param([string[]]$Arguments)

    & docker @script:composePrefix @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose falhou: $($Arguments -join ' ')"
    }
}

Write-Host "[nfse-local] Validando Docker Desktop..."
& docker version --format "{{.Server.Version}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop nao esta disponivel. Abra-o e execute o script novamente."
}
& docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose nao esta disponivel no Docker Desktop."
}

if (-not (Test-Path -LiteralPath $envFile)) {
    $port = $null
    foreach ($candidate in 3000..3099) {
        if (Test-LocalPortFree -Port $candidate) {
            $port = $candidate
            break
        }
    }
    if ($null -eq $port) {
        throw "Nenhuma porta livre encontrada entre 3000 e 3099."
    }

    New-LocalEnvFile -Path $envFile -Port $port
    Write-Host "[nfse-local] Configuracao local criada com segredos aleatorios."
}
else {
    $portValue = Get-EnvValue -Path $envFile -Name "LOCAL_HTTP_PORT"
    if ([string]::IsNullOrWhiteSpace($portValue)) {
        throw "LOCAL_HTTP_PORT ausente em $envFile."
    }
    $port = [int]$portValue
    Write-Host "[nfse-local] Reutilizando configuracao e volumes existentes."
}

# Mantem configuracoes geradas por versoes anteriores compativeis com a
# identidade de demonstracao, sem reescrever ou revelar os segredos existentes.
if ([string]::IsNullOrWhiteSpace((Get-EnvValue -Path $envFile -Name "API_ALLOW_LOCAL_DEMO_LOGIN"))) {
    [System.IO.File]::AppendAllText(
        $envFile,
        "API_ALLOW_LOCAL_DEMO_LOGIN=true$([Environment]::NewLine)",
        (New-Object System.Text.UTF8Encoding($false))
    )
}

$script:composePrefix = @(
    "compose",
    "--project-name", "nfse-local",
    "--env-file", $envFile,
    "-f", $composeFile
)

Write-Host "[nfse-local] Validando a configuracao..."
Invoke-Compose -Arguments @("config", "--quiet")

Write-Host "[nfse-local] Construindo as imagens da aplicacao..."
Invoke-Compose -Arguments @("build")

Write-Host "[nfse-local] Subindo banco, fila, storage e aplicacao..."
Invoke-Compose -Arguments @("up", "-d", "--remove-orphans")

$healthServices = @("postgres", "redis", "minio", "api", "worker", "scheduler", "web-app", "caddy")
$deadline = (Get-Date).AddMinutes(5)
do {
    $pending = @()
    foreach ($service in $healthServices) {
        $containerId = (& docker @composePrefix ps -q $service | Select-Object -First 1)
        if ([string]::IsNullOrWhiteSpace($containerId)) {
            $pending += "${service}:ausente"
            continue
        }
        $health = (& docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $containerId).Trim()
        if ($health -notin @("healthy", "running")) {
            $pending += "${service}:$health"
        }
    }

    if ($pending.Count -eq 0) {
        break
    }
    Write-Host "[nfse-local] Aguardando: $($pending -join ', ')"
    Start-Sleep -Seconds 3
} while ((Get-Date) -lt $deadline)

if ($pending.Count -ne 0) {
    & docker @composePrefix ps -a
    & docker @composePrefix logs --tail 80
    throw "A stack nao ficou saudavel no prazo: $($pending -join ', ')."
}

foreach ($service in @("minio-init", "migrate", "seed")) {
    $containerId = (& docker @composePrefix ps -a -q $service | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace($containerId)) {
        throw "Servico de inicializacao ausente: $service."
    }
    $exitCode = (& docker inspect --format "{{.State.ExitCode}}" $containerId).Trim()
    if ($exitCode -ne "0") {
        throw "Servico de inicializacao falhou: $service (exit $exitCode)."
    }
}

$baseUrl = "http://localhost:$port"
$ready = Invoke-RestMethod -Uri "$baseUrl/backend/ready" -TimeoutSec 15
if ($ready.status -ne "ok") {
    throw "API respondeu, mas nao esta pronta."
}
$webHealth = Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 15
if ($webHealth.status -ne "ok") {
    throw "Painel respondeu, mas o healthcheck nao esta pronto."
}

Write-Host ""
Write-Host "[nfse-local] Ambiente pronto." -ForegroundColor Green
Write-Host "Painel:  $baseUrl"
Write-Host "Swagger: $baseUrl/backend/docs"
Write-Host "Login:   admin@demo.local"
Write-Host "Senha:   demo12345"
Write-Host ""

if (-not $NoBrowser) {
    Start-Process $baseUrl
}
