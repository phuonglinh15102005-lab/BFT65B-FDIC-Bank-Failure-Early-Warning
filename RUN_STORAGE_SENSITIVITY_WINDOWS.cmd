@echo off
setlocal
cd /d "%~dp0"
if not exist "tools\storage_sensitivity.py" (
 echo Extract ALL files before running this command.
 pause
 exit /b 1
)
set "ENGINE=%USERPROFILE%\miniconda3\python.exe"
set "AUDIT=%USERPROFILE%\data_raw\fdic\audit_results\20261108T032158_540721Z"
if not exist "%ENGINE%" set /p "ENGINE=Full path to original engineering python.exe: "
if not exist "%AUDIT%\STANDARDIZATION_COMPLETE.json" set /p "AUDIT=Full path to original passing audit folder: "
if not exist "D:\" (
 echo Drive D: is not accessible. No benchmark started.
 pause
 exit /b 1
)
set "DEST=D:\BFT_OUT"
if not exist "%DEST%" mkdir "%DEST%"
if not exist "%DEST%\temp" mkdir "%DEST%\temp"
if not exist "%DEST%\temp" (
 echo Cannot create output/temp directory on D:.
 pause
 exit /b 1
)
set "TEMP=%DEST%\temp"
set "TMP=%DEST%\temp"
set "OUT=%DEST%\storage_%RANDOM%_%RANDOM%"
echo Output: %OUT%
echo Temporary files: %TEMP%
echo Original inputs stay on C:.
"%ENGINE%" -B tools\storage_sensitivity.py --audit-dir "%AUDIT%" --out "%OUT%" --repeats 7 --warmups 2 --threads 4
if errorlevel 1 (echo BLOCKED OR FAIL: capture terminal; do not use partial results.) else (echo Return only %OUT%\storage_review_bundle.zip)
pause
