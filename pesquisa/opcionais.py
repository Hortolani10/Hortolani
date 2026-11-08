"""Experimentos OPCIONAIS (nov/2026): memecoins, operação vendida (short) e
termômetro de regime. Nada aqui muda o bot ao vivo; só mede com dados reais.

Uso:  python -m pesquisa.opcionais          (da pasta do projeto)
"""
from __future__ import annotations

import copy
import time
from pathlib import Path

import numpy as np
import pandas as pd

import bot.backtest as bt
from bot.__main__ import load_config
from bot.data import apply_btc_filter, fetch_history, prepare
from bot.exchange import make_ccxt
from bot import regime
from bot.sleeve import portfolio_backtest
from bot.strategy import BAIXA

DAYS = 2450
BASE = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "LTC/USDT", "LINK/USDT"]
MEMES = ["DOGE/USDT", "SHIB/USDT", "PEPE/USDT", "FLOKI/USDT", "BONK/USDT", "WIF/USDT"]
_EX = None


def load(sym: str, tf: str) -> pd.DataFrame:
    """Candles da Binance (cache em data/, renovado a cada 24 h)."""
    global _EX
    p = Path("data") / f"{sym.replace('/', '')}_{tf}_{DAYS}d.csv"
    if p.exists() and time.time() - p.stat().st_mtime < 24 * 3600:
        return pd.read_csv(p)
    _EX = _EX or make_ccxt(CFG, with_keys=False)
    df = fetch_history(_EX, sym, tf, int(time.time() * 1000) - DAYS * 86_400_000)
    p.parent.mkdir(exist_ok=True)
    df.to_csv(p, index=False)
    return df


def dataset(cfg: dict, syms: list[str]) -> dict[str, pd.DataFrame]:
    tf_e, tf_t = cfg["timeframes"]["entry"], cfg["timeframes"]["trend"]
    btc = prepare(load("BTC/USDT", tf_e), load("BTC/USDT", tf_t), cfg)
    data = {s: (btc if s == "BTC/USDT" else prepare(load(s, tf_e), load(s, tf_t), cfg)) for s in syms}
    return apply_btc_filter(data, cfg, btc)


def stats(eq: pd.Series, n_ops: int, wins: int) -> dict:
    eq = eq.dropna()
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    return {"retorno": eq.iloc[-1] / eq.iloc[0] - 1, "queda_max": float((1 - eq / eq.cummax()).max()),
            "ops": n_ops, "ops_mes": n_ops / (years * 12), "acerto": wins / n_ops if n_ops else 0.0,
            "final_100": 100 * eq.iloc[-1] / eq.iloc[0]}


def daily(eq_vals, eq_ts) -> pd.Series:
    return pd.Series(eq_vals, index=pd.to_datetime(eq_ts, unit="ms", utc=True)).resample("1D").last().ffill()


def run_long(data, cfg, start, end=None):
    r = bt.run(data, cfg, 1000.0, start_ts=start, end_ts=end, close_at_end=True)
    return daily(r.equity_curve, r.equity_ts), r.trades


