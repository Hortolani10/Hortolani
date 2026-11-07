# Testar na Binance TESTNET (dinheiro de mentira, ordens de verdade)

A testnet é uma cópia da Binance para testes. O bot envia ordens reais (compra, stop, venda),
mas o saldo é fictício. Serve para confirmar que tudo funciona antes de usar dinheiro de verdade.

## 1. Criar as chaves da testnet
1. Abra **https://testnet.binance.vision** no navegador.
2. Clique em **"Log In with GitHub"** (precisa de uma conta no GitHub; é grátis).
3. Clique em **"Generate HMAC_SHA256 Key"**, dê um nome (ex.: `bot-hortolani`) e confirme.
4. Aparecem a **API Key** e a **Secret Key**. **Copie as duas agora** — a Secret só aparece uma vez.

Essas chaves só funcionam na testnet (não mexem na sua conta real), mas mesmo assim:
**não mande para ninguém, nem para o Claude.**

## 2. Colocar as chaves no .env
Feche o bot, abra o `.env` no Bloco de Notas e preencha:
```
BINANCE_API_KEY=a_api_key_da_testnet
BINANCE_API_SECRET=a_secret_key_da_testnet
CONFIRMO_OPERAR_DINHEIRO_REAL=NAO
```
Deixe `CONFIRMO_OPERAR_DINHEIRO_REAL=NAO`. No `config`, confira que está `testnet: true`.

## 3. Ligar
Dois cliques em **`iniciar_testnet.bat`**. No Telegram chega **"[TESTNET] Bot iniciado"**.
Painel da testnet: **http://localhost:8766** (o do paper continua em 8765).

O bot usa no máximo **100 USDT** (`live.budget_usdt` no config), mesmo a conta da testnet
tendo milhares de dólares fictícios.

## 4. O que conferir nas próximas 1–2 semanas
- Quando houver compra: a ordem aparece no histórico da testnet?
- Logo depois, o **stop** aparece como ordem aberta ("Open Orders")?
- Quando o stop sobe (trailing), a ordem antiga some e uma nova aparece?
- A venda acontece no stop ou quando o preço volta à média (lateralização)?
- Os avisos chegam no Telegram marcados **[TESTNET]**?

Observação: os preços da testnet às vezes ficam diferentes do mercado real (pouca gente
negocia lá), então os sinais podem não bater com o paper. O objetivo aqui é testar as ORDENS.

## Rodar paper e testnet juntos?
Pode: são janelas separadas, com estados separados (`state_paper.json` e `state_live.json`).
As respostas do Telegram dizem de qual bot vêm ([PAPER] ou [TESTNET]).
