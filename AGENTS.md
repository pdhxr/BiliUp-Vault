# BiliUp 项目规范

本文件补充全局 `AGENTS.md`；冲突时以全局规则为准。

## 全局准则

- MVP 实现：OpenCLI 搜索 B 站 UP 主 → 展示昵称、UP ID、简介 → 用户单选确认 → 写入本地 UpList；支持刷新已登记 UP 的视频列表、配置 UP 自动追踪下载和批量增量追踪下载；“其他功能”页签支持知识库目录操作和未纳入追踪的单视频下载。
- 采用三层单向架构：静态网页层 → FastAPI 路由层 → `core` 业务内核层。禁止反向导入或跨层耦合。
- 所有文件路径使用 `pathlib`。项目内部路径使用项目根目录下的相对路径；禁止硬编码路径。用户首次选择的 `knowledge_base_root` 是配置中唯一允许保存的绝对路径，由 `core/utils/system/` 发现应用配置目录后统一读取。
- Windows/macOS 差异代码只能放在 `core/utils/system/`，以统一函数接口屏蔽平台差异。其他模块不得判断系统类型、调用 shell 或使用系统专有 API。
- OpenCLI 仅能由 `core` 内的适配模块调用；路由、网页与数据写入器不得执行 CLI 命令。
- 不添加转录、调度、登录、迁移、云同步、批量写入和文件整理等非 MVP 功能；视频下载后的字幕脚本、封面图片获取与状态判断属于当前 MVP；UP 管理列表删除只移除登记与视频索引，不删除已下载视频文件。

### 原项目参考规则

- 开发具体功能时，只读参考 `/Users/juliehou/Movies/Up/tools/server.py` 的既有行为，重点核对 OpenCLI 命令、终端输出解析、超时与错误语义。
- 参考文件不是本项目依赖：禁止从源码导入、运行时访问或复制其绝对路径；新项目必须能够独立运行。
- 禁止照搬旧 `server.py` 的单文件聚合结构。HTTP 处理留在 `app/routes/`，搜索与写入实现放在 `core/`，系统差异放在 `core/utils/system/`。
- 只提取当前 PRD 所需的 UP 搜索、登记、视频列表刷新、视频下载、单视频下载和字幕脚本获取逻辑；旧项目的转录、调度、迁移与日志功能不得带入 MVP。

## 项目结构

```text
app/
  main.py                  # 组装应用、启动本机服务、打开浏览器
  routes/                  # FastAPI 路由：校验 HTTP 输入/输出，调用 core
  static/                  # 静态网页：只调用本机 API、展示与交互
core/
  up_search.py             # 搜索用例与 OpenCLI 结果标准化
  configuration.py         # 用户知识库根目录配置
  setup.py                 # 首次目录选择与配置保存
  followings.py            # UP 主登记/更新用例
  following_delete.py      # UP 主删除用例
  video_sync.py            # UP 视频列表刷新用例
  video_batch_sync.py      # 选中 UP 的后台批量增量同步
  video_batch_track_download.py # 按配置日期追踪并下载“自动追踪下载”列已勾选的 UP
  video_download.py        # 视频下载队列与状态用例
  single_video_download.py # 未纳入 UP 追踪的单视频下载用例
  subtitle_download.py     # 字幕脚本获取、sidecar 写入和 transcript 状态同步
  cover_download.py        # 封面元数据补查、CDN 下载和原子写入
  video_cover_backfill.py  # 追踪范围内已下载视频的缺失封面补齐
  download_files.py        # 下载文件发现、临时文件清理和安全命名
  download_progress.py     # 下载状态存储、大小监测和过期清理
  opencli_videos.py        # OpenCLI 视频查询/下载适配
  repositories/            # UpList JSON 与 Markdown 读写
  utils/system/            # 唯一的平台适配边界（含目录选择与配置目录）
requirements.txt           # Python 依赖
README.md                  # 安装、运行、测试说明
ARCHITECTURE.md            # 当前架构说明
PRD.md                     # 当前 MVP 产品需求
tests/                     # 自动化测试和测试样例
tmp/                       # 可删除的测试/运行临时文件
logs/                      # 本地诊断日志
```

### 分层规则

