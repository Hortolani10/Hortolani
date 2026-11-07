@echo off
REM Bot "ATIVO" em modo PAPER (dinheiro ficticio), ao lado do bot normal, para comparar.
REM Painel: http://localhost:8767   Para parar: feche a janela.
setlocal
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Rode primeiro o iniciar_paper.bat uma vez para preparar o ambiente.
  pause
  exit /b 1
)
"%PY%" -m pip install -q --disable-pip-version-check -r requirements.txt
"%PY%" -X utf8 -m bot --config config_ativo.yaml paper
pause
exit /b 0
