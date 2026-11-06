# Colocar o bot no ar 24 horas (VPS)

Tempo estimado: 40–60 minutos na primeira vez. Custo: ~5–6 dólares/mês.

O caminho é sempre o mesmo: **paper (4–6 semanas) → testnet (1–2 semanas) → real com 100 USDT**.

---

## 1. Contratar o servidor

- **Sistema:** Ubuntu 24.04 LTS
- **Tamanho:** 1 vCPU, 1 GB de RAM, 25 GB de disco é suficiente
- **Região: São Paulo ou Europa.** **Não use servidor nos EUA**: a Binance bloqueia
  (vimos o erro 451 nos testes).
- Provedores com São Paulo: Vultr, AWS Lightsail, Oracle Cloud (tem plano gratuito), Magalu Cloud.
- Na criação, escolha **acesso por chave SSH** (não por senha).

### Criar a chave SSH (no seu computador)
Windows (PowerShell), Mac ou Linux:
```bash
ssh-keygen -t ed25519 -C "bot-hortolani"
```
Aperte Enter para aceitar o local e **defina uma senha para a chave**. Cole o conteúdo do
arquivo `id_ed25519.pub` (a parte **pública**) no painel do provedor ao criar o servidor.
Nunca compartilhe o arquivo `id_ed25519` (sem `.pub`).

## 2. Proteger o servidor (uma vez)
```bash
ssh root@IP_DO_SERVIDOR
curl -fsSL -o preparar_servidor.sh https://raw.githubusercontent.com/Hortolani10/Hortolani/main/deploy/preparar_servidor.sh
#   (ou copie o arquivo deploy/preparar_servidor.sh do projeto)
bash preparar_servidor.sh
```
O script instala Docker, firewall (só SSH aberto), fail2ban, atualizações automáticas de
segurança, cria o usuário `bot` e **desliga login por senha e como root**.

**Antes de fechar a janela, abra OUTRA e teste:** `ssh bot@IP_DO_SERVIDOR`.
Se entrar, está tudo certo. Daqui em diante use sempre o usuário `bot`.

## 3. Colocar o projeto no servidor
```bash
ssh bot@IP_DO_SERVIDOR
git clone https://github.com/Hortolani10/Hortolani.git
cd Hortolani
```
(Repositório privado: o GitHub vai pedir login; use um *token* de acesso pessoal com permissão
só de leitura. Alternativa: copie a pasta do seu computador com
`scp -r Hortolani bot@IP_DO_SERVIDOR:~/`.)

## 4. Configurar as chaves (arquivo .env)
```bash
cp .env.example .env
nano .env          # preencha; Ctrl+O salva, Ctrl+X sai
chmod 600 .env     # só você lê
```
Para o **paper** não precisa de chave da Binance — só o Telegram (opcional, recomendado).

### Telegram (avisos e comandos no celular)
1. No Telegram, fale com **@BotFather** → `/newbot` → escolha um nome → copie o **token**
   para `TELEGRAM_BOT_TOKEN`. **O token é uma senha: não mande para ninguém.**
2. Mande um "oi" para o seu bot novo.
3. No navegador: `https://api.telegram.org/bot<TOKEN>/getUpdates` → procure
   `"chat":{"id":123456789` → copie o número para `TELEGRAM_CHAT_ID`.
4. O bot só obedece a esse chat. Comandos: `/status`, `/pausar`, `/retomar`.

Você recebe: compras, vendas, stops, movimentos do cofre, alarmes, erros e um resumo
diário (~22h de Brasília).

### Alerta de bot PARADO (healthchecks.io, grátis)
Se o servidor cair, o bot não consegue avisar — por isso um serviço de fora vigia:
1. Crie conta em https://healthchecks.io → **Add Check** → *Period* 5 minutos, *Grace* 10 minutos.
2. Em **Integrations**, ligue o **Telegram** (e/ou e-mail).
3. Copie a URL de ping (`https://hc-ping.com/...`) para `HEALTHCHECK_URL` no `.env`.

O bot manda um sinal a cada minuto; se ficar 15 minutos sem sinal, você recebe o alerta.

## 5. Ligar o bot (modo paper)
```bash
mkdir -p runtime && sudo chown 10001:10001 runtime   # pasta de dados do bot
docker compose up -d --build
docker compose logs -f        # acompanhar (Ctrl+C sai do log; o bot continua rodando)
```
O container reinicia sozinho se cair ou se o servidor reiniciar.

## 6. Dia a dia

| Quero... | Comando (na pasta Hortolani) |
|---|---|
| Ver o que está acontecendo | `docker compose logs -f --tail 100` |
| Ver o status no celular | `/status` ou `/radar` no Telegram |
| Ver o painel ao vivo | no seu PC: `ssh -L 8765:localhost:8765 bot@IP` e abra http://localhost:8765 |
| **Parar novas compras (emergência)** | `/pausar` no Telegram ou `touch runtime/PAUSAR` |
| Voltar a comprar | `/retomar` ou `rm runtime/PAUSAR` |
| Desligar o bot | `docker compose down` (stops na Binance continuam valendo) |
| Relatório do que funcionou | `docker compose run --rm bot aprender` |
| Atualizar o código | `git pull && docker compose up -d --build` |
| Backup (diário e estado) | `tar czf backup-$(date +%F).tgz runtime/` e baixe com `scp` |

## 7. Testnet (depois de 4–6 semanas de paper)
1. Crie chaves em https://testnet.binance.vision (login com GitHub).
2. No `.env`: `BINANCE_API_KEY` e `BINANCE_API_SECRET` da testnet.
3. Em `config.yaml`: `testnet: true` (já é o padrão).
4. Em `docker-compose.yml`: troque `command: ["paper"]` por `command: ["live"]`.
5. `docker compose up -d --build`. Os avisos chegam marcados `[TESTNET]`.

Confira nas 1–2 semanas: as compras aparecem na testnet? O stop aparece como ordem aberta?
Quando o stop sobe, a ordem antiga é cancelada e a nova aparece?

## 8. Dinheiro real (100 USDT)
1. Na Binance: **Gerenciamento de API** → criar chave →
   - marque **somente "Permitir negociação Spot e Margem"** (sem margem na prática — o bot só usa spot);
   - **NÃO** marque saque, transferência universal ou futuros;
   - **Restringir acesso a IPs confiáveis** → coloque o IP do servidor.
   O bot confere essas permissões e **se recusa a operar** se a chave puder sacar.
2. No `.env`: as chaves reais e `CONFIRMO_OPERAR_DINHEIRO_REAL=SIM`.
3. Em `config.yaml`: `testnet: false`.
4. Deixe na Binance só o dinheiro do bot (100 USDT) e um pouco de BNB se quiser desconto de taxa.
5. `docker compose up -d --build` — avisos chegam marcados `[REAL]`.

**Conta Binance:** 2FA ligado (app autenticador, não SMS), código anti-phishing ativado,
e-mail exclusivo para a Binance. Nunca informe códigos a ninguém.

## Problemas comuns
- **Erro 451 / "restricted location":** servidor nos EUA. Crie outro em São Paulo/Europa.
- **"Já existe um bot rodando":** já há um container ativo — `docker compose ps`.
- **Container "unhealthy":** o bot parou de salvar o estado — veja `docker compose logs`.
- **Não chegam avisos:** confira token e chat ID; mande `/status` para testar.
