# BiliUp MVP 产品需求文档

适用应用版本：`0.2.0`。

## 1. 背景与目标

用户需要在本地快速检索 B 站 UP 主，并把确认后的 UP 主信息登记到用户自行选择的视频知识库中，供后续视频追踪能力使用。

本 MVP 的目标是完成知识库初始化、UP 主信息登记、视频列表刷新与选中视频下载，并通过 Tauri v2 桌面外壳自动管理本机 FastAPI 后端；应用在 macOS 和 Windows 上以相同功能运行。

## 2. 范围

### 包含

1. 首次运行时，用户选择视频知识库目录，系统校验可写并保存配置。
2. 用户输入 UP 主昵称并点击搜索。
3. 后端通过 OpenCLI 搜索 B 站用户。
4. 网页展示候选结果的昵称、UP ID 与简介。
5. 用户一次只能选择一个候选结果并确认写入。
6. 系统创建或更新知识库内的 UpList，并提示结果。
7. 首次运行检测 OpenCLI；未安装或不可运行时展示明确的准备步骤并暂时禁用搜索。
8. “UP 主管理”页签读取当前知识库中的登记记录，并按参考页面展示管理列表。
9. 用户可以刷新已登记 UP 的视频信息列表。
10. 用户可以在第二个页签选择 UP、选择视频并下载到知识库的视频目录。
11. 用户可以填写起始日期，对“自动追踪下载”列已勾选的 UP 执行批量追踪，并自动下载期限内所有尚未下载的视频。
12. “其他功能”页签可以显示当前知识库目录、通过系统目录选择器重新保存目录、打开知识库目录或单视频目录，并下载未纳入 UP 追踪的单个视频。
13. Tauri 桌面应用自动启动和退出 Python sidecar，后端就绪后在窗口中展示现有 FastAPI 页面。
14. 桌面应用保持单实例，支持固定可配置端口，并对端口冲突、配置错误和后端启动失败显示明确错误。
15. 普通 Web 模式和桌面模式共用现有用户配置和知识库数据，不要求迁移或重新选择目录。
16. 批量同步进行时，用户可以立即请求停止，修正 UP 选择后重新开始同步。

### 不包含

- 转录、定时追踪、登录、迁移、云同步和文件整理。
- 头像展示、批量写入、编辑和排序功能。
- 参考工作流中与本 MVP 无关的旧版 Markdown 视频记录。
- 重写业务 UI、把业务迁到 Rust 或开放局域网/远程访问。
- 打包 OpenCLI、Node.js、Chrome 扩展、yt-dlp、FFmpeg/FFprobe。
- 代码签名、公证、SmartScreen 信誉、自动更新和发布 CI。

## 3. 用户流程

1. 用户启动 BiliUp 桌面应用；Tauri 自动启动 Python 后端，健康检查成功后在窗口中打开现有 WebUI。源码开发时仍可独立启动普通 Web 模式。
2. 用户点击“选择视频知识库目录”，在系统原生目录选择器中选择一个已存在、可写的目录。
3. 系统保存配置后显示搜索看板。
4. 系统打开“UP 主管理”页签，读取已登记的 UP 主并按序号、昵称、UP 简介、最后同步时间、已下载/已同步和操作列展示；没有记录时显示空状态。
5. 用户在搜索框输入昵称并点击“搜索”；输入过程不自动调用接口。
6. 系统显示匹配项的昵称、UP ID 与简介；没有结果时显示“未找到匹配的 UP 主”。
7. 用户单选一项并点击确认写入。
8. 系统按 UP ID 写入或更新 UpList，显示“已新增”或“已更新”；失败时显示简短错误信息，不写入半成品数据。
9. 用户在 UP 管理列表中点击行操作或批量刷新，从 OpenCLI 获取该 UP 的视频列表并保存索引。
10. 用户勾选一个或多个 UP，点击“删除”并确认；系统删除登记和视频索引，但保留已下载视频文件。
11. 用户切换到视频下载页签，选择 UP 和视频，点击下载；系统后台执行下载并反馈成功或失败状态。
12. 用户填写起始日期并点击“批量追踪并下载”；系统先逐个刷新“自动追踪下载”列已勾选的全部 UP，再下载其视频列表中日期不早于该日期且 `downloaded=false` 的视频，最后为追踪范围内所有已有本地 MP4 但缺少封面的视频补齐封面，不设补齐数量上限，并持续反馈各阶段进度。
13. 用户关闭桌面窗口；应用先请求后端优雅停止后台任务和子进程，再回收本实例启动的 sidecar。

