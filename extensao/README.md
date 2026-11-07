# Leitor de Pedidos – Protocolo Sarapuí

Extensão para Chrome/Edge que, ao abrir um protocolo no sistema de Processos
Digitais (`sarapuiweb.jlsoft.com.br/protocolo`), encontra o documento
`pedido-NNNN-AAAA...` na árvore, lê o PDF do **Pedido de Compra** e mostra os
dados num painel, com botão para enviar ao sistema de acompanhamento de entregas.

**Ela só lê.** Ela nunca clica em "Receber", "Tramitar", "Enviar" ou em
qualquer outro botão do sistema da prefeitura, e não guarda nem envia login ou senha.

## Campos lidos do PDF

`pedido`, `protocolo`, `processo`, `requisicao`, `ata`, `pregao`, `modalidade`,
`diretoria`, `fornecedorCodigo`, `empresa`, `cnpj`, `objeto`, `aplicacao`,
`valor`, `dataPedido`, `vencimento`. A tela do protocolo acrescenta
`dataTramitacao`, `documento`, `pdfUrl` e `lidoEm`.

Nomes de servidores que aparecem no PDF (usuários, assinaturas) são ignorados.

## Instalar (modo desenvolvedor)

1. Baixe esta pasta `extensao/`.
2. No Chrome, abra `chrome://extensions`. No Edge, abra `edge://extensions`.
3. Ligue o **Modo do desenvolvedor**.
4. Clique em **Carregar sem compactação** e escolha a pasta `extensao`.
5. Clique no ícone da extensão e preencha o **endereço do sistema externo** e a
   **chave de acesso**. Até isso ser configurado, o botão "Copiar dados" já funciona.

## Envio

A extensão faz um `POST` com o JSON do pedido para o endereço configurado,
com o cabeçalho `x-api-key: <chave>`. Os pedidos enviados ficam marcados no
navegador, e o painel avisa "Já enviado em …" se o pedido já foi mandado.

## Testes

```
npm test
```
