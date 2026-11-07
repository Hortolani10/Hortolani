"""Acesso à Binance via ccxt + corretora simulada (paper trading)."""
from __future__ import annotations

import logging
import os

import pandas as pd

from .data import drop_open_candle, to_df

log = logging.getLogger("bot")


def make_ccxt(cfg: dict, with_keys: bool):
    import ccxt

    params = {"enableRateLimit": True, "timeout": 60000,
              "options": {"defaultType": "spot", "adjustForTimeDifference": True, "fetchMarkets": ["spot"]}}
    if with_keys:
        params["apiKey"] = os.getenv("BINANCE_API_KEY", "")
        params["secret"] = os.getenv("BINANCE_API_SECRET", "")
    ex = ccxt.binance(params)
    # ccxt ignora as variáveis de proxy do sistema; repassa se existirem
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if proxy:
        ex.httpsProxy = proxy
    # Só dados públicos (sem chave): usa o espelho oficial de dados de mercado da Binance,
    # que funciona mesmo em regiões onde api.binance.com responde 451.
    if not with_keys and cfg.get("market_data_url"):
        ex.urls["api"]["public"] = cfg["market_data_url"]
    if with_keys and cfg.get("testnet", True):
        ex.set_sandbox_mode(True)
    return ex


class Broker:
    """Interface comum para LiveBroker e PaperBroker."""

    def __init__(self, cfg: dict, market_ex):
        self.cfg = cfg
        self.market = market_ex           # usado para candles/preços
        self.market.load_markets()

    # ---- dados de mercado ----
    def candles(self, symbol: str, tf: str, limit: int = 500) -> pd.DataFrame:
        return drop_open_candle(to_df(self.market.fetch_ohlcv(symbol, tf, limit=limit)), tf)

    def price(self, symbol: str) -> float:
        return float(self.market.fetch_ticker(symbol)["last"])

    def amount(self, symbol: str, qty: float) -> float:
        return float(self.market.amount_to_precision(symbol, qty))

    def min_notional(self, symbol: str) -> float:
        lim = self.market.market(symbol).get("limits", {}).get("cost", {}) or {}
        return float(lim.get("min") or 10.0)

    # ---- a implementar ----
    def usdt_free(self) -> float: ...
    def buy(self, symbol: str, qty: float) -> tuple[float, float, float]: ...   # (qty, preço médio, custo)
    def sell(self, symbol: str, qty: float) -> tuple[float, float]: ...         # (preço médio, recebido)
    def place_stop(self, symbol: str, qty: float, stop: float) -> str | None: ...
    def cancel(self, symbol: str, order_id: str | None) -> tuple[float, float]: ...   # (qtd já vendida, USDT recebido)
    def base_balance(self, symbol: str) -> float | None: ...   # saldo total da moeda (None = não verificável)
    def stop_active(self, symbol: str, order_id: str | None) -> bool: ...
    def stop_filled(self, symbol: str, order_id: str | None, stop: float) -> tuple[bool, float, float]: ...


class PaperBroker(Broker):
    """Usa preços reais da Binance, mas as ordens são simuladas."""

    def __init__(self, cfg: dict, market_ex, state: dict):
        super().__init__(cfg, market_ex)
        self.state = state
        self.state.setdefault("paper_cash", float(cfg["paper"]["initial_balance"]))
        self.fee, self.slip = cfg["fees"]["taker"], cfg["fees"]["slippage"]

    def usdt_free(self) -> float:
        return self.state["paper_cash"]

    def buy(self, symbol, qty):
        px = self.price(symbol) * (1 + self.slip)
        cost = qty * px * (1 + self.fee)
        self.state["paper_cash"] -= cost
        return qty, px, cost

    def sell(self, symbol, qty, px: float | None = None):
        px = (px or self.price(symbol)) * (1 - self.slip)
        got = qty * px * (1 - self.fee)
        self.state["paper_cash"] += got
        return px, got

    def place_stop(self, symbol, qty, stop):
        return "paper-stop"

    def cancel(self, symbol, order_id):
        return 0.0, 0.0

    def base_balance(self, symbol):
        return None

    def stop_active(self, symbol, order_id):
        return bool(order_id)

    def stop_filled(self, symbol, order_id, stop):
        px = self.price(symbol)
        return (px <= stop, px, 0.0)


