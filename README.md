# Bot de Trading Binance — Tendência + Pullback com gestão de risco

**A carteira tem duas partes, com dinheiro separado:**

| Parte | Quanto | O que faz | Por quê |
|---|---|---|---|
| **Bot** | 75% | Operações de poucos dias (4h) com stop, só a favor da tendência | Protege o capital: queda máx. ~9% em 6 anos, ficou de fora em 2022 |
| **Cofre de tendência** | 25% | Segura BTC/ETH enquanto a tendência diária está em alta; senão USDT | Aproveita as grandes altas que o bot perde |

Reequilíbrio para 75/25 todo mês. Teste em 6 anos (out/2020–nov/2026, 100 USDT):
**100 → ~213–221 USDT, queda máxima 17%** (só o bot: 100 → 117, queda 9%;
segurar BTC: 100 → 717, queda 77%). Detalhes em [`PESQUISA.md`](PESQUISA.md).

Bot em Python para **Binance Spot (somente compra)** que segue regras objetivas:
só compra **a favor da tendência**, no **pullback que já mostrou retomada**, com **stop
loss registrado na corretora**, **tamanho de posição pelo risco** e **saída em etapas**
(parcial + empate + trailing). O mesmo conjunto de regras está escrito em linguagem
natural em [`PROMPT_ANALISE.md`](PROMPT_ANALISE.md) para você analisar gráficos com uma IA.

> ⚠️ **Aviso**: nenhuma estratégia garante lucro. Criptomoedas são muito voláteis.
> Faça **backtest → paper → testnet → valor pequeno real**, nessa ordem. Use só dinheiro
> que você pode perder. Isto não é recomendação financeira.

## Como a estratégia decide

| Etapa | Regra |
|---|---|
| **Mercado (BTC, diário)** | Só compra qualquer moeda se o BTC também estiver em tendência de ALTA |
| **Tendência (diário)** | ALTA = preço > EMA200, EMA50 > EMA200 e EMA200 subindo. Só compra em ALTA. |
| **Estrutura (4h)** | EMA21 > EMA50 > EMA200 |
| **Pullback** | Nos últimos 5 candles o preço tocou a EMA21 sem fechar abaixo da EMA50 |
| **Gatilho** | Candle de alta fechando acima da EMA21 e da máxima anterior |
| **Filtros** | RSI 45–68 · MACD > 0 com histograma subindo · ADX ≥ 20 · volume ≥ média · no máx. 1,5 ATR acima da EMA21 |
| **Stop** | Fundo dos últimos 10 candles − 0,2 ATR, limitado entre 1 e 3 ATR |
| **Tamanho** | Perda no stop = 1% do capital (com taxas); posição ≤ 25% do capital |
| **Saída** | Trailing stop: máxima desde a entrada − 3 ATR (o stop só sobe) |
| **Travas** | Para no dia com −3% · pausa 24h após 3 stops seguidos · máx. 2 posições · risco pela metade se a carteira cair 5% do pico |

Moedas: BTC, ETH, BNB, SOL, XRP, ADA, LTC e LINK (consolidadas).
Estas regras foram escolhidas num teste com 3 anos de dados reais — veja
[`PESQUISA.md`](PESQUISA.md) para os números, inclusive o que **não** funcionou.

Tudo é ajustável em [`config.yaml`](config.yaml).

**Coerência na entrada**: decisões só em **candle fechado**; a tendência do 4h usada em
cada candle de 1h vem apenas de candles de 4h **já fechados** (sem olhar o futuro — há
teste para isso); e o backtest usa **exatamente o mesmo código** do bot ao vivo, entrando
na abertura do candle seguinte ao sinal, com taxa e slippage.

Os dados públicos de preço vêm do espelho oficial `data-api.binance.vision`
(`market_data_url` no config), que funciona em regiões onde `api.binance.com` é bloqueado.

## Começar no seu computador (sem servidor)
Windows: dois cliques em `iniciar_paper.bat`. Mac/Linux: `bash iniciar_paper.sh`.
Detalhes em [`docs/COMPUTADOR.md`](docs/COMPUTADOR.md). Funciona enquanto o computador estiver ligado.

## Rodar 24 horas num servidor
Passo a passo completo (VPS, segurança, Telegram, alerta de bot parado, testnet e real):
**[`docs/VPS.md`](docs/VPS.md)**. Resumo:
```bash
bash deploy/preparar_servidor.sh        # uma vez, no VPS novo (firewall, Docker, SSH só por chave)
cp .env.example .env && chmod 600 .env  # Telegram/healthchecks (e chaves da Binance depois)
mkdir -p runtime && sudo chown 10001:10001 runtime
docker compose up -d --build            # liga e mantém ligado; reinicia sozinho
```
**No celular (Telegram):** avisos de compra, venda, stop, cofre, alarmes e erros; resumo diário;
comandos `/status`, `/pausar`, `/retomar` (só do seu chat; não há comando de compra/venda/saque).
**Bot parado:** o healthchecks.io avisa se o bot ficar 15 minutos sem dar sinal de vida.

