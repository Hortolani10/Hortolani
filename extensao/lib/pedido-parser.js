/**
 * Leitor do "PEDIDO DE COMPRA DIRETO - ANALÍTICO" (PDF gerado pelo
 * sistema de compras da prefeitura, Crystal Reports).
 *
 * Funciona em duas etapas:
 *  1. extrairLinhas(pdfDoc)  -> agrupa o texto do PDF (via pdf.js) em linhas,
 *                               cada linha = lista de "pedaços" em ordem da esquerda p/ direita.
 *  2. lerPedido(linhas)      -> procura os rótulos ("Pedido:", "Ata:" ...) e devolve os campos.
 *
 * Só campos públicos do pedido são devolvidos: nomes de servidores
 * (usuário requisição/pedido, assinaturas) são ignorados de propósito.
 */

const MESES = {
  janeiro: '01', fevereiro: '02', 'março': '03', marco: '03', abril: '04', maio: '05', junho: '06',
  julho: '07', agosto: '08', setembro: '09', outubro: '10', novembro: '11', dezembro: '12',
};

/** Agrupa os itens de texto do pdf.js em linhas (mesma altura = mesma linha). */
export async function extrairLinhas(pdfDoc, tolerancia = 3) {
  const linhas = [];
  for (let n = 1; n <= pdfDoc.numPages; n++) {
    const pagina = await pdfDoc.getPage(n);
    const { items } = await pagina.getTextContent();
    const daPagina = [];
    for (const it of items) {
      const texto = it.str.trim();
      if (!texto) continue;
      const x = it.transform[4];
      const y = it.transform[5];
      let linha = daPagina.find((l) => Math.abs(l.y - y) <= tolerancia);
      if (!linha) daPagina.push((linha = { y, itens: [] }));
      linha.itens.push({ x, texto });
    }
    daPagina.sort((a, b) => b.y - a.y); // de cima para baixo
    for (const l of daPagina) linhas.push(l.itens.sort((a, b) => a.x - b.x).map((i) => i.texto));
  }
  return linhas;
}

const limpaNum = (s) => s.replace(/\s+/g, '');

/** Valor que vem logo depois de um rótulo, na mesma linha. */
function depoisDe(linhas, rotulo, ocorrencia = 0) {
  let achadas = 0;
  for (const linha of linhas) {
    const i = linha.findIndex((p) => p === rotulo || p.startsWith(rotulo + ' '));
    if (i === -1) continue;
    if (achadas++ < ocorrencia) continue;
    const proprio = linha[i].slice(rotulo.length).trim();
    if (proprio) return proprio;
    return linha[i + 1] ?? null;
  }
  return null;
}

export function formataCnpj(digitos) {
  const d = (digitos || '').replace(/\D/g, '');
  if (d.length === 14) return d.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
  if (d.length === 11) return d.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, '$1.$2.$3-$4');
  return digitos || null;
}

/** "1.234,56" -> 1234.56 */
export function paraNumero(valorBr) {
  if (!valorBr) return null;
  const n = Number(valorBr.replace(/\./g, '').replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}

/** Lê os campos do pedido a partir das linhas extraídas. */
export function lerPedido(linhas) {
  const texto = linhas.map((l) => l.join(' ')).join('\n');
  if (!/PEDIDO DE COMPRA/i.test(texto)) throw new Error('Documento não parece um Pedido de Compra');

  const fornecedor = depoisDe(linhas, 'Fornecedor:'); // "11372 - PRINTSUL COMÉRCIO ATACADISTA LTDA"
  const mFornecedor = fornecedor && fornecedor.match(/^(\d+)\s*-\s*(.+)$/);
  const unidade = depoisDe(linhas, 'Unid. Orçamentária:'); // "02.0006 DIRETORIA DE ..."
  const modalidade = depoisDe(linhas, 'Modalidade:');
  const mPregao = modalidade && modalidade.match(/Nr\.?:?\s*(\d+\/\d{4})/);
  const mData = texto.match(/,\s*(\d{1,2}) de ([A-Za-zçÇ]+) de (\d{4})/);

  return {
    pedido: depoisDe(linhas, 'Pedido:'), // "4758/0-2026"
    protocolo: limpaNum(depoisDe(linhas, 'Protocolo:') || '') || null, // "10857/2026"
    processo: limpaNum(depoisDe(linhas, 'Processo/Ano:') || '') || null,
    requisicao: depoisDe(linhas, 'Requisição Nro.:'),
    ata: depoisDe(linhas, 'Ata:'), // nº da Ata de Registro
    pregao: mPregao ? mPregao[1] : null, // nº do pregão (Modalidade)
    modalidade,
    diretoria: unidade ? unidade.replace(/^[\d.]+\s*/, '') : null,
    fornecedorCodigo: mFornecedor ? mFornecedor[1] : null,
    empresa: mFornecedor ? mFornecedor[2].trim() : fornecedor,
    cnpj: formataCnpj(depoisDe(linhas, 'Cnpj/Cpf:', 0)), // 1ª ocorrência = fornecedor
    objeto: depoisDe(linhas, 'Objeto:'),
    aplicacao: depoisDe(linhas, 'Aplicação:'),
    valor: paraNumero(depoisDe(linhas, 'Valor Líquido:') || depoisDe(linhas, 'Valor Total:')),
    dataPedido: mData
      ? `${mData[3]}-${MESES[mData[2].toLowerCase()] ?? '??'}-${mData[1].padStart(2, '0')}`
      : null,
    vencimento: (depoisDe(linhas, 'Dt. Vencimento:') || '').split('/').reverse().join('-') || null,
  };
}
