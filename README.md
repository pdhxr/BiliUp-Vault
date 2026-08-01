# BiliUp

BiliUp 是跨 macOS 和 Windows 的本地 B 站 UP 主搜索与登记工具。

当前 MVP：通过 OpenCLI 搜索 UP 主，展示昵称、UP ID 和简介，用户确认后写入本地 UpList。

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

7. 确认搜索命令能够返回 JSON：

   ```bash
   opencli bilibili search "测试昵称" --type user -f json
   ```

只有 `opencli doctor` 的 Daemon、Extension 和 Connectivity 检查正常后，BiliUp 的搜索功能才能使用。若检查失败，请先确认 Chrome 已启动、扩展已启用且 B 站仍处于登录状态，然后重新执行检查。

### 为什么需要浏览器登录

B 站用户搜索是 OpenCLI 的浏览器型命令，需要从已登录的 Chrome 会话获取访问凭据。BiliUp 不保存 B 站密码，也不要求用户把 Cookie、令牌或密码写入项目文件。

## macOS 安装包使用方法

1. 下载并打开 `BiliUp.dmg`。
2. 将 `BiliUp.app` 拖入“应用程序”目录。
3. 首次启动时双击 `BiliUp.app`。
4. 如果 macOS 阻止未签名应用，右键点击应用，选择“打开”，再确认一次。
5. 应用启动本机 FastAPI 服务并打开 WebUI。
6. 输入 UP 主昵称，在结果中单选一项，点击“确认写入”。

当前 macOS 包尚未进行 Apple 开发者签名和公证，因此首次启动可能出现系统安全提示。

## Windows 安装包使用方法

Windows 安装包必须在 Windows 原生环境构建。构建完成后：

1. 解压完整的 `BiliUp` 目录，不要只复制其中的 EXE。
2. 双击 `BiliUp.exe`。
3. 如果 Windows SmartScreen 提示未知发布者，确认文件来源后选择“更多信息”→“仍要运行”。
4. 应用启动本机 FastAPI 服务并打开 WebUI。
5. 输入 UP 主昵称，在结果中单选一项，点击“确认写入”。

当前项目已提供 Windows 构建脚本，但尚未在 Windows 原生环境生成和验证 EXE。

## 数据保存位置

源码模式从项目根目录启动时，数据写入：

```text
UpList/followings.json
UpList/bilibili-up-followings.md
```

- `followings.json` 是唯一数据真源。
- `bilibili-up-followings.md` 是自动生成的可读表格。
- 仅执行搜索不会写文件；选择结果并点击“确认写入”后才会保存。

已知限制：当前打包版的相对数据目录仍受应用启动工作目录影响，尚未固定到统一的用户数据目录。正式使用安装包保存数据前，需要先完成该路径修复。

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

## 构建安装包

macOS 生成 `.app` 与 `.dmg`：

```bash
.venv/bin/python scripts/build.py macos
```

Windows 生成 EXE 目录（必须在 Windows 原生环境执行）：

```powershell
.\.venv\Scripts\python.exe scripts\build.py windows
```

构建产物位于 `dist/`，不提交 Git。macOS 和 Windows 必须分别在对应原生系统构建与验证，PyInstaller 不支持从 macOS 直接生成可验证的 Windows EXE。

## 当前发布限制

- OpenCLI、Node.js、Chrome 扩展与 B 站浏览器登录尚未被安装包自动处理。
- GUI 启动的应用需要能够从系统环境中找到 `opencli` 命令。
- macOS 包尚未签名、公证；Windows EXE 尚未原生构建、签名和验证。
- 打包版 UpList 的固定保存位置仍待修复。

这些限制解决前，推荐从项目根目录使用源码模式测试完整搜索和写入流程。
