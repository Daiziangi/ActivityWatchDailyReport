param(
    [string]$TaskName = "ActivityWatch Daily Report",
    [string]$At = "23:55",
    [ValidateSet("today", "yesterday")]
    [string]$ReportDate = "today",
    [ValidateSet("auto", "on", "off")]
    [string]$Llm = "auto",
    [string]$Provider = "",
    [switch]$Preview
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root "activity_daily_report.py"

if (-not (Test-Path $Script)) {
    throw "Cannot find $Script"
}

$Python = (Get-Command python -ErrorAction Stop).Source
$ReportArgs = @("`"$Script`"", "--date", $ReportDate, "--llm", $Llm)
if ($Provider) {
    $ReportArgs += @("--provider", $Provider)
}
$ReportArgument = $ReportArgs -join " "

if ($Preview) {
    Write-Host "Execute: $Python"
    Write-Host "Arguments: $ReportArgument"
    Write-Host "WorkingDirectory: $Root"
    Write-Host "Trigger: Daily at $At"
    exit 0
}

$Action = New-ScheduledTaskAction `
    -Execute $Python `
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
