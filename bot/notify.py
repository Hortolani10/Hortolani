"""Avisos no Telegram e sinal de vida (bot parado).

Configuração no .env (opcional — sem isso o bot roda normalmente, só não avisa):
    TELEGRAM_BOT_TOKEN=123456:ABC...     (crie com o @BotFather)
    TELEGRAM_CHAT_ID=123456789           (o seu chat; veja o README)
    HEALTHCHECK_URL=https://hc-ping.com/<uuid>   (healthchecks.io: avisa se o bot PARAR)

Segurança:
  * Comandos só são aceitos do TELEGRAM_CHAT_ID configurado; os demais são ignorados.
  * Pelo Telegram só dá para ver o status e pausar/retomar novas compras. Não existe
    comando para comprar, vender, sacar ou mudar configuração.
  * Uma falha do Telegram nunca derruba o bot.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request

log = logging.getLogger("bot")

# Mensagens do log que viram aviso no celular (o resto fica só no arquivo de log)
AVISAR = ("COMPRA ", "VENDA ", "STOP executado", "FECHOU ", "COFRE COMPRA", "COFRE VENDA",
          "COFRE reequilíbrio:", "ALARME", "SEGURANÇA", "Bot iniciado", "MODO LIVE", "gap", "sem stop ativo",
          "executado parcialmente", "Venda manual", "bot desligado")


def _post(url: str, data: dict, timeout: float = 10.0) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310 - URL fixa https da API do Telegram
        return json.loads(r.read().decode())


class Telegram:
    API = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, token: str | None = None, chat_id: str | None = None, post=_post):
        self.token = token if token is not None else os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = str(chat_id if chat_id is not None else os.getenv("TELEGRAM_CHAT_ID", ""))
        self._post = post
        self._last: dict[str, float] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def _call(self, method: str, **data) -> dict | None:
        if not self.enabled:
            return None
        try:
            return self._post(self.API.format(token=self.token, method=method), data)
        except Exception as e:  # rede, Telegram fora do ar etc.: nunca derruba o bot
            logging.getLogger("bot.notify").debug("telegram %s falhou: %s", method, e)
            return None

    def send(self, text: str, dedupe_s: float = 60.0) -> None:
        """Envia uma mensagem. Mensagens idênticas em menos de `dedupe_s` são ignoradas."""
        now = time.time()
        if now - self._last.get(text, 0) < dedupe_s:
            return
        self._last[text] = now
        self._call("sendMessage", chat_id=self.chat_id, text=text[:4000])

    def commands(self, offset: int) -> tuple[list[str], int]:
        """Lê comandos novos (só do chat autorizado). Devolve (comandos, novo offset)."""
        r = self._call("getUpdates", offset=offset, timeout=0)
        if not r or not r.get("ok"):
            return [], offset
        cmds = []
        for u in r.get("result", []):
            offset = max(offset, int(u["update_id"]) + 1)
            msg = u.get("message") or {}
            if str((msg.get("chat") or {}).get("id")) != self.chat_id:
                continue                                  # ignora qualquer outra pessoa
            text = (msg.get("text") or "").strip().split()
            if text:
                cmds.append(text[0].split("@")[0].lower())
        return cmds, offset


class TelegramLogHandler(logging.Handler):
    """Encaminha para o Telegram os eventos importantes do log e todos os erros."""

    def __init__(self, tg: Telegram, prefix: str = "", so_erros: bool = False):
        super().__init__(level=logging.INFO)
        self.tg, self.prefix, self.so_erros = tg, prefix, so_erros

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("bot.notify"):
            return
        try:
            msg = record.getMessage()
        except Exception:
            return
        if record.levelno >= logging.ERROR:
            self.tg.send(f"{self.prefix}⚠️ ERRO: {msg[:500]}", dedupe_s=900)
        elif self.so_erros:
            return
        elif record.levelno >= logging.WARNING or any(k in msg for k in AVISAR):
            self.tg.send(f"{self.prefix}{msg}")


def ping_health(url: str | None = None, fail: bool = False) -> None:
    """Sinal de vida para o healthchecks.io: se os pings pararem, ele avisa você."""
    url = url if url is not None else os.getenv("HEALTHCHECK_URL", "")
    if not url:
        return
    try:
        urllib.request.urlopen(url + ("/fail" if fail else ""), timeout=10).read()  # nosec B310 - URL do usuário
    except Exception as e:
        logging.getLogger("bot.notify").debug("healthcheck falhou: %s", e)
