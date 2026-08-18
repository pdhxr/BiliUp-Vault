# BiliUp Tauri 封装执行指南

> 用途：把本项目的其他分支封装为 Tauri v2 桌面应用，并让执行任务的 AI 有明确、可验证的实施规则。
>
> 参考实现：当前仓库的 `dev-full` 分支。另一分支的文件位置和接口可能不同，执行时应先审计，再迁移设计；不要机械复制整份文件。

> BiliUp 当前项目适配：现有用户配置固定在 macOS `~/Library/Application Support/BiliUp/config.json` 或 Windows `%LOCALAPPDATA%\BiliUp\config.json`；`UpList`、`SortedMp4` 和 `OtherVideos` 位于用户选择的 `knowledge_base_root`。Tauri 必须复用现有用户配置且不得移动知识库数据。实施计划见 `TAURI_DEVELOPMENT_PLAN.md`。

## 1. 目标与完成标准

桌面版采用“Tauri 外壳 + Python sidecar + 原有 FastAPI 页面”的结构：

```text
Tauri 主进程
  ├─ 保证桌面应用单实例
  ├─ 读取并校验固定端口
  ├─ 启动和持有 Python sidecar
  ├─ 等待 BiliUp 健康检查通过
  └─ 将窗口导航到 http://127.0.0.1:<port>/
                                │
                                ▼
                     FastAPI 页面与 /api/*
                                │
                                ▼
                   原有业务、配置和数据 Store
```

封装完成后必须同时满足：

- 原有 Web 开发模式仍可独立运行；
- 安装版无需用户手动启动 FastAPI；
- 桌面应用、Python 后端和后台任务具有一致的启动、退出生命周期；
- 固定端口可配置，端口冲突不会误连或结束其他程序；
- 桌面服务只监听回环地址；
- 桌面模式下的修改类 API 使用公开请求头标记；
- Tauri 不直接读写 JSONL 或接管 Python 业务逻辑；
- 开发、测试、构建和安装包启动均经过验证。

## 2. 为什么选择 Tauri

### 2.1 适合当前项目的原因

1. **能保留现有应用。** 本项目已经有 FastAPI 后端和完整 Web UI。Tauri 只负责窗口和进程管理，不需要重写前端或业务层。
2. **适合封装 Python sidecar。** Python 服务可以构建为目标平台可执行文件，由 Tauri 启动、监控和退出时回收。
3. **桌面外壳较轻。** Tauri 使用系统 WebView，不随应用携带完整浏览器运行时。实际安装包大小仍取决于 Python、依赖和资源，不能只用空项目体积估算。
4. **生命周期边界清晰。** Rust 主进程可以统一处理单实例、端口检测、健康检查、启动失败页面和后端退出。
5. **权限可收敛。** localhost 页面不需要获得 shell、文件系统等 Tauri 权限；这些操作继续通过受控的 Python API 完成。
6. **不破坏 Web 模式。** 同一套 FastAPI 页面仍能用于开发和故障排查。

### 2.2 本次选择不代表什么

- Tauri 不是 Python 业务层的替代品；不要把下载、索引或文件整理逻辑迁到 Rust。
- 固定 localhost 端口不是安全认证机制。
- PyInstaller sidecar 不能跨操作系统通用，必须按目标平台构建和测试。
- 当前 MVP 不自动打包 OpenCLI、Browser Bridge、浏览器扩展、FFmpeg/FFprobe；它们仍是系统依赖，除非目标分支另有明确方案。
- 代码签名、公证、自动更新和发布流水线不在基础封装范围内，应作为单独任务处理。

## 3. 不可自行改变的架构决策

执行 AI 必须遵守以下规则。若目标分支无法满足，应先说明冲突，不得静默改成另一套架构。

| 主题 | 规则 |
|---|---|
| 业务边界 | Tauri 管窗口、单实例和 sidecar；FastAPI 保留页面与业务 API |
| 数据写入 | Rust 不直接写 JSONL；继续使用 Python Store、跨进程锁、临时文件和原子替换 |
| 页面来源 | 后端就绪后加载 FastAPI 提供的同源页面，不建立第二套桌面前端 |
| 监听地址 | 只允许 `127.0.0.1`，不得使用 `0.0.0.0` 或局域网地址 |
| 端口 | 默认 `8765`，配置键 `desktop_port`，允许 `1024–65535` |
| 单实例 | 使用 Tauri 单实例能力；不能以“端口已占用”代替单实例判断 |
| 请求标记 | 桌面模式修改类 `/api/*` 请求要求 `X-BiliUp-Client: desktop` |
| 跨域 | 不开放通配 CORS，不允许任意网页跨域调用本地 API |
| 数据目录 | 安装版使用系统应用数据目录；视频库仍由 `library_root` 单独指定 |
| 退出 | 先请求后端优雅退出，再由 Tauri 回收其持有的 sidecar |
| 权限 | localhost 业务页面不获得 Tauri shell 或文件系统权限 |

