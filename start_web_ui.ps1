$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python -ErrorAction Stop).Source
$Port = 8765

$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
foreach ($conn in $existing) {
    if ($conn.OwningProcess) {
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $($conn.OwningProcess)" -ErrorAction SilentlyContinue
        if ($processInfo.CommandLine -like "*web_ui.py*") {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

Start-Process `
    -FilePath $Python `
    -ArgumentList "`"$Root\web_ui.py`" --host 127.0.0.1 --port $Port" `
    -WorkingDirectory $Root `
    -WindowStyle Hidden

Start-Sleep -Seconds 1
Start-Process "http://127.0.0.1:$Port"
