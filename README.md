# BiliUp

BiliUp 是一个跨 macOS 和 Windows 运行的本地 B 站视频知识库工具。首次运行时，用户选择自己的知识库目录；应用通过 OpenCLI 复用已登录的 Chrome 会话访问 B 站，不保存 B 站密码或 Cookie。

## 功能概览

当前页面包含三个功能页签：

- **UP 主管理**：搜索并登记 UP 主，查看 UP 信息和视频统计，刷新视频列表，设置自动追踪下载，批量同步或删除登记。
- **UP 主视频下载**：查看 UP 的视频清单，下载单个或多个视频，按起始日期批量追踪并下载未下载视频。
- **其他功能**：查看/重新选择视频知识库目录，打开知识库或单视频目录，并通过 B 站链接、短链接或 BV 号下载未纳入 UP 追踪的单个视频。
- **本地索引与字幕脚本**：UP 视频列表中选择下载与“其他功能”的单视频下载，都会在视频落盘后尝试获取官方字幕，并在视频旁写入 `__transcript.md`；字幕接口失败不影响视频下载。

详细需求和业务规则见 [PRD.md](PRD.md)，架构和模块边界见 [ARCHITECTURE.md](ARCHITECTURE.md)。源码验证命令见 [VerifyGuide.md](VerifyGuide.md)。

## 运行前置条件

安装包已包含 Python、FastAPI 和应用代码，普通用户不需要安装 Python、创建 `.venv` 或执行 `pip install`。以下组件需要用户在系统中准备：

1. Google Chrome、Node.js 21 或更高版本。
2. OpenCLI：

   ```bash
   npm install -g @jackwener/opencli
   ```

3. Chrome 中的 [OpenCLI 扩展](https://chromewebstore.google.com/detail/opencli/ildkmabpimmkaediidaifkhjpohdnifk)。
4. 在同一个 Chrome 配置中登录 B 站，并保持 Chrome 运行。
5. `yt-dlp`，视频下载功能依赖它：

   macOS：

   ```bash
   brew install yt-dlp
   ```

   Windows：安装 yt-dlp 官方 Windows 可执行文件，并将所在目录加入 `PATH`。

安装后可运行以下命令检查 OpenCLI 和 yt-dlp：

```bash
opencli doctor
yt-dlp --version
```

OpenCLI 的 Daemon、Extension 和 Connectivity 检查正常后，BiliUp 才能搜索、刷新和下载。BiliUp 会自动查找常见安装位置，并以后台窗口方式调用 OpenCLI。

应用固定使用 `http://127.0.0.1:8765/`。再次启动时，应用会检查本机的监听服务；只有能确认身份为旧 BiliUp 的服务才会被停止，再由新实例接管固定端口。若 `8765` 属于其他程序，应用不会自动终止它。

## 使用安装包

### macOS

1. 打开 `BiliUp.dmg`，将 `BiliUp.app` 拖入“应用程序”。
2. 启动应用；如遇未签名提示，使用“右键 → 打开”。
3. 首次进入 WebUI 时，选择一个已存在且可写的视频知识库目录。

当前 macOS 包尚未签名和公证。

### Windows

1. 解压完整的 `BiliUp` 目录，不要只复制 EXE 文件。
2. 双击 `BiliUp.exe`；如遇 SmartScreen 提示，确认来源后选择继续运行。
3. 首次进入 WebUI 时，选择一个已存在且可写的视频知识库目录。

Windows 安装包必须在 Windows 原生环境构建；构建脚本已在 Windows 11 / Python 3.13 上验证通过，PyInstaller 产物 `dist/BiliUp/BiliUp.exe` 可正常启动 WebUI、读写本地知识库。`--windowed` 模式下 uvicorn 的 stdout 崩溃已通过 `scripts/pyi_rth_stdout.py` runtime hook 修复。

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
- `transcript` 字段记录视频旁 `__transcript.md` 字幕脚本状态；UP 视频下载和单视频下载共用字幕下载逻辑。OpenCLI 短暂失败时会自动重试一次；仍失败则保持为 `false`，不影响视频下载。
- 应用配置保存在 macOS `~/Library/Application Support/BiliUp/config.json` 或 Windows `%LOCALAPPDATA%\BiliUp\config.json`，记录知识库目录和批量追踪起始日期。

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

## 构建安装包

macOS 生成 `.app` 和 `.dmg`：

```bash
.venv/bin/python -m scripts.build macos
```

Windows 生成 EXE 目录（必须在 Windows 原生环境执行）：

```powershell
.\.venv\Scripts\python.exe -m scripts.build windows
```

构建产物位于 `dist/`，不提交 Git。修复或开发完成后先运行源码测试并手动验收，版本确认后再打包。

## 当前限制

- OpenCLI、Node.js、Chrome 扩展、yt-dlp 和 B 站浏览器登录尚未由安装包自动处理。
- macOS 包尚未签名、公证。Windows EXE 已在 Windows 11 原生环境完成 PyInstaller 构建与启动冒烟验证；代码签名与 SmartScreen 白名单仍待处理。
- 第三个页签的单视频下载统一写入 `OtherVideos/`，不会加入 UP 自动追踪列表。
