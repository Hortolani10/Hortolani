# Pesquisa da estratégia — 3 anos de dados reais (Binance)

Dados: candles reais de set/2023 a nov/2026 (`data-api.binance.vision`), moedas
consolidadas: BTC, ETH, BNB, SOL, XRP, ADA, LTC, LINK. Taxa 0,1% + slippage 0,05% por lado.
Carteira de 100 USDT, risco de 1% por operação.

**Método (para não "decorar" o passado):** a escolha foi feita só com os 2 primeiros anos
(**treino**, até 05/11/2025). O último ano (**validação**) ficou escondido e só foi olhado
depois. Regra de escolha definida antes: maior retorno no treino com pelo menos 30 operações.

## 1. O mercado no período

| Moeda | 09/23–11/24 | 11/24–11/25 | 11/25–11/26 | Tempo em ALTA no diário (treino / validação) |
|---|---|---|---|---|
| BTC | +159% | +46% | −23% | 83% / 15% |
| ETH | +49% | +36% | −29% | 51% / 15% |
| BNB | +160% | +66% | −25% | 82% / 28% |
| SOL | +758% | −7% | −41% | 65% / 13% |
| XRP | +4% | +329% | −44% | 66% / 3% |
| ADA | +31% | +56% | −64% | 35% / 0% |
| LTC | +6% | +30% | −37% | 45% / 9% |
| LINK | +70% | +36% | −24% | 34% / 17% |

O último ano foi de **queda forte em todas**. Uma estratégia que só compra (spot) tem pouco a
fazer num ano assim; o objetivo é perder pouco e preservar o capital.

## 2. Qual tipo de entrada tem vantagem? (cada sinal isolado)

| Entrada | Tempo gráfico | Treino | Validação |
|---|---|---|---|
| Pullback (regra do bot) | 1h / 4h | FL 0,91 · −0,13%/op | FL 0,73 |
| Rompimento de 20 candles | 1h / 4h | FL 0,98 | FL 1,10 |
| RSI(2) sobrevenda | 1h / 4h | FL 0,76 | FL 0,51 |
| Entradas aleatórias (base) | 1h / 4h | FL 1,26 | FL 0,84 |
| **Pullback (regra do bot)** | **4h / 1d** | **FL 2,50 · +2,94%/op** | FL 0,68 |
| Rompimento de 20 candles | 4h / 1d | FL 1,47 | FL 0,21 |
| RSI(2) sobrevenda | 4h / 1d | FL 0,71 | FL 0,46 |

FL = fator de lucro (ganhos ÷ perdas; acima de 1 = lucro).
**No 1h nada superou entradas aleatórias** — as taxas comem a vantagem de operações curtas.
No 4h com tendência no diário, o pullback teve a melhor vantagem no treino.

## 3. Bot completo (carteira, travas e taxas), 4h / 1d

| Variante | Treino ops | Treino FL | Treino retorno | Validação ops | Validação retorno |
|---|---|---|---|---|---|
| **Trailing 3 ATR + filtro BTC (escolhida)** | 49 | 1,81 | **+13,0%** | 9 | −2,5% |
| Trailing 3 ATR | 51 | 1,72 | +12,0% | 12 | −1,7% |
| Trailing + saída na EMA50 | 52 | 1,59 | +10,7% | 12 | −1,3% |
| Parcial 1,5R + empate + trailing | 51 | 1,34 | +6,5% | 12 | +0,3% |
| Alvo fixo 2R | 50 | 1,03 | +0,7% | 12 | +1,3% |
| Configuração antiga (1h/4h, parcial) | 53 | 0,68 | −5,0% | 23 | −2,4% |

Também descobrimos que o filtro "espaço até a resistência ≥ 1,5R" barrava 95% dos sinais
no 4h; ele foi desligado (`min_reward_risk: 0`).

## 4. Resultado da configuração escolhida (3 anos)

- 69 operações, 39% de acerto, fator de lucro 1,47, **100 → ~111 USDT** (+11,6%), maior queda 8,5%.
- Em janelas de 30 dias: média **+0,37%**, mediana 0% (em metade dos meses o bot nem opera),
  pior mês −2,5%, melhor mês +10,3%.
- Período de alta (treino): média +0,73% a cada 30 dias. Ano de baixa (validação): −0,21%.

## Conclusões honestas

- A estratégia **ganha em mercado de alta e perde pouco em mercado de baixa**; ela não lucra
  com quedas (spot, só compra).
- A validação (9 operações) foi negativa. É uma amostra pequena num ano atípico de queda —
  **não prova** que a estratégia funciona daqui para frente.
- Próximo passo recomendado: rodar em `paper` por algumas semanas e comparar com o backtest
  antes de qualquer dinheiro real.
