"""Campaign goals, persistent rewards, migration, isolated matches and cosmetic UI."""

from dataclasses import asdict, replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from hog import GameSession, STRATEGIES, seeded_dice
from hog_campaign import (stages, stage_by_id, evaluate_stage, available_stages,
                          earned_cosmetics, campaign_achievements)
from hog_match import MatchConfig
from hog_storage import Store
from hog_desktop import HogApp, tk
from hog_preferences import Preferences

CERTIFICATES = json.loads((Path(__file__).parent / 'fixtures/campaign_three_stars.json').read_text())


def stage_run(stage, choices=None, count=5):
    choices = iter(choices) if choices is not None else None
    session = GameSession(dice=seeded_dice(stage.seed))
    events = []
    while not session.finished:
        if session.current_player == 1:
            choice = STRATEGIES[stage.strategy][0](session.scores[1], session.scores[0])
        else:
            choice = next(choices) if choices is not None else count
        events.append(session.advance(choice))
    record = {'config': {'names': ('Alice', stage.opponent)}, 'scores': session.scores,
              'events': [asdict(event) for event in events]}
    return session, events, record


class CampaignLogicTests(unittest.TestCase):
    def test_six_stages_have_legal_opponents_and_distinct_seeds(self):
        self.assertEqual(len(stages()), 6)
        self.assertEqual(len({stage.seed for stage in stages()}), 6)
        for stage in stages():
            self.assertIn(stage.strategy, STRATEGIES)
            self.assertEqual(len(stage.objectives), 3)
        with self.assertRaises(ValueError): stage_by_id('unknown')

    def test_each_stage_has_a_real_three_star_completion(self):
        for stage in stages():
            _, _, record = stage_run(stage, CERTIFICATES[stage.identifier])
            result = evaluate_stage(stage, record)
            self.assertTrue(result['cleared'])
            self.assertEqual(result['stars'], 3, stage.title)

    def test_first_stage_can_clear_after_loss(self):
        session, _, record = stage_run(stages()[0], count=1)
        self.assertEqual(session.winner, 1)
        self.assertTrue(evaluate_stage(stages()[0], record)['cleared'])

    def test_optional_objectives_do_not_clear_a_lost_later_stage(self):
        session, _, record = stage_run(stages()[1], count=0)
        self.assertEqual(session.winner, 1)
        result = evaluate_stage(stages()[1], record)
        self.assertFalse(result['cleared'])
        self.assertEqual(result['stars'], 0)
        self.assertTrue(result['objectives'][1][1])

    def test_only_the_next_stage_unlocks_after_clear(self):
        self.assertEqual(available_stages({}), ('first-steps',))
        unlocked = available_stages({'first-steps': {'cleared': True, 'stars': 1}})
        self.assertEqual(unlocked, ('first-steps', 'free-points'))

    def test_rewards_and_milestone_targets_follow_best_stars(self):
        empty = earned_cosmetics({})
        self.assertEqual(len(empty), 5)
        progress = {stage.identifier: {'cleared': True, 'stars': 3} for stage in stages()}
        self.assertEqual(len(earned_cosmetics(progress)), 12)
        self.assertTrue(all(value == target for _, value, target in campaign_achievements(progress)))


class CampaignStorageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'hog.sqlite3'
        self.store = Store(self.path)
        self.profile = self.store.create_profile('Alice')

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def clear_stage(self, stage, identifier=None):
        _, events, _ = stage_run(stage, CERTIFICATES[stage.identifier])
        run_id = uuid4().hex
        self.assertTrue(self.store.record_campaign(run_id, identifier or self.profile, stage.identifier, events))
        return run_id, events

    def test_campaign_completion_persists_across_reopen(self):
        self.clear_stage(stages()[0])
        other = Store(self.path)
        try:
            self.assertEqual(other.campaign_progress(self.profile)['first-steps']['stars'], 3)
        finally: other.close()

    def test_duplicate_run_does_not_add_attempts_or_stars(self):
        run_id, events = self.clear_stage(stages()[0])
        self.assertFalse(self.store.record_campaign(run_id, self.profile, stages()[0].identifier, events))
        self.assertEqual(self.store.campaign_progress(self.profile)['first-steps']['attempts'], 1)

    def test_replaying_a_weaker_attempt_never_lowers_best_stars(self):
        self.clear_stage(stages()[0])
        _, events, _ = stage_run(stages()[0], count=1)
        self.store.record_campaign(uuid4().hex, self.profile, 'first-steps', events)
        data = self.store.campaign_progress(self.profile)['first-steps']
        self.assertEqual((data['stars'], data['attempts']), (3, 2))

    def test_campaign_does_not_change_standard_stats_or_save(self):
        config = MatchConfig(profile_ids=(self.profile, None))
        self.store.save(config, GameSession(dice=seeded_dice(9)), [], uuid4().hex)
        before = self.store.connection.execute('SELECT payload FROM saves').fetchone()[0]
        self.clear_stage(stages()[0])
        self.assertEqual(self.store.stats()[0]['played'], 0)
        self.assertEqual(self.store.history(), [])
        self.assertEqual(self.store.tournaments(), [])
        self.assertEqual(self.store.connection.execute('SELECT payload FROM saves').fetchone()[0], before)

    def test_locked_stage_rejected_without_recording(self):
        _, events, _ = stage_run(stages()[1], CERTIFICATES['free-points'])
        with self.assertRaises(ValueError):
            self.store.record_campaign(uuid4().hex, self.profile, 'free-points', events)
        self.assertEqual(self.store.campaign_runs(self.profile), [])

    def test_wrong_seed_and_opponent_moves_rejected(self):
        _, events, _ = stage_run(stages()[0], CERTIFICATES['first-steps'])
        tampered = [replace(events[0], score_after=events[0].score_after + 1), *events[1:]]
        with self.assertRaises(ValueError):
            self.store.record_campaign(uuid4().hex, self.profile, 'first-steps', tampered)
        changed = list(events)
        changed[1] = replace(changed[1], num_rolls=0)
        with self.assertRaises(ValueError):
            self.store.record_campaign(uuid4().hex, self.profile, 'first-steps', changed)

    def test_incomplete_attempt_not_recorded(self):
        with self.assertRaises(ValueError):
            self.store.record_campaign(uuid4().hex, self.profile, 'first-steps', [GameSession(dice=seeded_dice(3401)).advance(4)])
        self.assertEqual(self.store.campaign_runs(self.profile), [])

    def test_locked_cosmetic_rejected_then_earned_equipment_persists(self):
        with self.assertRaises(ValueError): self.store.equip_cosmetic(self.profile, 'dice', 'cobalt')
        self.clear_stage(stages()[0])
        self.store.equip_cosmetic(self.profile, 'dice', 'cobalt')
        self.store.equip_cosmetic(self.profile, 'theme', 'aurora')
        other = Store(self.path)
        try:
            self.assertEqual(other.equipment(self.profile)['dice'], 'cobalt')
            self.assertEqual(other.equipment(self.profile)['theme'], 'aurora')
        finally: other.close()

    def test_profiles_do_not_share_progress_or_equipment(self):
        other = self.store.create_profile('Bob')
        self.clear_stage(stages()[0])
        self.store.equip_cosmetic(self.profile, 'dice', 'cobalt')
        self.assertEqual(self.store.campaign_progress(other), {})
        self.assertEqual(self.store.equipment(other)['dice'], 'classic')
        with self.assertRaises(ValueError): self.store.equip_cosmetic(other, 'dice', 'cobalt')

    def test_unknown_profiles_and_cosmetics_rejected(self):
        with self.assertRaises(ValueError): self.store.campaign_progress('missing')
        with self.assertRaises(ValueError): self.store.equip_cosmetic(self.profile, 'dice', 'unknown')
        with self.assertRaises(ValueError): self.store.equip_cosmetic(self.profile, 'unknown', 'classic')

    def test_unknown_stored_cosmetic_falls_back_to_default(self):
        self.store.connection.execute("INSERT INTO profile_cosmetics VALUES(?,?,?,?)", (self.profile, 'future-skin', 'initials', 'dark'))
        self.assertEqual(self.store.equipment(self.profile)['dice'], 'classic')

    def make_v1(self):
        normal = GameSession(dice=seeded_dice(42))
        turns = []
        while not normal.finished:
            turns.append(normal.advance(5))
        self.store.record_match(uuid4().hex, MatchConfig(2, ('Alice', 'Bob'), profile_ids=(self.profile, None)), normal, turns)
        self.store.save(MatchConfig(profile_ids=(self.profile, None)), GameSession(dice=seeded_dice(77)), [], uuid4().hex)
        self.store.save_tournament({'example': 'preserved'})
        with self.store.connection:
            self.store.connection.execute('DROP TABLE campaign_runs')
            self.store.connection.execute('DROP TABLE profile_cosmetics')
            self.store.connection.execute('PRAGMA user_version=1')
        self.store.close()

    def test_v1_migration_creates_backup_and_preserves_old_data(self):
        self.make_v1()
        self.store = Store(self.path)
        self.assertEqual(self.store.connection.execute('PRAGMA user_version').fetchone()[0], 2)
        self.assertEqual(self.store.profiles()[0]['id'], self.profile)
        self.assertEqual(len(self.store.tournaments()), 1)
        self.assertEqual(len(self.store.history()), 1)
        self.assertEqual(self.store.stats()[0]['played'], 1)
        self.assertEqual(self.store.load()[1].scores, (0, 0))
        backup = sqlite3.connect(str(self.path) + '.v1-backup')
        try:
            self.assertEqual(backup.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertEqual(backup.execute('SELECT COUNT(*) FROM profiles').fetchone()[0], 1)
            self.assertEqual(backup.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='campaign_runs'").fetchone()[0], 0)
        finally: backup.close()

    def test_failed_backup_does_not_migrate_original_database(self):
        self.make_v1()
        with patch('pathlib.Path.replace', side_effect=OSError('read only')):
            with self.assertRaises(OSError): Store(self.path)
        connection = sqlite3.connect(self.path)
        try: self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 1)
        finally: connection.close()
        self.assertFalse(Path(str(self.path) + '.v1-backup').exists())
        self.assertEqual(len(list(Path(self.folder.name).iterdir())), 1)
        self.store = Store(self.path)

    def test_future_database_version_rejected(self):
        self.store.connection.execute('PRAGMA user_version=3')
        with self.assertRaises(sqlite3.DatabaseError): Store(self.path)
        self.assertEqual(self.store.connection.execute('PRAGMA user_version').fetchone()[0], 3)


class CampaignDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if tk is None: raise unittest.SkipTest('Tk not installed')
        try:
            root = tk.Tk();root.destroy()
        except tk.TclError: raise unittest.SkipTest('A display is required')

    def setUp(self):
        self.root = tk.Tk()
        self.errors = []
        self.root.report_callback_exception = lambda kind, error, trace: self.errors.append(error)
        self.app = HogApp(self.root, cpu_delay=600000, preferences=Preferences(animations=False))
        self.identifier = self.app.store.create_profile('Alice')
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [])

    def cancel_cpu(self):
        if self.app.analysis_pending is not None:
            self.root.after_cancel(self.app.analysis_pending)
            self.app.analysis_pending = None

    def finish_stage(self):
        choices = iter(CERTIFICATES[self.app.campaign_stage.identifier])
        while not self.app.campaign_session.finished:
            self.cancel_cpu()
            if self.app.campaign_session.current_player == 1:
                self.app.campaign_cpu()
            else:
                self.app.campaign_count_buttons[next(choices)].invoke()
                self.app.campaign_roll_button.invoke()
        self.cancel_cpu()

    def test_map_starts_with_only_first_stage_available(self):
        self.app.show_campaign(self.identifier)
        self.root.update()
        self.assertTrue(self.app.campaign_map.find_all())
        self.app.campaign_select_stage('summit')
        self.assertEqual(str(self.app.campaign_start_button.cget('state')), 'disabled')
        self.app.campaign_select_stage('first-steps')
        self.assertEqual(str(self.app.campaign_start_button.cget('state')), 'normal')

    def test_completion_records_once_and_unlocks_next_stage(self):
        self.app.start_campaign_stage(self.identifier, 'first-steps')
        self.finish_stage()
        self.assertEqual(self.app.campaign_result['stars'], 3)
        self.assertEqual(self.app.store.campaign_progress(self.identifier)['first-steps']['attempts'], 1)
        self.app.campaign_draw()
        self.assertEqual(self.app.store.campaign_progress(self.identifier)['first-steps']['attempts'], 1)
        self.app.campaign_back_button.invoke()
        self.root.update()
        self.assertIn('free-points', available_stages(self.app.campaign_progress_data))

    def test_pause_cancels_cpu_without_advancing_rng(self):
        self.app.start_campaign_stage(self.identifier, 'first-steps')
        self.app.campaign_roll_button.invoke()
        rng = self.app.campaign_session.dice.rng.getstate()
        self.app.campaign_pause_button.invoke()
        self.assertIsNone(self.app.analysis_pending)
        self.app.campaign_cpu()
        self.assertEqual(self.app.campaign_session.dice.rng.getstate(), rng)
        self.app.campaign_pause_button.invoke()
        self.assertIsNotNone(self.app.analysis_pending)

    def test_wardrobe_locks_and_equips_only_earned_items(self):
        self.app.show_campaign(self.identifier)
        self.root.update()
        controls = self.app.wardrobe_controls['dice']
        controls['var'].set(next(label for label, item in controls['lookup'].items() if item.identifier == 'cobalt'))
        self.app.wardrobe_update()
        self.assertEqual(str(controls['button'].cget('state')), 'disabled')
        self.app.start_campaign_stage(self.identifier, 'first-steps')
        self.finish_stage()
        self.app.show_campaign(self.identifier)
        self.root.update()
        controls = self.app.wardrobe_controls['dice']
        controls['var'].set(next(label for label, item in controls['lookup'].items() if item.identifier == 'cobalt'))
        self.app.wardrobe_update()
        controls['button'].invoke()
        self.assertEqual(self.app.store.equipment(self.identifier)['dice'], 'cobalt')

    def test_cosmetics_and_theme_do_not_change_live_standard_rng(self):
        _, events, _ = stage_run(stages()[0], CERTIFICATES['first-steps'])
        self.app.store.record_campaign(uuid4().hex, self.identifier, 'first-steps', events)
        self.app.start_match(MatchConfig(2, ('Alice', 'Bob'), seed=42, profile_ids=(self.identifier, None)))
        rng = self.app.session.dice.rng.getstate()
        self.app.show_campaign(self.identifier)
        self.root.update()
        controls = self.app.wardrobe_controls['theme']
        controls['var'].set(next(label for label, item in controls['lookup'].items() if item.identifier == 'aurora'))
        self.app.wardrobe_update();controls['button'].invoke()
        self.assertEqual(self.app.preferences.theme, 'aurora')
        self.assertEqual(self.app.session.dice.rng.getstate(), rng)
        self.assertEqual(self.app.events, [])

    def test_abandon_confirmation_and_timer_cleanup(self):
        self.app.start_campaign_stage(self.identifier, 'first-steps')
        self.app.campaign_roll_button.invoke()
        with patch('hog_campaign_ui.messagebox.askyesno', return_value=False):
            self.app.campaign_back_button.invoke()
        self.assertFalse(self.app.campaign_paused)
        self.assertIsNotNone(self.app.analysis_pending)
        with patch('hog_campaign_ui.messagebox.askyesno', return_value=True):
            self.app.campaign_back_button.invoke()
        self.assertIsNone(self.app.analysis_pending)
        self.assertEqual(self.app.store.campaign_runs(self.identifier), [])

    def test_campaign_does_not_touch_standard_history_or_manual_save(self):
        self.app.start_match(MatchConfig(2, ('Alice', 'Bob'), seed=42))
        self.app.save_current()
        before = self.app.store.connection.execute('SELECT payload FROM saves').fetchone()[0]
        self.app.start_campaign_stage(self.identifier, 'first-steps')
        self.finish_stage()
        self.assertEqual(self.app.store.history(), [])
        self.assertEqual(self.app.store.connection.execute('SELECT payload FROM saves').fetchone()[0], before)

    def test_campaign_controls_fit_minimum_popup(self):
        self.app.start_campaign_stage(self.identifier, 'first-steps')
        self.app.analysis_window.geometry('900x720')
        self.root.update()
        window = self.app.analysis_window
        for widget in (*self.app.campaign_count_buttons, self.app.campaign_roll_button, self.app.campaign_back_button):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(), window.winfo_rooty()+720)

    def test_campaign_remembers_profile_selection_within_session(self):
        other = self.app.store.create_profile('Bob')
        self.app.show_campaign(other)
        self.app.close_analysis()
        self.app.show_campaign()
        self.assertEqual(self.app.campaign_profile_var.get(), 'Bob')

    def test_empty_campaign_can_create_first_profile(self):
        self.app.store.connection.execute('DELETE FROM profiles')
        self.app.show_campaign()
        self.root.update()
        self.assertIn('Create a local profile', self.app.campaign_hub_status.cget('text'))
