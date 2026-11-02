"""Direct USB iPhone transport, tested with pymobiledevice3 11.19.4."""

import asyncio
from contextlib import AsyncExitStack
from pathlib import Path

import pymobiledevice3.common

from pymobiledevice3 import usbmux
from pymobiledevice3.exceptions import CoreDeviceError
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
from pymobiledevice3.remote.remote_service_discovery import (
    RemoteServiceDiscoveryService,
)
from pymobiledevice3.remote.core_device.app_service import AppServiceService
from pymobiledevice3.remote.core_device.screen_capture_service import (
    ScreenCaptureService,
)
from pymobiledevice3.remote.core_device.hid_service import (
    touch_session,
    TOUCHSCREEN_STATE_CONTACT,
    TOUCHSCREEN_STATE_RELEASE,
)

REMOTE_CONTROL_UNSUPPORTED_CODE = 9021
REQUIRED_SERVICES = {
    "com.apple.coredevice.screencaptureservice",
    "com.apple.coredevice.displayservice",
    "com.apple.coredevice.hid.universalhidservice",
}


class DeviceLockedError(RuntimeError):
    """The paired phone is reachable but cannot safely accept game input."""


class RemoteControlUnavailableError(RuntimeError):
    """The device permits capture but its OS refuses remote input."""


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
        self.serial = None
        self.lockdown = None
        self.lock = asyncio.Lock()

    async def __aenter__(self):
        """Open one trusted USB device and its userspace tunnel."""
        devices = [
            d
            for d in await asyncio.wait_for(usbmux.list_devices(), 5)
            if d.connection_type == "USB"
        ]
        if len(devices) != 1:
            raise RuntimeError("Connect exactly one unlocked, trusted iPhone by USB.")
        try:
            if self.serial is not None and devices[0].serial != self.serial:
                raise RuntimeError(
                    "Reconnect the same iPhone used when the task started."
                )
            self.serial = devices[0].serial
            tunnel = UserspaceRsdTunnel(serial=self.serial)
            await asyncio.wait_for(self.stack.enter_async_context(tunnel), timeout=40)
            self.rsd = tunnel.rsd
            self.lockdown = await self.stack.enter_async_context(
                await asyncio.wait_for(create_using_usbmux(serial=self.serial), 10)
            )
            await self.ensure_unlocked()
            await self.ensure_developer_services()
            return self
        except BaseException:
            await self._close_services()
            raise

    async def __aexit__(self, *args):
        """Release all transport resources."""
        await self._close_services()

    async def _close_services(self):
        """Bound teardown even when USB vanishes during a request."""
        try:
            await asyncio.wait_for(self.stack.aclose(), timeout=5)
        except (OSError, TimeoutError):
            pass

    async def reconnect(self):
        """Reopen the same device; callers may retry reads, never ambiguous taps."""
        await self._close_services()
        self.stack = AsyncExitStack()
        self.hid = None
        self.rsd = None
        self.lockdown = None
        return await self.__aenter__()

    async def ensure_unlocked(self):
        """Check the live lockdown indicator; it changes with screen lock state."""
        if await asyncio.wait_for(self.lockdown.get_value(key="PasswordProtected"), 5):
            raise DeviceLockedError(
                "Device locked. Unlock your iPhone and return to AFK Journey."
            )

    @property
    def metadata(self):
        """Public device characteristics, without names or pairing identifiers."""
        return {"model": self.rsd.product_type, "ios_version": self.rsd.product_version}

    async def ensure_developer_services(self):
        """Load Apple developer support when a restart removed its services."""
        if REQUIRED_SERVICES <= self.rsd.peer_info.get("Services", {}).keys():
            return
        if not await self.lockdown.get_developer_mode_status():
            raise RuntimeError(
                "Enable Developer Mode in Settings > Privacy & Security on the "
                "iPhone or iPad, restart it, then confirm Turn On."
            )
        try:
            from pymobiledevice3.services.mobile_image_mounter import auto_mount  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "Apple developer support is unavailable in this installation. "
                "Install the updated iOS add-on with its Python 3.13 dependencies."
            ) from exc
        # Apple support is downloaded on first use and cached locally. This is
        # developer tooling, not a firmware update, and does not install an app.
        mount_error = None
        try:
            await asyncio.wait_for(auto_mount(self.rsd), timeout=40)
        except Exception as exc:
            # A daemon can restart after accepting its image and close the reply
            # channel. Check the resulting services before reporting failure;
            # do not blindly repeat installation after an ambiguous response.
            mount_error = exc
        original = self.rsd
        for _ in range(3):
            fresh = RemoteServiceDiscoveryService(
                original.service.address,
                open_connection=original.open_connection,
                handshake_uuid=original.handshake_uuid,
            )
            await asyncio.wait_for(fresh.connect(), timeout=10)
            if REQUIRED_SERVICES <= fresh.peer_info.get("Services", {}).keys():
                self.stack.push_async_callback(fresh.close)
                self.rsd = fresh
                return
            await fresh.close()
            await asyncio.sleep(0.5)
        if mount_error is not None:
            raise RuntimeError(
                "Apple developer support setup failed. Check the computer's "
                "internet connection, reconnect the unlocked device, and retry. "
                + str(mount_error)
            ) from mount_error
        raise RuntimeError(
            "Apple developer support loaded but screenshot/input services are "
            "still unavailable. Reconnect the unlocked device and restart the task."
        )

    async def screenshot(self):
        """Capture a native portrait PNG with a bounded request."""
        await self.ensure_unlocked()
        async with self.lock:
            # iOS 27 / pymobiledevice3 11.19.4 stalls on a second capture over
            # the same ScreenCaptureService. Keep the tunnel, reopen this service.
            async with ScreenCaptureService(self.rsd) as service:
                result = await asyncio.wait_for(
                    service.capture_screenshot(), timeout=20
                )
                return result["image"]

    async def launch(self, bundle, restart=False):
        """Open AFK Journey on the phone."""
        await self.ensure_unlocked()
        async with self.lock:
            async with AppServiceService(self.rsd) as service:
                return await asyncio.wait_for(
                    service.launch_application(bundle, kill_existing=restart),
                    timeout=30,
                )

    async def tap(self, x, y, width, height):
        """Send one bounded touch and always release the contact."""
        x, y = normalized_point(x, y, width, height)
        async with self.lock:
            await self.ensure_touch_session()
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

    async def ensure_touch_session(self):
        """Open input once and distinguish OS restrictions from USB failures."""
        await self.ensure_unlocked()
        if self.hid is not None:
            return
        try:
            self.hid = await self.stack.enter_async_context(touch_session(self.rsd))
        except CoreDeviceError as exc:
            if (
                exc.code != REMOTE_CONTROL_UNSUPPORTED_CODE
                and "remote control requires" not in str(exc).lower()
            ):
                raise
            info = self.metadata
            raise RemoteControlUnavailableError(
                f"Remote input is unavailable on {info['model']} "
                f"(iOS/iPadOS {info['ios_version']}). {exc} "
                "Screenshots may work while taps and swipes are blocked. "
                "Check Settings > General > Software Update on the device."
            ) from exc
        # Additional settling time prevents the first tap being dropped.
        await asyncio.sleep(0.5)
