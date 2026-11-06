"""Parte "seguir a tendência" da carteira (25% por padrão).

Regra (a mesma definição de tendência do bot, sem ajuste):
  * BTC: segura enquanto a tendência DIÁRIA do BTC estiver em ALTA; senão fica em USDT.
  * ETH (e demais): segura enquanto a tendência diária da moeda E a do BTC estiverem em ALTA.
  * Decide no fechamento do candle diário (00:00 UTC = 21:00 em Brasília) e executa logo depois.
  * Ao entrar, cada moeda recebe uma fatia igual do valor do "cofre"; ao sair, vende tudo.

O cofre tem dinheiro próprio (virtual dentro da mesma conta): as oscilações dele não
acionam as travas do bot e vice-versa. Não há stop: a saída é a virada da tendência diária
(foi assim que a regra foi testada; quedas de até ~50% dentro do cofre aconteceram em 6 anos).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from .indicators import add_all
from .strategy import ALTA, trend_series

log = logging.getLogger("bot")


def daily_trends(daily: dict[str, pd.DataFrame], cfg: dict) -> dict[str, pd.Series]:
    """Tendência diária por moeda (index = close_ts em ms)."""
    out = {}
    for s, d in daily.items():
        t = trend_series(add_all(d, cfg))
        out[s] = pd.Series(t.values, index=(d["ts"] + 86_400_000).astype("int64").values)
    return out


def wanted(trends: dict[str, pd.Series], close_ts: int, symbols: list[str]) -> dict[str, bool]:
    """Quais moedas o cofre deve segurar após o candle diário que fechou em `close_ts`."""
    def at(s):
        ser = trends.get(s)
        if ser is None:
            return "LATERAL"
        ser = ser[ser.index <= close_ts]
        return ser.iloc[-1] if len(ser) else "LATERAL"
    btc_up = at("BTC/USDT") == ALTA
    return {s: (at(s) == ALTA and (btc_up or s == "BTC/USDT")) for s in symbols}


# ------------------------------------------------------------------ backtest
def backtest(daily: dict[str, pd.DataFrame], cfg: dict, initial: float, start_ts: int, end_ts: int | None = None) -> dict:
    """Simula o cofre dia a dia: sinal no fechamento do dia t, execução na abertura de t+1."""
    sc = cfg["trend_sleeve"]
    syms = sc["symbols"]
    fee, slip = cfg["fees"]["taker"], cfg["fees"]["slippage"]
    trends = daily_trends(daily, cfg)
    px = {s: daily[s].set_index("ts") for s in syms}
    days = sorted(set().union(*[set(px[s].index) for s in syms]))
    days = [d for d in days if d >= start_ts and (end_ts is None or d < end_ts)]
    cash, hold, curve, trades = initial, {s: 0.0 for s in syms}, [], []
    for d in days:
        want = wanted(trends, d, syms)          # decidido no fechamento anterior (close_ts == d)
        opens = {s: float(px[s].at[d, "open"]) for s in syms if d in px[s].index}
        value = cash + sum(hold[s] * opens.get(s, 0) for s in syms)
        for s in syms:
            if s not in opens:
                continue
            if hold[s] > 0 and not want[s]:
                got = hold[s] * opens[s] * (1 - slip) * (1 - fee)
                cash += got
                trades.append({"simbolo": s, "lado": "venda", "ts": d, "preco": opens[s], "usdt": got})
                hold[s] = 0.0
        for s in syms:
            if s not in opens:
                continue
            if hold[s] == 0 and want[s]:
                spend = min(cash, value / len(syms))
                if spend >= 5:
                    hold[s] = spend * (1 - fee) / (opens[s] * (1 + slip))
                    cash -= spend
                    trades.append({"simbolo": s, "lado": "compra", "ts": d, "preco": opens[s], "usdt": spend})
        closes = {s: float(px[s].at[d, "close"]) for s in syms if d in px[s].index}
        curve.append((d + 86_400_000, cash + sum(hold[s] * closes.get(s, 0) for s in syms)))
    eq = pd.Series([v for _, v in curve], index=pd.to_datetime([t for t, _ in curve], unit="ms", utc=True))
    return {"equity": eq, "trades": trades}


# ------------------------------------------------------------------ ao vivo / paper
class TrendSleeve:
    """Estado guardado em state["sleeve"]: {"cash", "holdings": {sym: qty}, "last_day", "cost": {sym: usdt}}."""

    def __init__(self, cfg: dict, broker, state: dict):
        self.cfg, self.broker = cfg, broker
        self.sc = cfg["trend_sleeve"]
        self.st = state.setdefault("sleeve", {})
        self.st.setdefault("holdings", {})
        self.st.setdefault("cost", {})
        self.st.setdefault("last_day", 0)

    @property
    def enabled(self) -> bool:
        return bool(self.sc.get("enabled"))

    def ensure_funded(self, total_equity: float) -> None:
        """Na primeira vez, separa `fraction` do patrimônio para o cofre."""
        if "cash" not in self.st:
            self.st["cash"] = round(total_equity * float(self.sc["fraction"]), 8)
            log.info("COFRE TENDÊNCIA criado com %.2f USDT (%.0f%% da carteira)", self.st["cash"],
                     float(self.sc["fraction"]) * 100)

    def qty(self, sym: str) -> float:
        return float(self.st["holdings"].get(sym, 0.0))

    def value(self) -> float:
        v = float(self.st.get("cash", 0.0))
        for s, q in self.st["holdings"].items():
            if q > 0:
                try:
                    v += q * self.broker.price(s)
                except Exception:
                    v += self.st["cost"].get(s, 0.0)
        return v

    def on_tick(self, daily: dict[str, pd.DataFrame], paused: bool = False, journal=None) -> None:
        syms = self.sc["symbols"]
        if any(s not in daily or daily[s].empty for s in syms + ["BTC/USDT"]):
            return
        last_close = int(daily["BTC/USDT"]["ts"].iloc[-1]) + 86_400_000
        if last_close <= int(self.st["last_day"]):
            return
        want = wanted(daily_trends(daily, self.cfg), last_close, syms)
        day = datetime.fromtimestamp(last_close / 1000, timezone.utc).date().isoformat()
        log.info("COFRE TENDÊNCIA %s: quer segurar %s", day, [s for s, w in want.items() if w] or "nada (USDT)")
        for s in syms:                                   # vendas primeiro (liberam caixa)
            if self.qty(s) > 0 and not want[s]:
                q = self.qty(s)
                px, got = self.broker.sell(s, q)
                cost = self.st["cost"].pop(s, 0.0)
                self.st["cash"] += got
                self.st["holdings"][s] = 0.0
                log.info("COFRE VENDA %s qty=%.8f @ %.6g -> %.2f USDT (resultado %+.2f)", s, q, px, got, got - cost)
                if journal:
                    journal({"origem": f"{self.cfg['mode']}-tendencia", "simbolo": s, "pnl": got - cost,
                             "r": (got - cost) / cost if cost else 0.0, "motivo": "tendência diária virou",
                             "features": {}})
        value = self.value()
        for s in syms:
            if self.qty(s) == 0 and want[s] and not paused:
                spend = min(self.st["cash"], value / len(syms))
                p = self.broker.price(s)
                q = self.broker.amount(s, spend * 0.995 / p)
                if q * p < self.broker.min_notional(s):
                    log.info("COFRE %s: valor pequeno demais para comprar (%.2f USDT)", s, q * p)
                    continue
                filled, avg, cost = self.broker.buy(s, q)
                self.st["cash"] -= cost
                self.st["holdings"][s] = filled
                self.st["cost"][s] = cost
                log.info("COFRE COMPRA %s qty=%.8f @ %.6g (%.2f USDT)", s, filled, avg, cost)
        self.st["last_day"] = last_close

    # -------------------------------------------------------------- reequilíbrio mensal
    def rebalance(self, total_equity: float, bot_free_cash: float, now: datetime) -> None:
        """Uma vez por mês, volta o cofre para `fraction` do patrimônio total.
        Cofre grande demais: vende parte das moedas (ou libera caixa) para o bot.
        Cofre pequeno demais: recebe caixa do bot e compra mais das moedas que já segura."""
        month = now.strftime("%Y-%m")
        if "rebal_month" not in self.st:          # criado agora: primeiro reequilíbrio no mês seguinte
            self.st["rebal_month"] = month
            return
        if self.st["rebal_month"] == month:
            return
        self.st["rebal_month"] = month
        target = total_equity * float(self.sc["fraction"])
        cur = self.value()
        delta = target - cur
        tol = max(target * float(self.sc.get("rebalance_tolerance", 0.05)), 5.0)
        if abs(delta) < tol:
            log.info("COFRE reequilíbrio %s: %.2f de %.2f alvo, dentro da tolerância", month, cur, target)
            return
        held = [s for s in self.sc["symbols"] if self.qty(s) > 0]
        prices = {s: self.broker.price(s) for s in held}
        hold_val = sum(self.qty(s) * prices[s] for s in held)
        log.info("COFRE reequilíbrio %s: %.2f -> alvo %.2f (%+.2f)", month, cur, target, delta)
        if delta < 0:                                   # cofre grande: devolve ao bot
            give = min(-delta, self.st["cash"])
            self.st["cash"] -= give
            rest = -delta - give
            if rest >= 5 and hold_val > 0:
                frac = min(1.0, rest / hold_val)
                for s in held:
                    q = self.broker.amount(s, self.qty(s) * frac)
                    if q * prices[s] < self.broker.min_notional(s):
                        continue
                    px, got = self.broker.sell(s, q)     # o dinheiro vai para o lado do bot
                    self.st["cost"][s] = self.st["cost"].get(s, 0.0) * (1 - q / self.qty(s))
                    self.st["holdings"][s] = self.qty(s) - q
                    log.info("COFRE reequilíbrio: vendeu %.8f %s (%.2f USDT para o bot)", q, s, got)
        else:                                           # cofre pequeno: recebe do bot
            move = min(delta, max(0.0, bot_free_cash))
            self.st["cash"] += move
            if held and hold_val > 0:
                for s in held:
                    spend = min(self.st["cash"], move * (self.qty(s) * prices[s]) / hold_val)
                    q = self.broker.amount(s, spend * 0.995 / prices[s])
                    if q * prices[s] < self.broker.min_notional(s):
                        continue
                    filled, avg, cost = self.broker.buy(s, q)
                    self.st["cash"] -= cost
                    self.st["holdings"][s] = self.qty(s) + filled
                    self.st["cost"][s] = self.st["cost"].get(s, 0.0) + cost
                    log.info("COFRE reequilíbrio: comprou %.8f %s (%.2f USDT)", filled, s, cost)


# ------------------------------------------------------------------ carteira completa (backtest)
def portfolio_backtest(data: dict[str, pd.DataFrame], daily: dict[str, pd.DataFrame], cfg: dict,
                       initial: float, start_ts: int, end_ts: int | None = None) -> dict:
    """Bot (1-f) + cofre (f), reequilibrados todo mês, a partir dos retornos diários de cada parte."""
    from .backtest import run

    f = float(cfg["trend_sleeve"]["fraction"])
    r = run(data, cfg, initial * (1 - f), start_ts=start_ts, end_ts=end_ts, close_at_end=True)
    bot = pd.Series(r.equity_curve, index=pd.to_datetime(r.equity_ts, unit="ms", utc=True)).resample("1D").last().ffill()
    sl = backtest(daily, cfg, initial * f, start_ts, end_ts)
    se = sl["equity"].resample("1D").last().ffill()        # alinha por data (00:00 UTC)
    idx = bot.index.intersection(se.index)
    if len(idx) == 0:
        raise ValueError("os dados do bot e do cofre não se sobrepõem no período pedido")
    rb, rs = bot[idx].pct_change().fillna(0), se[idx].pct_change().fillna(0)
    vb, vs, out, prev = initial * (1 - f), initial * f, [], None
    for i, d in enumerate(idx):
        vb *= 1 + rb.iat[i]
        vs *= 1 + rs.iat[i]
        if prev is not None and d.month != prev:
            tot = vb + vs
            vb, vs = tot * (1 - f), tot * f
        prev = d.month
        out.append(vb + vs)
    eq = pd.Series(out, index=idx)
    return {"equity": eq, "retorno": eq.iloc[-1] / initial - 1, "queda_max": float((1 - eq / eq.cummax()).max()),
            "bot": r, "cofre_ordens": len(sl["trades"])}
