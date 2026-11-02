"""Read-only device presence probe for the desktop status bar."""

import argparse
import asyncio
import json
from pathlib import Path

from pymobiledevice3 import usbmux

if __package__:
    from .discovery import ConnectionUnavailableError, discovery_target, select_device
else:
    from discovery import ConnectionUnavailableError, discovery_target, select_device


async def main(allow_wifi=False, workdir=None):
    devices = await asyncio.wait_for(usbmux.list_devices(), timeout=5)
    serial = None
    target = Path(workdir) / "wireless-device.json" if workdir else None
    if target and target.is_file():
        try:
            serial = json.loads(target.read_text()).get("serial")
        except (OSError, ValueError):
            pass
    serial = discovery_target(devices, preferred_serial=serial)
    try:
        device = select_device(devices, allow_wifi, serial)
        result = {"connected": True, "connection_type": device.connection_type}
    except ConnectionUnavailableError:
        result = {"connected": False}
        if allow_wifi and not any(d.connection_type == "USB" for d in devices):
            # Reuse the package loader for this standalone status subprocess.
            from device_worker import load_transport

            load_transport()
            from ios_transport.wifi import open_wifi_lockdown

            try:
                async with await open_wifi_lockdown(serial):
                    result = {"connected": True, "connection_type": "Network"}
            except (RuntimeError, TimeoutError, OSError):
                pass
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--allow-wifi", action="store_true")
    parser.add_argument("--workdir", type=Path)
    args = parser.parse_args()
    asyncio.run(main(args.allow_wifi, args.workdir))
