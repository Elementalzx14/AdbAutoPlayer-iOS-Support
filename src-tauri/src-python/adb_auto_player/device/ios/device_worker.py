"""Persistent Apple device worker with file-based screenshot transport."""

import argparse
import asyncio
import importlib.util
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np


def load_transport():
    folder = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "ios_transport",
        folder / "__init__.py",
        submodule_search_locations=[str(folder)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules["ios_transport"] = package
    spec.loader.exec_module(package)


def device_error(exc):
    """Keep actionable connection failures distinct from template failures."""
    detail = f"{type(exc).__name__}: {exc}"
    lower = detail.lower()
    if type(exc).__name__ == "RemoteControlUnavailableError":
        return str(exc)
    if "connect exactly one" in lower:
        return "iPhone disconnected or multiple devices connected. Connect exactly one iPhone by USB, unlock it, then restart the task."
    if isinstance(exc, ValueError):
        return "iOS operation rejected: " + str(exc)
    if (
        any(word in lower for word in ("locked", "password", "passcode"))
        and "unlocked" not in lower
    ):
        return "Unlock your iPhone and leave AFK Journey visible. " + detail
    if any(word in lower for word in ("pair", "trust", "invalidhost")):
        return (
            "Reconnect by USB, unlock the iPhone, and accept Trust This Computer. "
            + detail
        )
    return (
        "iOS connection failed. Check USB, unlock the device, and ensure Developer Mode is enabled. "
        + detail
    )


async def serve(args):
    load_transport()
    from ios_transport.bundles import resolve_bundle
    from ios_transport.geometry import Canvas
    from ios_transport.phone import DeviceLockedError, Phone, normalized_point
    from ios_transport.usb_lock import exclusive_run
    from pymobiledevice3.remote.core_device.app_service import AppServiceService
    from pymobiledevice3.remote.core_device.hid_service import (
        TOUCHSCREEN_STATE_CONTACT,
        TOUCHSCREEN_STATE_RELEASE,
    )

    args.session.mkdir(parents=True, exist_ok=True)
    process_id = None
    bundle = None
    canvas = None
    native_data = None
    metadata = {}
    with exclusive_run(args.workdir):
        async with Phone(args.workdir) as phone:

            async def screenshot(force_native=False):
                nonlocal canvas, native_data, metadata
                started = time.perf_counter()

                async def capture():
                    nonlocal native_data
                    if force_native:
                        native_data = await phone.screenshot()
                        return cv2.imdecode(
                            np.frombuffer(native_data, np.uint8), cv2.IMREAD_COLOR
                        )
                    return await phone.capture_frame()

                try:
                    native = await capture()
                except DeviceLockedError:
                    raise
                except Exception:
                    # A screenshot has no game side effects. Retry once after reopening
                    # the same paired device. Never retry a tap or launch automatically.
                    await phone.reconnect()
                    native = await capture()
                if native is None:
                    raise RuntimeError("Invalid iOS screenshot.")
                h, w = native.shape[:2]
                if (h > w) != (args.height > args.width):
                    raise RuntimeError(
                        "Rotate the Apple device to portrait for this game."
                    )
                canvas = Canvas(w, h, args.width, args.height)
                frame = canvas.render(native)
                metadata = {
                    **phone.metadata,
                    "native_size": [w, h],
                    "canvas_size": [args.width, args.height],
                    "viewport": canvas.viewport,
                    "capture_seconds": round(time.perf_counter() - started, 4),
                    "capture_source": "screenshot"
                    if force_native
                    else phone.capture_source,
                    "capture_warning": phone.capture_warning,
                    "input_held": phone.held_contact is not None,
                }
                # Atomic replacement prevents a partial frame from being consumed.
                pending = args.session / "frame.pending.bmp"
                cv2.imwrite(str(pending), frame)
                pending.replace(args.session / "frame.bmp")
                return metadata

            async def point(x, y):
                if canvas is None:
                    await screenshot()
                return canvas.native_point(x, y)

            async def drag(request):
                await phone.ensure_touch_session()
                duration = float(request["duration"])
                if not 0 < duration <= 30:
                    raise ValueError(
                        "Hold/swipe duration must be between 0 and 30 seconds."
                    )
                start = normalized_point(
                    *(await point(request["x"], request["y"])),
                    canvas.native_width,
                    canvas.native_height,
                )
                end = normalized_point(
                    *(await point(request["end_x"], request["end_y"])),
                    canvas.native_width,
                    canvas.native_height,
                )
                steps = max(1, round(duration * 30))
                x, y = start
                try:
                    for step in range(steps + 1):
                        x = round(start[0] + (end[0] - start[0]) * step / steps)
                        y = round(start[1] + (end[1] - start[1]) * step / steps)
                        await asyncio.wait_for(
                            phone.hid.send_touchscreen(TOUCHSCREEN_STATE_CONTACT, x, y),
                            10,
                        )
                        if step < steps:
                            await asyncio.sleep(duration / steps)
                finally:
                    await asyncio.wait_for(
                        phone.hid.send_touchscreen(TOUCHSCREEN_STATE_RELEASE, x, y), 10
                    )

            while line := await asyncio.to_thread(sys.stdin.readline):
                request_id = None
                try:
                    request = json.loads(line)
                    request_id = request.get("id")
                    action = request["action"]
                    value = None
                    if action in ("screenshot", "check_orientation", "debug_capture"):
                        value = await screenshot(force_native=action == "debug_capture")
                        if action == "debug_capture":
                            (args.session / "native.png").write_bytes(native_data)
                    elif action == "tap":
                        if phone.held_contact is not None:
                            raise ValueError("A touch hold is already active.")
                        x, y = await point(request["x"], request["y"])
                        await phone.tap(x, y, canvas.native_width, canvas.native_height)
                    elif action == "swipe":
                        if phone.held_contact is not None:
                            raise ValueError("A touch hold is already active.")
                        await drag(request)
                    elif action == "touch_down":
                        x, y = await point(request["x"], request["y"])
                        await phone.begin_hold(
                            x,
                            y,
                            canvas.native_width,
                            canvas.native_height,
                            duration=request.get("duration", 30),
                        )
                    elif action == "touch_up":
                        await phone.release_hold()
                    elif action in ("select_game", "start"):
                        await phone.release_hold()
                        bundle = resolve_bundle(
                            request["packages"]
                            if action == "select_game"
                            else [request["package"]]
                        )
                        result = await phone.launch(bundle)
                        process_id = int(result["processToken"]["processIdentifier"])
                    elif action == "installed_packages":
                        async with AppServiceService(phone.rsd) as service:
                            apps = await asyncio.wait_for(service.list_apps(), 20)
                        value = [
                            app["bundleIdentifier"]
                            for app in apps
                            if str(app.get("bundleIdentifier", "")).startswith(
                                request["prefix"]
                            )
                        ]
                    elif action == "running_app":
                        if process_id is not None:
                            async with AppServiceService(phone.rsd) as service:
                                processes = await asyncio.wait_for(
                                    service.list_processes(), 15
                                )
                            if any(
                                int(p["processIdentifier"]) == process_id
                                for p in processes
                            ):
                                value = bundle
                    elif action == "stop":
                        await phone.release_hold()
                        if resolve_bundle([request["package"]]) != bundle:
                            raise ValueError("The requested game is not selected.")
                        if process_id is not None:
                            async with AppServiceService(phone.rsd) as service:
                                await asyncio.wait_for(
                                    service.send_signal_to_process(process_id, 15), 15
                                )
                            process_id = None
                    else:
                        raise ValueError(
                            "Unsupported Apple device operation: " + action
                        )
                    print(json.dumps({"id": request_id, "value": value}), flush=True)
                except Exception as exc:
                    await phone.release_hold_quietly()
                    print(
                        json.dumps({"id": request_id, "error": device_error(exc)}),
                        flush=True,
                    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    args = parser.parse_args()
    try:
        asyncio.run(serve(args))
    except Exception as exc:
        print(json.dumps({"error": device_error(exc)}), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
