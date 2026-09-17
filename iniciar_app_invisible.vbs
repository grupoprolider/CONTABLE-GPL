Set WshShell = CreateObject("WScript.Shell")
' Run the batch file completely hidden
WshShell.Run chr(34) & "iniciar_app.bat" & Chr(34), 0
Set WshShell = Nothing
