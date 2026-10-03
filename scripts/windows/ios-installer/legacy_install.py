"""Version-checked iOS add-on installer. Does not write user settings."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


def digest(path):
    data = path.read_bytes()
    if path.suffix == ".py":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
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


def check(app, payload):
    manifest = json.loads((payload / "manifest.json").read_text())
    exe = app / "adb-auto-player.exe"
    if not exe.is_file() or digest(exe) != manifest["exe_sha256"]:
        raise RuntimeError(
            "Install the official Windows x64 AdbAutoPlayer 12.13.0 release first, then select its folder."
        )
    idle(app)
    package = app / "Lib/site-packages/adb_auto_player"
    for item in manifest["files"]:
        target = inside(package, item["path"])
        source = inside(payload / "files", item["path"])
        if digest(source) != item["current"]:
            raise RuntimeError("Installer payload is damaged: " + item["path"])
        if target.exists():
            if digest(target) not in (item["stock"], item["current"]):
                raise RuntimeError(
                    "An unexpected app modification was found: " + item["path"]
                )
        elif item["stock"] is not None:
            raise RuntimeError("The app installation is incomplete: " + item["path"])
    for name, expected in manifest["runtime"].items():
        if digest(inside(payload / "runtime", name)) != expected:
            raise RuntimeError("Bundled runtime is damaged: " + name)
    return manifest


def install(app, payload):
    manifest = check(app, payload)
    marker = app / "ios-support-install.json"
    if marker.exists():
        raise RuntimeError(
            "iOS support is already installed. Use Restore first to reinstall."
        )
    backup = inside(app, "ios-support-backups/" + uuid.uuid4().hex)
    backup.mkdir(parents=True)
    package = app / "Lib/site-packages/adb_auto_player"
    state = {
        "files": [],
        "runtime_existed": (app / "ios-runtime").exists(),
        "backup": str(backup.relative_to(app)),
    }
    for item in manifest["files"]:
        target = inside(package, item["path"])
        entry = dict(item, existed=target.exists())
        if target.exists():
            saved = inside(backup / "files", item["path"])
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            entry["backup_hash"] = digest(saved)
        state["files"].append(entry)
    (backup / "state.json").write_text(json.dumps(state, indent=2))
    staging = inside(app, "ios-runtime-staging-" + uuid.uuid4().hex)
    runtime_moved = False
    runtime_installed = False
    changed = []
    try:
        shutil.copytree(payload / "runtime", staging)
        subprocess.run(
            [
                str(staging / "Scripts/python.exe"),
                "-c",
                "import cv2, psutil; from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel",
            ],
            check=True,
            timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        idle(app)
        if state["runtime_existed"]:
            (app / "ios-runtime").rename(backup / "runtime")
            runtime_moved = True
        staging.rename(app / "ios-runtime")
        runtime_installed = True
        for item in state["files"]:
            target = inside(package, item["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            changed.append(item)
            shutil.copy2(inside(payload / "files", item["path"]), target)
        marker.write_text(json.dumps(state, indent=2))
    except BaseException:
        for item in reversed(changed):
            target = inside(package, item["path"])
            if item["existed"]:
                shutil.copy2(inside(backup / "files", item["path"]), target)
            elif target.exists():
                target.unlink()
        if runtime_installed:
            shutil.rmtree(inside(app, "ios-runtime"))
        if runtime_moved:
            (backup / "runtime").rename(app / "ios-runtime")
        if staging.exists():
            shutil.rmtree(inside(app, staging.name))
        if marker.exists():
            marker.unlink()
        raise
    print("Installed iOS support for 12.13.0. Your game settings were preserved.")
    print(
        "Open ADB Settings > iPhone / iOS > Enable iOS. Leave iOS Python Path blank to use the bundled runtime."
    )


def restore(app):
    idle(app)
    marker = app / "ios-support-install.json"
    if not marker.is_file():
        raise RuntimeError("No iOS installer backup was found in this app folder.")
    state = json.loads(marker.read_text())
    backup = inside(app, state["backup"])
    package = app / "Lib/site-packages/adb_auto_player"
    for item in state["files"]:
        target = inside(package, item["path"])
        if not target.is_file() or digest(target) != item["current"]:
            raise RuntimeError(
                "The app changed since installation; restore stopped: " + item["path"]
            )
        if (
            item["existed"]
            and digest(inside(backup / "files", item["path"])) != item["backup_hash"]
        ):
            raise RuntimeError("Backup validation failed.")
    if state["runtime_existed"] and not (backup / "runtime").is_dir():
        raise RuntimeError("Runtime backup is missing.")
    # Keep the removed runtime recoverable rather than deleting it.
    (app / "ios-runtime").rename(backup / "removed-ios-runtime")
    if state["runtime_existed"]:
        (backup / "runtime").rename(app / "ios-runtime")
    for item in state["files"]:
        target = inside(package, item["path"])
        if item["existed"]:
            shutil.copy2(inside(backup / "files", item["path"]), target)
        else:
            target.unlink()
    marker.unlink()
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
    sys.exit(main())
