@echo off
chcp 65001 >NUL
cd /d "%~dp0"
py -3 E12_AUTO_RUN.py
if errorlevel 1 echo E12 failed. Read the console error; verify the original development Parquet.
echo.
pause
