# BiliUp

BiliUp 是跨 macOS 和 Windows 的本地 B 站 UP 主搜索与登记工具。

当前 MVP：首次选择视频知识库目录后，通过 OpenCLI 搜索 UP 主，展示昵称、UP ID 和简介，用户确认后写入该知识库的 UpList。输入昵称不会自动搜索，只有点击“搜索”按钮才会调用 OpenCLI；搜索期间按钮置灰并显示“搜索中…”。搜索结果区默认显示约 3–5 项，其余结果可在列表内滚动查看；“确认写入”按钮位于结果列表上方。

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

BiliUp 首次启动会检查 OpenCLI。未安装或无法运行时，首页显示安装提示并禁用搜索；安装完成并重新启动 BiliUp 后会自动重新检测。已安装在 Homebrew、npm、NVM 或 Volta 常见位置的 OpenCLI，即使从 Finder 双击应用也会被系统适配层查找。

### 为什么需要浏览器登录

B 站用户搜索是 OpenCLI 的浏览器型命令，需要从已登录的 Chrome 会话获取访问凭据。BiliUp 不保存 B 站密码，也不要求用户把 Cookie、令牌或密码写入项目文件。

## macOS 安装包使用方法

1. 下载并打开 `BiliUp.dmg`。
2. 将 `BiliUp.app` 拖入“应用程序”目录。
3. 首次启动时双击 `BiliUp.app`。
4. 如果 macOS 阻止未签名应用，右键点击应用，选择“打开”，再确认一次。
5. 应用启动本机 FastAPI 服务并打开 WebUI。
6. 首次使用时，点击“选择视频知识库目录”，在 Finder 中选择一个已存在、可写的长期保存目录。
7. 输入 UP 主昵称，点击“搜索”，在结果中单选一项，点击“确认写入”。

当前 macOS 包尚未进行 Apple 开发者签名和公证，因此首次启动可能出现系统安全提示。

## Windows 安装包使用方法

Windows 安装包必须在 Windows 原生环境构建。构建完成后：

1. 解压完整的 `BiliUp` 目录，不要只复制其中的 EXE。
2. 双击 `BiliUp.exe`。
3. 如果 Windows SmartScreen 提示未知发布者，确认文件来源后选择“更多信息”→“仍要运行”。
4. 应用启动本机 FastAPI 服务并打开 WebUI。
5. 首次使用时，点击“选择视频知识库目录”，在 Windows 目录选择框中选择一个已存在、可写的长期保存目录。
6. 输入 UP 主昵称，点击“搜索”，在结果中单选一项，点击“确认写入”。

当前项目已提供 Windows 构建脚本，但尚未在 Windows 原生环境生成和验证 EXE。

## 数据保存位置

首次选择的视频知识库目录是所有用户数据的根目录。当前 MVP 写入：

```text
<知识库目录>/UpList/followings.json
<知识库目录>/UpList/bilibili-up-followings.md
```

- `followings.json` 是唯一数据真源。
- `bilibili-up-followings.md` 是自动生成的可读表格。
- 仅执行搜索不会写文件；选择结果并点击“确认写入”后才会保存。
- 已存在于项目根目录的旧 `UpList/` 不会自动迁移；后续登记以用户选择的新知识库目录为准。

应用配置文件不在安装包或项目目录中：macOS 为 `~/Library/Application Support/BiliUp/config.json`，Windows 为 `%LOCALAPPDATA%\BiliUp\config.json`。其中保存用户选择的知识库绝对路径；这是用户选择的受控配置值，不是硬编码路径。

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
