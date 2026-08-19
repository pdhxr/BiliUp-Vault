# 更新记录

本项目使用[语义化版本](https://semver.org/lang/zh-CN/)；每个正式版本对应一个 Git 标签（例如 `v0.1.0`）。

## [未发布]

暂无。

## [0.3.0] - 2026-08-19

### 新增

- “其他功能”的单视频下载支持抖音分享文本、短链接和正式视频链接。
- 抖音视频通过 yt-dlp 获取元数据与视频，保存网站竖版封面，并在公开访问失败时使用本机 Chrome Cookie 重试。
- `OtherVideos/videos.jsonl` 使用 `platform` 和 `video_id` 区分 B 站与抖音来源，已有视频不会重复下载。

### 修复

- macOS 从应用菜单或系统退出应用时，先正常关闭 Python 后端并回收 sidecar，不再遗留监听端口的后台进程。

### 验证状态

- macOS Apple Silicon 的 122 项自动测试、Rust 检查、sidecar 冒烟和 Tauri release 构建均已通过。
- macOS 安装包尚未签名或公证；Windows 安装包仍需在 Windows 原生环境构建和验证。

## [0.2.0] - 2026-08-18

### 新增

- Tauri v2 桌面外壳，复用现有 FastAPI UI、路由和 `core` 业务内核。
- 桌面单实例、后端健康识别、端口冲突保护和受管 sidecar 退出回收。
- Web 与桌面应用共用现有 `config.json`、知识库路径和业务数据；新增可在界面设置的 `desktop_port`。
- 端口设置区域显示实际 `config.json` 完整路径。
- UP 批量同步和“批量追踪并下载”增加停止操作；只取消对应批次并保留已经完成的数据。
- 采用用户选定的简洁 B 图标，统一 Finder、DMG 和 Dock 图标。
- macOS DMG 与 Windows Tauri 安装器的原生构建流程，以及桌面安全边界和验收文档。

### 安全

- 桌面修改类 API 要求公开客户端标记，并限制可信本机 Host；localhost 页面不获得 shell 或文件系统能力。

### 修复

- UP 主管理页不再依赖桌面 WebView 无法稳定显示的浏览器原生确认框；删除操作改用应用内确认对话框。
- 退出时协调关闭后台任务和受管子进程；下次启动可识别并安全回收身份明确的旧 BiliUp 后端，不终止未知程序。
- HEVC `hev1` 视频在下载后无损重封装为 QuickTime 兼容的 `hvc1`。

### 验证状态

- macOS Apple Silicon 的自动测试、Rust 测试、sidecar 冒烟和 Tauri release 构建已通过。
- Windows 原生构建、安装和退出回收仍待验证；`v0.2.0` 仅发布 macOS Apple Silicon 安装包。

## [0.1.0] - 2026-08-12

### 新增

- UP 主搜索、登记、管理、视频列表刷新及自动追踪下载。
- 已下载视频的本地索引、字幕脚本和封面图片获取。
- 未纳入 UP 追踪的单视频下载，以及知识库目录管理。
- macOS 与 Windows 的源码运行和安装包构建流程。

### 已知限制

- OpenCLI、Chrome 扩展、yt-dlp 和 B 站登录需由用户自行准备。
- macOS 安装包尚未签名或公证；Windows 代码签名与 SmartScreen 白名单尚未完成。
