(function () {
  const libraryRoot = document.querySelector('#library-root');
  const saveRootButton = document.querySelector('#btn-save-library-root');
  const openRootButton = document.querySelector('#btn-open-library-folder');
  const singleInput = document.querySelector('#single-video-url');
  const singleDownloadButton = document.querySelector('#btn-single-download');
  const openSingleButton = document.querySelector('#btn-open-single-folder');
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
      const response = await fetch('/api/setup-status');
      const data = await responseData(response);
      if (!response.ok || !data.configured) throw new Error(data.message || '无法读取视频知识库目录');
      libraryRoot.value = data.knowledge_base_root || '';
      libraryRoot.placeholder = '选择视频库根目录';
    } catch (error) {
      libraryRoot.value = '';
      libraryRoot.placeholder = error.message;
      setStatus(error.message, true);
    }
  }

  async function chooseLibrary() {
    saveRootButton.disabled = true;
    saveRootButton.textContent = '正在打开目录选择器…';
    try {
      const response = await fetch('/api/setup/select-library', { method: 'POST' });
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
      const response = await fetch(endpoint, { method: 'POST' });
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
      const response = await fetch('/api/videos/download-progress');
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
      setStatus('请输入 B 站视频链接或 BV 号', true);
      return;
    }
    stopProgressPolling();
    singleDownloadButton.disabled = true;
    setStatus('正在获取视频信息…');
    try {
      const response = await fetch('/api/single-video/download', {
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
  singleDownloadButton.addEventListener('click', downloadSingle);
  singleInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') downloadSingle();
  });

  window.otherFeatures = { load };
}());
