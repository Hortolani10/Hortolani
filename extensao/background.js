// Service worker: faz o meio de campo entre a página do protocolo,
// o documento "offscreen" (que lê o PDF) e o sistema externo.

const OFFSCREEN = 'offscreen.html';

async function garantirOffscreen() {
  const existentes = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });
  if (existentes.length) return;
  await chrome.offscreen.createDocument({
    url: OFFSCREEN,
    reasons: ['WORKERS'],
    justification: 'Ler o texto do PDF do pedido de compra com pdf.js',
  });
}

async function lerPdf(url) {
  await garantirOffscreen();
  return chrome.runtime.sendMessage({ alvo: 'offscreen', tipo: 'lerPdf', url });
}

async function enviar(pedido) {
  const { endpoint, chave } = await chrome.storage.sync.get(['endpoint', 'chave']);
  if (!endpoint) throw new Error('Configure o endereço do sistema externo nas opções da extensão.');
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(chave ? { 'x-api-key': chave } : {}) },
    body: JSON.stringify(pedido),
  });
  const texto = await resp.text();
  if (!resp.ok) throw new Error(`Sistema externo respondeu ${resp.status}: ${texto.slice(0, 200)}`);
  const { enviados = {} } = await chrome.storage.local.get('enviados');
  enviados[pedido.pedido] = new Date().toISOString();
  await chrome.storage.local.set({ enviados });
  return { ok: true };
}

chrome.runtime.onMessage.addListener((msg, _sender, responder) => {
  if (msg.alvo !== 'background') return false;
  const tarefa =
    msg.tipo === 'lerPdf' ? lerPdf(msg.url)
    : msg.tipo === 'enviar' ? enviar(msg.pedido)
    : Promise.reject(new Error('mensagem desconhecida'));
  tarefa.then(
    (r) => responder(r),
    (e) => responder({ erro: e.message || String(e) }),
  );
  return true; // resposta assíncrona
});