## 4. 功能需求

### 4.1 搜索

- 搜索输入按去除首尾空白后的昵称处理。
- `POST /api/up-search` 接收昵称，返回 `uid`、`nickname`、`bio`。
- `core` 层通过 OpenCLI 执行用户搜索并标准化结果；网页和 FastAPI 路由不直接执行命令。
- 搜索、视频刷新和视频下载调用 OpenCLI 时使用后台浏览器窗口模式，不抢占用户前台；仍复用用户已登录的 Chrome 会话。
- OpenCLI 无结果、超时或返回不可解析数据时，系统返回可理解的失败信息。
- 已安装 OpenCLI 时，打包应用必须在 Finder/Explorer 启动环境中正确定位它；未安装时不得只返回笼统错误。

### 4.2 首次知识库设置

- `GET /api/setup-status` 返回知识库是否已配置；已配置时返回 `knowledge_base_root`，供“其他功能”页签显示当前目录。
- `POST /api/setup/select-library` 调用当前系统的原生目录选择器；用户取消时不写入配置。
- 所选目录必须已经存在且可写；验证失败时不创建半成品配置。
- 配置文件固定在 macOS `~/Library/Application Support/BiliUp/config.json` 或 Windows `%LOCALAPPDATA%\BiliUp\config.json`。
- 配置中的 `knowledge_base_root` 保存用户选择的绝对路径。它是用户选择的受控例外，不得由业务代码硬编码。
- 同一个配置文件预留并保存 `batch_track_since_date`，用于批量追踪并下载的起始日期；日期使用 `YYYY-MM-DD`，未设置时为空。
- 同一个配置文件保存 `desktop_port`；缺失时使用默认值 `8765`，合法值为整数 `1024–65535`，保存后下次启动生效。“其他功能”的端口设置区域显示该 `config.json` 的完整路径，方便用户定位实际配置文件。
- 普通 Web 和 Tauri 桌面模式共用该配置文件；重新选择知识库或保存其他设置时必须保留已有端口和兼容字段。
- `src-tauri/tauri.conf.json` 是开发构建配置，不保存用户知识库、日期或端口设置。

### 4.3 UP 主管理列表

- `GET /api/followings` 读取当前配置的 `<knowledge_base_root>/UpList/followings.json`，返回按登记顺序排列的列表。
- `POST /api/followings/tracking` 接收 `up_id` 和 `scheduled_tracking`，立即更新对应的 `followings.json` 记录。
- 每行返回 `up_id`、`nickname`、`bio`、`scheduled_tracking`、`last_sync_time`、`total_count`、`synced_count` 和 `downloaded_count`；表格展示昵称、简介、自动追踪下载、时间和已下载/已同步列，`up_id` 用于后续视频接口。
- 页面列顺序为：选择框、序号、UP 名称、UP 简介、自动追踪下载、最后同步时间、已下载/已同步、操作。
- 表头总复选框与每行选择框双向联动；部分行选中时显示半选状态。批量同步只处理当前勾选的 UP。
- `followings.json` 中没有视频统计字段时，统计列显示为 `0 / 0`，最后同步时间显示为 `-`。
- 自动追踪下载开关变更后立即保存到当前知识库的 `UpList/followings.json`；批量追踪并下载只处理管理列表中 `scheduled_tracking=true`（即“自动追踪下载”列已勾选）的全部 UP，不要求左侧主复选框。
- 列表读取失败时不修改本地数据，页面显示可理解的错误信息。
- 行同步与批量同步均在后台执行；行同步每次继续该 UP 的下一页，批量同步只处理当前勾选的 UP。两者均按 BV 号增量合并新视频、保留已有下载状态。
- 删除按钮只对当前勾选的 UP 生效；确认后移除 `followings.json` 登记和对应 `UpList/<UP名称>.jsonl` 远端追踪清单，不删除 `SortedMp4/<UP名称>/videos.jsonl` 与实际视频文件。
- 批量同步按钮默认可用；未勾选时点击后显示提示。任务执行期间显示“同步中…”并置灰批量同步按钮和所有行同步按钮，同时显示“停止同步”按钮。用户停止后，系统中断当前同步使用的 OpenCLI 查询，不再处理剩余 UP；已经完成并写入的视频索引保留，不回滚、不删除文件。停止完成后恢复选择和同步按钮，用户可以修改勾选项并重新启动。

