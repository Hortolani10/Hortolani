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

## 11. Correção: valor mínimo de ordem e mais moedas (nov/2026)

**Erro corrigido:** o backtest descartava ordens abaixo de **10 USDT**, mas o mínimo real da Binance
é **5 USDT** (DOGE: 1). Com carteira pequena (100 USDT, 75 no bot, defesa reduzindo o risco pela
metade), muitas ordens reais eram puladas no teste. Agora é `fees.min_order: 5` no config.
Números corrigidos (out/2020–nov/2026, 100 USDT):

| | Antes (mínimo 10) | **Corrigido (mínimo 5)** |
|---|---|---|
| Bot sozinho, 8 moedas | 117 (queda 9%) | **139 (queda 12%)** |
| Carteira bot + cofre | ~213–221 (queda 17%) | **~226–227 (queda 19%)** |
| Por ano (carteira) | — | 2020 +34% · 2021 +32% · 2022 0% · 2023 +5% · 2024 +14% · 2025 +11% · 2026 −3% |

As escolhas anteriores (defesa automática, máx. 2 posições) foram feitas com o mínimo errado e
não foram refeitas, para não ajustar de novo em cima dos mesmos dados.

**Mais moedas:** 8 atuais vs 16 (+ DOGE, AVAX, DOT, TRX, ATOM, UNI, BCH, XLM), escolhidas por
critério fixo (grandes, líquidas, na Binance desde 2020), mesmas regras:

| Período | Bot 8 moedas | Bot 16 moedas | Carteira 8 | Carteira 16 |
|---|---|---|---|---|
| Nunca visto out/20–set/23 | **+8,5%** (FL 1,26) | +6,9% (FL 1,17) | 163 (queda 18%) | 161 (queda 20%) |
| Treino set/23–nov/25 | +35,5% (FL 2,65) | +43,4% (FL 2,28) | 141 | 159 |
| Último ano | −1,8% | −1,5% | 97 | 97 |
| Tudo out/20–nov/26 | +39,0% (FL 1,70, queda 11,6%) | +41,6% (FL 1,53, queda 12,9%) | 226 (19%) | 235 (21%) |

Viés de sobrevivência: moedas que quebraram (LUNA, FTT) saíram da Binance e não entram no teste,
o que favorece qualquer lista "de hoje". **Decisão: manter 8 moedas** — ganho pequeno, pior no
período nunca visto, operações de qualidade menor e quedas maiores.

## 12. Mais operações: 24 combinações (nov/2026)

Pedido: mais entradas por mês, aceitando mais perdas. Regra fixada antes: entre as versões com
≥ 5 ops/mês no treino e queda ≤ 20%, vence a de maior retorno no treino. Bot sozinho, 100 USDT:

| Versão (bot sozinho) | Ops/mês (6 anos) | Acerto | 6 anos | Queda | Nunca visto |
|---|---|---|---|---|---|
| Atual: 8 moedas, 2 posições | 2,3 | 37% | +39,0% | 12% | +8,5% |
| Escolhida pela regra: 16 moedas, 4 posições | 3,7 | 39% | +41,2% | 12% | +9,5% |
| 8 moedas + lateralização, 2 posições | 4,2 | 43% | +32,7% | 15% | +10,3% |
| 16 moedas + lateralização, 4 posições | 7,4 | 44% | +17,3% | 17% | +8,5% |
| Alvo fixo 1,5R (maior acerto) | 2,1–7,5 | 47–49% | +7% a +34% | 7–17% | +2% a +10% |

Na **carteira completa** (bot 75% + cofre 25%), porém, a escolhida pela regra piorou
(6 anos 207 vs 226; nunca visto 152 vs 163). A opção mais equilibrada foi
**8 moedas + lateralização** (carteira, 100 USDT):

| | Atual | 8 moedas + lateralização |
|---|---|---|
| Operações do bot por mês (6 anos) | ~2,1 | **~4,0** |
| Último ano (mercado em queda) | 8 ops, 97,1 | **22 ops (acerto 50%), 98,2** |
| Nunca visto out/20–set/23 | 163,4 (queda 18%) | 164,5 (queda 22%) |
| 6 anos | 225,7 (queda 19%) | 219,5 (queda 22%) |

**Decisão:** ligada (`lateral.enabled: true`) para ganhar operações e dados reais no paper,
sabendo que em 6 anos rende um pouco menos e a queda máxima sobe ~3 pontos. Lembrete da
seção 10: a lateralização não foi robusta a mudanças de parâmetros em 2020–2023.
Mais operações não aumentaram o lucro em nenhuma versão: o ganho é atividade e dados, não retorno.

