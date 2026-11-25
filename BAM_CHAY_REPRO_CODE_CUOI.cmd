@echo off
setlocal
chcp 65001 >nul
set PYTHONDONTWRITEBYTECODE=1
set PYTHONUTF8=1
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" -B "%~dp0workflow\windows_start.py"
  goto done
)
if exist "%USERPROFILE%\miniconda3\python.exe" (
  "%USERPROFILE%\miniconda3\python.exe" -B "%~dp0workflow\windows_start.py"
  goto done
)
where python >nul 2>nul
if errorlevel 1 (
  echo BLOCKED: Existing Python not found. No installation attempted.
  goto done
)
python -B "%~dp0workflow\windows_start.py"
:done
pause
