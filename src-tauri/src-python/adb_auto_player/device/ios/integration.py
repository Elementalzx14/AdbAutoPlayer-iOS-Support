"""Bridge desktop controls to the current interpreter or a legacy runtime."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from adb_auto_player.file_loader import SettingsLoader
from adb_auto_player.ipc import GameGUIOptions

STOP_TIMEOUT_SECONDS = 45

RESULT_PREFIX = "IOS_RESULT:"


def game_menu() -> GameGUIOptions:
    """Keep the original game's menu and settings on every device type."""
    from adb_auto_player.tauri_helpers.menu import get_game_gui_options  # noqa: PLC0415

    return get_game_gui_options()


def worker_command():
    """Resolve the isolated runtime without depending on a system PATH."""
    if sys.platform != "win32":
        raise RuntimeError(
            "This experimental iOS integration currently requires Windows."
        )
    configured = SettingsLoader.adb_settings().ios.python_path
    if configured:
        runtime = Path(configured)
    elif importlib.util.find_spec("pymobiledevice3") is not None:
        executable = Path(sys.executable)
        # An embedded Rust host may report the desktop EXE as sys.executable.
        # Spawn its bundled Python, never recursively launch the desktop UI.
        runtime = (
            executable
            if executable.name.lower().startswith("python")
            else SettingsLoader.get_resource_dir() / "python.exe"
        )
    else:
        # Compatibility with previously shipped add-on installations.
        runtime = SettingsLoader.get_resource_dir() / "ios-runtime/Scripts/python.exe"
    if not runtime.is_file():
        raise RuntimeError(
            "iOS runtime is missing. Run "
            "scripts/windows/setup-ios.ps1 or set iOS Python Path in Settings."
        )
    return [str(runtime), "-u", str(Path(__file__).with_name("worker.py"))]


def worker_environment():
    """Prevent the embedded desktop interpreter from contaminating the worker."""
    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"}
    }


def connected_device() -> str | None:
    """Inspect USB presence without opening a control tunnel or using ADB."""
    result = subprocess.run(
        [*worker_command(), "--status"],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
        creationflags=subprocess.CREATE_NO_WINDOW,
        env=worker_environment(),
    )
    if result.returncode:
        raise RuntimeError(
            "iPhone USB detection failed. Check Apple Mobile "
            "Device Service and the iOS runtime."
        )
    return "iPhone (USB)" if json.loads(result.stdout)["connected"] else None
