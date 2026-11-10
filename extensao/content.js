// Roda no sistema de Processos Digitais da prefeitura, em duas telas:
//
// A) Tela de documentos do protocolo (co.wppreviewdocsprotocolo):
//    1. Acha na árvore os documentos "pedido-NNNN-AAAA..."
//    2. Clica neles (só visualizar) para o sistema mostrar o PDF
//    3. Pede para a extensão ler o PDF, coloca o pedido na fila e mostra num painel
//
// B) Lista "Meus Protocolos" (tela Principal):
//    pega os protocolos em "Receber" e pede para a extensão abrir cada um
//    em segundo plano (tela A), que lê o pedido e fecha a aba.
//
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
    const lidos = [];
    const erros = [];
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
        lidos.push(p.pedido);
      } catch (e) {
        erros.push(`${item.nome}: ${e.message}`);
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
    avisarLido(protocoloTela, lidos, erros);
    return true;
  }

  /** Avisa a extensão que este protocolo foi lido (usado pela leitura em segundo plano). */
  function avisarLido(protocolo, pedidos, erros = []) {
    msg({ tipo: 'protocoloLido', protocolo, pedidos, erros }).catch(() => {});
  }

  // A árvore é montada por JavaScript depois que a página carrega: espera ela aparecer.
  // Se a árvore aparecer e não tiver pedido, avisa "sem pedido" depois de alguns segundos.
  let feito = false;
  let semPedidoTimer = null;
  const tentarArvore = async () => {
    if (feito || !document.querySelector('span[id^="ygtvlabelel"]')) return;
    if (!acharPedidosNaArvore().length) {
      semPedidoTimer ??= setTimeout(() => {
        if (feito || acharPedidosNaArvore().length) return;
        feito = true;
        avisarLido(protocoloDaTela(), []);
      }, 5000);
      return;
    }
    feito = true;
    clearTimeout(semPedidoTimer);
    await processar();
  };

  // ---------- B) lista "Meus Protocolos" ----------
  const STATUS_SEL = 'span[id*="VW_PROTOCOLOUSUARIO_STATUSPROTOCOLO_"]';
  const RE_STATUS_ID = /^span_(\w*?)VW_PROTOCOLOUSUARIO_STATUSPROTOCOLO_(\d+)$/;

  /** Linhas da lista com situação "Receber" e assunto de pedido de compra. */
  function protocolosEmReceber() {
    const lista = [];
    for (const st of document.querySelectorAll(STATUS_SEL)) {
      const m = st.id.match(RE_STATUS_ID);
      if (!m || st.textContent.trim() !== 'Receber') continue;
      const [, pre, linha] = m;
      const txt = (col) => document.getElementById(`span_${pre}VW_PROTOCOLOUSUARIO_${col}_${linha}`)?.textContent.trim() || '';
      const assunto = txt('PROTOCOLOASSUNTODESCRICAO');
      if (assunto && !/pedido de compra/i.test(assunto)) continue;
      const link = document.querySelector(`#span_${pre}vGRIDCONDFORMATTING_${linha} a[href*="wppreviewdocsprotocolo"]`);
      const protocolo = txt('NUMEROEXIBICAO');
      if (link && protocolo) lista.push({ protocolo, url: link.href });
    }
    return lista;
  }

  let painelLista = null;
  let autoFeito = false;
  function montarPainelLista() {
    if (painelLista?.isConnected) return painelLista;
    painelLista = document.createElement('div');
    painelLista.id = 'leitor-pedidos-painel';
    painelLista.innerHTML = `
      <div class="lp-topo"><strong>Leitor de Pedidos</strong><button class="lp-fechar" title="Fechar">×</button></div>
      <div class="lp-corpo">
        <div class="lp-resumo"></div>
        <div class="lp-progresso"></div>
        <div class="lp-acoes">
          <button class="lp-enviar lp-ler-novos">Ler novos</button>
          <button class="lp-ler-todos" title="Lê de novo também os que já foram lidos">Ler todos de novo</button>
        </div>
        <div class="lp-rodape">Os pedidos lidos vão para a fila: clique no ícone da extensão para ver.</div>
      </div>`;
    painelLista.querySelector('.lp-fechar').onclick = () => painelLista.remove();
    painelLista.querySelector('.lp-ler-novos').onclick = () => iniciarLeitura(false);
    painelLista.querySelector('.lp-ler-todos').onclick = () => iniciarLeitura(true);
    document.body.appendChild(painelLista);
    return painelLista;
  }

  async function atualizarPainelLista() {
    const lista = protocolosEmReceber();
    if (!lista.length && !painelLista?.isConnected) return;
    const painel = montarPainelLista();
    const { protocolosLidos = {}, varredura = null } = await chrome.storage.local.get(['protocolosLidos', 'varredura']);
    const novos = lista.filter((p) => !protocolosLidos[p.protocolo] || protocolosLidos[p.protocolo].erros?.length);
    painel.querySelector('.lp-resumo').textContent =
      `${lista.length} protocolo(s) de pedido em "Receber" nesta página · ${novos.length} ainda não lido(s)`;
    const prog = painel.querySelector('.lp-progresso');
    // se o Chrome reiniciar a extensão no meio, a leitura não termina: depois de 10 min libera os botões
    const rodando = varredura && !varredura.fim && Date.now() - Date.parse(varredura.inicio) < 10 * 60000;
    if (varredura) {
      const r = varredura;
      prog.textContent = rodando
        ? `Lendo ${r.feitos}/${r.total}… (${r.pedidos} pedido(s) encontrado(s))`
        : `Última leitura: ${r.feitos}/${r.total} protocolo(s), ${r.pedidos} pedido(s) encontrado(s)` +
          (r.semPedido ? `, ${r.semPedido} sem pedido` : '') +
          (r.erros ? `, ${r.erros} com erro` : '') + '.';
    }
    for (const b of painel.querySelectorAll('.lp-acoes button')) b.disabled = rodando;
    return novos;
  }

  async function iniciarLeitura(forcar) {
    const lista = protocolosEmReceber();
    if (!lista.length) return;
    try {
      await msg({ tipo: 'varrer', protocolos: lista, forcar });
    } catch (e) {
      montarPainelLista().querySelector('.lp-progresso').textContent = 'Erro: ' + e.message;
    }
  }

  const tentarLista = async () => {
    if (!document.querySelector(STATUS_SEL)) return;
    const novos = await atualizarPainelLista();
    if (autoFeito || !novos?.length) return;
    autoFeito = true;
    const { leituraAutomatica = true } = await chrome.storage.sync.get('leituraAutomatica');
    if (leituraAutomatica) iniciarLeitura(false);
  };

  chrome.storage.onChanged.addListener((mudou, area) => {
    if (area === 'local' && (mudou.varredura || mudou.protocolosLidos) && document.querySelector(STATUS_SEL)) atualizarPainelLista();
  });

  // ---------- início ----------
  let agendado = false;
  const tentar = () => {
    if (agendado) return;
    agendado = true;
    setTimeout(() => {
      agendado = false;
      tentarArvore();
      tentarLista();
    }, 300);
  };
  // ignora mudanças feitas pelo próprio painel (senão um atualiza o outro sem parar)
  const obs = new MutationObserver((mudancas) => {
    if (mudancas.every((m) => m.target.closest?.('#leitor-pedidos-painel') || m.target.id === 'leitor-pedidos-painel' ||
      [...m.addedNodes, ...m.removedNodes].every((n) => n.id === 'leitor-pedidos-painel'))) return;
    tentar();
  });
  obs.observe(document.documentElement, { childList: true, subtree: true });
  tentar();
})();
