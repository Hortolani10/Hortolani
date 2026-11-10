// Fila de pedidos: tudo o que foi lido nos protocolos abertos, em qualquer aba.
const $ = (id) => document.getElementById(id);
const brl = (v) => (v == null ? '—' : v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }));
const dataBr = (iso) => (iso ? iso.split('-').reverse().join('/') : '—');
const quando = (iso) => new Date(iso).toLocaleString('pt-BR');

const msg = (dados) =>
  new Promise((ok, falha) =>
    chrome.runtime.sendMessage({ alvo: 'background', ...dados }, (r) => {
      if (chrome.runtime.lastError) return falha(new Error(chrome.runtime.lastError.message));
      if (r && r.erro) return falha(new Error(r.erro));
      ok(r);
    }),
  );

function el(tag, attrs = {}, ...filhos) {
  const e = document.createElement(tag);
  Object.assign(e, attrs);
  e.append(...filhos.filter((f) => f != null));
  return e;
}

async function lerFila() {
  const { fila = {} } = await chrome.storage.local.get('fila');
  // ainda não abertos primeiro; dentro de cada grupo, os mais recentes primeiro
  return Object.values(fila).sort(
    (a, b) => !!a.abertoEm - !!b.abertoEm || (b.adicionadoEm || '').localeCompare(a.adicionadoEm || ''),
  );
}

async function desenhar() {
  const itens = await lerFila();
  const prontos = itens.filter((i) => !i.abertoEm && !i.avisos?.length).length;
  $('resumo').textContent = itens.length ? `${itens.length} pedido(s) · ${prontos} pronto(s)` : '';
  if (!itens.length) {
    $('lista').replaceChildren(
      el('p', { className: 'vazio', textContent: 'Nenhum pedido na fila. Abra um protocolo com pedido no sistema da prefeitura.' }),
    );
    return;
  }
  $('lista').replaceChildren(...itens.map(cartao));
}

function cartao(item) {
  const p = item.pedido;
  const temAviso = item.avisos?.length > 0;
  const importar = el('button', {
    className: 'primario',
    textContent: item.abertoEm ? 'Abrir de novo' : 'Importar no Ventrículo',
    disabled: temAviso,
    title: temAviso ? 'Faltam dados do pedido' : '',
  });
  importar.onclick = async () => {
    importar.disabled = true;
    try {
      await msg({ tipo: 'enviar', pedido: p }); // abre a aba do Ventrículo (o popup fecha)
    } catch (e) {
      $('status').textContent = 'Erro: ' + e.message;
      importar.disabled = false;
    }
  };
  const remover = el('button', { textContent: 'Remover', title: 'Tirar da fila' });
  remover.onclick = async () => {
    await msg({ tipo: 'removerFila', numero: p.pedido });
    desenhar();
  };
  return el(
    'div',
    { className: 'item' + (item.abertoEm ? ' aberto' : '') },
    el('div', { className: 'linha1' }, el('span', { textContent: `Pedido ${p.pedido}` }), el('span', { className: 'valor', textContent: brl(p.valor) })),
    el('div', { className: 'empresa', textContent: p.empresa || '—' }),
    el('div', { className: 'meta', textContent: `Ata ${p.ata || '—'} · Protocolo ${p.protocolo || '—'} · ${dataBr(p.dataPedido)}` }),
    temAviso ? el('div', { className: 'aviso', textContent: '⚠️ ' + item.avisos.join(' · ') }) : null,
    item.abertoEm
      ? el('span', { className: 'tag aberto', textContent: `Aberto no Ventrículo em ${quando(item.abertoEm)}` })
      : temAviso ? null : el('span', { className: 'tag pronto', textContent: 'Pronto para importar' }),
    el('div', { className: 'acoes' }, importar, remover),
  );
}

$('copiarTodos').onclick = async () => {
  const itens = await lerFila();
  await navigator.clipboard.writeText(JSON.stringify(itens.map((i) => i.pedido), null, 2));
  $('status').textContent = `${itens.length} pedido(s) copiados.`;
};
$('limparAbertos').onclick = async () => {
  for (const i of await lerFila()) if (i.abertoEm) await msg({ tipo: 'removerFila', numero: i.pedido.pedido });
  desenhar();
};
$('config').onclick = () => chrome.runtime.openOptionsPage();

// atualiza sozinho quando outra aba adiciona um pedido
chrome.storage.onChanged.addListener((mudou, area) => area === 'local' && mudou.fila && desenhar());
desenhar();
