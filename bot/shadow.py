"""Estratégias em OBSERVAÇÃO: o bot acompanha os sinais e registra no diário o que TERIA
acontecido, sem operar nenhum centavo. Serve para testar ideias novas na prática, com risco zero.

Hoje em observação — "lateralização" (reversão à média), testada em PESQUISA.md (seção 10):
  * só quando a tendência DIÁRIA da moeda está LATERAL;
  * entra quando o 4h fecha abaixo da banda de Bollinger inferior (20 períodos, 2 desvios) com RSI < 30;
  * sai quando o preço volta à média de 20 períodos, ou no stop de 2 ATR, ou após 12 velas (~2 dias).
Funcionou em 2023–2026, mas não foi robusta em 2020–2023; por isso fica só observando.
"""
from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger("bot")
ORIGEM = "observacao-lateral"
COST = 0.003          # taxas + slippage ida e volta, igual à pesquisa


def range_signal(df: pd.DataFrame, i: int) -> bool:
    c = df["close"]
    mid = c.rolling(20).mean()
    low = mid - 2 * c.rolling(20).std()
    row = df.iloc[i]
    return bool(row["trend"] == "LATERAL" and row["close"] < low.iloc[i] and row["rsi"] < 30)


class ShadowRange:
    def __init__(self, state: dict, journal=None, mode: str = "paper"):
        self.st = state.setdefault("shadow_range", {})
        self.journal, self.mode = journal, mode

    def on_bar(self, sym: str, df: pd.DataFrame) -> None:
        """Chamado a cada candle de 4h FECHADO do par."""
        i = len(df) - 1
        row = df.iloc[i]
        mid = float(df["close"].rolling(20).mean().iloc[i])
        o = self.st.get(sym)
        if o:                                        # acompanha a operação imaginária
            o["velas"] += 1
            px, why = None, ""
            if float(row["low"]) <= o["stop"]:
                px, why = min(float(row["open"]), o["stop"]), "stop"
            elif float(row["close"]) >= mid:
                px, why = float(row["close"]), "voltou à média"
            elif o["velas"] >= 12:
                px, why = float(row["close"]), "tempo esgotado"
            if px is not None:
                ret = px / o["entrada"] - 1 - COST
                risk = (o["entrada"] - o["stop"]) / o["entrada"]
                log.info("observação lateralização %s: teria saído (%s) com %+.2f%% (não operado)", sym, why, ret * 100)
                if self.journal:
                    self.journal({"origem": ORIGEM, "simbolo": sym, "aberta": o["aberta"],
                                  "fechada": pd.Timestamp(int(row["close_ts"]), unit="ms", tz="UTC").isoformat(),
                                  "entrada": o["entrada"], "saida": px, "pnl": ret, "r": ret / risk if risk else 0.0,
                                  "motivo": why, "features": {"tendencia": str(row["trend"])}})
                del self.st[sym]
            return
        if i >= 30 and range_signal(df, i):
            entry = float(row["close"])
            self.st[sym] = {"entrada": entry, "stop": entry - 2 * float(row["atr"]), "velas": 0,
                            "aberta": pd.Timestamp(int(row["close_ts"]), unit="ms", tz="UTC").isoformat()}
            log.info("observação lateralização %s: sinal a %.6g (só observando, não operado)", sym, entry)
