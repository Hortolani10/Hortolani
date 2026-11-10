const $ = (id) => document.getElementById(id);
const APP_URL_PADRAO = 'https://ventriculo-app.vercel.app/pedidos/cadastrar';

chrome.storage.sync.get(['appUrl', 'endpoint', 'leituraAutomatica']).then(({ appUrl = '', endpoint = '', leituraAutomatica = true }) => {
  $('appUrl').value = appUrl || endpoint || APP_URL_PADRAO;
  $('leituraAutomatica').checked = leituraAutomatica;
});

$('salvar').onclick = async () => {
  const appUrl = $('appUrl').value.trim();
  if (appUrl) {
    try {
      new URL(appUrl);
    } catch {
      return ($('status').textContent = ' Endereço inválido.');
    }
  }
  await chrome.storage.sync.set({ appUrl, endpoint: appUrl, leituraAutomatica: $('leituraAutomatica').checked });
  $('status').textContent = ' Salvo ✔';
};
