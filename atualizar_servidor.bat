@echo off
rem Atualiza o servidor com os arquivos desta pasta e reinicia os bots.
rem Nao envia .env, saldo, diario nem logs: isso tudo fica como esta no servidor.
cd /d "%~dp0"
title Atualizar servidor do bot
echo.
echo  ============================================
echo   ATUALIZAR O SERVIDOR (5 bots)
echo  ============================================
echo.
if not exist "bot\regime.py" (
  echo  ERRO: rode este arquivo de dentro da pasta Hortolani.
  pause
  exit /b 1
)
set PACOTE=%TEMP%\bot_atualizacao.tar
if exist "%PACOTE%" del "%PACOTE%"
echo  1/3 Juntando os arquivos...
tar -cf "%PACOTE%" --exclude=__pycache__ --exclude=*.pyc bot pesquisa deploy docs tests config.yaml config_ativo.yaml config_aprendiz.yaml config_aprendiz_2h.yaml config_aprendiz_1h.yaml config_aprendiz_15m.yaml requirements.txt Dockerfile docker-compose.yml .dockerignore README.md PESQUISA.md PROMPT_ANALISE.md
if errorlevel 1 (
  echo  ERRO ao juntar os arquivos. Confira se o ZIP foi extraido nesta pasta.
  pause
  exit /b 1
)
echo.
echo  2/3 Enviando para o servidor. Digite a senha da chave SSH:
scp "%PACOTE%" bot@187.41.127.210:atualizacao.tar
if errorlevel 1 (
  echo  ERRO no envio. Confira a senha da chave e a internet e tente de novo.
  pause
  exit /b 1
)
echo.
echo  3/3 Instalando e reiniciando os bots (2 a 4 minutos). Digite a senha da chave de novo:
ssh bot@187.41.127.210 "rm -rf ~/novo && mkdir -p ~/novo && tar -xf ~/atualizacao.tar -C ~/novo && cp -r ~/novo/. ~/Hortolani/ && rm -rf ~/novo ~/atualizacao.tar && cd ~/Hortolani && docker compose up -d --build && echo && docker compose ps"
if errorlevel 1 (
  echo.
  echo  Algo deu errado na instalacao. Tire um print desta janela e mande para o Claude.
  pause
  exit /b 1
)
del "%PACOTE%"
echo.
echo  PRONTO! Os 5 bots devem aparecer acima como "Up".
echo  Para ver o painel: dois cliques em abrir_painel.bat
echo.
pause
