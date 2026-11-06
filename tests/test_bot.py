import pandas as pd

from bot.backtest import run
from bot.data import drop_open_candle, prepare, tf_ms
from bot.indicators import add_all, rsi
from bot.risk import RiskGuard, position_size
from bot.strategy import ALTA, BAIXA, Position, entry_signal, manage_position, trend_series
from bot.trader import Trader

H1, H4 = tf_ms("1h"), tf_ms("4h")


def make(synth, cfg, drift, n=3000, seed=1):
    e = synth(n, H1, drift, seed)
    # TF maior construído agregando o TF de entrada (4 candles de 1h = 1 de 4h)
    g = e.groupby(e.index // 4)
    t = pd.DataFrame({"ts": g["ts"].first(), "open": g["open"].first(), "high": g["high"].max(),
                      "low": g["low"].min(), "close": g["close"].last(), "volume": g["volume"].sum()})
    return prepare(e, t.reset_index(drop=True), cfg), add_all(t.reset_index(drop=True), cfg)


def test_rsi_bounds(synth):
    r = rsi(synth(500, H1, 0.0)["close"]).dropna()
    assert r.between(0, 100).all()


def test_trend_classification(synth, cfg):
    _, up = make(synth, cfg, 0.002)
    _, down = make(synth, cfg, -0.002)
    assert trend_series(up).iloc[-1] == ALTA
    assert trend_series(down).iloc[-1] == BAIXA


def test_no_lookahead_trend(synth, cfg):
    df, t = make(synth, cfg, 0.001, n=1200)
    # a tendência anexada a cada candle de 1h só pode vir de um candle de 4h já FECHADO
    t_close = t["ts"] + H4
    for i in range(300, len(df), 37):
        avail = t[t_close <= df["close_ts"].iloc[i]]
        assert df["trend"].iloc[i] == trend_series(t).loc[avail.index[-1]]


def test_drop_open_candle(synth):
    df = synth(10, H1, 0)
    now = int(df["ts"].iloc[-1]) + H1 // 2      # último candle ainda aberto
    assert len(drop_open_candle(df, "1h", now)) == 9


def test_no_buy_in_downtrend(synth, cfg):
    df, _ = make(synth, cfg, -0.002)
    assert not any(entry_signal(df, i, df["trend"].iloc[i], cfg).ok for i in range(300, len(df)))


def test_signal_has_coherent_stop(synth, cfg):
    df, _ = make(synth, cfg, 0.0008, n=4000)
    sigs = [entry_signal(df, i, df["trend"].iloc[i], cfg) for i in range(300, len(df))]
    oks = [s for s in sigs if s.ok]
    assert oks, "esperava ao menos um sinal em tendência de alta"
    for s, row in ((s, None) for s in oks):
        assert s.stop < s.entry
        assert s.reward_risk >= cfg["risk"]["min_reward_risk"]


def test_position_size_respects_risk(cfg):
    qty = position_size(1000, 100, 95, cfg)
    loss = qty * (100 - 95) + qty * 100 * (2 * cfg["fees"]["taker"] + cfg["fees"]["slippage"])
    assert abs(loss - 10) < 1e-6           # 1% de 1000
    assert qty * 100 <= 250 + 1e-9         # teto de 25%
    assert position_size(1000, 100, 99.9, cfg) * 100 <= 250 + 1e-9


def candle(o, h, l, c, a=1.0, ema_mid=0.0):
    return pd.Series({"open": o, "high": h, "low": l, "close": c, "atr": a, "ema_mid": ema_mid})


def test_manage_stop_hit(cfg):
    p = Position("X", 1, 100, 95, 5, "t", highest=100)
    acts = manage_position(p, candle(99, 100, 94, 96), ALTA, cfg)
    assert acts[0].kind == "sell" and acts[0].price == 95 and p.qty == 0


def test_manage_gap_below_stop_fills_at_open(cfg):
    p = Position("X", 1, 100, 95, 5, "t", highest=100)
    acts = manage_position(p, candle(90, 92, 89, 91), ALTA, cfg)
    assert acts[0].price == 90


def test_manage_partial_breakeven_trailing(cfg):
    p = Position("X", 1, 100, 95, 5, "t", highest=100)
    acts = manage_position(p, candle(101, 108, 100.5, 107, a=1.0), ALTA, cfg)
    kinds = [a.kind for a in acts]
    assert kinds[0] == "sell" and abs(acts[0].qty - 0.5) < 1e-12 and acts[0].price == 107.5
    assert p.partial_done and p.stop > 100            # stop saiu do prejuízo
    assert abs(p.stop - (108 - 3)) < 1e-9             # trailing máxima - 3 ATR
    old = p.stop
    manage_position(p, candle(107, 107.5, 106, 106.5), ALTA, cfg)
    assert p.stop == old                              # trailing nunca desce


def test_manage_trend_exit(cfg):
    p = Position("X", 1, 100, 95, 5, "t", highest=100)
    acts = manage_position(p, candle(100, 101, 99, 99.5, ema_mid=99.8), ALTA, cfg)
    assert acts[-1].kind == "sell" and p.qty == 0
    p = Position("X", 1, 100, 95, 5, "t", highest=100)
    assert manage_position(p, candle(100, 101, 99, 100.5), BAIXA, cfg)[-1].kind == "sell"


def test_risk_guard(cfg):
    from datetime import datetime, timezone
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    g = RiskGuard(cfg)
    g.new_bar(now, 1000)
    assert g.can_open(now, 980)[0]
    assert not g.can_open(now, 960)[0]                # -4% no dia
    g2 = RiskGuard(cfg)
    for _ in range(3):
        g2.register_close(-1, now)
    assert not g2.can_open(now, 1000)[0]


def test_backtest_runs(synth, cfg):
    up, _ = make(synth, cfg, 0.0008, n=4000, seed=3)
    down, _ = make(synth, cfg, -0.001, n=4000, seed=4)
    res = run({"UP/USDT": up, "DOWN/USDT": down}, cfg, 1000)
    s = res.summary()
    assert s["operacoes"] > 0
    assert all(t.symbol == "UP/USDT" or t.pnl is not None for t in res.trades)
    # perda por operação nunca muito maior que o risco planejado (1R + gaps/taxas)
    assert min(t.r_multiple for t in res.trades) > -1.6
    assert s["drawdown_max"] < 0.5


class FakeBroker:
    """Corretora falsa que alimenta o Trader com candles sintéticos."""
    def __init__(self, e, t):
        self.e, self.t, self.n, self.cash, self.stops = e, t, 400, 1000.0, {}
    def candles(self, sym, tf, limit=500):
        df = self.e if tf == "1h" else self.t
        end = self.e["ts"].iloc[self.n]
        return df[df["ts"] + tf_ms(tf) <= end].reset_index(drop=True)
    def price(self, sym): return float(self.e["close"].iloc[self.n - 1])
    def amount(self, sym, q): return round(q, 6)
    def min_notional(self, sym): return 10.0
    def usdt_free(self): return self.cash
    def buy(self, sym, q):
        px = self.price(sym); self.cash -= q * px * 1.001; return q, px, q * px * 1.001
    def sell(self, sym, q, px=None):
        px = self.price(sym); self.cash += q * px * 0.999; return px, q * px * 0.999
    def place_stop(self, sym, q, s): self.stops[sym] = s; return "id"
    def cancel(self, sym, oid): self.stops.pop(sym, None); return 0.0, 0.0
    def stop_filled(self, sym, oid, s): return self.price(sym) <= s, 0.0, 0.0
    def stop_active(self, sym, oid): return sym in self.stops
    def base_balance(self, sym): return None


def test_trader_end_to_end(synth, cfg, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)          # o diário (logs/diario.jsonl) vai para a pasta temporária
    e = synth(2500, H1, 0.0008, 3)
    g = e.groupby(e.index // 4)
    t = pd.DataFrame({"ts": g["ts"].first(), "open": g["open"].first(), "high": g["high"].max(),
                      "low": g["low"].min(), "close": g["close"].last(), "volume": g["volume"].sum()}).reset_index(drop=True)
    cfg["symbols"] = ["UP/USDT"]
    br = FakeBroker(e, t)
    tr = Trader(cfg, br, {}, str(tmp_path / "s.json"))
    opened = closed = 0
    while br.n < 2400:
        had = "UP/USDT" in tr.positions
        tr.tick()
        has = "UP/USDT" in tr.positions
        opened += (not had and has); closed += (had and not has)
        if has:
            assert br.stops.get("UP/USDT") == tr.positions["UP/USDT"].stop   # sempre protegido
        br.n += 1
    assert opened > 0 and closed > 0
    assert (tmp_path / "s.json").exists()
    from bot.learn import ler_diario
    d = ler_diario(tmp_path / "logs" / "diario.jsonl")
    assert len(d) == closed and {"adx", "sessao", "r"} <= set(d.columns)   # cada operação ficou no diário


def test_prefilter_is_superset_of_entry_signal(synth, cfg):
    from bot.strategy import prefilter
    for drift, seed in [(0.0008, 3), (0.0, 5), (0.0012, 9)]:
        df, _ = make(synth, cfg, drift, n=3000, seed=seed)
        m = prefilter(df, cfg).to_numpy()
        for i in range(len(df)):
            if entry_signal(df, i, df["trend"].iloc[i], cfg).ok:
                assert m[i], f"prefilter perdeu o sinal em {i}"


def test_exit_modes(cfg):
    cfg["risk"]["exit_mode"] = "alvo"; cfg["risk"]["target_r"] = 2.0
    p = Position("X", 1, 100, 95, 5, "t", highest=100)
    acts = manage_position(p, candle(101, 111, 100.5, 108, ema_mid=99), ALTA, cfg)
    assert acts[0].price == 110 and p.qty == 0
    cfg["risk"]["exit_mode"] = "trailing"
    p = Position("X", 1, 100, 95, 5, "t", highest=100)
    manage_position(p, candle(101, 104, 100.5, 103.5, a=1.0, ema_mid=99), ALTA, cfg)
    assert p.stop == 101 and p.qty == 1          # 104 - 3 ATR


def test_btc_filter_blocks_alt_entries_when_btc_not_up(synth, cfg):
    from bot.data import attach_btc_trend
    alt, _ = make(synth, cfg, 0.0008, n=4000, seed=3)
    btc_down, _ = make(synth, cfg, -0.002, n=4000, seed=4)
    cfg["strategy"]["btc_filter"] = True
    alt_f = attach_btc_trend(alt, btc_down)
    assert not any(entry_signal(alt_f, i, alt_f["trend"].iloc[i], cfg).ok for i in range(300, len(alt_f)))
    assert not prefilter_any(alt_f, cfg)
    cfg["strategy"]["btc_filter"] = False
    assert any(entry_signal(alt, i, alt["trend"].iloc[i], cfg).ok for i in range(300, len(alt)))


def prefilter_any(df, cfg):
    from bot.strategy import prefilter
    return bool(prefilter(df, cfg).any())


def test_production_config_is_consistent():
    import yaml
    from pathlib import Path
    c = yaml.safe_load((Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8"))
    assert c["risk"]["exit_mode"] in ("trailing", "parcial", "alvo")
    assert "BTC/USDT" in c["symbols"] or not c["strategy"].get("btc_filter")
    assert c["risk"]["risk_per_trade"] <= 0.02


def test_risk_scale_defense(cfg):
    cfg["risk"]["adaptive_risk"] = {"enabled": True, "drawdown_trigger": 0.05, "factor": 0.5}
    g = RiskGuard(cfg)
    assert g.risk_scale(100) == 1.0
    assert g.risk_scale(96) == 1.0            # -4%: normal
    assert g.risk_scale(94) == 0.5            # -6%: defesa
    assert g.risk_scale(101) == 1.0           # novo pico: volta ao normal
    assert position_size(1000, 100, 95, cfg, 0.5) * 2 == position_size(1000, 100, 95, cfg)


def test_drift_alarm():
    from bot.learn import checar_desvio
    import numpy as np
    hist = list(np.random.default_rng(0).normal(0.2, 1.5, 200))     # histórico com média +0,2R
    assert not checar_desvio(hist[-10:], hist)["alarme"]
    assert checar_desvio([-1.0] * 10, hist)["alarme"]
    assert not checar_desvio([-1.0] * 3, hist)["alarme"]        # poucas operações: não conclui


def test_backtest_window_and_close_at_end(synth, cfg):
    up, _ = make(synth, cfg, 0.0008, n=4000, seed=3)
    mid = int(up["close_ts"].iloc[2500])
    r = run({"UP/USDT": up}, cfg, 1000, end_ts=mid, close_at_end=True)
    assert r.equity_ts[-1] < mid
    assert all(t.closed <= pd.Timestamp(mid, unit="ms", tz="UTC").isoformat() for t in r.trades)
    assert all("adx" in t.features for t in r.trades)


def test_journal_report(tmp_path):
    from bot.learn import ler_diario, registrar, relatorio
    p = tmp_path / "d.jsonl"
    for k in range(12):
        registrar({"origem": "paper", "simbolo": "BTC/USDT", "r": (-1.0 if k % 2 else 2.0),
                   "features": {"adx": 20 + k, "atr_pct": 1 + k / 10, "rsi": 50, "volume_rel": 1.2, "sessao": "EUA"}}, p)
    txt = relatorio(ler_diario(p))
    assert "12 operações" in txt and "EUA" in txt



# ---------------- falhas do modo real (corretora simulada que se comporta como a Binance) ----------------
class LiveLikeBroker:
    """Stop-limit que pode NÃO executar (gap), execução parcial e cancelamento no app."""
    def __init__(self, price=100.0):
        self.px, self.cash, self.sold, self.placed, self.active = price, 1000.0, [], [], True
        self.partial = (0.0, 0.0); self.balance = None; self.filled_stop = False
    def price(self, sym): return self.px
    def amount(self, sym, q): return q
    def min_notional(self, sym): return 5.0
    def usdt_free(self): return self.cash
    def sell(self, sym, q, px=None): self.sold.append(q); self.cash += q * self.px; return self.px, q * self.px
    def place_stop(self, sym, q, s): self.placed.append((q, s)); self.active = True; return f"id{len(self.placed)}"
    def cancel(self, sym, oid): self.active = False; r = self.partial; self.partial = (0.0, 0.0); return r
    def stop_filled(self, sym, oid, s): return (self.filled_stop, s, 950.0) if self.filled_stop else (False, 0.0, 0.0)
    def stop_active(self, sym, oid): return self.active
    def base_balance(self, sym): return self.balance


def live_trader(cfg, tmp_path, br):
    cfg["mode"] = "live"
    tr = Trader(cfg, br, {}, str(tmp_path / "s.json"))
    tr.positions["X/USDT"] = Position("X/USDT", 10.0, 100.0, 95.0, 5.0, "t", highest=100.0, cost=1001.0, stop_order_id="id0")
    return tr


def test_gap_below_stop_sells_at_market(cfg, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    br = LiveLikeBroker(price=90.0)              # caiu de 100 para 90, stop em 95 não executou
    tr = live_trader(cfg, tmp_path, br)
    tr._check_stop("X/USDT", tr.positions["X/USDT"])
    assert br.sold == [10.0] and "X/USDT" not in tr.positions


def test_reprotects_position_without_active_stop(cfg, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    br = LiveLikeBroker(price=100.0); br.active = False      # stop cancelado no aplicativo
    tr = live_trader(cfg, tmp_path, br)
    tr._check_stop("X/USDT", tr.positions["X/USDT"])
    assert br.placed == [(10.0, 95.0)] and tr.positions["X/USDT"].stop_order_id == "id1"


def test_partial_stop_fill_is_accounted(cfg, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    br = LiveLikeBroker(price=100.0); br.partial = (4.0, 380.0)   # stop vendeu 4 antes de cancelar
    tr = live_trader(cfg, tmp_path, br)
    pos = tr.positions["X/USDT"]
    tr._sell("X/USDT", pos, 10.0, "saída")
    assert br.sold == [6.0]                       # vende só o que sobrou
    assert "X/USDT" not in tr.positions


def test_reconcile_detects_manual_sale_and_offline_stop(cfg, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    br = LiveLikeBroker(); br.balance = 0.0
    tr = live_trader(cfg, tmp_path, br)
    tr.reconcile()
    assert "X/USDT" not in tr.positions           # vendida no app: bot para de gerenciar
    br2 = LiveLikeBroker(); br2.balance = 0.0; br2.filled_stop = True
    tr2 = live_trader(cfg, tmp_path, br2)
    tr2.reconcile()
    from bot.learn import ler_diario
    assert "X/USDT" not in tr2.positions and len(ler_diario()) == 1   # stop offline vai para o diário


def test_pause_file_blocks_new_buys(synth, cfg, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "PAUSAR").write_text("")
    e = synth(2500, H1, 0.0008, 3)
    from bot.demo import resample
    cfg["symbols"] = ["UP/USDT"]
    br = FakeBroker(e, resample(e, 4))
    tr = Trader(cfg, br, {}, str(tmp_path / "s.json"))
    while br.n < 2400:
        tr.tick(); br.n += 1
        assert not tr.positions


def test_refuses_key_with_withdrawal_permission(cfg):
    import pytest
    from bot.exchange import LiveBroker
    b = LiveBroker.__new__(LiveBroker)
    b.ex = type("E", (), {"sapi_get_account_apirestrictions": lambda self: {"enableWithdrawals": True, "ipRestrict": True}})()
    with pytest.raises(SystemExit):
        b.check_key_permissions(real_money=True)
    b.ex = type("E", (), {"sapi_get_account_apirestrictions": lambda self: {"enableWithdrawals": False, "ipRestrict": True}})()
    b.check_key_permissions(real_money=True)      # chave correta: passa


def test_single_instance_lock(tmp_path, monkeypatch):
    import pytest
    from bot.__main__ import single_instance
    monkeypatch.chdir(tmp_path)
    first = single_instance("paper")
    with pytest.raises(SystemExit):
        single_instance("paper")
    first.close()


# ---------------- cofre "seguir a tendência" ----------------
D1 = tf_ms("1d")


def _daily(synth, drift, seed, n=700):
    return synth(n, D1, drift, seed)


def test_sleeve_eth_needs_btc_up(synth, cfg):
    from bot import sleeve
    daily = {"BTC/USDT": _daily(synth, -0.004, 1), "ETH/USDT": _daily(synth, 0.004, 2)}
    tr = sleeve.daily_trends(daily, cfg)
    last = int(daily["BTC/USDT"]["ts"].iloc[-1]) + D1
    w = sleeve.wanted(tr, last, ["BTC/USDT", "ETH/USDT"])
    assert w == {"BTC/USDT": False, "ETH/USDT": False}      # ETH em alta, mas BTC em baixa: fica fora
    daily["BTC/USDT"] = _daily(synth, 0.004, 3)
    w = sleeve.wanted(sleeve.daily_trends(daily, cfg), last, ["BTC/USDT", "ETH/USDT"])
    assert w == {"BTC/USDT": True, "ETH/USDT": True}


def test_sleeve_backtest_cash_in_downtrend(synth, cfg):
    from bot import sleeve
    daily = {"BTC/USDT": _daily(synth, -0.004, 1), "ETH/USDT": _daily(synth, -0.004, 2)}
    start = int(daily["BTC/USDT"]["ts"].iloc[300])
    r = sleeve.backtest(daily, cfg, 25, start)
    assert r["trades"] == [] and abs(r["equity"].iloc[-1] - 25) < 1e-9
    daily = {"BTC/USDT": _daily(synth, 0.004, 3), "ETH/USDT": _daily(synth, 0.004, 4)}
    r = sleeve.backtest(daily, cfg, 25, start)
    assert r["trades"] and r["equity"].iloc[-1] > 25


class SleeveBroker(LiveLikeBroker):
    def __init__(self, price=100.0):
        super().__init__(price); self.bought = []
    def buy(self, sym, q): self.bought.append((sym, q)); self.cash -= q * self.px; return q, self.px, q * self.px
    def candles(self, sym, tf, limit=500): return self.daily[sym]


def test_buckets_are_separate_and_rebalance_monthly(cfg, tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from bot.sleeve import TrendSleeve
    monkeypatch.chdir(tmp_path)
    cfg["mode"] = "paper"
    br = SleeveBroker()
    tr = Trader(cfg, br, {}, str(tmp_path / "s.json"))
    tr.sleeve.ensure_funded(tr.equity())
    assert tr.sleeve.st["cash"] == 250.0                     # 25% de 1000
    assert abs(tr.bot_equity() - 750.0) < 1e-9 and abs(tr.bot_free_usdt() - 750.0) < 1e-9
    sl = tr.sleeve
    sl.rebalance(1000, 750, datetime(2026, 1, 15, tzinfo=timezone.utc))   # primeiro mês: só marca
    sl.st["cash"] = 400.0                                    # cofre ficou grande (40%)
    sl.rebalance(1000, 600, datetime(2026, 2, 1, tzinfo=timezone.utc))
    assert sl.st["cash"] == 250.0                            # devolveu 150 ao bot
    sl.st["cash"], sl.st["holdings"]["BTC/USDT"] = 0.0, 1.0  # cofre pequeno (100 de 1000) e com BTC
    sl.rebalance(1000, 900, datetime(2026, 3, 1, tzinfo=timezone.utc))
    assert br.bought and br.bought[-1][0] == "BTC/USDT"     # recebeu caixa do bot e comprou mais BTC
    sl.rebalance(1000, 900, datetime(2026, 3, 20, tzinfo=timezone.utc))
    assert len(br.bought) == 1                               # só uma vez por mês


def test_portfolio_backtest(synth, cfg):
    from bot import sleeve
    from bot.data import prepare
    up, _ = make(synth, cfg, 0.0008, n=9000, seed=3)        # ~375 dias de 1h
    daily = {"BTC/USDT": _daily(synth, 0.003, 3), "ETH/USDT": _daily(synth, 0.003, 4)}
    t0 = int(daily["BTC/USDT"]["ts"].iloc[230])              # após aquecer a EMA200 diária
    r = sleeve.portfolio_backtest({"UP/USDT": up}, daily, cfg, 100, t0)
    assert len(r["equity"]) > 10 and r["queda_max"] < 0.6
