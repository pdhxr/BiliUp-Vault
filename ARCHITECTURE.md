# BiliUp 架构

适用应用版本：`0.2.0`。

## 总体架构

桌面版采用“Tauri 外壳 + Python sidecar + 原有 FastAPI 页面”的结构。Tauri 只负责桌面窗口、单实例、端口和 Python sidecar 生命周期，不重写业务 UI，也不接管 Python 业务或数据写入。

```text
Tauri 主进程
  ├─ 单实例、端口检查、窗口和错误页
  ├─ 启动、健康检查和回收 Python sidecar
  └─ 后端就绪后导航到 http://127.0.0.1:<port>/
                                      │
                                      ▼
                    app/static → app/routes → core → repositories
```

详细需求见 [PRD.md](PRD.md)，实施顺序和逐阶段验证见 [TAURI_DEVELOPMENT_PLAN.md](TAURI_DEVELOPMENT_PLAN.md)。

## 三层架构

系统按单向依赖组织：静态网页层 → FastAPI 路由层 → `core` 业务内核层。

- `src-tauri/`：Tauri v2 桌面外壳；负责窗口、单实例、端口校验、sidecar 生命周期和安装包配置，不读写业务数据。
- `desktop/`：后端就绪前使用的本地加载/错误页及图标源，不建立第二套业务 UI；`desktop/icons/biliup-icon.png` 是桌面应用图标母版。
- `packaging/build_sidecar.py`：使用 PyInstaller 构建当前平台的 Python sidecar，并生成 Tauri external binary 目标命名。
- `tools/desktop_entry.py`：桌面专用 Uvicorn 入口；接收端口和应用配置目录，设置桌面运行环境并复用 `create_app()`。
- `app/main.py`：FastAPI 应用工厂和普通 Web 开发入口；Web 模式负责打开浏览器，桌面模式不经过该浏览器启动流程。
- `app/static/`：静态网页；只调用本机 API 并展示结果。
- `app/static/js/up_search.js`：UP 搜索、结果单选和确认写入交互；不直接读写本地文件或执行 OpenCLI。
- `app/static/js/up_management.js`：UP 管理列表读取、选择联动和删除确认；不直接读写本地文件。
- `app/static/js/video_download.js`：视频列表选择、刷新和下载提交；不直接读写本地文件，也不负责进度展示。
- `app/static/js/download_progress.js`：独立轮询下载状态，展示汇总状态、任务标题、任务状态和已下载大小；下载完成后通知视频列表刷新。
- `app/static/js/other_features.js`：其他功能页签的目录显示/选择、目录打开、单视频下载提交和进度轮询；不直接读写本地文件或执行 OpenCLI。
- `app/routes/`：FastAPI 路由；只负责 HTTP 输入/输出与调用 `core`。
- `core/`：配置、首次设置、搜索、UP 主登记、UP 管理列表、OpenCLI 适配和 UpList 数据读写；不得依赖 FastAPI 或前端。
- `core/configuration.py`：读写用户知识库根目录、批量追踪起始日期和桌面端口配置，并校验已配置目录可写；更新单个字段时保留其他兼容字段。
- `core/setup.py`：编排首次目录选择、配置保存和批量追踪设置读取/保存；设置状态接口返回当前 `knowledge_base_root` 供“其他功能”页签展示。
- `core/up_management.py`：编排当前知识库 UP 管理列表读取。
- `core/following_delete.py`：删除选中的 UP 登记和视频索引，不删除实际视频文件。
- `core/repositories/followings.py`：保存登记记录、自动追踪下载开关并将其转换为 UP 管理列表行，不包含 HTTP 或前端逻辑。
- `core/opencli_videos.py`：封装 OpenCLI 用户视频查询和视频下载命令，并标准化输出；浏览器型调用统一使用后台窗口模式。
- `core/douyin_videos.py`：从抖音分享文本提取链接和作者，通过 yt-dlp 读取单视频元数据并下载视频；静态 `cover` 保存为网站竖版封面，仅允许受限抖音图片域名。抖音目前不向外部提供作者上传的独立横版封面，`origin_cover` 实际可能是视频画面截图，因此不作为封面保存。公开访问失败时复用本机 Chrome Cookie 重试，不请求字幕。
- `core/video_sync.py`：刷新 UP 视频列表并回写视频统计。
- `core/followings.py`：登记 UP；确认登记后编排一次首批视频刷新。
- `core/video_reconcile.py`：协调远端追踪清单与本地视频库状态。
- `core/video_index.py`：按网站元数据扫描已有月度视频文件，补建本地 `videos.jsonl`。
- `core/video_batch_sync.py`：管理选中 UP 的后台批量增量同步和进度快照。
- `core/video_batch_track_download.py`：从应用配置读取起始日期，接收前端按“自动追踪下载”列筛出的 UP，编排按日期批量追踪、下载与封面补齐；刷新后从每个 UP 的完整视频列表筛选期限内未下载的视频，交给下载队列，并提供三阶段进度快照。
- `core/video_download.py`：后台下载队列、文件命名和索引更新；通过进度模块更新任务状态。
- `core/single_video_download.py`：识别 B 站或抖音单视频来源并分派到对应适配器，复用文件发现、命名、进度和本地索引组件；结果写入 `OtherVideos`，不创建作者追踪记录。
- `core/subtitle_download.py`：调用 OpenCLI 获取字幕、写入 `__transcript.md` sidecar，并同步远端追踪清单和本地视频索引；单次 OpenCLI 错误自动重试一次，仍失败不阻断视频下载。
- `core/cover_download.py`：从标准化视频元数据取得封面 URL，只允许 B 站图片 CDN，按镜像重试、校验图片内容并原子写入 `<视频主名>_cover.<扩展名>`；失败不阻断视频下载。
- `core/video_cover_backfill.py`：筛选追踪起始日期之后已下载但缺少封面的 UP 视频，复用 `core/cover_download.py` 的统一接口逐一补齐，并刷新本地与远端索引；不设数量上限，不重新下载视频。
- `core/download_files.py`：识别 OpenCLI 生成的视频文件、清理 `.part` 临时文件、执行跨平台安全命名，并在新下载 MP4 重命名后探测首个视频轨道，仅将 `codec_name=hevc` 且 `codec_tag_string=hev1` 的文件无损重封装为 `hvc1` 标签；不包含 HTTP 或 OpenCLI 调用。
- `core/download_progress.py`：下载状态存储、过期记录清理和下载目录大小监测，不包含 OpenCLI 或 HTTP 逻辑。
- `core/repositories/videos.py`：读写 `<knowledge_base_root>/UpList/<UP名称>.jsonl` 远端追踪清单。
- `core/repositories/library.py`：读写 `<knowledge_base_root>/SortedMp4/<UP名称>/videos.jsonl` 和 `<knowledge_base_root>/OtherVideos/videos.jsonl` 本地视频库索引；持久化格式与参考项目一致。
- `core/utils/system/`：唯一的 macOS/Windows 平台适配边界，提供统一的浏览器、子进程、目录选择、目录打开、应用配置目录、运行资源和退出清理接口。
- `core/version.py`：应用版本的唯一来源；FastAPI 元数据和安装包名称从此读取。
- `package.json`：提供 `desktop:dev`、`sidecar:build` 和 `desktop:build` 统一命令。
- `src-tauri/tauri.conf.json`：开发者构建配置，记录应用身份、窗口、bundle、各平台图标和 sidecar；`src-tauri/icons/` 中的尺寸资源由图标母版生成，不保存用户设置。