# ---------------------------------------------------------------- short (vendido)
def short_mask(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Espelho exato das regras de compra: tendência de BAIXA, repique até a EMA21
    que falhou, candle de baixa rompendo a mínima anterior, RSI 32-55, MACD < 0 caindo."""
    s = cfg["strategy"]
    pl = s["pullback_lookback"]
    touched = (df["high"] >= df["ema_fast"] * 0.998).astype(float).rolling(pl).max() == 1
    held = (df["close"] < df["ema_mid"]).astype(float).rolling(pl).min() == 1
    m = ((df["trend"] == BAIXA)
         & (df["ema_fast"] < df["ema_mid"]) & (df["ema_mid"] < df["ema_slow"])
         & touched & held
         & (df["close"] < df["ema_fast"]) & (df["close"] < df["open"]) & (df["close"] < df["low"].shift(1))
         & (df["rsi"] >= 100 - s["rsi_max"]) & (df["rsi"] <= 100 - s["rsi_min"])
         & (df["macd_hist"] < df["macd_hist"].shift(1)) & (df["macd"] < 0)
         & (df["adx"] >= s["adx_min"])
         & (df["volume"] >= df["vol_ma"] * s["volume_factor"])
         & ((df["ema_fast"] - df["close"]) <= s["max_extension_atr"] * df["atr"]))
    if s.get("btc_filter") and "btc_trend" in df.columns:
        m &= df["btc_trend"] == BAIXA
    m.iloc[: max(s["ema_slow"], s["resistance_lookback"]) + 5] = False
    return m.fillna(False)


def run_short(data, cfg, start, end=None, fee=0.0005, slip=0.0005, funding_8h=0.0001, max_pos=2):
    """Futuros USDT-M SEM alavancagem extra (margem = valor da posição).
    Taxa de futuros 0,05% + slippage 0,05% + funding de 0,01%/8 h COBRADO (pessimista:
    na prática o funding costuma ser pago AOS vendidos)."""
    r, s = cfg["risk"], cfg["strategy"]
    cash, pos, pend, trades = 1000.0, {}, {}, []
    masks = {k: short_mask(df, cfg).to_numpy() for k, df in data.items()}
    idx = {k: dict(zip(df["close_ts"].astype(int), range(len(df)))) for k, df in data.items()}
    tl = sorted({int(t) for df in data.values() for t in df["close_ts"]})
    tl = [t for t in tl if t >= start and (end is None or t < end)]
    last, eq_v, eq_t = {}, [], []
    bar_h = 4

    def equity():
        return cash + sum(p["margin"] + p["qty"] * (p["entry"] - last.get(k, p["entry"])) for k, p in pos.items())

    for ts in tl:
        for k, df in data.items():
            i = idx[k].get(ts)
            if i is None:
                continue
            o, h, l, c, a = (float(df[x].iat[i]) for x in ("open", "high", "low", "close", "atr"))
            if k in pend:                                   # entra vendido na abertura
                stop = pend.pop(k)
                px = o * (1 - slip)
                if stop > px:
                    eqn = equity()
                    per = (stop - px) + px * (2 * fee + slip)
                    qty = min(eqn * r["risk_per_trade"] / per, eqn * r["max_position_pct"] / px)
                    margin = qty * px
                    if qty > 0 and margin + margin * fee <= cash and margin >= 5:
                        cash -= margin + margin * fee
                        pos[k] = {"qty": qty, "entry": px, "stop": stop, "low": px, "margin": margin,
                                  "risk": (stop - px) * qty, "fees": margin * fee}
            if k in pos:
                p = pos[k]
                cash -= p["qty"] * c * funding_8h * bar_h / 8
                exit_px = None
                if h >= p["stop"]:
                    exit_px = max(o, p["stop"]) * (1 + slip)
                else:
                    p["low"] = min(p["low"], l)
                    p["stop"] = min(p["stop"], p["low"] + r["trailing_atr"] * a)
                if exit_px is not None:
                    pnl = p["qty"] * (p["entry"] - exit_px) - p["qty"] * exit_px * fee
                    cash += p["margin"] + pnl
                    trades.append({"sym": k, "pnl": pnl - p["fees"], "R": (pnl - p["fees"]) / p["risk"]})
                    del pos[k]
            last[k] = c
            if k not in pos and k not in pend and len(pos) + len(pend) < max_pos and masks[k][i]:
                sw = float(df["high"].iloc[i - s["swing_lookback"] + 1: i + 1].max()) + 0.2 * a
                dist = min(max(sw - c, r["stop_min_atr"] * a), r["stop_max_atr"] * a)
                pend[k] = c + dist
        eq_v.append(equity())
        eq_t.append(ts)
    for k, p in list(pos.items()):                          # fecha no fim do período
        px = last[k] * (1 + slip)
        pnl = p["qty"] * (p["entry"] - px) - p["qty"] * px * fee
        cash += p["margin"] + pnl
        trades.append({"sym": k, "pnl": pnl - p["fees"], "R": (pnl - p["fees"]) / p["risk"]})
    if eq_v:
        eq_v[-1] = cash
    return daily(eq_v, eq_t), trades


def blend(parts: list[tuple[pd.Series, float]]) -> pd.Series:
    """Carteira com várias partes, reequilibradas todo mês (como o cofre)."""
    idx = parts[0][0].index
    for s, _ in parts[1:]:
        idx = idx.intersection(s.index)
    rets = [s[idx].pct_change().fillna(0) for s, _ in parts]
    vals = [w for _, w in parts]
    out, prev = [], None
    for j, d in enumerate(idx):
        vals = [v * (1 + r.iat[j]) for v, r in zip(vals, rets)]
        if prev is not None and d.month != prev:
            tot = sum(vals)
            vals = [tot * w for _, w in parts]
        prev = d.month
        out.append(sum(vals))
    return pd.Series(out, index=idx)


# ---------------------------------------------------------------- execução
def fmt(nome, st):
    return (f"| {nome} | {st['ops']} | {st['ops_mes']:.1f} | {st['acerto']:.0%} | {st['retorno']:+.1%} | "
            f"{st['queda_max']:.1%} | {st['final_100']:.0f} |")


if __name__ == "__main__":
    CFG = load_config("config.yaml")
    globals()["CFG"] = CFG
    cfg = copy.deepcopy(CFG)
    base = dataset(cfg, BASE)
    memes = dataset(cfg, ["BTC/USDT"] + MEMES)
    memes_only = {k: v for k, v in memes.items() if k != "BTC/USDT"}
    start = int(base["BTC/USDT"]["close_ts"].iloc[260])           # após aquecimento da EMA200 diária
    periods = {"6 anos": (start, None),
               "2022 (baixa)": (int(pd.Timestamp("2022-01-01", tz="UTC").value // 1e6), int(pd.Timestamp("2023-01-01", tz="UTC").value // 1e6)),
               "últimos 12 meses": (int(pd.Timestamp.now(tz="UTC").value // 1e6) - 365 * 86_400_000, None)}
    hdr = "| Variante | Ops | Ops/mês | Acerto | Retorno | Queda máx. | 100 vira |\n|---|---|---|---|---|---|---|"
    for pname, (s0, e0) in periods.items():
        s0 = max(s0, start)
        print(f"\n### {pname}\n{hdr}")
        eqL, trL = run_long(base, cfg, s0, e0)
        print(fmt("Bot atual (8 moedas, compra)", stats(eqL, len(trL), sum(t.pnl > 0 for t in trL))))
        eqM, trM = run_long(memes_only, cfg, s0, e0)
        print(fmt("Só memecoins (6)", stats(eqM, len(trM), sum(t.pnl > 0 for t in trM))))
        eqB, trB = run_long({**base, **memes_only}, cfg, s0, e0)
        print(fmt("8 moedas + memecoins", stats(eqB, len(trB), sum(t.pnl > 0 for t in trB))))
        eqS, trS = run_short(base, cfg, s0, e0)
        print(fmt("Só vendido (short, 8 moedas)", stats(eqS, len(trS), sum(t["pnl"] > 0 for t in trS))))
        for w in (0.25, 0.5):
            eqC = blend([(eqL, 1 - w), (eqS, w)])
            print(fmt(f"Compra {1-w:.0%} + vendido {w:.0%}", stats(eqC, len(trL) + len(trS), sum(t.pnl > 0 for t in trL) + sum(t["pnl"] > 0 for t in trS))))
        for on in (False, True):
            c2 = copy.deepcopy(cfg)
            c2["termometro"] = {"enabled": on, "limite": 40, "fator": 0.5}
            eqR, trR = run_long(base, c2, s0, e0)
            print(fmt("Termômetro " + ("LIGADO (risco ½ se nota < 40)" if on else "desligado"), stats(eqR, len(trR), sum(t.pnl > 0 for t in trR))))
        for on in (False, True):
            c2 = copy.deepcopy(cfg)
            c2["termometro"] = {"enabled": on, "limite": 40, "fator": 0.5}
            dd = {k: load(k, "1d") for k in c2["trend_sleeve"]["symbols"]}
            pr = portfolio_backtest(base, dd, c2, 1000.0, s0, e0)
            print(fmt("Carteira completa (bot 75% + cofre 25%), termômetro " + ("ligado" if on else "desligado"),
                      stats(pr["equity"], len(pr["bot"].trades), sum(t.pnl > 0 for t in pr["bot"].trades))))
    sc = regime.serie(base)
    print(f"\nTermômetro agora: {sc.iloc[-1]:.0f}/100 (em {pd.Timestamp(int(sc.index[-1]), unit='ms', tz='UTC'):%d/%m/%Y %H:%M} UTC)")
