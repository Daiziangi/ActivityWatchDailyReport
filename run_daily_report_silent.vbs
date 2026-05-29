Option Explicit

Dim fso, shell, scriptDir, ps1, reportDate, llm, provider, cmd

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = fso.BuildPath(scriptDir, "run_daily_report.ps1")

reportDate = "today"
llm = "auto"
provider = ""

If WScript.Arguments.Count >= 1 Then reportDate = WScript.Arguments(0)
If WScript.Arguments.Count >= 2 Then llm = WScript.Arguments(1)
If WScript.Arguments.Count >= 3 Then provider = WScript.Arguments(2)

cmd = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File " & Q(ps1) & _
      " -ReportDate " & Q(reportDate) & _
      " -Llm " & Q(llm) & _
      " -SaveJson -Silent"

If Len(provider) > 0 Then
    cmd = cmd & " -Provider " & Q(provider)
End If

shell.CurrentDirectory = scriptDir
shell.Run cmd, 0, False

Function Q(value)
    Q = Chr(34) & Replace(CStr(value), Chr(34), Chr(34) & Chr(34)) & Chr(34)
End Function
