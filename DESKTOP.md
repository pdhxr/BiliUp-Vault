# BiliUp 桌面版

BiliUp 桌面版采用 Tauri v2 外壳启动 PyInstaller 单文件 sidecar，sidecar 运行现有 FastAPI 页面和业务。普通 Web 模式仍可独立使用。

## 运行结构

```text
Tauri 窗口
  └─ biliup-backend sidecar
       └─ FastAPI app/static → app/routes → core
```

Tauri 负责单实例、端口检查、加载/错误页、sidecar 健康检查和退出回收，不读写 UP、视频或 JSONL 数据。若上一次异常退出留下旧 BiliUp 后端，下一次启动先请求优雅关闭，再由 Python 平台适配层核对健康响应、PID 和可执行文件后安全回收；其他端口占用者只显示身份信息，不会被终止。

## 配置和数据

Web 与桌面版共用用户配置：

```text
macOS:  ~/Library/Application Support/BiliUp/config.json
Windows: %LOCALAPPDATA%\BiliUp\config.json
```

`desktop_port` 默认 `8765`，允许整数 `1024–65535`。UI 保存新端口后，本次进程继续使用 `current_port`，下次启动才使用新值。
端口设置区域同时显示实际 `config.json` 的完整路径，方便定位和排障。

`UpList`、`SortedMp4` 和 `OtherVideos` 始终位于配置的 `knowledge_base_root`，桌面封装不迁移这些目录。

## 开发环境

需要 Python、Node.js、Rust，以及 macOS/Windows 对应的 Tauri 系统依赖。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-desktop.txt
npm install
```

Windows PowerShell 使用：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-desktop.txt
npm install
```

## 开发和构建

```bash
npm run desktop:dev
npm run sidecar:build
npm run desktop:build
```

`sidecar:build` 会优先使用项目 `.venv`，调用 PyInstaller 并通过 `rustc --print host-tuple` 生成 Tauri 所需文件名。构建产物位于：

桌面开发和构建脚本从 `core/version.py` 读取 `APP_VERSION` 并传给 Tauri，继续保持该文件为应用版本唯一来源。

```text
src-tauri/binaries/                         # 临时 sidecar，不提交
src-tauri/target/release/bundle/            # 当前平台安装包，不提交
```

macOS 和 Windows 必须分别在原生系统执行 sidecar 和安装包构建，不能跨平台复用二进制。

## 发布前验证

1. 运行 Python 完整测试；
2. 运行 `cargo test --manifest-path src-tauri/Cargo.toml --lib`；
3. 单独启动 sidecar，用临时数据目录验证 `/api/health` 和关闭接口；
4. 运行 `npm run desktop:dev`，验证加载页、现有 UI 和第二次启动；
5. 运行 `npm run desktop:build`；
6. 使用新配置和已有配置分别启动 release 应用；
7. 验证端口冲突、损坏配置和退出回收；
8. 在每个承诺支持的原生平台重复。

当前基础封装不包含签名、公证、SmartScreen 信誉、自动更新和发布 CI，也不打包 OpenCLI、Node.js、Chrome 扩展、yt-dlp 或 FFmpeg/FFprobe。
