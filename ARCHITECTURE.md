# BiliUp 架构

## 当前状态

项目处于工程初始化阶段，尚未实现应用模块。

当前 MVP 范围见 [PRD.md](PRD.md)。

## 三层架构

系统按单向依赖组织：静态网页层 → FastAPI 路由层 → `core` 业务内核层。

- `app/main.py`：应用组装、服务生命周期和浏览器打开。
- `app/static/`：静态网页；只调用本机 API 并展示结果。
- `app/routes/`：FastAPI 路由；只负责 HTTP 输入/输出与调用 `core`。
- `core/`：搜索、UP 主登记、OpenCLI 适配和 UpList 数据读写；不得依赖 FastAPI 或前端。
- `core/utils/system/`：唯一的 macOS/Windows 平台适配边界，提供统一的浏览器、子进程和退出清理接口。

## 数据流

WebUI → FastAPI route → core → OpenCLI / UpList repository。

`UpList/followings.json` 是 canonical 数据源；`UpList/bilibili-up-followings.md` 由 JSON 生成，仅供人工阅读。

## 跨平台原则

核心业务模块由 macOS 和 Windows 共用。平台差异仅限 `core/utils/system/`；两端运行同一套测试，并分别原生打包验证。
