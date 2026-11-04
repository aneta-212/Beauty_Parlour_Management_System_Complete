@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" manage.py send_reminders
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" manage.py send_notifications
exit /b %errorlevel%
