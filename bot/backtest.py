"""Backtest candle a candle usando exatamente as mesmas regras do bot ao vivo."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from .risk import RiskGuard, position_size
from .strategy import Position, entry_signal, manage_position


@dataclass
class Trade:
    symbol: str
    opened: str
    closed: str
    entry: float
    exit: float
    qty: float
    pnl: float
    r_multiple: float
    reasons: str


@dataclass
class Result:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    initial: float = 0.0

    def summary(self) -> dict:
        n = len(self.trades)
        final = self.equity_curve[-1] if self.equity_curve else self.initial
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        gross_win = sum(t.pnl for t in wins)
        gross_loss = -sum(t.pnl for t in losses)
        peak, mdd = self.initial, 0.0
        for v in self.equity_curve:
            peak = max(peak, v)
            mdd = max(mdd, 1 - v / peak if peak else 0)
        return {
            "operacoes": n,
            "taxa_acerto": len(wins) / n if n else 0.0,
            "fator_lucro": gross_win / gross_loss if gross_loss else float("inf") if gross_win else 0.0,
            "media_R": sum(t.r_multiple for t in self.trades) / n if n else 0.0,
            "retorno_total": final / self.initial - 1 if self.initial else 0.0,
            "drawdown_max": mdd,
            "saldo_final": final,
        }


def _ts(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def run(data: dict[str, pd.DataFrame], cfg: dict, initial: float = 1000.0) -> Result:
    """`data`: símbolo -> DataFrame já passado por data.prepare().

    Sinal no fechamento do candle i -> entrada na ABERTURA do candle i+1.
    Taxa e slippage aplicados em todas as execuções.
    """
    fee, slip = cfg["fees"]["taker"], cfg["fees"]["slippage"]
    cash = initial
    positions: dict[str, Position] = {}
    pending: dict[str, tuple] = {}      # símbolo -> (stop, risco) aguardando abertura do próximo candle
    guard = RiskGuard(cfg)
    res = Result(initial=initial)

    timeline = sorted({int(ts) for df in data.values() for ts in df["close_ts"]})
    idx = {s: dict(zip(df["close_ts"].astype(int), range(len(df)))) for s, df in data.items()}

    def equity(prices: dict[str, float]) -> float:
        return cash + sum(p.qty * prices.get(s, p.entry) for s, p in positions.items())

    last_px: dict[str, float] = {}
    for ts in timeline:
        now = _ts(ts)
        for sym, df in data.items():
            i = idx[sym].get(ts)
            if i is None:
                continue
            row = df.iloc[i]

            # 1) executa entrada pendente na abertura deste candle
            if sym in pending:
                stop, _ = pending.pop(sym)
                px = float(row["open"]) * (1 + slip)
                if px > stop:
                    qty = position_size(equity(last_px), px, stop, cfg)
                    cost = qty * px * (1 + fee)
                    if qty > 0 and cost <= cash and cost >= 10:
                        cash -= cost
                        positions[sym] = Position(sym, qty, px, stop, px - stop, now.isoformat(), highest=px, cost=cost)

            # 2) gerencia posição aberta
            if sym in positions:
                pos = positions[sym]
                for act in manage_position(pos, row, row["trend"], cfg):
                    if act.kind == "sell" and act.qty > 0:
                        px = act.price * (1 - slip)
                        proceeds = act.qty * px * (1 - fee)
                        cash += proceeds
                        pos.proceeds += proceeds
                        pos.reasons.append(act.reason)
                        exit_px = px
                if pos.qty <= 1e-12:
                    pnl = pos.proceeds - pos.cost
                    qty0 = pos.cost / pos.entry / (1 + fee)
                    risk_cash = qty0 * pos.initial_risk
                    res.trades.append(Trade(
                        sym, pos.opened_at, now.isoformat(), pos.entry, exit_px, qty0, pnl,
                        pnl / risk_cash if risk_cash else 0.0, ", ".join(pos.reasons),
                    ))
                    guard.register_close(pnl, now)
                    del positions[sym]

            last_px[sym] = float(row["close"])

            # 3) procura nova entrada
            guard.new_bar(now, equity(last_px))
            if sym not in positions and sym not in pending and len(positions) + len(pending) < cfg["risk"]["max_open_positions"]:
                ok, _ = guard.can_open(now, equity(last_px))
                if ok:
                    sig = entry_signal(df, i, row["trend"], cfg)
                    if sig.ok:
                        pending[sym] = (sig.stop, sig.entry - sig.stop)

        res.equity_curve.append(equity(last_px))
    return res