## 数据流

桌面启动：Tauri 单实例检查 → 解析现有 BiliUp 应用配置目录 → 读取并校验 `desktop_port` → 启动 `tools/desktop_entry.py` sidecar → `core/utils/system/network.py` 检查端口占用者。确认是旧 BiliUp 时先请求优雅关闭，超时后再次核对健康响应、PID 和可执行文件身份，全部匹配才强制结束；其他应用只返回名称、PID 和路径。新 sidecar 绑定端口后，Tauri 轮询 `/api/health`，且只接受本次启动生成的实例标识，再导航到现有 FastAPI 页面。失败时停止本实例 sidecar 并在窗口显示错误，不连接或结束未知服务。

桌面退出：Tauri 使用公开桌面请求头调用后端关闭接口 → FastAPI 取消本实例持有的后台任务和子进程 → Uvicorn 退出 → Tauri 对仍存活的本实例 sidecar 兜底回收。若该流程异常留下后端，下一次启动通过受控的端口恢复流程清理；未知进程永不终止。

首次设置：WebUI → FastAPI setup route → `core/setup.py` → 系统目录选择器 / 配置文件。打开“其他功能”页签时，WebUI 通过 `GET /api/setup-status` 读取并显示已配置的知识库目录，不修改配置。

其他功能：WebUI → `app/static/js/other_features.js` → setup/videos 路由。目录按钮调用 `core/utils/system/directories.py` 的统一目录选择/打开接口；单视频下载由 videos route 调用 `core/single_video_download.py` 识别平台。B 站走 `core/opencli_videos.py` 并尝试字幕和封面，抖音走 `core/douyin_videos.py` 下载视频和封面但不请求字幕；两者复用文件发现、命名、进度和 `OtherVideos/videos.jsonl`。

