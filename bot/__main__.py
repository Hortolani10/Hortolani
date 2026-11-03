"""CLI:  python -m bot {backtest|paper|live|analyze} [opções]"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import yaml


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging() -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("logs/bot.log", encoding="utf-8")],
    )


def load_state(path: str) -> dict:
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def cmd_backtest(cfg, args):
    from .backtest import run
    from .data import cached_history, prepare
    from .exchange import make_ccxt

    ex = make_ccxt(cfg, with_keys=False)
    data = {}
    for sym in args.symbols or cfg["symbols"]:
        print(f"baixando {sym}...")
        e = cached_history(ex, sym, cfg["timeframes"]["entry"], args.days)
        t = cached_history(ex, sym, cfg["timeframes"]["trend"], args.days + 60)
        data[sym] = prepare(e, t, cfg)
    res = run(data, cfg, initial=args.balance)
    print("\n=== RESULTADO DO BACKTEST ===")
    for k, v in res.summary().items():
        print(f"{k:>15}: {v:.2%}" if k in ("taxa_acerto", "retorno_total", "drawdown_max") else f"{k:>15}: {v:.2f}")
    print("\núltimas operações:")
    for t in res.trades[-15:]:
        print(f"  {t.symbol:<10} {t.opened[:16]} -> {t.closed[:16]}  {t.r_multiple:+.2f}R  {t.pnl:+.2f} USDT  [{t.reasons}]")


def cmd_analyze(cfg, args):
    from .data import drop_open_candle, prepare, to_df
    from .exchange import make_ccxt
    from .indicators import add_all
    from .report import analysis_report

    ex = make_ccxt(cfg, with_keys=False)
    out = []
    for sym in args.symbols or cfg["symbols"]:
        e = drop_open_candle(to_df(ex.fetch_ohlcv(sym, cfg["timeframes"]["entry"], limit=500)), cfg["timeframes"]["entry"])
        t = drop_open_candle(to_df(ex.fetch_ohlcv(sym, cfg["timeframes"]["trend"], limit=500)), cfg["timeframes"]["trend"])
        out.append(analysis_report(sym, prepare(e, t, cfg), add_all(t, cfg), cfg))
    text = "\n\n---\n\n".join(out)
    if args.prompt:
        text = Path("PROMPT_ANALISE.md").read_text(encoding="utf-8") + "\n\n# DADOS DE MERCADO\n\n" + text
    print(text)


def cmd_dashboard(cfg, args):
    from .backtest import run
    from .dashboard import build_payload, render
    from .data import prepare, tf_ms

    data = {}
    if args.demo:
        from .demo import regime_series, resample

        k = tf_ms(cfg["timeframes"]["trend"]) // tf_ms(cfg["timeframes"]["entry"])
        for name, seed, start in [("DEMO-A/USDT", 10, 100.0), ("DEMO-B/USDT", 20, 40.0)]:
            e = regime_series(4000, tf_ms(cfg["timeframes"]["entry"]), seed, start)
            data[name] = prepare(e, resample(e, k), cfg)
    else:
        from .data import cached_history
        from .exchange import make_ccxt

        ex = make_ccxt(cfg, with_keys=False)
        for sym in args.symbols or cfg["symbols"]:
            print(f"baixando {sym}...")
            e = cached_history(ex, sym, cfg["timeframes"]["entry"], args.days)
            t = cached_history(ex, sym, cfg["timeframes"]["trend"], args.days + 60)
            data[sym] = prepare(e, t, cfg)
    res = run(data, cfg, initial=args.balance)
    path = render(build_payload(data, res, cfg, simulated=args.demo), args.out)
    print(f"painel gerado: {path.resolve()}  (abra no navegador)")


def cmd_run(cfg, mode):
    from dotenv import load_dotenv

    from .exchange import LiveBroker, PaperBroker, make_ccxt
    from .trader import Trader

    load_dotenv()
    setup_logging()
    cfg["mode"] = mode
    state_path = f"state_{mode}.json"
    state = load_state(state_path)
    market = make_ccxt({**cfg, "testnet": False}, with_keys=False) if mode == "paper" else None

    if mode == "paper":
        broker = PaperBroker(cfg, market, state)
    else:
        if not os.getenv("BINANCE_API_KEY"):
            sys.exit("Defina BINANCE_API_KEY e BINANCE_API_SECRET no arquivo .env")
        if not cfg.get("testnet", True) and os.getenv("CONFIRMO_OPERAR_DINHEIRO_REAL") != "SIM":
            sys.exit("Modo live com dinheiro real bloqueado. Defina CONFIRMO_OPERAR_DINHEIRO_REAL=SIM no .env")
        trade_ex = make_ccxt(cfg, with_keys=True)
        broker = LiveBroker(cfg, trade_ex, trade_ex)
        logging.getLogger("bot").warning("MODO LIVE (%s)", "TESTNET" if cfg.get("testnet", True) else "DINHEIRO REAL")
    Trader(cfg, broker, state, state_path).run_forever()


def main():
    ap = argparse.ArgumentParser(prog="bot", description="Bot de trading Binance (spot)")
    ap.add_argument("--config", default="config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backtest", help="testa a estratégia no histórico")
    b.add_argument("--days", type=int, default=365)
    b.add_argument("--balance", type=float, default=1000)
    b.add_argument("--symbols", nargs="*")
    a = sub.add_parser("analyze", help="mostra a análise/checklist atual dos pares")
    a.add_argument("--symbols", nargs="*")
    a.add_argument("--prompt", action="store_true", help="junta o PROMPT_ANALISE.md para colar numa IA")
    d = sub.add_parser("dashboard", help="gera painel HTML com gráfico, sinais e resultados")
    d.add_argument("--days", type=int, default=180)
    d.add_argument("--balance", type=float, default=1000)
    d.add_argument("--symbols", nargs="*")
    d.add_argument("--demo", action="store_true", help="usa dados simulados (sem internet)")
    d.add_argument("--out", default="dashboard.html")
    sub.add_parser("paper", help="opera com dinheiro fictício e preços reais")
    sub.add_parser("live", help="opera de verdade (testnet ou real, conforme config)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.cmd == "backtest":
        cmd_backtest(cfg, args)
    elif args.cmd == "dashboard":
        cmd_dashboard(cfg, args)
    elif args.cmd == "analyze":
        cmd_analyze(cfg, args)
    else:
        cmd_run(cfg, args.cmd)


if __name__ == "__main__":
    main()
