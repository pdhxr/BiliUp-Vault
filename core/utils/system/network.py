import socket


def available_local_port(preferred: int = 8765) -> int:
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
            return int(probe.getsockname()[1])
    raise RuntimeError("无法分配本地服务端口")