登记：WebUI → FastAPI UP route → `core/followings.py` → `<knowledge_base_root>/UpList` repository → `core/video_sync.py` 首批刷新 → 两套视频索引协调。登记成功但首批刷新失败时保留登记，并把可重试错误返回给前端。

删除：WebUI → `POST /api/followings/delete` → FastAPI UP route → `core/following_delete.py` → followings repository 与远端追踪 repository；删除登记和 `UpList/<UP名称>.jsonl`，保留 `SortedMp4/<UP名称>/videos.jsonl` 及实际视频文件。

列表：WebUI → `GET /api/followings` → FastAPI UP route → `core/up_management.py` → UpList repository；读取失败只返回错误，不写入数据。

视频刷新：WebUI → `POST /api/up/{up_id}/videos/refresh` → FastAPI videos route → `core/video_batch_sync.py` → `core/video_sync.py` → `core/opencli_videos.py`。接口立即启动后台任务，WebUI 复用批量同步进度接口显示“同步中”。单个 UP 的手动刷新每次读取一页 30 条视频，最多新增 30 条；成功后将 `followings.json` 内部的下一页游标向后推进，到达末页后回到第一页。按 BV 号排除远端追踪清单已有记录后写入 `UpList/<UP名称>.jsonl`。刷新后按元数据扫描已有月度视频文件补建本地 `videos.jsonl`，再用本地索引校准远端下载状态。

批量刷新：WebUI → `POST /api/up/videos/batch-refresh` → `core/video_batch_sync.py` 后台串行处理选中的 UP；每个 UP 复用普通增量同步用例，避免一次批量操作长时间占用 OpenCLI。WebUI 通过 `GET /api/up/videos/batch-refresh-progress` 轮询 UP 数量、当前页、停止状态和失败信息；用户点击停止时调用 `POST /api/up/videos/batch-refresh-cancel`，取消信号沿 `video_batch_sync.py` → `video_sync.py` → `opencli_videos.py` 传到 `core/utils/system/process.py`，只终止当前同步查询的子进程并保留此前已完成结果。

自动追踪设置：WebUI → `POST /api/followings/tracking` → `core/followings.py` → `UpList/followings.json`，保存每个 UP 的 `scheduled_tracking` 开关。批量日期设置：WebUI → `GET/PUT /api/settings/batch-track` → `core/setup.py` → `core/configuration.py`，保存到与知识库目录相同的应用 `config.json`。