### 4.4 视频列表刷新

- `POST /api/up/{up_id}/videos/refresh` 读取该 UP 保存的下一页游标，按时间倒序调用 `opencli bilibili user-videos <uid> -f json --limit 30 --page <n>`；每次只读取一页、最多新增 30 条。该页不足 30 条时，下一页游标回到第一页。
- 视频按 BV 号与本地索引增量去重后合并到 `<knowledge_base_root>/UpList/<UP名称>.jsonl`，保留已有下载状态。
- `GET /api/up/{up_id}/videos` 返回远端追踪清单，并用本地视频索引校准下载、字幕和封面状态；列表按发布时间倒序，提供序号、日期、标题、BV 号、链接和本地媒体状态。
- 刷新成功后更新 `followings.json` 的 `total_count`、`synced_count`、`downloaded_count` 和 `last_sync_at`。
- OpenCLI 不可用、超时或数据不可解析时不破坏已有视频索引，并返回可理解的错误。
- 单个 UP 刷新与 `POST /api/up/videos/batch-refresh` 均复用后台同步任务；单个刷新每次只追加一页（每页 30 条、最多新增 30 条），成功后保存下一页游标；到达末页后游标回到第一页，后者接收选中的 `up_ids` 并执行普通增量同步。`POST /api/up/videos/batch-refresh-cancel` 请求停止当前任务，`GET /api/up/videos/batch-refresh-progress` 返回完成数、当前 UP、当前页/页数上限、新增数、失败数以及停止状态；停止、完成或失败后页面恢复按钮。

### 4.5 视频下载

- `POST /api/videos/download` 接收 `up_id` 和一个或多个 `bvids`，后台提交下载任务。
- 下载调用 `opencli bilibili download <bvid> --output <知识库目录>/SortedMp4/<UP名称>/<YYYYMM>/`。
- 下载依赖用户单独安装的 `yt-dlp`。为节省存储空间，后台按 `480p`、`720p`、`1080p`、`best` 从低到高尝试，优先采用可下载的低分辨率档位；前一档不可用时自动升级，最后以 `best` 兼容没有常见分辨率档位的视频。OpenCLI 返回失败状态时显示其简要错误，若实际生成有效视频文件则仍按成功处理。
- 下载任务通过 `GET /api/videos/download-progress` 查询状态；成功后更新远端追踪清单的下载状态，并在本地 `SortedMp4/<UP名称>/videos.jsonl` 登记相对文件路径、大小和扫描时间。
- 第二个页签实时轮询并展示下载汇总和任务列表，至少显示视频标题、排队中/下载中/完成/失败状态；下载过程中显示已发现的文件大小，失败项显示错误提示。
- `GET/PUT /api/settings/batch-track` 读写应用 `config.json` 中的 `batch_track_since_date`。视频下载页打开时读取该值，用户选择日期后立即保存。
- “批量追踪并下载”接收前端根据管理列表“自动追踪下载”列生成的 `up_ids`；左侧主复选框只用于批量同步和删除，不参与此功能。追踪起始日期从应用配置读取（仍兼容请求中的 `since_date` 字段）。日期支持 `YYYY-MM-DD`，按自然日包含当天；先按 B 站发布时间倒序分页刷新，再从每个 UP 的完整视频列表中筛选日期不早于起始日期且 `downloaded=false` 的视频，已登记但尚未下载的视频也必须提交下载，不能只处理本轮新增视频。
- 批量任务分为 `tracking`、`downloading` 和 `covering` 三阶段。封面阶段只处理追踪起始日期之后、MP4 已存在且 `cover=false` 的视频，逐条复用统一封面下载接口，不重新下载 MP4，也不限制单次补齐数量；状态接口和界面分别显示下载与封面补齐进度。
- 批量任务运行时显示“停止追踪下载”按钮。`POST /api/up/videos/batch-track-download-cancel` 请求停止当前批量任务：正在执行的追踪查询或该批次拥有的视频下载会被中断，尚未开始的 UP、字幕、下载和封面任务不再提交；此前已经完成的索引与落盘文件保留。该停止信号只属于本次批量任务，不影响用户手动提交的下载。
- 下载进度记录在后台保留最多 30 分钟，前端允许隐藏进度面板；隐藏不会停止后台下载。
- 同一 UP 的下载文件按 `<UP名称>_<日期>_<标题>.<扩展名>` 保存；文件名中的跨平台非法字符统一替换。
- OpenCLI/yt-dlp 在同一次下载中遗留的 JPG/JPEG/WEBP 封面或 M4A 音频附件，若文件名含该视频 BV 号，则先按视频主名规范化。若没有可用封面，core 从 `bilibili video` 元数据读取 `thumbnail`，通过受限的 B 站图片 CDN 镜像下载，并根据实际图片格式原子保存为 `<视频主名>_cover.jpg` 或 `<视频主名>_cover.webp`；封面获取失败不影响视频下载。
- UP 视频列表中选择下载与“其他功能”的单视频下载均在视频落盘后调用同一字幕查询与 sidecar 写入接口；OpenCLI 字幕查询短暂失败时自动重试一次，仍失败不影响视频下载主流程。
- 下载失败不修改已下载标记；不实现语音转录或重新编码。

