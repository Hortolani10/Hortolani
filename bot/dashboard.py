"""Gera um painel HTML (arquivo único) com gráfico, sinais, stop, capital e checklist.

    python -m bot dashboard --days 365          # dados reais da Binance
    python -m bot dashboard --demo              # dados simulados (sem internet)
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .backtest import Result
from .strategy import entry_signal

TEMPLATE = Path(__file__).with_name("dashboard_template.html")
TREND_CODE = {"ALTA": 1, "LATERAL": 0, "BAIXA": -1}


def _r(x, nd=6):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return float(f"{float(x):.{nd}g}")


def _series(df: pd.DataFrame, col: str) -> list:
    return [[int(t) // 1000, _r(v)] for t, v in zip(df["ts"], df[col]) if not pd.isna(v)]


def symbol_summary(trades) -> dict:
    n = len(trades)
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [-t.pnl for t in trades if t.pnl <= 0]
    return {
        "operacoes": n,
        "taxa_acerto": _r(len(wins) / n, 4) if n else None,
        "fator_lucro": _r(sum(wins) / sum(losses), 4) if losses and sum(losses) > 0 else None,
        "media_R": _r(sum(t.r_multiple for t in trades) / n, 4) if n else None,
        "pnl": _r(sum(t.pnl for t in trades), 4),
        "melhor_R": _r(max(t.r_multiple for t in trades), 3) if n else None,
        "pior_R": _r(min(t.r_multiple for t in trades), 3) if n else None,
    }


def build_payload(data: dict[str, pd.DataFrame], res: Result, cfg: dict, simulated: bool) -> dict:
    symbols = {}
    for sym, df in data.items():
        i = len(df) - 1
        sig = entry_signal(df, i, df["trend"].iloc[i], cfg)
        r = cfg["risk"]
        plan = None
        if sig.ok:
            risk = sig.entry - sig.stop
            plan = {"entrada": _r(sig.entry), "stop": _r(sig.stop),
                    "parcial": _r(sig.entry + r["take_partial_r"] * risk) if r.get("exit_mode", "parcial") == "parcial" else None,
                    "alvo": _r(sig.target), "rr": _r(sig.reward_risk, 3)}
        symbols[sym] = {
            "candles": [[int(t) // 1000, _r(o), _r(h), _r(l), _r(c), _r(v, 4)]
                        for t, o, h, l, c, v in df[["ts", "open", "high", "low", "close", "volume"]].itertuples(index=False)],
            "ema21": _series(df, "ema_fast"),
            "ema50": _series(df, "ema_mid"),
            "ema200": _series(df, "ema_slow"),
            "rsi": _series(df, "rsi"),
            "trend": [TREND_CODE.get(x, 0) for x in df["trend"]],
            "stop": [[t // 1000, _r(s)] for t, s in res.stop_path.get(sym, [])],
            "events": [{**e, "ts": e["ts"] // 1000, "price": _r(e["price"])} for e in res.events if e["symbol"] == sym],
            "trades": [{"aberta": t.opened, "fechada": t.closed, "entrada": _r(t.entry), "saida": _r(t.exit),
                        "r": _r(t.r_multiple, 3), "pnl": _r(t.pnl, 4), "motivo": t.reasons}
                       for t in res.trades if t.symbol == sym],
            "resumo": symbol_summary([t for t in res.trades if t.symbol == sym]),
            "checklist": [{"regra": k, "ok": bool(ok), "detalhe": d} for k, (ok, d) in sig.checks.items()],
            "sinal": sig.ok,
            "plano": plan,
            "tendencia_atual": df["trend"].iloc[i],
            "ultimo": _r(df["close"].iloc[i]),
        }
    summary = {k: _r(v, 4) for k, v in res.summary().items()}
    return {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "simulado": simulated,
        "timeframes": cfg["timeframes"],
        "risco": {k: cfg["risk"].get(k) for k in ("risk_per_trade", "take_partial_r", "partial_fraction",
                                                   "trailing_atr", "max_daily_loss", "min_reward_risk", "exit_mode")},
        "resumo": summary,
        "capital_inicial": res.initial,
        "equity": [[t // 1000, _r(v, 7)] for t, v in zip(res.equity_ts, res.equity_curve)],
        "simbolos": symbols,
    }


def render(payload: dict, out: str = "dashboard.html") -> Path:
    html = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    path = Path(out)
    path.write_text(html.replace("/*__DADOS__*/null", blob), encoding="utf-8")
    return path
