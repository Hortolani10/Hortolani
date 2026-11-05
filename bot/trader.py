"""Loop do bot ao vivo/paper: mesmas regras do backtest, decisões só em candle fechado."""
from __future__ import annotations

import copy
import json
import logging
import time
from pathlib import Path

from .data import attach_btc_trend, prepare
from .risk import RiskGuard, position_size, utcnow
from .strategy import Position, entry_signal, manage_position

log = logging.getLogger("bot")


class Trader:
    def __init__(self, cfg: dict, broker, state: dict, state_path: str = "state.json"):
        self.cfg, self.broker, self.state = cfg, broker, state
        self.state_path = Path(state_path)
        self.state.setdefault("positions", {})
        self.state.setdefault("last_bar", {})
        self.guard = RiskGuard(cfg)
        self.guard.load(self.state.get("guard", {}))
        self.positions = {s: Position.from_dict(d) for s, d in self.state["positions"].items()}

    # ---------- persistência ----------
    def save(self) -> None:
        self.state["positions"] = {s: p.to_dict() for s, p in self.positions.items()}
        self.state["guard"] = self.guard.to_dict()
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, default=str))
        tmp.replace(self.state_path)

    def equity(self) -> float:
        total = self.broker.usdt_free()
        for s, p in self.positions.items():
            try:
                total += p.qty * self.broker.price(s)
            except Exception:
                total += p.qty * p.entry
        return total

    # ---------- execução ----------
    def _close(self, sym: str, pos: Position, reason: str) -> None:
        pnl = pos.proceeds - pos.cost
        log.info("FECHOU %s | motivo: %s | PnL %.2f USDT", sym, reason, pnl)
        self.guard.register_close(pnl, utcnow())
        del self.positions[sym]

    def _sell(self, sym: str, pos: Position, qty: float, reason: str) -> None:
        self.broker.cancel(sym, pos.stop_order_id)
        pos.stop_order_id = None
        qty = min(qty, pos.qty)
        px, got = self.broker.sell(sym, qty)
        pos.qty -= qty
        pos.proceeds += got
        pos.reasons.append(reason)
        log.info("VENDA %s qty=%.6f @ %.4f (%s)", sym, qty, px, reason)
        if pos.qty * px < self.broker.min_notional(sym):
            if pos.qty > 0:   # sobra pequena demais para ordem: vende junto se possível
                log.info("resto %.8f %s abaixo do mínimo, mantido como poeira", pos.qty, sym)
            self._close(sym, pos, reason)
        else:
            self._protect(sym, pos)

    def _protect(self, sym: str, pos: Position) -> None:
        """Registra o stop. Se o preço já está abaixo dele, vende a mercado."""
        if self.broker.price(sym) <= pos.stop:
            self._sell(sym, pos, pos.qty, "stop (preço já abaixo do stop)")
            return
        pos.stop_order_id = self.broker.place_stop(sym, pos.qty, pos.stop)

    def _check_stop(self, sym: str, pos: Position) -> None:
        filled, px, got = self.broker.stop_filled(sym, pos.stop_order_id, pos.stop)
        if not filled:
            return
        if got <= 0:      # paper: simula a venda agora
            px, got = self.broker.sell(sym, pos.qty)
        pos.proceeds += got
        pos.qty = 0
        pos.reasons.append("stop")
        log.info("STOP executado %s @ %.4f", sym, px)
        self._close(sym, pos, "stop")

    def _on_closed_bar(self, sym: str, df) -> None:
        i = len(df) - 1
        row = df.iloc[i]
        trend = row["trend"]

        if sym in self.positions:
            pos = self.positions[sym]
            shadow = copy.deepcopy(pos)            # calcula as ações sem mexer na posição real
            acts = manage_position(shadow, row, trend, self.cfg)
            old_stop = pos.stop
            pos.stop, pos.highest, pos.partial_done = shadow.stop, shadow.highest, shadow.partial_done
            sold = False
            for act in acts:
                if act.kind == "sell" and act.qty > 0:
                    self._sell(sym, pos, act.qty, act.reason)
                    sold = True
                    if sym not in self.positions:
                        return
                elif act.kind == "move_stop":
                    log.info("STOP %s -> %.4f (%s)", sym, act.price, act.reason)
            if not sold and pos.stop != old_stop:
                self.broker.cancel(sym, pos.stop_order_id)
                pos.stop_order_id = None
                self._protect(sym, pos)
            return

        if len(self.positions) >= self.cfg["risk"]["max_open_positions"]:
            return
        eq = self.equity()
        self.guard.new_bar(utcnow(), eq)
        ok, why = self.guard.can_open(utcnow(), eq)
        if not ok:
            log.info("%s: entrada bloqueada (%s)", sym, why)
            return

        sig = entry_signal(df, i, trend, self.cfg)
        if not sig.ok:
            log.info("%s: sem entrada [tendência %s] falhou: %s", sym, trend, ", ".join(sig.failed))
            return

        px = self.broker.price(sym)
        if px <= sig.stop:
            return
        qty = self.broker.amount(sym, position_size(eq, px, sig.stop, self.cfg))
        if qty * px < self.broker.min_notional(sym) or qty * px * 1.002 > self.broker.usdt_free():
            log.info("%s: sinal válido mas saldo/tamanho insuficiente", sym)
            return
        filled, avg, cost = self.broker.buy(sym, qty)
        pos = Position(sym, filled, avg, sig.stop, avg - sig.stop, utcnow().isoformat(), highest=avg, cost=cost)
        self.positions[sym] = pos
        self._protect(sym, pos)
        log.info(
            "COMPRA %s qty=%.6f @ %.4f | stop %.4f (%.2f%%) | R:R %.2f | parcial em %.4f",
            sym, filled, avg, sig.stop, (1 - sig.stop / avg) * 100, sig.reward_risk,
            avg + self.cfg["risk"]["take_partial_r"] * pos.initial_risk,
        )

    def tick(self) -> None:
        tf_e, tf_t = self.cfg["timeframes"]["entry"], self.cfg["timeframes"]["trend"]
        btc = None
        if self.cfg["strategy"].get("btc_filter"):
            try:
                btc = prepare(self.broker.candles("BTC/USDT", tf_e), self.broker.candles("BTC/USDT", tf_t), self.cfg)
            except Exception:
                log.exception("erro buscando BTC para o filtro de mercado")
                return                      # sem o filtro, não decide nada neste ciclo
        for sym in self.cfg["symbols"]:
            try:
                if sym in self.positions:
                    self._check_stop(sym, self.positions[sym])
                df = prepare(self.broker.candles(sym, tf_e), self.broker.candles(sym, tf_t), self.cfg)
                if btc is not None:
                    df = attach_btc_trend(df, btc)
                last_ts = int(df["ts"].iloc[-1])
                if last_ts > int(self.state["last_bar"].get(sym, 0)):
                    self._on_closed_bar(sym, df)
                    self.state["last_bar"][sym] = last_ts
            except Exception:
                log.exception("erro processando %s", sym)
            finally:
                self.save()

    def run_forever(self) -> None:
        log.info("Bot iniciado | modo=%s | símbolos=%s", self.cfg["mode"], self.cfg["symbols"])
        while True:
            self.tick()
            time.sleep(self.cfg["loop"]["poll_seconds"])
