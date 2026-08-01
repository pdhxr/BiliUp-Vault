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
