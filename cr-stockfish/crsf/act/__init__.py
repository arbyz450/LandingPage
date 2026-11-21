"""Acting on the game: ADB taps, mouse clicks, window messages, and the autoplay policy."""
from .adb import AdbDevice, AdbSource, AdbActuator, MouseActuator, EMULATOR_PORTS  # noqa: F401
from .winmsg import WindowMessageActuator  # noqa: F401