## 4. 在目标分支开始前先审计

不要先安装依赖或复制 `src-tauri/`。先形成一份简短审计记录，至少回答：

1. 该分支的 `AGENTS.md`、`README.md`、`ARCHITECTURE.md` 和数据模型文档有哪些额外约束？
2. FastAPI 应用对象和 Web 启动入口在哪里？是否固定依赖当前工作目录？
3. 静态页面、图标及运行时只读资源在哪里？PyInstaller 需要收集哪些目录？
4. `config.json` 由谁读写？是否已有原子写入函数和配置 API？
5. `UpList/`、日志、下载临时目录等可写路径是否仍由项目根目录常量决定？
6. 视频库根目录是否与应用状态目录分离？
7. 前端是否有统一请求函数？搜索所有 `fetch`、XHR 和表单直提，找出绕过统一函数的修改请求。
8. 服务退出时有哪些下载进程、调度器、线程或子进程需要先取消？
9. 是否已有 `/api/health`、关闭接口、TrustedHost 或 CORS 配置？
10. 当前测试怎样启动服务？工作树是否有用户未提交的修改？

审计后建立“目标分支路径 → 本指南角色”的映射。例如目标分支没有 `tools/server.py` 时，应修改实际 FastAPI 入口，不能为了与指南同名而新建重复服务。

## 5. 建议的交付结构

文件名可以适配目标分支，但职责应保持一致：

```text
项目根目录/
├── package.json
├── requirements-desktop.txt
├── desktop/
│   ├── index.html                  # 后端启动前的本地加载/错误页
│   └── icons/                      # Tauri 安装包图标源
├── packaging/
│   └── build_sidecar.py            # PyInstaller + target 命名
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── capabilities/default.json
│   ├── icons/
│   ├── binaries/                   # 构建产物，不提交
│   └── src/
│       ├── main.rs
│       └── lib.rs                  # 生命周期、端口和 sidecar
├── tools/
│   └── desktop_entry.py            # 桌面专用 Uvicorn 入口
├── DESKTOP.md                      # 当前分支实际使用说明
├── SECURITY.md                     # 请求头的边界和公开协议
└── tests/
    └── test_desktop_security.py
```

`TAURI_PACKAGING_GUIDE.md` 是跨分支执行规则；`DESKTOP.md` 应记录目标分支最终实际实现。两者不要混为一份容易过期的文档。

## 6. 实施顺序

每一步都要完成右侧验证后再继续。改动应小而可追踪，不顺手重构无关代码。

### 步骤 1：整理运行时路径

使 Python 后端能从显式数据目录读取和写入运行数据：

- `BILIUP_DATA_DIR`：显式覆盖数据目录，优先级最高；
- 安装版：由 Tauri 传入系统应用数据目录；
- 桌面开发版：默认沿用项目根目录，可用 `BILIUP_DEV_DATA_DIR` 隔离；
- 普通 Web 模式：保持该分支原有目录行为。

应放入应用数据目录的通常包括 `config.json` 和日志；已经明确属于用户知识库的数据不得迁移。BiliUp 当前项目的 `UpList/`、`SortedMp4/` 和 `OtherVideos/` 均继续位于 `knowledge_base_root`。静态页面、Python 模块等只读资源属于应用资源。`knowledge_base_root` 不能因桌面封装被重置到应用数据目录。

验证：用临时 `BILIUP_DATA_DIR` 启动后端，确认配置和应用运行状态只写入临时目录，知识库数据仍写入临时配置所指向的 `knowledge_base_root`，并且 Web 默认模式没有改变。

### 步骤 2：增加端口配置

在现有配置读写路径上增加 `desktop_port`，不要建立第二份配置文件。

- 缺失时返回默认值 `8765`；
- 保存时严格校验整数和范围；
- 配置 API 同时返回 `desktop_port`、`current_port`、`desktop_mode` 和实际 `config_file` 路径；
- 保存结果返回 `restart_required`；
- UI 在设置区域展示“本次端口”和“下次启动端口”。
- 普通 Web 与桌面模式共用现有用户 `config.json`；重新选择知识库或保存其他字段时必须保留 `desktop_port` 和未知兼容字段；
- `src-tauri/tauri.conf.json` 只记录构建、窗口、bundle、图标和 sidecar，不保存用户设置。