批量追踪并下载：WebUI 读取配置中的起始日期，并把 UP 主管理页签“自动追踪下载”列已勾选的全部 UP 组成 `up_ids`；左侧主复选框不参与此功能。随后调用 `POST /api/up/videos/batch-track-download` → `core/video_batch_track_download.py`。该模块后台串行调用 `core/video_sync.py` 的截止日期分页刷新，收集每个 UP 的新视频并更新远端追踪清单；随后从完整视频列表筛选日期不早于起始日期且 `downloaded=false` 的视频（包含之前已登记但尚未下载的视频），交给 `core/video_download.py` 的下载队列。下载结束后，`core/video_cover_backfill.py` 对期限内所有已下载但缺少封面的本地 MP4 逐一调用既有封面接口，不设数量上限。WebUI 轮询 `tracking`、`downloading`、`covering` 三阶段状态及各自进度。用户停止时调用 `POST /api/up/videos/batch-track-download-cancel`；批次专属 `Event` 沿追踪和该批次下载调用链传递到受管子进程，只取消本批次正在执行或排队的视频任务，并阻止后续字幕、下载和封面任务提交，手动下载不共享该信号。

视频下载：WebUI → `POST /api/videos/download` → FastAPI videos route → `core/video_download.py` → `core/opencli_videos.py` → `<knowledge_base_root>/SortedMp4/<UP名称>/<YYYYMM>/`。UP 视频与 B 站单视频下载共用 `core/opencli_videos.py` 定义的 `480p`、`720p`、`1080p`、`best` 低到高回退顺序，优先节省存储，并依据实际生成的视频文件确认成功；`core/download_files.py` 先规范化 OpenCLI 遗留附件，再用 FFprobe 检查新下载 MP4，仅对 HEVC `hev1` 文件使用 FFmpeg `-c copy -tag:v hvc1` 无损重封装，`core/cover_download.py` 随后按需补查元数据并从受限 CDN 下载封面。接着由 `core/subtitle_download.py` 尝试查询并写入相邻 `__transcript.md`，再由 core 同步更新两套视频索引和 `followings.json`。兼容探测或修复、封面或字幕失败不改变视频任务的成功状态。

单视频下载：WebUI → `POST /api/single-video/download` → `core/single_video_download.py` → B 站 `core/opencli_videos.py` 或抖音 `core/douyin_videos.py` → `<knowledge_base_root>/OtherVideos/`。任务不写入 `UpList`；同一平台和视频 ID 已有有效文件时不重复下载。B 站尝试补充官方字幕和封面；抖音由 yt-dlp 下载视频并保存网站竖版 `cover`，不下载平台未对外提供的作者横版封面；已有视频会只刷新竖版封面而不重复下载，`transcript=false`。

媒体状态：视频刷新扫描 `SortedMp4/<UP名称>/<YYYYMM>/` 中已有的 `__transcript.md` 和封面图片，更新本地索引的 `transcript`、`cover`；再由协调层回写给视频列表。批量追踪也会为已下载但缺少字幕 sidecar 的视频保留补拉接口。

下载进度：WebUI `download_progress.js` 每秒调用 `GET /api/videos/download-progress`；路由只返回 `core/download_progress.py` 的状态快照。后台任务在 OpenCLI 下载期间监测当前目录的新文件大小，状态记录保留最多 30 分钟，前端展示排队中、下载中、完成、已停止和失败。

`<knowledge_base_root>/UpList/followings.json` 是 UP 登记和统计 canonical 数据源；同目录的 `bilibili-up-followings.md` 由 JSON 生成，仅供人工阅读。远端追踪清单独立保存在 `<knowledge_base_root>/UpList/<UP名称>.jsonl`，本地视频索引独立保存在 `<knowledge_base_root>/SortedMp4/<UP名称>/videos.jsonl`，两者不混用，也不混入登记 JSON。

