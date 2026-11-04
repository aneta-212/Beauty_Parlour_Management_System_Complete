@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run SETUP_WINDOWS.bat first.
    pause
    exit /b 1
)
echo Open http://127.0.0.1:8000/ after the server starts.
".venv\Scripts\python.exe" manage.py runserver
pause
