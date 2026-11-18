@echo off
rem Confere a saude do servidor: bots, disco, memoria e erros recentes. So LE, nao muda nada.
cd /d "%~dp0"
title Verificar servidor do bot
echo.
echo  Conferindo o servidor. Digite a senha da chave SSH:
echo.
ssh bot@187.41.127.210 "cd ~/Hortolani && echo '=== BOTS ===' && docker compose ps --format 'table {{.Name}}\t{{.Status}}' && echo && echo '=== DISCO (precisa ter espaco livre) ===' && df -h / | awk 'NR==2{print \"usado \" $3 \" de \" $2 \" (\" $5 \") - livre \" $4}' && echo && echo '=== MEMORIA ===' && free -h | awk 'NR==2{print \"usada \" $3 \" de \" $2}' && echo && echo '=== ERROS NAS ULTIMAS 24 H ===' && (docker compose logs --since 24h 2>&1 | grep -E 'ERROR|Traceback' | tail -8 || true) && echo '(se nao apareceu nada acima, nenhum erro)' && echo && echo '=== ATUALIZACOES DO SISTEMA ===' && (test -f /var/run/reboot-required && echo 'O servidor pede REINICIO (avise o Claude)' || echo 'nenhum reinicio pendente')"
echo.
pause
