# BiliUp 源码验证指南

本指南用于开发完成后的本地源码验证；不需要构建安装包。Tauri 开发运行、候选包和桌面专项验收见 [DESKTOP.md](DESKTOP.md)。

## 1. 打开项目目录

macOS 的终端中：

```bash
cd /path/to/BiliUp
```

Windows PowerShell 中，进入克隆后的 `BiliUp` 项目目录。

## 2. 创建并激活虚拟环境

首次使用时创建虚拟环境；之后只需执行激活命令。

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

激活成功后，终端提示符通常会显示 `(.venv)`。后续再次验证时：

```bash
cd /path/to/BiliUp
source .venv/bin/activate
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

后续再次验证时：

```powershell
Set-Location <BiliUp 项目目录>
.\.venv\Scripts\Activate.ps1
```

若 PowerShell 阻止执行激活脚本，请在该窗口先运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

然后重新执行激活命令。该设置仅对当前 PowerShell 窗口有效。

## 3. 启动源码服务

保持虚拟环境已激活，在项目根目录运行应用入口：

```bash
python -m app.main
```

该命令以普通 Web 模式启动在 `http://127.0.0.1:8765/`。桌面版可通过共用 `config.json` 的 `desktop_port` 修改其下次启动端口；Web 源码入口仍使用 `8765`。服务运行期间保持终端窗口打开；结束时按 `Ctrl+C`。

### 检查和释放 macOS 端口

Web 源码入口使用 `8765`。Tauri 桌面版通过单实例插件避免重复启动；若端口被其他程序占用，它会显示错误且不会终止未知程序。遇到源码服务端口占用时，可先查看占用进程：

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

输出中的 `PID` 是进程号。确认 `COMMAND` 或启动路径确实是旧版 BiliUp 后，先发送正常退出信号：

```bash
kill -TERM <PID>
```

例如：

```bash
kill -TERM 68368
```

再次检查端口是否释放：

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

只有进程仍未退出时，才使用强制终止：

```bash
kill -KILL <PID>
```

不要直接对未知 PID 或使用通配符执行 `kill`，避免终止其他程序。Windows PowerShell 可用以下命令完成同样操作：

```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen
Stop-Process -Id <PID>
```

应用启动后，另开一个终端窗口并进入项目根目录，可执行以下接口检查：

### macOS / Linux

```bash
curl -s http://127.0.0.1:8765/api/setup-status
curl -s http://127.0.0.1:8765/api/followings
curl -s http://127.0.0.1:8765/api/health
```

检查 OpenCLI 状态及搜索接口：

```bash
curl -s http://127.0.0.1:8765/api/runtime-status
curl -s -X POST http://127.0.0.1:8765/api/up-search \
  -H 'Content-Type: application/json' \
  -d '{"nickname":"示例昵称"}'

# 将 <UP_ID> 替换为 followings.json 中的 uid；刷新会调用 OpenCLI 并写入视频索引
curl -s http://127.0.0.1:8765/api/up/<UP_ID>/videos
curl -s -X POST http://127.0.0.1:8765/api/up/<UP_ID>/videos/refresh \
  -H 'Content-Type: application/json' \
  -d '{"page":1,"limit":50}'

# 批量增量同步选中的 UP（替换为实际 UID）
curl -s -X POST http://127.0.0.1:8765/api/up/videos/batch-refresh \
  -H 'Content-Type: application/json' \
  -d '{"up_ids":["<UP_ID_1>","<UP_ID_2>"]}'
curl -s http://127.0.0.1:8765/api/up/videos/batch-refresh-progress
curl -s -X POST http://127.0.0.1:8765/api/up/videos/batch-refresh-cancel

# 读取/保存批量追踪起始日期（保存到应用 config.json）
curl -s http://127.0.0.1:8765/api/settings/batch-track
curl -s -X PUT http://127.0.0.1:8765/api/settings/batch-track \
  -H 'Content-Type: application/json' \
  -d '{"since_date":"2026-07-01"}'

# 保存某个 UP 是否参与自动追踪下载（替换为实际 UID）
curl -s -X POST http://127.0.0.1:8765/api/followings/tracking \
  -H 'Content-Type: application/json' \
  -d '{"up_id":"<UP_ID_1>","scheduled_tracking":true}'

# 按 config.json 中保存的起始日期批量追踪并下载“自动追踪下载”列已启用的 UP（替换为实际 UID）
curl -s -X POST http://127.0.0.1:8765/api/up/videos/batch-track-download \
  -H 'Content-Type: application/json' \
  -d '{"up_ids":["<UP_ID_1>","<UP_ID_2>"]}'
curl -s http://127.0.0.1:8765/api/up/videos/batch-track-download-progress
curl -s -X POST http://127.0.0.1:8765/api/up/videos/batch-track-download-cancel

# 桌面端口设置会同时返回实际 config.json 路径；保存后下次桌面启动生效
curl -s http://127.0.0.1:8765/api/settings/desktop
curl -s -X PUT http://127.0.0.1:8765/api/settings/desktop \
  -H 'Content-Type: application/json' \
  -d '{"desktop_port":8765}'

# 删除选中的 UP 登记和视频索引；不会删除 SortedMp4 中的实际视频文件
curl -s -X POST http://127.0.0.1:8765/api/followings/delete \
  -H 'Content-Type: application/json' \
  -d '{"up_ids":["<UP_ID_1>"]}'

# 将 <BV_ID> 替换为刷新结果中的 bvid；下载在后台执行
curl -s -X POST http://127.0.0.1:8765/api/videos/download \
  -H 'Content-Type: application/json' \
  -d '{"up_id":"<UP_ID>","bvids":["<BV_ID>"]}'
curl -s http://127.0.0.1:8765/api/videos/download-progress
```

