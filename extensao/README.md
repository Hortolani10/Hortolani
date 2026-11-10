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

## Leitura automática dos protocolos em "Receber"

Ao abrir **Meus Protocolos** (tela Principal), a extensão pega as linhas com
situação **"Receber"** e assunto de **Pedido de Compra**, abre cada protocolo
(pelo mesmo link do olho) numa **aba em segundo plano**, 2 de cada vez, lê o
pedido, coloca na fila e fecha a aba. Um painel mostra o andamento.

- Protocolos já lidos não são lidos de novo. Os que deram erro, sim.
- Protocolos sem pedido são ignorados. Protocolos com mais de um pedido geram um item por pedido.
- **Importar todos (N)**, no próprio painel: abre uma aba do Ventrículo para cada
  pedido pronto, já preenchida (a primeira fica em foco). Pedidos com aviso ficam de fora.
- Botões: **Ler novos** e **Ler todos de novo**.
- A leitura automática pode ser desligada nas configurações (⚙ na fila).
- Ela lê só a página da lista que está aberta (até 50 linhas).
- Ela nunca clica em "Receber": só abre para ver.

## Fila de pedidos

Cada pedido lido entra numa **fila**, que é a mesma para todas as abas. Dá para
abrir vários protocolos (ao mesmo tempo ou um depois do outro) e ver tudo
clicando no ícone da extensão. A chave da fila é o número do pedido, que já
inclui o ano (ex.: `4758/0-2026`), então o mesmo pedido nunca aparece duas vezes.

Na fila: **Importar no Ventrículo**, **Remover**, **Copiar todos** e
**Limpar abertos** (tira da fila os que já foram abertos no Ventrículo).

Se faltar algum campo no PDF (ata, CNPJ, valor…), o pedido aparece com um aviso
amarelo e o botão de importar fica bloqueado.

## Importação

A extensão abre o cadastro de pedido do Ventrículo numa nova aba, com os dados
preenchidos para revisão (`/pedidos/cadastrar#importar-pedido=...`).
O prazo certo é o da **ata oficial cadastrada no Ventrículo**. A tela de cadastro
do Ventrículo, porém, só preenche o formulário se o bloco `ata` vier completo
(`numero`, `diasParaEntrega`, `diasUteis`, `fiscal`). Por isso esses campos vão
com valores padrão (7, true, ""), e o Ventrículo deve ignorá-los quando a ata já existir.

Como quem salva é a pessoa, lá no Ventrículo, a extensão só registra
"Aberto no Ventrículo em …", e não "salvo".

## Testes

```
npm test
```
