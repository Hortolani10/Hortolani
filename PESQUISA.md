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

## 6. Aprendizado: o que ajudou e o que não ajudou

**Defesa automática (risco pela metade quando a carteira cai X% do pico)**, escolhida pelo treino:

| Variante | Treino | Queda máx. (treino) | Validação |
|---|---|---|---|
| Sem defesa | +14,8% | 8,0% | −1,8% |
| **−5% → risco ×0,5 (adotada)** | **+15,6%** | **6,4%** | −1,8% |
| −3% → risco ×0,5 | +12,7% | 5,1% | −1,8% |

**Reotimização automática a cada 3 meses (walk-forward)**: em cada data o bot escolhia, só com
os 12 meses anteriores, o melhor de 18 ajustes (ADX mínimo, trailing, tipo de saída) e operava
os 3 meses seguintes. De abr/2025 a nov/2026, partindo de 100 USDT:

| Método | Saldo final |
|---|---|
| Bot fixo | **117,71 USDT** |
| Bot que se reajusta sozinho | 111,20 USDT |

O adaptativo trocou para "parcial" em jul/2025, logo antes de um período em que deixar o lucro
correr rendia mais. Conclusão: com ~2 operações por mês, reajustar sozinho persegue ruído.
Por isso a reotimização só **propõe**; a mudança é decisão humana.

## 7. Outros tempos gráficos de entrada (tendência no diário) e combinações

| Entrada | Treino ops | Acerto | FL | Treino retorno | Queda | Dias/op | Validação |
|---|---|---|---|---|---|---|---|
| 2h | 76 | 29% | 0,62 | −7,7% | 13,0% | 1,1 | +0,1% |
| **4h** | 42 | 43% | 2,28 | **+15,6%** | 6,4% | 2,8 | −1,8% |
| 6h | 31 | 29% | 1,03 | +0,3% | 5,4% | 4,2 | −1,0% |
| 8h | 24 | 29% | 0,36 | −6,4% | 6,5% | 4,5 | +0,6% |
| 12h | 16 | 19% | 0,32 | −5,2% | 6,2% | 6,1 | −0,8% |

Combinações 50/50 (4h + outro) ficaram todas piores que o 4h sozinho no treino
(+3,9% a +7,9%). **Alerta:** uma estratégia robusta costuma piorar aos poucos quando se
muda o tempo gráfico; aqui o 4h é um pico isolado (vizinhos 2h e 6h bem piores). Isso indica
que parte do resultado do 4h pode ser sorte do período — mais um motivo para o teste com
5–6 anos de dados e o paper antes de dinheiro real.

## 8. Teste com 6 anos (fev/2020–nov/2026) — período NUNCA usado nas escolhas

As regras foram escolhidas com dados de 2023–2025. De out/2020 a set/2023 nada foi visto.

| Período | Bot 4h ops | Bot retorno | Bot queda | BTC segurar | BTC queda | Bot 2h | Bot 6h |
|---|---|---|---|---|---|---|---|
| fim 2020 | 17 | +6,4% | 5,4% | +172% | 11% | −1,5% | +10,9% |
| 2021 (alta forte) | 17 | −5,5% | 6,8% | +58% | 53% | +2,5% | +5,0% |
| 2022 (queda, FTX) | **0** | **0,0%** | 0,0% | −65% | 67% | 0,0% | 0,0% |
| 2023 (recuperação) | 23 | −3,6% | 7,7% | +154% | 20% | −3,1% | −0,1% |
| 2024 | 26 | −0,9% | 7,7% | +112% | 26% | −7,3% | +2,8% |
| 2025 | 26 | +16,2% | 3,7% | −7% | 32% | −4,8% | +3,2% |
| 2026 (até nov) | 8 | −1,8% | 4,1% | −14% | 40% | +0,1% | −1,0% |
| **Nunca visto out/20–set/23** | 53 | **+4,0%** | 8,3% | +143% | 77% | −0,8% | +11,2% |
| **Tudo out/20–nov/26** | 116 | **+17,3%** | 9,3% | +617% | 77% | −8,5% | +25,8% |

Leituras:
- **Protege muito bem:** em 2022 o filtro do BTC deixou o bot 100% fora (zero operações)
  enquanto o BTC caía 65%.
- **Não aproveita as altas:** em 2021 e 2023 perdeu um pouco enquanto o BTC subia 58% e 154%.
- O retorno é baixo (~2,7% ao ano em 6 anos) e veio quase todo de 2025.
- O 6h foi melhor que o 4h no período nunca visto: a vantagem do 4h era do período.

**Seguir a tendência diária (mesma definição do bot, sem ajuste):** segurar a moeda quando a
tendência diária está em ALTA, senão ficar em USDT; custo 0,15% por troca, ~7 trocas por ano.

