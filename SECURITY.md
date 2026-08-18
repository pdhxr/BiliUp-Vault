# BiliUp 桌面安全边界

## 本机服务

桌面 sidecar 只监听 `127.0.0.1`，不监听 `0.0.0.0` 或局域网地址。默认端口为 `8765`，端口号不是秘密，也不是认证手段。

Tauri 启动后端前检查端口是否可绑定，并使用 `GET /api/health` 的稳定 BiliUp 身份确认 sidecar 就绪。端口冲突时不自动更换端口、不连接未知服务、不结束身份不明的占用进程。

若占用端口的是健康响应、PID 和可执行文件身份均可确认的旧 BiliUp 后端，应用会先请求其优雅退出；超时后才回收该旧进程。身份无法确认时始终拒绝终止。

## 桌面请求标记

桌面模式的 `POST`、`PUT`、`PATCH`、`DELETE /api/*` 要求：

```http
X-BiliUp-Client: desktop
```

该值公开保存在源码中，不是 token、密码或密钥。它的作用是让普通外部网页向 localhost 发送带自定义头的修改请求时触发浏览器 CORS 预检；BiliUp 不开放通配 CORS，因此不受信任网页不能直接完成这类跨域请求。

该标记不能防止本机恶意程序。本项目若未来开放局域网、远程访问或第三方客户端，必须重新设计真实认证和授权。

## Tauri 权限

localhost 业务页面只获得 `core:default` capability，不获得 Tauri shell 或文件系统权限。sidecar 由 Rust 主进程启动，shell 能力不暴露给网页。

Rust 不读写 `followings.json`、JSONL、视频、字幕或封面。用户配置由 Python 配置模块原子写入，业务数据继续由 Python repositories 管理。

## 进程退出

关闭窗口时，Tauri 先调用受保护的后端关闭接口。Python 停止接受新下载任务、通知批量任务取消并终止本实例管理的 OpenCLI/FFmpeg 进程；短暂等待后，Tauri 对仍存在的本实例 sidecar 执行兜底回收。应用不扫描或终止未知进程。

日志不得记录 Cookie、令牌、凭据或完整 OpenCLI 原始输出。
