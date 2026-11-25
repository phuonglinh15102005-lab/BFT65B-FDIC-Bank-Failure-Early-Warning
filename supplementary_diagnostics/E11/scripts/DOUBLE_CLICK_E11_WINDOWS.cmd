@echo off
chcp 65001 >NUL
cd /d "%~dp0"
py -3 E11_AUTO_RUN.py
if errorlevel 1 (
  echo E11 FAILED. Please save screenshot and check the requirements.
)
echo.
pause