### 4.6 UP 删除

- `POST /api/followings/delete` 接收 `up_ids`，删除选中的 UP 登记。
- 删除同时移除对应的 `<knowledge_base_root>/UpList/<UP名称>.jsonl` 远端追踪清单，并重建 `bilibili-up-followings.md`；本地视频库索引和实际文件保留。
- 删除不触碰 `<knowledge_base_root>/SortedMp4/<UP名称>/` 下的实际视频文件。
- 前端删除前必须显示确认提示；删除期间按钮不可重复提交。

### 4.7 选择与确认

- 搜索结果只能单选。
- 未选择结果时，确认按钮不可写入。
- 用户确认后，前端发送选定的 `uid`、`nickname`、`bio` 到 `POST /api/followings`。

- `POST /api/followings` 写入登记后立即执行一次首批视频刷新；成功时响应包含 `video_sync.video_count`，前端显示初始视频数。OpenCLI 首次刷新失败不回滚登记，响应包含可重试的 `video_sync.message`。

### 4.8 本地写入

数据根目录为配置的 `knowledge_base_root`；当前 UP 数据相对该根目录保存到 `UpList/`。

- `<knowledge_base_root>/UpList/followings.json` 是唯一真源，为按添加顺序保存的 JSON 数组。
- 每条记录包含：`uid`、`nickname`、`bio`、`scheduled_tracking`、`created_at`、`last_sync_at`、`total_count`、`synced_count`、`downloaded_count`。
- `uid` 是唯一键。新 UID 追加记录；已有 UID 仅更新昵称和简介，保留原 `created_at`。
- 空简介保存为 `-`。新记录的 `scheduled_tracking` 为 `true`；`created_at` 与 `last_sync_at` 使用当前带时区的 ISO-8601 时间，以兼容参考格式。
- 写入使用独占锁与原子替换，确保失败不会破坏已有 JSON。
- 写入 JSON 成功后，重建 `<knowledge_base_root>/UpList/bilibili-up-followings.md`：表头固定为“序号、昵称、UP ID、简介”，序号从 1 连续递增。Markdown 只是派生视图，不能作为写入源。
- 远端视频追踪清单使用 `<knowledge_base_root>/UpList/<UP名称>.jsonl`，每行包含 `date`、`title`、`bvid`、`url`、`downloaded`、`transcript`、`cover`、`local_filename` 和 `index`。
- 本地视频库使用 `<knowledge_base_root>/SortedMp4/<UP名称>/videos.jsonl`，只有真实存在且大小大于零的视频才写入，每行包含 `bvid`、`date`（YYYYMMDD）、`title`、`relative_path`、`original_filename`、`size_bytes`、`transcript`、`cover`、`scanned_at` 和 `index`。`cover` 根据视频旁的 `_cover` 图片或旧 BV 命名封面文件扫描更新。
- 视频文件写入 `<knowledge_base_root>/SortedMp4/<UP名称>/<YYYYMM>/`，文件名为 `<UP名称>_<YYYYMMDD>_<标题>.<扩展名>`；`relative_path` 始终相对知识库根目录。

