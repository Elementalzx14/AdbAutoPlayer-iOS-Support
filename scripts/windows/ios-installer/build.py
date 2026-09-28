"""Build the offline Windows add-on from official stock and a portable runtime."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


def digest(path):
    data = path.read_bytes()
    if path.suffix == ".py":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", required=True, type=Path)
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = "src-tauri/src-python/adb_auto_player/"
    files = subprocess.check_output(
        ["git", "diff", "--name-only", "12.13.0", "--", prefix], cwd=repo, text=True
    ).splitlines()
    manifest = {
        "version": "12.13.0-ios.1",
        "exe_sha256": digest(args.stock / "adb-auto-player.exe"),
        "files": [],
        "runtime": {},
    }
    with tempfile.TemporaryDirectory(prefix="adb-ios-build-") as scratch:
        payload = Path(scratch)
        archive = payload / "payload.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for file in files:
                rel = file[len(prefix) :]
                src = repo / file
                stock = args.stock / "Lib/site-packages/adb_auto_player" / rel
                if not src.is_file():
                    raise RuntimeError(
                        "Deleted backend files are not supported: " + file
                    )
                manifest["files"].append(
                    {
                        "path": rel,
                        "current": digest(src),
                        "stock": digest(stock) if stock.exists() else None,
                    }
                )
                z.write(src, "files/" + rel)
            for p in args.runtime.rglob("*"):
                if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc":
                    continue
                rel = p.relative_to(args.runtime).as_posix()
                manifest["runtime"][rel] = digest(p)
                z.write(p, "runtime/" + rel)
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            z.write(here / "install.py", "install.py")
            z.write(repo / "LICENSE", "LICENSE-AdbAutoPlayer.txt")
        compiler = (
            Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        )
        subprocess.run(
            [
                str(compiler),
                "/nologo",
                "/target:winexe",
                "/platform:x64",
                "/reference:System.Windows.Forms.dll",
                "/reference:System.Drawing.dll",
                "/reference:System.IO.Compression.dll",
                "/reference:System.IO.Compression.FileSystem.dll",
                "/resource:" + str(archive) + ",payload.zip",
                "/out:" + str(output),
                str(here / "Setup.cs"),
            ],
            check=True,
        )
    output.with_suffix(".exe.sha256").write_text(
        digest(output) + "  " + output.name + "\n"
    )
    shutil.copy2(here / "README.md", output.parent / "INSTALL-iOS-Support.md")
    print(str(output))


if __name__ == "__main__":
    main()