## 13. Inteligência artificial (machine learning) para filtrar sinais (nov/2026)

Modelo treinado com o "retrato do mercado" de cada entrada (ADX, volatilidade, RSI, volume,
distância da média, hora, dia, sessão, estratégia) para prever se a operação daria lucro.
311 operações em 6 anos; walk-forward (treina só com o passado, testa no bloco seguinte, 5 blocos).

| | Operações | Acerto | Soma de R |
|---|---|---|---|
| Sem modelo | 187 | 45% | **+22,2R** |
| Com modelo (mediana de 69 variações: gradient boosting, random forest, regressão logística, cortes 30/50/70%) | 106 | **50%** | +14,8R |

O modelo **aumenta a taxa de acerto** (45% → ~50%) **mas corta quase metade das operações e
reduz o lucro total**: só 16% das variações superaram o bot sem modelo. Com poucas centenas de
operações, um modelo aprende ruído. **Não adotado.** Pode ser revisto quando o diário tiver
centenas de operações reais.

## 14. Opcionais testados: memecoins, operação vendida e termômetro do mercado (nov/2026)

Ideias tiradas da varredura de skills no GitHub (Binance Skills Hub, agiprolabs, tradermonty,
crypto-trader-skill e outras). Script reproduzível: `python -m pesquisa.opcionais`.
Dados reais da Binance, fev/2020–nov/2026, 4h/1d, mesmas taxas do bot.

| Variante (só o bot, 100 USDT) | Ops/mês | Acerto | 6 anos | Queda máx. | 2022 | Últimos 12 meses |
|---|---|---|---|---|---|---|
| Bot sem termômetro | 4,0 | 42% | 124 | 16,2% | −0,3% | −0,4% |
| **Bot com termômetro (adotado)** | 4,0 | 42% | **127** | **14,4%** | −0,1% | −0,0% |
| Só memecoins (DOGE, SHIB, PEPE, FLOKI, BONK, WIF) | 1,5 | 41% | 120 | 12,3% | −1,4% | −0,7% |
| 8 moedas + memecoins | 4,7 | 42% | 126 | 14,5% | −2,0% | −2,2% |
| Só vendido (short em futuros, sem alavancagem) | 1,5 | 33% | 92 | 17,2% | −11,1% | +2,7% |
| Compra 75% + vendido 25% | 5,6 | 39% | 118 | 13,3% | −2,9% | +0,7% |
| "Cofre vendido" (short no BTC com diário em baixa) | — | 33% | 85 | 42% | +60% | — |

Carteira completa (bot 75% + cofre 25%): 214 → **218** com o termômetro, queda 22,1% → **20,9%**.

**Termômetro (adotado, `termometro.enabled`).** Nota 0–100: 50% amplitude (% das moedas com
diário em alta), 30% BTC em alta no diário, 20% BTC acima da EMA50 do 4h. Abaixo de 40 o bot
arrisca metade por operação; não bloqueia entradas. Melhorou um pouco em todos os períodos e
não mexe na quantidade de operações. Aparece no painel e no `/status` / `/radar` do Telegram.

**Rejeitados:**
- **Operação vendida (short):** perdeu em 6 anos e **até em 2022**, o ano de baixa
  (−11%, mesmo sem cobrar funding: −10%). Os repiques em tendência de baixa são violentos e
  batem nos stops. Só ganhou nos últimos 12 meses (+2,7%), o que é pouco e recente demais.
  Exigiria também chave de futuros, o que aumenta o risco da conta.
- **"Cofre vendido":** +60% em 2022, mas 85 em 6 anos com queda de 42%: depende de acertar um ano.
- **Memecoins:** sozinhas rendem menos que as 8 moedas, e juntas pioraram 2022 e os últimos 12
  meses. Ainda têm risco de deslistagem e golpes. Ficam de fora.
- **Day trade (1h/15m):** já testado na seção 10, perde mesmo sem taxas.
- **Solana/DeFi on-chain:** fora da Binance spot; exige carteira com chave privada. Não se aplica.

**Revisão de segurança das skills (código lido, nada executado):**
- Binance Skills Hub (crypto-market-rank, query-token-info, query-token-audit, academy): só leitura,
  sem chave, falam com web3.binance.com / www.binance.com (o query-token-info também usa
  dquery.sintral.io para candles). Sem eval, sem ofuscação.
- Skill `binance` (binance-cli): opera spot/futuros com a sua chave e instala um programa por script
  (`curl … | sh`). Não usar junto com o bot.
