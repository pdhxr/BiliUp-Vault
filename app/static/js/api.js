(function () {
  async function apiFetch(resource, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set('X-BiliUp-Client', 'desktop');
    return fetch(resource, { ...options, headers });
  }

  window.apiFetch = apiFetch;
}());
