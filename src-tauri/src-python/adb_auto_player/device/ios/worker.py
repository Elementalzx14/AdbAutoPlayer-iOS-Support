"""Read-only USB presence probe for the desktop status bar."""

import asyncio
import json
from pymobiledevice3 import usbmux


async def main():
    devices = await asyncio.wait_for(usbmux.list_devices(), timeout=5)
    print(
        json.dumps(
            {"connected": len([d for d in devices if d.connection_type == "USB"]) == 1}
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
