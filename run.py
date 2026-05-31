"""Entry point for the standalone (PyInstaller) build and `python run.py`."""

import sys

from mizuno_menace.cli import main

if __name__ == "__main__":
    sys.exit(main())
