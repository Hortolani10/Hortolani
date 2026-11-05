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

### Resultado por moeda (3 anos, mesma carteira de 100 USDT)

| Moeda | Operações | Acerto | Fator de lucro | Média (R) | Resultado |
|---|---|---|---|---|---|
| BNB | 15 | 40% | 2,10 | +0,61R | +6,93 USDT |
| ETH | 9 | 44% | 2,79 | +0,53R | +4,54 USDT |
| XRP | 3 | 67% | 5,60 | +2,80R | +4,43 USDT |
| ADA | 3 | 33% | 2,28 | +0,67R | +1,91 USDT |
| SOL | 12 | 50% | 1,16 | +0,02R | +0,53 USDT |
| LINK | 6 | 50% | 0,69 | −0,10R | −0,60 USDT |
| LTC | 3 | 0% | 0,00 | −0,49R | −1,56 USDT |
| BTC | 18 | 28% | 0,28 | −0,39R | −4,63 USDT |

Cada moeda tem operações próprias. O BTC foi o pior: muitos sinais, poucos andaram.
XRP, ADA e LTC tiveram só 3 operações cada — amostra pequena demais para concluir algo
sobre elas isoladamente. **Não remova moedas com base nesta tabela**: escolher as
vencedoras olhando o passado é exatamente o tipo de ajuste que falha no futuro.

## 5. Auditoria dos dados e análise de mercado (nov/2026)

**Dados:** 8 moedas × 1h/4h/1d, set/2023–nov/2026. Nenhum buraco, duplicata, candle inválido
ou volume zero. Os maiores saltos batem com eventos reais (crise do iene em ago/2024,
eleição dos EUA em nov/2024, −14% e +12% em 5–6/fev/2026).

**Horários (UTC):** a abertura da China (01:30 UTC) não mostra efeito consistente; as
diferenças de retorno por hora são de 0,01–0,05% e trocam de sinal entre treino e validação.
A volatilidade e o volume são maiores no horário dos EUA (13–16 UTC: amplitude ~60% maior,
volume até 1,6×), quando saem dados econômicos e abre Wall Street. Fins de semana têm
~25% menos amplitude. Nenhum desses efeitos virou regra: não se repetem com consistência.

**Correlação diária com o BTC:** ETH 0,81 · SOL 0,75 · ADA 0,69 · LINK 0,68 · BNB 0,66 ·
XRP 0,64 · LTC 0,61. Por isso o limite caiu para **2 posições abertas** (treino +14,8% contra
+13,0%; validação −1,8% contra −2,5%).

**Padrões gráficos (4h, diário e BTC em alta; retorno em 3 dias descontando 0,3% de custos):**

| Padrão | Treino | Validação |
|---|---|---|
| Candle qualquer (base) | −0,30% | −0,77% |
| Engolfo de alta | −0,17% | −0,58% |
| Martelo | −0,57% | −1,09% |
| Inside bar rompida | +0,11% | −1,61% |
| Squeeze + rompimento | −0,51% | −3,83% |
| Rompimento da máxima de 20 | +0,72% | −2,00% |
| Fundo duplo (rompido) | −0,38% | −3,23% |
| **Sinal do bot** | **+1,50%** | −0,72% |

Nenhum padrão clássico teve vantagem consistente; no ano de baixa, rompimentos e fundos
duplos viraram armadilhas. Tendência forte (ADX > 30) foi melhor que ADX 20–30 nos dois
períodos; exigir ADX ≥ 25 no bot reduziu o retorno no treino (+9,7%), então **não** foi
adotado — fica como candidato para observar no paper.

## Conclusões honestas

- A estratégia **ganha em mercado de alta e perde pouco em mercado de baixa**; ela não lucra
  com quedas (spot, só compra).
- A validação (9 operações) foi negativa. É uma amostra pequena num ano atípico de queda —
  **não prova** que a estratégia funciona daqui para frente.
- Próximo passo recomendado: rodar em `paper` por algumas semanas e comparar com o backtest
  antes de qualquer dinheiro real.
