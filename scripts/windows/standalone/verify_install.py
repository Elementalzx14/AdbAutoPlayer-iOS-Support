"""Check a clean full installation, with no overlay or external Python paths."""
# ruff: noqa: F401
import json
import sys
from importlib.metadata import version
from pathlib import Path

import av
import cv2
import lzfse
import numpy
import adb_auto_player
from adb_auto_player.device.ios.phone import Phone
from adb_auto_player.device.ios.video import VideoCapture
from adb_auto_player.games.afk_journey.base import AFKJourneyBase
from adb_auto_player.models.pydantic.adb_settings import AdbSettings

app = Path(sys.executable).resolve().parent
assert Path(adb_auto_player.__file__).resolve().is_relative_to(app)
assert (app / "adb-auto-player.exe").is_file()
assert (app / "binaries/adb.exe").is_file()
assert (app / "games/afk_journey/templates/battle/battle.png").is_file()
profile = app / "Lib/site-packages/adb_auto_player/games/afk_journey/ios_templates/ipad/manifest.json"
assert profile.is_file()
assert not (app / "ios-support-install.json").exists(), "No overlay marker should be needed"
assert not (app / "ios-runtime").exists(), "Use one bundled runtime"
assert "allow_wifi" in AdbSettings.model_fields["ios"].annotation.model_fields
print(json.dumps({"python": sys.version.split()[0], "app": version("adb-auto-player"), "pymobiledevice3": version("pymobiledevice3"), "av": av.__version__, "clean_install": True}))

