"""Trusted Bonjour discovery and a pinned userspace-tunnel adapter."""

import asyncio
from contextlib import aclosing

from pymobiledevice3.exceptions import RemotePairingCompletedError
from pymobiledevice3.lockdown import get_mobdev2_lockdowns
from pymobiledevice3.remote import userspace_tunnel
from pymobiledevice3.remote.tunnel_service import (
    RemotePairingLockdownService,
    get_remote_pairing_tunnel_services,
)

from .discovery import ConnectionUnavailableError


async def open_wifi_lockdown(serial=None):
    """Return exactly one already-paired device; close every unused client."""
    clients = []
    selected = None
    try:
        async with asyncio.timeout(10):
            async with aclosing(
                get_mobdev2_lockdowns(udid=serial, only_paired=True, timeout=3)
            ) as discovery:
                async for _, client in discovery:
                    clients.append(client)
            unique = {client.udid: client for client in clients if client.paired}
            if serial is not None:
                unique = {key: value for key, value in unique.items() if key == serial}
            if len(unique) != 1:
                raise ConnectionUnavailableError(
                    "No single trusted iPhone or iPad was found over Wi-Fi. Keep both "
                    "devices on the same network and unlock the device. Reconnect USB "
                    "to complete wireless setup or choose the intended device."
                )
            selected = next(iter(unique.values()))
            return selected
    finally:
        for client in clients:
            if client is not selected:
                await client.close()


async def prepare_remote_pairing(lockdown):
    """Bootstrap media-tunnel pairing through an already trusted connection."""
    service = await RemotePairingLockdownService.create(lockdown)
    try:
        try:
            await asyncio.wait_for(service.connect(autopair=True), 15)
        except RemotePairingCompletedError:
            pass
    finally:
        await service.close()


class LockdownRsdTunnel(userspace_tunnel.UserspaceRsdTunnel):
    """Reuse 11.19.4's media-capable tunnel with an existing Wi-Fi lockdown.

    That pinned release has no provider-injection argument. Substitute only its
    provider factory while its lifecycle lock is held, then restore it on every
    exit. Each device worker owns one tunnel; no library files are modified.
    All packet handling, transport monitoring and teardown remain upstream.
    """

    def __init__(self, lockdown):
        super().__init__(serial=lockdown.udid, autopair=False)
        self.lockdown = lockdown

    async def _aopen_locked(self):
        original = userspace_tunnel._create_no_root_tunnel_provider

        async def provider(serial, autopair, remotepairing_fallback=True):
            if serial != self.lockdown.udid:
                raise ValueError("Wireless tunnel device identity changed.")
            services = await get_remote_pairing_tunnel_services(
                udid=serial, bonjour_timeout=5
            )
            if not services:
                raise ConnectionUnavailableError(
                    "Wireless control tunnel was not found. Reconnect USB to complete setup, then check that both devices use the same network."
                )
            for unused in services[1:]:
                await unused.close()
            return services[0], None

        userspace_tunnel._create_no_root_tunnel_provider = provider
        try:
            return await super()._aopen_locked()
        finally:
            userspace_tunnel._create_no_root_tunnel_provider = original
