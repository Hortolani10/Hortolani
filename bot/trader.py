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
from .notify import ping_health
from .shadow import ShadowRange
from .sleeve import TrendSleeve
from .strategy import Position, entry_features, entry_signal, lateral_signal, manage_position

log = logging.getLogger("bot")


class Trader:
    def __init__(self, cfg: dict, broker, state: dict, state_path: str = "state.json", tg=None, painel=None):
        self.cfg, self.broker, self.state = cfg, broker, state
        self.tg = tg                                   # Telegram (opcional)
        self.painel = painel                           # painel ao vivo no navegador (opcional)
        self.state_path = Path(state_path)
        self.state.setdefault("positions", {})
        self.state.setdefault("last_bar", {})
        self.guard = RiskGuard(cfg)
        self.guard.load(self.state.get("guard", {}))
        self.positions = {s: Position.from_dict(d) for s, d in self.state["positions"].items()}
        sc = cfg.get("trend_sleeve") or {}
        self.sleeve = TrendSleeve(cfg, broker, state) if sc.get("enabled") else None
        lat_on = bool((cfg.get("lateral") or {}).get("enabled"))
        # se a lateralização opera de verdade, não precisa mais observá-la
        self.shadow = (ShadowRange(state, registrar, cfg.get("mode", "paper"))
                       if cfg.get("observacao", {}).get("lateralizacao", True) and not lat_on else None)

    @property
    def origem(self) -> str:
        """Nome desta instância no diário: 'paper', 'live' ou 'paper-ativo' etc."""
        inst = self.cfg.get("instancia")
        return f"{self.cfg['mode']}-{inst}" if inst else self.cfg["mode"]

    # ---------- persistência ----------
    def save(self) -> None:
        self.state["positions"] = {s: p.to_dict() for s, p in self.positions.items()}
        self.state["guard"] = self.guard.to_dict()
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=2, default=str))
        tmp.replace(self.state_path)

    def equity(self) -> float:
        """Patrimônio TOTAL (bot + cofre de tendência)."""
        total = self.broker.usdt_free()
        for s, p in self.positions.items():
            try:
                total += p.qty * self.broker.price(s)
            except Exception:
                total += p.qty * p.entry
        if self.sleeve:
            total += self.sleeve.value() - float(self.sleeve.st.get("cash", 0.0))   # caixa do cofre já está no USDT livre
        return total

    def bot_equity(self) -> float:
        """Só a parte do bot: o cofre tem dinheiro próprio e não entra nas travas do bot."""
        return self.equity() - (self.sleeve.value() if self.sleeve else 0.0)

    def bot_free_usdt(self) -> float:
        return self.broker.usdt_free() - (float(self.sleeve.st.get("cash", 0.0)) if self.sleeve else 0.0)

    # ---------- execução ----------
    def _close(self, sym: str, pos: Position, reason: str) -> None:
        pnl = pos.proceeds - pos.cost
        risk_cash = (pos.cost / pos.entry) * pos.initial_risk if pos.entry else 0
        r_mult = pnl / risk_cash if risk_cash else 0.0
        log.info("FECHOU %s | motivo: %s | PnL %.2f USDT (%+.2fR)", sym, reason, pnl, r_mult)
        self.guard.register_close(pnl, utcnow())
        del self.positions[sym]
        # diário: memória do bot para aprender com a prática
        registrar({"origem": self.origem, "simbolo": sym, "aberta": pos.opened_at,
                   "fechada": utcnow().isoformat(), "entrada": pos.entry, "pnl": pnl, "r": r_mult,
                   "motivo": ", ".join(pos.reasons), "features": pos.features})
        self._check_drift()

    def _check_drift(self) -> None:
        """Alarme de desvio: se a prática estiver muito pior que o histórico, arrisca metade."""
        try:
            hp = Path("logs/historico_r.json")
            hist = json.loads(hp.read_text()) if hp.exists() else []
            d = ler_diario()
            pratica = d[d["origem"] == self.origem]["r"].tolist() if not d.empty else []
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
        if self.shadow:
            try:
                self.shadow.on_bar(sym, df)          # só observa: nunca envia ordem
            except Exception:
                log.exception("erro na observação de %s", sym)

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
        eq = self.bot_equity()
        self.guard.new_bar(utcnow(), eq)
        ok, why = self.guard.can_open(utcnow(), eq)
        if not ok:
            log.info("%s: entrada bloqueada (%s)", sym, why)
            return

        sig = entry_signal(df, i, trend, self.cfg)
        strat = "tendencia"
        if not sig.ok and (self.cfg.get("lateral") or {}).get("enabled"):
            lsig = lateral_signal(df, i, self.cfg)
            if lsig.ok:
                sig, strat = lsig, "lateral"
        if not sig.ok:
            log.info("%s: sem entrada [tendência %s] falhou: %s", sym, trend, ", ".join(sig.failed))
            return

        px = self.broker.price(sym)
        if px <= sig.stop:
            return
        scale = self.guard.risk_scale(eq)
        if strat == "lateral":
            scale *= float((self.cfg.get("lateral") or {}).get("risk_scale", 1.0))
        if (self.state.get("alarme_desvio") or {}).get("alarme"):
            scale *= 0.5
        qty = self.broker.amount(sym, position_size(eq, px, sig.stop, self.cfg, scale))
        if qty * px < self.broker.min_notional(sym) or qty * px * 1.002 > self.bot_free_usdt():
            log.info("%s: sinal válido mas saldo/tamanho insuficiente", sym)
            return
        filled, avg, cost = self.broker.buy(sym, qty)
        pos = Position(sym, filled, avg, sig.stop, avg - sig.stop, utcnow().isoformat(), highest=avg, cost=cost,
                       strategy=strat, features={**entry_features(df, i), "risco_escala": scale, "estrategia": strat})
        self.positions[sym] = pos
        self._protect(sym, pos)
        log.info("COMPRA %s [%s] qty=%.6f @ %.4f | stop %.4f (%.2f%%) | risco x%.2f | saída: %s",
                 sym, strat, filled, avg, sig.stop, (1 - sig.stop / avg) * 100, scale,
                 "volta à média ou 12 velas" if strat == "lateral" else self.cfg["risk"].get("exit_mode", "parcial"))

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
        # 2) cofre de tendência (decide no fechamento diário; reequilibra uma vez por mês)
        if self.sleeve:
            try:
                self.sleeve.ensure_funded(self.equity())
                daily = {s: self.broker.candles(s, "1d") for s in set(self.sleeve.sc["symbols"]) | {"BTC/USDT"}}
                self.sleeve.on_tick(daily, paused=PAUSE_FILE.exists(), journal=registrar)
                if not PAUSE_FILE.exists():
                    self.sleeve.rebalance(self.equity(), self.bot_free_usdt(), utcnow())
            except Exception:
                log.exception("erro no cofre de tendência")
            finally:
                self.save()
        # 3) filtro de mercado (BTC). Se falhar, não abre nada neste ciclo
        btc = None
        if self.cfg["strategy"].get("btc_filter"):
            try:
                btc = prepare(self.broker.candles("BTC/USDT", tf_e), self.broker.candles("BTC/USDT", tf_t), self.cfg)
            except Exception:
                log.exception("erro buscando BTC para o filtro de mercado")
                return
        # 4) análise de cada par no candle fechado
        for sym in self.cfg["symbols"]:
            try:
                df = prepare(self.broker.candles(sym, tf_e), self.broker.candles(sym, tf_t), self.cfg)
                if btc is not None:
                    df = attach_btc_trend(df, btc)
                self._update_radar(sym, df)
                self._cache_chart(sym, df)
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
                if bal is not None and self.sleeve:
                    bal -= self.sleeve.qty(sym)          # parte da moeda pertence ao cofre
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

    # ---------- radar: o que o bot está vendo em cada moeda ----------
    def _update_radar(self, sym: str, df) -> None:
        i = len(df) - 1
        row = df.iloc[i]
        sig = entry_signal(df, i, row["trend"], self.cfg)
        checks = {k: bool(v[0]) for k, v in sig.checks.items()}
        lat = None
        if (self.cfg.get("lateral") or {}).get("enabled") or self.shadow:
            lat = bool(lateral_signal(df, i, self.cfg).ok)
        self.state.setdefault("radar", {})[sym] = {
            "preco": float(row["close"]),
            "tendencia": str(row["trend"]),
            "btc": str(row.get("btc_trend", "")),
            "regras_ok": sum(checks.values()),
            "regras_total": len(checks),
            "falhou": [k for k, ok in checks.items() if not ok],
            "regras": checks,
            "rsi": round(float(row["rsi"]), 1),
            "adx": round(float(row["adx"]), 1),
            "sinal_tendencia": bool(sig.ok),
            "sinal_lateral": lat,
            "candle": int(row["close_ts"]),
            "atualizado": utcnow().isoformat(),
        }

    def _cache_chart(self, sym: str, df) -> None:
        """Últimos 300 candles de 4h com as médias e a banda que o bot usa (para o painel)."""
        t = df.tail(300)
        cols = {"t": (t["ts"] // 1000).astype(int).tolist()}
        for k in ("open", "high", "low", "close", "ema_fast", "ema_mid", "ema_slow", "bbl", "bbm"):
            cols[k] = [None if v != v else round(float(v), 8) for v in t[k].tolist()]
        cols["trend"] = t["trend"].astype(str).tolist()
        if not hasattr(self, "charts"):
            self.charts = {}
        self.charts[sym] = cols

    def radar_text(self) -> str:
        rad = self.state.get("radar") or {}
        if not rad:
            return "Radar ainda vazio (aguarde o primeiro ciclo)."
        icon = {"ALTA": "🟢", "BAIXA": "🔴", "LATERAL": "🟡"}
        lines = ["📡 Radar (tendência diária da moeda · regras de entrada)"]
        for s, r in sorted(rad.items(), key=lambda x: -x[1]["regras_ok"]):
            extra = " · ✅ SINAL" if r["sinal_tendencia"] else (" · ↔ sinal lateral" if r.get("sinal_lateral") else "")
            lines.append(f"{icon.get(r['tendencia'], '⚪')} {s.split('/')[0]}: {r['tendencia'].lower()} · "
                         f"{r['regras_ok']}/{r['regras_total']} regras · RSI {r['rsi']}{extra}")
        btc = next(iter(rad.values())).get("btc")
        if btc:
            lines.append(f"Filtro do BTC: {btc.lower()}")
        return "\n".join(lines)

    def snapshot(self) -> dict:
        """Tudo o que o painel local mostra."""
        total = self.equity()
        hist = self.state.setdefault("equity_hist", [])
        now_s = int(time.time())
        if not hist or now_s - hist[-1][0] >= 300:            # um ponto a cada 5 minutos
            hist.append([now_s, round(total, 4)])
            del hist[:-3000]
        precos, var24 = {}, {}
        try:
            tk = self.broker.market.fetch_tickers(list(self.cfg["symbols"]))
            precos = {s: float(v["last"]) for s, v in tk.items() if v.get("last")}
            var24 = {s: float(v["percentage"]) for s, v in tk.items() if v.get("percentage") is not None}
        except Exception:
            pass
        sv = self.sleeve.value() if self.sleeve else 0.0
        pos = []
        for s, p in self.positions.items():
            try:
                px = self.broker.price(s)
            except Exception:
                px = p.entry
            pos.append({"simbolo": s, "estrategia": p.strategy, "entrada": p.entry, "preco": px, "stop": p.stop,
                        "qtd": p.qty, "resultado_pct": px / p.entry - 1, "aberta": p.opened_at})
        return {
            "modo": self.origem, "agora": utcnow().isoformat(), "pausado": PAUSE_FILE.exists(),
            "carteira": total, "bot": total - sv, "cofre": sv,
            "cofre_moedas": {k: v for k, v in (self.sleeve.st["holdings"].items() if self.sleeve else []) if v > 0},
            "posicoes": pos, "radar": self.state.get("radar") or {}, "precos": precos, "var24": var24, "equity_hist": hist,
            "alarme": (self.state.get("alarme_desvio") or {}).get("alarme", False),
            "timeframes": self.cfg["timeframes"], "lateral_ligada": bool((self.cfg.get("lateral") or {}).get("enabled")),
        }

    # ---------- celular: status, comandos e resumo diário ----------
    def status_text(self) -> str:
        total = self.equity()
        modo = {"paper": "PAPER", "live": "TESTNET" if self.cfg.get("testnet", True) else "REAL"}.get(self.cfg.get("mode"), "")
        if self.cfg.get("instancia"):
            modo += "-" + str(self.cfg["instancia"]).upper()
        lines = [f"📊 [{modo}] Carteira: {total:.2f} USDT"]
        if self.sleeve:
            sv = self.sleeve.value()
            held = [f"{s.split('/')[0]} {q:.6g}" for s, q in self.sleeve.st["holdings"].items() if q > 0]
            lines.append(f"• Bot: {total - sv:.2f} USDT")
            lines.append(f"• Cofre de tendência: {sv:.2f} USDT ({', '.join(held) if held else 'em USDT'})")
        if self.positions:
            for s, p in self.positions.items():
                try:
                    px = self.broker.price(s)
                    lines.append(f"• {s}: entrada {p.entry:.6g} · agora {px:.6g} ({px / p.entry - 1:+.1%}) · stop {p.stop:.6g}")
                except Exception:
                    lines.append(f"• {s}: entrada {p.entry:.6g} · stop {p.stop:.6g}")
        else:
            lines.append("• Bot sem posições abertas (aguardando sinal)")
        if PAUSE_FILE.exists():
            lines.append("⏸ PAUSADO: sem novas compras")
        if (self.state.get("alarme_desvio") or {}).get("alarme"):
            lines.append("🚨 Alarme de desvio ativo (risco pela metade)")
        if self.guard.paused_until:
            lines.append(f"⏸ Pausa após stops seguidos até {self.guard.paused_until[:16]}")
        return "\n".join(lines)

    def handle_commands(self) -> None:
        if not self.tg or not self.tg.enabled or not (self.cfg.get("telegram") or {}).get("comandos", True):
            return
        cmds, off = self.tg.commands(int(self.state.get("tg_offset", 0)))
        self.state["tg_offset"] = off
        for c in cmds:
            if c == "/status":
                self.tg.send(self.status_text(), dedupe_s=0)
            elif c == "/radar":
                self.tg.send(self.radar_text(), dedupe_s=0)
            elif c == "/pausar":
                PAUSE_FILE.write_text("pausado pelo Telegram\n")
                self.tg.send("⏸ Pausado: sem novas compras. Posições abertas continuam protegidas. /retomar para voltar.", dedupe_s=0)
                log.warning("pausado pelo Telegram")
            elif c == "/retomar":
                PAUSE_FILE.unlink(missing_ok=True)
                self.tg.send("▶️ Retomado: o bot volta a abrir posições quando houver sinal.", dedupe_s=0)
                log.warning("retomado pelo Telegram")
            else:
                self.tg.send("Comandos: /status · /radar (o que o bot vê em cada moeda) · /pausar (sem novas compras) · /retomar", dedupe_s=0)

    def daily_summary(self) -> None:
        if not self.tg or not self.tg.enabled:
            return
        day = utcnow().strftime("%Y-%m-%d")
        if utcnow().hour >= 1 and self.state.get("summary_day") != day:   # ~22h em Brasília, após o fechamento diário
            self.state["summary_day"] = day
            self.tg.send("🗓 Resumo do dia\n" + self.status_text() + "\n\n" + self.radar_text(), dedupe_s=0)

    def run_forever(self) -> None:
        log.info("Bot iniciado | modo=%s | símbolos=%s", self.cfg["mode"], self.cfg["symbols"])
        self.reconcile()
        while True:
            ok = True
            try:
                self.tick()
                self.handle_commands()
                self.daily_summary()
                self.save()
                self._refresh_painel()
            except Exception:
                ok = False
                log.exception("erro no ciclo principal")
            ping_health(fail=not ok)          # sinal de vida: se parar de chegar, o healthchecks avisa você
            self._sleep_listening(self.cfg["loop"]["poll_seconds"])

    def _refresh_painel(self) -> None:
        if self.painel:
            try:
                self.painel.update(self.snapshot(), getattr(self, "charts", {}))
            except Exception:
                log.exception("erro atualizando o painel")

    def _sleep_listening(self, seconds: float, step: float = 5.0) -> None:
        """Espera até o próximo ciclo, mas confere os comandos do Telegram a cada `step` segundos
        e atualiza os preços do painel a cada ~15 s."""
        end = time.time() + seconds
        k = 0
        while time.time() < end:
            time.sleep(min(step, max(0.0, end - time.time())))
            k += 1
            try:
                self.handle_commands()
            except Exception:
                log.exception("erro lendo comandos do Telegram")
            if k % 3 == 0:
                self._refresh_painel()
