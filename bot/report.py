"""Relatório de análise de um par: o "checklist" da estratégia em texto.

Pode ser lido direto ou colado junto do PROMPT_ANALISE.md numa IA.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .strategy import entry_signal


def exit_plan(sig, risk: float, r: dict) -> list[str]:
    mode = r.get("exit_mode", "parcial")
    if mode == "trailing":
        return [f"- Saída: trailing stop = máxima desde a entrada − {r['trailing_atr']} ATR (só sobe)"]
    if mode == "alvo":
        return [f"- Alvo fixo ({r.get('target_r', 2.0)}R): {sig.entry + r.get('target_r', 2.0) * risk:.6g}"]
    return [f"- Parcial ({r['partial_fraction']:.0%}) em {r['take_partial_r']}R: {sig.entry + r['take_partial_r'] * risk:.6g}",
            f"- Depois: stop no empate + trailing de {r['trailing_atr']} ATR"]


def analysis_report(symbol: str, df: pd.DataFrame, trend_df: pd.DataFrame, cfg: dict) -> str:
    i = len(df) - 1
    row = df.iloc[i]
    trow = trend_df.iloc[-1]
    sig = entry_signal(df, i, row["trend"], cfg)
    when = datetime.fromtimestamp(int(row["close_ts"]) / 1000, tz=timezone.utc)
    r = cfg["risk"]
    tf_e, tf_t = cfg["timeframes"]["entry"], cfg["timeframes"]["trend"]

    lines = [
        f"# Análise {symbol} — candle fechado em {when:%Y-%m-%d %H:%M} UTC",
        "",
        f"## Tendência ({tf_t}): **{row['trend']}**",
        f"- Preço {trow['close']:.6g} | EMA50 {trow['ema_mid']:.6g} | EMA200 {trow['ema_slow']:.6g}",
        f"- RSI {trow['rsi']:.1f} | ADX {trow['adx']:.1f} | ATR {trow['atr']:.6g}",
        "",
        f"## Tempo gráfico de entrada ({tf_e})",
        f"- Preço {row['close']:.6g} | EMA21 {row['ema_fast']:.6g} | EMA50 {row['ema_mid']:.6g} | EMA200 {row['ema_slow']:.6g}",
        f"- RSI {row['rsi']:.1f} | MACD {row['macd']:.6g} (hist {row['macd_hist']:.6g}) | ADX {row['adx']:.1f}",
        f"- ATR {row['atr']:.6g} ({row['atr'] / row['close']:.2%} do preço) | Volume {row['volume']:.6g} vs média {row['vol_ma']:.6g}",
        f"- Suporte recente (mín {cfg['strategy']['swing_lookback']} candles): {df['low'].iloc[-cfg['strategy']['swing_lookback']:].min():.6g}",
        f"- Resistência (máx {cfg['strategy']['resistance_lookback']} candles): {df['high'].iloc[-cfg['strategy']['resistance_lookback']:].max():.6g}",
        "",
        "## Checklist de entrada",
    ]
    for name, (ok, detail) in sig.checks.items():
        lines.append(f"- [{'x' if ok else ' '}] **{name}** — {detail}")
    lines.append("")
    if sig.ok:
        risk = sig.entry - sig.stop
        lines += [
            "## ✅ SINAL DE COMPRA",
            f"- Entrada: {sig.entry:.6g}",
            f"- Stop loss: {sig.stop:.6g} ({(1 - sig.stop / sig.entry):.2%} abaixo)",
            *exit_plan(sig, risk, r),
            f"- Resistência / alvo estrutural: {sig.target:.6g} (R:R {sig.reward_risk:.2f})",
            f"- Risco por operação: {r['risk_per_trade']:.1%} do capital",
        ]
    else:
        lines += ["## ⏸ SEM ENTRADA", f"Regras que falharam: {', '.join(sig.failed)}",
                  "Aguardar: não operar é uma posição válida."]
    return "\n".join(lines)
