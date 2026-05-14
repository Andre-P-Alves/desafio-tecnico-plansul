@echo off
:: Pipeline de faturamento hospitalar — Windows
:: Logging, tratamento de erros e exit code sao responsabilidade do main.py

set SCRIPT_DIR=%~dp0
set PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo ERRO: Ambiente virtual nao encontrado.
    echo Execute: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

"%PYTHON%" "%SCRIPT_DIR%main.py"
exit /b %ERRORLEVEL%
