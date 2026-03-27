Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\Xhoni\Desktop\Coding\master-mute"
WshShell.Run "pythonw main.py", 0, False
