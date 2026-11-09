# Painel no celular (com acesso só para os SEUS aparelhos)

O painel continua fechado para a internet. Usamos o **Tailscale**: uma rede privada entre o
servidor e os aparelhos que você autorizar (celular, PC). Só quem entra na SUA conta Tailscale
consegue abrir o link. Grátis para uso pessoal.

## 1. No servidor (uma vez só)
```
ssh bot@187.41.127.210
su -
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up
```
O `tailscale up` mostra um link `https://login.tailscale.com/...`: abra no PC ou no celular e
entre com sua conta (Google, Microsoft ou Apple). Isso autoriza o servidor na sua rede.

Ainda como root, libere o painel só dentro da rede Tailscale e publique o endereço:
```
ufw allow in on tailscale0
tailscale serve --bg 8765
```
Se aparecer um link pedindo para ativar HTTPS, abra, clique em **Enable** e rode o comando de novo.
No fim ele mostra o endereço, algo como `https://srv2139351.xxxx.ts.net`.

## 2. No celular (uma vez só)
1. Instale o app **Tailscale** (Play Store ou App Store).
2. Entre com a **mesma conta** do passo 1 e ative a conexão.
3. Abra no navegador o endereço `https://srv2139351.xxxx.ts.net` e salve nos favoritos
   (ou "Adicionar à tela inicial").

## Dia a dia
- Celular: abre o favorito (com o Tailscale ligado). Pronto, Central ao vivo.
- PC: continua funcionando o `abrir_painel.bat`; se instalar o Tailscale no PC, o mesmo link também abre.
- Tirar o acesso de um aparelho: https://login.tailscale.com/admin/machines → remover.
- Desligar tudo: no servidor, `su -` e `tailscale serve --https=443 off`.
