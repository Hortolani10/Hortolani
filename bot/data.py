"""Download de candles e alinhamento entre tempos gráficos (sem look-ahead)."""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from .indicators import add_all
from .strategy import trend_series

COLS = ["ts", "open", "high", "low", "close", "volume"]
_UNITS = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}


def tf_ms(tf: str) -> int:
    return int(tf[:-1]) * _UNITS[tf[-1]]


def to_df(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLS)
    df[COLS[1:]] = df[COLS[1:]].astype(float)
    df["ts"] = df["ts"].astype("int64")
    return df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def drop_open_candle(df: pd.DataFrame, tf: str, now_ms: int | None = None) -> pd.DataFrame:
    """Remove o último candle se ele ainda não fechou. Decisões só em candle fechado."""
    now_ms = now_ms or int(time.time() * 1000)
    return df[df["ts"] + tf_ms(tf) <= now_ms].reset_index(drop=True)


def fetch_history(exchange, symbol: str, tf: str, since_ms: int, until_ms: int | None = None) -> pd.DataFrame:
    """Baixa histórico paginado via ccxt (endpoint público, não precisa de chave)."""
    until_ms = until_ms or int(time.time() * 1000)
    rows, cursor = [], since_ms
    while cursor < until_ms:
        batch = exchange.fetch_ohlcv(symbol, tf, since=cursor, limit=1000)
        if not batch:
            break
        rows += batch
        cursor = batch[-1][0] + tf_ms(tf)
        time.sleep(exchange.rateLimit / 1000)
    return drop_open_candle(to_df(rows), tf)


def cached_history(exchange, symbol: str, tf: str, days: int, cache_dir: str = "data") -> pd.DataFrame:
    Path(cache_dir).mkdir(exist_ok=True)
    path = Path(cache_dir) / f"{symbol.replace('/', '')}_{tf}_{days}d.csv"
    if path.exists() and time.time() - path.stat().st_mtime < 6 * 3600:
        return pd.read_csv(path)
    since = int(time.time() * 1000) - days * 86_400_000
    df = fetch_history(exchange, symbol, tf, since)
    df.to_csv(path, index=False)
    return df


def prepare(entry_df: pd.DataFrame, trend_df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Calcula indicadores nos dois TFs e anexa a tendência do TF maior a cada
    candle de entrada usando APENAS candles do TF maior já fechados."""
    tf_e, tf_t = cfg["timeframes"]["entry"], cfg["timeframes"]["trend"]
    e = add_all(entry_df, cfg)
    t = add_all(trend_df, cfg)
    t = pd.DataFrame({"close_ts": t["ts"] + tf_ms(tf_t), "trend": trend_series(t)})
    e["close_ts"] = e["ts"] + tf_ms(tf_e)
    merged = pd.merge_asof(
        e.sort_values("close_ts"), t.sort_values("close_ts"), on="close_ts", direction="backward"
    )
    merged["trend"] = merged["trend"].fillna("LATERAL")
    return merged.reset_index(drop=True)
