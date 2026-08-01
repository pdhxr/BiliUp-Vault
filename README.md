# BiliUp

BiliUp 是跨 macOS 和 Windows 的本地 B 站 UP 主搜索与登记工具。

当前 MVP：首次选择视频知识库目录后，通过 OpenCLI 搜索并登记 UP 主；“UP 主管理”页签支持刷新视频信息列表，第二个页签支持选择视频并下载到知识库，也支持按起始日期批量追踪并下载多个 UP 的未下载视频。输入昵称不会自动搜索，只有点击“搜索”按钮才会调用 OpenCLI；搜索期间按钮置灰并显示“搜索中…”。搜索结果区默认显示约 3–5 项，其余结果可在列表内滚动查看；“确认写入”按钮位于结果列表上方。

- 产品需求：[PRD.md](PRD.md)
- 架构说明：[ARCHITECTURE.md](ARCHITECTURE.md)

## 下载后需要手动准备什么

### 使用安装包

安装包已经包含 Python、FastAPI 和应用代码。普通用户不需要安装 Python、不需要创建 `.venv`，也不需要执行 `pip install`。

当前版本尚未内置 OpenCLI 运行时，因此 macOS 和 Windows 用户仍需手动准备：

1. 安装 Google Chrome。
2. 安装 Node.js 21 或更高版本。
3. 安装 OpenCLI：

   ```bash
   npm install -g @jackwener/opencli
   ```

4. 在 Chrome 安装 [OpenCLI 扩展](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk)。
5. 在同一个 Chrome 用户配置中打开 B 站并完成登录。
6. 保持 Chrome 运行，执行以下命令检查 OpenCLI、扩展和浏览器连接：

   ```bash
   opencli doctor
   ```

7. 如果要使用第二个页签下载视频，还需要安装 `yt-dlp`：

   macOS：

   ```bash
   brew install yt-dlp
   ```

   Windows：安装 yt-dlp 官方 Windows 可执行文件，并把它所在目录加入 `PATH`。

   安装后确认命令可用：

   ```bash
   yt-dlp --version
   ```

8. 确认搜索命令能够返回 JSON：

   ```bash
   opencli bilibili search "测试昵称" --type user -f json
   ```

只有 `opencli doctor` 的 Daemon、Extension 和 Connectivity 检查正常后，BiliUp 的搜索功能才能使用。若检查失败，请先确认 Chrome 已启动、扩展已启用且 B 站仍处于登录状态，然后重新执行检查。

BiliUp 首次启动会检查 OpenCLI。未安装或无法运行时，首页显示安装提示并禁用搜索；安装完成并重新启动 BiliUp 后会自动重新检测。已安装在 Homebrew、npm、NVM 或 Volta 常见位置的 OpenCLI，即使从 Finder 双击应用也会被系统适配层查找。

### 为什么需要浏览器登录

B 站用户搜索是 OpenCLI 的浏览器型命令，需要从已登录的 Chrome 会话获取访问凭据。BiliUp 不保存 B 站密码，也不要求用户把 Cookie、令牌或密码写入项目文件。

BiliUp 调用 OpenCLI 搜索、刷新和下载时统一请求 `--window background`，不会主动把 OpenCLI 浏览器窗口切到前台；Chrome 和 OpenCLI Daemon 仍需保持运行。

## macOS 安装包使用方法

1. 下载并打开 `BiliUp.dmg`。
2. 将 `BiliUp.app` 拖入“应用程序”目录。
3. 首次启动时双击 `BiliUp.app`。
4. 如果 macOS 阻止未签名应用，右键点击应用，选择“打开”，再确认一次。
5. 应用启动本机 FastAPI 服务并打开 WebUI。
6. 首次使用时，点击“选择视频知识库目录”，在 Finder 中选择一个已存在、可写的长期保存目录。
7. 输入 UP 主昵称，点击“搜索”，在结果中单选一项，点击“确认写入”。

确认写入后，应用会立即为该 UP 拉取首批视频并建立或更新 `UpList/<UP名称>.jsonl` 和本地 `SortedMp4/<UP名称>/videos.jsonl`；添加成功反馈会显示初始视频数。若首次同步失败，UP 登记仍会保留，可在视频页点击“刷新列表”重试。

当前 macOS 包尚未进行 Apple 开发者签名和公证，因此首次启动可能出现系统安全提示。

## Windows 安装包使用方法

Windows 安装包必须在 Windows 原生环境构建。构建完成后：

