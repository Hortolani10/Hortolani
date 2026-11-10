// Service worker: faz o meio de campo entre a página do protocolo,
// o documento "offscreen" (que lê o PDF), a fila de pedidos e o Ventrículo.
import { camposFaltando } from './lib/pedido-parser.js';

const OFFSCREEN = 'offscreen.html';
const APP_URL_PADRAO = 'https://ventriculo-app.vercel.app/pedidos/cadastrar';

// Várias abas podem pedir leitura ao mesmo tempo: o documento é criado uma vez só.
let criando = null;
async function garantirOffscreen() {
  const existentes = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });
  if (existentes.length) return;
  criando ??= chrome.offscreen
    .createDocument({
      url: OFFSCREEN,
      reasons: ['WORKERS'],
      justification: 'Ler o texto do PDF do pedido de compra com pdf.js',
    })
    .finally(() => (criando = null));
  await criando;
}

async function lerPdf(url) {
  await garantirOffscreen();
  // logo após ser criado, o documento pode ainda não estar ouvindo: tenta de novo por alguns segundos
  for (let tentativa = 0; ; tentativa++) {
    try {
      return await chrome.runtime.sendMessage({ alvo: 'offscreen', tipo: 'lerPdf', url });
    } catch (e) {
      if (tentativa >= 20 || !/Receiving end does not exist/i.test(e.message)) throw e;
      await new Promise((r) => setTimeout(r, 250));
    }
  }
}

// ---------- fila ----------
// chrome.storage.local.fila = { "4758/0-2026": { pedido, avisos, adicionadoEm, abertoEm } }
// A chave é o número do pedido, que já inclui o ano: o mesmo pedido nunca entra duas vezes.

// Gravações uma de cada vez: evita que duas abas gravem ao mesmo tempo e uma apague a outra.
let gravacao = Promise.resolve();
function serializar(fn) {
  const tarefa = gravacao.then(fn);
  gravacao = tarefa.catch(() => {});
  return tarefa;
}

function alterarFila(fn) {
  return serializar(async () => {
    const { fila = {}, enviados = {} } = await chrome.storage.local.get(['fila', 'enviados']);
    const resultado = await fn(fila, enviados);
    await chrome.storage.local.set({ fila });
    return resultado;
  });
}

function adicionarFila(pedido) {
  return alterarFila((fila, enviados) => {
    const anterior = fila[pedido.pedido];
    fila[pedido.pedido] = {
      pedido,
      avisos: camposFaltando(pedido),
      adicionadoEm: anterior?.adicionadoEm || new Date().toISOString(),
      // "enviados" é onde a versão 0.2 guardava os pedidos já abertos
      abertoEm: anterior?.abertoEm || enviados[pedido.pedido] || null,
    };
    return fila[pedido.pedido];
  });
}

const removerFila = (numero) => alterarFila((fila) => void delete fila[numero]);
const limparFila = () => alterarFila((fila) => Object.keys(fila).forEach((k) => delete fila[k]));

// ---------- Ventrículo ----------
async function enderecoVentriculo(caminho) {
  const { appUrl, endpoint } = await chrome.storage.sync.get(['appUrl', 'endpoint']);
  try {
    return new URL(caminho, appUrl || endpoint || APP_URL_PADRAO);
  } catch {
    throw new Error('O endereço do Ventriculo não é válido.');
  }
}

