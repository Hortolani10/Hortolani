"""Setups de EXPLORAÇÃO do bot aprendiz (só em paper).

Objetivo: operar quase todo dia para gerar dados. Cada setup é uma hipótese simples e
cada operação grava setup + padrões de gráfico no diário; com o tempo o `aprender` mostra
quais hipóteses funcionam de verdade. As boas podem ser promovidas para o bot principal
depois de testadas em 6 anos de histórico.

Todos compram (spot) com o mesmo stop do bot principal (abaixo do fundo recente,
entre 1 e 3 ATR) e a mesma saída (config do aprendiz: alvo em R e limite de candles).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .strategy import Signal

DESCRICAO = {
    "rompimento": "fechou acima da máxima de 20 candles com volume 1,5× a média",
    "reversao_rsi": "RSI saiu da sobrevenda (< 30) com candle de alta",
    "padrao_suporte": "engolfo de alta ou martelo perto do suporte",
    "pullback_livre": "pullback na EMA21 com gatilho, sem exigir tendência do diário nem BTC",
    "divergencia": "divergência de alta no RSI com candle de alta",
}


def _mask(df: pd.DataFrame, nome: str, cfg: dict) -> pd.Series:
    c, o = df["close"], df["open"]
    verde = c > o
    if nome == "rompimento":
        return df["pad_rompimento_20"] & (df["volume"] >= 1.5 * df["vol_ma"]) & verde
    if nome == "reversao_rsi":
        return (df["rsi"].shift(1) < 30) & (df["rsi"] > df["rsi"].shift(1)) & verde
    if nome == "padrao_suporte":
        return (df["pad_engolfo_alta"] | df["pad_martelo"]) & df["pad_perto_suporte"]
    if nome == "pullback_livre":
        pl = cfg["strategy"]["pullback_lookback"]
        tocou = (df["low"] <= df["ema_fast"] * 1.002).astype(float).rolling(pl).max() == 1
        return ((df["ema_fast"] > df["ema_mid"]) & tocou & (c > df["ema_fast"]) & verde
                & (c > df["high"].shift(1)))
    if nome == "divergencia":
        return df["pad_divergencia_alta"] & verde
    raise ValueError(f"setup desconhecido: {nome}")


def ativos(cfg: dict) -> list[str]:
    ex = cfg.get("exploracao") or {}
    if not ex.get("enabled"):
        return []
    return [s for s in ex.get("setups", list(DESCRICAO)) if s in DESCRICAO]


def mascaras(df: pd.DataFrame, cfg: dict) -> dict[str, np.ndarray]:
    """Setup -> vetor booleano (candle a candle). Vazio se a exploração estiver desligada."""
    out = {}
    for nome in ativos(cfg):
        m = _mask(df, nome, cfg).fillna(False).to_numpy(dtype=bool).copy()
        m[:60] = False                                   # aquecimento dos indicadores
        out[nome] = m
    return out


def stop_padrao(df: pd.DataFrame, i: int, cfg: dict) -> float:
    s, r = cfg["strategy"], cfg["risk"]
    a = float(df["atr"].iat[i])
    close = float(df["close"].iat[i])
    swing = float(df["low"].iloc[max(0, i - s["swing_lookback"] + 1): i + 1].min()) - 0.2 * a
    dist = min(max(close - swing, r["stop_min_atr"] * a), r["stop_max_atr"] * a)
    return close - dist


def sinal(df: pd.DataFrame, i: int, cfg: dict, masks: dict | None = None) -> tuple[Signal, str]:
    """Primeiro setup de exploração presente no candle `i` (ordem do config)."""
    masks = masks if masks is not None else mascaras(df, cfg)
    a = float(df["atr"].iat[i]) if i < len(df) else 0.0
    for nome, m in masks.items():
        if m[i] and a > 0:
            close = float(df["close"].iat[i])
            return (Signal(True, entry=close, stop=stop_padrao(df, i, cfg), target=0.0,
                           checks={nome: (True, DESCRICAO[nome])}), nome)
    return Signal(False, checks={"exploracao": (False, "nenhum setup de exploração")}), ""