验证：默认值、边界值、字符串、布尔值、越界值及保存后重启提示均有测试。

### 步骤 3：统一桌面请求头

后端仅在 `BILIUP_DESKTOP=1` 时，对 `POST`、`PUT`、`PATCH`、`DELETE /api/*` 校验：

```http
X-BiliUp-Client: desktop
```

前端所有 API 请求必须经过一个统一方法，由该方法添加请求头。即使普通 Web 模式不强制，也可以始终发送该公开标记。逐个检查直接 `fetch`，确保没有修改类请求遗漏。

验证：桌面模式修改请求无头返回 `403`，错误值返回 `403`，正确值进入原处理器；只读 GET 和 Web 模式原有调用不被阻断。

### 步骤 4：增加桌面健康检查和退出入口

- `GET /api/health` 返回稳定的应用身份，例如 `{"app":"biliup","status":"ok"}`；
- `POST /api/desktop/shutdown` 只在桌面模式启用，并受请求头规则保护；
- 桌面入口把退出回调连接到 Uvicorn 的 `should_exit`；
- 应用关闭流程先取消正在运行的下载和受管子进程，再结束服务器。

健康检查不能只判断端口能连接，否则可能把其他服务误认为 BiliUp。

验证：健康响应包含稳定身份；Web 模式关闭接口不可用；桌面模式能够优雅停止监听。

### 步骤 5：建立桌面 Python 入口

桌面入口只负责：解析 `--port` 和 `--data-dir`、设置桌面环境变量、首次创建最小合法配置、在 `127.0.0.1` 上以单 worker 启动现有 FastAPI app。

至少设置：

```text
BILIUP_DESKTOP=1
BILIUP_CURRENT_PORT=<本次端口>
BILIUP_DATA_DIR=<应用数据目录>
```

首次配置要用临时文件和原子替换。不要在入口复制业务路由或创建第二个 FastAPI app。

验证：从任意当前工作目录启动入口都能找到模块和静态资源；退出后端口释放。

### 步骤 6：建立最小 Tauri v2 外壳

增加 Tauri 配置、Rust crate、本地加载页、图标和构建命令。最低依赖包括单实例插件；发布版启动 sidecar 时使用 shell 插件。capability 只授予加载页所需的 `core:default`，不要把 shell 或文件系统能力暴露给随后加载的 localhost 页面。

建议命令：

```json
{
  "scripts": {
    "desktop:dev": "tauri dev",
    "sidecar:build": "python packaging/build_sidecar.py",
    "desktop:build": "tauri build"
  }
}
```

验证：Tauri 配置可解析，`cargo check` 通过，本地加载页在后端未就绪时可见。

### 步骤 7：实现 Rust 生命周期

启动顺序必须是：

1. 单实例插件先处理第二次启动；
2. 计算数据目录并创建目录；
3. 读取 `config.json` 的 `desktop_port`；
4. 严格校验配置；
5. 检查端口当下是否可绑定；
6. 启动并保存 sidecar 句柄；
7. 轮询健康检查，确认 BiliUp 身份；
8. 成功后导航到 localhost 页面；
9. 超时则停止 sidecar，并在窗口显示错误和配置路径。

第二次启动只能显示、还原和聚焦已有窗口，不得启动另一个后端。退出时向关闭接口发送正确请求头，短暂等待优雅退出，然后对仍存在的受管 sidecar 执行兜底回收。不得扫描或结束不是本实例创建的进程。

验证：正常启动、第二次启动、健康超时、端口冲突、退出回收五条路径逐项测试。

### 步骤 8：构建 Python sidecar

使用 PyInstaller 单文件模式收集入口及静态资源，并通过：

```text
rustc --print host-tuple
```

取得当前 Rust target。输出必须符合 Tauri external binary 命名：

```text
src-tauri/binaries/biliup-backend-<target>[.exe]
```

PyInstaller 的 cache、work、dist、spec 以及 Tauri target、生成 schema 和 sidecar 二进制均应加入 `.gitignore`。不要提交本机可执行产物。

验证：直接运行生成的 sidecar，通过临时数据目录完成健康检查；随后执行当前平台 release 构建。

### 步骤 9：补齐说明和测试

至少同步修改：

- `README.md`：桌面开发、构建、依赖和入口；
- `ARCHITECTURE.md`：Tauri/FastAPI 边界、数据目录和生命周期；
- `DESKTOP.md`：目标分支的实际命令、端口与发布检查；
- `SECURITY.md`：请求头为什么公开、能防什么、不能防什么；
- `config.example.json`：加入 `desktop_port`；
- 测试：端口配置、请求头、健康检查和退出接口。

