# Rodar no seu computador (enquanto não tem o VPS)

Funciona igual ao servidor, mas **só enquanto o computador estiver ligado e acordado**.
Use para começar o modo paper e testar o Telegram. Depois é só levar a pasta para o VPS
(a pasta `runtime`/arquivos `state_paper.json` e `logs/` levam o histórico junto).

## Windows
1. Instale o **Python 3.14.10 ou mais novo** (https://www.python.org/downloads/windows/,
   "Windows installer (64-bit)") — na primeira tela marque **"Add python.exe to PATH"**.
   Não use versões anteriores a 3.14.10 / 3.13.18: elas não bloqueiam os certificados
   comprometidos da eMudhra (out/2026). O bot foi testado em 3.13.18 e 3.14.6.
2. Descompacte o `Hortolani-bot.zip` numa pasta (ex.: `Documentos\Hortolani`).
3. Dê dois cliques em **`iniciar_paper.bat`**. Na primeira vez ele prepara tudo e abre o
   `.env` no Bloco de Notas.
4. Preencha `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` (passo a passo na seção 4 do
   `docs/VPS.md`), salve e dê dois cliques no `iniciar_paper.bat` de novo.
5. Você deve receber no Telegram: **"[PAPER] Bot iniciado..."**. Mande `/status` para testar.

Para o bot não parar quando a tela apagar: *Configurações → Sistema → Energia →
Suspensão: Nunca* (quando ligado na tomada).

## Mac
1. Instale o Python 3.14.10 ou mais novo em https://www.python.org/downloads/.
2. Descompacte o zip, abra o **Terminal** na pasta e rode: `bash iniciar_paper.sh`.
3. Preencha o `.env` (`nano .env`), rode `bash iniciar_paper.sh` de novo.
4. Para o Mac não dormir: rode com `caffeinate -i bash iniciar_paper.sh`.

## Bom saber
- Fechar a janela para o bot. Os dados ficam salvos; ao abrir de novo ele continua de onde parou.
- O alerta de bot parado (healthchecks.io) vai disparar sempre que você desligar o computador —
  configure só quando estiver no VPS, ou ignore esses avisos por enquanto.
- O token do Telegram fica só no `.env` do seu computador. Não mande para ninguém.
