const $ = (id) => document.getElementById(id);

chrome.storage.sync.get(['endpoint', 'chave']).then(({ endpoint = '', chave = '' }) => {
  $('endpoint').value = endpoint;
  $('chave').value = chave;
});

$('salvar').onclick = async () => {
  const endpoint = $('endpoint').value.trim();
  if (endpoint) {
    // pede permissão só para o endereço configurado
    const origem = new URL(endpoint).origin + '/*';
    const ok = await chrome.permissions.request({ origins: [origem] });
    if (!ok) return ($('status').textContent = ' Permissão negada.');
  }
  await chrome.storage.sync.set({ endpoint, chave: $('chave').value });
  $('status').textContent = ' Salvo ✔';
};
