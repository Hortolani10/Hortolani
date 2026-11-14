@echo off
rem Baixa uma copia dos dados dos bots (diarios de operacoes e saldos) para a pasta backup.
rem So LE do servidor: nao muda nada nos bots. Rode uma vez por semana.
cd /d "%~dp0"
title Backup dos dados dos bots
if not exist backup mkdir backup
for /f %%d in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set DATA=%%d
set ARQ=backup\dados_%DATA%.tgz
echo.
echo  Baixando os diarios e saldos dos bots. Digite a senha da chave SSH:
ssh bot@187.41.127.210 "cd ~/Hortolani/runtime && tar -czf - $(find . -maxdepth 3 \( -name diario.jsonl -o -name 'state_*.json' \))" > "%ARQ%"
if errorlevel 1 (
  echo  ERRO no backup. Confira a senha da chave e a internet.
  del "%ARQ%" 2>nul
  pause
  exit /b 1
)
echo.
echo  PRONTO! Copia salva em: %CD%\%ARQ%
echo  Guarde essa pasta backup (Google Drive, pendrive...): sao os dados que os bots aprenderam.
echo.
pause
