"""Wireless selection must preserve device identity and close unused clients."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from adb_auto_player.device.ios.discovery import (
    ConnectionUnavailableError,
    discovery_target,
    select_device,
)


def device(serial, transport):
    return SimpleNamespace(serial=serial, connection_type=transport)


def test_usb_is_preferred_and_wifi_is_opt_in():
    usb, wifi = device("tablet", "USB"), device("phone", "Network")
    assert select_device([wifi, usb], True) is usb
    with pytest.raises(ConnectionUnavailableError):
        select_device([wifi])
    assert select_device([wifi], True) is wifi


def test_reconnect_cannot_switch_to_another_device():
    with pytest.raises(ConnectionUnavailableError, match="same iPhone or iPad"):
        select_device([device("other", "USB")], True, "tablet")
    tablet = device("tablet", "Network")
    assert select_device([device("other", "USB"), tablet], True, "tablet") is tablet


def test_saved_target_is_used_wirelessly_but_new_usb_can_select_a_device():
    assert discovery_target([], preferred_serial="tablet") == "tablet"
    usb = [device("phone", "USB")]
    assert discovery_target(usb, preferred_serial="tablet") is None
    assert (
        discovery_target(usb, active_serial="tablet", preferred_serial="phone")
        == "tablet"
    )


def test_multiple_devices_are_rejected_and_duplicate_transports_are_deduplicated():
    with pytest.raises(ConnectionUnavailableError):
        select_device([device("a", "Network"), device("b", "Network")], True)
    usb = device("a", "USB")
    assert select_device([usb, device("a", "Network")], True) is usb


def client(serial, paired=True):
    return SimpleNamespace(udid=serial, paired=paired, close=AsyncMock())


def test_wifi_discovery_filters_identity_and_closes_other_clients():
    pytest.importorskip("pymobiledevice3")
    from adb_auto_player.device.ios import wifi

    async def run():
        tablet, other = client("tablet"), client("phone")

        async def discovered(**kwargs):
            assert kwargs["only_paired"] is True
            yield "local", tablet
            yield "local", other

        with patch.object(wifi, "get_mobdev2_lockdowns", discovered):
            assert await wifi.open_wifi_lockdown("tablet") is tablet
        other.close.assert_awaited_once()
        tablet.close.assert_not_awaited()

    asyncio.run(run())


def test_ambiguous_wifi_discovery_closes_all_connections():
    pytest.importorskip("pymobiledevice3")
    from adb_auto_player.device.ios import wifi

    async def run():
        clients = [client("tablet"), client("phone")]

        async def discovered(**kwargs):
            for entry in clients:
                yield "local", entry

        with patch.object(wifi, "get_mobdev2_lockdowns", discovered):
            with pytest.raises(ConnectionUnavailableError):
                await wifi.open_wifi_lockdown()
        for entry in clients:
            entry.close.assert_awaited_once()

    asyncio.run(run())


@pytest.mark.parametrize("fail", [False, True])
def test_pinned_provider_adapter_restores_factory_even_on_failure(fail):
    pytest.importorskip("pymobiledevice3")
    from adb_auto_player.device.ios import wifi

    async def run():
        original = wifi.userspace_tunnel._create_no_root_tunnel_provider
        primary, unused = (
            SimpleNamespace(close=AsyncMock()),
            SimpleNamespace(close=AsyncMock()),
        )

        async def open_tunnel(self):
            (
                provider,
                lockdown,
            ) = await wifi.userspace_tunnel._create_no_root_tunnel_provider(
                "tablet", False
            )
            assert provider is primary and lockdown is None
            if fail:
                raise OSError("lost Wi-Fi")
            return "connected"

        with (
            patch.object(
                wifi,
                "get_remote_pairing_tunnel_services",
                AsyncMock(return_value=[primary, unused]),
            ) as discover,
            patch.object(
                wifi.userspace_tunnel.UserspaceRsdTunnel, "_aopen_locked", open_tunnel
            ),
        ):
            tunnel = wifi.LockdownRsdTunnel(client("tablet"))
            if fail:
                with pytest.raises(OSError):
                    await tunnel._aopen_locked()
            else:
                assert await tunnel._aopen_locked() == "connected"
            discover.assert_awaited_once_with(udid="tablet", bonjour_timeout=5)
        assert wifi.userspace_tunnel._create_no_root_tunnel_provider is original
        unused.close.assert_awaited_once()

    asyncio.run(run())
