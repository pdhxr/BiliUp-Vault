import argparse
from core.utils.system.packaging import build_package


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 BiliUp 安装包")
    parser.add_argument("target", choices=("macos", "windows"))
    build_package(parser.parse_args().target)


if __name__ == "__main__":
    main()