- `app/static` 只能调用 API，不能读取文件、执行 OpenCLI 或导入 Python 业务代码。
- `app/routes` 只能处理 HTTP 模型与状态码，并调用 `core`；不能直接读写 UpList 或执行 OpenCLI。
- `core` 不得导入 FastAPI、路由或前端代码。业务、OpenCLI 适配、数据读写均在此层完成。
- `core/utils/system` 不包含业务逻辑，只实现统一的平台操作接口，如浏览器启动、子进程管理和退出清理。

## 数据与配置

- 首次运行必须选择一个已存在、可写的视频知识库目录；取消或校验失败时不写入配置，不开放搜索和登记。
- 配置文件固定保存到 macOS `~/Library/Application Support/BiliUp/config.json` 或 Windows `%LOCALAPPDATA%\BiliUp\config.json`；`knowledge_base_root` 保存用户选择的绝对路径，`batch_track_since_date` 保存批量追踪起始日期，前者是路径规则的唯一受控例外。
- `<knowledge_base_root>/UpList/followings.json` 是 UP 登记与统计真源：按添加顺序保存 `uid`、`nickname`、`bio`、`scheduled_tracking`、`created_at`、`last_sync_at`、`total_count`、`synced_count`、`downloaded_count`；`next_sync_page` 是不在 UI 展示的单 UP 手动同步游标。
- 以 `uid` 去重；重复时更新昵称和简介，不重置 `created_at`。
- `<knowledge_base_root>/UpList/bilibili-up-followings.md` 仅由 JSON 生成，用固定 Markdown 表格展示；它不是写入源。
- 远端追踪清单保存为 `<knowledge_base_root>/UpList/<UP名称>.jsonl`（例如 `UpList/火星船长1989.jsonl`），保存网站元数据和下载状态；本地视频库索引独立保存为 `<knowledge_base_root>/SortedMp4/<UP名称>/videos.jsonl`，只记录真实存在的视频，并使用 `bvid`、`date`、`title`、`relative_path`、`original_filename`、`size_bytes`、`transcript`、`cover`、`scanned_at`、`index`。视频文件保存到 `<knowledge_base_root>/SortedMp4/<UP名称>/<YYYYMM>/`。不把视频明细混入 `followings.json`。
- 删除 UP 主时移除其 `followings.json` 登记和对应 JSONL 视频索引，保留 `SortedMp4/<UP名称>/` 下的实际视频文件。
- 单视频下载保存到 `<knowledge_base_root>/OtherVideos/`，索引为 `<knowledge_base_root>/OtherVideos/videos.jsonl`，不写入 `UpList` 或自动追踪清单。
- `tmp/` 不存正式数据；`logs/` 不记录令牌、Cookie、凭据或完整 OpenCLI 原始输出。

## 跨平台与验证

- macOS 和 Windows 共用静态网页、路由、`core` 业务和测试代码；不得维护两套功能实现。
- 系统差异必须通过 `core/utils/system` 的统一接口处理。修复不得只在单一系统旁路实现。
- 每项功能变更必须在 macOS 和 Windows 上运行同一套测试；涉及启动、OpenCLI 子进程或 PyInstaller 时，两端分别做集成或打包冒烟验证。
- 任一系统失败，禁止合入 `dev-full` 或进入 `MVP`。

## 依赖、文档与虚拟环境

- `.venv/` 是项目内本机虚拟环境，已被 Git 忽略；创建和激活命令记录在 README，不得在源码中硬编码其解释器路径。
- 新增或移除依赖时，同步更新 `requirements.txt` 与 README。
- 改动模块、接口、数据格式或平台适配时，同步更新 `ARCHITECTURE.md`。
- 文档只描述已实现的功能；未实现内容必须明确标记为规划。
- 修复 Bug 或开发功能后只运行源码测试，交由用户手动验收，不立即打包。若用户要求先验证安装包，可构建未提交候选包供其测试；通过后更新文档并提交。其他版本按用户确认的发布流程执行对应平台的构建与冒烟测试。

## Git 与多人协作

- 所有功能开发、修复和集成先进入 `dev-full`。
- `MVP` 是 GitHub 共享的 worktree 分支，只集成 `dev-full` 中已验证功能的子集；禁止在 `MVP` 修改功能实现。
- 纳入 `MVP` 的实现文件必须与 `dev-full` 一致；差异只能是未纳入功能、发布配置或本地机密。
- 多 Agent 开发时，按无重叠文件边界分配；每个 Agent 使用独立特性分支和 worktree。具体职责在开发开始时确定。
- 合入前运行相关测试；合入 `dev-full` 前运行完整测试。未经用户授权，不推送、改写历史或删除 worktree。
