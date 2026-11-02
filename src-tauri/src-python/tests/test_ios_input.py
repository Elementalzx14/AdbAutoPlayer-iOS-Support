"""Held input must allow vision, release on stop, and cancel stale taps."""

import asyncio
import json
import threading
from contextlib import asynccontextmanager, contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from adb_auto_player.device.ios.controller import IOSController
from adb_auto_player.models.device import Resolution
from adb_auto_player.models.geometry import Point


def _fake_worker(controller, stopped=None):
    down = threading.Event()
    state = {"held": False, "actions": []}

    def write(line):
        request = json.loads(line)
        action = request["action"]
        state["actions"].append(action)
        if action == "touch_down":
            state["held"] = True
            down.set()
            if stopped is not None:
                stopped.set()
        elif action == "touch_up":
            state["held"] = False
        elif action == "swipe":
            # Model the previous blocking worker operation: no other request
            # can pass until its acknowledgement arrives after release.
            state["held"] = True
            down.set()

            def finish():
                state["held"] = False
                controller._responses.put({"id": request["id"], "value": None})

            threading.Timer(request["duration"], finish).start()
            return
        value = {"held": state["held"]} if action == "screenshot" else None
        controller._responses.put({"id": request["id"], "value": value})

    controller._process = SimpleNamespace(
        stdin=SimpleNamespace(write=write, flush=lambda: None),
        poll=lambda: 0,
    )
    return down, state


def test_capture_request_completes_while_contact_is_held():
    device = IOSController(Resolution(1080, 1920))
    down, state = _fake_worker(device)
    thread = threading.Thread(target=device.hold, args=(Point(540, 350), 0.8))
    thread.start()
    try:
        assert down.wait(2)
        assert device.request("screenshot")["held"] is True
    finally:
        thread.join(2)
        device._process = None
    assert not thread.is_alive()
    assert state["actions"] == ["touch_down", "screenshot", "touch_up"]
    assert state["held"] is False


def test_stop_release_consumes_its_own_reply_instead_of_cancelled_down_reply():
    device = IOSController(Resolution(1080, 1920))
    stopped = threading.Event()
    _, state = _fake_worker(device, stopped)
    device.stop_requested = stopped.is_set
    with pytest.raises(KeyboardInterrupt):
        device.hold(Point(540, 350), 10)
    assert device._responses.empty()
    stopped.clear()
    assert device.request("screenshot") == {"held": False}
    device._process = None
    assert state["held"] is False


def test_stop_releases_contact_without_waiting_for_duration():
    device = IOSController(Resolution(1080, 1920))
    stopped = threading.Event()
    _, state = _fake_worker(device, stopped)
    device.stop_requested = stopped.is_set
    with pytest.raises(KeyboardInterrupt):
        device.hold(Point(540, 350), 10)
    device._process = None
    assert state["actions"] == ["touch_down", "touch_up"]
    assert state["held"] is False


def test_release_does_not_create_a_connection_after_stop():
    device = IOSController(Resolution(1080, 1920))
    device.stop_requested = lambda: True
    with patch.object(device, "_connect") as connect:
        assert device.request("touch_up") is None
        connect.assert_not_called()


def test_close_cancels_a_tap_queued_by_the_old_task():
    device = IOSController(Resolution(1080, 1920))
    waiting, resume = threading.Event(), threading.Event()

    @contextmanager
    def gate():
        waiting.set()
        assert resume.wait(2)
        yield

    device._input_lock = gate()
    device.request = MagicMock()
    thread = threading.Thread(target=device.tap, args=(Point(500, 1500),))
    thread.start()
    try:
        assert waiting.wait(2)
        device.close()
    finally:
        resume.set()
        thread.join(2)
    device.request.assert_not_called()


def test_owned_hold_is_released_before_hid_service_closes(tmp_path):
    pytest.importorskip("pymobiledevice3")
    from adb_auto_player.device.ios import phone as phone_module

    async def run():
        events = []

        async def send(state, *_):
            events.append(
                "down" if state == phone_module.TOUCHSCREEN_STATE_CONTACT else "up"
            )

        hid = SimpleNamespace(send_touchscreen=send)

        @asynccontextmanager
        async def session():
            try:
                yield hid
            finally:
                events.append("hid closed")

        phone = phone_module.Phone(tmp_path)
        phone.video = object()
        phone.ensure_unlocked = AsyncMock()
        with (
            patch.object(
                phone_module,
                "UniversalHIDServiceService",
                side_effect=lambda _: session(),
            ),
            patch.object(phone_module.asyncio, "sleep", new=AsyncMock()),
        ):
            await phone.begin_hold(10, 20, 100, 200)
            assert phone.held_contact is not None
            await phone._close_services()
        assert events == ["down", "up", "hid closed"]
        assert phone.held_contact is None

    asyncio.run(run())


def test_hold_deadline_releases_input_during_a_slow_native_capture(tmp_path):
    pytest.importorskip("pymobiledevice3")
    from adb_auto_player.device.ios import phone as phone_module

    async def run():
        started, finish, released = asyncio.Event(), asyncio.Event(), asyncio.Event()
        reports = []

        class Capture:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def capture_screenshot(self):
                started.set()
                await finish.wait()
                return {"image": b"native"}

        async def send(state, *_):
            reports.append(state)
            if state == phone_module.TOUCHSCREEN_STATE_RELEASE:
                released.set()

        phone = phone_module.Phone(tmp_path)
        phone.hid = SimpleNamespace(send_touchscreen=send)
        phone.ensure_touch_session = AsyncMock()
        phone.ensure_unlocked = AsyncMock()
        with patch.object(phone_module, "ScreenCaptureService", return_value=Capture()):
            await phone.begin_hold(10, 20, 100, 200, duration=0.02)
            capture = asyncio.create_task(phone.screenshot())
            try:
                await started.wait()
                await asyncio.wait_for(released.wait(), 1)
                assert phone.held_contact is None
                assert not capture.done()
            finally:
                finish.set()
                assert await capture == b"native"
                await phone.release_hold()
        assert reports == [
            phone_module.TOUCHSCREEN_STATE_CONTACT,
            phone_module.TOUCHSCREEN_STATE_RELEASE,
        ]

    asyncio.run(run())


def test_previous_hold_timer_cannot_release_a_new_contact(tmp_path):
    pytest.importorskip("pymobiledevice3")
    from adb_auto_player.device.ios import phone as phone_module

    async def run():
        phone = phone_module.Phone(tmp_path)
        phone.ensure_touch_session = AsyncMock()
        phone.hid = SimpleNamespace(send_touchscreen=AsyncMock())
        await phone.begin_hold(10, 20, 100, 200, duration=0.01)
        await phone.release_hold()
        await phone.begin_hold(30, 40, 100, 200, duration=0.5)
        try:
            await asyncio.sleep(0.04)
            assert phone.held_contact is not None
            assert phone.hid.send_touchscreen.await_count == 3
        finally:
            await phone.release_hold()
        assert phone.hid.send_touchscreen.await_count == 4

    asyncio.run(run())