class LiveBroker(Broker):
    """Ordens reais. Candles para a ANÁLISE vêm do mercado real (`market_ex`, histórico completo);
    ordens e saldo vão para `trade_ex` (testnet ou conta real). O stop fica REGISTRADO NA BINANCE (STOP_LOSS_LIMIT), então
    a posição continua protegida mesmo se o bot cair ou a internet falhar."""

    def __init__(self, cfg: dict, market_ex, trade_ex, state: dict | None = None):
        super().__init__(cfg, market_ex)
        self.ex = trade_ex
        self.ex.load_markets()
        # Orçamento: o bot só usa até `budget_usdt`, mesmo que a conta tenha mais.
        # Funciona como um caixa próprio: compras tiram, vendas devolvem (com o resultado).
        self.state = state if state is not None else {}
        budget = (cfg.get("live") or {}).get("budget_usdt")
        self.budget = float(budget) if budget else None
        if self.budget is not None:
            self.state.setdefault("live_cash", self.budget)
            log.info("Orçamento do bot: %.2f USDT (caixa atual do bot: %.2f)", self.budget, self.state["live_cash"])

    def price(self, symbol: str) -> float:
        """Preço da corretora onde as ordens são executadas (testnet ou real)."""
        return float(self.ex.fetch_ticker(symbol)["last"])

    def _cash(self, delta: float) -> None:
        if self.budget is not None:
            self.state["live_cash"] = float(self.state.get("live_cash", self.budget)) + delta

    def usdt_free(self) -> float:
        real = float(self.ex.fetch_balance()["free"].get("USDT", 0.0))
        if self.budget is None:
            return real
        return max(0.0, min(real, float(self.state.get("live_cash", self.budget))))

    def buy(self, symbol, qty):
        o = self.ex.create_order(symbol, "market", "buy", self.amount(symbol, qty))
        o = self.ex.fetch_order(o["id"], symbol)
        filled = float(o["filled"])
        avg = float(o["average"] or o["price"])
        fee_base = sum(float(f["cost"]) for f in o.get("fees") or [] if f.get("currency") == symbol.split("/")[0])
        self._cash(-float(o["cost"]))
        return filled - fee_base, avg, float(o["cost"])

    def sell(self, symbol, qty, px: float | None = None):
        o = self.ex.create_order(symbol, "market", "sell", self.amount(symbol, qty))
        o = self.ex.fetch_order(o["id"], symbol)
        fee_q = sum(float(f["cost"]) for f in o.get("fees") or [] if f.get("currency") == "USDT")
        self._cash(float(o["cost"]) - fee_q)
        return float(o["average"] or o["price"]), float(o["cost"]) - fee_q

    def place_stop(self, symbol, qty, stop):
        limit = float(self.ex.price_to_precision(symbol, stop * 0.995))
        stop_p = float(self.ex.price_to_precision(symbol, stop))
        o = self.ex.create_order(
            symbol, "STOP_LOSS_LIMIT", "sell", self.amount(symbol, qty), limit,
            {"stopPrice": stop_p, "timeInForce": "GTC"},
        )
        return str(o["id"])

    def cancel(self, symbol, order_id):
        """Cancela o stop e devolve o que ele JÁ tinha vendido (execução parcial)."""
        if not order_id:
            return 0.0, 0.0
        try:
            self.ex.cancel_order(order_id, symbol)
        except Exception as e:  # já executada/cancelada
            log.warning("cancelar stop %s %s: %s", symbol, order_id, e)
        try:
            o = self.ex.fetch_order(order_id, symbol)
            filled = float(o.get("filled") or 0)
            fee_q = sum(float(f["cost"]) for f in o.get("fees") or [] if f.get("currency") == "USDT")
            got = float(o.get("cost") or 0) - fee_q
            if filled > 0:
                self._cash(got)
            return filled, got
        except Exception as e:
            log.warning("conferir stop cancelado %s %s: %s", symbol, order_id, e)
            return 0.0, 0.0

    def base_balance(self, symbol):
        b = self.ex.fetch_balance()
        return float((b.get("total") or {}).get(symbol.split("/")[0], 0.0))

    def stop_active(self, symbol, order_id):
        if not order_id:
            return False
        try:
            return self.ex.fetch_order(order_id, symbol)["status"] in ("open", "closed")
        except Exception:
            return False

    def check_key_permissions(self, real_money: bool) -> None:
        """Recusa operar com dinheiro real se a chave da API puder SACAR."""
        if not real_money:
            return
        r = self.ex.sapi_get_account_apirestrictions()
        if str(r.get("enableWithdrawals")).lower() == "true":
            raise SystemExit("SEGURANÇA: esta API key tem permissão de SAQUE. Crie outra chave só com "
                             "'Spot Trading' habilitado. O bot não vai operar com essa chave.")
        if str(r.get("enableInternalTransfer", "false")).lower() == "true" or \
           str(r.get("permitsUniversalTransfer", "false")).lower() == "true":
            raise SystemExit("SEGURANÇA: esta API key permite transferências. Desabilite e tente de novo.")
        if str(r.get("ipRestrict")).lower() != "true":
            log.warning("SEGURANÇA: a API key não está restrita por IP. Recomendado restringir ao IP do servidor.")

    def stop_filled(self, symbol, order_id, stop):
        if not order_id:
            return False, 0.0, 0.0
        o = self.ex.fetch_order(order_id, symbol)
        if o["status"] == "closed":
            fee_q = sum(float(f["cost"]) for f in o.get("fees") or [] if f.get("currency") == "USDT")
            got = float(o["cost"]) - fee_q
            self._cash(got)
            return True, float(o["average"] or o["price"]), got
        return False, 0.0, 0.0
