"""Persistent Apple USB RPC worker; contains no game task or battle settings."""

import argparse
import asyncio
import base64
import importlib.util
import json
from pathlib import Path
import sys

import cv2
import numpy as np


async def serve(args):
    """Serve device primitives until the desktop closes its command pipe."""
    folder = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "ios_transport",
        folder / "__init__.py",
        submodule_search_locations=[str(folder)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules["ios_transport"] = package
    spec.loader.exec_module(package)
    from ios_transport.phone import Phone
    from ios_transport.usb_lock import exclusive_run
    from pymobiledevice3.remote.core_device.app_service import AppServiceService
    from pymobiledevice3.remote.core_device.hid_service import (
        touch_session,
        TOUCHSCREEN_STATE_CONTACT,
        TOUCHSCREEN_STATE_RELEASE,
    )

    # Logical identifiers keep the existing game's package checks unchanged.
    android_package = "com.farlightgames.igame.gp"
    process_id = None

    with exclusive_run(args.workdir):
        async with Phone(args.workdir) as phone:

            async def screenshot():
                data = await phone.screenshot()
                native = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if native is None:
                    raise RuntimeError("Invalid iOS screenshot.")
                height, width = native.shape[:2]
                if (height > width) != (args.height > args.width):
                    raise RuntimeError(
                        "Rotate the Apple device to the game's expected orientation."
                    )
                # Present a logical canvas; touches use the exact inverse mapping.
                return cv2.resize(
                    native, (args.width, args.height), interpolation=cv2.INTER_AREA
                )

            async def drag(request):
                if phone.hid is None:
                    phone.hid = await phone.stack.enter_async_context(
                        touch_session(phone.rsd)
                    )
                    await asyncio.sleep(0.5)
                duration = float(request["duration"])
                if not 0 < duration <= 30:
                    raise ValueError(
                        "Hold/swipe duration must be between 0 and 30 seconds."
                    )
                steps = max(1, round(duration * 30))
                from ios_transport.phone import normalized_point

                start = normalized_point(
                    request["x"], request["y"], args.width, args.height
                )
                end = normalized_point(
                    request["end_x"], request["end_y"], args.width, args.height
                )
                x, y = start
                try:
                    for step in range(steps + 1):
                        x = round(start[0] + (end[0] - start[0]) * step / steps)
                        y = round(start[1] + (end[1] - start[1]) * step / steps)
                        await phone.hid.send_touchscreen(
                            TOUCHSCREEN_STATE_CONTACT, x, y
                        )
                        if step < steps:
                            await asyncio.sleep(duration / steps)
                finally:
                    await phone.hid.send_touchscreen(TOUCHSCREEN_STATE_RELEASE, x, y)

            while line := await asyncio.to_thread(sys.stdin.readline):
                try:
                    request = json.loads(line)
                    action = request["action"]
                    value = None
                    if action in ("screenshot", "check_orientation"):
                        frame = await screenshot()
                        if action == "screenshot":
                            value = base64.b64encode(
                                cv2.imencode(".png", frame)[1]
                            ).decode()
                    elif action == "tap":
                        await phone.tap(
                            request["x"], request["y"], args.width, args.height
                        )
                    elif action == "swipe":
                        await drag(request)
                    elif action == "select_game":
                        if android_package not in request["packages"]:
                            raise RuntimeError(
                                "This game's Apple bundle identifier has not been mapped yet."
                            )
                        result = await phone.launch()
                        process_id = int(result["processToken"]["processIdentifier"])
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
                                value = android_package
                    elif action == "start":
                        if request["package"] != android_package:
                            raise RuntimeError("Unknown Apple game mapping.")
                        result = await phone.launch()
                        process_id = int(result["processToken"]["processIdentifier"])
                    elif action == "stop":
                        if request["package"] != android_package:
                            raise RuntimeError("Unknown Apple game mapping.")
                        if process_id is not None:
                            async with AppServiceService(phone.rsd) as service:
                                await asyncio.wait_for(
                                    service.send_signal_to_process(process_id, 15), 15
                                )
                            process_id = None
                    elif action == "back":
                        frame = await screenshot()
                        template = cv2.imread(request["template"])
                        if template is None:
                            raise RuntimeError(
                                "No iOS back-button template is available."
                            )
                        _, confidence, _, position = cv2.minMaxLoc(
                            cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
                        )
                        if confidence < 0.92:
                            raise RuntimeError(
                                "iOS has no Android Back key, and no verified in-game Back button was found."
                            )
                        h, w = template.shape[:2]
                        await phone.tap(
                            position[0] + w / 2,
                            position[1] + h / 2,
                            args.width,
                            args.height,
                        )
                    else:
                        raise ValueError(
                            "Unsupported Apple device operation: " + action
                        )
                    print(json.dumps({"value": value}), flush=True)
                except Exception as exc:
                    print(json.dumps({"error": str(exc)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    args = parser.parse_args()
    try:
        asyncio.run(serve(args))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
