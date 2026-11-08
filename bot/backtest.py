"""Backtest candle a candle usando exatamente as mesmas regras do bot ao vivo."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from . import regime
from .risk import RiskGuard, position_size
from .strategy import (Position, entry_features, entry_signal, lateral_prefilter, lateral_signal,
                       manage_position, prefilter)


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
    features: dict = field(default_factory=dict)


@dataclass
class Result:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    equity_ts: list[int] = field(default_factory=list)              # close_ts (ms) de cada ponto da curva
    events: list[dict] = field(default_factory=list)                # compras/vendas para desenhar no gráfico
    stop_path: dict[str, list] = field(default_factory=dict)        # símbolo -> [(ts, stop) ou (ts, None)]
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


def _bar_ms(df: pd.DataFrame) -> int:
    """Duração de um candle (ms): a nota usada na entrada é a do candle do SINAL (anterior)."""
    return int(df["close_ts"].iat[1] - df["close_ts"].iat[0]) if len(df) > 1 else 0


def _ts(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def run(data: dict[str, pd.DataFrame], cfg: dict, initial: float = 1000.0, start_ts: int | None = None,
        end_ts: int | None = None, close_at_end: bool = False) -> Result:
    """`data`: símbolo -> DataFrame já passado por data.prepare().

    Sinal no fechamento do candle i -> entrada na ABERTURA do candle i+1.
    Taxa e slippage aplicados em todas as execuções.
    `start_ts` (ms): candles anteriores servem só de aquecimento (sem operar).
    `end_ts` (ms): para antes deste instante; `close_at_end` zera as posições no fim
    (usado para encadear períodos no walk-forward).
    """
    fee, slip = cfg["fees"]["taker"], cfg["fees"]["slippage"]
    cash = initial
    positions: dict[str, Position] = {}
    pending: dict[str, tuple] = {}      # símbolo -> (stop, risco) aguardando abertura do próximo candle
    guard = RiskGuard(cfg)
    res = Result(initial=initial)

    timeline = sorted({int(ts) for df in data.values() for ts in df["close_ts"]})
    if start_ts is not None:
        timeline = [t for t in timeline if t >= start_ts]
    if end_ts is not None:
        timeline = [t for t in timeline if t < end_ts]
    candidates = {s: prefilter(df, cfg).to_numpy() for s, df in data.items()}
    lat_on = bool((cfg.get("lateral") or {}).get("enabled"))
    lat_cand = {s: lateral_prefilter(df, cfg).to_numpy() for s, df in data.items()} if lat_on else {}
    lat_scale = float((cfg.get("lateral") or {}).get("risk_scale", 1.0))
    idx = {s: dict(zip(df["close_ts"].astype(int), range(len(df)))) for s, df in data.items()}
    termo = regime.serie(data).to_dict() if (cfg.get("termometro") or {}).get("enabled") else {}

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
                stop, _, feats, strat = pending.pop(sym)
                px = float(row["open"]) * (1 + slip)
                if px > stop:
                    eq_now = equity(last_px)
                    qty = position_size(eq_now, px, stop, cfg,
                                        guard.risk_scale(eq_now) * (lat_scale if strat == "lateral" else 1.0)
                                        * regime.escala(cfg, termo.get(int(row["close_ts"]) - _bar_ms(df))))
                    cost = qty * px * (1 + fee)
                    if qty > 0 and cost <= cash and cost >= cfg["fees"].get("min_order", 5.0):
                        cash -= cost
                        positions[sym] = Position(sym, qty, px, stop, px - stop, now.isoformat(), highest=px, cost=cost, strategy=strat,
                                                  features={**feats, "risco_escala": guard.risk_scale(eq_now), "estrategia": strat})
                        res.events.append({"symbol": sym, "ts": int(row["ts"]), "side": "buy", "price": px,
                                           "reason": f"compra · stop {stop:.6g}"})

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
                        res.events.append({"symbol": sym, "ts": int(row["ts"]), "side": "sell", "price": px,
                                           "reason": act.reason})
                if pos.qty <= 1e-12:
                    pnl = pos.proceeds - pos.cost
                    qty0 = pos.cost / pos.entry / (1 + fee)
                    risk_cash = qty0 * pos.initial_risk
                    res.trades.append(Trade(
                        sym, pos.opened_at, now.isoformat(), pos.entry, exit_px, qty0, pnl,
                        pnl / risk_cash if risk_cash else 0.0, ", ".join(pos.reasons), pos.features,
                    ))
                    guard.register_close(pnl, now)
                    del positions[sym]

            last_px[sym] = float(row["close"])
            res.stop_path.setdefault(sym, []).append(
                (int(row["ts"]), positions[sym].stop if sym in positions else None))

            # 3) procura nova entrada
            guard.new_bar(now, equity(last_px))
            if sym not in positions and sym not in pending and len(positions) + len(pending) < cfg["risk"]["max_open_positions"]:
                ok, _ = guard.can_open(now, equity(last_px))
                if ok and candidates[sym][i]:
                    sig = entry_signal(df, i, row["trend"], cfg)
                    if sig.ok:
                        pending[sym] = (sig.stop, sig.entry - sig.stop, entry_features(df, i), "tendencia")
                if ok and lat_on and sym not in pending and lat_cand[sym][i]:
                    sig = lateral_signal(df, i, cfg)
                    if sig.ok:
                        pending[sym] = (sig.stop, sig.entry - sig.stop, entry_features(df, i), "lateral")

        res.equity_curve.append(equity(last_px))
        res.equity_ts.append(ts)

    if close_at_end and positions:
        for sym, pos in list(positions.items()):
            px = last_px.get(sym, pos.entry) * (1 - slip)
            proceeds = pos.qty * px * (1 - fee)
            cash += proceeds
            pos.proceeds += proceeds
            pnl = pos.proceeds - pos.cost
            qty0 = pos.cost / pos.entry / (1 + fee)
            risk_cash = qty0 * pos.initial_risk
            res.trades.append(Trade(sym, pos.opened_at, _ts(timeline[-1]).isoformat(), pos.entry, px, qty0, pnl,
                                    pnl / risk_cash if risk_cash else 0.0, "fim do período", pos.features))
        positions.clear()
        if res.equity_curve:
            res.equity_curve[-1] = cash
    return res
