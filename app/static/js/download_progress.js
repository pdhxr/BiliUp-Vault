(function () {
  const panel = document.querySelector('#download-progress-panel');
  const statusText = document.querySelector('#progress-status-text');
  const listDropdown = document.querySelector('#progress-list-dropdown');
  const list = document.querySelector('#progress-list');
  const clearButton = document.querySelector('#progress-clear');
  const videoPanel = document.querySelector('[data-panel="video-download"]');

  let timer = null;
  let dismissed = false;
  let previousActive = 0;

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

  function formatSize(value) {
    const size = Number(value || 0);
    if (!size) return '';
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
  }

  function statusLabel(status) {
    return {
      queued: '排队中',
      downloading: '下载中',
      success: '完成',
      failed: '失败',
      cancelled: '已停止',
    }[status] || status || '未知';
  }

  function render(rows) {
    const active = rows.filter((row) => row.status === 'queued' || row.status === 'downloading').length;
    const failed = rows.filter((row) => row.status === 'failed').length;
    const done = rows.filter((row) => row.status === 'success').length;
    const cancelled = rows.filter((row) => row.status === 'cancelled').length;
    const queued = rows.filter((row) => row.status === 'queued').length;
    const downloading = rows.filter((row) => row.status === 'downloading').length;
    const parts = [];
    if (downloading) parts.push(`${downloading} 下载中`);
    if (queued) parts.push(`${queued} 排队中`);
    if (failed) parts.push(`${failed} 失败`);
    if (cancelled) parts.push(`${cancelled} 已停止`);
    if (done) parts.push(`${done} 完成`);
    statusText.textContent = parts.join(' · ');

    const order = { downloading: 0, queued: 1, failed: 2, cancelled: 3, success: 4 };
    const sorted = [...rows].sort((left, right) => (order[left.status] ?? 9) - (order[right.status] ?? 9));
    list.innerHTML = sorted.map((row) => {
      const state = String(row.status || '');
      const className = state === 'success' ? 'done' : ['failed', 'cancelled'].includes(state) ? 'failed' : 'active';
      const icon = state === 'success' ? '✓' : state === 'cancelled' ? '■' : state === 'failed' ? '✗' : '⏳';
      const title = String(row.title || row.bvid || '视频').slice(0, 60);
      const error = state === 'failed' && row.error ? `：${row.error}` : '';
      const size = state === 'downloading' ? formatSize(row.size_bytes) : '';
      return `<div class="progress-item ${className}" title="${escapeHtml(error.slice(1))}">
        <span class="progress-icon">${icon}</span>
        <span class="progress-name">${escapeHtml(title)}</span>
        <span class="progress-status">${statusLabel(state)}<span class="progress-size">${escapeHtml(size)}</span></span>
      </div>`;
    }).join('');

    const visible = rows.length > 0 && !dismissed && !videoPanel.hidden;
    panel.classList.toggle('hidden', !visible);
    listDropdown.hidden = !visible;
    return active;
  }

  async function poll() {
    try {
      const response = await window.apiFetch('/api/videos/download-progress');
      const rows = await responseData(response);
      if (!response.ok) throw new Error(rows.detail || '无法读取下载进度');
      const normalized = Array.isArray(rows) ? rows : [];
      const active = render(normalized);
      if (previousActive > 0 && active === 0) {
        window.dispatchEvent(new CustomEvent('biliup:downloads-complete', { detail: normalized }));
      }
      previousActive = active;
    } catch (_) {
      // 下载任务仍在后台运行，下一轮轮询继续尝试。
    }
  }

  function start() {
    if (timer) return;
    poll();
    timer = window.setInterval(poll, 1000);
  }

  function show() {
    dismissed = false;
    start();
    poll();
  }

  clearButton.addEventListener('click', () => {
    dismissed = true;
    panel.classList.add('hidden');
    listDropdown.hidden = true;
  });
  document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', poll));

  start();
  window.downloadProgress = { start, show, refresh: poll };
}());
