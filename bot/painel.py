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
from urllib.parse import parse_qs, urlparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("bot")


def _tail(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", errors="replace") as f:
        return [x.rstrip("\n") for x in deque(f, maxlen=n)]


class Painel:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host, self.port = host, port
        self.data: dict = {"carregando": True}
        self.charts: dict = {}
        self.lock = threading.Lock()

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
                if u.path in ("/", "/index.html"):
                    self._send(200, HTML.encode(), "text/html; charset=utf-8")
                elif u.path == "/api/status":
                    self._send(200, painel.payload(), "application/json; charset=utf-8")
                elif u.path == "/api/candles":
                    sym = (parse_qs(u.query).get("s") or [""])[0]
                    self._send(200, painel.candles(sym), "application/json; charset=utf-8")
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
    return Painel(host, port)


HTML = (Path(__file__).with_name("static") / "painel.html").read_text(encoding="utf-8")
