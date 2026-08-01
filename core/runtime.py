import subprocess

from core.utils.system.process import find_opencli, run_opencli


def opencli_status() -> dict[str, object]:
    if find_opencli() is None:
        return {
            "installed": False,
            "ready": False,
            "message": "未检测到 OpenCLI。请先安装 Node.js 21+ 和 OpenCLI，然后配置 Chrome 扩展并登录 B 站。",
        }
    try:
        result = run_opencli(["--version"], timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return {
            "installed": True,
            "ready": False,
            "message": "已找到 OpenCLI，但无法运行。请检查 Node.js 安装和 OpenCLI 配置。",
        }
    if result.returncode != 0:
        return {
            "installed": True,
            "ready": False,
            "message": "已找到 OpenCLI，但无法运行。请检查 Node.js 安装和 OpenCLI 配置。",
        }
    return {
        "installed": True,
        "ready": True,
        "message": "已检测到 OpenCLI。搜索前请保持 Chrome 运行、启用 OpenCLI 扩展并登录 B 站。",
    }
