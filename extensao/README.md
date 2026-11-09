# Leitor de Pedidos – Protocolo Sarapuí

Extensão para Chrome/Edge que, ao abrir um protocolo no sistema de Processos
Digitais (`sarapuiweb.jlsoft.com.br/protocolo`), encontra o documento
`pedido-NNNN-AAAA...` na árvore, lê o PDF do **Pedido de Compra** e mostra os
dados num painel, com botão para enviar ao sistema de acompanhamento de entregas.

**Ela só lê.** Ela nunca clica em "Receber", "Tramitar", "Enviar" ou em
qualquer outro botão do sistema da prefeitura, e não guarda nem envia login ou senha.

## Campos lidos do PDF

`pedido`, `protocolo`, `processo`, `requisicao`, `ata` (número da Modalidade, ex.: 39/2026), `ataCampo`, `modalidade`,
`diretoria`, `fornecedorCodigo`, `empresa`, `cnpj`, `objeto`, `aplicacao`,
`valor`, `dataPedido`, `vencimento`. A tela do protocolo acrescenta
`dataTramitacao`, `documento`, `pdfUrl` e `lidoEm`.

Nomes de servidores que aparecem no PDF (usuários, assinaturas) são ignorados.

## Instalar (modo desenvolvedor)

1. Baixe esta pasta `extensao/`.
2. No Chrome, abra `chrome://extensions`. No Edge, abra `edge://extensions`.
3. Ligue o **Modo do desenvolvedor**.
4. Clique em **Carregar sem compactação** e escolha a pasta `extensao`.
5. Clique no ícone da extensão para conferir o **endereço do Ventriculo**. A
   extensão já vem configurada para `https://ventriculo-app.vercel.app/pedidos/cadastrar`.

## Importação

A extensão abre o cadastro de pedido do Ventriculo em uma nova aba com os dados
preenchidos para revisão. Os pedidos importados ficam marcados no navegador, e
o painel avisa "Já importado em …" se o pedido já foi aberto.

## Testes

```
npm test
```
