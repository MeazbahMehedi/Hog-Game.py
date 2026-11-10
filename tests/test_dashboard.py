"""Dashboard integration, responsive layout, and cosmetic-state isolation."""

from dataclasses import asdict
import json
import unittest

from hog import GameSession, seeded_dice
from hog_dashboard import initials, recent_results, turn_breakdown
from hog_desktop import HogApp, tk
from hog_match import MatchConfig
from hog_preferences import Preferences


class PresentationTests(unittest.TestCase):
    def test_initials_support_names_and_guest_fallback(self):
        self.assertEqual(initials("Md Meazbah Mehedi Prodhan"), "MP")
        self.assertEqual(initials("Alice"), "A")
        self.assertEqual(initials(""), "?")
        self.assertEqual(initials("李 明"), "李明")

    def test_breakdown_separates_bonus_from_base_points(self):
        session = GameSession(score0=7, dice=lambda: 1)
        event = session.advance(1)
        self.assertEqual(turn_breakdown(event), ("SOW SAD", "+1", "SUS FUSS", "+3", "NEW SCORE", "11"))
        self.assertEqual(turn_breakdown(None)[1::2], ("—", "—", "—"))

    def test_zero_dice_breakdown_uses_boar_brawl(self):
        event = GameSession(dice=seeded_dice(42)).advance(0)
        self.assertEqual(turn_breakdown(event)[0], "BOAR BRAWL")

    def test_recent_summaries_skip_unreadable_data_and_preserve_input(self):
        rows = [{"payload": "broken"}, {"payload": json.dumps({"config": {"names": ["Alice", "Bob"]}, "scores": [101, 89]})}]
        before = json.dumps(rows)
        self.assertEqual(recent_results(rows), [("Alice vs Bob", "101 : 89")])
        self.assertEqual(json.dumps(rows), before)


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if tk is None:
            raise unittest.SkipTest("Tkinter is not installed")
        try:
            root = tk.Tk()
            root.destroy()
        except tk.TclError:
            raise unittest.SkipTest("A graphical display is required")

    def setUp(self):
        self.root = tk.Tk()
        self.errors = []
        self.root.report_callback_exception = lambda kind, error, trace: self.errors.append(error)
        self.app = HogApp(self.root, cpu_delay=600000, preferences=Preferences(animations=False))
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [])

    def start(self):
        self.app.start_match(MatchConfig(2, ("Alice", "Bob"), seed=42))
        self.root.update()

    def test_dashboard_uses_actual_local_totals(self):
        self.assertEqual(self.app.dashboard_counts, (0, 0, 0))
        identifier = self.app.store.create_profile("Alice")
        config = MatchConfig(2, ("Alice", "Bob"), seed=42, profile_ids=(identifier, None))
        session = GameSession(dice=seeded_dice(42))
        events = []
        while not session.finished:
            events.append(session.advance(0))
        self.app.store.record_match("test-dashboard", config, session, events)
        self.app.show_home()
        self.root.update()
        self.assertEqual(self.app.dashboard_counts, (1, 1, 0))
        self.assertEqual(len(self.app.store.history()), 1)

    def test_dashboard_reflows_without_losing_mode_actions(self):
        for width, compact in ((1280, False), (960, True), (1280, False)):
            self.root.geometry(f"{width}x720")
            self.root.update()
            self.assertEqual(self.app.dashboard_compact, compact)
            self.assertTrue(all(button.winfo_ismapped() for button in self.app.dashboard_mode_buttons))
            nav = self.app.dashboard_buttons[-1]
            self.assertLessEqual(nav.winfo_rootx() + nav.winfo_width(), self.root.winfo_rootx() + width)
        self.app.dashboard_mode_buttons[1].invoke()
        self.assertEqual(self.app.mode_var.get(), 2)

    def test_journal_resize_and_manual_choice_preserve_rng(self):
        self.start()
        before = self.app.session.dice.rng.getstate()
        for width, visible in ((1280, True), (960, False)):
            self.root.geometry(f"{width}x720")
            self.root.update()
            self.assertEqual(self.app.journal_visible, visible)
        self.app.journal_button.invoke()
        self.root.update()
        self.assertTrue(self.app.journal_visible)
        self.root.geometry("1280x800")
        self.root.update()
        self.assertTrue(self.app.journal_visible)
        self.assertEqual(self.app.session.dice.rng.getstate(), before)
        self.assertEqual(self.app.events, [])

    def test_journal_hides_but_keeps_recorded_turns(self):
        self.start()
        self.app.roll_human()
        before = self.app.journal.get("1.0", "end")
        self.app.toggle_journal()
        self.app.toggle_journal()
        self.assertEqual(self.app.journal.get("1.0", "end"), before)
        self.assertEqual(len(self.app.events), 1)

    def test_selector_previews_risk_and_zero_dice_without_playing(self):
        self.start()
        self.app.select_count(10)
        self.assertIn("84% Sow Sad risk", self.app.free_label.cget("text"))
        self.app.select_count(0)
        self.assertIn("guaranteed +1", self.app.free_label.cget("text"))
        self.assertEqual(self.app.events, [])

    def test_breakdown_matches_the_completed_turn(self):
        self.start()
        self.app.select_count(0)
        self.app.roll_human()
        self.assertEqual(tuple(label.cget("text") for label in self.app.breakdown_labels), turn_breakdown(self.app.events[-1]))
        self.assertIn("Boar Brawl", self.app.journal.get("1.0", "end"))

    def test_turn_pulse_never_changes_rng_and_stops_on_pause(self):
        self.start()
        self.app.set_animations(True)
        self.assertIsNotNone(self.app.ui_pending)
        before = self.app.session.dice.rng.getstate()
        self.app._cancel_ui()
        self.app._pulse_turn()
        self.assertEqual(self.app.session.dice.rng.getstate(), before)
        self.app.toggle_pause()
        self.assertIsNone(self.app.ui_pending)
        self.app.toggle_pause()
        self.assertIsNotNone(self.app.ui_pending)
        self.app.set_animations(False)
        self.assertIsNone(self.app.ui_pending)

    def test_leaving_match_cancels_cosmetic_timer(self):
        self.start()
        self.app.set_animations(True)
        self.app.show_setup(1)
        self.assertIsNone(self.app.ui_pending)

    def test_match_controls_fit_compact_window_in_every_theme(self):
        self.start()
        self.root.geometry("960x720")
        for theme in ("dark", "light", "contrast"):
            self.app.set_theme(theme)
            self.root.update()
            self.assertEqual(self.app.journal.tag_cget("turn", "foreground"), self.app.palette.accent)
            for button in (*self.app.count_buttons, self.app.action_button, self.app.journal_button):
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(button.winfo_rootx() + button.winfo_width(), self.root.winfo_rootx() + 960)
                self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), self.root.winfo_rooty() + 720)
            self.assertTrue(all(button.winfo_width() >= 25 for button in self.app.count_buttons))


if __name__ == "__main__":
    unittest.main()
