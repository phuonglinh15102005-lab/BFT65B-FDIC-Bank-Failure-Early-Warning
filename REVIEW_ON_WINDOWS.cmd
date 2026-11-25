@echo off
cd /d "%~dp0"
set "OUT=%USERPROFILE%\Downloads\BFT65B_REVIEW_%RANDOM%_%RANDOM%"
py -3 -B tools\reviewer_check.py --out "%OUT%"
if errorlevel 1 (
 echo Check failed. Open %OUT% for logs.
) else (
 echo PASS source and archive verification only. Logs: %OUT%
)
pause
