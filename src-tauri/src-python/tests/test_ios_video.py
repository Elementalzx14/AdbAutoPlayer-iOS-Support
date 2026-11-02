"""Video freshness, buffering, geometry, and screenshot fallback."""

import asyncio
import queue
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import cv2
import numpy as np
import pytest

pytest.importorskip("pymobiledevice3")
from adb_auto_player.device.ios.phone import Phone
from adb_auto_player.device.ios.video import (
    MAX_DECODE_QUEUE,
    VideoCapture,
    _FrameDecoder,
    _FramePipeline,
)


def test_decoder_queue_is_bounded():
    decoder = object.__new__(_FrameDecoder)
    decoder._inq = queue.Queue()
    for _ in range(MAX_DECODE_QUEUE):
        decoder._inq.put(b"frame")
    with pytest.raises(RuntimeError, match="cannot keep up"):
        decoder.feed(b"next")
    assert decoder._inq.qsize() == MAX_DECODE_QUEUE


def test_frame_delivery_coalesces_when_consumer_is_busy():
    pipe = object.__new__(_FramePipeline)
    pipe._delivery_lock = threading.Lock()
    pipe._closed = False
    pipe._delivery_queued = False
    pipe._loop = MagicMock()
    for frame in range(100):
        pipe._on_frame_from_worker(frame)
    pipe._loop.call_soon_threadsafe.assert_called_once()
    assert pipe._pending_frame == 99


@pytest.mark.parametrize("bad_geometry", [False, True])
def test_read_waits_for_new_frame_and_checks_geometry(bad_geometry):
    async def run():
        capture = object.__new__(VideoCapture)
        capture.native_size = (100, 200)
        capture.tasks = []
        old = MagicMock()
        capture.pipeline = SimpleNamespace(
            frame_at=0,
            changed=asyncio.Event(),
            _latest_frame=old,
        )
        pixels = np.full((216, 112, 3), 120, dtype=np.uint8)
        frame = SimpleNamespace(
            width=90 if bad_geometry else 112,
            height=216,
            to_ndarray=MagicMock(return_value=pixels),
        )

        async def publish():
            await asyncio.sleep(0.01)
            capture.pipeline._latest_frame = frame
            capture.pipeline.frame_at = asyncio.get_running_loop().time()
            capture.pipeline.changed.set()

        producer = asyncio.create_task(publish())
        if bad_geometry:
            with pytest.raises(RuntimeError, match="dimensions changed"):
                await capture.read()
            frame.to_ndarray.assert_not_called()
        else:
            result = await capture.read()
            assert result.shape == (200, 100, 3)
            assert (result == 120).all()
        old.to_ndarray.assert_not_called()
        await producer

    asyncio.run(run())


def test_failed_receiver_cannot_return_cached_frame():
    async def run():
        capture = object.__new__(VideoCapture)
        capture.native_size = (100, 200)
        capture.pipeline = SimpleNamespace(
            frame_at=0,
            changed=asyncio.Event(),
            _latest_frame=MagicMock(),
        )

        async def failure():
            raise RuntimeError("USB receiver failed")

        capture.tasks = [asyncio.create_task(failure())]
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match="USB receiver failed"):
            await capture.read()

    asyncio.run(run())


def test_video_failure_releases_old_hid_and_falls_back_without_input(tmp_path):
    async def run():
        phone = Phone(tmp_path)
        phone.ensure_unlocked = AsyncMock()
        phone.video_attempted = True
        video = SimpleNamespace(
            read=AsyncMock(side_effect=TimeoutError()), close=AsyncMock()
        )
        hid = SimpleNamespace(close=AsyncMock())
        phone.video, phone.hid = video, hid
        frame = np.zeros((200, 100, 3), dtype=np.uint8)
        _, encoded = cv2.imencode(".png", frame)
        phone.screenshot = AsyncMock(return_value=encoded.tobytes())
        result = await phone.capture_frame()
        assert result.shape == frame.shape
        assert phone.video is None and phone.hid is None
        assert phone.capture_source == "screenshot"
        video.close.assert_awaited_once()
        hid.close.assert_awaited_once()
        phone.screenshot.assert_awaited_once()

    asyncio.run(run())