文档中不得把公开固定请求头描述为 token、密码或密钥。

## 7. 固定端口的完整规则

### 7.1 配置与生效

| 情况 | 行为 |
|---|---|
| `config.json` 不存在 | 使用 `8765`；桌面入口可创建最小配置 |
| `desktop_port` 缺失 | 使用 `8765`，不因读取而改写用户文件 |
| 合法值 | 必须是整数 `1024–65535` |
| 布尔、空值、小数、非数字或越界 | 保存 API 返回 `400`；启动页显示配置错误 |
| UI 保存新端口 | 只影响下次启动，不在线重绑服务 |
| 手动改配置 | 建议完全退出应用后编辑，下次启动生效 |

后端配置 API 应区分：

- `desktop_port`：配置中的下次启动端口；
- `current_port`：本次进程实际监听端口；
- `restart_required`：桌面模式且两者不同时为真。

### 7.2 端口冲突

启动前检查 `127.0.0.1:<port>` 能否绑定，但要认识到检查和 sidecar 实际绑定之间存在短暂竞态，因此最终以 sidecar 启动及健康检查为准。

端口不可用或 sidecar 无法绑定时：

- 在 Tauri 窗口显示端口和配置文件绝对路径；
- 不自动切换随机端口；
- 不连接端口上已有的未知服务；
- 不结束占用端口的未知进程；
- 若健康响应、PID 和可执行文件均能确认属于旧 BiliUp，可先请求优雅退出，超时后只回收该已确认进程；
- 不修改用户配置；
- 用户修改端口并重新启动后再尝试。

固定端口方便书签、排障、配置管理和外部本地自动化，但**单实例必须由 Tauri 单实例插件保证**。端口占用只代表资源冲突，不等于“已有 BiliUp 正在运行”。

### 7.3 端口不是安全边界

无论端口固定还是动态，都只能监听 `127.0.0.1`。端口号不保密，也不能阻止本机其他程序调用 API；不要以更换端口代替请求约束或操作系统隔离。

## 8. 请求头规则与安全边界

固定请求头是浏览器跨站请求防护标记，不是认证 token：

```http
X-BiliUp-Client: desktop
```

它应与源码、配置方法、验证逻辑和测试一起提交到 MIT 开源仓库，不放入 `.env`，不要求用户生成，也不进入密钥管理。它的作用是让普通外部网页向固定 localhost 端口发起修改请求时触发 CORS 预检；由于后端不允许该外部来源，浏览器会阻止请求。

规则如下：

- 桌面模式的 `POST`、`PUT`、`PATCH`、`DELETE /api/*` 必须校验；
- 健康检查和只读 GET 不要求该标记；
- 前端统一 API 方法自动添加；
- 不设置 `Access-Control-Allow-Origin: *`，也不反射任意 Origin；
- 桌面模式可使用 TrustedHost，只接受 `127.0.0.1`；
- 普通 Web 模式是否强制取决于已有自动化兼容性。本项目基线为仅桌面模式强制；目标分支改变此规则前必须审计所有脚本客户端。

该请求头不能防止本机恶意程序，也不能授权局域网、远程页面或第三方插件。如果未来扩大访问范围，必须重新设计真实的身份认证和授权。

## 9. 数据和资源规则

| 类型 | 安装版位置 | 说明 |
|---|---|---|
| 用户配置、应用日志 | 现有 BiliUp 应用数据目录 | Web 与桌面模式共用；不得因 Tauri bundle identifier 生成第二份配置 |
| UP 追踪、视频、字幕和索引 | 用户配置的 `knowledge_base_root` | 保持 `UpList`、`SortedMp4`、`OtherVideos` 现有结构，不擅自迁移 |
| 静态页面和 Python 模块 | 安装包/sidecar 资源 | 运行时只读 |
| 临时构建产物 | 项目 `build/`、`target/` 等 | 不提交 Git |

涉及 `UpList/{昵称}.jsonl` 和 `<library_root>/SortedMp4/{昵称}/videos.jsonl` 的规则不因桌面封装改变：所有写入仍必须使用跨进程锁、临时文件和原子替换；同时协调时保持项目规定的锁顺序。Tauri/Rust 不新增数据写入口。

## 10. 构建与发布规则

