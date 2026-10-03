"""Apple USB implementation of the device operations used by existing games."""

import logging
import shutil
import tempfile
import json
from pathlib import Path
import queue
import subprocess
import threading
import weakref

from adb_auto_player.exceptions import AutoPlayerUnrecoverableError
from adb_auto_player.file_loader import SettingsLoader
from adb_auto_player.models.device import DisplayInfo, Orientation
from .integration import worker_command, worker_environment


class IOSController:
    """Keep game commands and settings shared; translate only device operations."""

    _instances = weakref.WeakSet()
    stop_requested = staticmethod(lambda: False)

    def __init__(self, resolution):
        self.resolution = resolution
        self._lock = threading.RLock()
        self._responses = queue.Queue()
        self._process = None
        self._session = None
        self.metadata = {}
        self._instances.add(self)

    def _connect(self):
        if self._process is not None:
            return
        self._responses = queue.Queue()
        self._session = Path(tempfile.mkdtemp(prefix="adb-ios-"))
        command = worker_command()
        command[-1] = str(Path(__file__).with_name("device_worker.py"))
        command += [
            "--workdir",
            str(SettingsLoader.get_app_config_dir().parent / "ios-device"),
            "--session",
            str(self._session),
            "--width",
            str(self.resolution.width),
            "--height",
            str(self.resolution.height),
        ]
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW,
            env=worker_environment(),
        )

        process = self._process
        responses = self._responses

        def read_responses():
            try:
                for line in process.stdout:
                    responses.put(json.loads(line))
            except Exception as exc:
                responses.put({"error": str(exc)})
            finally:
                responses.put({"error": "Apple USB worker disconnected."})

        threading.Thread(target=read_responses, daemon=True).start()

    def request(self, action, **values):
        """Serialize device requests and interrupt them when Stop is requested."""
        with self._lock:
            if self.stop_requested():
                raise KeyboardInterrupt
            self._connect()
            try:
                self._process.stdin.write(
                    json.dumps({"action": action, **values}) + "\n"
                )
                self._process.stdin.flush()
            except (OSError, ValueError) as exc:
                raise AutoPlayerUnrecoverableError(
                    "iOS worker disconnected. Reconnect and unlock the device, then restart the task."
                ) from exc
            for _ in range(360):
                if self.stop_requested():
                    raise KeyboardInterrupt
                try:
                    result = self._responses.get(timeout=0.25)
                    break
                except queue.Empty:
                    continue
            else:
                raise AutoPlayerUnrecoverableError("Apple USB request timed out.")
            if "error" in result:
                raise AutoPlayerUnrecoverableError(result["error"])
            return result.get("value")

    @property
    def identifier(self):
        return "Apple USB"

    def get_display_info(self):
        self._update_metadata(self.request("check_orientation"))
        orientation = (
            Orientation.PORTRAIT
            if self.resolution.height > self.resolution.width
            else Orientation.LANDSCAPE
        )
        return DisplayInfo(resolution=self.resolution, orientation=orientation)

    def _update_metadata(self, metadata):
        if not self.metadata:
            logging.info(
                "iOS device: %s; iOS %s; native screenshot %s; canvas %s",
                metadata["model"],
                metadata["ios_version"],
                metadata["native_size"],
                metadata["canvas_size"],
            )
            ratio = metadata["native_size"][1] / metadata["native_size"][0]
            if not 2.1 <= ratio <= 2.25:
                logging.warning(
                    "This iOS aspect ratio is unverified (iPad/SE layouts require testing). Capture a debug report before automation."
                )
        self.metadata = metadata

    def screenshot(self, package_name_prefixes=None):
        self._update_metadata(self.request("screenshot"))
        return (self._session / "frame.bmp").read_bytes()

    def capture_debug(self, destination):
        """Save one native frame and its exact normalized counterpart locally."""
        self._update_metadata(self.request("debug_capture"))
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._session / "native.png", destination / "native.png")
        shutil.copyfile(self._session / "frame.bmp", destination / "normalized.bmp")
        return dict(self.metadata)

    def set_display_size(self, display_size):
        raise AutoPlayerUnrecoverableError(
            "iOS uses a virtual canvas; its physical display cannot be resized."
        )

    def tap(self, coordinates):
        self.request("tap", x=coordinates.x, y=coordinates.y)

    click = tap

    def swipe(self, start_point, end_point, duration=1.0):
        self.request(
            "swipe",
            x=start_point.x,
            y=start_point.y,
            end_x=end_point.x,
            end_y=end_point.y,
            duration=duration,
        )

    def hold(self, coordinates, duration=1.0):
        self.request(
            "swipe",
            x=coordinates.x,
            y=coordinates.y,
            end_x=coordinates.x,
            end_y=coordinates.y,
            duration=duration,
        )

    def get_running_app(self):
        return self.request("running_app")

    def start_game(self, package_name):
        self.request("start", package=package_name)

    def stop_game(self, package_name):
        self.request("stop", package=package_name)

    def press_back_button(self):
        raise AutoPlayerUnrecoverableError(
            "iOS has no system Back key; use a verified game navigation template."
        )

    def press_enter(self):
        raise AutoPlayerUnrecoverableError(
            "This game action requires an Enter-key mapping for iOS."
        )

    def resolve_display_targeting(self, package_name_prefixes):
        self.request("select_game", packages=package_name_prefixes)

    def reset_display_targeting(self):
        pass

    def is_controlling_emulator(self):
        return False

    def close(self):
        if self._process is not None:
            process, self._process = self._process, None
            if process.poll() is None:
                process.stdin.close()  # EOF lets the worker release USB resources.
                try:
                    process.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5)

        if self._session is not None:
            shutil.rmtree(self._session, ignore_errors=True)
            self._session = None
        self.metadata = {}

    @classmethod
    def close_all(cls):
        for instance in list(cls._instances):
            instance.close()