## Instalação
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Uso
```bash
# 1) Backtest com dados reais da Binance (não precisa de chave)
python -m bot backtest --days 1150          # ~3 anos
python -m bot backtest --days 180 --symbols BTC/USDT ETH/USDT

# 2) Análise atual de cada par (checklist + plano de trade)
python -m bot analyze
python -m bot analyze --symbols SOL/USDT --prompt > analise.md   # prompt + dados p/ colar numa IA

# 2b) Backtest da carteira completa (bot + cofre de tendência), ~6 anos
python -m bot carteira --balance 100

# 3) Painel visual (gráfico com sinais, stop, capital e checklist) -> abre dashboard.html no navegador
python -m bot dashboard --days 180            # dados reais da Binance
python -m bot dashboard --demo                # dados simulados, sem internet

# 4) Paper trading: preços reais, dinheiro fictício (config: paper.initial_balance)
python -m bot paper

# 5) Testnet (ordens de verdade em ambiente de teste)
#    Crie chaves em https://testnet.binance.vision e coloque no .env; config: testnet: true
python -m bot live

# 6) Dinheiro real: config testnet: false  e  CONFIRMO_OPERAR_DINHEIRO_REAL=SIM no .env
python -m bot live
```

### Como o bot aprende
```bash
python -m bot aprender      # o que funcionou, alarme de desvio e proposta de ajuste
```
- **Diário** (`logs/diario.jsonl`): cada operação do paper/live é gravada com o retrato do
  mercado na entrada (ADX, volatilidade, RSI, volume, sessão, tendência do BTC) e o resultado.
  O `aprender` junta isso com as operações do histórico e mostra o que deu certo em cada condição.
- **Defesa automática** (`risk.adaptive_risk`): carteira 5% abaixo do pico → arrisca metade
  até recuperar. Reage a cada perda sem mudar a estratégia.
- **Alarme de desvio**: se as últimas 10 operações na prática ficarem abaixo do pior 5% do
  histórico, o bot arrisca metade e avisa no log — sinal de que o mercado mudou.
- **Reotimização**: testa um conjunto fixo de ajustes nos últimos 12 meses e, só se um for
  claramente melhor (≥ 15 operações e 25% de pontuação a mais), salva `config_proposta.yaml`
  para você revisar. Ela **não** troca sozinha: no teste walk-forward, trocar automaticamente
  piorou o resultado (111 vs 118 USDT). Veja `PESQUISA.md`.

Logs ficam em `logs/bot.log`; o estado (posições, travas) em `state_<modo>.json`, então o
bot retoma de onde parou se reiniciar. No modo live o **stop fica na Binance**
(`STOP_LOSS_LIMIT`), protegendo a posição mesmo se o bot cair.

### Segurança
**Chave da API**
- Permissão **somente Spot Trading**. **Nunca** habilite saque nem transferências.
  Com dinheiro real o bot **confere isso na Binance e se recusa a operar** se a chave puder sacar.
- Restrinja a chave ao IP do servidor (o bot avisa no log se não estiver restrita).
- O `.env` fica fora do git. No servidor: `chmod 600 .env` (o bot avisa se estiver aberto).
- Ative 2FA na conta Binance e use um e-mail exclusivo para ela.

**Proteções do bot no modo real**
- O stop fica registrado na Binance; a cada minuto o bot confere se ele continua ativo e o
  registra de novo se tiver sumido (falha de rede, cancelado no aplicativo).
- Queda com "gap" (preço pulou o limite da ordem stop-limit): o bot vende a mercado na hora.
- Execução parcial do stop é contabilizada; na partida, o estado é conferido com o saldo
  real (venda manual, stop executado com o bot desligado).
- Os stops são conferidos **antes** de qualquer outra coisa em cada ciclo.
- Uma só cópia por modo (trava de arquivo) para não duplicar ordens.
- **Botão de emergência:** crie um arquivo `PAUSAR` na pasta do bot (`touch PAUSAR`) e ele
  para de abrir posições; as abertas continuam protegidas. Apague o arquivo para voltar.
- Logs com rotação (5 arquivos de 5 MB). Dependências com versões fixas (`requirements.txt`).

## Estrutura
```
PROMPT_ANALISE.md   prompt de análise técnica (mesmas regras do bot)
config.yaml         parâmetros da estratégia e do risco
bot/indicators.py   EMA, RSI, MACD, ATR, ADX (pandas puro)
bot/strategy.py     tendência, sinal de entrada, gestão da posição
bot/risk.py         tamanho de posição, perda diária, pausa após stops
bot/data.py         download de candles e alinhamento 1h × 4h sem look-ahead
bot/backtest.py     simulação candle a candle
bot/exchange.py     Binance (ccxt) e corretora simulada (paper)
bot/trader.py       loop ao vivo
bot/report.py       relatório/checklist de análise
bot/dashboard.py    gera o painel HTML (bot/dashboard_template.html)
bot/sleeve.py       cofre "seguir a tendência" (25%) e backtest da carteira
bot/learn.py        diário, relatório de aprendizado, alarme de desvio, reotimização
bot/notify.py       Telegram e sinal de vida (healthchecks.io)
Dockerfile, docker-compose.yml   container com reinício automático e restrições de segurança
deploy/preparar_servidor.sh      prepara e protege o VPS
docs/VPS.md                      passo a passo do servidor
bot/demo.py         dados simulados para demonstração e testes
tests/              testes (dados sintéticos)
```

## Testes
```bash
pytest -q
```

## Próximos passos sugeridos
- Rodar o backtest em vários períodos (alta, baixa, lateral) antes de mexer nos parâmetros —
  e cuidado com *overfitting*: parâmetro bom só num período não é parâmetro bom.
- Deixar no paper/testnet por algumas semanas e comparar com o backtest.
- Alertas por Telegram, filtro de correlação com o BTC.
