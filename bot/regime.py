"""Termômetro do mercado (0-100): quanto o mercado cripto está a favor de comprar.

Ideia da skill crypto-regime-analyzer, mas calculada só com os candles que o bot
já baixa da Binance (sem CoinGecko, sem chave, funciona no servidor):

  50% amplitude  — % das moedas da lista com tendência DIÁRIA de alta
  30% BTC        — tendência diária do BTC em alta
  20% força BTC  — BTC fechou acima da EMA50 do tempo gráfico de entrada

Uso no bot (opcional, `termometro.enabled`): nota abaixo de `limite` -> arrisca
`fator` (ex.: metade) por operação. Não bloqueia entradas, só diminui o tamanho.
Teste de 6 anos: retorno 124 -> 126 e queda máxima 16,2% -> 14,4% (PESQUISA.md, seção 14).
"""
from __future__ import annotations

import pandas as pd

from .strategy import ALTA

PESOS = (0.5, 0.3, 0.2)


def rotulo(nota: float) -> str:
    if nota >= 60:
        return "favorável (risk-on)"
    if nota >= 40:
        return "neutro"
    return "defensivo (risk-off)"


def nota_atual(dfs: dict[str, pd.DataFrame], btc: pd.DataFrame | None) -> dict | None:
    """Nota no último candle fechado. `dfs`: símbolo -> DataFrame de prepare()."""
    trends = [str(df["trend"].iloc[-1]) for df in dfs.values() if len(df)]
    trends = [t for t in trends if t != "SEM_DADOS"]
    if not trends:
        return None
    amp = sum(t == ALTA for t in trends) / len(trends)
    if btc is None:
        btc = dfs.get("BTC/USDT")
    if btc is not None and len(btc):
        b = btc.iloc[-1]
        btc_up = float(str(b["trend"]) == ALTA)
        btc_forca = float(b["close"] > b["ema_mid"])
    else:                                   # sem BTC: usa só a amplitude
        btc_up = btc_forca = amp
    nota = 100 * (PESOS[0] * amp + PESOS[1] * btc_up + PESOS[2] * btc_forca)
    return {"nota": round(nota), "rotulo": rotulo(nota), "amplitude": round(amp * 100),
            "moedas_em_alta": sum(t == ALTA for t in trends), "moedas": len(trends),
            "btc_alta": bool(btc_up), "btc_acima_ema50": bool(btc_forca)}


def serie(data: dict[str, pd.DataFrame]) -> pd.Series:
    """A mesma nota candle a candle (para o backtest), indexada por close_ts (ms)."""
    cols = []
    for k, df in data.items():
        t = df["trend"].astype(str)
        v = (t == ALTA).astype(float).where(t != "SEM_DADOS")
        cols.append(pd.Series(v.to_numpy(), index=df["close_ts"].astype("int64"), name=k))
    amp = pd.concat(cols, axis=1).sort_index().ffill().mean(axis=1)
    b = data.get("BTC/USDT")
    if b is not None:
        b = b.set_index(b["close_ts"].astype("int64"))
        up = (b["trend"].astype(str) == ALTA).astype(float).reindex(amp.index).ffill()
        forca = (b["close"] > b["ema_mid"]).astype(float).reindex(amp.index).ffill()
    else:
        up = forca = amp
    return (100 * (PESOS[0] * amp + PESOS[1] * up + PESOS[2] * forca)).fillna(50)


def escala(cfg: dict, nota: float | None) -> float:
    """Multiplicador do risco por operação conforme a nota."""
    t = cfg.get("termometro") or {}
    if not t.get("enabled") or nota is None:
        return 1.0
    return float(t.get("fator", 0.5)) if nota < float(t.get("limite", 40)) else 1.0
