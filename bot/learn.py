"""Aprendizado do bot: diário de operações, relatório do que funcionou e reotimização periódica.

Como o bot aprende (e por que não muda a cada operação):
  * Cada operação vai para o DIÁRIO (logs/diario.jsonl) com o retrato do mercado na entrada
    (ADX, volatilidade, RSI, volume, sessão, tendência do BTC) e o resultado em R.
  * A cada perda a DEFESA AUTOMÁTICA (risk.adaptive_risk) pode reduzir o risco, sem mudar regras.
  * A cada N meses a REOTIMIZAÇÃO testa um conjunto FIXO de ajustes nos últimos 12 meses
    (histórico + o que aconteceu na prática) e só propõe mudar se a melhora for clara e com
    operações suficientes. Em dinheiro real a proposta exige aprovação (config_proposta.yaml).
"""
from __future__ import annotations

import copy
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .backtest import run

DIARIO = Path("logs/diario.jsonl")

# Conjunto fixo e pequeno de ajustes que o bot pode escolher. Pequeno de propósito:
# quanto mais opções, maior a chance de escolher uma que "decorou" o passado.
GRADE = {
    "strategy.adx_min": [20, 25, 30],
    "risk.trailing_atr": [2.5, 3.0, 4.0],
    "risk.exit_mode": ["trailing", "parcial"],
}


# ---------------------------------------------------------------- diário
def registrar(trade: dict, path: Path = DIARIO) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trade, ensure_ascii=False, default=str) + "\n")


def ler_diario(path: Path = DIARIO) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    if not rows:
        return pd.DataFrame()
    df = pd.json_normalize(rows)
    df.columns = [c.replace("features.", "") for c in df.columns]
    return df


def trades_para_linhas(trades, origem: str) -> list[dict]:
    return [{"origem": origem, "simbolo": t.symbol, "aberta": t.opened, "fechada": t.closed,
             "entrada": t.entry, "saida": t.exit, "pnl": t.pnl, "r": t.r_multiple,
             "motivo": t.reasons, "features": t.features} for t in trades]


def relatorio(df: pd.DataFrame, min_ops: int = 8) -> str:
    """O que o diário mostra: resultado médio (em R) por condição de mercado na entrada."""
    if df.empty:
        return "Diário vazio: ainda não há operações registradas."
    out = [f"Diário: {len(df)} operações · acerto {(df.r > 0).mean():.0%} · média {df.r.mean():+.2f}R"]
    if "origem" in df:
        for o, g in df.groupby("origem"):
            out.append(f"  {o:<10} {len(g):>3} ops · acerto {(g.r > 0).mean():.0%} · média {g.r.mean():+.2f}R")
    buckets = {
        "adx": ("ADX na entrada", [0, 25, 35, 100], ["<25", "25-35", ">35"]),
        "atr_pct": ("Volatilidade (ATR % do preço)", None, ["baixa", "média", "alta"]),
        "rsi": ("RSI na entrada", [0, 55, 62, 100], ["45-55", "55-62", "62-68"]),
        "volume_rel": ("Volume vs média", [0, 1.5, 2.5, 99], ["1-1,5×", "1,5-2,5×", ">2,5×"]),
    }
    for col, (nome, edges, labels) in buckets.items():
        if col not in df or df[col].isna().all():
            continue
        cut = pd.qcut(df[col].rank(method="first"), 3, labels=labels) if edges is None else pd.cut(df[col], edges, labels=labels)
        out.append(f"\n{nome}:")
        for lab, g in df.groupby(cut, observed=True):
            aviso = "" if len(g) >= min_ops else "  (poucas operações: não conclua nada)"
            out.append(f"  {str(lab):<10} {len(g):>3} ops · acerto {(g.r > 0).mean():>4.0%} · média {g.r.mean():+.2f}R{aviso}")
    if "tf" in df and df["tf"].notna().any():
        out.append("\nPor tempo gráfico:")
        for lab, g in df.groupby("tf"):
            aviso = "" if len(g) >= min_ops else "  (poucas operações)"
            out.append(f"  {str(lab):<15} {len(g):>3} ops · acerto {(g.r > 0).mean():>4.0%} · média {g.r.mean():+.2f}R{aviso}")
    if "estrategia" in df and df["estrategia"].notna().any():
        out.append("\nPor setup (tipo de entrada):")
        for lab, g in df.groupby("estrategia"):
            aviso = "" if len(g) >= min_ops else "  (poucas operações)"
            out.append(f"  {str(lab):<15} {len(g):>3} ops · acerto {(g.r > 0).mean():>4.0%} · média {g.r.mean():+.2f}R{aviso}")
    if "padroes" in df and df["padroes"].notna().any():
        from .padroes import NOMES
        ex = df[["r", "padroes"]].dropna().explode("padroes").dropna()
        if not ex.empty:
            out.append("\nPadrões de gráfico no candle da entrada (com o padrão × média geral):")
            linhas = []
            for lab, g in ex.groupby("padroes"):
                linhas.append((g.r.mean(), lab, g))
            for media, lab, g in sorted(linhas, key=lambda x: -x[0]):
                aviso = "" if len(g) >= min_ops else "  (poucas operações)"
                out.append(f"  {NOMES.get(lab, lab):<44} {len(g):>3} ops · acerto {(g.r > 0).mean():>4.0%} · média {media:+.2f}R{aviso}")
    for col, nome in (("sessao", "Sessão do sinal"), ("simbolo", "Moeda")):
        if col in df:
            out.append(f"\n{nome}:")
            for lab, g in df.groupby(col):
                aviso = "" if len(g) >= min_ops else "  (poucas operações)"
                out.append(f"  {str(lab):<10} {len(g):>3} ops · acerto {(g.r > 0).mean():>4.0%} · média {g.r.mean():+.2f}R{aviso}")
    return "\n".join(out)


