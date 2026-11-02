"""Distinguish the real tablet OS restriction from connection failures."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("pymobiledevice3")

from pymobiledevice3.exceptions import CoreDeviceError

from adb_auto_player.device.ios.device_worker import device_error
from adb_auto_player.device.ios.phone import (
    REQUIRED_SERVICES,
    Phone,
    RemoteControlUnavailableError,
)


def make_phone(tmp_path):
    phone = Phone(tmp_path)
    phone.lockdown = SimpleNamespace(get_value=AsyncMock(return_value=False))
    phone.rsd = SimpleNamespace(product_type="iPad13,16", product_version="18.0.1")
    return phone


def test_tablet_os_rejection_explains_update_without_sending_a_touch(tmp_path):
    phone = make_phone(tmp_path)
    rejection = CoreDeviceError(
        "Remote control requires iOS 27.0 or later on this device.", code=9021
    )
    phone.stack.enter_async_context = AsyncMock(side_effect=rejection)
    with (
        patch("adb_auto_player.device.ios.phone.touch_session"),
        pytest.raises(RemoteControlUnavailableError) as error,
    ):
        asyncio.run(phone.tap(20, 20, 1640, 2360))
    assert phone.hid is None
    message = device_error(error.value)
    assert "iPad13,16" in message and "18.0.1" in message
    assert "27.0" in message and "Software Update" in message
    assert "Check USB" not in message
    assert error.value.__cause__ is rejection


def test_other_coredevice_failures_are_not_misreported_as_os_restrictions(tmp_path):
    phone = make_phone(tmp_path)
    failure = CoreDeviceError("Camera is in use", code=99)
    phone.stack.enter_async_context = AsyncMock(side_effect=failure)
    with (
        patch("adb_auto_player.device.ios.phone.touch_session"),
        pytest.raises(CoreDeviceError) as error,
    ):
        asyncio.run(phone.ensure_touch_session())
    assert error.value is failure


def test_existing_touch_session_checks_lock_but_does_not_reopen(tmp_path):
    phone = make_phone(tmp_path)
    phone.hid = object()
    phone.stack.enter_async_context = AsyncMock()
    asyncio.run(phone.ensure_touch_session())
    phone.lockdown.get_value.assert_awaited_once()
    phone.stack.enter_async_context.assert_not_awaited()


def test_ready_device_does_not_mount_or_download_developer_support(tmp_path):
    phone = make_phone(tmp_path)
    phone.rsd.peer_info = {"Services": dict.fromkeys(REQUIRED_SERVICES)}
    asyncio.run(phone.ensure_developer_services())
    phone.lockdown.get_value.assert_not_awaited()


@pytest.mark.parametrize("mount_error", [None, RuntimeError("Reply channel closed")])
def test_missing_services_mount_through_rsd_and_refresh_advertisements(
    tmp_path, mount_error
):
    phone = make_phone(tmp_path)
    original = phone.rsd
    original.peer_info = {"Services": {}}
    original.service = SimpleNamespace(address=("::1", 1234))
    original.open_connection = object()
    original.handshake_uuid = None
    phone.lockdown.get_developer_mode_status = AsyncMock(return_value=True)
    fresh = SimpleNamespace(
        connect=AsyncMock(),
        close=AsyncMock(),
        peer_info={"Services": dict.fromkeys(REQUIRED_SERVICES)},
    )
    with (
        patch(
            "pymobiledevice3.services.mobile_image_mounter.auto_mount",
            new_callable=AsyncMock,
        ) as mount,
        patch(
            "adb_auto_player.device.ios.phone.RemoteServiceDiscoveryService",
            return_value=fresh,
        ),
    ):
        mount.side_effect = mount_error
        asyncio.run(phone.ensure_developer_services())
    mount.assert_awaited_once_with(original)
    assert phone.rsd is fresh
    asyncio.run(phone.stack.aclose())
    fresh.close.assert_awaited_once()


def test_disabled_developer_mode_is_reported_without_mounting(tmp_path):
    phone = make_phone(tmp_path)
    phone.rsd.peer_info = {"Services": {}}
    phone.lockdown.get_developer_mode_status = AsyncMock(return_value=False)
    with pytest.raises(RuntimeError, match="Enable Developer Mode"):
        asyncio.run(phone.ensure_developer_services())
