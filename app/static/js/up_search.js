(function () {
  const addButton = document.querySelector('#btn-add');
  const dialog = document.querySelector('#add-dialog');
  const closeButton = document.querySelector('#dialog-close');
  const form = document.querySelector('#up-search-form');
  const nameInput = document.querySelector('#up-name-input');
  const searchButton = document.querySelector('#up-search-button');
  const confirmButton = document.querySelector('#dialog-confirm');
  const runtimeMessage = document.querySelector('#runtime-message');
  const addMessage = document.querySelector('#add-message');
  const loading = document.querySelector('#search-loading');
  const resultsContainer = document.querySelector('#search-results');
  const feedback = document.querySelector('#up-feedback');

  let selected = null;
  let runtimeReady = false;

  async function responseData(response) {
    const text = await response.text();
    try {
      return text ? JSON.parse(text) : {};
    } catch (_) {
      throw new Error(response.ok ? '服务返回的数据格式不正确' : '服务请求失败，请重试');
    }
  }

  function escapeHtml(value) {
    const element = document.createElement('div');
    element.textContent = String(value ?? '');
    return element.innerHTML;
  }

  function setMessage(element, text, isError = false) {
    element.textContent = text;
    element.classList.toggle('error', isError);
  }

  function resetSearch() {
    selected = null;
    nameInput.value = '';
    searchButton.disabled = true;
    searchButton.textContent = '检查中…';
    confirmButton.disabled = true;
    loading.hidden = true;
    resultsContainer.replaceChildren();
    const placeholder = document.createElement('p');
    placeholder.className = 'search-placeholder';
    placeholder.textContent = '请输入昵称后点击“搜索”';
    resultsContainer.appendChild(placeholder);
    setMessage(addMessage, '');
    setMessage(runtimeMessage, '正在检查 OpenCLI…');
  }

  function renderResults(items) {
    resultsContainer.replaceChildren();
    if (items.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'search-placeholder';
      empty.textContent = '未找到匹配的 UP 主';
      resultsContainer.appendChild(empty);
      return;
    }
    items.forEach((item, index) => {
      const label = document.createElement('label');
      label.className = 'search-item';
      label.innerHTML = `
        <input type="radio" name="up-search-result" value="${escapeHtml(item.uid)}">
        <span class="search-index">${index + 1}</span>
        <span class="search-info">
          <span class="search-name">${escapeHtml(item.nickname)}</span>
          <span class="search-uid">UP ID：${escapeHtml(item.uid)}</span>
          <span class="search-bio">${escapeHtml(item.bio || '-')}</span>
        </span>`;
      label.querySelector('input').addEventListener('change', () => {
        selected = item;
        confirmButton.disabled = false;
        resultsContainer.querySelectorAll('.search-item').forEach((row) => row.classList.remove('selected'));
        label.classList.add('selected');
      });
      resultsContainer.appendChild(label);
    });
  }

  async function checkRuntime() {
    try {
      const response = await fetch('/api/runtime-status');
      const data = await responseData(response);
      runtimeReady = Boolean(response.ok && data.ready);
      searchButton.disabled = !runtimeReady;
      searchButton.textContent = '搜索';
      setMessage(runtimeMessage, data.message || (runtimeReady ? 'OpenCLI 已就绪' : 'OpenCLI 尚未就绪'), !runtimeReady);
    } catch (error) {
      runtimeReady = false;
      searchButton.disabled = true;
      searchButton.textContent = '搜索';
      setMessage(runtimeMessage, error.message, true);
    }
  }

  async function search() {
    const nickname = nameInput.value.trim();
    if (!nickname || !runtimeReady) {
      setMessage(addMessage, nickname ? 'OpenCLI 尚未就绪' : '请输入 UP 主昵称', true);
      return;
    }
    selected = null;
    confirmButton.disabled = true;
    searchButton.disabled = true;
    searchButton.textContent = '搜索中…';
    loading.hidden = false;
    setMessage(addMessage, '');
    resultsContainer.replaceChildren();
    try {
      const response = await fetch('/api/up-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nickname }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || 'UP 主搜索失败，请重试');
      renderResults(Array.isArray(data) ? data : []);
    } catch (error) {
      renderResults([]);
      setMessage(addMessage, error.message, true);
    } finally {
      loading.hidden = true;
      searchButton.disabled = !runtimeReady;
      searchButton.textContent = '搜索';
    }
  }

  async function confirm() {
    if (!selected) return;
    confirmButton.disabled = true;
    setMessage(addMessage, '正在写入…');
    try {
      const response = await fetch('/api/followings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid: selected.uid, nickname: selected.nickname, bio: selected.bio || '' }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '写入失败，请重试');
      dialog.close();
      const actionText = data.action === 'updated' ? '已更新 UP 主信息' : '已添加 UP 主';
      const sync = data.video_sync || {};
      feedback.textContent = sync.status === 'ok'
        ? `${actionText}，已同步 ${sync.video_count || 0} 个视频`
        : `${actionText}，初始视频同步失败，可稍后点击“刷新列表”：${sync.message || '请重试'}`;
      if (window.upManagement) await window.upManagement.load();
    } catch (error) {
      setMessage(addMessage, error.message, true);
      confirmButton.disabled = false;
    }
  }

  function open() {
    resetSearch();
    dialog.showModal();
    checkRuntime();
    nameInput.focus();
  }

  function close() {
    dialog.close();
  }

  addButton.addEventListener('click', open);
  closeButton.addEventListener('click', close);
  form.addEventListener('submit', (event) => { event.preventDefault(); search(); });
  confirmButton.addEventListener('click', confirm);
}());
