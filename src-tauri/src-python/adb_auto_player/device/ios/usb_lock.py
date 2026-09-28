"""Cross-profile ownership of the Apple USB connection."""

from contextlib import contextmanager


@contextmanager
def exclusive_run(folder):
    """Prevent two launchers from sending competing commands to this phone."""
    import msvcrt  # noqa: PLC0415 -- optional runtime

    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "runner.lock").open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Another AFK iPhone run is already active.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
