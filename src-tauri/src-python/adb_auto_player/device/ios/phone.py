"""Direct USB iPhone transport, tested with pymobiledevice3 11.19.4."""

import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

import pymobiledevice3.common

from pymobiledevice3 import usbmux
from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
from pymobiledevice3.remote.core_device.app_service import AppServiceService
from pymobiledevice3.remote.core_device.screen_capture_service import (
    ScreenCaptureService,
)
from pymobiledevice3.remote.core_device.hid_service import (
    touch_session,
    TOUCHSCREEN_STATE_CONTACT,
    TOUCHSCREEN_STATE_RELEASE,
)

AFK_BUNDLE = "com.farlightgames.igame.ios"


def normalized_point(x, y, width, height):
    """Map an observed screenshot pixel to Apple's normalized touch coordinates."""
    if width <= 1 or height <= 1 or not (0 <= x < width and 0 <= y < height):
        raise ValueError("Touch point is outside the current screenshot.")
    return round(x * 65535 / (width - 1)), round(y * 65535 / (height - 1))


class Phone:
    """One closeable device connection with serialized screenshot and touch calls."""

    def __init__(self, workdir):
        pymobiledevice3.common._HOMEFOLDER = Path(workdir) / "device-cache"
        self.stack = AsyncExitStack()
        self.rsd = None
        self.hid = None
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        """Open one trusted USB device and its userspace tunnel."""
        devices = [d for d in await usbmux.list_devices() if d.connection_type == "USB"]
        if len(devices) != 1:
            raise RuntimeError("Connect exactly one unlocked, trusted iPhone by USB.")
        try:
            tunnel = UserspaceRsdTunnel(serial=devices[0].serial)
            await asyncio.wait_for(self.stack.enter_async_context(tunnel), timeout=40)
            self.rsd = tunnel.rsd
            return self
        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(self, *args):
        """Release all transport resources."""
        await self.stack.aclose()

    async def screenshot(self):
        """Capture a native portrait PNG with a bounded request."""
        async with self.lock:
            async with ScreenCaptureService(self.rsd) as service:
                result = await asyncio.wait_for(
                    service.capture_screenshot(), timeout=20
                )
                return result["image"]

    async def launch(self, restart=False):
        """Open AFK Journey on the phone."""
        async with self.lock:
            async with AppServiceService(self.rsd) as service:
                return await asyncio.wait_for(
                    service.launch_application(AFK_BUNDLE, kill_existing=restart),
                    timeout=30,
                )

    async def tap(self, x, y, width, height):
        """Send one bounded touch and always release the contact."""
        x, y = normalized_point(x, y, width, height)
        async with self.lock:
            if self.hid is None:
                self.hid = await self.stack.enter_async_context(touch_session(self.rsd))
                # Additional settling time prevents the first tap being dropped.
                await asyncio.sleep(0.5)
            try:
                await asyncio.wait_for(
                    self.hid.send_touchscreen(TOUCHSCREEN_STATE_CONTACT, x, y),
                    timeout=10,
                )
                await asyncio.sleep(0.1)
            finally:
                await asyncio.wait_for(
                    self.hid.send_touchscreen(TOUCHSCREEN_STATE_RELEASE, x, y),
                    timeout=10,
                )
