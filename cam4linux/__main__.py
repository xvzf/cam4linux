import sys


def main():
    args = sys.argv[1:]
    if "--daemon" in args:
        from .daemon import main as run
    elif "--install" in args or "--uninstall" in args:
        from . import install
        return install.main(args)
    elif "--status" in args:
        import json
        from .config import read_status
        print(json.dumps(read_status(), indent=2, ensure_ascii=False))
        return 0
    else:
        from .gui import main as run
    return run()


if __name__ == "__main__":
    sys.exit(main())
