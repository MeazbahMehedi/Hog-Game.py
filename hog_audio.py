"""Optional, nonblocking WAV playback with no required Python packages."""

from pathlib import Path
import shutil
import subprocess
import sys

EFFECTS = ("roll", "sow", "bonus", "win")


class SoundPlayer:
    def __init__(self, enabled=False, *, directory=None):
        self.directory = Path(directory) if directory else Path(__file__).parent / "assets/sounds"
        self.enabled = enabled
        self.process = None
        self.backend = self._detect_backend()
        self.last_error = ""

    @staticmethod
    def _detect_backend():
        if sys.platform == "win32":
            try:
                import winsound
                return "winsound", winsound
            except ImportError:
                return None
        commands = ("afplay",) if sys.platform == "darwin" else ("paplay", "aplay")
        for command in commands:
            executable = shutil.which(command)
            if executable:
                return command, executable
        return None

    @property
    def available(self):
        return self.backend is not None

    @property
    def description(self):
        return self.backend[0] if self.backend else "No WAV playback backend detected"

    def stop(self):
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    self.process.terminate()
                except OSError:
                    pass
            self.process = None
        if self.backend and self.backend[0] == "winsound":
            try:
                self.backend[1].PlaySound(None, 0)
            except (OSError, RuntimeError):
                pass

    def play(self, effect):
        if not self.enabled or not self.available or effect not in EFFECTS:
            return False
        path = self.directory / f"{effect}.wav"
        if not path.is_file():
            self.last_error = "A sound asset is missing. Play continues silently."
            return False
        self.stop()
        try:
            if self.backend[0] == "winsound":
                module = self.backend[1]
                module.PlaySound(str(path), module.SND_FILENAME | module.SND_ASYNC | module.SND_NODEFAULT)
            else:
                self.process = subprocess.Popen([self.backend[1], str(path)],
                                                stdin=subprocess.DEVNULL,
                                                stdout=subprocess.DEVNULL,
                                                stderr=subprocess.DEVNULL)
            self.last_error = ""
            return True
        except (OSError, RuntimeError):
            self.last_error = "Sound playback failed. Play continues silently."
            return False
