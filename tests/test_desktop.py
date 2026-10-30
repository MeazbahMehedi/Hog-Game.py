"""Real Tk integration checks. Skipped if Tk or a display is unavailable."""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import hog_desktop
from hog import seeded_dice, STRATEGIES, play, sus_update
from hog_match import MatchConfig


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if hog_desktop.tk is None:
            raise unittest.SkipTest("Tkinter is not installed")
        try:
            probe = hog_desktop.tk.Tk()
            probe.destroy()
        except hog_desktop.tk.TclError:
            raise unittest.SkipTest("No graphical display; run under xvfb-run to include desktop checks")

    def setUp(self):
        self.root = hog_desktop.tk.Tk()
        self.errors = []
        self.root.report_callback_exception = lambda kind, error, trace: self.errors.append(error)
        self.app = hog_desktop.HogApp(self.root, cpu_delay=600000)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [], "Tk callback raised an exception")

    def start(self, mode=1, seed=42):
        config = MatchConfig(mode, ("Alice", "Bob"), ("adaptive", "sus"), seed)
        self.app.start_match(config)
        self.root.update()
        return config

    def test_home_setup_and_mode_switches(self):
        self.assertEqual(self.app.screen, "home")
        self.app.show_setup(1)
        self.assertEqual(str(self.app.strategy_boxes[0].cget("state")), "disabled")
        self.assertEqual(str(self.app.strategy_boxes[1].cget("state")), "readonly")
        self.app.mode_var.set(2)
        self.app._setup_mode_changed()
        self.assertEqual(str(self.app.strategy_boxes[1].cget("state")), "disabled")
        self.app.mode_var.set(0)
        self.app._setup_mode_changed()
        self.assertEqual(str(self.app.strategy_boxes[0].cget("state")), "readonly")

    def test_setup_validation_and_start(self):
        self.app.show_setup(1)
        self.app.name_vars[0].set("")
        self.app._begin_from_setup()
        self.assertEqual(self.app.screen, "setup")
        self.assertTrue(self.app.setup_error.cget("text"))
        self.app.name_vars[0].set("Alice")
        self.app.seed_var.set("not a number")
        self.app._begin_from_setup()
        self.assertEqual(self.app.screen, "setup")
        self.app.seed_var.set("42")
        self.app._begin_from_setup()
        self.assertEqual(self.app.screen, "game")
        self.assertEqual(self.app.config.seed, 42)

    def test_human_controls_then_computer_controls(self):
        self.start()
        self.app.count_buttons[0].invoke()
        self.app.action_button.invoke()
        self.assertEqual(len(self.app.events), 1)
        self.assertEqual(self.app.events[0].num_rolls, 0)
        self.assertEqual(self.app.session.current_player, 1)
        self.assertEqual(str(self.app.action_button.cget("state")), "disabled")
        self.assertIsNotNone(self.app.pending)
        self.app.roll_human()
        self.assertEqual(len(self.app.events), 1)
        self.app.cancel_pending()
        self.app.computer_turn()
        self.assertEqual(len(self.app.events), 2)
        self.assertEqual(str(self.app.action_button.cget("state")), "normal")

    def test_two_humans_share_controls_without_cpu_timer(self):
        self.start(mode=2)
        for _ in range(2):
            self.app.select_count(0)
            self.app.roll_human()
            self.assertIsNone(self.app.pending)
        self.assertEqual([event.player for event in self.app.events], [0, 1])

    def test_watch_match_matches_engine_and_winner_screen(self):
        config = self.start(mode=0)
        while not self.app.session.finished:
            self.app.cancel_pending()
            self.app.computer_turn()
        self.app.cancel_pending()
        expected = play(STRATEGIES["adaptive"][0], STRATEGIES["sus"][0],
                        sus_update, dice=seeded_dice(42))
        self.assertEqual(self.app.session.scores, expected)
        self.app.show_winner()
        self.assertEqual(self.app.screen, "winner")
        self.app.build_game()
        self.assertEqual(self.app.action_button.cget("text"), "Match summary")
        self.assertIsNone(self.app.pending)
        self.app.start_match(config)
        self.assertEqual(self.app.session.scores, (0, 0))
        self.assertEqual(self.app.events, [])

    def test_computer_timer_advances_using_tk_event_loop(self):
        self.app.cpu_delay = 1
        self.start(mode=0)
        self.root.after(30, self.root.quit)
        self.root.mainloop()
        self.assertGreater(len(self.app.events), 0)

    def test_home_confirmation_cancels_timer(self):
        self.start(mode=0)
        with patch("hog_desktop.messagebox.askyesno", return_value=False):
            self.app.navigate_home()
        self.assertEqual(self.app.screen, "game")
        with patch("hog_desktop.messagebox.askyesno", return_value=True):
            self.app.navigate_home()
        self.assertEqual(self.app.screen, "home")
        self.assertIsNone(self.app.pending)

    def test_rules_window_is_reused_and_can_close(self):
        self.app.show_rules()
        first = self.app.rules_window
        self.app.show_rules()
        self.assertIs(first, self.app.rules_window)
        self.root.update()
        first.destroy()
        self.app.show_rules()
        self.assertIsNot(first, self.app.rules_window)

    def test_controls_fit_minimum_window_size(self):
        self.start(mode=2)
        self.root.geometry("1040x720")
        self.root.update()
        button = self.app.action_button
        self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                             self.root.winfo_rooty() + self.root.winfo_height())
        self.assertTrue(all(button.winfo_width() >= 25 for button in self.app.count_buttons))


class DesktopLauncherTests(unittest.TestCase):
    def test_version_flag_does_not_need_display(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "hog_desktop.py", "--version"],
                                cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "1.2.0")


if __name__ == "__main__":
    unittest.main()
