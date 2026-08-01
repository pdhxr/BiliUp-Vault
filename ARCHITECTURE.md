# BiliUp 架构

## 当前状态

当前 MVP 已实现首次知识库目录设置、OpenCLI 搜索、UP 单选登记、UP 视频列表刷新和选中视频下载。范围见 [PRD.md](PRD.md)。

## 三层架构

系统按单向依赖组织：静态网页层 → FastAPI 路由层 → `core` 业务内核层。

- `app/main.py`：应用组装、服务生命周期和浏览器打开。
- `app/static/`：静态网页；只调用本机 API 并展示结果。
- `app/static/js/up_search.js`：UP 搜索、结果单选和确认写入交互；不直接读写本地文件或执行 OpenCLI。
- `app/static/js/up_management.js`：UP 管理列表读取、选择联动和删除确认；不直接读写本地文件。
- `app/static/js/video_download.js`：视频列表选择、刷新和下载提交；不直接读写本地文件，也不负责进度展示。
- `app/static/js/download_progress.js`：独立轮询下载状态，展示汇总状态、任务标题、任务状态和已下载大小；下载完成后通知视频列表刷新。
- `app/routes/`：FastAPI 路由；只负责 HTTP 输入/输出与调用 `core`。
- `core/`：配置、首次设置、搜索、UP 主登记、UP 管理列表、OpenCLI 适配和 UpList 数据读写；不得依赖 FastAPI 或前端。
- `core/configuration.py`：读写用户知识库根目录和批量追踪起始日期配置，并校验已配置目录可写。
- `core/setup.py`：编排首次目录选择、配置保存和批量追踪设置读取/保存。
- `core/up_management.py`：编排当前知识库 UP 管理列表读取。
- `core/following_delete.py`：删除选中的 UP 登记和视频索引，不删除实际视频文件。
- `core/repositories/followings.py`：保存登记记录、自动追踪下载开关并将其转换为 UP 管理列表行，不包含 HTTP 或前端逻辑。
- `core/opencli_videos.py`：封装 OpenCLI 用户视频查询和视频下载命令，并标准化输出；浏览器型调用统一使用后台窗口模式。
- `core/video_sync.py`：刷新 UP 视频列表并回写视频统计。
- `core/followings.py`：登记 UP；确认登记后编排一次首批视频刷新。
- `core/video_reconcile.py`：协调远端追踪清单与本地视频库状态。
- `core/video_index.py`：按网站元数据扫描已有月度视频文件，补建本地 `videos.jsonl`。
- `core/video_batch_sync.py`：管理选中 UP 的后台批量增量同步和进度快照。
- `core/video_batch_track_download.py`：从应用配置读取起始日期，接收前端按“自动追踪下载”列筛出的 UP，编排按日期批量追踪与下载；刷新后从每个 UP 的完整视频列表筛选期限内未下载的视频，交给下载队列，并提供两阶段进度快照。
- `core/video_download.py`：后台下载队列、文件命名和索引更新；通过进度模块更新任务状态。
- `core/download_files.py`：识别 OpenCLI 生成的视频文件、清理 `.part` 临时文件和执行跨平台安全命名；不包含 HTTP 或 OpenCLI 调用。
- `core/download_progress.py`：下载状态存储、过期记录清理和下载目录大小监测，不包含 OpenCLI 或 HTTP 逻辑。
- `core/repositories/videos.py`：读写 `<knowledge_base_root>/UpList/<UP名称>.jsonl` 远端追踪清单。
- `core/repositories/library.py`：读写 `<knowledge_base_root>/SortedMp4/<UP名称>/videos.jsonl` 本地视频库索引；持久化格式与参考项目一致。
- `core/utils/system/`：唯一的 macOS/Windows 平台适配边界，提供统一的浏览器、子进程、目录选择、应用配置目录和 PyInstaller 资源路径接口。
- `scripts/build.py`：构建工具；在对应原生系统调用 PyInstaller，macOS 额外生成 DMG。

## 数据流

首次设置：WebUI → FastAPI setup route → `core/setup.py` → 系统目录选择器 / 配置文件。

登记：WebUI → FastAPI UP route → `core/followings.py` → `<knowledge_base_root>/UpList` repository → `core/video_sync.py` 首批刷新 → 两套视频索引协调。登记成功但首批刷新失败时保留登记，并把可重试错误返回给前端。

删除：WebUI → `POST /api/followings/delete` → FastAPI UP route → `core/following_delete.py` → followings repository 与远端追踪 repository；删除登记和 `UpList/<UP名称>.jsonl`，保留 `SortedMp4/<UP名称>/videos.jsonl` 及实际视频文件。

列表：WebUI → `GET /api/followings` → FastAPI UP route → `core/up_management.py` → UpList repository；读取失败只返回错误，不写入数据。

