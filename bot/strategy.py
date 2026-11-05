"""Regras de tendência, entrada e saída.

Filosofia: só comprar a favor da tendência do tempo gráfico maior, num
pullback (correção) que já mostrou retomada, com momentum saudável, sem
estar esticado e com espaço até a próxima resistência. Toda entrada nasce
com stop definido e tamanho calculado pelo risco.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

ALTA, BAIXA, LATERAL = "ALTA", "BAIXA", "LATERAL"


def trend_series(df: pd.DataFrame) -> pd.Series:
    """Classifica a tendência candle a candle (usar no tempo gráfico maior).

    ALTA:  preço > EMA200, EMA50 > EMA200 e EMA200 inclinada para cima
    BAIXA: preço < EMA200 e EMA50 < EMA200
    resto: LATERAL
    """
    slope_up = df["ema_slow"] > df["ema_slow"].shift(5)
    up = (df["close"] > df["ema_slow"]) & (df["ema_mid"] > df["ema_slow"]) & slope_up
    down = (df["close"] < df["ema_slow"]) & (df["ema_mid"] < df["ema_slow"])
    out = pd.Series(LATERAL, index=df.index)
    out[up] = ALTA
    out[down] = BAIXA
    out[df["ema_slow"].isna()] = LATERAL
    return out


@dataclass
class Signal:
    ok: bool
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0       # resistência estrutural usada para medir o R:R
    reward_risk: float = 0.0
    checks: dict = field(default_factory=dict)   # nome da regra -> (passou?, detalhe)

    @property
    def failed(self) -> list[str]:
        return [k for k, (ok, _) in self.checks.items() if not ok]


def prefilter(df: pd.DataFrame, cfg: dict) -> pd.Series:
    """Versão vetorizada (rápida) das regras de entrada, exceto o R:R.

    É um SUPERCONJUNTO de entry_signal().ok: onde dá False, entry_signal também
    daria False. O backtest só chama entry_signal nos candles marcados aqui.
    """
    s = cfg["strategy"]
    pl = s["pullback_lookback"]
    touched = (df["low"] <= df["ema_fast"] * 1.002).astype(float).rolling(pl).max() == 1
    held = (df["close"] > df["ema_mid"]).astype(float).rolling(pl).min() == 1
    m = (
        (df["trend"] == ALTA)
        & (df["ema_fast"] > df["ema_mid"]) & (df["ema_mid"] > df["ema_slow"])
        & touched & held
        & (df["close"] > df["ema_fast"]) & (df["close"] > df["open"]) & (df["close"] > df["high"].shift(1))
        & (df["rsi"] >= s["rsi_min"]) & (df["rsi"] <= s["rsi_max"])
        & (df["macd_hist"] > df["macd_hist"].shift(1)) & (df["macd"] > 0)
        & (df["adx"] >= s["adx_min"])
        & (df["volume"] >= df["vol_ma"] * s["volume_factor"])
        & ((df["close"] - df["ema_fast"]) <= s["max_extension_atr"] * df["atr"])
    )
    if s.get("btc_filter") and "btc_trend" in df.columns:
        m &= df["btc_trend"] == ALTA
    m.iloc[: max(s["ema_slow"], s["resistance_lookback"]) + 5] = False
    return m.fillna(False)


def _session(hour: int) -> str:
    if hour < 8:
        return "Ásia/China"
    if hour < 13:
        return "Europa"
    if hour < 21:
        return "EUA"
    return "fim do dia"


def entry_features(df: pd.DataFrame, i: int) -> dict:
    """Retrato do mercado no candle do sinal, guardado no diário para o bot aprender."""
    row = df.iloc[i]
    ts = pd.Timestamp(int(row["close_ts"]), unit="ms", tz="UTC")
    return {
        "adx": round(float(row["adx"]), 1),
        "atr_pct": round(float(row["atr"] / row["close"] * 100), 2),
        "rsi": round(float(row["rsi"]), 1),
        "volume_rel": round(float(row["volume"] / row["vol_ma"]), 2) if row["vol_ma"] else None,
        "dist_ema21_atr": round(float((row["close"] - row["ema_fast"]) / row["atr"]), 2),
        "hora_utc": int(ts.hour),
        "sessao": _session(int(ts.hour)),
        "dia_semana": int(ts.dayofweek),
        "tendencia": str(row["trend"]),
        "btc_tendencia": str(row["btc_trend"]) if "btc_trend" in row else None,
    }


def entry_signal(df: pd.DataFrame, i: int, trend: str, cfg: dict) -> Signal:
    """Avalia se o candle FECHADO de índice `i` gera uma entrada de compra."""
    s, r = cfg["strategy"], cfg["risk"]
    need = max(s["ema_slow"], s["resistance_lookback"]) + 5
    if i < need:
        return Signal(False, checks={"dados": (False, f"histórico insuficiente ({i} < {need})")})

    row, prev = df.iloc[i], df.iloc[i - 1]
    close, a = float(row["close"]), float(row["atr"])
    c: dict[str, tuple[bool, str]] = {}

    c["tendencia_maior"] = (trend == ALTA, f"tendência do TF maior = {trend}")
    if s.get("btc_filter") and "btc_trend" in df.columns:
        bt = row["btc_trend"]
        c["mercado_btc"] = (bt == ALTA, f"tendência do BTC = {bt} (altcoins só com BTC em alta)")
    c["emas_alinhadas"] = (
        row["ema_fast"] > row["ema_mid"] > row["ema_slow"],
        f"EMA{s['ema_fast']}={row['ema_fast']:.4f} EMA{s['ema_mid']}={row['ema_mid']:.4f} EMA{s['ema_slow']}={row['ema_slow']:.4f}",
    )

    win = df.iloc[i - s["pullback_lookback"] + 1 : i + 1]
    touched = bool((win["low"] <= win["ema_fast"] * 1.002).any())
    held = bool((win["close"] > win["ema_mid"]).all())
    c["pullback"] = (touched and held, f"tocou EMA rápida={touched}, segurou EMA média={held}")

    c["gatilho"] = (
        close > row["ema_fast"] and close > row["open"] and close > prev["high"],
        "candle de alta fechando acima da EMA rápida e da máxima anterior",
    )
    c["rsi"] = (s["rsi_min"] <= row["rsi"] <= s["rsi_max"], f"RSI={row['rsi']:.1f} (faixa {s['rsi_min']}-{s['rsi_max']})")
    c["macd"] = (
        row["macd_hist"] > prev["macd_hist"] and row["macd"] > 0,
        f"MACD={row['macd']:.5f} (precisa > 0), histograma {prev['macd_hist']:.5f} -> {row['macd_hist']:.5f} (precisa subir)",
    )
    c["adx"] = (row["adx"] >= s["adx_min"], f"ADX={row['adx']:.1f} (mín {s['adx_min']})")
    c["volume"] = (
        row["volume"] >= row["vol_ma"] * s["volume_factor"],
        f"vol={row['volume']:.2f} média={row['vol_ma']:.2f}",
    )
    ext = (close - row["ema_fast"]) / a if a > 0 else 99
    c["nao_esticado"] = (ext <= s["max_extension_atr"], f"{ext:.2f} ATR acima da EMA rápida (máx {s['max_extension_atr']})")

    # Stop técnico: abaixo do fundo recente, limitado entre stop_min_atr e stop_max_atr
    swing_low = float(df["low"].iloc[i - s["swing_lookback"] + 1 : i + 1].min())
    stop = swing_low - 0.2 * a
    dist = close - stop
    dist = min(max(dist, r["stop_min_atr"] * a), r["stop_max_atr"] * a)
    stop = close - dist

    # Espaço até a resistência (topo anterior). Rompimento de topo = espaço livre.
    hist = df["high"].iloc[i - s["resistance_lookback"] : i - s["pullback_lookback"] + 1]
    resistance = float(hist.max())
    if resistance <= close:
        rr, target = float("inf"), close + 3 * dist
    else:
        rr, target = (resistance - close) / dist, resistance
    c["reward_risk"] = (rr >= r["min_reward_risk"], f"R:R até resistência {resistance:.4f} = {rr:.2f} (mín {r['min_reward_risk']})")

    ok = all(v for v, _ in c.values())
    return Signal(ok, entry=close, stop=stop, target=target, reward_risk=rr, checks=c)


@dataclass
class Position:
    symbol: str
    qty: float
    entry: float
    stop: float
    initial_risk: float          # entry - stop inicial (por unidade)
    opened_at: str
    highest: float = 0.0
    partial_done: bool = False
    stop_order_id: str | None = None
    features: dict = field(default_factory=dict)   # retrato do mercado na entrada (diário de operações)
    cost: float = 0.0            # USDT gasto na compra (com taxa)
    proceeds: float = 0.0        # USDT recebido nas vendas (já líquido de taxa)
    reasons: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        return cls(**d)


@dataclass
class Action:
    kind: str        # "sell" (venda parcial/total) | "move_stop"
    qty: float = 0.0
    price: float = 0.0
    reason: str = ""


def manage_position(pos: Position, candle: pd.Series, trend: str, cfg: dict) -> list[Action]:
    """Gerencia uma posição aberta com o candle fechado mais recente.

    Ordem conservadora (assume o pior dentro do candle):
      1) stop atingido -> sai tudo no stop (ou na abertura, se abriu abaixo)
      2) alvo parcial (take_partial_r * R) -> vende fração, stop no empate
      3) trailing stop (máxima - N*ATR) só sobe, nunca desce
      4) saída por perda de tendência: fechamento abaixo da EMA média
         ou tendência do TF maior virou BAIXA
    Modifica `pos` in-place e devolve as ações a executar.
    """
    r = cfg["risk"]
    fee = cfg["fees"]["taker"]
    actions: list[Action] = []
    o, h, l, c, a = (float(candle[k]) for k in ("open", "high", "low", "close", "atr"))

    if l <= pos.stop:
        px = min(o, pos.stop)
        actions.append(Action("sell", pos.qty, px, "stop"))
        pos.qty = 0.0
        return actions

    pos.highest = max(pos.highest, h)

    mode = r.get("exit_mode", "parcial")

    if mode == "alvo":                       # alvo fixo em target_r, sem trailing
        target = pos.entry + r.get("target_r", 2.0) * pos.initial_risk
        if h >= target:
            actions.append(Action("sell", pos.qty, max(o, target), f"alvo {r.get('target_r', 2.0)}R"))
            pos.qty = 0.0
            return actions

    elif mode == "trailing":                 # sem parcial: trailing desde a entrada
        trail = pos.highest - r["trailing_atr"] * a
        if trail > pos.stop:
            pos.stop = trail
            actions.append(Action("move_stop", price=pos.stop, reason="trailing"))

    else:                                    # "parcial": parcial + empate + trailing
        if not pos.partial_done:
            target = pos.entry + r["take_partial_r"] * pos.initial_risk
            if h >= target:
                q = pos.qty * r["partial_fraction"]
                actions.append(Action("sell", q, max(o, target), f"parcial {r['take_partial_r']}R"))
                pos.qty -= q
                pos.partial_done = True
                if r["breakeven_after_partial"]:
                    be = pos.entry * (1 + 2 * fee)
                    if be > pos.stop:
                        pos.stop = be
                        actions.append(Action("move_stop", price=pos.stop, reason="empate (breakeven)"))
        if pos.partial_done:
            trail = pos.highest - r["trailing_atr"] * a
            if trail > pos.stop:
                pos.stop = trail
                actions.append(Action("move_stop", price=pos.stop, reason="trailing"))

    if not r.get("trend_exit", True):
        return actions

    if c < float(candle["ema_mid"]) or trend == BAIXA:
        why = "fechou abaixo da EMA média" if c < float(candle["ema_mid"]) else "tendência maior virou BAIXA"
        actions.append(Action("sell", pos.qty, c, why))
        pos.qty = 0.0

    return actions
