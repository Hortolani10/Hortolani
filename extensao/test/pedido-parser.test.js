// Rodar com: node --test extensao/test/*.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { lerPedido } from '../lib/pedido-parser.js';

// Linhas extraídas (via pdf.js) do pedido 4758/0-2026, sem nomes de servidores.
const linhas = JSON.parse(readFileSync(new URL('./pedido-4758-2026.linhas.json', import.meta.url)));

test('lê os campos do pedido de compra', () => {
  assert.deepEqual(lerPedido(linhas), {
    pedido: '4758/0-2026',
    protocolo: '10857/2026',
    processo: '5858/2026',
    requisicao: '6531/2026',
    ata: '39/2026',
    ataCampo: '42/2026',
    modalidade: 'Pregão Eletrônico Nr.: 39/2026 - Ata de Registro',
    diretoria: 'DIRETORIA DE EDUCAÇÃO, ESPORTE E CULTURA',
    fornecedorCodigo: '11372',
    empresa: 'PRINTSUL COMÉRCIO ATACADISTA LTDA',
    cnpj: '19.032.430/0001-13',
    objeto: 'ATA DE REGISTRO DE PREÇOS PARA AQUISIÇÃO DE MATERIAIS ESCOLARES E DE ESCRITÓRIO.',
    aplicacao: 'Aquisição Material Escritório - CIC',
    valor: 124.66,
    dataPedido: '2026-10-29',
    vencimento: '2026-11-30',
  });
});

test('recusa documento que não é pedido', () => {
  assert.throws(() => lerPedido([['Despacho de 3 de Novembro de 2026']]));
});

test('avisa quando falta campo obrigatório', async () => {
  const { camposFaltando } = await import('../lib/pedido-parser.js');
  assert.deepEqual(camposFaltando(lerPedido(linhas)), []);
  const semAta = { ...lerPedido(linhas), ata: null, valor: 0 };
  assert.deepEqual(camposFaltando(semAta), ['Não encontrei número da ata no PDF', 'Não encontrei valor no PDF']);
});