| Período | BTC seguindo tendência | Queda | 50% BTC + 50% ETH (tendência) | Queda | BTC segurar | Queda |
|---|---|---|---|---|---|---|
| Nunca visto out/20–set/23 | +167% | 58% | +304% | 51% | +140% | 77% |
| Tudo out/20–nov/26 | +496% | 58% | +621% | 51% | +606% | 77% |

**Misturas** (fração fixa em "BTC+ETH seguindo tendência", resto no bot), partindo de 100:

| Período | 0% (só bot) | 25% | 50% | 100% |
|---|---|---|---|---|
| Nunca visto out/20–set/23 | 104 (queda 8%) | 156 (16%) | 223 (29%) | 404 (51%) |
| Último ano nov/25–nov/26 | 98 (4%) | 97 (7%) | 96 (10%) | 94 (16%) |
| Tudo out/20–nov/26 | 117 (9%) | 204 (16%) | 332 (29%) | 721 (51%) |

Cuidado: os 6 anos começam perto de um fundo de ciclo (BTC ~10 mil dólares em out/2020),
o que favorece qualquer estratégia compradora. Seguir tendência ainda tem quedas grandes
(51–58%), porque não escapa de tombos rápidos dentro de uma tendência de alta (ex.: maio/2021).

## 9. Carteira adotada: 25% cofre de tendência + 75% bot (versão implementada)

Testada exatamente como roda (cofres separados, ordens reais simuladas, taxas):

| Reequilíbrio entre os cofres | Nunca visto out/20–set/23 | 6 anos | Último ano |
|---|---|---|---|
| Nunca | 185 (queda 38%) | 284 (queda 39%) | 98 (7%) |
| Quando o cofre zera | 198 (34%) | 267 (34%) | 98 (7%) |
| **Mensal (adotado)** | **165 (16%)** | **221 (17%)** | 97 (7%) |

Sem reequilíbrio o cofre cresce nas altas e passa de 25% para ~60% da carteira, e a queda
máxima vai a ~39% — risco que não foi o escolhido. Por ano (100 USDT, out/2020–nov/2026):
2020 +35% · 2021 +26% · 2022 0% · 2023 +4% · 2024 +12% · 2025 +10% · 2026 −3%.

## 10. Day trade e outros estilos (nov/2026)

**Day trade / tempos curtos — vantagem bruta (SEM taxas) vs com taxas**, mesma regra do bot:

| Entrada | Período | Sem taxas | Taxa BNB 0,075% | Taxa normal 0,1% |
|---|---|---|---|---|
| 15 min | nov/25–nov/26 | −1,8% | −4,9% | −3,7% |
| 1h | abr/24–nov/26 | −6,4% | −16,4% | −16,4% |
| 2h | abr/24–nov/26 | −4,5% | −6,8% | −7,5% |
| **4h** | abr/24–nov/26 | **+15,8%** | +12,7% | +12,6% |
| 6h | abr/24–nov/26 | +0,5% | −0,4% | −0,7% |

Mesmo sem taxa nenhuma, 15 min, 1h e 2h perdem: em tempos curtos o preço é quase só ruído.
Scalping (segundos/minutos, livro de ofertas) exige dados de profundidade, latência baixa e taxas
de criador de mercado — fora do alcance de uma conta comum. **Day trade não foi adotado.**

**Lateralização (reversão à média, 4h, só com o diário LATERAL)**: compra abaixo da banda de
Bollinger inferior (20, 2) com RSI < 30; vende na média de 20, stop 2 ATR, máx. 12 velas.
Parâmetros clássicos escolhidos antes, sem ajuste. Custo 0,3% ida e volta.

| Período | Ops | Acerto | Média/op | FL |
|---|---|---|---|---|
| Nunca visto out/20–set/23 | 95 | 44% | +0,39% | 1,14 |
| Treino set/23–nov/25 | 93 | 57% | +0,79% | 1,35 |
| Validação nov/25–nov/26 | 12 | 58% | +0,88% | 1,86 |

Robustez (81 variações de RSI, bandas, tempo e stop): positivas em 84% (treino) e 78%
(validação), mas só **36% no período nunca visto** (mediana −0,33%/op). Funciona no mercado
recente, não no de 2020–2023. Comprar a mesma "esticada" com o diário em BAIXA perdeu
(−1,03%/op no período nunca visto), como esperado.
**Decisão:** fica em **observação** (`bot/shadow.py`): o bot registra no diário o que teria
acontecido, sem operar. Depois de semanas de dados reais, `python -m bot aprender` mostra o resultado.

## Conclusões honestas

- A estratégia **ganha em mercado de alta e perde pouco em mercado de baixa**; ela não lucra
  com quedas (spot, só compra).
- A validação (9 operações) foi negativa. É uma amostra pequena num ano atípico de queda —
  **não prova** que a estratégia funciona daqui para frente.
- Próximo passo recomendado: rodar em `paper` por algumas semanas e comparar com o backtest
  antes de qualquer dinheiro real.
