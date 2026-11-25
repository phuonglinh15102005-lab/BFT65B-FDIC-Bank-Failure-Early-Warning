@echo off
chcp 65001 >NUL
cd /d "%~dp0"
set "MODEL=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%MODEL%" set /p "MODEL=Full path to original Python 3.13.7 python.exe: "
"%MODEL%" -c "import platform,sys; print(platform.python_version()); sys.exit(platform.python_version()!='3.13.7')"
if errorlevel 1 (echo Original Python 3.13.7 required. Do not modify the version guard. & pause & exit /b 1)
"%MODEL%" -B tools\reproduce_policy_windows.py
if errorlevel 1 echo BLOCKED or FAIL. Save terminal screenshot; do not change the frozen hashes.
pause
