(function () {
  const selector = document.querySelector('#video-up-selector');
  const refreshButton = document.querySelector('#btn-refresh-videos');
  const downloadButton = document.querySelector('#btn-download');
  const batchButton = document.querySelector('#btn-batch-track-video');
  const batchSyncButton = document.querySelector('#btn-sync');
  const sinceDate = document.querySelector('#track-since-date-video');
  const sinceDateStatus = document.querySelector('#track-date-status');
  const checkAll = document.querySelector('#check-all-videos');
  const tableBody = document.querySelector('#video-table-body');
  const emptyState = document.querySelector('#video-empty-state');
  const status = document.querySelector('#video-status');
  const upFeedback = document.querySelector('#up-feedback');
  const tabs = document.querySelectorAll('.tab');

  let currentUpId = '';
  let videos = [];
  let batchTrackTimer = null;
  let saveSinceDatePromise = Promise.resolve();

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

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle('error', isError);
  }

  function formatDate(value) {
    const text = String(value || '');
    return text || '-';
  }

  function visibleVideos() {
    return videos;
  }

  function selectedBvids() {
    return [...tableBody.querySelectorAll('.video-checkbox:checked')].map((input) => input.value);
  }

  function batchUpIds() {
    return window.upManagement && window.upManagement.getSelectedAutoTrackIds
      ? window.upManagement.getSelectedAutoTrackIds()
      : [];
  }

  function updateButtons() {
    const hasUp = Boolean(currentUpId);
    const selected = selectedBvids().length > 0;
    downloadButton.disabled = !hasUp || !selected;
    refreshButton.disabled = !hasUp;
    checkAll.disabled = visibleVideos().length === 0;
  }

  function render() {
    const rows = visibleVideos();
    tableBody.replaceChildren();
    emptyState.style.display = rows.length ? 'none' : 'flex';
    rows.forEach((video, index) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td class="col-check"><input class="video-checkbox" type="checkbox" value="${escapeHtml(video.bvid)}" aria-label="选择 ${escapeHtml(video.title)}"></td>
        <td class="col-index">${index + 1}</td>
        <td class="col-date">${escapeHtml(formatDate(video.pub_time))}</td>
        <td class="col-title" title="${escapeHtml(video.title)}">${escapeHtml(video.title)}</td>
        <td class="col-download video-download-state">${video.downloaded ? '是' : '否'}</td>
        <td class="col-script">—</td>`;
      row.querySelector('.video-checkbox').addEventListener('change', updateButtons);
      tableBody.appendChild(row);
    });
    checkAll.checked = false;
    updateButtons();
  }

  async function loadFollowings() {
    try {
      const response = await fetch('/api/followings');
      const rows = await responseData(response);
      if (!response.ok) throw new Error(rows.detail || '无法读取 UP 列表');
      const previous = currentUpId;
      selector.replaceChildren();
      const first = document.createElement('option');
      first.value = '';
      first.textContent = '-- 选择UP主 --';
      selector.appendChild(first);
      rows.forEach((row) => {
        const option = document.createElement('option');
        option.value = row.up_id;
        option.textContent = `${row.nickname} (${row.total_count || 0} 个视频)`;
        selector.appendChild(option);
      });
      selector.disabled = rows.length === 0;
      if (rows.some((row) => row.up_id === previous)) {
        selector.value = previous;
        await loadVideos(previous);
      } else {
        currentUpId = '';
        videos = [];
        render();
      }
    } catch (error) {
      selector.disabled = true;
      setStatus(error.message, true);
    }
  }

  async function loadBatchTrackSettings() {
    try {
      const response = await fetch('/api/settings/batch-track');
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '无法读取批量追踪设置');
      sinceDate.value = data.since_date || '';
      sinceDateStatus.textContent = sinceDate.value ? '已保存' : '未设置';
      render();
    } catch (error) {
      sinceDateStatus.textContent = error.message;
      setStatus(error.message, true);
    }
  }

  function saveBatchTrackSettings() {
    const value = sinceDate.value;
    sinceDateStatus.textContent = '保存中…';
    saveSinceDatePromise = (async () => {
      const response = await fetch('/api/settings/batch-track', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ since_date: value }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '保存批量追踪设置失败');
      sinceDate.value = data.since_date || '';
      sinceDateStatus.textContent = sinceDate.value ? '已保存' : '未设置';
      return data.since_date || '';
    })().catch((error) => {
      sinceDateStatus.textContent = error.message;
      setStatus(error.message, true);
      throw error;
    });
    return saveSinceDatePromise;
  }

  async function loadVideos(upId) {
    currentUpId = upId;
    videos = [];
    render();
    if (!upId) return;
    try {
      const response = await fetch(`/api/up/${encodeURIComponent(upId)}/videos`);
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '无法读取视频列表');
      videos = Array.isArray(data) ? data : [];
      render();
      setStatus(videos.length ? `已加载 ${videos.length} 个视频` : '暂无本地视频列表，请点击“刷新列表”');
    } catch (error) {
      videos = [];
      render();
      setStatus(error.message, true);
    }
  }

  async function refresh(upId, button = refreshButton) {
    if (!upId) return [];
    const original = button.textContent;
    const isRowButton = button.classList.contains('btn-sync-row');
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    if (!isRowButton) button.textContent = '刷新中…';
    setStatus('正在从 B 站刷新视频列表…');
    try {
      const response = await fetch(`/api/up/${encodeURIComponent(upId)}/videos/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ page: 1, limit: 50 }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '刷新视频列表失败');
      if (upId === currentUpId) {
        videos = Array.isArray(data) ? data : [];
        render();
      }
      if (window.upManagement) await window.upManagement.load();
      setStatus(`刷新完成，共 ${Array.isArray(data) ? data.length : 0} 个视频`);
      upFeedback.textContent = `已刷新 ${upId} 的视频列表`;
      return data;
    } catch (error) {
      setStatus(error.message, true);
      upFeedback.textContent = error.message;
      return [];
    } finally {
      button.disabled = false;
      button.removeAttribute('aria-busy');
      if (!isRowButton) button.textContent = original;
      updateButtons();
    }
  }

  let batchSyncTimer = null;

  function restoreBatchSyncButton(button, original) {
    button.textContent = original;
    if (window.upManagement) window.upManagement.setSyncing(false);
  }

  async function pollBatchSync(button, original) {
    try {
      const response = await fetch('/api/up/videos/batch-refresh-progress');
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '无法读取批量同步进度');
      if (data.running) {
        const current = data.current_up ? `：${data.current_up}` : '';
        setStatus(`正在增量同步 ${data.done}/${data.total}${current}`);
        upFeedback.textContent = `同步中 ${data.done}/${data.total}${current}`;
        button.textContent = '同步中…';
        return;
      }
      if (batchSyncTimer) {
        clearInterval(batchSyncTimer);
        batchSyncTimer = null;
      }
      restoreBatchSyncButton(button, original);
      await loadFollowings();
      if (window.upManagement) await window.upManagement.load();
      const errorSuffix = Number(data.errors || 0) ? `，${data.errors} 个失败` : '';
      setStatus(`批量同步完成：新增 ${data.added_total || 0} 个视频${errorSuffix}`);
      upFeedback.textContent = `批量同步完成：新增 ${data.added_total || 0} 个视频${errorSuffix}`;
    } catch (error) {
      if (batchSyncTimer) {
        clearInterval(batchSyncTimer);
        batchSyncTimer = null;
      }
      restoreBatchSyncButton(button, original);
      upFeedback.textContent = error.message;
      setStatus(error.message, true);
    }
  }

  function startBatchSyncPolling(button, original) {
    if (batchSyncTimer) clearInterval(batchSyncTimer);
    batchSyncTimer = setInterval(() => pollBatchSync(button, original), 1000);
    pollBatchSync(button, original);
  }

  async function refreshAll(upIds, triggerButton = batchSyncButton) {
    const selected = [...new Set((upIds || []).map((value) => String(value).trim()).filter(Boolean))];
    if (selected.length === 0) {
      upFeedback.textContent = '请先选择要同步的 UP 主';
      return [];
    }
    const original = triggerButton.textContent;
    if (window.upManagement) window.upManagement.setSyncing(true);
    triggerButton.textContent = '同步中…';
    upFeedback.textContent = `正在启动 ${selected.length} 个 UP 主的增量同步…`;
    try {
      const response = await fetch('/api/up/videos/batch-refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ up_ids: selected }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '批量同步启动失败');
      startBatchSyncPolling(triggerButton, original);
      return data;
    } catch (error) {
      restoreBatchSyncButton(triggerButton, original);
      upFeedback.textContent = error.message;
      setStatus(error.message, true);
      return [];
    }
  }

  async function downloadSelected() {
    const bvids = selectedBvids();
    if (!currentUpId || !bvids.length) return;
    downloadButton.disabled = true;
    setStatus(`已提交 ${bvids.length} 个视频下载任务…`);
    try {
      const response = await fetch('/api/videos/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ up_id: currentUpId, bvids }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '提交下载失败');
      setStatus(`已提交 ${data.jobs.length} 个下载任务`);
      if (window.downloadProgress) window.downloadProgress.show();
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      updateButtons();
    }
  }

  function restoreBatchTrackButton(original) {
    if (batchTrackTimer) {
      clearInterval(batchTrackTimer);
      batchTrackTimer = null;
    }
    batchButton.textContent = original;
    if (window.upManagement) window.upManagement.setSyncing(false);
    updateButtons();
  }

  async function pollBatchTrackDownload(original) {
    try {
      const response = await fetch('/api/up/videos/batch-track-download-progress');
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '无法读取批量追踪下载进度');
      if (data.running) {
        if (data.phase === 'tracking') {
          const current = data.current_up ? `：${data.current_up}` : '';
          setStatus(`正在追踪 ${data.done}/${data.total}${current}`);
          upFeedback.textContent = `追踪中 ${data.done}/${data.total}${current}`;
          batchButton.textContent = `追踪中 ${data.done}/${data.total}`;
        } else {
          setStatus(`正在下载 ${data.download_done}/${data.download_total}`);
          upFeedback.textContent = `下载中 ${data.download_done}/${data.download_total}`;
          batchButton.textContent = `下载中 ${data.download_done}/${data.download_total}`;
        }
        return;
      }
      restoreBatchTrackButton(original);
      await loadFollowings();
      if (currentUpId) await loadVideos(currentUpId);
      if (window.upManagement) await window.upManagement.load();
      const errorSuffix = Number(data.errors || 0) ? `，${data.errors} 个失败` : '';
      setStatus(`批量追踪并下载完成：新增 ${data.added_total || 0} 个视频，下载 ${data.download_done || 0}/${data.download_total || 0}${errorSuffix}`);
      upFeedback.textContent = `批量追踪并下载完成：新增 ${data.added_total || 0} 个视频${errorSuffix}`;
    } catch (error) {
      restoreBatchTrackButton(original);
      upFeedback.textContent = error.message;
      setStatus(error.message, true);
    }
  }

  async function startBatchTrackDownload() {
    try {
      await saveSinceDatePromise;
    } catch (_) {
      return;
    }
    const ids = batchUpIds();
    const since = sinceDate.value;
    if (!ids.length) {
      upFeedback.textContent = '请先在 UP 主管理页签勾选并启用自动追踪下载的 UP 主';
      return;
    }
    if (!since) {
      upFeedback.textContent = '请先选择起始日期';
      setStatus('批量追踪并下载需要起始日期', true);
      return;
    }
    const original = batchButton.textContent;
    if (window.upManagement) window.upManagement.setSyncing(true);
    batchButton.textContent = '追踪中…';
    upFeedback.textContent = `正在启动 ${ids.length} 个 UP 主的批量追踪…`;
    setStatus('正在启动批量追踪…');
    if (window.downloadProgress) window.downloadProgress.show();
    try {
      const response = await fetch('/api/up/videos/batch-track-download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ up_ids: ids }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '批量追踪启动失败');
      if (data.status === 'busy') throw new Error('已有批量任务正在运行');
      if (data.skipped_ids && data.skipped_ids.length) {
        upFeedback.textContent = `已跳过 ${data.skipped_ids.length} 个未启用自动追踪的 UP 主`;
      }
      if (batchTrackTimer) clearInterval(batchTrackTimer);
      batchTrackTimer = setInterval(() => pollBatchTrackDownload(original), 1000);
      await pollBatchTrackDownload(original);
    } catch (error) {
      restoreBatchTrackButton(original);
      upFeedback.textContent = error.message;
      setStatus(error.message, true);
    }
  }

  selector.addEventListener('change', () => loadVideos(selector.value));
  sinceDate.addEventListener('change', () => {
    render();
    updateButtons();
    saveBatchTrackSettings().catch(() => {});
  });
  refreshButton.addEventListener('click', () => refresh(currentUpId));
  downloadButton.addEventListener('click', downloadSelected);
  batchButton.addEventListener('click', startBatchTrackDownload);
  batchSyncButton.addEventListener('click', () => {
    const selectedIds = window.upManagement ? window.upManagement.getSelectedIds() : [];
    refreshAll(selectedIds, batchSyncButton).catch((error) => {
      upFeedback.textContent = error.message;
      setStatus(error.message, true);
    });
  });
  window.addEventListener('biliup:downloads-complete', async () => {
    if (currentUpId) await loadVideos(currentUpId);
    if (window.upManagement) await window.upManagement.load();
    setStatus('下载任务已完成');
  });
  window.addEventListener('biliup:tracking-setting-changed', updateButtons);
  checkAll.addEventListener('change', () => {
    tableBody.querySelectorAll('.video-checkbox').forEach((input) => { input.checked = checkAll.checked; });
    updateButtons();
  });
  tabs.forEach((tab) => tab.addEventListener('click', () => {
    if (tab.dataset.tab === 'video-download') {
      loadBatchTrackSettings();
      loadFollowings();
    }
  }));

  window.upVideoSync = { refresh, batchRefresh: refreshAll };
}());
