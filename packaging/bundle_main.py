# Entry point of the single-file bundle cam4linux.pyz (double-click to install/start)
import os
import sys

from cam4linux.install import run_bundle

if __name__ == "__main__":
    sys.exit(run_bundle(os.path.dirname(os.path.abspath(__file__))))
