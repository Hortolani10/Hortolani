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
        self.lock = threading.Lock()

    def update(self, snap: dict) -> None:
        with self.lock:
            self.data = snap

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
                if self.path in ("/", "/index.html"):
                    self._send(200, HTML.encode(), "text/html; charset=utf-8")
                elif self.path == "/api/status":
                    self._send(200, painel.payload(), "application/json; charset=utf-8")
                else:
                    self._send(404, b"nao encontrado", "text/plain")

        try:
            srv = ThreadingHTTPServer((self.host, self.port), H)
        except OSError as e:
            log.warning("painel não iniciou na porta %s: %s", self.port, e)
            return
        threading.Thread(target=srv.serve_forever, daemon=True, name="painel").start()
        log.info("Painel ao vivo: http://localhost:%s (abra no navegador)", self.port)


def from_config(cfg: dict) -> Painel | None:
    pc = cfg.get("painel") or {}
    if not pc.get("enabled", True):
        return None
    host = os.getenv("PAINEL_HOST", pc.get("host", "127.0.0.1"))
    return Painel(host, int(pc.get("port", 8765)))


HTML = r"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bot Hortolani · ao vivo</title>
<style>
:root{--bg:#eef1f4;--panel:#fff;--fg:#142029;--muted:#5a6875;--line:#d9e0e6;--soft:#f5f7f9;--up:#0b8f63;--down:#cf3f3f;--flat:#b07a00;--accent:#2457d6}
@media (prefers-color-scheme:dark){:root{--bg:#0c1218;--panel:#121b23;--fg:#e3eaf0;--muted:#8b9aa7;--line:#223140;--soft:#172230;--up:#2cc38a;--down:#f06b6b;--flat:#f2b84b;--accent:#6b9bff;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 40px;display:grid;gap:16px}
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:8px}
h1{margin:0;font-size:26px}h2{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
.muted{color:var(--muted)}.num{font-family:ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums}
.live{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
.dot{width:9px;height:9px;border-radius:50%;background:var(--up);box-shadow:0 0 0 0 var(--up);animation:p 2s infinite}
.dot.off{background:var(--down);animation:none}@keyframes p{0%{box-shadow:0 0 0 0 rgba(44,195,138,.6)}100%{box-shadow:0 0 0 10px rgba(44,195,138,0)}}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 16px;min-width:0}
.kpi b{display:block;font-size:22px;font-weight:600}.kpi span{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.tag{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:2px 8px;border-radius:4px;border:1px solid var(--line)}
.up{color:var(--up)}.down{color:var(--down)}.flat{color:var(--flat)}
.tw{overflow-x:auto}table{width:100%;border-collapse:collapse}th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}tr:last-child td{border-bottom:0}
.bar{height:8px;background:var(--soft);border-radius:4px;overflow:hidden;min-width:90px}.bar i{display:block;height:100%;background:var(--accent)}
.sig{font-weight:700}pre{margin:0;max-height:320px;overflow:auto;font:12px/1.5 ui-monospace,Consolas,monospace;white-space:pre-wrap;word-break:break-word}
.grid2{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}
@media(max-width:820px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.grid2{grid-template-columns:minmax(0,1fr)}}
</style></head><body><div class="wrap">
<header><div><h1>Bot Hortolani <span class="tag" id="modo">—</span></h1>
<div class="muted">Entrada no <span id="tfe"></span> · tendência no <span id="tft"></span> · atualiza sozinho a cada 5 s</div></div>
<div class="live"><i class="dot" id="dot"></i><span id="hora">conectando…</span></div></header>
<section class="kpis">
<div class="card kpi"><span>Carteira</span><b class="num" id="k1">—</b></div>
<div class="card kpi"><span>Bot</span><b class="num" id="k2">—</b></div>
<div class="card kpi"><span>Cofre de tendência</span><b class="num" id="k3">—</b><small class="muted" id="k3b"></small></div>
<div class="card kpi"><span>Situação</span><b id="k4">—</b></div>
</section>
<section class="card"><h2>Radar — o que o bot está vendo agora</h2><div class="tw"><table>
<thead><tr><th>Moeda</th><th>Preço</th><th>Tendência diária</th><th>BTC</th><th>Regras de entrada</th><th>RSI</th><th>ADX</th><th>Sinal</th><th>Falta</th></tr></thead>
<tbody id="radar"><tr><td colspan="9" class="muted">Aguardando o primeiro ciclo…</td></tr></tbody></table></div></section>
<section class="card"><h2>Posições abertas</h2><div class="tw"><table>
<thead><tr><th>Moeda</th><th>Estratégia</th><th>Entrada</th><th>Agora</th><th>Resultado</th><th>Stop</th><th>Aberta em</th></tr></thead>
<tbody id="pos"></tbody></table></div></section>
<div class="grid2">
<section class="card"><h2>Diário (últimas operações)</h2><div class="tw"><table>
<thead><tr><th>Origem</th><th>Moeda</th><th>Resultado</th><th>Motivo</th></tr></thead><tbody id="diario"></tbody></table></div></section>
<section class="card"><h2>Log ao vivo</h2><pre id="log"></pre></section>
</div>
<p class="muted">Somente leitura: este painel não compra, não vende e não muda nada. Visível só neste computador.</p>
</div>
<script>
const $=id=>document.getElementById(id);
const fmt=(v,d=2)=>v==null?"—":Number(v).toLocaleString("pt-BR",{minimumFractionDigits:d,maximumFractionDigits:d});
const px=v=>{const a=Math.abs(v);return fmt(v,a>=100?2:a>=1?4:6)};
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const cls=t=>t==="ALTA"?"up":t==="BAIXA"?"down":"flat";
const NOMES={tendencia_maior:"tendência da moeda",mercado_btc:"BTC em alta",emas_alinhadas:"médias alinhadas",pullback:"pullback",gatilho:"gatilho",rsi:"RSI",macd:"MACD",adx:"força (ADX)",volume:"volume",nao_esticado:"não esticado",reward_risk:"espaço até resistência"};
async function load(){
 try{
  const r=await fetch("/api/status",{cache:"no-store"});const d=await r.json();
  $("dot").className="dot";$("hora").textContent="ao vivo · "+new Date().toLocaleTimeString("pt-BR");
  if(d.carregando){return}
  $("modo").textContent=d.modo==="paper"?"PAPER (dinheiro fictício)":d.modo;
  $("tfe").textContent=d.timeframes.entry;$("tft").textContent=d.timeframes.trend;
  $("k1").textContent=fmt(d.carteira)+" USDT";$("k2").textContent=fmt(d.bot)+" USDT";$("k3").textContent=fmt(d.cofre)+" USDT";
  const cm=Object.keys(d.cofre_moedas||{});$("k3b").textContent=cm.length?"segurando "+cm.map(s=>s.split("/")[0]).join(", "):"em USDT (aguardando tendência)";
  $("k4").innerHTML=d.pausado?'<span class="flat">Pausado</span>':d.alarme?'<span class="down">Alarme de desvio</span>':'<span class="up">Operando</span>';
  const rad=Object.entries(d.radar||{}).sort((a,b)=>b[1].regras_ok-a[1].regras_ok);
  $("radar").innerHTML=rad.length?rad.map(([s,x])=>{
   const pct=100*x.regras_ok/x.regras_total;
   const sig=x.sinal_tendencia?'<span class="sig up">COMPRA (tendência)</span>':x.sinal_lateral?'<span class="sig flat">'+(d.lateral_ligada?"COMPRA (lateral)":"lateral (observando)")+'</span>':'<span class="muted">aguardando</span>';
   const falta=(x.falhou||[]).slice(0,3).map(k=>NOMES[k]||k).join(", ")+((x.falhou||[]).length>3?"…":"");
   return `<tr><td><b>${esc(s.split("/")[0])}</b></td><td class="num">${px(x.preco)}</td><td class="${cls(x.tendencia)}">${esc(x.tendencia.toLowerCase())}</td><td class="${cls(x.btc)}">${esc((x.btc||"").toLowerCase())}</td><td><div style="display:flex;gap:8px;align-items:center"><div class="bar"><i style="width:${pct}%"></i></div><span class="num">${x.regras_ok}/${x.regras_total}</span></div></td><td class="num">${fmt(x.rsi,1)}</td><td class="num">${fmt(x.adx,1)}</td><td>${sig}</td><td class="muted">${esc(falta)}</td></tr>`}).join(""):'<tr><td colspan="9" class="muted">Aguardando o primeiro ciclo…</td></tr>';
  $("pos").innerHTML=(d.posicoes||[]).length?d.posicoes.map(p=>`<tr><td><b>${esc(p.simbolo)}</b></td><td>${esc(p.estrategia)}</td><td class="num">${px(p.entrada)}</td><td class="num">${px(p.preco)}</td><td class="num ${p.resultado_pct>=0?"up":"down"}">${p.resultado_pct>=0?"+":""}${fmt(p.resultado_pct*100)}%</td><td class="num">${px(p.stop)}</td><td class="muted">${esc(String(p.aberta).slice(0,16).replace("T"," "))}</td></tr>`).join(""):'<tr><td colspan="7" class="muted">Nenhuma posição aberta — o bot está esperando um sinal.</td></tr>';
  $("diario").innerHTML=(d.diario||[]).length?d.diario.map(j=>`<tr><td class="muted">${esc(j.origem)}</td><td>${esc(j.simbolo)}</td><td class="num ${j.r>=0?"up":"down"}">${j.r>=0?"+":""}${fmt(j.r)}R</td><td class="muted">${esc(j.motivo)}</td></tr>`).join(""):'<tr><td colspan="4" class="muted">Ainda sem operações registradas.</td></tr>';
  const lg=$("log"),atBottom=lg.scrollTop+lg.clientHeight>=lg.scrollHeight-20;lg.textContent=(d.log||[]).join("\n");if(atBottom)lg.scrollTop=lg.scrollHeight;
 }catch(e){$("dot").className="dot off";$("hora").textContent="sem conexão com o bot (ele está rodando?)"}
}
load();setInterval(load,5000);
</script></body></html>"""
