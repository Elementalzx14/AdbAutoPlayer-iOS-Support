"""Build a version-checked offline overlay using the app's Python 3.13."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

# Published early iOS source revisions, before the shared Python runtime update.
LEGACY_REFS = ("6c718615", "61bb078a", "7c062064", "02c02ef9")


def legacy_additions(repo, paths):
    """Fingerprint known early iOS files without extracting them to disk."""
    result = {path: {"previous": set(), "previous_json": set()} for path in paths}
    for ref in LEGACY_REFS:
        archive = subprocess.check_output(
            ["git", "archive", ref, "src-tauri/src-python/adb_auto_player"], cwd=repo
        )
        with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
            for member in contents:
                if not member.isfile() or member.name not in result:
                    continue
                data = contents.extractfile(member).read()
                if member.name.endswith(".py"):
                    data = data.replace(b"\r\n", b"\n")
                result[member.name]["previous"].add(hashlib.sha256(data).hexdigest())
                if member.name.endswith((".txt", ".json")):
                    # git archive can apply Windows checkout line endings.
                    # Early manual installs also used the original Git LF bytes.
                    lf = data.replace(b"\r\n", b"\n")
                    for variant in (lf, lf.replace(b"\n", b"\r\n")):
                        result[member.name]["previous"].add(
                            hashlib.sha256(variant).hexdigest()
                        )
                if member.name.endswith(".json"):
                    canonical = json.dumps(
                        json.loads(data), sort_keys=True, separators=(",", ":")
                    )
                    result[member.name]["previous_json"].add(
                        hashlib.sha256(canonical.encode()).hexdigest()
                    )
    return {
        path: {key: sorted(values) for key, values in hashes.items() if values}
        for path, hashes in result.items()
    }


def digest(path):
    data = path.read_bytes()
    if path.suffix == ".py":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--bootstrap", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = "src-tauri/src-python/adb_auto_player/"
    backend = subprocess.check_output(
        ["git", "diff", "--name-only", "12.13.0", "--", prefix], cwd=repo, text=True
    ).splitlines()
    files = {}
    for file in backend:
        source = repo / file
        if not source.is_file():
            raise RuntimeError("Deleted stock backend files are unsupported: " + file)
        files["Lib/site-packages/adb_auto_player/" + file[len(prefix) :]] = source
    legacy = legacy_additions(
        repo,
        [
            file
            for file in backend
            if not (
                args.stock
                / ("Lib/site-packages/adb_auto_player/" + file[len(prefix) :])
            ).exists()
        ],
    )
    for source in (args.prepared / "Lib/site-packages").rglob("*"):
        if (
            not source.is_file()
            or "__pycache__" in source.parts
            or source.suffix == ".pyc"
        ):
            continue
        relative = source.relative_to(args.prepared).as_posix()
        original = args.stock / relative
        if not original.exists() or digest(source) != digest(original):
            files.setdefault(relative, source)
    manifest = {
        "format": 2,
        "version": "12.13.0-ios.3",
        "files": [],
        "base": {
            name: digest(args.stock / name)
            for name in ("adb-auto-player.exe", "python.exe")
        },
    }
    with tempfile.TemporaryDirectory(prefix="adb-ios-build-") as scratch:
        archive = Path(scratch) / "payload.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for relative, source in sorted(files.items()):
                original = args.stock / relative
                manifest["files"].append(
                    {
                        "path": relative,
                        "current": digest(source),
                        "stock": digest(original) if original.exists() else None,
                        **legacy.get(
                            "src-tauri/src-python/"
                            + relative.removeprefix("Lib/site-packages/"),
                            {},
                        ),
                    }
                )
                z.write(source, "files/" + relative)
            for source in args.bootstrap.rglob("*"):
                if (
                    source.is_file()
                    and "__pycache__" not in source.parts
                    and source.suffix != ".pyc"
                ):
                    z.write(
                        source,
                        "bootstrap/" + source.relative_to(args.bootstrap).as_posix(),
                    )
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            for name in ("install.py", "legacy_install.py"):
                z.write(here / name, name)
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
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    shutil.copy2(here / "README.md", output.parent / "INSTALL-iOS-Support-v3.md")
    print(
        f"Built {output.name}: {len(files)} files; {output.stat().st_size / 1024 / 1024:.1f} MiB"
    )


if __name__ == "__main__":
    main()