### Windows PowerShell

```powershell
curl.exe -s http://127.0.0.1:8765/api/setup-status
curl.exe -s http://127.0.0.1:8765/api/followings
curl.exe -s http://127.0.0.1:8765/api/health
curl.exe -s http://127.0.0.1:8765/api/runtime-status
curl.exe -s -X POST http://127.0.0.1:8765/api/up-search `
  -H "Content-Type: application/json" `
  -d '{"nickname":"示例昵称"}'
curl.exe -s http://127.0.0.1:8765/api/up/<UP_ID>/videos
curl.exe -s -X POST http://127.0.0.1:8765/api/up/<UP_ID>/videos/refresh `
  -H "Content-Type: application/json" `
  -d '{"page":1,"limit":50}'
curl.exe -s -X POST http://127.0.0.1:8765/api/up/videos/batch-refresh `
  -H "Content-Type: application/json" `
  -d '{"up_ids":["<UP_ID_1>","<UP_ID_2>"]}'
curl.exe -s http://127.0.0.1:8765/api/up/videos/batch-refresh-progress
curl.exe -s -X POST http://127.0.0.1:8765/api/up/videos/batch-refresh-cancel
curl.exe -s http://127.0.0.1:8765/api/settings/batch-track
curl.exe -s -X PUT http://127.0.0.1:8765/api/settings/batch-track `
  -H "Content-Type: application/json" `
  -d '{"since_date":"2026-07-01"}'
curl.exe -s -X POST http://127.0.0.1:8765/api/followings/tracking `
  -H "Content-Type: application/json" `
  -d '{"up_id":"<UP_ID_1>","scheduled_tracking":true}'
curl.exe -s -X POST http://127.0.0.1:8765/api/up/videos/batch-track-download `
  -H "Content-Type: application/json" `
  -d '{"up_ids":["<UP_ID_1>","<UP_ID_2>"]}'
curl.exe -s http://127.0.0.1:8765/api/up/videos/batch-track-download-progress
curl.exe -s -X POST http://127.0.0.1:8765/api/up/videos/batch-track-download-cancel
curl.exe -s http://127.0.0.1:8765/api/settings/desktop
curl.exe -s -X PUT http://127.0.0.1:8765/api/settings/desktop `
  -H "Content-Type: application/json" `
  -d '{"desktop_port":8765}'
curl.exe -s -X POST http://127.0.0.1:8765/api/followings/delete `
  -H "Content-Type: application/json" `
  -d '{"up_ids":["<UP_ID_1>"]}'
curl.exe -s -X POST http://127.0.0.1:8765/api/videos/download `
  -H "Content-Type: application/json" `
  -d '{"up_id":"<UP_ID>","bvids":["<BV_ID>"]}'
curl.exe -s http://127.0.0.1:8765/api/videos/download-progress
```

搜索和刷新接口需要 OpenCLI、Chrome 扩展和已登录的 B 站浏览器会话；搜索不会自动写入 `followings.json`，刷新会写入视频索引和 UP 统计。

检查并升级 OpenCLI：

```bash
opencli --version
npm install -g @jackwener/opencli@latest
opencli doctor
```

视频下载还需要 `yt-dlp`。验证下载前先检查：

```bash
yt-dlp --version
```

单个下载任务按 `480p`、`720p`、`1080p`、`best` 从低到高尝试，进度接口中的 `error` 字段会显示 OpenCLI/yt-dlp 的简要错误；下载成功后会按知识库规则命名视频，并尝试生成相邻的 `_cover.jpg` 或 `_cover.webp` 封面和 `__transcript.md` 字幕脚本。

## 4. 运行自动化测试

停止服务后，在项目根目录运行：

```bash
python -m unittest discover -s tests -v
```

也可不激活虚拟环境，直接使用其解释器：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

所有测试通过，并完成手动验证后，才可将该版本作为待提交版本。

若本次修改涉及桌面入口、配置、打包脚本或 `src-tauri/`，还需运行：

```bash
cargo check --manifest-path src-tauri/Cargo.toml
cargo test --manifest-path src-tauri/Cargo.toml --lib
```

Windows PowerShell 使用相同命令。安装包必须在对应原生系统另行构建和验收，不能用本节检查替代。

## 5. 查看当前 UpList 数据

正式数据不保存在项目目录，而是保存在首次配置时选择的知识库目录下的 `UpList/`。先查看应用配置中的 `knowledge_base_root`，再检查该目录。

### macOS

```bash
cat "$HOME/Library/Application Support/BiliUp/config.json"
```

将输出中的 `knowledge_base_root` 替换到以下命令的路径中：

```bash
ls -la "<knowledge_base_root>/UpList"
ls -la "<knowledge_base_root>/UpList" | grep '\.jsonl$'
ls -la "<knowledge_base_root>/SortedMp4"
```

### Windows PowerShell

```powershell
Get-Content "$env:LOCALAPPDATA\BiliUp\config.json"
```

将输出中的 `knowledge_base_root` 替换到以下命令的路径中：

```powershell
Get-ChildItem "<knowledge_base_root>\UpList"
Get-ChildItem "<knowledge_base_root>\UpList\*.jsonl"
Get-ChildItem "<knowledge_base_root>\SortedMp4"
```

其中 `followings.json` 是唯一的正式数据真源，`bilibili-up-followings.md` 是由它生成的可读表格。项目根目录若存在旧 `UpList/`，不属于当前配置的写入目标。

## 6. 退出虚拟环境

验证结束后可运行：

```bash
deactivate
```

`.venv/` 是本机开发环境，已被 Git 忽略，不应提交。