/** Um pedido no formato que a tela de cadastro do Ventrículo entende. */
function itemVentriculo(pedido) {
  // O prazo certo é o da ata oficial cadastrada no Ventrículo. Mas a tela de cadastro
  // do Ventrículo só preenche o formulário se o bloco "ata" vier completo (testado: sem
  // diasParaEntrega/diasUteis/fiscal ela abre vazia). Por isso os campos vão no formato
  // que o Ventrículo espera; o ideal é o Ventrículo ignorá-los quando a ata já existe.
  return {
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
}

// Só sabemos que a tela foi aberta; quem salva é a pessoa, lá no Ventrículo.
function marcarAbertos(pedidos) {
  const abertoEm = new Date().toISOString();
  return alterarFila((fila) => {
    for (const pedido of pedidos) {
      fila[pedido.pedido] = { avisos: [], adicionadoEm: abertoEm, ...fila[pedido.pedido], pedido, abertoEm };
    }
    return abertoEm;
  });
}

/** Um pedido: abre /pedidos/cadastrar preenchido. */
async function enviar(pedido, { ativa = true } = {}) {
  const avisos = camposFaltando(pedido);
  if (avisos.length) throw new Error(avisos.join('; '));
  const url = await enderecoVentriculo('/pedidos/cadastrar');
  url.hash = `importar-pedido=${encodeURIComponent(
    JSON.stringify({ version: 1, source: 'leitor-pedidos-extensao', ...itemVentriculo(pedido) }),
  )}`;
  if (url.href.length > 16000) throw new Error('O pedido é grande demais para ser enviado ao Ventriculo.');
  await chrome.tabs.create({ url: url.href, active: ativa });
  return { ok: true, abertoEm: await marcarAbertos([pedido]) };
}

/**
 * Vários pedidos numa aba só: /pedidos/cadastrar#importar-pedidos=...
 * A mesma tela de cadastro, que já importa vários PDFs, recebe a lista
 * (ver docs/importacao-em-lote.md).
 */
async function enviarLote(pedidos) {
  const url = await enderecoVentriculo('/pedidos/cadastrar');
  url.hash = `importar-pedidos=${encodeURIComponent(
    JSON.stringify({ version: 2, source: 'leitor-pedidos-extensao', pedidos: pedidos.map(itemVentriculo) }),
  )}`;
  // o Chrome aceita endereços de até ~2 MB; dá folga para centenas de pedidos
  if (url.href.length > 1_500_000) throw new Error('Pedidos demais para uma aba só: importe em partes.');
  await chrome.tabs.create({ url: url.href, active: true });
  await marcarAbertos(pedidos);
}

// Importar todos os pedidos prontos da fila (sem aviso e ainda não abertos).
// - modo lote ligado (configuração): uma aba só, com a tela de lote do Ventrículo;
// - senão: uma aba do Ventrículo para cada pedido (a primeira fica em foco).
// Quando existir a gravação automática, é aqui que ela entra.
async function importarTodos() {
  const { fila = {} } = await chrome.storage.local.get('fila');
  const prontos = Object.values(fila)
    .filter((i) => !i.abertoEm && !i.avisos?.length)
    .map((i) => i.pedido);
  if (!prontos.length) return { abertos: 0, falhas: [], lote: false };

  const { importarEmLote = false } = await chrome.storage.sync.get('importarEmLote');
  if (importarEmLote) {
    await enviarLote(prontos);
    return { abertos: prontos.length, falhas: [], lote: true };
  }

  let abertos = 0;
  const falhas = [];
  for (const [n, pedido] of prontos.entries()) {
    try {
      await enviar(pedido, { ativa: n === 0 });
      abertos++;
    } catch (e) {
      falhas.push(`${pedido.pedido}: ${e.message}`);
    }
    await new Promise((r) => setTimeout(r, 300)); // não abre tudo no mesmo instante
  }
  return { abertos, falhas, lote: false };
}

// ---------- leitura dos protocolos em "Receber" ----------
// Abre cada protocolo numa aba em segundo plano; o content script lê o pedido,
// coloca na fila e avisa "protocoloLido"; aí a aba é fechada.
// chrome.storage.local.protocolosLidos = { "10880/2026": { lidoEm, pedidos: [...], erros: [...] } }
const SIMULTANEOS = 2;
const TEMPO_MAX_MS = 60000;
const esperando = new Map(); // tabId -> resolve

function registrarLido(protocolo, pedidos, erros) {
  if (!protocolo) return;
  return serializar(async () => {
    const { protocolosLidos = {} } = await chrome.storage.local.get('protocolosLidos');
    protocolosLidos[protocolo] = { lidoEm: new Date().toISOString(), pedidos, erros };
    await chrome.storage.local.set({ protocolosLidos });
  });
}

async function protocoloLido(m, sender) {
  const tabId = sender.tab?.id;
  // aberto pela leitura em segundo plano: quem registra é varrer(), com o número da lista
  if (esperando.has(tabId)) return esperando.get(tabId)(m);
  await registrarLido(m.protocolo, m.pedidos || [], m.erros || []); // aberto pela pessoa
}

function lerEmSegundoPlano(url) {
  return new Promise((ok) => {
    let tabId;
    const fim = (r) => {
      clearTimeout(timer);
      esperando.delete(tabId);
      if (tabId != null) chrome.tabs.remove(tabId).catch(() => {});
      ok(r);
    };
    const timer = setTimeout(() => fim({ erros: ['O protocolo demorou demais para abrir'] }), TEMPO_MAX_MS);
    chrome.tabs.create({ url, active: false }).then(
      (tab) => { tabId = tab.id; esperando.set(tabId, fim); },
      (e) => fim({ erros: [e.message] }),
    );
  });
}

let varrendo = false;
async function varrer({ protocolos, forcar }) {
  if (varrendo) throw new Error('Já existe uma leitura em andamento.');
  const { protocolosLidos = {} } = await chrome.storage.local.get('protocolosLidos');
  const fila = protocolos.filter(
    (p) => forcar || !protocolosLidos[p.protocolo] || protocolosLidos[p.protocolo].erros?.length,
  );
  const estado = { inicio: new Date().toISOString(), total: fila.length, feitos: 0, pedidos: 0, semPedido: 0, erros: 0, fim: null };
  const salvar = () => chrome.storage.local.set({ varredura: { ...estado } });
  varrendo = true;
  await salvar();
  try {
    const trabalhador = async () => {
      while (fila.length) {
        const p = fila.shift();
        const r = await lerEmSegundoPlano(p.url);
        // registra pelo número da lista; se teve erro, fica marcado e é tentado de novo
        await registrarLido(p.protocolo, r.pedidos || [], r.erros || []);
        if (r.erros?.length && !r.pedidos?.length) estado.erros++;
        else if (!r.pedidos?.length) estado.semPedido++;
        else estado.pedidos += r.pedidos.length;
        estado.feitos++;
        await salvar();
      }
    };
    await Promise.all(Array.from({ length: SIMULTANEOS }, trabalhador));
  } finally {
    estado.fim = new Date().toISOString();
    varrendo = false;
    await salvar();
  }
  return estado;
}

const acoes = {
  importarTodos: () => importarTodos(),
  varrer: (m) => { varrer(m).catch(() => {}); return { ok: true }; }, // roda em segundo plano
  protocoloLido: (m, sender) => protocoloLido(m, sender),
  lerPdf: (m) => lerPdf(m.url),
  enviar: (m) => enviar(m.pedido),
  adicionarFila: (m) => adicionarFila(m.pedido),
  removerFila: (m) => removerFila(m.numero),
  limparFila: () => limparFila(),
};

chrome.runtime.onMessage.addListener((msg, _sender, responder) => {
  if (msg.alvo !== 'background') return false;
  const acao = acoes[msg.tipo];
  const tarefa = acao ? Promise.resolve().then(() => acao(msg, _sender)) : Promise.reject(new Error('mensagem desconhecida'));
  tarefa.then(
    (r) => responder(r ?? { ok: true }),
    (e) => responder({ erro: e.message || String(e) }),
  );
  return true; // resposta assíncrona
});
