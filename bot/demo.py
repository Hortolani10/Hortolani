"""Dados sintéticos para demonstração e testes (NÃO são preços reais)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def synthetic(n: int, tf_ms: int, drift: float, seed: int = 1, start: float = 100.0,
              t0: int = 1_700_000_000_000) -> pd.DataFrame:
    """Passeio aleatório com tendência + ondas (gera pullbacks)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    rets = drift + 0.004 * np.sin(t / 9) + rng.normal(0, 0.006, n)
    close = start * np.exp(np.cumsum(rets))
    open_ = np.r_[start, close[:-1]]
    spread = np.abs(rng.normal(0, 0.004, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    vol = rng.uniform(50, 150, n) * (1 + 2 * (close > open_))
    ts = t0 + t * tf_ms
    return pd.DataFrame({"ts": ts, "open": open_, "high": high, "low": low, "close": close, "volume": vol})


def resample(df: pd.DataFrame, k: int) -> pd.DataFrame:
    """Agrupa k candles em 1 (ex.: 4 x 1h = 1 x 4h)."""
    g = df.groupby(df.index // k)
    return pd.DataFrame({"ts": g["ts"].first(), "open": g["open"].first(), "high": g["high"].max(),
                         "low": g["low"].min(), "close": g["close"].last(),
                         "volume": g["volume"].sum()}).reset_index(drop=True)


def regime_series(n: int, tf_ms: int, seed: int, start: float) -> pd.DataFrame:
    """Mercado que alterna alta, lateral e baixa — bom para ver o bot ficar de fora."""
    parts, price, t0 = [], start, 1_700_000_000_000
    for j, (m, drift) in enumerate([(0.35, 0.0009), (0.2, 0.0), (0.2, -0.0012), (0.25, 0.0010)]):
        k = int(n * m)
        df = synthetic(k, tf_ms, drift, seed + j, price, t0)
        parts.append(df)
        price, t0 = float(df["close"].iloc[-1]), int(df["ts"].iloc[-1]) + tf_ms
    return pd.concat(parts, ignore_index=True)
