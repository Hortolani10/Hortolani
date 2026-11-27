"""Aprendizes de CARTEIRA no gráfico diário (só PAPER, dinheiro fictício). Criados em 27/11/2026 (PESQUISA.md seção 27).

  rotacao  — toda segunda-feira compra as N moedas que mais subiram nos últimos D dias (só as que estão acima da
             média de 50 dias e só com o BTC também acima dela); as que saem do grupo são vendidas.
  donchian — compra quando a moeda FECHA acima da máxima dos últimos N dias (com o BTC acima da média de 50 dias)
             e vende quando fecha abaixo da mínima dos últimos M dias. Até `vagas` moedas ao mesmo tempo.

Decide uma vez por dia, com o candle diário JÁ FECHADO (nada de olhar o candle em andamento). Usa só dados públicos.
Uso:  python -m bot.carteira --config /app/config_aprendiz_rotacao.yaml
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .__main__ import load_config, setup_logging
from .exchange import make_ccxt
from .learn import DIARIO, registrar
from .notify import Telegram
from .painel import Painel

log = logging.getLogger("bot")
BR = timezone(timedelta(hours=-3))
NOMES = {"rotacao": "rotação semanal", "donchian": "rompimento diário"}


# ---------------- decisões (funções puras, testadas em tests/test_bot.py) ----------------
def alvo_rotacao(closes: pd.DataFrame, dias: int, top: int, media: int = 50, filtro_btc: bool = True) -> list[str]:
    """As `top` moedas que mais subiram em `dias`, entre as que estão acima da média; [] se o BTC estiver abaixo."""
    if len(closes) < max(dias, media) + 1:
        return []
    ult = closes.iloc[-1]
    acima = ult > closes.rolling(media).mean().iloc[-1]
    if filtro_btc and "BTC/USDT" in closes and not bool(acima.get("BTC/USDT", False)):
        return []
    mom = (ult / closes.iloc[-1 - dias] - 1).where(acima).dropna()
    mom = mom[mom > 0]
    return list(mom.sort_values(ascending=False).index[:top])


def sinais_donchian(highs: pd.DataFrame, lows: pd.DataFrame, closes: pd.DataFrame, entrada: int, saida: int,
                    seguro: set[str], vagas: int, media: int = 50, filtro_btc: bool = True) -> tuple[list[str], list[str]]:
    """(comprar, vender) com o último candle fechado: rompeu a máxima de `entrada` dias / perdeu a mínima de `saida`."""
    if len(closes) < max(entrada, saida, media) + 1:
        return [], []
    c = closes.iloc[-1]
    hi = highs.iloc[-1 - entrada:-1].max()
    lo = lows.iloc[-1 - saida:-1].min()
    vender = [s for s in seguro if s in c and c[s] < lo.get(s, float("-inf"))]
    btc_ok = (not filtro_btc) or ("BTC/USDT" in closes and c["BTC/USDT"] > closes["BTC/USDT"].rolling(media).mean().iloc[-1])
    livres = vagas - (len(seguro) - len(vender))
    comprar = []
    if btc_ok and livres > 0:
        forca = ((c - hi) / hi).where(c > hi).dropna().sort_values(ascending=False)
        comprar = [s for s in forca.index if s not in seguro][:livres]
    return comprar, vender


# ---------------- o bot ----------------
class Carteira:
    def __init__(self, cfg: dict):
        self.cfg, self.k = cfg, cfg["carteira"]
        self.metodo = self.k["metodo"]
        self.inst = cfg.get("instancia") or f"aprendiz-{self.metodo}"
        self.origem = "paper-" + self.inst
        self.sim = list(cfg["symbols"])
        self.fee = float(cfg["fees"]["taker"])
        self.slip = float(cfg["fees"].get("slippage", 0.0005))
        self.ex = make_ccxt({**cfg, "testnet": False}, with_keys=False)
        self.path = Path(f"state_{self.inst}.json")
        ini = float((cfg.get("paper") or {}).get("initial_balance") or 10000)
        self.st = json.loads(self.path.read_text()) if self.path.exists() else {"cash": ini, "inicial": ini, "pos": {}, "hist": [], "dias": {}}
        self.precos: dict[str, float] = {}
        self.tg = Telegram() if (cfg.get("telegram") or {}).get("avisos") else None
        pc = cfg.get("painel") or {}
        self.painel = Painel(os.getenv("PAINEL_HOST", "127.0.0.1"), int(pc.get("port", 8769)), self.inst, {})

    # -- contas --
    def equity(self) -> float:
        return self.st["cash"] + sum(p["qty"] * self.precos.get(s, p["entrada"]) for s, p in self.st["pos"].items())

    def salvar(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.st))
        tmp.replace(self.path)

    def _aviso(self, texto: str) -> None:
        if self.tg:
            self.tg.send(texto, dedupe_s=0, html=True)

    def comprar(self, s: str, usdt: float, motivo: str) -> None:
        px = self.precos[s] * (1 + self.slip)
        usdt = min(usdt, self.st["cash"])
        if usdt < 10:
            return
        qty = usdt / (px * (1 + self.fee))
        self.st["cash"] -= usdt
        self.st["pos"][s] = {"qty": qty, "entrada": px, "custo": usdt, "aberta": datetime.now(timezone.utc).isoformat(), "motivo": motivo}
        log.info("COMPRA %s [%s] qty=%.6f @ %.6g | %s", s, self.metodo, qty, px, motivo)
        self._aviso(f"🟢 <b>COMPRA {s.split('/')[0]}</b>\n<i>{self.cfg['painel'].get('nome')} · 📝 simulação</i>\n\n"
                    f"📌 {NOMES[self.metodo].capitalize()} — {motivo}\n💵 Entrada <code>{px:.6g}</code> · {usdt:.2f} USDT")

    def vender(self, s: str, motivo: str) -> None:
        p = self.st["pos"].pop(s)
        px = self.precos.get(s, p["entrada"]) * (1 - self.slip)
        bruto = p["qty"] * px
        liquido = bruto * (1 - self.fee)
        self.st["cash"] += liquido
        pnl = liquido - p["custo"]
        r = (pnl / p["custo"]) / 0.10                      # 1R = 10% da posição (para comparar com os outros bots)
        taxas = bruto * self.fee + p["custo"] * self.fee / (1 + self.fee)
        registrar({"origem": self.origem, "simbolo": s, "aberta": p["aberta"], "fechada": datetime.now(timezone.utc).isoformat(),
                   "entrada": p["entrada"], "saida": px, "pnl": round(pnl, 4), "r": round(r, 3), "motivo": motivo,
                   "taxas": round(taxas, 4), "features": {"estrategia": self.metodo}})
        log.info("FECHOU %s [%s] | motivo: %s | PnL %.2f USDT (%+.2fR)", s, self.metodo, motivo, pnl, r)
        self._aviso(f"{'✅' if pnl > 0 else '❌'} <b>{'GANHO' if pnl > 0 else 'PERDA'} {s.split('/')[0]}  {pnl:+.2f} USDT</b>\n"
                    f"<i>{self.cfg['painel'].get('nome')} · 📝 simulação</i>\n\n📌 saiu: {motivo} · {px / p['entrada'] - 1:+.1%}")

    # -- dados --
    def atualizar_precos(self) -> None:
        tk = self.ex.fetch_tickers(self.sim)
        self.precos.update({s: float(v["last"]) for s, v in tk.items() if v.get("last")})

    def velas(self, n: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        hoje = int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        c, h, lw = {}, {}, {}
        for s in self.sim:
            try:
                rows = [r for r in self.ex.fetch_ohlcv(s, "1d", limit=n + 2) if r[0] < hoje]   # só candles FECHADOS
            except Exception as e:
                log.warning("%s: sem candles diários (%s)", s, e)
                continue
            idx = [pd.Timestamp(r[0], unit="ms") for r in rows]
            c[s], h[s], lw[s] = (pd.Series([r[i] for r in rows], index=idx) for i in (4, 2, 3))
        return pd.DataFrame(c), pd.DataFrame(h), pd.DataFrame(lw)

    # -- decisão diária --
    def decidir(self) -> None:
        k = self.k
        closes, highs, lows = self.velas(max(int(k.get("dias", 28)), int(k.get("entrada", 20)), 50) + 30)
        if closes.empty:
            return
        seguro = set(self.st["pos"])
        if self.metodo == "rotacao":
            if datetime.now(timezone.utc).weekday() != 0 and self.st.get("girou"):
                return                                     # troca só na segunda-feira (a 1ª vez, na hora)
            alvo = alvo_rotacao(closes, int(k["dias"]), int(k["top"]), int(k.get("media", 50)), bool(k.get("filtro_btc", True)))
            self.st["girou"] = True
            for s in sorted(seguro - set(alvo)):
                self.vender(s, "saiu das mais fortes" if alvo else "BTC abaixo da média de 50 dias")
            novas = [s for s in alvo if s not in self.st["pos"]]
            if novas:
                cada = self.equity() / int(k["top"])
                for s in novas:
                    self.comprar(s, min(cada, self.st["cash"]), f"entre as {k['top']} mais fortes em {k['dias']} dias")
            log.info("ROTAÇÃO: segurando %s", ", ".join(s.split("/")[0] for s in self.st["pos"]) or "nada (USDT)")
        else:
            comprar, vender = sinais_donchian(highs, lows, closes, int(k["entrada"]), int(k["saida"]), seguro,
                                              int(k["vagas"]), int(k.get("media", 50)), bool(k.get("filtro_btc", True)))
            for s in vender:
                self.vender(s, f"fechou abaixo da mínima de {k['saida']} dias")
            for s in comprar:
                self.comprar(s, self.equity() / int(k["vagas"]), f"fechou acima da máxima de {k['entrada']} dias")
            if not comprar and not vender:
                log.info("ROMPIMENTO: nenhuma moeda rompeu hoje; segurando %s", ", ".join(s.split("/")[0] for s in self.st["pos"]) or "nada")

    # -- painel --
    def _desempenho(self) -> dict:
        ops = []
        if DIARIO.exists():
            for linha in DIARIO.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    j = json.loads(linha)
                except ValueError:
                    continue
                if j.get("origem") == self.origem:
                    ops.append(j)
        corte = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        hoje = [o for o in ops if str(o.get("fechada", "")) >= corte]
        g = [o for o in ops if float(o.get("pnl") or 0) > 0]
        soma = lambda L: {"ops": len(L), "ganhos": sum(1 for o in L if float(o.get("pnl") or 0) > 0),
                          "soma_r": sum(float(o.get("r") or 0) for o in L), "pnl": sum(float(o.get("pnl") or 0) for o in L),
                          "taxas": sum(float(o.get("taxas") or 0) for o in L)}
        return {"ops": len(ops), "realizado": round(soma(ops)["pnl"], 4), "acerto": len(g) / len(ops) if ops else None,
                "media_r": soma(ops)["soma_r"] / len(ops) if ops else None, "hoje_ops": len(hoje), "hoje_pnl": round(soma(hoje)["pnl"], 4),
                "taxas": round(soma(ops)["taxas"], 4), "por_setup": {self.metodo: soma(ops)} if ops else {}, "por_padrao": {}, "por_fase": {}}

    def snapshot(self) -> dict:
        eq, agora = self.equity(), time.time()
        hist = self.st["hist"]
        if not hist or agora - hist[-1][0] >= 300:
            hist.append([int(agora), round(eq, 4)])
            del hist[:-3000]
        dia = datetime.fromtimestamp(agora, BR).strftime("%Y-%m-%d")
        self.st["dias"].setdefault(dia, round(eq, 4))
        for d in sorted(self.st["dias"])[:-400]:
            del self.st["dias"][d]
        pos = [{"simbolo": s, "estrategia": self.metodo, "entrada": p["entrada"], "preco": self.precos.get(s), "stop": None, "alvo": None,
                "qtd": p["qty"], "resultado_pct": self.precos.get(s, p["entrada"]) / p["entrada"] - 1, "aberta": p["aberta"]} for s, p in self.st["pos"].items()]
        k = self.k
        fala = (f"Toda segunda compro as {k['top']} moedas mais fortes dos últimos {k['dias']} dias (com o BTC acima da média de 50)."
                if self.metodo == "rotacao" else
                f"Compro quando uma moeda fecha acima da máxima de {k['entrada']} dias e vendo abaixo da mínima de {k['saida']}.")
        return {"modo": self.origem, "agora": datetime.now(timezone.utc).isoformat(), "nome": (self.cfg.get("painel") or {}).get("nome"),
                "real": False, "pausado": False, "carteira": eq, "bot": eq, "cofre": 0.0, "cofre_moedas": {}, "posicoes": pos,
                "radar": {}, "precos": dict(self.precos), "var24": {}, "equity_hist": hist, "alarme": False,
                "timeframes": {"entry": "1d", "trend": "1d"}, "termometro": None, "inicial": self.st["inicial"], "aprendiz": True,
                "metodo": NOMES[self.metodo], "metodo_fala": fala,
                "dias": sorted(self.st["dias"].items()), "intradia": [p for p in hist if p[0] >= agora - 86_400][::3],
                "desempenho": self._desempenho()}

    def rodar(self) -> None:
        self.painel.start()
        log.info("Bot iniciado: %s (%s, simulação, %d moedas)", self.inst, NOMES[self.metodo], len(self.sim))
        while True:
            try:
                self.atualizar_precos()
                hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if self.st.get("decidiu") != hoje and datetime.now(timezone.utc).minute >= 2:
                    self.decidir()
                    self.st["decidiu"] = hoje
                self.painel.update(self.snapshot())
                self.salvar()
            except Exception:
                log.exception("erro no ciclo da carteira")
            time.sleep(60)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    setup_logging()
    cfg = load_config(a.config)
    # sempre simulação: este módulo nem carrega chaves da Binance (make_ccxt sem chaves)
    Carteira(cfg).rodar()


if __name__ == "__main__":
    main()
