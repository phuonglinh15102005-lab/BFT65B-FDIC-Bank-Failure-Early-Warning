@echo off
setlocal
REM No final-test scoring; input must be the original hash-pinned development cohort.
set /p DEV=Path to development_primary_binary_v2.parquet: 
set /p CLEAN=Path to panel_clean.parquet (press ENTER to skip RBCRWAJ): 
set /p SOURCE=Path to frozen_pipeline folder: 
set "OUT=%LOCALAPPDATA%\BFT65B_TARGETED_DEV_AUDIT_%RANDOM%_%RANDOM%"
echo New outputs will be written to "%OUT%"
if "%CLEAN%"=="" (
    python "%~dp0dev_only_targeted_diagnostics.py" --dev "%DEV%" --source "%SOURCE%" --out "%OUT%"
) else (
    python "%~dp0dev_only_targeted_diagnostics.py" --dev "%DEV%" --clean "%CLEAN%" --source "%SOURCE%" --out "%OUT%"
)
if errorlevel 1 (echo FAILED. No result should be cited. & pause & exit /b 1)
echo Success. Send the CSVs and RUN_MANIFEST.json in "%OUT%" for evidence integration.
pause
