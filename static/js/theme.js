(() => {
  let theme = 'light';
  try { theme = localStorage.getItem('pio-theme') || 'light'; } catch (_) { /* Theme remains usable without storage. */ }
  document.documentElement.dataset.theme = theme;
  document.addEventListener('click', event => {
    if (!event.target.closest('.theme-toggle')) return;
    const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('pio-theme', next); } catch (_) { /* Optional preference. */ }
  });
})();
