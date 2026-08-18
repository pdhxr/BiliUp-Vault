(function () {
  const tableBody = document.querySelector('#table-body');
  const emptyState = document.querySelector('#empty-state');
  const emptyStateText = emptyState.querySelector('p');
  const checkAll = document.querySelector('#check-all-ups');
  const batchSyncButton = document.querySelector('#btn-sync');
  const stopSyncButton = document.querySelector('#btn-stop-sync');
  const deleteButton = document.querySelector('#btn-delete');
  const deleteDialog = document.querySelector('#delete-dialog');
  const deleteDialogClose = document.querySelector('#delete-dialog-close');
  const deleteDialogCancel = document.querySelector('#delete-dialog-cancel');
  const deleteDialogConfirm = document.querySelector('#delete-dialog-confirm');
  const deleteDialogMessage = document.querySelector('#delete-dialog-message');
  const batchSyncButtonLabel = batchSyncButton.textContent;
  const stopSyncButtonLabel = stopSyncButton.textContent;

  let rows = [];
  let syncing = false;
  let pendingDeleteIds = [];

  function formatDate(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function escapeHtml(value) {
    const element = document.createElement('div');
    element.textContent = String(value ?? '');
    return element.innerHTML;
  }

  function count(value) {
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 ? number : 0;
  }

  function syncPercent(downloaded, synced) {
    return synced ? Math.round((downloaded / synced) * 100) : 0;
  }

  function rowCheckboxes() {
    return [...tableBody.querySelectorAll('.table-checkbox')];
  }

  function selectedIds() {
    return rowCheckboxes()
      .filter((checkbox) => checkbox.checked)
      .map((checkbox) => checkbox.dataset.upId)
      .filter(Boolean);
  }

  function selectedAutoTrackIds() {
    return [...tableBody.querySelectorAll('.tracking-checkbox:checked')]
      .map((checkbox) => checkbox.dataset.upId)
      .filter(Boolean);
  }

  function updateSelectionButtons() {
    deleteButton.disabled = syncing || selectedIds().length === 0;
  }

  function setSyncing(value, stopAllowed = false) {
    syncing = Boolean(value);
    batchSyncButton.disabled = syncing;
    batchSyncButton.textContent = syncing ? '同步中…' : batchSyncButtonLabel;
    stopSyncButton.hidden = !syncing || !stopAllowed;
    if (!syncing) {
      stopSyncButton.disabled = false;
      stopSyncButton.textContent = stopSyncButtonLabel;
    }
    deleteButton.disabled = syncing || selectedIds().length === 0;
    tableBody.querySelectorAll('.btn-sync-row').forEach((button) => {
      button.disabled = syncing;
    });
    tableBody.querySelectorAll('.tracking-checkbox').forEach((checkbox) => {
      checkbox.disabled = syncing;
    });
  }

  function updateCheckAllState() {
    const checkboxes = rowCheckboxes();
    const checkedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
    checkAll.disabled = checkboxes.length === 0;
    checkAll.checked = checkboxes.length > 0 && checkedCount === checkboxes.length;
    checkAll.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
    updateSelectionButtons();
  }

  function renderRows() {
    tableBody.replaceChildren();
    checkAll.checked = false;
    checkAll.indeterminate = false;
    checkAll.disabled = rows.length === 0;
    deleteButton.disabled = true;
    emptyState.style.display = rows.length === 0 ? 'flex' : 'none';
    emptyStateText.textContent = '暂无UP主数据，点击“添加”开始';

    rows.forEach((row, index) => {
      const downloaded = count(row.downloaded_count);
      const synced = count(row.synced_count);
      const percent = syncPercent(downloaded, synced);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="col-check"><input type="checkbox" class="table-checkbox" data-up-id="${escapeHtml(row.up_id)}" aria-label="选择 ${escapeHtml(row.nickname)}"></td>
        <td class="col-index">${index + 1}</td>
        <td class="col-name">${escapeHtml(row.nickname)}</td>
        <td class="col-bio" title="${escapeHtml(row.bio)}">${escapeHtml(row.bio)}</td>
        <td class="col-tracking"><input class="tracking-checkbox" type="checkbox" data-up-id="${escapeHtml(row.up_id)}" ${row.scheduled_tracking ? 'checked' : ''} aria-label="${escapeHtml(row.nickname)}自动追踪下载"></td>
        <td class="col-time">${escapeHtml(formatDate(row.last_sync_time))}</td>
        <td class="col-synced">
          <div class="sync-bar-bg"><div class="sync-bar-fill" style="width:${percent}%"></div></div>
          <span class="sync-pct">${downloaded} / ${synced}</span>
        </td>
        <td class="col-action">
          <button class="btn-sync-row" type="button" title="刷新视频列表" aria-label="刷新视频列表">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M10 4.5q1.823 0 3.604.162a.68.68 0 0 1 .615.597q.187 1.557.25 3.15l-1.689-1.69a.75.75 0 0 0-1.06 1.061l2.999 3a.75.75 0 0 0 1.06 0l3.001-3a.75.75 0 1 0-1.06-1.06l-1.748 1.747a41 41 0 0 0-.264-3.386a2.18 2.18 0 0 0-1.97-1.913a41.5 41.5 0 0 0-7.477 0a2.18 2.18 0 0 0-1.969 1.913a41 41 0 0 0-.16 1.61a.75.75 0 1 0 1.495.12q.062-.78.154-1.552a.68.68 0 0 1 .615-.597A40 40 0 0 1 10 4.5"/>
              <path d="M5.281 9.22a.75.75 0 0 0-1.06 0l-3.001 3a.75.75 0 1 0 1.06 1.06l1.748-1.747q.063 1.712.264 3.386a2.18 2.18 0 0 0 1.97 1.913a41.5 41.5 0 0 0 7.477 0a2.18 2.18 0 0 0 1.969-1.913q.096-.801.16-1.61a.75.75 0 1 0-1.495-.12q-.062-.78-.154 1.552a.68.68 0 0 1-.615.597a40 40 0 0 1-7.208 0a.68.68 0 0 1-.615-.597a40 40 0 0 1-.25-3.15l1.689 1.69a.75.75 0 0 0 1.06-1.061z"/>
            </svg>
          </button>
      </td>`;
      tableBody.appendChild(tr);
      tr.querySelector('.table-checkbox').addEventListener('change', updateCheckAllState);
      const syncButton = tr.querySelector('.btn-sync-row');
      if (window.upVideoSync) {
        syncButton.addEventListener('click', () => window.upVideoSync.refresh(row.up_id, syncButton));
      } else {
        syncButton.disabled = true;
      }
      const trackingCheckbox = tr.querySelector('.tracking-checkbox');
      trackingCheckbox.addEventListener('change', async () => {
        const enabled = trackingCheckbox.checked;
        trackingCheckbox.disabled = true;
        try {
          const response = await window.apiFetch('/api/followings/tracking', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ up_id: row.up_id, scheduled_tracking: enabled }),
          });
          const data = await response.json();
          if (!response.ok) throw new Error(data.detail || '保存自动追踪设置失败');
          row.scheduled_tracking = Boolean(data.scheduled_tracking);
          trackingCheckbox.checked = row.scheduled_tracking;
          window.dispatchEvent(new CustomEvent('biliup:tracking-setting-changed'));
          document.querySelector('#up-feedback').textContent = row.scheduled_tracking
            ? `已启用 ${row.nickname} 的自动追踪下载`
            : `已停用 ${row.nickname} 的自动追踪下载`;
        } catch (error) {
          trackingCheckbox.checked = !enabled;
          document.querySelector('#up-feedback').textContent = error.message;
        } finally {
          trackingCheckbox.disabled = syncing;
          updateCheckAllState();
        }
      });
    });
    updateCheckAllState();
    setSyncing(syncing);
  }

  async function load() {
    try {
      const response = await window.apiFetch('/api/followings');
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '无法读取 UP 列表');
      rows = Array.isArray(data) ? data : [];
      renderRows();
      return rows;
    } catch (error) {
      rows = [];
      tableBody.replaceChildren();
      checkAll.disabled = true;
      checkAll.checked = false;
      checkAll.indeterminate = false;
      deleteButton.disabled = true;
      emptyState.style.display = 'flex';
      emptyStateText.textContent = error.message;
      return [];
    }
  }

  checkAll.addEventListener('change', () => {
    rowCheckboxes().forEach((checkbox) => { checkbox.checked = checkAll.checked; });
    updateCheckAllState();
  });

  async function deleteSelected(ids) {
    deleteButton.disabled = true;
    deleteDialogConfirm.disabled = true;
    try {
      const response = await window.apiFetch('/api/followings/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ up_ids: ids }),
      });
      const text = await response.text();
      let data = {};
      try {
        data = text ? JSON.parse(text) : {};
      } catch (_) {
        throw new Error(response.ok ? '服务返回的数据格式不正确' : '删除请求失败，请重试');
      }
      if (!response.ok) throw new Error(data.detail || '删除 UP 主失败');
      rows = rows.filter((row) => !ids.includes(String(row.up_id)));
      renderRows();
      const count = Number(data.count || data.deleted?.length || 0);
      document.querySelector('#up-feedback').textContent = `已删除 ${count} 个 UP 主登记，本地视频文件已保留`;
    } catch (error) {
      document.querySelector('#up-feedback').textContent = error.message;
      updateCheckAllState();
    } finally {
      deleteDialogConfirm.disabled = false;
    }
  }

  function closeDeleteDialog() {
    pendingDeleteIds = [];
    if (deleteDialog.open) deleteDialog.close();
  }

  deleteButton.addEventListener('click', () => {
    const ids = selectedIds();
    if (!ids.length || syncing) return;
    const selectedRows = rows.filter((row) => ids.includes(String(row.up_id)));
    const names = selectedRows.map((row) => row.nickname).join('、');
    pendingDeleteIds = ids;
    deleteDialogMessage.textContent = `确定删除选中的 ${ids.length} 个 UP 主登记吗？${names ? `（${names}）` : ''}`;
    deleteDialog.showModal();
  });

  deleteDialogClose.addEventListener('click', closeDeleteDialog);
  deleteDialogCancel.addEventListener('click', closeDeleteDialog);
  deleteDialog.addEventListener('cancel', () => { pendingDeleteIds = []; });
  deleteDialogConfirm.addEventListener('click', async () => {
    const ids = pendingDeleteIds;
    if (!ids.length) return;
    closeDeleteDialog();
    await deleteSelected(ids);
  });

  window.upManagement = {
    getSelectedIds: selectedIds,
    getSelectedAutoTrackIds: selectedAutoTrackIds,
    load,
    setSyncing,
  };
}());
