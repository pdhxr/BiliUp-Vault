# BiliUp 架构

## 当前状态

当前 MVP 已实现首次知识库目录设置、OpenCLI 搜索、UP 单选登记和本地 UpList 写入。范围见 [PRD.md](PRD.md)。

## 三层架构

系统按单向依赖组织：静态网页层 → FastAPI 路由层 → `core` 业务内核层。

- `app/main.py`：应用组装、服务生命周期和浏览器打开。
- `app/static/`：静态网页；只调用本机 API 并展示结果。
- `app/routes/`：FastAPI 路由；只负责 HTTP 输入/输出与调用 `core`。
- `core/`：配置、首次设置、搜索、UP 主登记、OpenCLI 适配和 UpList 数据读写；不得依赖 FastAPI 或前端。
- `core/configuration.py`：读写用户知识库根目录配置，并校验已配置目录可写。
- `core/setup.py`：编排首次目录选择与配置保存。
- `core/utils/system/`：唯一的 macOS/Windows 平台适配边界，提供统一的浏览器、子进程、目录选择、应用配置目录和 PyInstaller 资源路径接口。
- `scripts/build.py`：构建工具；在对应原生系统调用 PyInstaller，macOS 额外生成 DMG。

## 数据流

首次设置：WebUI → FastAPI setup route → `core/setup.py` → 系统目录选择器 / 配置文件。

登记：WebUI → FastAPI UP route → `core/followings.py` → `<knowledge_base_root>/UpList` repository。

`<knowledge_base_root>/UpList/followings.json` 是 canonical 数据源；同目录的 `bilibili-up-followings.md` 由 JSON 生成，仅供人工阅读。

## 跨平台原则

核心业务模块由 macOS 和 Windows 共用。平台差异仅限 `core/utils/system/`：macOS 使用 Finder/AppleScript 选择目录，Windows 使用 FolderBrowserDialog；两者对上层统一返回 `Path | None`。两端运行同一套测试，并分别原生打包验证。

应用启动时自动选择可用的本地端口并打开 WebUI，避免占用或终止其他程序的端口。打包后的应用不创建虚拟环境；虚拟环境只用于源码开发和构建。

首次运行先通过 `/api/setup-status` 检查知识库配置。配置文件固定保存在 macOS `~/Library/Application Support/BiliUp/config.json` 或 Windows `%LOCALAPPDATA%\BiliUp\config.json`，其中唯一的绝对路径值是用户选择的 `knowledge_base_root`。未配置时网页不开放搜索和写入。

知识库配置完成后，`/api/runtime-status` 检查 OpenCLI。系统适配层从当前 PATH 以及 Homebrew、npm、NVM、Volta 等平台常见位置发现可执行文件，并为子进程补齐 Node/OpenCLI 所需 PATH；未安装时由 WebUI 展示人工安装、Chrome 扩展和 B 站登录指引。
