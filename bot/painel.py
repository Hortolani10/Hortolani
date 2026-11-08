"""Painel ao vivo do bot, no navegador: http://localhost:8765

Segurança: por padrão só aceita conexões do PRÓPRIO computador (127.0.0.1) e só mostra
informações — não existe nenhum botão ou rota que compre, venda ou mude configuração.
No VPS, acesse por túnel SSH:  ssh -L 8765:localhost:8765 bot@IP  e abra http://localhost:8765
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlencode, urlparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("bot")


def _tail(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="replace") as f:
        return [x.rstrip("\n") for x in deque(f, maxlen=n)]


def _get_json(url: str, timeout: float = 4.0) -> dict:
    """Busca o /api/status de outro bot (endereço fixo do config, nunca vindo do navegador)."""
    with urllib.request.urlopen(url, timeout=timeout) as r:  # nosec B310 - só URLs do config.yaml
        return json.loads(r.read().decode("utf-8"))


def resumo_bot(nome: str, d: dict | None, erro: str | None = None) -> dict:
    """Cartão da Central: saldo, lucro/prejuízo (realizado e em aberto) e estatísticas."""
    if not d or d.get("carregando"):
        return {"id": nome, "online": False, "erro": erro or "carregando"}
    dz = d.get("desempenho") or {}
    ini = float(d.get("inicial") or 0) or None
    cart = float(d.get("carteira") or 0)
    lucro = cart - ini if ini else None
    real = float(dz.get("realizado") or 0)
    eh = d.get("equity_hist") or []
    passo = max(1, len(eh) // 120)
    return {"id": nome, "online": True, "nome": d.get("nome"), "modo": d.get("modo"), "real": d.get("real"),
            "tf": (d.get("timeframes") or {}).get("entry"), "aprendiz": bool(d.get("aprendiz")),
            "carteira": cart, "inicial": ini, "lucro": lucro, "lucro_pct": (lucro / ini) if ini else None,
            "realizado": real, "aberto": (lucro - real) if lucro is not None else None,
            "posicoes": len(d.get("posicoes") or []), "ops": dz.get("ops", 0), "acerto": dz.get("acerto"),
            "media_r": dz.get("media_r"), "hoje_pnl": dz.get("hoje_pnl"), "hoje_ops": dz.get("hoje_ops", 0),
            "pausado": d.get("pausado"), "agora": d.get("agora"), "termometro": d.get("termometro"),
            "equity": [v for _, v in eh[::passo]][-120:], "por_setup": dz.get("por_setup") or {},
            "por_padrao": dz.get("por_padrao") or {},
            "ultimas": [{**j, "bot": nome} for j in (d.get("diario") or [])[:10]]}


def ranking(bots: list[dict], chave: str) -> list[dict]:
    """Junta as estatísticas de todos os bots por setup (ou padrão) e ordena pela média em R."""
    tot: dict[str, dict] = {}
    for b in bots:
        for k, v in (b.get(chave) or {}).items():
            t = tot.setdefault(k, {"nome": k, "ops": 0, "ganhos": 0, "soma_r": 0.0, "pnl": 0.0, "bots": []})
            t["ops"] += v.get("ops", 0)
            t["ganhos"] += v.get("ganhos", 0)
            t["soma_r"] += v.get("soma_r", 0.0)
            t["pnl"] += v.get("pnl", 0.0)
            t["bots"].append(b.get("tf") or b["id"])
    out = []
    for t in tot.values():
        if t["ops"]:
            out.append({**t, "acerto": t["ganhos"] / t["ops"], "media_r": t["soma_r"] / t["ops"]})
    return sorted(out, key=lambda x: (-x["media_r"], -x["ops"]))


class Painel:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765, nome: str = "principal",
                 outros: dict[str, str] | None = None):
        self.host, self.port = host, port
        self.nome = nome
        self.outros = dict(outros or {})                 # nome -> endereço base (fixos no config)
        self.data: dict = {"carregando": True}
        self.charts: dict = {}
        self.lock = threading.Lock()
        self._central: tuple[float, bytes] | None = None

    def update(self, snap: dict, charts: dict | None = None) -> None:
        with self.lock:
            self.data = snap
            if charts is not None:
                self.charts = dict(charts)

    def candles(self, sym: str) -> bytes:
        with self.lock:
            c = self.charts.get(sym)
        trades = []
        for line in _tail(Path("logs/diario.jsonl"), 400):
            try:
                j = json.loads(line)
            except ValueError:
                continue
            if j.get("simbolo") == sym:
                trades.append({k: j.get(k) for k in ("aberta", "fechada", "entrada", "saida", "r", "motivo", "origem")})
        return json.dumps({"simbolo": sym, "candles": c, "operacoes": trades}, default=str).encode()

    def payload(self) -> bytes:
        with self.lock:
            d = dict(self.data)
        d["log"] = _tail(Path("logs/bot.log"), 40)
        diario = []
        for line in _tail(Path("logs/diario.jsonl"), 15):
            try:
                diario.append(json.loads(line))
            except ValueError:
                pass
        d["diario"] = diario[::-1]
        return json.dumps(d, ensure_ascii=False, default=str).encode()

    def proxy(self, nome: str, caminho: str) -> bytes | None:
        """Repassa /api/status ou /api/candles de outro bot (só nomes da lista fixa)."""
        url = self.outros.get(nome)
        if not url:
            return None
        try:
            with urllib.request.urlopen(url.rstrip("/") + caminho, timeout=6) as r:  # nosec B310
                return r.read()
        except Exception as e:
            return json.dumps({"carregando": True, "erro": f"{nome} fora do ar: {type(e).__name__}"}).encode()

    def central(self) -> bytes:
        """Todos os bots numa resposta só (guardada 5 s para não sobrecarregar)."""
        if self._central and time.time() - self._central[0] < 5:
            return self._central[1]
        bots = [resumo_bot(self.nome, json.loads(self.payload()))]

        def busca(item):
            n, url = item
            try:
                return resumo_bot(n, _get_json(url.rstrip("/") + "/api/status"))
            except Exception as e:
                return resumo_bot(n, None, f"fora do ar ({type(e).__name__})")

        if self.outros:
            with ThreadPoolExecutor(max_workers=len(self.outros)) as ex:
                bots += list(ex.map(busca, self.outros.items()))
        on = [b for b in bots if b.get("online")]
        ultimas = sorted((j for b in on for j in b.pop("ultimas", [])), key=lambda j: str(j.get("fechada")), reverse=True)[:20]
        body = json.dumps({"agora": time.time(), "bots": bots, "setups": ranking(on, "por_setup"),
                           "padroes": ranking(on, "por_padrao"), "ultimas": ultimas},
                          ensure_ascii=False, default=str).encode()
        self._central = (time.time(), body)
        return body

    def start(self) -> None:
        painel = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):        # não polui o terminal
                pass

            def _send(self, code, body: bytes, ctype: str):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                bot = (q.get("b") or [""])[0]
                outro = bot and bot != painel.nome
                if outro and bot not in painel.outros:
                    self._send(404, b"bot desconhecido", "text/plain")
                elif u.path in ("/", "/index.html", "/central"):
                    self._send(200, CENTRAL.encode(), "text/html; charset=utf-8")
                elif u.path == "/bot":
                    self._send(200, HTML.encode(), "text/html; charset=utf-8")
                elif u.path == "/api/central":
                    self._send(200, painel.central(), "application/json; charset=utf-8")
                elif u.path == "/api/status":
                    body = painel.proxy(bot, "/api/status") if outro else painel.payload()
                    self._send(200, body, "application/json; charset=utf-8")
                elif u.path == "/api/candles":
                    sym = (q.get("s") or [""])[0]
                    if outro:
                        body = painel.proxy(bot, "/api/candles?" + urlencode({"s": sym}))
                    else:
                        body = painel.candles(sym)
                    self._send(200, body, "application/json; charset=utf-8")
                elif u.path == "/static/lw.js":
                    self._send(200, LW_JS.read_bytes(), "application/javascript")
                else:
                    self._send(404, b"nao encontrado", "text/plain")

        try:
            srv = ThreadingHTTPServer((self.host, self.port), H)
        except OSError as e:
            log.warning("painel não iniciou na porta %s: %s", self.port, e)
            return
        threading.Thread(target=srv.serve_forever, daemon=True, name="painel").start()
        log.info("Painel ao vivo: http://localhost:%s (abra no navegador)", self.port)


LW_JS = Path(__file__).with_name("static") / "lightweight-charts.js"   # TradingView Lightweight Charts (Apache 2.0)


def from_config(cfg: dict) -> Painel | None:
    pc = cfg.get("painel") or {}
    if not pc.get("enabled", True):
        return None
    host = os.getenv("PAINEL_HOST", pc.get("host", "127.0.0.1"))
    port = int(pc.get("port", 8765)) + (1 if cfg.get("mode") == "live" else 0)   # paper 8765, testnet/real 8766
    nome = cfg.get("instancia") or "principal"
    return Painel(host, port, nome, pc.get("outros") or {})


HTML = (Path(__file__).with_name("static") / "painel.html").read_text(encoding="utf-8")
CENTRAL = (Path(__file__).with_name("static") / "central.html").read_text(encoding="utf-8")