# ---------------------------------------------------------------- reotimização
def _set(cfg: dict, key: str, value) -> None:
    sec, k = key.split(".")
    cfg[sec][k] = value


def candidatos(cfg: dict) -> list[tuple[dict, dict]]:
    keys = list(GRADE)
    out = []
    for vals in itertools.product(*(GRADE[k] for k in keys)):
        c = copy.deepcopy(cfg)
        for k, v in zip(keys, vals):
            _set(c, k, v)
        if c["risk"]["exit_mode"] == "trailing":
            c["risk"]["trend_exit"] = False
        out.append((dict(zip(keys, vals)), c))
    return out


def pontuar(resumo: dict) -> float:
    """Retorno ajustado ao risco: retorno dividido pela queda máxima (+1% para não dividir por ~0)."""
    return resumo["retorno_total"] / (resumo["drawdown_max"] + 0.01)


def reotimizar(data: dict[str, pd.DataFrame], cfg: dict, fim_ts: int, janela_dias: int = 365,
               min_ops: int = 15, margem: float = 0.25) -> dict:
    """Testa a GRADE nos `janela_dias` antes de `fim_ts` e decide se vale trocar.

    Só troca se o melhor candidato tiver >= min_ops operações E pontuação pelo menos
    `margem` (25%) acima da configuração atual. Senão mantém: na dúvida, não mexe.
    """
    ini = fim_ts - janela_dias * 86_400_000
    atual = run(data, cfg, 100, start_ts=ini, end_ts=fim_ts, close_at_end=True).summary()
    linhas = []
    for params, c in candidatos(cfg):
        r = run(data, c, 100, start_ts=ini, end_ts=fim_ts, close_at_end=True).summary()
        linhas.append({"params": params, "cfg": c, **r, "pontos": pontuar(r)})
    validos = [x for x in linhas if x["operacoes"] >= min_ops]
    melhor = max(validos, key=lambda x: x["pontos"]) if validos else None
    p_atual = pontuar(atual)
    trocar = bool(melhor) and melhor["pontos"] > p_atual + margem * abs(p_atual) and melhor["pontos"] > 0
    return {"atual": {**atual, "pontos": p_atual}, "melhor": melhor, "trocar": trocar,
            "ranking": sorted(linhas, key=lambda x: -x["pontos"])}


def walk_forward(data: dict[str, pd.DataFrame], cfg: dict, inicio_ts: int, fim_ts: int,
                 passo_dias: int = 90, janela_dias: int = 365, inicial: float = 100.0) -> dict:
    """Testa o PRÓPRIO método de aprendizado: a cada `passo_dias` reotimiza só com o passado
    e opera o período seguinte. Compara com o bot fixo nos mesmos períodos."""
    adapt_cfg = copy.deepcopy(cfg)
    eq_a = eq_f = inicial
    passos, t = [], inicio_ts
    while t < fim_ts:
        t2 = min(t + passo_dias * 86_400_000, fim_ts)
        dec = reotimizar(data, adapt_cfg, t, janela_dias)
        if dec["trocar"]:
            adapt_cfg = dec["melhor"]["cfg"]
        ra = run(data, adapt_cfg, eq_a, start_ts=t, end_ts=t2, close_at_end=True).summary()
        rf = run(data, cfg, eq_f, start_ts=t, end_ts=t2, close_at_end=True).summary()
        eq_a, eq_f = ra["saldo_final"], rf["saldo_final"]
        passos.append({"inicio": datetime.fromtimestamp(t / 1000, timezone.utc).date().isoformat(),
                       "trocou": dec["trocar"],
                       "params": {k: _get(adapt_cfg, k) for k in GRADE},
                       "adaptativo": eq_a, "fixo": eq_f, "ops_adapt": ra["operacoes"], "ops_fixo": rf["operacoes"]})
        t = t2
    return {"passos": passos, "final_adaptativo": eq_a, "final_fixo": eq_f}


def _get(cfg: dict, key: str):
    sec, k = key.split(".")
    return cfg[sec][k]


# ---------------------------------------------------------------- alarme de desvio
def checar_desvio(r_pratica: list[float], r_historico: list[float], janela: int = 10,
                  percentil: float = 0.05) -> dict:
    """Compara a média das últimas `janela` operações na PRÁTICA com o que o HISTÓRICO
    considera normal. Se estiver abaixo do pior `percentil` (5%) das sequências do
    histórico, o mercado provavelmente mudou: reduzir risco e revisar."""
    import numpy as np

    if len(r_pratica) < janela or len(r_historico) < janela * 3:
        return {"alarme": False, "motivo": f"poucas operações na prática ({len(r_pratica)}/{janela})"}
    h = pd.Series(r_historico).rolling(janela).mean().dropna()
    limite = float(np.quantile(h, percentil))
    atual = float(np.mean(r_pratica[-janela:]))
    alarme = atual < limite
    return {"alarme": alarme, "media_recente_R": atual, "limite_R": limite,
            "motivo": (f"últimas {janela} operações: média {atual:+.2f}R, abaixo do pior "
                       f"{percentil:.0%} do histórico ({limite:+.2f}R)") if alarme
                      else f"normal: média recente {atual:+.2f}R (limite {limite:+.2f}R)"}
