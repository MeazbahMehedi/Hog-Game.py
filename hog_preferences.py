"""Theme tokens and validated, atomically saved desktop preferences."""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
import tempfile


@dataclass(frozen=True)
class Palette:
    bg: str
    panel: str
    raised: str
    border: str
    text: str
    muted: str
    accent: str
    accent_text: str
    gold: str
    red: str
    disabled: str
    die: str
    pip: str
    shadow: str
    hero: str


PALETTES = {
    "dark": Palette("#0d1626", "#17243a", "#20324c", "#30445e", "#eef3f8",
                    "#a3b4ca", "#85e0ba", "#0d1626", "#f4c375", "#ff9c9c",
                    "#71869f", "#eff5f4", "#172a32", "#080f1c", "#1d3b3a"),
    "light": Palette("#f3f6f8", "#ffffff", "#e6edf1", "#cedae1", "#152c36",
                     "#536976", "#147758", "#ffffff", "#92540a", "#b32e43",
                     "#86979f", "#f4f8fa", "#172a32", "#d3dfe5", "#deeee7"),
    "contrast": Palette("#000001", "#101011", "#262627", "#eeeeed", "#ffffff",
                        "#dededf", "#ffdf00", "#000000", "#71e4ff", "#ffb0ba",
                        "#b8b8b9", "#fffffe", "#010101", "#303031", "#242425"),
}

PALETTES.update({
    "aurora": Palette("#081b22", "#102e37", "#19434f", "#365963", "#efffff",
                      "#b2d6df", "#5eead4", "#062c2d", "#f5cf83", "#ffadad",
                      "#7b99a0", "#e6fffb", "#123033", "#031215", "#164f50"),
    "twilight": Palette("#191329", "#271d3e", "#382950", "#5c4674", "#f6efff",
                        "#c8b6e0", "#d8b4fe", "#2e124e", "#f9cc8a", "#ffacbc",
                        "#9685ab", "#faf2ff", "#351b49", "#0d0718", "#46315f"),
})

BASE_THEMES = ("dark", "light", "contrast")

PACE_DELAYS = {"relaxed": 1200, "normal": 700, "fast": 220}


@dataclass(frozen=True)
class Preferences:
    theme: str = "dark"
    animations: bool = True
    sound: bool = False
    pace: str = "normal"
    large_text: bool = False
    welcome_seen: bool = False
    shortcuts: tuple = ("Return", "p", "r", "h", "t", "m", "Escape", "F1", "x")

    def __post_init__(self):
        from hog_controls import validate_shortcuts
        object.__setattr__(self, "shortcuts", validate_shortcuts(self.shortcuts))
        if type(self.welcome_seen) is not bool:
            raise ValueError("Welcome status must be true or false.")
        if self.theme not in PALETTES or self.pace not in PACE_DELAYS:
            raise ValueError("Unknown theme or computer pace.")
        if type(self.animations) is not bool or type(self.sound) is not bool or type(self.large_text) is not bool:
            raise ValueError("Animation and sound settings must be true or false.")


def default_preferences_path():
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "Hog" / "settings.json"


def load_preferences_with_notice(path):
    """Read legacy/current preferences without mutating an unreadable file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Expected settings object")
        keys = ("theme", "animations", "sound", "pace", "large_text", "welcome_seen", "shortcuts")
        return Preferences(**{key: data[key] for key in keys if key in data}), ""
    except FileNotFoundError:
        return Preferences(), ""
    except (OSError, ValueError, TypeError):
        return Preferences(), "Settings could not be read; defaults are active. Saving a setting will replace the settings file."


def load_preferences(path):
    """Use defaults for missing, malformed or invalid preferences."""
    return load_preferences_with_notice(path)[0]


def save_preferences(path, preferences):
    """Write beside the destination then replace it; report OS errors to caller."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(asdict(preferences), stream, indent=2)
            stream.write("\n")
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
