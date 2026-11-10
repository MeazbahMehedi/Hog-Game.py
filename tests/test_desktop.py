"""Real Tk integration checks. Skipped if Tk or a display is unavailable."""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import hog_desktop
from hog import seeded_dice, STRATEGIES, play, sus_update
from hog_match import MatchConfig
from hog_preferences import Preferences


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
        self.app = hog_desktop.HogApp(self.root, cpu_delay=600000,
                                      preferences=Preferences(animations=False))
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

    def test_advisor_renders_without_playing_a_turn(self):
        self.start(mode=1)
        before = self.app.session.scores
        self.app.show_advice()
        self.root.after(600, self.root.quit)
        self.root.mainloop()
        self.assertIn("Model win chance", self.app.analysis_status.cget("text"))
        self.assertEqual(self.app.session.scores, before)
        self.assertEqual(self.app.events, [])
        self.app.close_analysis()
        self.assertIsNone(self.app.analysis_pending)

    def test_comparison_renders_worker_results_and_closes_cleanly(self):
        self.app.show_comparison()
        rows = (("hard", 30, 25, .6875, .58, .78),)
        with patch("hog_desktop.compare_opponents", return_value=rows):
            self.app.comparison_run_button.invoke()
            self.root.after(300, self.root.quit)
            self.root.mainloop()
        self.assertIn("Baseline: adaptive", self.app.analysis_status.cget("text"))
        self.assertEqual(str(self.app.comparison_run_button.cget("state")), "normal")
        self.app.close_analysis()

    def test_profile_setup_assigns_human_identity(self):
        identifier = self.app.store.create_profile("Alice")
        self.app.show_setup(1)
        self.app.profile_vars[0].set("Alice")
        self.app._profile_selected(0)
        self.app._begin_from_setup()
        self.assertEqual(self.app.config.profile_ids, (identifier, None))
        self.assertEqual(self.app.config.names[0], "Alice")

    def test_save_resume_preserves_turns_and_starts_paused(self):
        self.start(mode=1)
        self.app.roll_human()
        before = tuple(self.app.events)
        scores = self.app.session.scores
        self.app.save_current()
        self.assertTrue(self.app.paused)
        self.app.resume_saved()
        self.assertEqual(self.app.session.scores, scores)
        self.assertEqual(tuple(self.app.events), before)
        self.assertTrue(self.app.paused)
        self.assertIsNone(self.app.pending)

    def test_player_hub_and_tournament_results_persist(self):
        from hog_tournament import run_tournament
        self.app.store.create_profile("Alice")
        self.app.show_player_hub()
        self.assertIn("Leaderboard", self.app.hub_tabs)
        self.app.show_tournament()
        result = run_tournament(("always5", "hard"), 1, 42)
        with patch("hog_desktop.run_tournament", return_value=result):
            self.app.tournament_run_button.invoke()
            self.root.after(300, self.root.quit)
            self.root.mainloop()
        self.assertEqual(len(self.app.store.tournaments()), 1)
        self.assertTrue(self.app.tournament_chart.find_all())
        self.app.show_tournament()
        self.assertEqual(self.app.tournament_result["matches"], result["matches"])


class DesktopLauncherTests(unittest.TestCase):
    def test_version_flag_does_not_need_display(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "hog_desktop.py", "--version"],
                                cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "2.2.0")


if __name__ == "__main__":
    unittest.main()
