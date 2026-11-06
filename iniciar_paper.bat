@echo off
REM Inicia o bot em modo PAPER no Windows (dinheiro fictício, preços reais).
REM Dê dois cliques neste arquivo. Para parar: feche a janela ou aperte Ctrl+C.
cd /d %~dp0
chcp 65001 >nul
if not exist .venv (
  echo Preparando o ambiente pela primeira vez...
  py -3 -m venv .venv || (echo ERRO: instale o Python 3.14.10 ou mais novo em python.org e marque "Add to PATH" & pause & exit /b 1)
)
call .venv\Scripts\activate.bat
REM pip/certifi novos: as versões antigas confiam em certificados comprometidos (eMudhra, out/2026)
python -m pip install -q --upgrade "pip>=26.2.2" certifi || (echo ERRO ao atualizar o pip & pause & exit /b 1)
python -m pip install -q -r requirements.txt || (echo ERRO ao instalar dependencias & pause & exit /b 1)
if not exist .env (
  copy .env.example .env >nul
  echo Arquivo .env criado. Abra-o no Bloco de Notas, preencha o Telegram e rode de novo.
  notepad .env
  pause
  exit /b 0
)
python -m bot paper
pause
