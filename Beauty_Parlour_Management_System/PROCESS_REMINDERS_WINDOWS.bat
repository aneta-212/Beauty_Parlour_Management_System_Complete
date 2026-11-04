@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" manage.py send_reminders
if errorlevel 1 goto end
".venv\Scripts\python.exe" manage.py send_notifications
:end
pause
