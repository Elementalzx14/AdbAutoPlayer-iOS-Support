"""Offline iOS dependency overlay for the official 12.13.0 Windows app."""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

MARKER = "ios-support-install.json"
PENDING = "ios-support-pending.json"


def digest(path):
    data = path.read_bytes()
    if path.suffix == ".py":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def inside(root, relative):
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Invalid installer path")
    return path


def idle(app):
    import psutil

    for process in psutil.process_iter(["exe"]):
        try:
            exe = process.info["exe"]
            if exe and Path(exe).resolve().is_relative_to(app):
                raise RuntimeError(
                    "Close AdbAutoPlayer and its running tasks, then retry."
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def atomic_copy(source, target):
    """Keep every destination either old or new if setup is interrupted."""
    temporary = target.with_name(target.name + ".ios-staging-" + uuid.uuid4().hex)
    try:
        shutil.copy2(source, temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def compatible_existing(target, item):
    """Recognize stock, identical payloads, and known leftover iOS additions."""
    if not target.is_file():
        return False
    actual = digest(target)
    if actual in {item["stock"], item["current"]}:
        return True
    # Earlier app upgrades overwrote stock files but left added iOS files behind.
    # Only allow known versions of additions; never trust arbitrary modifications.
    if item["stock"] is not None:
        return False
    if actual in item.get("previous", []):
        return True
    if target.suffix == ".json" and item.get("previous_json"):
        try:
            value = json.loads(target.read_text(encoding="utf-8-sig"))
            canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
            return (
                hashlib.sha256(canonical.encode()).hexdigest() in item["previous_json"]
            )
        except (ValueError, UnicodeError):
            return False
    return False


def check(app, payload):
    manifest = json.loads((payload / "manifest.json").read_text())
    if (app / PENDING).exists():
        raise RuntimeError(
            "An interrupted setup was found. Choose Restore previous files first."
        )
    if (app / MARKER).exists():
        raise RuntimeError(
            "An iOS preview is already installed. Choose Restore previous files, then Install iOS Support to update. Your game settings are preserved."
        )
    for name, expected in manifest["base"].items():
        target = inside(app, name)
        if not target.is_file() or digest(target) != expected:
            raise RuntimeError(
                "Install official Windows x64 AdbAutoPlayer 12.13.0 first, then select its folder."
            )
    idle(app)
    for item in manifest["files"]:
        source = inside(payload / "files", item["path"])
        target = inside(app, item["path"])
        if not source.is_file() or digest(source) != item["current"]:
            raise RuntimeError("Installer payload is damaged: " + item["path"])
        if target.exists():
            if not compatible_existing(target, item):
                raise RuntimeError("Unexpected app modification: " + item["path"])
        elif item["stock"] is not None:
            raise RuntimeError("The app installation is incomplete: " + item["path"])
    return manifest


def validate_runtime(app):
    environment = {
        k: v
        for k, v in os.environ.items()
        if k.upper() not in {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"}
    }
    result = subprocess.run(
        [
            str(app / "python.exe"),
            "-I",
            "-B",
            "-c",
            "import sys,cv2,numpy,psutil; assert sys.version_info[:2]==(3,13); "
            "from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel; "
            "from adb_auto_player.device.ios.phone import Phone; "
            "from adb_auto_player.device.ios.geometry import Canvas",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env=environment,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError("iOS dependency check failed: " + result.stderr[-2000:])


def install(app, payload):
    manifest = check(app, payload)
    backup = inside(app, "ios-support-backups/" + uuid.uuid4().hex)
    backup.mkdir(parents=True)
    state = {
        "format": 2,
        "version": manifest["version"],
        "backup": str(backup.relative_to(app)),
        "files": [],
    }
    for item in manifest["files"]:
        target = inside(app, item["path"])
        entry = dict(item, existed=target.exists())
        if target.exists():
            saved = inside(backup / "files", item["path"])
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            entry["backup_hash"] = digest(saved)
        state["files"].append(entry)
    state_text = json.dumps(state, indent=2)
    (backup / "state.json").write_text(state_text)
    (app / PENDING).write_text(state_text)
    try:
        idle(app)
        for item in state["files"]:
            target = inside(app, item["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_copy(inside(payload / "files", item["path"]), target)
        validate_runtime(app)
        (app / PENDING).replace(app / MARKER)
    except BaseException:
        # Our own failed write may be partial; backups were verified before writes.
        # Pending state allows recovery via Restore if cleanup itself is interrupted.
        restore_files(app, state)
        (app / PENDING).unlink(missing_ok=True)
        raise
    print("Installed iOS Support v3 for AdbAutoPlayer 12.13.0.")
    print("Uses the app's Python 3.13. No separate iOS runtime was installed.")
    print(
        "Game settings were preserved. Enable iOS in ADB Settings and leave iOS Python Path blank."
    )


def restore_files(app, state):
    backup = inside(app, state["backup"])
    for item in state["files"]:
        if item["existed"]:
            saved = inside(backup / "files", item["path"])
            if not saved.is_file() or digest(saved) != item["backup_hash"]:
                raise RuntimeError("Backup validation failed: " + item["path"])
    for item in reversed(state["files"]):
        target = inside(app, item["path"])
        if item["existed"]:
            atomic_copy(inside(backup / "files", item["path"]), target)
        else:
            target.unlink(missing_ok=True)


def restore(app):
    idle(app)
    marker, pending = app / MARKER, app / PENDING
    if not marker.exists() and not pending.exists():
        raise RuntimeError("No iOS installer backup was found in this app folder.")
    state = json.loads((pending if pending.exists() else marker).read_text())
    if state.get("format") != 2:
        # The embedded helper's isolated _pth excludes this script's directory.
        spec = importlib.util.spec_from_file_location(
            "legacy_ios_installer", Path(__file__).with_name("legacy_install.py")
        )
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)
        legacy.restore(app)
        return
    for item in state["files"]:
        target = inside(app, item["path"])
        allowed = {item["current"]}
        if pending.exists():
            allowed.add(item.get("backup_hash"))
        if target.exists():
            if digest(target) not in allowed:
                raise RuntimeError(
                    "The app changed since installation; restore stopped: "
                    + item["path"]
                )
        elif not pending.exists() or item["existed"]:
            raise RuntimeError("A required app file is missing: " + item["path"])
    # Keep a journal so a interrupted restore can be retried.
    pending.write_text(json.dumps(state, indent=2))
    restore_files(app, state)
    marker.unlink(missing_ok=True)
    pending.unlink(missing_ok=True)
    print("Previous app files restored. Game settings were preserved.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument(
        "--action", choices=["check", "install", "restore"], default="install"
    )
    args = parser.parse_args()
    app = args.app.resolve()
    payload = Path(__file__).resolve().parent
    try:
        if args.action == "restore":
            restore(app)
        elif args.action == "check":
            check(app, payload)
            print("Compatible official 12.13.0 installation found. Payload verified.")
        else:
            install(app, payload)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
