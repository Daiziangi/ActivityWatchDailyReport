param(
    [ValidateSet("today", "yesterday")]
    [string]$ReportDate = "today",
    [ValidateSet("auto", "on", "off")]
    [string]$Llm = "auto",
    [string]$Provider = "",
    [string]$ConfigPath = "",
    [switch]$SaveJson,
    [switch]$Silent,
    [switch]$Notify
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root "activity_daily_report.py"
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogDir "daily-report-$Stamp.log"
$LatestLogPath = Join-Path $LogDir "latest.log"

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message"
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    if ($Notify -and -not $Silent) {
        Write-Host $line
    }
}

try {
    Write-Log "ActivityWatch Daily Reporter task started."
    Write-Log "Root: $Root"
    Write-Log "ReportDate: $ReportDate"
    Write-Log "LLM: $Llm"
    Write-Log "Provider: $Provider"

    if (-not (Test-Path $Script)) {
        throw "Cannot find report script: $Script"
    }

    $Python = (Get-Command python -ErrorAction Stop).Source
    Write-Log "Python: $Python"

    $Args = @($Script, "--date", $ReportDate, "--llm", $Llm)
    if ($Provider) {
        $Args += @("--provider", $Provider)
    }
    if ($ConfigPath) {
        $Args += @("--config", $ConfigPath)
    }
    if ($SaveJson) {
        $Args += "--save-json"
    }

    Write-Log "Command: $Python $($Args -join ' ')"

    Push-Location $Root
    try {
        $Output = & $Python @Args 2>&1
        $ExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if ($Output) {
        $Output | ForEach-Object { Write-Log "OUT: $_" }
    }
    Write-Log "ExitCode: $ExitCode"
    if ($ExitCode -ne 0) {
        throw "Report command failed with exit code $ExitCode."
    }

    Write-Log "ActivityWatch Daily Reporter task finished."
    Copy-Item -LiteralPath $LogPath -Destination $LatestLogPath -Force
    if ($Notify -and -not $Silent) {
        Write-Host "Daily report finished. This window will close in 8 seconds."
        Start-Sleep -Seconds 8
    }
    exit 0
}
catch {
    Write-Log "ERROR: $($_.Exception.Message)"
    Copy-Item -LiteralPath $LogPath -Destination $LatestLogPath -Force
    if ($Notify -and -not $Silent) {
        Write-Host "Daily report failed. Check logs/latest.log. This window will close in 20 seconds."
        Start-Sleep -Seconds 20
    }
    exit 1
}