基础开发流程：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-desktop.txt
npm install
npm run desktop:dev
```

当前平台构建：

```bash
npm run desktop:build
```

不要把“在 macOS 构建成功”视为 Windows 或 Linux 已支持。每个发布目标都要在目标平台或可信兼容环境中重新生成 sidecar、构建安装包并做启动测试。至少建立以下发布矩阵：

- macOS Apple Silicon；
- macOS Intel（若项目承诺支持）；
- Windows x64；
- 项目选定的 Linux 发行格式。

图标必须用 Tauri 生成或接受的各平台格式，不要只放一张 PNG 后假定所有安装器都可用。

## 11. 验收清单

### 11.1 自动测试

- [ ] `desktop_port` 缺失时为 `8765`；
- [ ] `1024` 和 `65535` 可保存；
- [ ] 布尔、非整数、`1023`、`65536` 被拒绝；
- [ ] 桌面模式修改请求无头/错误头为 `403`；
- [ ] 正确请求头可以调用修改 API；
- [ ] Web 模式现有修改请求保持兼容；
- [ ] `/api/health` 返回稳定 BiliUp 身份；
- [ ] Web 模式不能调用桌面关闭接口；
- [ ] Rust debug 和 release 检查通过。

### 11.2 手工冒烟测试

- [ ] `npm run desktop:dev` 显示加载页并进入原有 UI；
- [ ] UI 保存新端口后提示下次启动生效；
- [ ] UI 显示实际 `config.json` 完整路径；
- [ ] 重启后只监听新端口；
- [ ] 第二次启动只聚焦已有窗口，不创建第二个后端；
- [ ] 预占配置端口后启动，窗口显示冲突及配置路径；
- [ ] 端口上运行另一个 HTTP 服务时，不误判为 BiliUp；
- [ ] 已确认身份的旧 BiliUp 后端可被安全接管，未知进程不被终止；
- [ ] 配置 JSON 损坏时显示错误，不静默覆盖；
- [ ] 关闭窗口后监听端口释放，没有遗留 sidecar 或下载进程；
- [ ] release 安装包在新数据目录首次启动成功；
- [ ] OpenCLI、浏览器桥接或 FFmpeg 缺失时显示可理解错误，不导致应用外壳崩溃。

## 12. AI 执行约束

执行此指南的 AI 应：

1. 先报告审计结果、路径映射、假设和计划，再修改代码；
2. 保留用户工作树中的无关修改，不重排或清理相邻代码；
3. 先复用现有配置和请求封装，不创建重复抽象；
4. 每完成一个步骤就运行对应检查，失败则定位原因后再继续；
5. 不下载或引入超出 Tauri 封装所需的依赖；
6. 不把外部工具打包、签名、公证、更新器等范围自动加入本任务；
7. 同步更新多份项目文档，确保实现、操作说明和安全说明一致；
8. 最终列出改动文件、验证结果、剩余平台风险和提交哈希；
9. 按项目规范创建一个原子提交；若目标分支规则要求拆分提交，以目标分支规则为准。

出现以下情况应停止并向用户说明，而不是自行选方案：

- 目标分支已经使用另一个桌面框架或远程服务；
- FastAPI 不再是 UI 的同源服务；
- 应用必须允许局域网访问；
- 端口必须由多个并发实例共享或动态分配；
- 配置目录迁移可能覆盖或移动现有用户数据；
- 现有自动化大量依赖无请求头的修改接口，且无法确认兼容策略；
- 需要扩大 Tauri shell/文件系统权限才能完成新增需求。

## 13. 可直接交给 AI 的任务指令

```text
请先完整阅读 AGENTS.md、TAURI_PACKAGING_GUIDE.md，以及其中要求审计的项目文档。
目标是在当前分支按指南添加 Tauri v2 桌面外壳。

先不要改代码。先输出：
1. 当前分支与指南角色对应的文件路径；
2. 数据目录、FastAPI 入口、前端请求封装和后台进程的审计结果；
3. 需要保留的分支差异与明确假设；
4. 按“步骤 → 验证”格式列出的实施计划。

随后按指南最小化实施。不可改变的规则包括：Tauri 只管理外壳和 sidecar；
固定可配置端口默认 8765、范围 1024–65535、下次启动生效；单实例独立于端口；
只监听 127.0.0.1；端口冲突不自动换端口、不误连、不结束未知进程；
桌面模式修改类 /api/* 校验 X-BiliUp-Client: desktop；不开放通配 CORS；
Rust 不直接写 JSONL；安装版状态使用应用数据目录，视频库保持独立。

逐步验证并完成自动测试、桌面冒烟测试、release 构建和文档同步。
保留无关修改，最后按项目规范做原子提交，并报告提交哈希和未覆盖的平台验证。
```
