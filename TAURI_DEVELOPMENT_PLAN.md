# BiliUp Tauri 桌面封装开发计划

状态：已按计划完成 macOS Apple Silicon 实现、自动测试、sidecar 冒烟和 Tauri release 候选构建；等待用户手工验收及 Windows 原生验证。

本计划记录把现有 BiliUp 封装为 Tauri v2 桌面应用的设计决策、实施步骤和验收状态。

## 1. 目标与成功标准

桌面版采用“Tauri 外壳 + Python sidecar + 原有 FastAPI 页面”结构，在不重写 UI 和业务内核的前提下实现：

- 安装版启动时由 Tauri 自动启动、监控并退出 Python 后端；
- 继续复用现有 HTML、JavaScript、FastAPI 路由、`core` 业务和 repositories；
- 普通 Web 源码模式继续独立运行；
- macOS 和 Windows 使用同一套业务代码，分别在原生平台构建和冒烟验证；
- 桌面应用只监听 `127.0.0.1`，具有独立的单实例、端口冲突和进程回收机制；
- 用户原有配置和知识库数据保持原位置，不要求重新选择或迁移。

完成标准以本文第 8 节为准。

## 2. 已确认的设计决策

### 2.1 不重写业务 UI

Tauri 不建立第二套业务前端。窗口启动时先显示 `desktop/index.html` 加载/错误页，Python 健康检查成功后导航到现有 FastAPI 页面：

```text
Tauri 主进程
  ├─ 单实例、端口、窗口和 sidecar 生命周期
  └─ http://127.0.0.1:<port>/
       └─ 现有静态网页 → FastAPI routes → core → repositories
```

### 2.2 保留三层单向架构

现有“静态网页层 → FastAPI 路由层 → `core` 业务内核层”不改变。Tauri 位于应用外壳层，只管理窗口和自己创建的 sidecar：

- Rust 不读写 `followings.json`、JSONL、视频、字幕或封面；
- `core` 不导入 FastAPI、Tauri 或前端代码；
- FastAPI 路由不执行 Tauri/Rust 逻辑，也不直接写 repositories；
- 静态网页只调用本机 HTTP API，不获得 Tauri shell 或文件系统权限。

### 2.3 共用现有用户配置

普通 Web 模式和 Tauri 桌面模式共用同一份用户配置：

```text
macOS:  ~/Library/Application Support/BiliUp/config.json
Windows: %LOCALAPPDATA%\BiliUp\config.json
```

现有字段保持兼容，并在同一文件增加 `desktop_port`：

```json
{
  "version": 1,
  "knowledge_base_root": "/用户选择的视频知识库",
  "batch_track_since_date": "",
  "desktop_port": 8765
}
```

- `desktop_port` 缺失时读取默认值 `8765`，不得仅因读取而改写旧配置；
- 保存端口时只接受整数 `1024–65535`，布尔值也必须拒绝；
- 重新选择知识库时必须保留 `desktop_port` 和其他未知兼容字段；
- 配置继续由 Python `core/configuration.py` 统一校验并原子写入；
- Tauri 启动时只读取本次启动需要的 `desktop_port`，不修改业务设置；
- `src-tauri/tauri.conf.json` 是提交到 Git 的构建配置，不与用户 `config.json` 合并。

Tauri 默认 `app_data_dir` 可能受 bundle identifier 影响，不能假定它天然等于现有 `BiliUp` 目录。实现时必须显式解析并把现有应用配置目录传给 sidecar，不复制或迁移配置。

### 2.4 保持知识库数据位置

以下内容继续保存在用户选择的 `knowledge_base_root`：

```text
<knowledge_base_root>/UpList/
<knowledge_base_root>/SortedMp4/
<knowledge_base_root>/OtherVideos/
```

Tauri 封装不得把 `UpList` 或视频索引迁入应用数据目录。`BILIUP_DATA_DIR` 若用于桌面入口，只表示现有应用配置/运行状态目录，不改变 `knowledge_base_root` 的含义。

### 2.5 两种启动入口复用同一个应用工厂

- `app/main.py` 保留普通 Web 开发入口和原有浏览器启动行为；
- `tools/desktop_entry.py` 只解析桌面参数、设置运行环境并启动现有 `create_app()`；
- 两个入口不得复制 FastAPI app、路由或业务逻辑；
- 桌面模式的单实例和 sidecar 回收由 Tauri 负责，不沿用“扫描并终止旧 BiliUp 进程”作为单实例机制。

### 2.6 桌面请求边界

