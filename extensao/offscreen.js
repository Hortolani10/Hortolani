// Documento invisível da extensão: baixa o PDF e extrai os campos do pedido.
import * as pdfjs from './vendor/pdf.min.mjs';
import { extrairLinhas, lerPedido } from './lib/pedido-parser.js';

pdfjs.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL('vendor/pdf.worker.min.mjs');

async function lerPdf(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Não consegui baixar o PDF (${resp.status})`);
  const dados = new Uint8Array(await resp.arrayBuffer());
  const doc = await pdfjs.getDocument({ data: dados }).promise;
  try {
    return lerPedido(await extrairLinhas(doc));
  } finally {
    doc.destroy();
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, responder) => {
  if (msg.alvo !== 'offscreen' || msg.tipo !== 'lerPdf') return false;
  lerPdf(msg.url).then(
    (pedido) => responder({ pedido }),
    (e) => responder({ erro: e.message || String(e) }),
  );
  return true;
});
