"""Padrões de gráfico detectados em cada candle (só com dados até aquele candle, sem olhar o futuro).

Cada padrão vira uma coluna booleana `pad_<nome>` no DataFrame. Toda operação grava no diário
a lista de padrões presentes no candle do sinal, e o `aprender` mostra quais deram resultado.
"""
from __future__ import annotations

import pandas as pd

NOMES = {
    "engolfo_alta": "Engolfo de alta",
    "engolfo_baixa": "Engolfo de baixa",
    "martelo": "Martelo",
    "estrela_cadente": "Estrela cadente",
    "doji": "Doji (indecisão)",
    "tres_soldados": "Três soldados (3 altas seguidas)",
    "rompimento_20": "Rompimento da máxima de 20 candles",
    "perda_20": "Perda da mínima de 20 candles",
    "perto_suporte": "Perto do suporte (mínima de 50 candles)",
    "perto_resistencia": "Perto da resistência (máxima de 50 candles)",
    "fundo_duplo": "Fundo duplo",
    "divergencia_alta": "Divergência de alta no RSI",
    "volume_explosivo": "Volume explosivo (2× a média)",
    "squeeze": "Bandas apertadas (squeeze)",
    "acima_ema200": "Preço acima da EMA200",
    "rsi_sobrevenda": "RSI em sobrevenda (< 30)",
    "rsi_sobrecompra": "RSI em sobrecompra (> 70)",
}


def add_padroes(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta as colunas pad_* (precisa de open/high/low/close/volume, atr, rsi, vol_ma, ema_slow)."""
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]
    a = df["atr"]
    corpo = (c - o).abs()
    faixa = (h - l).replace(0, float("nan"))
    sombra_sup = h - pd.concat([o, c], axis=1).max(axis=1)
    sombra_inf = pd.concat([o, c], axis=1).min(axis=1) - l
    verde, vermelho = c > o, c < o
    po, pc = o.shift(1), c.shift(1)

    p = {}
    p["engolfo_alta"] = verde & (pc < po) & (o <= pc) & (c >= po)
    p["engolfo_baixa"] = vermelho & (pc > po) & (o >= pc) & (c <= po)
    p["martelo"] = (sombra_inf >= 2 * corpo) & (sombra_sup <= corpo) & (corpo > 0)
    p["estrela_cadente"] = (sombra_sup >= 2 * corpo) & (sombra_inf <= corpo) & (corpo > 0)
    p["doji"] = corpo <= 0.1 * faixa
    p["tres_soldados"] = verde & verde.shift(1, fill_value=False) & verde.shift(2, fill_value=False) & (c > pc) & (pc > c.shift(2))
    max20, min20 = h.shift(1).rolling(20).max(), l.shift(1).rolling(20).min()
    p["rompimento_20"] = c > max20
    p["perda_20"] = c < min20
    min50, max50 = l.shift(1).rolling(50).min(), h.shift(1).rolling(50).max()
    p["perto_suporte"] = (l - min50) <= 0.5 * a
    p["perto_resistencia"] = (max50 - c) <= 0.5 * a
    fundo_a = l.shift(6).rolling(25).min()                  # fundo entre 30 e 6 candles atrás
    fundo_b = l.rolling(5).min()                            # fundo recente
    p["fundo_duplo"] = ((fundo_a - fundo_b).abs() <= 0.5 * a) & (c > fundo_b + 0.5 * a)
    rsi = df["rsi"]
    p["divergencia_alta"] = (l <= min20 + 0.25 * a) & (rsi > rsi.shift(1).rolling(20).min() + 5)
    p["volume_explosivo"] = v >= 2 * df["vol_ma"]
    std = c.rolling(20).std()
    largura = 4 * std / c.rolling(20).mean()
    p["squeeze"] = largura <= largura.rolling(100).quantile(0.2)
    p["acima_ema200"] = c > df["ema_slow"]
    p["rsi_sobrevenda"] = rsi < 30
    p["rsi_sobrecompra"] = rsi > 70

    out = df.copy()
    for k, s in p.items():
        out[f"pad_{k}"] = s.fillna(False).astype(bool)
    return out


def presentes(df: pd.DataFrame, i: int) -> list[str]:
    """Nomes dos padrões presentes no candle `i`."""
    row = df.iloc[i]
    return [k for k in NOMES if bool(row.get(f"pad_{k}", False))]