视频刷新：WebUI → `POST /api/up/{up_id}/videos/refresh` → FastAPI videos route → `core/video_sync.py` → `core/opencli_videos.py`。单个 UP 按时间倒序最多查询 5 页，每页默认 50 条；按 BV 号排除远端追踪清单已有记录，每次最多新增 20 条，连续两页无新增或遇到最后一页即停止，再写入 `UpList/<UP名称>.jsonl`。刷新后按元数据扫描已有月度视频文件补建本地 `videos.jsonl`，再用本地索引校准远端下载状态。

批量刷新：WebUI → `POST /api/up/videos/batch-refresh` → `core/video_batch_sync.py` 后台串行处理选中的 UP；每个 UP 复用单个渐进同步用例。WebUI 通过 `GET /api/up/videos/batch-refresh-progress` 轮询进度。

自动追踪设置：WebUI → `POST /api/followings/tracking` → `core/followings.py` → `UpList/followings.json`，保存每个 UP 的 `scheduled_tracking` 开关。批量日期设置：WebUI → `GET/PUT /api/settings/batch-track` → `core/setup.py` → `core/configuration.py`，保存到与知识库目录相同的应用 `config.json`。

批量追踪并下载：WebUI 读取配置中的起始日期，并把 UP 主管理页签“自动追踪下载”列已勾选的全部 UP 组成 `up_ids`；左侧主复选框不参与此功能。随后调用 `POST /api/up/videos/batch-track-download` → `core/video_batch_track_download.py`。该模块后台串行调用 `core/video_sync.py` 的截止日期分页刷新，收集每个 UP 的新视频并更新远端追踪清单；随后从完整视频列表筛选日期不早于起始日期且 `downloaded=false` 的视频（包含之前已登记但尚未下载的视频），交给 `core/video_download.py` 的下载队列。WebUI 通过 `GET /api/up/videos/batch-track-download-progress` 轮询 `tracking`/`downloading` 两阶段状态。下载阶段的 `download_done/download_total` 显示成功完成数/需要下载总数，`download_failed` 单独记录失败数。

视频下载：WebUI → `POST /api/videos/download` → FastAPI videos route → `core/video_download.py` → `core/opencli_videos.py` → `<knowledge_base_root>/SortedMp4/<UP名称>/<YYYYMM>/`。下载用例按 `best`、`720p`、`480p` 顺序重试，依据实际生成的视频文件确认成功；成功后由 core 同步更新 `UpList/<UP名称>.jsonl` 的追踪状态和 `SortedMp4/<UP名称>/videos.jsonl` 的本地文件索引，再更新 `followings.json` 统计。

下载进度：WebUI `download_progress.js` 每秒调用 `GET /api/videos/download-progress`；路由只返回 `core/download_progress.py` 的状态快照。后台任务在 OpenCLI 下载期间监测当前目录的新文件大小，状态记录保留最多 30 分钟，前端展示排队中、下载中、完成和失败。

`<knowledge_base_root>/UpList/followings.json` 是 UP 登记和统计 canonical 数据源；同目录的 `bilibili-up-followings.md` 由 JSON 生成，仅供人工阅读。远端追踪清单独立保存在 `<knowledge_base_root>/UpList/<UP名称>.jsonl`，本地视频索引独立保存在 `<knowledge_base_root>/SortedMp4/<UP名称>/videos.jsonl`，两者不混用，也不混入登记 JSON。

两套 JSONL 不得混用：远端追踪清单保存网站元数据和状态；本地 `videos.jsonl` 只保存硬盘上真实存在的视频文件。视频下载目录按月份分层，文件名为 `<UP名称>_<YYYYMMDD>_<标题>.<扩展名>`。

UP 管理列表沿用参考页面的列结构，并增加可读的 UP 简介列。视频统计由刷新和下载用例回写；字幕、转录和调度不在当前 MVP 中实现。

## 跨平台原则

核心业务模块由 macOS 和 Windows 共用。平台差异仅限 `core/utils/system/`：macOS 使用 Finder/AppleScript 选择目录，Windows 使用 FolderBrowserDialog；两者对上层统一返回 `Path | None`。两端运行同一套测试，并分别原生打包验证。

应用启动时自动选择可用的本地端口并打开 WebUI，避免占用或终止其他程序的端口。打包后的应用不创建虚拟环境；虚拟环境只用于源码开发和构建。

首次运行先通过 `/api/setup-status` 检查知识库配置。配置文件固定保存在 macOS `~/Library/Application Support/BiliUp/config.json` 或 Windows `%LOCALAPPDATA%\BiliUp\config.json`，其中保存用户选择的 `knowledge_base_root` 和 `batch_track_since_date`。未配置时网页不开放搜索和写入。

知识库配置完成后，`/api/runtime-status` 检查 OpenCLI。系统适配层从当前 PATH 以及 Homebrew、npm、NVM、Volta 等平台常见位置发现可执行文件，并为子进程补齐 Node/OpenCLI 所需 PATH；未安装时由 WebUI 展示人工安装、Chrome 扩展和 B 站登录指引。
