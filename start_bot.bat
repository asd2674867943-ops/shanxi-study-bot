@echo off
cd /d "%~dp0"
start "" /b pythonw "%~dp0run_bot.py"
echo Bot started in background.
echo Check logs at: %~dp0logs\bot.log
echo To stop: run stop_bot.bat
