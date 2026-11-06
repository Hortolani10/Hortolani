@echo off
REM Inicia o bot em modo PAPER no Windows (dinheiro ficticio, precos reais).
REM Dois cliques neste arquivo. Para parar: feche a janela ou aperte Ctrl+C.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"

REM ambiente quebrado de uma tentativa anterior: apaga e recria
if exist ".venv" if not exist "%PY%" rmdir /s /q ".venv"

if exist "%PY%" goto deps
echo Preparando o ambiente pela primeira vez (2 a 5 minutos)...
py -3 -m venv .venv 2>nul
if not exist "%PY%" if exist "%LocalAppData%\Programs\Python\Python314\python.exe" "%LocalAppData%\Programs\Python\Python314\python.exe" -m venv .venv
if not exist "%PY%" if exist "%ProgramFiles%\Python314\python.exe" "%ProgramFiles%\Python314\python.exe" -m venv .venv
if not exist "%PY%" goto sem_python

:deps
REM pip/certifi novos: versoes antigas confiam em certificados comprometidos (eMudhra)
"%PY%" -m pip install -q --disable-pip-version-check --upgrade "pip>=26.2.2" certifi
if errorlevel 1 goto erro_pip
"%PY%" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto erro_pip

if exist ".env" goto rodar
copy ".env.example" ".env" >nul
echo.
echo Arquivo .env criado. Preencha o Telegram no Bloco de Notas, salve e rode de novo.
echo (pode deixar vazio para rodar sem avisos no celular)
notepad ".env"
pause
exit /b 0

:rodar
"%PY%" -X utf8 -m bot paper
pause
exit /b 0

:sem_python
echo.
echo ERRO: nao encontrei o Python.
echo Instale o Python 3.14.10 (python.org) marcando "Add python.exe to PATH" e rode de novo.
echo Para conferir, abra o Prompt de Comando e digite:  py --version
pause
exit /b 1

:erro_pip
echo.
echo ERRO ao instalar as bibliotecas. Confira a internet e rode de novo.
pause
exit /b 1
