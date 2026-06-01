Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = "C:\cursor项目内容\第三个文件"
objShell.Run "pythonw C:\cursor项目内容\第三个文件\run_bot.py", 0, False
