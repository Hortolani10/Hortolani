// Service worker: faz o meio de campo entre a página do protocolo,
// o documento "offscreen" (que lê o PDF) e o sistema externo.

const OFFSCREEN = 'offscreen.html';
const APP_URL_PADRAO = 'https://ventriculo-app.vercel.app/pedidos/cadastrar';

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
  const { appUrl, endpoint } = await chrome.storage.sync.get(['appUrl', 'endpoint']);
  const baseUrl = appUrl || endpoint || APP_URL_PADRAO;

  let url;
  try {
    url = new URL('/pedidos/cadastrar', baseUrl);
  } catch {
    throw new Error('O endereço do Ventriculo não é válido.');
  }

  const payload = {
    version: 1,
    source: 'leitor-pedidos-extensao',
    ata: {
      numero: pedido.ata || '',
      diasParaEntrega: 7,
      diasUteis: true,
      fiscal: '',
    },
    empresa: {
      nomeEmpresa: pedido.empresa || '',
      cnpj: pedido.cnpj || '',
    },
    pedido: {
      numeroPedido: pedido.pedido || '',
      ataNumero: pedido.ata || '',
      empresaCnpj: pedido.cnpj || '',
      dataPedido: pedido.dataPedido || '',
      numeroProtocolo: pedido.protocolo || '',
      diretoria: pedido.diretoria || '',
      valorPedido: pedido.valor || 0,
    },
  };

  url.hash = `importar-pedido=${encodeURIComponent(JSON.stringify(payload))}`;
  if (url.href.length > 16000) throw new Error('O pedido é grande demais para ser enviado ao Ventriculo.');
  await chrome.tabs.create({ url: url.href });
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
