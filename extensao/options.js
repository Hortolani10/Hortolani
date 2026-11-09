const $ = (id) => document.getElementById(id);
const APP_URL_PADRAO = 'https://ventriculo-app.vercel.app/pedidos/cadastrar';

chrome.storage.sync.get(['appUrl', 'endpoint']).then(({ appUrl = '', endpoint = '' }) => {
  $('appUrl').value = appUrl || endpoint || APP_URL_PADRAO;
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
  await chrome.storage.sync.set({ appUrl, endpoint: appUrl });
  $('status').textContent = ' Salvo ✔';
};
