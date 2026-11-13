"""Mensagens do Telegram em formato de cartão (HTML do Telegram: <b>, <i>, <code>).

Uma mensagem por evento: compra (com stop, alvo e risco) e operação fechada (com resultado).
Os valores vêm do bot; o texto é escapado para o Telegram não interpretar nada como formatação.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape

SETUPS = {
    "tendencia": ("Tendência (pullback)", "pullback na EMA21 a favor da tendência"),
    "lateral": ("Lateralização", "preço abaixo da banda inferior com RSI baixo"),
    "rompimento": ("Rompimento", "fechou acima da máxima de 20 candles com volume forte"),
    "reversao_rsi": ("Reversão do RSI", "RSI saiu da sobrevenda com candle de alta"),
    "padrao_suporte": ("Padrão no suporte", "engolfo de alta ou martelo perto do suporte"),
    "divergencia": ("Divergência no RSI", "divergência de alta no RSI"),
    "pullback_livre": ("Pullback livre", "pullback na EMA21 sem exigir tendência"),
}
CURTO = {   # padrões em poucas palavras para caber no celular
    "engolfo_alta": "engolfo de alta", "engolfo_baixa": "engolfo de baixa", "martelo": "martelo",
    "estrela_cadente": "estrela cadente", "doji": "doji", "tres_soldados": "3 altas seguidas",
    "rompimento_20": "rompeu máx. 20", "perda_20": "perdeu mín. 20", "perto_suporte": "no suporte",
    "perto_resistencia": "na resistência", "fundo_duplo": "fundo duplo", "divergencia_alta": "divergência RSI",
    "volume_explosivo": "volume 2×", "squeeze": "bandas apertadas", "acima_ema200": "acima EMA200",
    "rsi_sobrevenda": "RSI < 30", "rsi_sobrecompra": "RSI > 70",
}


def num(v: float, casas: int | None = None) -> str:
    """Número no padrão brasileiro (1.234,56). Preços pequenos ganham mais casas."""
    auto = casas is None
    if auto:
        a = abs(v)
        casas = 2 if a >= 100 else 4 if a >= 1 else 6
    s = f"{v:,.{casas}f}"
    if auto and "." in s:                      # tira zeros sobrando, mas deixa pelo menos 2 casas
        inteiro, dec = s.split(".")
        s = inteiro + "." + (dec.rstrip("0") + "00")[:max(2, len(dec.rstrip("0")))]
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def sinal(v: float, casas: int = 2) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + num(abs(v), casas)


def nome_bot(cfg: dict) -> str:
    inst = str(cfg.get("instancia") or "")
    nome = "Bot principal" if not inst else inst.replace("aprendiz-", "Aprendiz ").replace("ativo", "Bot ativo")
    modo = cfg.get("mode")
    if modo == "live":
        selo = "🧪 testnet" if cfg.get("testnet", True) else "💰 DINHEIRO REAL"
    else:
        selo = "📝 simulação"
    return f"{escape(nome)} · {selo}"


def _duracao(aberta: str) -> str:
    try:
        ini = datetime.fromisoformat(aberta)
        if ini.tzinfo is None:
            ini = ini.replace(tzinfo=timezone.utc)
        h = (datetime.now(timezone.utc) - ini).total_seconds() / 3600
    except (TypeError, ValueError):
        return ""
    if h < 1:
        return f"{max(1, round(h * 60))} min"
    if h < 48:
        return f"{h:.0f} h"
    return f"{h / 24:.1f} dias".replace(".", ",")


def compra(cfg: dict, simbolo: str, setup: str, entrada: float, stop: float, qtd: float,
           alvo: float | None, padroes: list[str]) -> str:
    moeda = escape(simbolo.split("/")[0])
    titulo, desc = SETUPS.get(setup, (setup, ""))
    risco = qtd * (entrada - stop)
    linhas = [f"🟢 <b>COMPRA {moeda}</b>",
              f"<i>{escape(nome_bot(cfg))}</i>",
              "",
              f"📌 <b>{escape(titulo)}</b>" + (f" — {escape(desc)}" if desc else ""),
              f"💵 Entrada <code>{num(entrada)}</code>",
              f"🛑 Stop <code>{num(stop)}</code>  ({sinal((stop / entrada - 1) * 100, 1)}%)"]
    r = cfg.get("risk") or {}
    if setup == "lateral":
        linhas.append(f"🎯 Saída: volta à média" + (f" ~<code>{num(alvo)}</code>" if alvo else ""))
    elif r.get("exit_mode") == "alvo" and alvo:
        linhas.append(f"🎯 Alvo <code>{num(alvo)}</code>  ({sinal((alvo / entrada - 1) * 100, 1)}%)")
    elif r.get("exit_mode") == "trailing":
        linhas.append(f"🎯 Saída: stop móvel ({num(float(r.get('trailing_atr', 3)), 1).rstrip('0').rstrip(',')} ATR), sobe junto")
    linhas.append(f"⚖️ Risco {num(risco, 2)} USDT · posição {num(qtd * entrada, 2)} USDT")
    if padroes:
        linhas.append("📐 " + escape(" · ".join(CURTO.get(p, p) for p in padroes)))
    return "\n".join(linhas)


def fechou(cfg: dict, simbolo: str, setup: str, entrada: float, saida: float | None, pnl: float,
           r_mult: float, motivo: str, aberta: str) -> str:
    moeda = escape(simbolo.split("/")[0])
    if r_mult >= 0.15:
        icone, rotulo = "✅", "GANHO"
    elif r_mult <= -0.15:
        icone, rotulo = "❌", "PERDA"
    else:
        icone, rotulo = "➖", "EMPATE"
    titulo = SETUPS.get(setup, (setup, ""))[0]
    m = (motivo or "").lower()
    saiu = ("no alvo" if "alvo" in m else "no stop" if "stop" in m else "por tempo" if "tempo" in m
            else "na volta à média" if "média" in m else escape(motivo or "—"))
    linhas = [f"{icone} <b>{rotulo} {moeda}  {sinal(pnl)} USDT</b>  ({sinal(r_mult)}R)",
              f"<i>{escape(nome_bot(cfg))}</i>",
              "",
              f"📌 {escape(titulo)} · saiu {saiu}"]
    if saida:
        linhas.append(f"💵 <code>{num(entrada)}</code> → <code>{num(saida)}</code>  ({sinal((saida / entrada - 1) * 100, 2)}%)")
    d = _duracao(aberta)
    if d:
        linhas.append(f"⏱ durou {d}")
    return "\n".join(linhas)
