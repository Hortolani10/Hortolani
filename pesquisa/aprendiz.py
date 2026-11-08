"""Backtest do BOT APRENDIZ em cada tempo gráfico: frequência de operações e o que cada
setup e cada padrão de gráfico rendeu no histórico real da Binance.

Uso:  python -m pesquisa.aprendiz            (todos)    ·    python -m pesquisa.aprendiz 1h
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from bot.__main__ import load_config
from bot.backtest import run
from bot.data import apply_btc_filter, fetch_history, prepare, tf_ms
from bot.exchange import make_ccxt
from bot.learn import relatorio, trades_para_linhas

CONFIGS = {"4h": ("config_aprendiz.yaml", 2450), "2h": ("config_aprendiz_2h.yaml", 1150),
           "1h": ("config_aprendiz_1h.yaml", 1150), "15m": ("config_aprendiz_15m.yaml", 400)}
_EX = None


def load(cfg, sym, tf, days):
    global _EX
    p = Path("data") / f"{sym.replace('/', '')}_{tf}_{days}d.csv"
    if p.exists() and time.time() - p.stat().st_mtime < 4 * 3600:
        return pd.read_csv(p)
    _EX = _EX or make_ccxt(cfg, with_keys=False)
    df = fetch_history(_EX, sym, tf, int(time.time() * 1000) - days * 86_400_000)
    p.parent.mkdir(exist_ok=True)
    df.to_csv(p, index=False)
    return df


def roda(nome: str) -> str:
    path, days = CONFIGS[nome]
    cfg = load_config(path)
    tf_e, tf_t = cfg["timeframes"]["entry"], cfg["timeframes"]["trend"]
    data = {}
    for s in cfg["symbols"]:
        e, t = load(cfg, s, tf_e, days), load(cfg, s, tf_t, days)
        if len(e) > 300 and len(t) > 210:
            data[s] = prepare(e, t, cfg)
    data = apply_btc_filter(data, cfg, data.get("BTC/USDT"))
    start = int(data["BTC/USDT"]["close_ts"].iloc[0]) + 210 * tf_ms(tf_t)
    r = run(data, cfg, 1000.0, start_ts=start, close_at_end=True)
    s = r.summary()
    dias = (r.equity_ts[-1] - r.equity_ts[0]) / 86_400_000
    df = pd.json_normalize(trades_para_linhas(r.trades, f"aprendiz-{nome}"))
    df.columns = [c.replace("features.", "") for c in df.columns]
    cab = (f"## Aprendiz {nome} (tendência {tf_t}) · {dias / 365:.1f} anos · {len(data)} moedas\n"
           f"{s['operacoes']} operações = {s['operacoes'] / dias:.1f} por dia · acerto {s['taxa_acerto']:.0%} · "
           f"média {s['media_R']:+.2f}R · retorno {s['retorno_total']:+.1%} · queda máx. {s['drawdown_max']:.1%}\n")
    return cab + relatorio(df, min_ops=30)


if __name__ == "__main__":
    for n in (sys.argv[1:] or list(CONFIGS)):
        print(roda(n), "\n", flush=True)
