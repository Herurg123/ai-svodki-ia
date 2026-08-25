Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
shell.Run "cmd.exe /d /c """ & base & "\run-worker.cmd""", 0, False
