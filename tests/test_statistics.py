"""Validated aggregates, identity filters, factual milestones and replay UI."""

from copy import deepcopy
from dataclasses import asdict
import json
import unittest

from hog import GameSession, seeded_dice, STRATEGIES
from hog_charts import score_position
from hog_match import MatchConfig
from hog_statistics import read_matches, summarize, key_moments, explain_turn
from hog_desktop import HogApp, tk
from hog_preferences import Preferences


def completed(seed=42, config=None, identifier='match', count=5):
    config = config or MatchConfig(2, ('Alice', 'Bob'), seed=seed)
    session = GameSession(dice=seeded_dice(seed))
    events = []
    while not session.finished:
        events.append(session.advance(count))
    record = {'config': asdict(config), 'scores': session.scores, 'events': [asdict(event) for event in events]}
    return {'id': identifier, 'finished_at': '2026-10-29T04:00:00+00:00', 'payload': json.dumps(record)}, session, events


class StatisticsTests(unittest.TestCase):
    def test_all_seats_count_each_turn_once(self):
        row, session, events = completed()
        matches, skipped = read_matches([row])
        data = summarize(matches)
        self.assertEqual(skipped, 0)
        self.assertEqual((data['matches'], data['appearances'], data['wins'], data['losses']), (1, 2, 1, 1))
        self.assertEqual(data['win_rate'], .5)
        self.assertEqual(sum(data['dice_counts']), len(events))
        self.assertEqual(data['average_gain'], sum(session.scores) / len(events))
        self.assertIsNone(data['best_streak'])

    def test_profile_filter_uses_identity_not_display_name(self):
        identifier = 'a' * 32
        config = MatchConfig(1, ('Renamed Alice', 'CPU'), ('always5', 'hard'), 42, (identifier, None))
        row, session, events = completed(config=config)
        matches, _ = read_matches([row])
        data = summarize(matches, identifier)
        self.assertEqual(data['appearances'], 1)
        self.assertEqual(data['turns'], sum(event.player == 0 for event in events))
        self.assertEqual(data['opponents'][0]['key'], 'cpu:hard')
        self.assertEqual(data['best_score'], session.scores[0])
        self.assertEqual(summarize(matches, 'unrelated')['appearances'], 0)

    def test_zero_dice_counts_and_rules_are_observed(self):
        row, _, events = completed(count=0)
        data = summarize(read_matches([row])[0])
        self.assertEqual(data['zeros'], len(events))
        self.assertEqual(data['dice_counts'][0], len(events))
        self.assertEqual(data['sow'], 0)
        self.assertEqual(data['bonuses'], sum(event.bonus > 0 for event in events))

    def test_empty_selection_has_no_fake_rate(self):
        data = summarize(())
        self.assertIsNone(data['win_rate'])
        self.assertIsNone(data['average_gain'])
        self.assertEqual(data['dice_counts'], (0,) * 11)
        self.assertEqual(data['opponents'], ())

    def test_bad_records_are_excluded_and_duplicates_not_counted(self):
        row, _, _ = completed()
        bad = deepcopy(row)
        bad['id'] = 'corrupt'
        raw = json.loads(bad['payload']);raw['events'][0]['score_after'] += 1
        bad['payload'] = json.dumps(raw)
        matches, skipped = read_matches([row, row, bad, {'id': 'broken', 'payload': 'null'}])
        self.assertEqual((len(matches), skipped), (1, 2))

    def test_legacy_guest_record_without_profile_ids(self):
        row, _, _ = completed()
        raw = json.loads(row['payload']);del raw['config']['profile_ids']
        row['payload'] = json.dumps(raw)
        matches, _ = read_matches([row])
        self.assertEqual(summarize(matches)['appearances'], 2)
        self.assertEqual(summarize(matches, 'a' * 32)['appearances'], 0)

    def test_profile_opponents_keep_identity_across_display_changes(self):
        own, other = 'a' * 32, 'b' * 32
        rows = []
        for seed, name in ((42, 'Bob'), (43, 'New Bob')):
            config = MatchConfig(2, ('Alice', name), seed=seed, profile_ids=(own, other))
            rows.insert(0, completed(seed, config, str(seed))[0])
        data = summarize(read_matches(rows)[0], own)
        self.assertEqual(len(data['opponents']), 1)
        self.assertEqual(data['opponents'][0]['played'], 2)
        self.assertEqual(data['opponents'][0]['name'], 'Profile / New Bob')

    def test_personal_winning_streak_uses_chronological_results(self):
        own = 'a' * 32
        # Reassign the same profile to the winning seat, then a losing seat.
        rows = []
        for seed, want_win in ((42, True), (43, True), (44, False), (45, True)):
            row, session, _ = completed(seed=seed, identifier=str(seed))
            raw = json.loads(row['payload'])
            seat = session.winner if want_win else 1 - session.winner
            raw['config']['profile_ids'][seat] = own
            row['payload'] = json.dumps(raw)
            rows.insert(0, row)
        data = summarize(read_matches(rows)[0], own)
        self.assertEqual((data['wins'], data['best_streak']), (3, 2))

    def test_milestones_match_real_gains_and_winning_turn(self):
        row, _, events = completed()
        states = read_matches([row])[0][0].states
        moments = key_moments(states)
        largest = max(events, key=lambda event: event.score_after - event.score_before)
        self.assertIn('Largest score gain', dict(moments)[largest.number])
        self.assertIn('Winning turn', dict(moments)[len(events)])
        self.assertEqual(list(dict(moments)), sorted(dict(moments)))

    def test_scoring_explanations_do_not_mutate_record(self):
        row, _, _ = completed(count=0)
        before = deepcopy(row)
        match = read_matches([row])[0][0]
        self.assertIn('Before turn 1', explain_turn(match.states[0], match.config.names))
        self.assertIn('Boar Brawl', explain_turn(match.states[1], match.config.names))
        self.assertEqual(row, before)

    def test_chart_clicks_clamp_to_recorded_positions(self):
        class Canvas:
            def winfo_width(self): return 1000
        self.assertEqual(score_position(Canvas(), 20, -30), 0)
        self.assertEqual(score_position(Canvas(), 20, 2000), 20)
        self.assertEqual(score_position(Canvas(), 20, 513), 10)


class InsightsDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if tk is None: raise unittest.SkipTest('Tk not installed')
        try:
            root = tk.Tk();root.destroy()
        except tk.TclError:
            raise unittest.SkipTest('A display is required')

    def setUp(self):
        self.root = tk.Tk()
        self.errors = []
        self.root.report_callback_exception = lambda kind, error, trace: self.errors.append(error)
        self.app = HogApp(self.root, cpu_delay=600000, preferences=Preferences(animations=False))
        self.identifier = self.app.store.create_profile('Alice')
        config = MatchConfig(2, ('Alice', 'Bob'), seed=42, profile_ids=(self.identifier, None))
        _, session, events = completed(config=config)
        self.app.store.record_match('insights-test', config, session, events)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [])

    def test_statistics_profile_scope_and_all_seats(self):
        self.app.show_statistics(self.identifier)
        self.root.update()
        self.assertEqual(self.app.statistics_summary['appearances'], 1)
        self.assertTrue(self.app.statistics_chart.find_all())
        self.app.statistics_profile.set('All recorded seats')
        self.app.statistics_refresh()
        self.assertEqual(self.app.statistics_summary['appearances'], 2)
        self.assertIn('not a player skill estimate', self.app.statistics_status.cget('text'))
        self.assertEqual(len(self.app.statistics_opponents.get_children()), 2)

    def test_default_filter_prefers_active_profile_over_alphabetical_empty_profile(self):
        self.app.store.create_profile('Aardvark')
        self.app.show_statistics()
        self.root.update()
        self.assertEqual(self.app.statistics_profile.get(), 'Profile / Alice')
        self.assertEqual(self.app.statistics_summary['appearances'], 1)

    def test_timeline_scrub_and_key_turns_are_read_only(self):
        before = self.app.store.history()
        self.app.show_replay()
        self.root.update()
        self.app.replay_seek(5)
        self.root.update()
        self.assertEqual(self.app.replay_index, 5)
        self.assertEqual(int(self.app.replay_timeline_var.get()), 5)
        self.assertTrue(self.app.replay_chart.find_all())
        self.assertTrue(self.app.replay_moments)
        self.assertIn('Position 5', self.app.replay_step_label.cget('text'))
        self.assertEqual(self.app.store.history(), before)

    def test_real_playback_survives_timeline_updates_and_speed_change(self):
        self.app.show_replay()
        self.root.update()
        self.app.replay_speed.set('4×')
        self.app.replay_play_pause()
        self.root.after(730, self.root.quit)
        self.root.mainloop()
        self.assertGreaterEqual(self.app.replay_index, 3)
        self.assertTrue(self.app.replay_playing)
        self.app.replay_speed.set('2×')
        self.app.replay_change_speed()
        self.assertIsNotNone(self.app.analysis_pending)
        self.app.replay_seek(1)
        self.assertFalse(self.app.replay_playing)
        self.assertIsNone(self.app.analysis_pending)

    def test_replay_end_stops_timer_and_play_restarts(self):
        self.app.show_replay()
        self.root.update()
        total = len(self.app.replay_states) - 1
        self.app.replay_seek(total - 1)
        self.app.replay_play_pause()
        self.root.after(850, self.root.quit)
        self.root.mainloop()
        self.assertEqual(self.app.replay_index, total)
        self.assertFalse(self.app.replay_playing)
        self.assertIsNone(self.app.analysis_pending)
        self.app.replay_play_pause()
        self.assertEqual(self.app.replay_index, 0)
        self.assertTrue(self.app.replay_playing)

    def test_closing_or_switching_views_cancels_replay(self):
        self.app.show_replay()
        self.app.replay_play_pause()
        self.app.show_statistics()
        self.assertIsNone(self.app.analysis_pending)
        self.assertFalse(self.app.replay_playing)
        self.app.close_analysis()
        self.assertIsNone(self.app._redraw_insights)

    def test_themes_redraw_charts_without_changing_live_rng_or_storage(self):
        self.app.start_match(MatchConfig(2, ('Alice', 'Bob'), seed=91))
        rng = self.app.session.dice.rng.getstate()
        before = self.app.store.history()
        for view in (self.app.show_statistics, self.app.show_replay):
            view()
            for theme in ('light', 'contrast', 'dark'):
                self.app.set_theme(theme)
                self.root.update()
                if view == self.app.show_replay:
                    self.assertEqual(self.app.replay_timeline.cget('troughcolor'), self.app.palette.raised)
            self.app.close_analysis()
        self.assertEqual(self.app.session.dice.rng.getstate(), rng)
        self.assertEqual(self.app.events, [])
        self.assertEqual(self.app.store.history(), before)

    def test_empty_statistics_and_replay_windows(self):
        self.app.store.connection.execute('DELETE FROM players')
        self.app.store.connection.execute('DELETE FROM matches')
        self.app.show_statistics()
        self.root.update()
        self.assertEqual(self.app.statistics_summary['appearances'], 0)
        self.app.show_replay()
        self.root.update()
        self.assertEqual(self.app.replay_states, ())

    def test_corrupt_history_is_excluded_without_callback_errors(self):
        with self.app.store.connection:
            self.app.store.connection.execute("INSERT INTO matches VALUES('bad','later','null')")
        self.app.show_statistics()
        self.root.update()
        self.assertEqual(self.app.statistics_skipped, 1)
        self.assertIn('excluded', self.app.statistics_status.cget('text'))
        self.app.show_replay()
        self.root.update()
        self.assertTrue(self.app.replay_states)

    def test_replay_and_statistics_controls_fit_minimum_popup(self):
        for view in (self.app.show_replay, self.app.show_statistics):
            view()
            window = self.app.analysis_window
            window.geometry('900x720')
            self.root.update()
            widgets = self.app.replay_buttons.values() if view == self.app.show_replay else (self.app.statistics_rule_counts,)
            for widget in widgets:
                self.assertTrue(widget.winfo_ismapped())
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), window.winfo_rooty() + window.winfo_height())