1. 解压完整的 `BiliUp` 目录，不要只复制其中的 EXE。
2. 双击 `BiliUp.exe`。
3. 如果 Windows SmartScreen 提示未知发布者，确认文件来源后选择“更多信息”→“仍要运行”。
4. 应用启动本机 FastAPI 服务并打开 WebUI。
5. 首次使用时，点击“选择视频知识库目录”，在 Windows 目录选择框中选择一个已存在、可写的长期保存目录。
6. 输入 UP 主昵称，点击“搜索”，在结果中单选一项，点击“确认写入”。

确认写入后，应用会立即为该 UP 拉取首批视频并建立或更新 `UpList/<UP名称>.jsonl` 和本地 `SortedMp4/<UP名称>/videos.jsonl`；添加成功反馈会显示初始视频数。若首次同步失败，UP 登记仍会保留，可在视频页点击“刷新列表”重试。

当前项目已提供 Windows 构建脚本，但尚未在 Windows 原生环境生成和验证 EXE。

## 数据保存位置

首次选择的视频知识库目录是所有用户数据的根目录。当前 MVP 写入：

```text
<知识库目录>/UpList/followings.json
<知识库目录>/UpList/bilibili-up-followings.md
<知识库目录>/UpList/<UP名称>.jsonl
<知识库目录>/SortedMp4/<UP名称>/videos.jsonl
<知识库目录>/SortedMp4/<UP名称>/<YYYYMM>/<UP名称>_<YYYYMMDD>_<标题>.mp4
```

- `followings.json` 是唯一数据真源。
- `bilibili-up-followings.md` 是自动生成的可读表格。
- `UpList/<UP名称>.jsonl` 是 B 站远端追踪清单，保存 `date`、`title`、`bvid`、`url`、`downloaded`、`transcript`、`local_filename` 和 `index`。
- `SortedMp4/<UP名称>/videos.jsonl` 是本地视频库索引，只有真实存在且大小大于零的视频才写入；每行使用 `bvid`、`date`、`title`、`relative_path`、`original_filename`、`size_bytes`、`transcript`、`scanned_at` 和 `index` 字段。例如：

  ```json
  {"bvid":"BV19UGw6hEV1","date":"20260731","title":"科技-红利双星系统","relative_path":"SortedMp4/火星船长1989/202607/火星船长1989_20260731_科技-红利双星系统.mp4","original_filename":"火星船长1989_20260731_科技-红利双星系统.mp4","size_bytes":16411331,"transcript":true,"scanned_at":"2026-08-01T00:35:55.830778-07:00","index":1}
  ```
- `SortedMp4/<UP名称>/<YYYYMM>/` 保存下载完成的视频文件；本地索引的 `relative_path` 始终相对知识库根目录记录。
- 刷新视频列表时，系统按网站元数据扫描已有月度视频，补建缺失的本地 `videos.jsonl` 条目，并用本地索引校准 `UpList/<UP名称>.jsonl` 的下载状态。下载成功时同时更新两套索引。
- 仅执行搜索不会写文件；选择结果并点击“确认写入”后才会保存。
- 已存在于项目根目录的旧 `UpList/` 不会自动迁移；后续登记以用户选择的新知识库目录为准。

应用配置文件不在安装包或项目目录中：macOS 为 `~/Library/Application Support/BiliUp/config.json`，Windows 为 `%LOCALAPPDATA%\BiliUp\config.json`。其中保存用户选择的知识库绝对路径和 `batch_track_since_date` 批量追踪起始日期；这是用户选择的受控配置值，不是硬编码路径。

## UP 主管理页签

页签从当前配置的 `<知识库目录>/UpList/followings.json` 读取登记数据，显示：选择框、序号、UP 名称、UP 简介、自动追踪下载、最后同步时间、视频总数、已下载/已同步和操作列。当前登记数据没有视频统计时，统计列显示 `0 / 0`；未提供同步时间时显示 `-`。

列表左上角总复选框与每行选择框联动，部分选中时显示半选状态。点击“批量同步”只处理当前勾选的 UP；同步按 BV 号增量合并新视频，不覆盖已有下载状态。未勾选 UP 时按钮仍可点击并显示提示；任务开始后按钮置灰并显示“同步中…”，行刷新同步禁用，任务结束后恢复初始状态。

