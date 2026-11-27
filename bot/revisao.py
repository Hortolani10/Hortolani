"""Revisão mensal automática: todo dia 1º refaz o teste das saídas com os dados mais novos da Binance
e manda o resultado no Telegram. NÃO muda nada no bot: só informa se a regra atual continua boa.

Uso:  python -m bot.revisao            (fica esperando o dia 1º, 09:10 de Brasília, e repete todo mês)
      python -m bot.revisao --agora    (roda uma vez agora e sai)

Só usa dados públicos (sem chave da Binance). No Telegram só ENVIA mensagem (não lê comandos),
então não conflita com o bot principal.
"""
from __future__ import annotations

import copy
import logging
import sys
import time
from datetime import datetime, timedelta, timezone

from . import backtest as bt
from .__main__ import load_config
from .data import apply_btc_filter, fetch_history, prepare
from .exchange import make_ccxt
from .notify import Telegram

log = logging.getLogger("bot.revisao")
BR = timezone(timedelta(hours=-3))
DIA = 86_400_000
CONFIG = "/app/config.yaml"


def pct(v: float) -> str:
    return f"{v * 100:+.1f}%".replace(".", ",")


def variantes(cfg: dict) -> list[tuple[str, dict]]:
    """A regra atual e as vizinhas que vale comparar todo mês."""
    def com(**risk):
        c = copy.deepcopy(cfg)
        c["risk"].update(risk)
        return c
    return [("Regra atual (trava +5%)", cfg),
            ("Só stop móvel (sem trava)", com(trava_gatilho=None)),
            ("Trava em +4%", com(trava_gatilho=0.04, trava_lucro=0.04)),
            ("Trava em +6%", com(trava_gatilho=0.06, trava_lucro=0.06))]


def dados(cfg: dict, dias: int = 640) -> dict:
    ex = make_ccxt({**cfg, "testnet": False}, with_keys=False)
    desde = int(time.time() * 1000) - dias * DIA
    tf_e, tf_t = cfg["timeframes"]["entry"], cfg["timeframes"]["trend"]
    out = {}
    for s in cfg["symbols"]:
        try:
            e, t = fetch_history(ex, s, tf_e, desde), fetch_history(ex, s, tf_t, desde)
            if len(e) > 300 and len(t) > 210:
                out[s] = prepare(e, t, cfg)
        except Exception as err:  # uma moeda com problema não derruba a revisão
            log.warning("revisão: sem dados de %s (%s)", s, err)
    return apply_btc_filter(out, cfg, out.get("BTC/USDT"))


def revisar(cfg: dict) -> str:
    data = dados(cfg)
    fim = int(data["BTC/USDT"]["close_ts"].iloc[-1])
    per = {"12 meses": fim - 365 * DIA, "3 meses": fim - 91 * DIA}
    res = {}
    for nome, c in variantes(cfg):
        res[nome] = {p: bt.run(data, c, 1000.0, start_ts=s0, close_at_end=True).summary() for p, s0 in per.items()}
    linhas = [f"📊 <b>Revisão mensal das regras</b>",
              f"<i>dados reais da Binance até {datetime.fromtimestamp(fim / 1000, BR):%d/%m/%Y}</i>", ""]
    for nome, r in res.items():
        a, b = r["12 meses"], r["3 meses"]
        linhas.append(f"{'⭐' if nome.startswith('Regra atual') else '•'} {nome}\n"
                      f"   12m: <code>{pct(a['retorno_total'])}</code> ({a['operacoes']} ops) · 3m: <code>{pct(b['retorno_total'])}</code>")
    atual = res["Regra atual (trava +5%)"]
    melhor = [n for n, r in res.items() if not n.startswith("Regra atual")
              and r["12 meses"]["retorno_total"] > atual["12 meses"]["retorno_total"] + 0.02
              and r["3 meses"]["retorno_total"] > atual["3 meses"]["retorno_total"] + 0.01]
    linhas.append("")
    linhas.append(f"⚠️ Vale conversar: <b>{', '.join(melhor)}</b> foi melhor nos dois períodos." if melhor
                  else "✅ A regra atual continua entre as melhores. Nada a mudar.")
    linhas.append("<i>Só informativo: nada é alterado automaticamente.</i>")
    return "\n".join(linhas)


def proxima(agora: datetime) -> datetime:
    """Dia 1º do próximo mês, 09:10 (Brasília)."""
    a = agora.astimezone(BR)
    alvo = a.replace(day=1, hour=9, minute=10, second=0, microsecond=0)
    if alvo <= a:
        alvo = (alvo + timedelta(days=32)).replace(day=1)
    return alvo


def main(argv: list[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    tg = Telegram()
    while True:
        if "--agora" not in argv:
            alvo = proxima(datetime.now(timezone.utc))
            log.info("revisão mensal: próxima em %s", alvo.strftime("%d/%m/%Y %H:%M"))
            while datetime.now(timezone.utc) < alvo:
                time.sleep(min(3600.0, max(1.0, (alvo - datetime.now(timezone.utc)).total_seconds())))
        try:
            texto = revisar(load_config(CONFIG))
            log.info("revisão mensal pronta:\n%s", texto)
            tg.send(texto, dedupe_s=0, html=True)
        except Exception:
            log.exception("revisão mensal falhou")
        if "--agora" in argv:
            return


if __name__ == "__main__":
    main(sys.argv[1:])