两套 JSONL 不得混用：远端追踪清单保存网站元数据和状态；本地 `videos.jsonl` 只保存硬盘上真实存在的视频文件。视频下载目录按月份分层，文件名为 `<UP名称>_<YYYYMMDD>_<标题>.<扩展名>`。

单视频下载的 `OtherVideos/videos.jsonl` 仍是本地文件索引，但不属于任何 UP 的远端追踪清单；其文件直接保存在 `OtherVideos/`，文件名沿用统一的 `<作者>_<YYYYMMDD>_<标题>.<扩展名>` 规则。

UP 管理列表沿用参考页面的列结构，并增加可读的 UP 简介列。视频统计由刷新和下载用例回写；视频下载页的字幕状态列来自本地 sidecar。语音转录和调度不在当前 MVP 中实现。

## 跨平台原则

核心业务模块由 macOS 和 Windows 共用。平台差异仅限 `core/utils/system/`：macOS 使用 Finder/AppleScript 选择目录，Windows 使用 FolderBrowserDialog；两者对上层统一返回 `Path | None`。单页同步游标与字幕 sidecar 只使用 `Path`、JSON、线程和统一的 OpenCLI 进程适配，不含 macOS 专有调用；两端运行同一套测试，并分别原生打包验证。

服务只监听 `127.0.0.1`。桌面端口默认 `8765`，允许用户在 `1024–65535` 范围内配置并在下次启动生效。Tauri 单实例独立于端口判断；端口冲突时不自动切换。仅可确认的旧 BiliUp 后端允许先优雅关闭、再按需强制回收；其他占用者只报告身份，不连接、不结束。打包后的应用不创建虚拟环境；虚拟环境只用于源码开发和构建。

首次运行先通过 `/api/setup-status` 检查知识库配置。普通 Web 和桌面模式共用同一用户配置：macOS `~/Library/Application Support/BiliUp/config.json`，Windows `%LOCALAPPDATA%\BiliUp\config.json`。其中保存 `knowledge_base_root`、`batch_track_since_date` 和 `desktop_port`；`GET/PUT /api/settings/desktop` 同时返回该配置文件的完整路径，供“其他功能”页签展示。旧配置缺少端口时读取默认值但不自动改写。未配置知识库时网页不开放搜索和业务写入。

知识库配置完成后，`/api/runtime-status` 检查 OpenCLI。OpenCLI 是安装包外的系统级 npm 依赖，当前兼容验证版本为 `1.8.6`；系统适配层从当前 PATH 以及 Homebrew、npm、NVM、Volta 等平台常见位置发现可执行文件，并为子进程补齐 Node/OpenCLI 所需 PATH。未安装时由 WebUI 展示人工安装、升级、Chrome 扩展和 B 站登录指引。

## 桌面安全边界

桌面模式的 `POST`、`PUT`、`PATCH`、`DELETE /api/*` 请求必须包含公开标记 `X-BiliUp-Client: desktop`，前端所有 API 调用通过统一方法添加。该标记用于配合浏览器 CORS 预检降低外部网页调用 localhost 修改接口的风险，不是密码、token 或本机程序认证。Tauri 每次启动另生成临时实例标识并要求 `/api/health` 原样返回，仅用于区分新旧 sidecar，不保存到用户配置。

不开放通配 CORS，不反射任意 Origin。localhost 业务页面只使用 HTTP API，不获得 Tauri shell 或文件系统 capability。`GET /api/health` 返回稳定 BiliUp 身份；桌面关闭接口仅在桌面模式启用并受修改请求头规则保护。

用户配置与业务数据保持分离：`config.json` 位于现有 BiliUp 应用配置目录，`UpList`、`SortedMp4` 和 `OtherVideos` 位于 `knowledge_base_root`。Tauri 默认应用数据目录若受 bundle identifier 影响而不同，必须显式使用现有 BiliUp 配置目录，不复制或迁移配置；Rust 不直接写用户配置中的业务字段或任何 JSONL。