### 4.9 其他功能

- “其他功能”页签打开时通过 `GET /api/setup-status` 显示当前 `knowledge_base_root`。
- “选择并保存位置”复用首次设置的系统目录选择器和配置写入流程；用户取消选择时不修改配置。打开目录按钮分别调用 `POST /api/library/open-folder` 和 `POST /api/single-video/open-folder`，由系统适配层使用 Finder 或 Explorer 打开目录。
- 单视频下载调用 `POST /api/single-video/download`，输入支持 B 站完整链接、`b23.tv` 短链接、BV 号、抖音分享文本、抖音短链接和正式视频链接。B 站通过 `bilibili video` 获取元数据并沿用现有字幕/封面流程；抖音通过 yt-dlp 获取元数据和视频，元数据中的 `cover` 保存为 `<视频主名>_cover.<扩展名>` 网站竖版封面。抖音目前不向外部提供作者上传的独立横版封面，`origin_cover` 实际可能是视频画面截图，因此项目不下载或生成横版封面。已有抖音视频重新提交时只刷新竖版封面，不重复下载视频；公开访问失败时使用本机 Chrome Cookie 重试，不请求字幕。
- 单视频文件保存到 `<knowledge_base_root>/OtherVideos/`，其本地索引保存到 `<knowledge_base_root>/OtherVideos/videos.jsonl`，以 `platform` 和 `video_id` 区分来源；B 站记录继续保存 `bvid`。单视频不写入 `UpList`，不加入 UP 自动追踪，下载进度仍通过 `GET /api/videos/download-progress` 查询。

### 4.10 Tauri 桌面运行

- Tauri v2 只负责窗口、单实例、端口检查、Python sidecar 启动、身份健康检查、错误展示和退出回收；
- Tauri 启动时先显示本地加载页，`GET /api/health` 返回稳定 BiliUp 身份后导航到 `http://127.0.0.1:<port>/`；
- Tauri 不建立第二套业务 UI，Python sidecar 复用现有 FastAPI app、静态页面、路由和 `core`；
- 第二次启动只显示、还原并聚焦已有窗口，不创建第二个 sidecar；单实例判断独立于端口；
- 端口不可绑定、配置损坏或健康检查超时时，窗口显示明确错误和配置路径，不自动切换端口、不连接未知服务、不修改用户配置；若固定端口由可确认身份的旧 BiliUp 后端占用，先请求其优雅退出并等待释放，超时后仅在健康响应、PID 和可执行文件身份均匹配 BiliUp 时强制结束旧进程。若占用者是其他应用或身份无法确认，显示应用名称、PID 和路径并拒绝终止；
- 桌面模式的 `POST`、`PUT`、`PATCH`、`DELETE /api/*` 必须包含 `X-BiliUp-Client: desktop`；该公开标记不是密码或 token；
- 不开放通配 CORS，localhost 页面不获得 Tauri shell 或文件系统权限；
- 退出时先调用受保护的后端关闭接口，取消本实例持有的下载和子进程，再由 Tauri 对仍存活的本实例 sidecar 兜底回收；
- `<knowledge_base_root>/UpList`、`SortedMp4` 和 `OtherVideos` 保持现有位置，Tauri/Rust 不读写 JSONL 或视频索引；
- 普通 Web 模式继续独立运行，不强制采用 Tauri 单实例或桌面关闭协议。

## 5. 非功能需求

