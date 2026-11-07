@echo off
REM Inicia o bot na TESTNET da Binance (ordens de verdade, dinheiro de mentira).
REM Precisa das chaves da testnet no .env (testnet.binance.vision). Para parar: feche a janela.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Rode primeiro o iniciar_paper.bat uma vez para preparar o ambiente.
  pause
  exit /b 1
)
findstr /r /c:"^BINANCE_API_KEY=..*" ".env" >nul
if errorlevel 1 (
  echo Falta a chave da TESTNET no arquivo .env ^(BINANCE_API_KEY e BINANCE_API_SECRET^).
  echo Veja o passo a passo em docs\TESTNET.md
  notepad ".env"
  pause
  exit /b 1
)
"%PY%" -m pip install -q --disable-pip-version-check -r requirements.txt
"%PY%" -X utf8 -m bot live
pause
exit /b 0
