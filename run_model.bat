@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 goto error
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 goto error
python -m streamlit run app.py
goto end
:error
echo Please check that Python 3.12 is installed and available on PATH.
:end
pause
