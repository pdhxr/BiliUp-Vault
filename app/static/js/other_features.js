(function () {
  const libraryRoot = document.querySelector('#library-root');
  const saveRootButton = document.querySelector('#btn-save-library-root');
  const openRootButton = document.querySelector('#btn-open-library-folder');
  const singleInput = document.querySelector('#single-video-url');
  const singleDownloadButton = document.querySelector('#btn-single-download');
  const openSingleButton = document.querySelector('#btn-open-single-folder');
  const desktopPort = document.querySelector('#desktop-port');
  const saveDesktopPortButton = document.querySelector('#btn-save-desktop-port');
  const desktopPortStatus = document.querySelector('#desktop-port-status');
  const desktopConfigFilePath = document.querySelector('#desktop-config-file-path');
  const status = document.querySelector('#other-status');

  let progressTimer = null;

  async function responseData(response) {
    const text = await response.text();
    try {
      return text ? JSON.parse(text) : {};
    } catch (_) {
      throw new Error(response.ok ? '服务返回的数据格式不正确' : '服务请求失败，请重试');
    }
  }

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle('error', isError);
  }

  async function load() {
    try {
      const response = await window.apiFetch('/api/setup-status');
      const data = await responseData(response);
      if (!response.ok || !data.configured) throw new Error(data.message || '无法读取视频知识库目录');
      libraryRoot.value = data.knowledge_base_root || '';
      libraryRoot.placeholder = '选择视频库根目录';
    } catch (error) {
      libraryRoot.value = '';
      libraryRoot.placeholder = error.message;
      setStatus(error.message, true);
    }
    await loadDesktopSettings();
  }

  async function loadDesktopSettings() {
    try {
      const response = await window.apiFetch('/api/settings/desktop');
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '无法读取桌面端口设置');
      desktopPort.value = String(data.desktop_port || 8765);
      desktopConfigFilePath.textContent = data.config_file || '未返回配置文件路径';
      if (data.restart_required) {
        desktopPortStatus.textContent = `本次使用 ${data.current_port}，重启后使用 ${data.desktop_port}`;
      } else if (data.desktop_mode) {
        desktopPortStatus.textContent = `本次使用 ${data.current_port}`;
      } else {
        desktopPortStatus.textContent = `桌面版下次使用 ${data.desktop_port}`;
      }
      desktopPortStatus.classList.remove('error');
    } catch (error) {
      desktopConfigFilePath.textContent = '无法读取配置文件路径';
      desktopPortStatus.textContent = error.message;
      desktopPortStatus.classList.add('error');
    }
  }

  async function saveDesktopPort() {
    saveDesktopPortButton.disabled = true;
    desktopPortStatus.textContent = '保存中…';
    desktopPortStatus.classList.remove('error');
    try {
      const value = Number(desktopPort.value);
      const response = await window.apiFetch('/api/settings/desktop', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ desktop_port: value }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '保存桌面端口失败');
      desktopPort.value = String(data.desktop_port);
      desktopConfigFilePath.textContent = data.config_file || desktopConfigFilePath.textContent;
      desktopPortStatus.textContent = data.restart_required
        ? `已保存；本次仍使用 ${data.current_port}，重启后使用 ${data.desktop_port}`
        : `已保存：${data.desktop_port}`;
    } catch (error) {
      desktopPortStatus.textContent = error.message;
      desktopPortStatus.classList.add('error');
    } finally {
      saveDesktopPortButton.disabled = false;
    }
  }

  async function chooseLibrary() {
    saveRootButton.disabled = true;
    saveRootButton.textContent = '正在打开目录选择器…';
    try {
      const response = await window.apiFetch('/api/setup/select-library', { method: 'POST' });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '设置视频库位置失败');
      if (data.cancelled) {
        setStatus(data.message || '未选择目录');
        return;
      }
      libraryRoot.value = data.knowledge_base_root || '';
      setStatus('视频库位置已保存');
      if (window.upManagement) await window.upManagement.load();
      window.dispatchEvent(new CustomEvent('biliup:library-changed'));
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      saveRootButton.disabled = false;
      saveRootButton.textContent = '选择并保存位置';
    }
  }

  async function openFolder(endpoint, button) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = '正在打开…';
    try {
      const response = await window.apiFetch(endpoint, { method: 'POST' });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '无法打开目录');
      setStatus(`已打开：${data.path}`);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function stopProgressPolling() {
    if (progressTimer) {
      clearTimeout(progressTimer);
      progressTimer = null;
    }
  }

  async function pollProgress(bvid) {
    try {
      const response = await window.apiFetch('/api/videos/download-progress');
      const rows = await responseData(response);
      if (!response.ok) throw new Error(rows.detail || '无法读取下载进度');
      const row = Array.isArray(rows)
        ? rows.find((item) => String(item.bvid || '').toUpperCase() === String(bvid).toUpperCase())
        : null;
      if (!row) {
        progressTimer = setTimeout(() => pollProgress(bvid), 1000);
        return;
      }
      if (row.status === 'queued' || row.status === 'downloading') {
        setStatus(`单视频下载中：${row.title || bvid}`);
        progressTimer = setTimeout(() => pollProgress(bvid), 1000);
        return;
      }
      if (row.status === 'success') {
        setStatus(`单视频下载完成：${row.title || bvid}`);
      } else {
        setStatus(row.error || '单视频下载失败', true);
      }
      singleDownloadButton.disabled = false;
    } catch (error) {
      setStatus(error.message, true);
      singleDownloadButton.disabled = false;
    }
  }

  async function downloadSingle() {
    const url = singleInput.value.trim();
    if (!url) {
      setStatus('请输入 B 站或抖音视频链接', true);
      return;
    }
    stopProgressPolling();
    singleDownloadButton.disabled = true;
    setStatus('正在获取视频信息…');
    try {
      const response = await window.apiFetch('/api/single-video/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await responseData(response);
      if (!response.ok) throw new Error(data.detail || '提交单视频下载失败');
      const job = data.job || {};
      if (job.status === 'success') {
        setStatus(`视频已在本地：${job.title || job.bvid || ''}`);
        singleDownloadButton.disabled = false;
        return;
      }
      setStatus(`已提交单视频下载：${job.title || job.bvid || ''}`);
      if (job.bvid) pollProgress(job.bvid);
    } catch (error) {
      setStatus(error.message, true);
      singleDownloadButton.disabled = false;
    }
  }

  saveRootButton.addEventListener('click', chooseLibrary);
  openRootButton.addEventListener('click', () => openFolder('/api/library/open-folder', openRootButton));
  openSingleButton.addEventListener('click', () => openFolder('/api/single-video/open-folder', openSingleButton));
  saveDesktopPortButton.addEventListener('click', saveDesktopPort);
  singleDownloadButton.addEventListener('click', downloadSingle);
  singleInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') downloadSingle();
  });

  window.otherFeatures = { load };
}());
