"""Local USB video frames using pymobiledevice3's pinned HEVC pipeline.

No VNC/HTTP listener, audio, clipboard, or remote input is started here.
Only the library's RTP depacketizer, decoder recovery, and RTCP keepalive
are reused. The application consumes the newest frame on demand.
"""

import asyncio
import contextlib
import threading

from pymobiledevice3.remote.core_device.display_service import DisplayService
from pymobiledevice3.remote.core_device.hevc_av import HevcToBgraTranscoder
from pymobiledevice3.remote.core_device.screen_stream import open_media_receiver
from pymobiledevice3.remote.core_device.vnc_server import VncStreamServer

MAX_DECODE_QUEUE = 8
MAX_PADDING = 31


class _FrameDecoder(HevcToBgraTranscoder):
    """Retain decoded video frames; avoid converting 60 full frames per second."""

    def _emit_frame(self, frame):
        self._on_frame(frame)

    def feed(self, annexb):
        if self._inq.qsize() >= MAX_DECODE_QUEUE:
            raise RuntimeError("Apple video decoder cannot keep up; capture stopped.")
        super().feed(annexb)


class _FramePipeline(VncStreamServer):
    """Use the media pipeline without starting the library's server."""

    def __init__(self, rsd):
        super().__init__(rsd, decoder="av", audio=False, share_clipboard=False)
        self._transcoder_cls = _FrameDecoder
        self._delivery_lock = threading.Lock()
        self._pending_frame = None
        self._delivery_queued = False
        self._closed = False
        self.frame_at = 0
        self.changed = asyncio.Event()

    def _on_frame_from_worker(self, frame):
        # One pending callback/frame, even if the event loop is occupied by
        # image matching or a slow filesystem. Never queue full RGB frames.
        with self._delivery_lock:
            if self._closed:
                return
            self._pending_frame = frame
            if self._delivery_queued:
                return
            self._delivery_queued = True
        self._loop.call_soon_threadsafe(self._deliver_frame)

    def _deliver_frame(self):
        with self._delivery_lock:
            frame = self._pending_frame
            self._pending_frame = None
            self._delivery_queued = False
        if self._closed or frame is None:
            return
        super()._broadcast_frame(frame)
        self.frame_at = self._loop.time()
        self.changed.set()


class VideoCapture:
    """One closeable media session with bounded buffering and fresh reads."""

    def __init__(self, rsd, native_size):
        self.rsd = rsd
        self.native_size = native_size
        self.pipeline = _FramePipeline(rsd)
        self.service = DisplayService(rsd)
        self.transport = None
        self.tasks = []
        self.started = False
        self.closed = False

    async def __aenter__(self):
        """Start local media reception and wait for a validated first frame."""
        try:
            await asyncio.wait_for(self.service.connect(), 10)
            self.transport, ip = open_media_receiver(
                self.service, (8 * 1024 * 1024, 4 * 1024 * 1024)
            )
            self.started = True
            answer = await asyncio.wait_for(
                self.service.start_video_stream(
                    receiver_ip=ip,
                    receiver_port=self.transport.port,
                    sender_ip=self.pipeline._sender_ip,
                    allow_rtcp_fb=False,
                    ltrp_enabled=False,
                ),
                20,
            )
            cfg = answer["connection"].get("streamConfig", {})
            pipe = self.pipeline
            pipe._loop = asyncio.get_running_loop()
            pipe._local_ssrc = int(cfg.get("RemoteSSRC", 0))
            pipe._remote_ssrc = int(cfg.get("LocalSSRC", 0))
            source = int(cfg.get("SourcePort", 0))
            if not source or not pipe._local_ssrc or not pipe._remote_ssrc:
                raise RuntimeError("Apple video did not negotiate a keepalive channel.")
            pipe._rtcp_dest = (pipe._sender_ip, source)
            pipe._active_transport = self.transport
            self.tasks = [
                asyncio.create_task(pipe._udp_recv_and_pipe(self.transport)),
                asyncio.create_task(pipe._rtcp_send_loop(self.transport)),
                asyncio.create_task(pipe._decoder_refresh_loop()),
            ]
            await self.read()
            return self
        except BaseException:
            await self.close()
            raise

    async def read(self):
        """Wait for a newly decoded frame; reject stale or changed geometry."""
        pipe = self.pipeline
        requested_at = asyncio.get_running_loop().time()

        async def fresh():
            while pipe.frame_at <= requested_at:
                for task in self.tasks:
                    if task.done():
                        task.result()
                        raise RuntimeError("Apple video receiver stopped.")
                pipe.changed.clear()
                await pipe.changed.wait()
            return pipe._latest_frame

        try:
            frame = await asyncio.wait_for(fresh(), 3)
        except TimeoutError as exc:
            raise RuntimeError(
                "No fresh Apple video frame arrived within 3 seconds."
            ) from exc
        width, height = self.native_size
        # Apple rounds its coded frame up to codec block boundaries. The
        # native screenshot establishes the visible top-left pixel rectangle.
        # A resolution/orientation change must never alter input mapping.
        if not (
            width <= frame.width <= width + MAX_PADDING
            and height <= frame.height <= height + MAX_PADDING
        ):
            raise RuntimeError("Apple video dimensions changed; recapture required.")
        pixels = await asyncio.to_thread(frame.to_ndarray, format="bgr24")
        return pixels[:height, :width].copy()

    async def __aexit__(self, *args):
        """Close the media session when its owning device disconnects."""
        await self.close()

    async def close(self):
        """Release only this session's tasks, decoder, and media transport."""
        if self.closed:
            return
        self.closed = True
        self.pipeline._closed = True
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.pipeline._transcoder:
            await asyncio.to_thread(self.pipeline._transcoder.close)
        if self.transport:
            self.transport.close()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.service.close(), 1)
        if self.started:
            # The stop request must use a fresh XPC connection.
            with contextlib.suppress(Exception):
                await asyncio.wait_for(DisplayService.stop_all_streams(self.rsd), 2)