“刷新列表”会调用 OpenCLI 分页获取已登记 UP 的视频信息，最多向前查询 5 页，每次最多新增 20 条；按 BV 号增量合并到本地 JSONL，不覆盖已有下载状态。“批量同步”只对勾选的 UP 在后台逐个执行同样的分页增量同步。下载会将选中的视频提交到后台任务；下载期间，第二个页签会实时显示任务汇总、视频标题、排队中/下载中/完成/失败状态和已下载大小；单个任务失败时会按 `best`、`720p`、`480p` 依次重试，并在进度面板显示 OpenCLI/yt-dlp 的简要错误。即使 OpenCLI 退出码异常，只要检测到有效视频文件也会继续完成登记。下载结束后自动刷新视频列表和 UP 统计。

UP 管理列表的“自动追踪下载”复选框会立即写入 `<知识库目录>/UpList/followings.json` 的 `scheduled_tracking` 字段。批量追踪并下载只读取这一列：凡是该列被勾选的 UP 都会参与；左侧主复选框不影响批量追踪。

第二个页签的“批量追踪并下载”使用同页的“起始日期”。进入页签时日期从应用 `config.json` 读取；修改日期后立即保存回同一个配置文件。任务先按日期从 B 站向前分页追踪，随后从每个 UP 的完整视频列表中筛选“`downloaded` 为否且日期不早于起始日期”的视频，全部提交下载；新发现的视频也会先写入远端追踪清单。它处理 UP 管理页中“自动追踪下载”列已勾选的全部 UP，不要求左侧主复选框，也不使用视频页当前 UP 作为回退。界面分“追踪中”和“下载中”两阶段；追踪完成后显示“下载中 已完成数/需要下载总数”，并继续显示新增数和失败数；按钮始终可点击，缺少必要条件时点击后显示提示。

删除按钮只对勾选的 UP 生效。确认删除后，系统移除 `followings.json` 中的登记和对应 `UpList/<UP名称>.jsonl` 视频索引，但保留 `SortedMp4/<UP名称>/` 下的已下载视频文件。

## 视频接口

- `GET /api/up/{up_id}/videos`：读取远端追踪清单，并用本地 `SortedMp4/<UP名称>/videos.jsonl` 校准下载状态。
- `POST /api/up/{up_id}/videos/refresh`：通过 OpenCLI 刷新视频列表。
- `POST /api/up/videos/batch-refresh`：后台增量同步选中的 UP。
- `GET /api/up/videos/batch-refresh-progress`：读取批量增量同步进度。
- `POST /api/up/videos/batch-track-download`：按起始日期后台追踪“自动追踪下载”列已勾选的 UP，并提交期限内所有未下载视频的下载任务。
- `GET /api/up/videos/batch-track-download-progress`：读取批量追踪和下载的两阶段进度。
- `POST /api/followings/tracking`：保存单个 UP 的自动追踪下载开关到 `followings.json`。
- `GET /api/settings/batch-track`：读取 `config.json` 中的批量追踪起始日期。
- `PUT /api/settings/batch-track`：保存批量追踪起始日期到 `config.json`。
- `POST /api/followings/delete`：删除选中的 UP 登记和视频索引，保留实际视频文件。
- `POST /api/videos/download`：提交一个或多个 BV 号下载任务。
- `GET /api/videos/download-progress`：读取后台下载状态、任务标题、状态、错误信息和已下载大小；已结束记录最多保留 30 分钟。

## 从源码运行

源码运行额外需要 Python。当前开发环境使用 Python 3.14。

### macOS

在项目根目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.main
```

### Windows PowerShell

在项目根目录执行：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app.main
```

`.venv/` 只用于源码开发和构建，已被 Git 忽略。

## 测试

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 开发与打包流程

修复 Bug 或开发功能后，先运行源码自动化测试，再由用户以源码模式手动验收；该阶段不生成安装包。若用户要求验证安装包，可先构建未提交的候选包供其手动测试；验证通过后，再更新文档并提交本地版本。

## 构建安装包

macOS 生成 `.app` 与 `.dmg`：

```bash
.venv/bin/python -m scripts.build macos
```

Windows 生成 EXE 目录（必须在 Windows 原生环境执行）：

```powershell
.\.venv\Scripts\python.exe -m scripts.build windows
```

构建产物位于 `dist/`，不提交 Git。macOS 和 Windows 必须分别在对应原生系统构建与验证，PyInstaller 不支持从 macOS 直接生成可验证的 Windows EXE。

## 当前发布限制

- OpenCLI、Node.js、Chrome 扩展与 B 站浏览器登录尚未被安装包自动处理。
- macOS 包尚未签名、公证；Windows EXE 尚未原生构建、签名和验证。

当前 MVP 尚未提供在 WebUI 中更换已选知识库目录的设置页。
