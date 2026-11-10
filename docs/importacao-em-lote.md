# Importação em lote no Ventrículo

Guia para criar no Ventrículo a tela que recebe **vários pedidos de uma vez**
da extensão "Leitor de Pedidos". Hoje, o botão "Importar todos" abre uma aba
de `/pedidos/cadastrar` para cada pedido. Com a tela de lote, ele abre **uma aba
só**, com a lista, e um botão **"Salvar todos"**.

## 1. Endereço

A extensão abre:

```
https://ventriculo-app.vercel.app/pedidos/importar-lote#importar-pedidos=<JSON codificado>
```

- O JSON vem depois do `#`, codificado com `encodeURIComponent`. Ele não vai
  para o servidor nem para os registros da Vercel.
- Para ler:

```ts
const hash = window.location.hash; // "#importar-pedidos=..."
const prefixo = '#importar-pedidos=';
if (hash.startsWith(prefixo)) {
  const lote = JSON.parse(decodeURIComponent(hash.slice(prefixo.length)));
  // limpa o endereço para um F5 não importar de novo
  history.replaceState(null, '', window.location.pathname);
}
```

## 2. Formato (version 2)

Cada item de `pedidos` tem **exatamente o mesmo formato** que a tela
`/pedidos/cadastrar` já recebe hoje em `#importar-pedido=` (version 1), só sem
`version` e `source`. Então dá para reaproveitar o código que já existe.

```json
{
  "version": 2,
  "source": "leitor-pedidos-extensao",
  "pedidos": [
    {
      "ata": { "numero": "39/2026", "diasParaEntrega": 7, "diasUteis": true, "fiscal": "" },
      "empresa": { "nomeEmpresa": "PRINTSUL COMÉRCIO ATACADISTA LTDA", "cnpj": "19.032.430/0001-13" },
      "pedido": {
        "numeroPedido": "4758/0-2026",
        "ataNumero": "39/2026",
        "empresaCnpj": "19.032.430/0001-13",
        "dataPedido": "2026-10-29",
        "numeroProtocolo": "10857/2026",
        "diretoria": "DIRETORIA DE EDUCAÇÃO, ESPORTE E CULTURA",
        "valorPedido": 124.66
      }
    }
  ]
}
```

Observações:
- `dataPedido` vem no formato `AAAA-MM-DD`. `valorPedido` é um número (ponto decimal).
- `numeroPedido` já traz o ano (`4758/0-2026`). Pedidos com o mesmo número e anos
  diferentes (541/2025 e 541/2026) são pedidos diferentes.
- `ata.diasParaEntrega`, `ata.diasUteis` e `ata.fiscal` são **valores padrão**,
  mandados só porque `/pedidos/cadastrar` hoje não preenche sem eles. O prazo
  certo é o da **ata oficial cadastrada no Ventrículo**: ignore esses três campos
  quando a ata já existir.

## 3. O que a tela deve fazer (combinado com o Victor)

Mostrar uma tabela com uma linha por pedido e a situação de cada um:

| Situação | Regra | Ao clicar "Salvar todos" |
|---|---|---|
| ✅ Pronto | ata cadastrada e pedido ainda não existe | grava |
| ⛔ Ata não cadastrada | `ataNumero` não existe no Ventrículo | **não grava** e mostra o aviso (o protocolo continua em "Receber" na prefeitura, então o pedido não se perde) |
| ↩️ Já cadastrado | já existe pedido com o mesmo `numeroPedido` (número + ano) | **não grava** (evita duplicar) |

Outras regras:
- **Prazo:** calcular pela ata cadastrada + `dataPedido`, igual ao cadastro manual.
- **Empresa:** procurar pelo CNPJ. Se não existir, criar com `nomeEmpresa` e `cnpj`
  (ou marcar a linha para revisão, como preferir).
- Permitir **desmarcar** uma linha antes de salvar.
- Depois de salvar, mostrar o resumo, por exemplo: "17 gravados · 1 ata não
  cadastrada · 1 já existia".

## 4. Como ligar na extensão

Depois que a tela estiver publicada: no ícone da extensão → ⚙ (configurações) →
marcar **"Importar todos abre uma aba só"** → Salvar. Enquanto não estiver
marcado, a extensão continua abrindo uma aba por pedido.
