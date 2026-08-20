# BiliUp

BiliUp 是一个跨 macOS 和 Windows 运行的本地 B 站视频知识库工具。首次运行时，用户选择自己的知识库目录；应用通过 OpenCLI 复用已登录的 Chrome 会话访问 B 站，不保存 B 站密码或 Cookie。

当前版本：`0.3.0`。安装包请从 [GitHub Releases](https://github.com/pdhxr/BiliUp-Vault/releases) 下载，版本变更见 [CHANGELOG.md](CHANGELOG.md)。

## 功能概览

当前页面包含三个功能页签：

- **UP 主管理**：搜索并登记 UP 主，查看 UP 信息和视频统计，刷新视频列表，设置自动追踪下载，批量同步或删除登记；批量同步过程中可立即停止并重新选择。
- **UP 主视频下载**：查看 UP 的视频清单，下载单个或多个视频，按起始日期批量追踪并下载未下载视频，同时补齐追踪范围内本地视频缺少的封面；批量追踪或下载过程中可停止本批次，不影响手动下载。
- **其他功能**：查看/重新选择视频知识库目录，打开知识库或单视频目录，通过链接或 BV 号下载单个视频，并配置桌面服务端口、查看实际配置文件路径。

此外，UP 视频列表中选择下载与“其他功能”的单视频下载都会写入本地媒体索引，并在视频落盘后尝试获取官方字幕和封面图片；附加资源获取失败不影响视频下载。

详细需求和业务规则见 [PRD.md](PRD.md)，架构和模块边界见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 桌面应用架构

桌面安装包采用 Tauri v2 外壳，保留现有 FastAPI 页面和三层业务架构，由 Tauri 负责窗口、单实例和 Python sidecar 生命周期。

Web 与桌面模式共用现有用户 `config.json`，其中包含 `desktop_port`；`UpList`、`SortedMp4` 和 `OtherVideos` 继续位于用户选择的知识库，不做数据迁移。桌面开发与发布检查见 [DESKTOP.md](DESKTOP.md)，安全边界见 [SECURITY.md](SECURITY.md)。

## 运行前置条件

安装包已包含 Python、FastAPI 和应用代码，普通用户不需要安装 Python、创建 `.venv` 或执行 `pip install`。以下组件需要用户在系统中准备：

1. Google Chrome、Node.js 20 或更高版本。
2. OpenCLI。首次安装与升级均使用：

   ```bash
   npm install -g @jackwener/opencli@latest
   ```

3. Chrome 中的 [OpenCLI 扩展](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk)。
4. 在同一个 Chrome 配置中登录 B 站，并保持 Chrome 运行。
5. `yt-dlp`，视频下载功能依赖它；同时安装 `ffprobe` 和 `ffmpeg`，用于识别 HEVC `hev1` 视频并无损重封装为兼容 QuickTime 的 `hvc1`：

   macOS：

   ```bash
   brew install yt-dlp ffmpeg
   ```

   Windows：安装 yt-dlp 和 FFmpeg 的官方 Windows 可执行文件，并将所在目录加入 `PATH`。

安装后可运行以下命令检查 OpenCLI、yt-dlp、FFprobe 和 FFmpeg：

```bash
opencli --version
opencli doctor
yt-dlp --version
ffprobe -version
ffmpeg -version
```

当前源码已使用 OpenCLI `1.8.6` 验证。版本低于 `1.8.6` 时先执行上面的升级命令；OpenCLI 的 Daemon、Extension 和 Connectivity 检查正常后，BiliUp 才能搜索、刷新和下载。BiliUp 会自动查找常见安装位置，并以后台窗口方式调用 OpenCLI。

桌面应用默认使用 `http://127.0.0.1:8765/`，可在“其他功能”中设置下次启动端口并查看 `config.json` 的完整路径。第二次启动只聚焦已有窗口；若端口由身份可确认的旧 BiliUp 后端占用，应用会先请求其正常退出，必要时只回收该旧进程。未知程序占用时不自动换端口、不连接也不终止。普通 Web 源码模式仍使用固定端口。

## 使用安装包

### macOS

1. 从 GitHub Releases 下载 `BiliUp_<版本>_aarch64.dmg`，打开后将 `BiliUp.app` 拖入“应用程序”。
2. 启动应用；如遇未签名提示，使用“右键 → 打开”。
3. 首次进入 WebUI 时，选择一个已存在且可写的视频知识库目录。

当前 macOS 包尚未签名和公证。

### Windows

1. 运行 Tauri 生成的 Windows 安装器。
2. 启动 BiliUp；如遇 SmartScreen 提示，确认来源后选择继续运行。
3. 首次进入 WebUI 时，选择一个已存在且可写的视频知识库目录。

Windows 安装包必须在 Windows 原生环境重新构建 sidecar 和 Tauri 安装器。当前 Tauri 封装已在 macOS Apple Silicon 完成构建与启动验证，Windows Tauri 安装包仍需原生平台验证。

## 数据和配置

首次选择的视频知识库目录是所有用户数据的根目录：

```text
<知识库目录>/UpList/followings.json
<知识库目录>/UpList/bilibili-up-followings.md
<知识库目录>/UpList/<UP名称>.jsonl
<知识库目录>/SortedMp4/<UP名称>/videos.jsonl
<知识库目录>/SortedMp4/<UP名称>/<YYYYMM>/<视频文件>
<知识库目录>/OtherVideos/videos.jsonl
<知识库目录>/OtherVideos/<视频文件>
```

- `followings.json` 保存 UP 登记和管理状态。
- `UpList/<UP名称>.jsonl` 保存 B 站视频追踪信息；`SortedMp4/<UP名称>/videos.jsonl` 保存本地视频索引，两者独立维护。
- `transcript` 与 `cover` 字段分别记录视频旁 `__transcript.md` 字幕脚本和 `<视频主名>_cover.<扩展名>` 封面状态；封面按实际图片格式保存为 JPG 或 WEBP。UP 视频下载和单视频下载共用字幕、封面获取逻辑；附加资源获取失败时对应字段保持为 `false`，不影响视频下载。
- 应用配置保存在 macOS `~/Library/Application Support/BiliUp/config.json` 或 Windows `%LOCALAPPDATA%\BiliUp\config.json`，记录知识库目录、批量追踪起始日期和桌面端口。

项目根目录中已有的旧 `UpList/` 不会自动迁移，后续数据以用户选择的知识库目录为准。

## 源码运行

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.main
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app.main
```

`.venv/` 只用于源码开发和构建，已被 Git 忽略。

## 测试

macOS：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 构建桌面安装包

先安装桌面构建依赖：

```bash
python -m pip install -r requirements-desktop.txt
npm ci
```

开发、sidecar 和当前平台 release 构建：

```bash
npm run desktop:dev
npm run sidecar:build
npm run desktop:build
```

构建产物位于 `src-tauri/target/release/bundle/`，不提交 Git。sidecar 与安装包必须在目标原生系统构建。详细步骤见 [DESKTOP.md](DESKTOP.md)。原有 `scripts.build` 保留用于旧 PyInstaller 包验证，不再是 Tauri 发布入口。

## 当前限制

- OpenCLI、Node.js、Chrome 扩展、yt-dlp、FFmpeg 和 B 站浏览器登录尚未由安装包自动处理。
- Tauri macOS 包尚未签名、公证；Windows Tauri 安装包尚待原生构建与冒烟验证。代码签名与 SmartScreen 白名单仍待处理。
- 第三个页签的单视频下载统一写入 `OtherVideos/`，不会加入 UP 自动追踪列表。

## 许可证

本项目采用 [MIT License](LICENSE)，版权持有人为 `-kb-`。
