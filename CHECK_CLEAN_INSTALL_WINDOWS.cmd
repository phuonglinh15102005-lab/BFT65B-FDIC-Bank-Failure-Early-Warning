@echo off
cd /d "%~dp0"
set "ENGINE=%USERPROFILE%\miniconda3\python.exe"
set "MODEL=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%ENGINE%" set /p "ENGINE=Original Python 3.13.9 executable: "
if not exist "%MODEL%" set /p "MODEL=Original Python 3.13.7 executable: "
set "OUT=%USERPROFILE%\Downloads\BFT65B_INSTALL_%RANDOM%_%RANDOM%"
"%ENGINE%" -B tools\verify_clean_install.py --profile engineering --out "%OUT%_engineering"
"%MODEL%" -B tools\verify_clean_install.py --profile model --out "%OUT%_model"
echo Return STATUS.json and install, freeze, pip_check, imports logs only. Do not send the venv or private files.
pause
