"""Estratégia de TENDÊNCIA do bot Hortolani reescrita no Freqtrade, só para conferir o simulador.

Mesmas regras do bot (bot/strategy.py): tendência diária da moeda e do BTC em ALTA, pullback na
EMA21 com gatilho, RSI 45-68, MACD > 0 subindo, ADX >= 20, volume >= média, não esticado;
stop no fundo de 10 candles - 0,2 ATR (entre 1 e 3 ATR); stop móvel = máxima desde a entrada - 3 ATR;
risco de 1% por operação, posição máxima de 25%. Indicadores: o mesmo código do bot (bot/indicators.py),
para comparar o MOTOR (execução, stops, tamanho), não a biblioteca de indicadores.
"""
import sys
from datetime import datetime, timedelta

import pandas as pd
from freqtrade.strategy import IStrategy, informative, stoploss_from_absolute

sys.path.insert(0, "/home/user/Hortolani")
from bot.__main__ import load_config  # noqa: E402
from bot.indicators import add_all  # noqa: E402
from bot.strategy import ALTA, trend_series  # noqa: E402

CFG = load_config("/home/user/Hortolani/config.yaml")
S, R = CFG["strategy"], CFG["risk"]


def _tendencia(df: pd.DataFrame) -> pd.Series:
    base = df[["date", "open", "high", "low", "close", "volume"]].copy()
    base["ts"] = base["date"].astype("int64") // 10**6
    return trend_series(add_all(base, CFG)).values


class HortolaniTendencia(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "4h"
    can_short = False
    minimal_roi = {"0": 100}
    stoploss = -0.99
    use_custom_stoploss = True
    process_only_new_candles = True
    startup_candle_count = 260

    @informative("1d")
    def populate_indicators_1d(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df["tend"] = _tendencia(df)
        return df

    @informative("1d", "BTC/{stake}")
    def populate_indicators_btc_1d(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df["tend"] = _tendencia(df)
        return df

    def populate_indicators(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        base = df[["date", "open", "high", "low", "close", "volume"]].copy()
        base["ts"] = base["date"].astype("int64") // 10**6
        ind = add_all(base, CFG)
        for c in ("ema_fast", "ema_mid", "ema_slow", "rsi", "macd", "macd_hist", "adx", "atr", "vol_ma"):
            df[c] = ind[c].values
        pl = S["pullback_lookback"]
        df["tocou"] = (df["low"] <= df["ema_fast"] * 1.002).astype(float).rolling(pl).max() == 1
        df["segurou"] = (df["close"] > df["ema_mid"]).astype(float).rolling(pl).min() == 1
        swing = df["low"].rolling(S["swing_lookback"]).min() - 0.2 * df["atr"]
        dist = (df["close"] - swing).clip(lower=R["stop_min_atr"] * df["atr"], upper=R["stop_max_atr"] * df["atr"])
        df["stop_ini"] = df["close"] - dist
        return df

    def populate_entry_trend(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        c = (
            (df["tend_1d"] == ALTA) & (df["btc_usdt_tend_1d"] == ALTA)
            & (df["ema_fast"] > df["ema_mid"]) & (df["ema_mid"] > df["ema_slow"])
            & df["tocou"] & df["segurou"]
            & (df["close"] > df["ema_fast"]) & (df["close"] > df["open"]) & (df["close"] > df["high"].shift(1))
            & (df["rsi"] >= S["rsi_min"]) & (df["rsi"] <= S["rsi_max"])
            & (df["macd_hist"] > df["macd_hist"].shift(1)) & (df["macd"] > 0)
            & (df["adx"] >= S["adx_min"])
            & (df["volume"] >= df["vol_ma"] * S["volume_factor"])
            & ((df["close"] - df["ema_fast"]) <= S["max_extension_atr"] * df["atr"])
        )
        df.loc[c, "enter_long"] = 1
        return df

    def populate_exit_trend(self, df: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df["exit_long"] = 0
        return df

    def _fechados(self, pair: str, ate: datetime) -> pd.DataFrame:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        # só candles que já FECHARAM antes de `ate` (sem olhar o futuro)
        return df[df["date"] + timedelta(hours=4) <= ate]

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake, min_stake, max_stake,
                            leverage, entry_tag, side, **kwargs):
        df = self._fechados(pair, current_time)
        if df.empty:
            return 0
        stop = float(df["stop_ini"].iloc[-1])
        fee = self.config["fee"]
        per_unit = (current_rate - stop) + current_rate * (2 * fee)
        if per_unit <= 0:
            return 0
        eq = self.wallets.get_total_stake_amount()
        stake = min(eq * R["risk_per_trade"] / per_unit * current_rate, eq * R["max_position_pct"])
        return max(0.0, min(stake, max_stake))

    def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, after_fill, **kwargs):
        df = self._fechados(pair, current_time)
        sinal = df[df["date"] + timedelta(hours=4) <= trade.open_date_utc]
        if sinal.empty:
            return None
        stop = float(sinal["stop_ini"].iloc[-1])
        apos = df[df["date"] >= trade.open_date_utc]
        if not apos.empty:
            trail = float(apos["high"].max()) - R["trailing_atr"] * float(apos["atr"].iloc[-1])
            stop = max(stop, trail)
        return stoploss_from_absolute(stop, current_rate, is_short=False)