- 三层调用方向固定为：静态网页层 → FastAPI 路由层 → `core` 业务内核层。
- 所有文件操作使用 `pathlib`。项目内部路径使用项目相对路径；用户选择的 `knowledge_base_root` 是配置中唯一允许保存的绝对路径。
- Windows/macOS 差异仅在 `core/utils/system/` 中处理；核心功能与测试代码必须共用。
- 服务仅监听 `127.0.0.1` 或 `localhost`。
- 桌面服务默认监听 `127.0.0.1:8765`，允许配置端口但不允许自动随机切换；单实例由 Tauri 保证。主应用已退出但旧 BiliUp 后端残留时允许安全接管端口；未知应用占用仍作为资源错误处理。
- Tauri 是三层业务架构之外的外壳；Rust 不接管业务、配置写入、JSONL 或下载逻辑。
- 桌面模式修改类 API 校验公开客户端标记，不开放通配 CORS；该标记不作为本机认证或秘密。
- 日志不得记录凭据、Cookie、令牌或完整 OpenCLI 原始输出。

## 6. 验收标准

1. 未配置时只能选择知识库目录；取消选择或不可写目录不生成配置。
2. 配置成功后，`UpList` 只写入用户选择的知识库目录，不写入安装包或启动目录。
3. 已登记的 UP 主能在“UP 主管理”页签按参考页面列结构显示；无记录时显示空状态。
4. 输入昵称后，用户能看到包含昵称、UP ID、简介的搜索结果或无结果提示。
5. 不选择结果时不能写入；选择一项并确认后产生明确成功或失败反馈。
6. 首次写入创建正确的 JSON 记录和 Markdown 表，并立即完成首批视频同步；相同 UID 再次写入不会产生重复记录。
7. 刷新已登记 UP 后，`UpList/<UP名称>.jsonl` 远端追踪清单产生或更新；已有本地视频同步补建到 `SortedMp4/<UP名称>/videos.jsonl`，列表统计同步更新。
8. 第二个页签能读取本地视频索引、单选或多选视频并提交下载任务。
9. 下载成功后视频文件位于知识库的 `SortedMp4/<UP名称>/<YYYYMM>/`，列表显示已下载。
10. 下载期间第二个页签能够实时显示任务标题、当前状态和已下载大小；任务完成、停止或失败后仍显示结果，直至记录过期或用户隐藏。
11. 填写起始日期并执行批量追踪后，系统刷新自动追踪 UP 的视频列表，筛选不早于该日期且尚未下载的视频并自动提交下载任务；页面能显示追踪阶段和下载阶段的进度，支持停止当前批量任务且不影响手动下载，完成或停止后刷新视频列表与 UP 统计。
12. 删除选中的 UP 后，登记和 `UpList/<UP名称>.jsonl` 远端追踪清单消失；`SortedMp4/<UP名称>/videos.jsonl` 与实际视频文件仍存在。
13. `followings.json` 或视频索引写入失败时，原文件仍可读取且内容未损坏。
14. macOS 与 Windows 均通过相同自动化测试；涉及启动或打包的改动在两个系统分别验证。
15. 未安装 OpenCLI 时首页显示安装、Chrome 扩展和 B 站登录指引；安装完成后无需修改业务代码即可被识别。
16. 字幕接口返回有效内容时生成相邻的 `__transcript.md` 并更新索引；接口失败不得影响视频下载，已有 sidecar 可继续被本地索引识别。
17. Tauri 启动后自动进入现有 UI，无需用户手动启动后端；普通 Web 模式仍可独立运行。
18. 旧用户配置可直接复用，`desktop_port` 默认值、边界值、错误类型、保存和重启提示均通过测试，重新选择知识库不丢失兼容字段。
19. 桌面模式修改请求无头或错误头返回 `403`，正确请求正常处理；GET 和普通 Web 模式保持兼容。
20. 正常启动、第二次启动、旧 BiliUp 后端残留自动恢复、健康超时、配置损坏、端口冲突和未知服务占用均有明确且安全的行为；未知服务不得被终止。
21. 关闭窗口后端口释放，无遗留 sidecar 或本实例创建的后台进程。
22. macOS 和 Windows 分别在原生系统构建安装包，并完成新配置、已有配置两种启动冒烟测试。

## 7. 参考边界

参考工作流说明了 UP 主视频列表、删除登记、下载和字幕 sidecar 的行为边界。本 PRD 保留字幕查询/写入接口，不采用语音转录、调度、迁移和旧版 Markdown 视频记录流程。
