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

if (-not (Test-Path $Script)) {
    throw "Cannot find $Script"
}

$PowerShell = (Get-Command powershell -ErrorAction Stop).Source
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
if ($Silent) {
    $ReportArgs = @("-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass") + $ReportArgs[4..($ReportArgs.Count - 1)]
    $ReportArgs += "-Silent"
}
else {
    $ReportArgs += "-Notify"
}
$ReportArgument = $ReportArgs -join " "

if ($Preview) {
    Write-Host "Execute: $PowerShell"
    Write-Host "Arguments: $ReportArgument"
    Write-Host "WorkingDirectory: $Root"
    Write-Host "Trigger: Daily at $At"
    exit 0
}

$Action = New-ScheduledTaskAction `
    -Execute $PowerShell `
    -Argument $ReportArgument `
    -WorkingDirectory $Root
$Trigger = New-ScheduledTaskTrigger -Daily -At $At

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Description "Generate a Markdown daily report from ActivityWatch data." `
    -Force | Out-Null

Write-Host "Installed scheduled task '$TaskName' at $At for --date $ReportDate --llm $Llm."
