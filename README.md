# Bot de Trading Binance — Tendência + Pullback com gestão de risco

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
| **Tendência (4h)** | ALTA = preço > EMA200, EMA50 > EMA200 e EMA200 subindo. Só compra em ALTA. |
| **Estrutura (1h)** | EMA21 > EMA50 > EMA200 |
| **Pullback** | Nos últimos 5 candles o preço tocou a EMA21 sem fechar abaixo da EMA50 |
| **Gatilho** | Candle de alta fechando acima da EMA21 e da máxima anterior |
| **Filtros** | RSI 45–68 · MACD > 0 com histograma subindo · ADX ≥ 20 · volume ≥ média · no máx. 1,5 ATR acima da EMA21 |
| **Espaço** | Distância até a resistência ≥ 1,5× o risco (ou rompimento de topo) |
| **Stop** | Fundo dos últimos 10 candles − 0,2 ATR, limitado entre 1 e 3 ATR |
| **Tamanho** | Perda no stop = 1% do capital (com taxas); posição ≤ 25% do capital |
| **Saída** | 50% em +1,5R → stop no empate → trailing de 3 ATR · sai se fechar abaixo da EMA50 ou se o 4h virar BAIXA |
| **Travas** | Para no dia com −3% · pausa 24h após 3 stops seguidos · máx. 3 posições |

Tudo é ajustável em [`config.yaml`](config.yaml).

**Coerência na entrada**: decisões só em **candle fechado**; a tendência do 4h usada em
cada candle de 1h vem apenas de candles de 4h **já fechados** (sem olhar o futuro — há
teste para isso); e o backtest usa **exatamente o mesmo código** do bot ao vivo, entrando
na abertura do candle seguinte ao sinal, com taxa e slippage.

## Instalação
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Uso
```bash
# 1) Backtest com dados reais da Binance (não precisa de chave)
python -m bot backtest --days 365
python -m bot backtest --days 180 --symbols BTC/USDT ETH/USDT

# 2) Análise atual de cada par (checklist + plano de trade)
python -m bot analyze
python -m bot analyze --symbols SOL/USDT --prompt > analise.md   # prompt + dados p/ colar numa IA

# 3) Paper trading: preços reais, dinheiro fictício (config: paper.initial_balance)
python -m bot paper

# 4) Testnet (ordens de verdade em ambiente de teste)
#    Crie chaves em https://testnet.binance.vision e coloque no .env; config: testnet: true
python -m bot live

# 5) Dinheiro real: config testnet: false  e  CONFIRMO_OPERAR_DINHEIRO_REAL=SIM no .env
python -m bot live
```

Logs ficam em `logs/bot.log`; o estado (posições, travas) em `state_<modo>.json`, então o
bot retoma de onde parou se reiniciar. No modo live o **stop fica na Binance**
(`STOP_LOSS_LIMIT`), protegendo a posição mesmo se o bot cair.

### Segurança da API key
- Permissão **somente Spot Trading**. **Nunca** habilite saque.
- Restrinja a chave ao IP do servidor.
- Nunca faça commit do `.env` (já está no `.gitignore`).

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
