"""Preferences, optional audio, and animation lifecycle regressions."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

from hog_audio import EFFECTS, SoundPlayer
from hog_preferences import (PALETTES, Preferences, default_preferences_path,
                             load_preferences, save_preferences)


class PreferencesTests(unittest.TestCase):
    def test_round_trip_and_no_temporary_files_left(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "Hog/settings.json"
            expected = Preferences("light", False, True, "fast")
            save_preferences(path, expected)
            self.assertEqual(load_preferences(path), expected)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_missing_and_malformed_files_use_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            self.assertEqual(load_preferences(path), Preferences())
            for content in ("broken {", "[]", '{"theme":"unknown"}',
                            '{"sound":"yes"}', '{"pace":12}'):
                path.write_text(content)
                self.assertEqual(load_preferences(path), Preferences())

    def test_future_keys_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            path.write_text(json.dumps({"theme": "light", "future_setting": 12}))
            self.assertEqual(load_preferences(path).theme, "light")

    def test_preferences_validation(self):
        for changes in (dict(theme="invalid"), dict(pace="invalid"),
                        dict(sound=1), dict(animations="false")):
            with self.assertRaises(ValueError):
                Preferences(**changes)

    def test_atomic_failure_keeps_previous_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            save_preferences(path, Preferences())
            with patch("hog_preferences.os.replace", side_effect=OSError("read only")):
                with self.assertRaises(OSError):
                    save_preferences(path, Preferences(theme="light"))
            self.assertEqual(load_preferences(path), Preferences())
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_settings_path_stays_outside_source_tree(self):
        with patch("hog_preferences.sys.platform", "linux"), \
                patch.dict("os.environ", {"XDG_CONFIG_HOME": "/tmp/test-hog-config"}):
            self.assertEqual(default_preferences_path(), Path("/tmp/test-hog-config/Hog/settings.json"))

    def test_light_and_dark_text_contrast(self):
        def brightness(color):
            channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4
                      for channel in channels]
            return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))

        for palette in PALETTES.values():
            for foreground, background in ((palette.text, palette.panel),
                                           (palette.muted, palette.panel),
                                           (palette.accent_text, palette.accent)):
                low, high = sorted((brightness(foreground), brightness(background)))
                self.assertGreaterEqual((high + .05) / (low + .05), 4.5)


class AudioTests(unittest.TestCase):
    def player(self, enabled=True):
        with patch.object(SoundPlayer, "_detect_backend", return_value=None):
            return SoundPlayer(enabled=enabled)

    def test_missing_backend_and_mute_are_safe(self):
        player = self.player()
        self.assertFalse(player.available)
        self.assertFalse(player.play("win"))
        player.enabled = False
        self.assertFalse(player.play("roll"))
        player.stop()

    def test_bundled_wav_assets_are_readable_and_short(self):
        directory = Path(__file__).resolve().parents[1] / "assets/sounds"
        for name in EFFECTS:
            with wave.open(str(directory / f"{name}.wav")) as stream:
                self.assertEqual((stream.getnchannels(), stream.getsampwidth()), (1, 2))
                self.assertGreater(stream.getnframes(), 0)
                self.assertLess(stream.getnframes() / stream.getframerate(), 1)

    def test_external_player_uses_argument_list_and_can_stop(self):
        player = self.player()
        player.backend = ("aplay", "/usr/bin/aplay")
        process = Mock()
        process.poll.return_value = None
        with patch("hog_audio.subprocess.Popen", return_value=process) as launch:
            self.assertTrue(player.play("bonus"))
            args = launch.call_args.args[0]
            self.assertEqual(args[0], "/usr/bin/aplay")
            self.assertTrue(args[1].endswith("bonus.wav"))
            player.stop()
            process.terminate.assert_called_once()

    def test_windows_async_flags_and_stop(self):
        player = self.player()
        module = SimpleNamespace(PlaySound=Mock(), SND_FILENAME=1, SND_ASYNC=2, SND_NODEFAULT=4)
        player.backend = ("winsound", module)
        self.assertTrue(player.play("win"))
        self.assertEqual(module.PlaySound.call_args.args[1], 7)
        player.stop()
        self.assertEqual(module.PlaySound.call_args.args, (None, 0))

    def test_playback_failure_does_not_escape_into_game(self):
        player = self.player()
        player.backend = ("paplay", "/missing/paplay")
        with patch("hog_audio.subprocess.Popen", side_effect=OSError("no audio")):
            self.assertFalse(player.play("win"))
            self.assertTrue(player.last_error)

    def test_unknown_effect_is_rejected(self):
        self.assertFalse(self.player().play("../settings"))


if __name__ == "__main__":
    unittest.main()
