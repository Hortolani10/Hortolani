"""CLI:  python -m bot {backtest|paper|live|analyze} [opções]"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import yaml


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging() -> None:
    from logging.handlers import RotatingFileHandler

    try:                                    # acentos no terminal do Windows
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  RotatingFileHandler("logs/bot.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")],
    )


def single_instance(mode: str):
    """Impede duas cópias do bot no mesmo modo (ordens duplicadas). Funciona em Linux, Mac e Windows."""
    f = open(f".bot_{mode}.lock", "a+")
    try:
        if os.name == "nt":
            import msvcrt

            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        sys.exit(f"Já existe um bot rodando em modo {mode}. Pare o outro antes de iniciar.")
    return f          # manter a referência viva mantém o bloqueio


def check_env_file() -> None:
    p = Path(".env")
    if os.name != "nt" and p.exists() and p.stat().st_mode & 0o077:      # no Windows as permissões são outras
        logging.getLogger("bot").warning(
            "SEGURANÇA: .env pode ser lido por outros usuários do sistema. Rode: chmod 600 .env")


def load_state(path: str) -> dict:
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else {}


def _with_btc(cfg, data, fetch_btc):
    """Aplica o filtro do BTC; busca o BTC se ele não estiver na lista de pares."""
    from .data import apply_btc_filter, prepare

    if not cfg["strategy"].get("btc_filter"):
        return data
    btc = data.get("BTC/USDT")
    if btc is None:
        btc = prepare(*fetch_btc(), cfg)
    return apply_btc_filter(data, cfg, btc)


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
    data = _with_btc(cfg, data, lambda: (cached_history(ex, "BTC/USDT", cfg["timeframes"]["entry"], args.days),
                                         cached_history(ex, "BTC/USDT", cfg["timeframes"]["trend"], args.days + 60)))
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
    tf_e, tf_t = cfg["timeframes"]["entry"], cfg["timeframes"]["trend"]

    def get(sym):
        e = drop_open_candle(to_df(ex.fetch_ohlcv(sym, tf_e, limit=500)), tf_e)
        t = drop_open_candle(to_df(ex.fetch_ohlcv(sym, tf_t, limit=500)), tf_t)
        return e, t

    out = []
    syms = args.symbols or cfg["symbols"]
    raw = {sym: get(sym) for sym in syms}
    data = _with_btc(cfg, {s: prepare(e, t, cfg) for s, (e, t) in raw.items()}, lambda: get("BTC/USDT"))
    for sym in syms:
        out.append(analysis_report(sym, data[sym], add_all(raw[sym][1], cfg), cfg))
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
        data = _with_btc(cfg, data, lambda: (cached_history(ex, "BTC/USDT", cfg["timeframes"]["entry"], args.days),
                                             cached_history(ex, "BTC/USDT", cfg["timeframes"]["trend"], args.days + 60)))
    res = run(data, cfg, initial=args.balance)
    path = render(build_payload(data, res, cfg, simulated=args.demo), args.out)
    print(f"painel gerado: {path.resolve()}  (abra no navegador)")


def cmd_carteira(cfg, args):
    """Backtest da carteira completa: bot + cofre de tendência, reequilíbrio mensal."""
    import time as _t

    from .data import cached_history, prepare
    from .exchange import make_ccxt
    from .sleeve import portfolio_backtest

    ex = make_ccxt(cfg, with_keys=False)
    data = {}
    for sym in cfg["symbols"]:
        print(f"baixando {sym}...")
        data[sym] = prepare(cached_history(ex, sym, cfg["timeframes"]["entry"], args.days),
                            cached_history(ex, sym, cfg["timeframes"]["trend"], args.days), cfg)
    data = _with_btc(cfg, data, lambda: None)
    syms = set(cfg["trend_sleeve"]["symbols"]) | {"BTC/USDT"}
    daily = {s: cached_history(ex, s, "1d", args.days) for s in syms}
    start = int(_t.time() * 1000) - (args.days - 240) * 86_400_000     # 240 dias de aquecimento das médias
    r = portfolio_backtest(data, daily, cfg, args.balance, start)
    eq = r["equity"]
    f = cfg["trend_sleeve"]["fraction"]
    print(f"\n=== CARTEIRA: {f:.0%} cofre de tendência + {1 - f:.0%} bot, reequilíbrio mensal ===")
    print(f"período: {eq.index[0]:%d/%m/%Y} a {eq.index[-1]:%d/%m/%Y}")
    print(f"{args.balance:.2f} -> {eq.iloc[-1]:.2f} USDT ({r['retorno']:+.1%}) · queda máxima {r['queda_max']:.1%}")
    print(f"operações do bot: {len(r['bot'].trades)} · ordens do cofre: {r['cofre_ordens']}")
    anos = eq.resample("YE").last()
    prev = args.balance
    for d, v in anos.items():
        print(f"  {d.year}: {v / prev - 1:+.1%}")
        prev = v


def cmd_aprender(cfg, args):
    """Relatório de aprendizado: histórico + prática, alarme de desvio e proposta de ajuste."""
    import time as _t

    from .backtest import run
    from .data import cached_history, prepare
    from .exchange import make_ccxt
    from .learn import checar_desvio, ler_diario, relatorio, reotimizar, trades_para_linhas

    ex = make_ccxt(cfg, with_keys=False)
    data = {}
    for sym in cfg["symbols"]:
        print(f"baixando {sym}...")
        data[sym] = prepare(cached_history(ex, sym, cfg["timeframes"]["entry"], args.days),
                            cached_history(ex, sym, cfg["timeframes"]["trend"], args.days), cfg)
    data = _with_btc(cfg, data, lambda: None)
    hist = run(data, cfg, 100)
    Path("logs").mkdir(exist_ok=True)
    Path("logs/historico_r.json").write_text(json.dumps([t.r_multiple for t in hist.trades]))

    pratica = ler_diario()
    todas = pd.concat([pd.json_normalize(trades_para_linhas(hist.trades, "backtest")), pratica], ignore_index=True)
    todas.columns = [c.replace("features.", "") for c in todas.columns]
    print("\n=== O QUE O BOT APRENDEU (histórico + prática) ===")
    print(relatorio(todas))

    print("\n=== ALARME DE DESVIO (prática x histórico) ===")
    for modo in ("paper", "live"):
        r = pratica[pratica["origem"] == modo]["r"].tolist() if not pratica.empty else []
        print(f"{modo:<6}", checar_desvio(r, [t.r_multiple for t in hist.trades])["motivo"])

    print("\n=== REOTIMIZAÇÃO (últimos 12 meses) ===")
    fim = int(_t.time() * 1000)
    dec = reotimizar(data, cfg, fim)
    a = dec["atual"]
    print(f"atual: {a['operacoes']} ops, retorno {a['retorno_total']:+.2%}, queda máx {a['drawdown_max']:.2%}")
    for x in dec["ranking"][:5]:
        print(f"  {x['params']}  ops={x['operacoes']} ret={x['retorno_total']:+.2%} dd={x['drawdown_max']:.2%}")
    if dec["trocar"]:
        prop = Path("config_proposta.yaml")
        prop.write_text(yaml.safe_dump(dec["melhor"]["cfg"], allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"\nPROPOSTA salva em {prop}: {dec['melhor']['params']}")
        print("Atenção: no teste walk-forward, trocar automaticamente PIOROU o resultado (111 vs 118 USDT).")
        print("Só adote se a melhora persistir em mais de uma revisão e for coerente com o mercado.")
    else:
        print("\nSem proposta: nenhum ajuste foi claramente melhor. Mantenha a configuração atual.")


def cmd_run(cfg, mode):
    from dotenv import load_dotenv

    from .exchange import LiveBroker, PaperBroker, make_ccxt
    from .trader import Trader

    load_dotenv()
    setup_logging()
    lock = single_instance(mode)  # noqa: F841
    check_env_file()
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
        broker.check_key_permissions(real_money=not cfg.get("testnet", True))
        logging.getLogger("bot").warning("MODO LIVE (%s)", "TESTNET" if cfg.get("testnet", True) else "DINHEIRO REAL")
    from .notify import Telegram, TelegramLogHandler

    tg = Telegram()
    if tg.enabled:
        tag = {"paper": "[PAPER] ", "live": "[TESTNET] " if cfg.get("testnet", True) else "[REAL] "}[mode]
        logging.getLogger("bot").addHandler(TelegramLogHandler(tg, tag))
    else:
        logging.getLogger("bot").info("Telegram não configurado (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID): sem avisos no celular")
    Trader(cfg, broker, state, state_path, tg=tg).run_forever()


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
    c_ = sub.add_parser("carteira", help="backtest da carteira completa (bot + cofre de tendência)")
    c_.add_argument("--days", type=int, default=2450)
    c_.add_argument("--balance", type=float, default=100)
    ap_ = sub.add_parser("aprender", help="relatório do que funcionou, alarme de desvio e proposta de ajuste")
    ap_.add_argument("--days", type=int, default=1150)
    sub.add_parser("paper", help="opera com dinheiro fictício e preços reais")
    sub.add_parser("live", help="opera de verdade (testnet ou real, conforme config)")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.cmd == "backtest":
        cmd_backtest(cfg, args)
    elif args.cmd == "carteira":
        cmd_carteira(cfg, args)
    elif args.cmd == "aprender":
        cmd_aprender(cfg, args)
    elif args.cmd == "dashboard":
        cmd_dashboard(cfg, args)
    elif args.cmd == "analyze":
        cmd_analyze(cfg, args)
    else:
        cmd_run(cfg, args.cmd)


if __name__ == "__main__":
    main()
