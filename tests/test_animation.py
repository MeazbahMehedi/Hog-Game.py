"""Real Tk animation and controls; no audio output is required."""

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import hog_desktop
from hog import STRATEGIES, play, seeded_dice, sus_update
from hog_match import MatchConfig
from hog_preferences import Preferences


class AnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hog_desktop.tk is None:
            raise unittest.SkipTest("Tkinter is not installed")
        try:
            probe = hog_desktop.tk.Tk()
            probe.destroy()
        except hog_desktop.tk.TclError:
            raise unittest.SkipTest("A display is needed for animation tests")

    def setUp(self):
        self.root = hog_desktop.tk.Tk()
        self.errors = []
        self.root.report_callback_exception = lambda kind, error, trace: self.errors.append(error)
        self.app = hog_desktop.HogApp(self.root, cpu_delay=600000)
        self.root.update()
        self.config = MatchConfig(1, ("Alice", "Computer"), ("adaptive", "sus"), 42)
        self.app.start_match(self.config)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [])

    def finish_animation(self):
        for _ in range(20):
            if not self.app.animating:
                break
            self.app.cancel_pending()
            self.app.animation_tick()
        self.assertFalse(self.app.animating)

    def test_animation_does_not_consume_scoring_dice_early(self):
        calls = []
        self.app.session.dice = lambda: calls.append(4) or 4
        self.app.select_count(3)
        self.app.roll_human()
        self.assertTrue(self.app.animating)
        self.assertEqual(calls, [])
        self.assertEqual(self.app.session.scores, (0, 0))
        self.app.roll_human()
        self.finish_animation()
        self.assertEqual(calls, [4, 4, 4])
        self.assertEqual(len(self.app.events), 1)
        self.assertEqual(self.app.events[0].outcomes, (4, 4, 4))

    def test_pause_freezes_animation_and_resumes_once(self):
        self.app.roll_human()
        self.app.toggle_pause()
        frame = self.app._animation_frame
        self.assertIsNone(self.app.pending)
        self.root.after(100, self.root.quit)
        self.root.mainloop()
        self.app.roll_human()
        self.assertEqual((self.app._animation_frame, self.app.session.scores), (frame, (0, 0)))
        self.app.toggle_pause()
        self.finish_animation()
        self.assertEqual(len(self.app.events), 1)

    def test_pause_stops_computer_turn_until_resume(self):
        self.app.start_match(replace(self.config, num_players=0))
        self.app.toggle_pause()
        self.app.computer_turn()
        self.assertEqual(self.app.events, [])
        self.app.toggle_pause()
        self.assertIsNotNone(self.app.pending)

    def test_reduced_motion_resolves_immediately(self):
        self.app.set_animations(False)
        self.app.select_count(3)
        self.app.roll_human()
        self.assertFalse(self.app.animating)
        self.assertEqual(len(self.app.events), 1)

    def test_disable_motion_mid_roll_commits_exactly_once(self):
        self.app.roll_human()
        self.app.set_animations(False)
        self.assertFalse(self.app.animating)
        self.app.finish_roll()
        self.assertEqual(len(self.app.events), 1)

    def test_theme_switch_preserves_session_and_inflight_animation(self):
        self.app.roll_human()
        session = self.app.session
        self.app.set_theme("light")
        self.assertIs(self.app.session, session)
        self.assertTrue(self.app.animating)
        self.assertEqual(self.app.dice_canvas.cget("bg"), self.app.palette.panel)
        self.finish_animation()
        self.assertEqual(len(self.app.events), 1)
        self.app.set_theme("dark")

    def test_settings_pause_and_restore_running_match(self):
        self.app.roll_human()
        self.app.show_settings()
        self.assertTrue(self.app.paused)
        self.assertIsNone(self.app.pending)
        self.app.close_settings()
        self.assertFalse(self.app.paused)
        self.finish_animation()

    def test_settings_respect_already_paused_match(self):
        self.app.toggle_pause()
        self.app.show_settings()
        self.app.set_theme("light")
        self.app.close_settings()
        self.assertTrue(self.app.paused)

    def test_motion_change_while_paused_waits_for_resume(self):
        self.app.roll_human()
        self.app.show_settings()
        self.app.set_animations(False)
        self.assertEqual(len(self.app.events), 0)
        self.app.close_settings()
        self.assertEqual(len(self.app.events), 1)

    def test_restart_cancels_old_animation(self):
        self.app.roll_human()
        with patch("hog_desktop.messagebox.askyesno", return_value=True):
            self.app.restart_match()
        self.assertFalse(self.app.animating)
        self.assertFalse(self.app.paused)
        self.assertEqual(self.app.session.scores, (0, 0))
        self.assertEqual(self.app.events, [])

    def test_cancel_restart_resumes_previously_running_animation(self):
        self.app.roll_human()
        with patch("hog_desktop.messagebox.askyesno", return_value=False):
            self.app.restart_match()
        self.assertTrue(self.app.animating)
        self.assertFalse(self.app.paused)
        self.finish_animation()

    def test_keyboard_chooses_ten_and_respects_entry_editing(self):
        event = SimpleNamespace(keysym="x", widget=self.root, state=0)
        self.app._keyboard(event)
        self.assertEqual(self.app.selected_count, 10)
        self.app.show_setup(1)
        entry = hog_desktop.tk.Entry(self.root)
        event = SimpleNamespace(keysym="t", widget=entry, state=0)
        self.app._keyboard(event)
        self.assertEqual(self.app.preferences.theme, "dark")
        entry.destroy()

    def test_settings_write_error_is_nonfatal(self):
        self.app.preferences_path = "/not-writable/settings.json"
        with patch("hog_desktop.save_preferences", side_effect=OSError("denied")):
            self.app.toggle_theme()
        self.assertEqual(self.app.preferences.theme, "light")
        self.assertTrue(self.app.settings_save_error)

    def test_animation_enabled_and_disabled_matches_are_identical(self):
        config = replace(self.config, num_players=0)
        outcomes = []
        for enabled in (True, False):
            self.app.set_animations(enabled)
            self.app.start_match(config)
            while not self.app.session.finished:
                self.app.cancel_pending()
                self.app.computer_turn()
                self.finish_animation()
            self.app.cancel_pending()
            outcomes.append(tuple(self.app.events))
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(self.app.session.scores, play(STRATEGIES["adaptive"][0],
                         STRATEGIES["sus"][0], sus_update, dice=seeded_dice(42)))


if __name__ == "__main__":
    unittest.main()
