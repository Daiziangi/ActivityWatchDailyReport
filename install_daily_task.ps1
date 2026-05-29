param(
    [string]$TaskName = "ActivityWatch Daily Report",
    [string]$At = "23:55",
    [ValidateSet("today", "yesterday")]
    [string]$ReportDate = "today",
    [ValidateSet("auto", "on", "off")]
    [string]$Llm = "auto",
    [string]$Provider = "",
    [switch]$Silent,
    [switch]$Preview
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root "run_daily_report.ps1"
$SilentScript = Join-Path $Root "run_daily_report_silent.vbs"

if (-not (Test-Path $Script)) {
    throw "Cannot find $Script"
}
if ($Silent -and -not (Test-Path $SilentScript)) {
    throw "Cannot find $SilentScript"
}

if ($Silent) {
    $Execute = Join-Path $env:WINDIR "System32\wscript.exe"
    if (-not (Test-Path $Execute)) {
        $Execute = (Get-Command wscript -ErrorAction Stop).Source
    }
    $ReportArgs = @("`"$SilentScript`"", "`"$ReportDate`"", "`"$Llm`"")
    if ($Provider) {
        $ReportArgs += "`"$Provider`""
    }
}
else {
    $Execute = (Get-Command powershell -ErrorAction Stop).Source
    $ReportArgs = @(
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$Script`"",
        "-ReportDate", $ReportDate,
        "-Llm", $Llm,
        "-SaveJson"
    )
    if ($Provider) {
        $ReportArgs += @("-Provider", $Provider)
    }
    $ReportArgs += "-Notify"
}
$ReportArgument = $ReportArgs -join " "

if ($Preview) {
    Write-Host "Execute: $Execute"
    Write-Host "Arguments: $ReportArgument"
    Write-Host "WorkingDirectory: $Root"
    Write-Host "Trigger: Daily at $At"
    exit 0
}

$Action = New-ScheduledTaskAction `
    -Execute $Execute `
    -Argument $ReportArgument `
    -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At $At

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Description "Generate a Markdown daily report from ActivityWatch data. Silent=$($Silent.IsPresent)" `
    -Force | Out-Null

Write-Host "Installed scheduled task '$TaskName' at $At for --date $ReportDate --llm $Llm --silent $($Silent.IsPresent)."