- agiprolabs (walk-forward, regime, volatilidade, saídas, métricas, correlação): só cálculo local
  (algumas baixam preços da Birdeye/CoinGecko). Limpas. O pacote também tem skills que assinam
  transações Solana com chave privada (dex-execution, raptor-dex): não usar.
- daviddme/claude-skills: **envia API key e secret da corretora para um servidor de terceiros**
  (fastcloud.daviddtech.com/encryptor). Não usar.
- roman-rr/trading-skills: depende de serviço pago (signals.x70.ai) com sua chave. Dispensável.
- crypto-trader-skill: futuros alavancados e day trade (Bybit/Hyperliquid/Binance). Não usar.

## 15. Bot aprendiz: 7 setups × 4 tempos gráficos e 17 padrões de gráfico (nov/2026)

Objetivo: **processo antes do resultado**. Os aprendizes operam quase todo dia em paper,
erram de propósito e gravam setup, padrões e tempo gráfico de cada operação no diário.
Backtest com dados reais da Binance, 16 moedas, 0,5% de risco, alvo 2R ou saída após 18 candles,
taxas e slippage incluídos. Script: `python -m pesquisa.aprendiz`.

| Aprendiz | Histórico | Operações/dia | Acerto | Média por operação |
|---|---|---|---|---|
| 4h (tendência 1d) | 6,1 anos | 2,8 | 40% | −0,08R |
| 2h (tendência 1d) | 2,6 anos | 5,2 | 38% | −0,17R |
| 1h (tendência 4h) | 3,1 anos | 5,1 | 38% | −0,21R |
| 15 min (tendência 1h) | 1,1 ano | 11,0 | 30% | −0,52R |

**Setups (média por operação em R):**

| Setup | 4h | 2h | 1h | 15 min |
|---|---|---|---|---|
| Rompimento (máxima de 20 + volume) | **+0,02** | −0,01 | −0,08 | −0,20 |
| Tendência (regras do bot principal) | **+0,10** | −0,01 | −0,20 | −0,62 |
| Lateral (banda inferior) | 0,00 | −0,07 | −0,15 | −0,53 |
| Pullback livre (sem filtro de tendência) | −0,03 | −0,12 | −0,15 | −0,48 |
| Reversão do RSI (sai da sobrevenda) | −0,10 | −0,31 | −0,36 | −0,64 |
| Divergência de alta no RSI | −0,15 | −0,16 | −0,24 | −0,60 |
| Engolfo/martelo no suporte | −0,23 | −0,31 | −0,37 | −0,69 |

**Padrões de gráfico (os mesmos nos 4 tempos gráficos):**
- **Funcionam melhor = força:** RSI acima de 70, três soldados, perto da resistência,
  rompimento da máxima de 20. No 4h: +0,12R, +0,08R, +0,05R e +0,02R.
- **Funcionam pior = fraqueza:** martelo, doji, fundo duplo, perto do suporte, squeeze,
  sobrevenda e divergência de alta (de −0,10R a −0,25R no 4h, pior nos gráficos menores).

**O que isso ensina:**
1. Em cripto, **comprar força** (rompimento, momentum) é melhor que **comprar fraqueza**
   (fundo, suporte, sobrevenda). Os padrões "clássicos" de reversão (martelo, fundo duplo,
   divergência) perderam em todos os tempos gráficos.
2. **Quanto menor o gráfico, pior:** no 15 min a taxa + slippage (~0,15% por ida e volta) é
   grande perto do stop, e o acerto cai para 30%.
3. Só o 4h com setups de força ficou perto do zero ou positivo. Bate com as seções 2, 7 e 10.

**Como os aprendizes rodam:** 4 contêineres em paper (4h, 2h, 1h, 15 min), saldo fictício de
10.000 com risco fixo de 5 USDT por operação (o saldo encolher não os faz parar). O backtest é
o ponto de partida; o diário real vai confirmar ou derrubar estes números. Candidato a testar
no bot principal quando houver 100+ operações reais: rompimento no 4h com RSI > 62.
Relatório da prática: `python -m bot diario`.

## Conclusões honestas

- A estratégia **ganha em mercado de alta e perde pouco em mercado de baixa**; ela não lucra
  com quedas (spot, só compra).
- A validação (9 operações) foi negativa. É uma amostra pequena num ano atípico de queda —
  **não prova** que a estratégia funciona daqui para frente.
- Próximo passo recomendado: rodar em `paper` por algumas semanas e comparar com o backtest
  antes de qualquer dinheiro real.
