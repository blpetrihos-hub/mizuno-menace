"""Filesystem locations that work both from source and as a frozen exe.

When packaged with PyInstaller the app is a single self-contained .exe. Config
files (products.json, .env) are looked up next to the exe / current directory /
user-data dir, and all writable state (sitemap cache, default exports) goes to a
per-user data directory so it works even if the exe lives in Program Files.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "MizunoMenace"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def exe_dir() -> Path:
    """Directory containing the running exe (frozen) or the project root."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    d = Path(base) / APP_NAME if base else Path.home() / f".{APP_NAME.lower()}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    d = user_data_dir() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def package_dir() -> Path:
    """Directory containing bundled package data (logo, defaults)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", exe_dir())) / "mizuno_menace"
    return Path(__file__).resolve().parent


def asset_path(name: str) -> Path:
    return package_dir() / "assets" / name


def find_config(filename: str) -> Path | None:
    """Find a config file by searching cwd, the exe dir, then the user dir."""
    seen: set[Path] = set()
    for base in (Path.cwd(), exe_dir(), user_data_dir()):
        if base in seen:
            continue
        seen.add(base)
        candidate = base / filename
        if candidate.exists():
            return candidate
    return None
