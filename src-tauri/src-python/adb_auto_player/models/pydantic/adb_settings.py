from typing import Annotated

from pydantic import BaseModel, Field

from .toml_settings import TomlSettings

# Type constraints
PortInt = Annotated[int, Field(ge=1024, le=65535)]
FPSInt = Annotated[int, Field(ge=1, le=60)]
NonNegativeInt = Annotated[int, Field(ge=0)]
VerticalOffsetInt = Annotated[int, Field(ge=-500, le=500)]


class AdvancedSettings(BaseModel):
    """Advanced settings model."""

    adb_host: str = Field("127.0.0.1", title="ADB Host")
    adb_port: PortInt = Field(5037, title="ADB Port")
    hardware_decoding: bool = Field(False, title="Enable Hardware Decoding")
    auto_resolve_device: bool = Field(
        True,
        title="Automatically Select Available Device",
    )


class DeviceSettings(BaseModel):
    """ADB Device settings model."""

    id: str = Field("127.0.0.1:5555", title="Device ID")
    streaming: bool = Field(True, title="Real-time Display Streaming")
    streaming_fps: FPSInt = Field(30, title="Streaming FPS")
    use_wm_resize: bool = Field(False, title="Resize Display (Phone/Tablet)")
    vertical_offset: VerticalOffsetInt = Field(
        0,
        title="Vertical Screen Offset (px)",
    )


class IOSSettings(BaseModel):
    """Device transport selection, independent of game settings."""

    enabled: bool = Field(
        False,
        title="Enable iOS",
        description="Windows USB connection. Open AFK Journey in "
        "English on an unlocked, "
        "trusted iPhone with Developer Mode enabled. Tested on iPhone 17 Pro Max, "
        "iOS 27, portrait 1320 x 2868. Selects the Apple USB connection; "
        "configure game behavior in Game Settings. Other iPhone/iPad layouts "
        "and game modes still require device support.",
    )
    python_path: str = Field(
        "",
        title="iOS Python Path",
        description="Leave blank to use the bundled iOS runtime. "
        "Advanced: path to Python 3.11 with the iOS requirements installed.",
    )


class AdbSettings(TomlSettings):
    """Adb settings model."""

    ios: IOSSettings = Field(
        default_factory=IOSSettings, title="iPhone / iOS (Experimental)"
    )
    device: DeviceSettings = Field(default_factory=DeviceSettings, title="Device")
    advanced: AdvancedSettings = Field(
        default_factory=AdvancedSettings, title="Advanced"
    )
