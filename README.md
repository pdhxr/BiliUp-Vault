# BiliUp

跨 macOS 和 Windows 的本地 B 站 UP 主搜索与登记工具。

当前 MVP：通过 OpenCLI 搜索 UP 主，展示昵称、UP ID 和简介，并写入项目内相对目录 `UpList/`。

产品需求见 [PRD.md](PRD.md)，架构说明见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 本机开发环境

虚拟环境实现于项目根目录的 `.venv/`，不提交 Git。

macOS：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

运行、测试和打包命令会在对应功能实现后补充。依赖变更时同步更新 `requirements.txt`。

## 运行与打包

源码运行：

```bash
.venv/bin/python -m app.main
```

macOS 生成 `.app` 与 `.dmg`：

```bash
.venv/bin/python scripts/build.py macos
```

Windows 生成 `.exe`（必须在 Windows 原生环境执行）：

```powershell
.venv\Scripts\python.exe scripts\build.py windows
```

构建产物位于 `dist/`，不提交 Git。打包后的应用内置 Python 运行时，不依赖用户本机 `.venv`；UP 搜索仍需要可用且已配置的 OpenCLI，后续发布版需将 OpenCLI 运行时一并交付。