桌面模式下，`POST`、`PUT`、`PATCH`、`DELETE /api/*` 必须包含公开标记：

```http
X-BiliUp-Client: desktop
```

它用于配合浏览器预检和严格 CORS 降低外部网页调用 localhost 修改接口的风险，不是密码、token 或本机恶意程序防护。前端所有 API 请求应经过统一请求方法，避免遗漏。

## 3. 计划新增或调整的文件

```text
package.json                              # Tauri 开发和构建命令
requirements-desktop.txt                  # sidecar 构建依赖
desktop/index.html                        # 后端就绪前加载/错误页
desktop/icons/                            # 桌面图标源
packaging/build_sidecar.py                # PyInstaller sidecar 构建
src-tauri/Cargo.toml                      # Rust/Tauri 依赖
src-tauri/tauri.conf.json                 # 构建、窗口、bundle、sidecar
src-tauri/capabilities/default.json       # 最小窗口权限
src-tauri/src/main.rs
src-tauri/src/lib.rs                      # 单实例、端口、sidecar 生命周期
tools/desktop_entry.py                    # 桌面专用 Uvicorn 入口
DESKTOP.md                                # 实现完成后的实际使用/构建说明
SECURITY.md                               # localhost 和公开请求头边界
tests/test_desktop_security.py            # 桌面接口和配置测试
```

现有文件预计只做以下局部修改：

- `core/configuration.py`：增加端口读取、严格校验和保留字段更新；
- `core/utils/system/directories.py`：以统一接口解析现有应用配置目录和桌面覆盖值；
- `app/main.py`：复用应用工厂，挂载桌面中间件及健康/退出路由；
- `app/static/js/*` 和必要的内联脚本：改用统一 API 请求方法；
- 后台任务/进程管理模块：提供优雅退出接口，只取消本实例持有的任务；
- `.gitignore`：忽略 sidecar、PyInstaller 和 Tauri 构建产物；
- `README.md`、`ARCHITECTURE.md`、`PRD.md`：实现完成后从“规划”更新为“已实现”。

最终文件位置以实施前审计为准；不得为了匹配文件名创建重复模块。

## 4. 分阶段实施计划

### 阶段 0：建立干净基线

工作：确认用户已验收并提交当前业务改动；记录目标提交、当前测试结果和 macOS/Windows 支持矩阵。

验证：工作树无意外修改，完整源码测试通过，当前 Web 模式可启动。

### 阶段 1：配置和运行目录兼容

工作：为现有配置增加 `desktop_port`；支持显式桌面数据目录；确保重新选择知识库保留所有兼容字段；保持 `UpList` 位于知识库。

验证：覆盖旧配置、缺失端口、边界值、布尔/字符串/越界输入、字段保留、原子写入和临时目录隔离测试；普通 Web 默认路径不变。

### 阶段 2：FastAPI 桌面协议

工作：增加稳定身份的 `/api/health`、仅桌面模式可用的优雅关闭接口、修改请求头校验，以及配置 API 的 `desktop_port`、`current_port`、`desktop_mode` 和 `restart_required`。

验证：桌面模式错误/缺失请求头返回 `403`，正确请求进入原处理器；GET 与普通 Web 模式保持兼容；健康检查可识别 BiliUp；Web 模式不能调用桌面关闭接口。

### 阶段 3：统一前端请求

工作：建立一个公共 API 请求方法并替换所有直接修改请求；设置区域展示当前端口、下次启动端口和重启提示。

验证：逐项搜索 `fetch`、XHR 和表单直提，确认无修改请求绕过封装；现有三个页签手工操作无回归。

### 阶段 4：桌面 Python 入口和退出协调

工作：新增 `desktop_entry.py`，从任意当前工作目录启动现有 FastAPI app；接收 Tauri 传入的端口和配置目录；退出前取消受管下载、线程和子进程。

验证：临时配置目录启动成功，只监听回环地址；健康检查通过；优雅退出后端口释放且无遗留受管进程；Web 入口行为不变。

### 阶段 5：最小 Tauri v2 外壳

工作：新增 Tauri crate、加载页、图标、最小 capability、单实例插件和 sidecar 声明。localhost 业务页不获得 shell/文件系统能力。

验证：Tauri 配置可解析，Rust debug/release 检查通过，后端未就绪时加载页可见。

### 阶段 6：Rust 生命周期

工作：实现读取配置端口、严格校验、端口可绑定检查、启动 sidecar、身份健康检查、导航页面、第二次启动聚焦、错误页和退出回收。只处理本实例创建的 sidecar。

