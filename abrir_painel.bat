@echo off
rem Abre o tunel seguro ate o servidor e a Central dos bots no navegador.
rem Deixe esta janela aberta enquanto usa o painel. Para fechar: feche a janela.
title Painel do bot - tunel SSH
echo.
echo  Digite a senha da sua chave SSH e aperte Enter.
echo  Depois o navegador abre sozinho em http://localhost:8765
echo  Deixe esta janela ABERTA enquanto usa o painel.
echo.
start "" cmd /c "timeout /t 12 /nobreak >nul & start http://localhost:8765"
ssh -N -o ExitOnForwardFailure=yes -L 8765:localhost:8765 bot@187.41.127.210
echo.
echo  O tunel foi fechado. Se nao abriu, confira a senha da chave e tente de novo.
pause
