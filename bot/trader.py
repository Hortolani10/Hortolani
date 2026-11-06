"""Loop do bot ao vivo/paper: mesmas regras do backtest, decisões só em candle fechado."""
from __future__ import annotations

import copy
import json
import logging
import time
from pathlib import Path

from .data import attach_btc_trend, prepare

PAUSE_FILE = Path("PAUSAR")      # crie este arquivo para impedir NOVAS compras (posições seguem protegidas)
from .risk import RiskGuard, position_size, utcnow
from .learn import checar_desvio, ler_diario, registrar
from .strategy import Position, entry_features, entry_signal, manage_position

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
        risk_cash = (pos.cost / pos.entry) * pos.initial_risk if pos.entry else 0
        r_mult = pnl / risk_cash if risk_cash else 0.0
        log.info("FECHOU %s | motivo: %s | PnL %.2f USDT (%+.2fR)", sym, reason, pnl, r_mult)
        self.guard.register_close(pnl, utcnow())
        del self.positions[sym]
        # diário: memória do bot para aprender com a prática
        registrar({"origem": self.cfg["mode"], "simbolo": sym, "aberta": pos.opened_at,
                   "fechada": utcnow().isoformat(), "entrada": pos.entry, "pnl": pnl, "r": r_mult,
                   "motivo": ", ".join(pos.reasons), "features": pos.features})
        self._check_drift()

    def _check_drift(self) -> None:
        """Alarme de desvio: se a prática estiver muito pior que o histórico, arrisca metade."""
        try:
            hp = Path("logs/historico_r.json")
            hist = json.loads(hp.read_text()) if hp.exists() else []
            d = ler_diario()
            pratica = d[d["origem"] == self.cfg["mode"]]["r"].tolist() if not d.empty else []
        except Exception:
            log.exception("erro lendo o diário")
            return
        res = checar_desvio(pratica, hist)
        self.state["alarme_desvio"] = res
        if res["alarme"]:
            log.warning("ALARME DE DESVIO: %s -> risco reduzido à metade. Revise com 'python -m bot aprender'.",
                        res["motivo"])

    def _cancel_stop(self, sym: str, pos: Position) -> None:
        """Cancela o stop da corretora e contabiliza o que ele já tinha vendido."""
        done, got = self.broker.cancel(sym, pos.stop_order_id)
        pos.stop_order_id = None
        if done > 0:
            log.warning("%s: stop tinha executado parcialmente (%.8f) antes do cancelamento", sym, done)
            pos.qty = max(0.0, pos.qty - done)
            pos.proceeds += got

    def _sell(self, sym: str, pos: Position, qty: float, reason: str) -> None:
        self._cancel_stop(sym, pos)
        qty = min(qty, pos.qty)
        if qty <= 0:
            self._close(sym, pos, reason)
            return
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
            # Queda com "gap": o preço passou do limite da ordem stop-limit e ela não executou.
            # Não espera o próximo candle: vende a mercado agora.
            now_px = self.broker.price(sym)
            if now_px <= pos.stop * (1 - 0.006):
                log.warning("%s: preço %.6g abaixo do stop %.6g sem execução (gap) -> venda a mercado",
                            sym, now_px, pos.stop)
                self._sell(sym, pos, pos.qty, "stop (gap)")
                return
            # Posição sem stop registrado (falha ao colocar, ou cancelado no app): protege de novo.
            if not self.broker.stop_active(sym, pos.stop_order_id):
                log.warning("%s: posição sem stop ativo na corretora -> registrando de novo", sym)
                pos.stop_order_id = None
                self._protect(sym, pos)
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
                self._cancel_stop(sym, pos)
                if pos.qty * float(row["close"]) < self.broker.min_notional(sym):
                    self._close(sym, pos, "stop (executado parcialmente)")
                else:
                    self._protect(sym, pos)
            return

        if len(self.positions) >= self.cfg["risk"]["max_open_positions"]:
            return
        if PAUSE_FILE.exists():
            log.info("%s: arquivo PAUSAR presente -> sem novas compras", sym)
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
        scale = self.guard.risk_scale(eq)
        if (self.state.get("alarme_desvio") or {}).get("alarme"):
            scale *= 0.5
        qty = self.broker.amount(sym, position_size(eq, px, sig.stop, self.cfg, scale))
        if qty * px < self.broker.min_notional(sym) or qty * px * 1.002 > self.broker.usdt_free():
            log.info("%s: sinal válido mas saldo/tamanho insuficiente", sym)
            return
        filled, avg, cost = self.broker.buy(sym, qty)
        pos = Position(sym, filled, avg, sig.stop, avg - sig.stop, utcnow().isoformat(), highest=avg, cost=cost,
                       features={**entry_features(df, i), "risco_escala": scale})
        self.positions[sym] = pos
        self._protect(sym, pos)
        log.info("COMPRA %s qty=%.6f @ %.4f | stop %.4f (%.2f%%) | risco x%.2f | saída: %s",
                 sym, filled, avg, sig.stop, (1 - sig.stop / avg) * 100, scale,
                 self.cfg["risk"].get("exit_mode", "parcial"))

    def tick(self) -> None:
        tf_e, tf_t = self.cfg["timeframes"]["entry"], self.cfg["timeframes"]["trend"]
        # 1) PROTEÇÃO PRIMEIRO: confere stops de todas as posições, aconteça o que acontecer depois
        for sym in list(self.positions):
            try:
                self._check_stop(sym, self.positions[sym])
            except Exception:
                log.exception("erro conferindo stop de %s", sym)
            finally:
                self.save()
        # 2) filtro de mercado (BTC). Se falhar, não abre nada neste ciclo
        btc = None
        if self.cfg["strategy"].get("btc_filter"):
            try:
                btc = prepare(self.broker.candles("BTC/USDT", tf_e), self.broker.candles("BTC/USDT", tf_t), self.cfg)
            except Exception:
                log.exception("erro buscando BTC para o filtro de mercado")
                return
        # 3) análise de cada par no candle fechado
        for sym in self.cfg["symbols"]:
            try:
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

    def reconcile(self) -> None:
        """Na partida, confere o estado salvo com a corretora (vendas manuais, stop executado
        com o bot desligado, stop cancelado no aplicativo)."""
        for sym, pos in list(self.positions.items()):
            try:
                bal = self.broker.base_balance(sym)
                if bal is not None and bal < pos.qty * 0.98:
                    filled, px, got = self.broker.stop_filled(sym, pos.stop_order_id, pos.stop)
                    if filled:
                        log.warning("%s: stop executou com o bot desligado", sym)
                        pos.proceeds += got
                        pos.qty = 0
                        pos.reasons.append("stop")
                        self._close(sym, pos, "stop (bot desligado)")
                    else:
                        log.error("%s: saldo na corretora (%.8f) menor que o registrado (%.8f). "
                                  "Venda manual? Posição removida do bot.", sym, bal, pos.qty)
                        self.broker.cancel(sym, pos.stop_order_id)
                        del self.positions[sym]
                    continue
                self._check_stop(sym, pos)
            except Exception:
                log.exception("erro reconciliando %s", sym)
        self.save()

    def run_forever(self) -> None:
        log.info("Bot iniciado | modo=%s | símbolos=%s", self.cfg["mode"], self.cfg["symbols"])
        self.reconcile()
        while True:
            self.tick()
            time.sleep(self.cfg["loop"]["poll_seconds"])
