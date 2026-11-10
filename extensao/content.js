// Roda dentro da tela do protocolo (co.wppreviewdocsprotocolo).
// 1. Acha na árvore os documentos "pedido-NNNN-AAAA..."
// 2. Clica neles (só visualizar) para o sistema mostrar o PDF
// 3. Pede para a extensão ler o PDF e mostra os dados num painel
// 4. Envia ao sistema externo quando a pessoa clica em "Enviar"
// Nunca clica em "Receber", "Tramitar" ou qualquer outro botão do sistema.
(() => {
  if (window.__leitorPedidos) return;
  window.__leitorPedidos = true;

  const RE_PEDIDO = /^pedido[-\s]*(\d+)[-\s/]+(\d{4})/i;
  const RE_DATA_PASTA = /(\d{2})\/(\d{2})\/(\d{4})\s*$/;

  const msg = (dados) =>
    new Promise((ok, falha) =>
      chrome.runtime.sendMessage({ alvo: 'background', ...dados }, (r) => {
        if (chrome.runtime.lastError) return falha(new Error(chrome.runtime.lastError.message));
        if (r && r.erro) return falha(new Error(r.erro));
        ok(r);
      }),
    );

  const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

  /** Documentos da árvore cujo nome começa com "pedido-". */
  function acharPedidosNaArvore() {
    const achados = [];
    for (const span of document.querySelectorAll('span[id^="ygtvlabelel"][id$="Span"]')) {
      const nome = span.textContent.trim();
      const m = nome.match(RE_PEDIDO);
      if (!m) continue;
      // pasta-mãe ("4 - Tramitação - 29/10/2026")
      const filhos = span.closest('.ygtvchildren');
      const pasta = filhos && filhos.previousElementSibling?.querySelector('span[id^="ygtvlabelel"]');
      const nomePasta = pasta ? pasta.textContent.trim() : '';
      const d = nomePasta.match(RE_DATA_PASTA);
      achados.push({
        span,
        link: span.closest('a'),
        nome,
        numero: `${m[1]}/${m[2]}`,
        pasta: nomePasta,
        dataTramitacao: d ? `${d[3]}-${d[2]}-${d[1]}` : null,
      });
    }
    return achados;
  }

  function protocoloDaTela() {
    for (const span of document.querySelectorAll('span[id^="ygtvlabelel"]')) {
      const m = span.textContent.match(/Protocolo\s*-\s*(\d+\/\d{4})/i);
      if (m) return m[1];
    }
    return null;
  }

  const urlDoPreview = () =>
    document.querySelector('#W0062UCFILEPREVIEWContainer embed, embed[src$=".pdf"], iframe[src*=".pdf"]')?.src ||
    null;

  /** Clica no documento da árvore e espera o visualizador trocar de PDF. */
  async function abrirNoVisualizador(item, timeoutMs = 15000) {
    const antes = urlDoPreview();
    if (item.span.classList.contains('NodeTextDecorationSelected') && antes) return antes;
    item.link.click();
    const fim = Date.now() + timeoutMs;
    while (Date.now() < fim) {
      await esperar(300);
      const agora = urlDoPreview();
      if (agora && agora !== antes) return agora;
    }
    throw new Error('O sistema não abriu o PDF do pedido a tempo.');
  }

  // ---------- painel ----------
  const painel = document.createElement('div');
  painel.id = 'leitor-pedidos-painel';
  painel.innerHTML = `
    <div class="lp-topo"><strong>Leitor de Pedidos</strong><button class="lp-fechar" title="Fechar">×</button></div>
    <div class="lp-corpo">Procurando pedido na árvore…</div>`;
  painel.querySelector('.lp-fechar').onclick = () => painel.remove();
  const corpo = painel.querySelector('.lp-corpo');

  const brl = (v) => (v == null ? '—' : v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }));
  const dataBr = (iso) => (iso ? iso.split('-').reverse().join('/') : '—');
  const esc = (s) => String(s ?? '—').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

  const quando = (iso) => new Date(iso).toLocaleString('pt-BR');

  function cartao(item) {
    const p = item.pedido;
    const div = document.createElement('div');
    div.className = 'lp-cartao';
    const avisos = item.avisos?.length
      ? `<div class="lp-aviso">⚠️ ${item.avisos.map(esc).join('<br>⚠️ ')}</div>`
      : '';
    div.innerHTML = `
      <div class="lp-titulo">Pedido ${esc(p.pedido)}</div>
      ${avisos}
      <table>
        <tr><th>Protocolo</th><td>${esc(p.protocolo)}</td></tr>
        <tr><th>Empresa</th><td>${esc(p.empresa)}<br><small>CNPJ ${esc(p.cnpj)}</small></td></tr>
        <tr><th>Ata</th><td>${esc(p.ata)}</td></tr>
        <tr><th>Diretoria</th><td>${esc(p.diretoria)}</td></tr>
        <tr><th>Valor</th><td>${brl(p.valor)}</td></tr>
        <tr><th>Data do pedido</th><td>${dataBr(p.dataPedido)}</td></tr>
        <tr><th>Tramitação</th><td>${dataBr(p.dataTramitacao)}</td></tr>
      </table>
      <div class="lp-acoes">
        <button class="lp-enviar" ${item.avisos?.length ? 'disabled title="Faltam dados do pedido"' : ''}>${item.abertoEm ? 'Abrir de novo no Ventrículo' : 'Importar no Ventrículo'}</button>
        <button class="lp-copiar">Copiar dados</button>
      </div>
      <div class="lp-status">${item.abertoEm ? `Aberto no Ventrículo em ${quando(item.abertoEm)}` : 'Adicionado à fila de pedidos ✔'}</div>`;
    const status = div.querySelector('.lp-status');
    div.querySelector('.lp-copiar').onclick = async () => {
      await navigator.clipboard.writeText(JSON.stringify(p, null, 2));
      status.textContent = 'Dados copiados.';
    };
    div.querySelector('.lp-enviar').onclick = async (ev) => {
      ev.target.disabled = true;
      status.textContent = 'Abrindo o Ventrículo…';
      try {
        const r = await msg({ tipo: 'enviar', pedido: p });
        status.textContent = `Aberto no Ventrículo em ${quando(r.abertoEm)}. Confira e salve lá.`;
        ev.target.textContent = 'Abrir de novo no Ventrículo';
      } catch (e) {
        status.textContent = 'Erro: ' + e.message;
      } finally {
        ev.target.disabled = false;
      }
    };
    return div;
  }

  async function processar() {
    const itens = acharPedidosNaArvore();
    if (!itens.length) return false;
    if (!painel.isConnected) document.body.appendChild(painel);
    corpo.textContent = `Lendo ${itens.length} pedido(s)…`;
    const protocoloTela = protocoloDaTela();
    const cartoes = [];
    for (const item of itens) {
      try {
        const url = await abrirNoVisualizador(item);
        const { pedido } = await msg({ tipo: 'lerPdf', url });
        const p = {
          ...pedido,
          protocolo: pedido.protocolo || protocoloTela,
          dataTramitacao: item.dataTramitacao,
          documento: item.nome,
          pdfUrl: url,
          lidoEm: new Date().toISOString(),
        };
        // sem número de pedido não dá para identificar na fila: usa o nome do documento
        if (!p.pedido) p.pedido = item.numero;
        cartoes.push(cartao(await msg({ tipo: 'adicionarFila', pedido: p })));
      } catch (e) {
        const div = document.createElement('div');
        div.className = 'lp-cartao lp-erro';
        div.textContent = `${item.nome}: ${e.message}`;
        cartoes.push(div);
      }
    }
    const rodape = document.createElement('div');
    rodape.className = 'lp-rodape';
    rodape.textContent = 'Os pedidos ficam na fila: clique no ícone da extensão para ver todos.';
    corpo.replaceChildren(...cartoes, rodape);
    return true;
  }

  // A árvore é montada por JavaScript depois que a página carrega: espera ela aparecer.
  let feito = false;
  const tentar = async () => {
    if (feito || !document.querySelector('span[id^="ygtvlabelel"]')) return;
    if (!acharPedidosNaArvore().length) return;
    feito = true;
    obs.disconnect();
    await processar();
  };
  const obs = new MutationObserver(() => tentar());
  obs.observe(document.documentElement, { childList: true, subtree: true });
  tentar();
})();