验证：正常启动、重复启动、配置损坏、健康超时、端口冲突、未知 HTTP 服务占用和退出回收逐项通过。

### 阶段 7：sidecar 和安装包构建

工作：用 PyInstaller 生成 Tauri external binary 目标命名，收集 Python 模块与静态资源；增加 `sidecar:build`、`desktop:dev` 和 `desktop:build` 命令。

验证：sidecar 可单独启动并通过健康检查；当前平台 release 安装包构建成功；构建产物未进入 Git。

### 阶段 8：原生平台验收和文档收口

工作：在 macOS 和 Windows 分别构建、安装和冒烟测试；补齐 `DESKTOP.md`、`SECURITY.md`、README 和架构现状；记录未包含的签名、公证和自动更新范围。

验证：第 8 节全部满足后才视为开发完成。按项目发布规则先交用户验收，不自动发布或推送。

## 5. 固定的后续打包流程

Tauri 基础封装完成后，普通业务提交不需要重新设计架构。候选版本固定执行：

1. 选择已验证的 `dev-full` 提交并确认版本；
2. 检查是否改变依赖、静态资源、启动、配置或进程生命周期；
3. 运行完整源码测试；
4. 构建 Python sidecar；
5. 用临时配置目录单独验证 sidecar 健康和退出；
6. 运行 Rust/Tauri 检查；
7. 构建当前平台安装包；
8. 使用新配置目录和已有配置分别做安装冒烟测试；
9. 在每个承诺支持的原生平台重复构建和验证；
10. 用户验收后再更新发布文档并进入发布流程。

Python、静态网页或依赖发生变化时都必须重建 sidecar 和 Tauri 安装包；纯文档或测试修改无需单独产生安装包。

## 6. 明确不在本次范围

- 重写现有业务 UI；
- 把业务、下载或 JSONL 写入迁到 Rust；
- 搬迁现有 `config.json`、`UpList` 或视频库；
- 自动安装 OpenCLI、Chrome 扩展、Node.js、yt-dlp、FFmpeg/FFprobe；
- 代码签名、公证、SmartScreen 信誉、自动更新和发布 CI；
- 局域网或远程访问；
- 转录、调度、登录、云同步和其他非 MVP 功能。

## 7. 风险和停止条件

出现以下情况时停止实施并请用户确认：

- 现有配置目录与 Tauri 解析目录无法无迁移地统一；
- 必须移动或覆盖用户知识库数据；
- 需要给 localhost 页面开放 Tauri shell 或文件系统权限；
- 现有自动化依赖无请求头的桌面修改接口且无法兼容；
- FastAPI 不再提供同源 UI；
- 要求多个并发实例、动态端口或局域网访问；
- 当前工作树含无法与封装隔离的未验收修改。

平台风险：PyInstaller sidecar 和 Tauri 安装包不能跨系统通用；macOS 成功不代表 Windows 已通过。签名、公证和自动更新未纳入本计划。

## 8. 最终验收标准

### 自动验证

- Python 完整测试通过，普通 Web 模式无回归；
- 旧配置可直接读取，`desktop_port` 默认值和严格校验通过；
- 重新选择知识库不会丢失桌面端口或兼容字段；
- 桌面修改请求头、健康检查和关闭接口测试通过；
- Rust debug/release 检查通过；
- sidecar 使用临时配置目录独立启动和退出成功。

### 手工验证

- Tauri 开发模式从加载页进入现有 UI；
- 现有用户首次打开桌面版时无需重新选择知识库；
- 保存新端口后提示下次启动生效，重启后使用新端口；
- 第二次启动只聚焦现有窗口；
- 端口冲突、未知服务和损坏配置均显示明确错误且不修改用户数据；
- 关闭窗口后端口释放，无遗留 sidecar、下载进程或受管后台任务；
- release 安装包在新配置和已有配置两种场景下启动成功；
- OpenCLI、yt-dlp 或 FFmpeg 缺失时业务错误可理解，桌面外壳不崩溃；
- macOS 和 Windows 分别完成原生构建与安装冒烟测试。

## 9. 文档确认点

开始开发前，请确认以下决策：

1. Tauri 只做外壳，继续使用现有 FastAPI UI；
2. Web 与桌面版共用现有用户 `config.json`；
3. `desktop_port` 加入同一配置，默认 `8765`，下次启动生效；
4. `UpList`、`SortedMp4`、`OtherVideos` 保持在 `knowledge_base_root`；
5. 不迁移现有用户数据，不打包外部工具；
6. 本轮不包含签名、公证、自动更新和发布 CI；
7. macOS、Windows 必须分别构建并验收。
