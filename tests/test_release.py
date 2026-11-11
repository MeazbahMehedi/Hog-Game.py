"""v4 data safety, identity retention, remapped inputs and real Tk workflows."""

from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from hog import GameSession, seeded_dice
from hog_backup import export_backup, prepare_backup, restore_backup, MAX_BYTES
from hog_controls import DEFAULT_KEYS, validate_shortcuts
from hog_desktop import HogApp, tk
from hog_match import MatchConfig
from hog_preferences import Preferences, load_preferences, save_preferences
from hog_storage import Store
from hog_tournament import run_tournament
from test_campaign import stage_run, CERTIFICATES
from hog_campaign import stages


class ReleaseStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.folder = Path(self.directory.name)
        self.store = Store(self.folder / 'hog.sqlite3')
        self.profile = self.store.create_profile('Alice')
        self.preferences = Preferences(theme='light', welcome_seen=True)
        self.path = self.folder / 'progress.hogbackup'

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def populate(self):
        config = MatchConfig(2, ('Alice', 'Bob'), seed=42, profile_ids=(self.profile, None))
        session = GameSession(dice=seeded_dice(42))
        events = []
        while not session.finished: events.append(session.advance(5))
        self.store.record_match(uuid4().hex, config, session, events)
        self.store.save(config, GameSession(dice=seeded_dice(42)), [], uuid4().hex)
        for stage in stages()[:2]:
            _, events, _ = stage_run(stage, CERTIFICATES[stage.identifier])
            self.store.record_campaign(uuid4().hex, self.profile, stage.identifier, events)
        self.store.equip_cosmetic(self.profile, 'dice', 'cobalt')
        self.store.save_tournament(run_tournament(('always5', 'sus'), 1, 42))
        self.store.archive_profile(self.profile)

    def tamper(self, mutate):
        data = json.loads(self.path.read_text())
        mutate(data['body'])
        canonical = json.dumps(data['body'], ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        data['sha256'] = hashlib.sha256(canonical).hexdigest()
        self.path.write_text(json.dumps(data))

    def test_rename_keeps_statistics_campaign_and_historical_names(self):
        self.populate()
        self.store.rename_profile(self.profile, 'New Alice')
        self.assertEqual(self.store.stats()[0]['name'], 'New Alice')
        self.assertEqual(self.store.stats()[0]['played'], 1)
        self.assertEqual(self.store.campaign_progress(self.profile)['first-steps']['stars'], 3)
        self.assertEqual(json.loads(self.store.history()[0]['payload'])['config']['names'][0], 'Alice')

    def test_archive_restore_preserves_identity_and_save(self):
        self.populate()
        self.assertEqual(self.store.profiles(), [])
        self.assertEqual(self.store.profiles(True)[0]['id'], self.profile)
        self.assertEqual(self.store.load()[0].profile_ids[0], self.profile)
        self.store.archive_profile(self.profile, False)
        self.assertEqual(self.store.profiles()[0]['id'], self.profile)

    def test_rename_rejects_duplicates_and_reserved_names(self):
        self.store.create_profile('Bob')
        for name in ('bOB', '', 'Guest / no profile', 'x'*21, 'a\nb'):
            with self.assertRaises(ValueError): self.store.rename_profile(self.profile, name)
        self.assertEqual(self.store.profiles()[0]['name'], 'Alice')

    def test_schema_two_migration_backup_is_preserved(self):
        self.store.connection.execute('DROP TABLE profile_archive')
        self.store.connection.execute('PRAGMA user_version=2')
        self.store.close()
        self.store = Store(self.folder / 'hog.sqlite3')
        self.assertEqual(self.store.connection.execute('PRAGMA user_version').fetchone()[0], 3)
        backup = sqlite3.connect(self.folder / 'hog.sqlite3.v2-backup')
        try:
            self.assertEqual(backup.execute('PRAGMA user_version').fetchone()[0], 2)
            self.assertEqual(backup.execute('SELECT name FROM profiles').fetchone()[0], 'Alice')
        finally: backup.close()

    def test_full_backup_round_trip_and_exact_rng(self):
        self.populate()
        export_backup(self.path, self.store, self.preferences)
        prepared = prepare_backup(self.path)
        try:
            self.assertEqual(prepared.counts['matches'], 1)
            self.assertEqual(prepared.counts['campaign_runs'], 2)
            self.assertEqual(prepared.preferences, self.preferences)
            self.assertEqual(prepared.store.profiles(True), self.store.profiles(True))
            self.assertEqual(prepared.store.equipment(self.profile), self.store.equipment(self.profile))
            self.assertEqual(prepared.store.tournaments(), self.store.tournaments())
            self.assertEqual(prepared.store.history(), self.store.history())
            self.assertEqual(prepared.store.load()[1].advance(6), self.store.load()[1].advance(6))
        finally: prepared.close()

    def test_restore_safety_copy_contains_old_data(self):
        export_backup(self.path, self.store, self.preferences)
        prepared = prepare_backup(self.path)
        extra = self.store.create_profile('Current Bob')
        safety = self.folder / 'safety.hogbackup'
        try:
            restored = restore_backup(prepared, self.store, safety, Preferences())
            self.assertEqual(restored.theme, 'light')
            self.assertEqual(len(self.store.profiles()), 1)
            old = prepare_backup(safety)
            try: self.assertIn(extra, [row['id'] for row in old.store.profiles()])
            finally: old.close()
        finally: prepared.close()

    def test_safety_copy_failure_does_not_change_live_database(self):
        export_backup(self.path, self.store, self.preferences)
        prepared = prepare_backup(self.path)
        self.store.create_profile('Bob')
        try:
            with patch('hog_backup._atomic_write', side_effect=OSError('no space')):
                with self.assertRaises(OSError):
                    restore_backup(prepared, self.store, self.folder/'safety', Preferences())
            self.assertEqual(len(self.store.profiles()), 2)
        finally: prepared.close()

    def test_export_failure_preserves_existing_file(self):
        export_backup(self.path, self.store, self.preferences)
        old = self.path.read_bytes()
        with patch('hog_backup.os.replace', side_effect=OSError('denied')):
            with self.assertRaises(OSError): export_backup(self.path, self.store, self.preferences)
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(len(list(self.folder.glob('tmp*'))), 0)

    def test_checksum_corruption_rejected(self):
        export_backup(self.path, self.store, self.preferences)
        data = json.loads(self.path.read_text()); data['body']['game_version'] = '99.0.0'
        self.path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'checksum'): prepare_backup(self.path)

    def test_modified_scoring_rejected_even_with_new_checksum(self):
        self.populate(); export_backup(self.path, self.store, self.preferences)
        def change(body):
            row = body['tables']['matches'][0]
            record = json.loads(row['payload']); record['events'][0]['score_after'] += 1
            row['payload'] = json.dumps(record)
        self.tamper(change)
        with self.assertRaises(ValueError): prepare_backup(self.path)
        self.assertEqual(len(self.store.history()), 1)

    def test_duplicate_ids_rejected(self):
        export_backup(self.path, self.store, self.preferences)
        self.tamper(lambda body: body['tables']['profiles'].append(body['tables']['profiles'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'): prepare_backup(self.path)

    def test_missing_profile_reference_rejected(self):
        self.populate(); export_backup(self.path, self.store, self.preferences)
        self.tamper(lambda body: body['tables']['profiles'].clear())
        with self.assertRaises(ValueError): prepare_backup(self.path)

    def test_unearned_cosmetic_rejected(self):
        self.populate(); export_backup(self.path, self.store, self.preferences)
        self.tamper(lambda body: body['tables']['profile_cosmetics'][0].update(avatar='crown'))
        with self.assertRaises(ValueError): prepare_backup(self.path)

    def test_campaign_reward_forgery_rejected(self):
        self.populate(); export_backup(self.path, self.store, self.preferences)
        self.tamper(lambda body: body['tables']['campaign_runs'][0].update(stars=0))
        with self.assertRaises(ValueError): prepare_backup(self.path)

    def test_tournament_standings_mismatch_rejected(self):
        self.populate(); export_backup(self.path, self.store, self.preferences)
        def change(body):
            row = body['tables']['tournaments'][0]
            result = json.loads(row['payload']); result['standings'][0]['wins'] += 1
            row['payload'] = json.dumps(result)
        self.tamper(change)
        with self.assertRaises(ValueError): prepare_backup(self.path)

    def test_oversized_and_non_json_files_rejected(self):
        self.path.write_bytes(b'PK not a backup')
        with self.assertRaises(ValueError): prepare_backup(self.path)
        with self.path.open('wb') as stream: stream.truncate(MAX_BYTES+1)
        with self.assertRaises(ValueError): prepare_backup(self.path)


class ControlTests(unittest.TestCase):
    def test_shortcut_validation_rejects_conflicts_and_binding_expressions(self):
        for values in ([*DEFAULT_KEYS[:-1], 'p'], [*DEFAULT_KEYS[:-1], '<Control-q>'],
                       [*DEFAULT_KEYS[:-1], '1'], [*DEFAULT_KEYS[:-1], True], []):
            with self.assertRaises(ValueError): validate_shortcuts(values)
        self.assertEqual(validate_shortcuts(list(DEFAULT_KEYS)), DEFAULT_KEYS)

    def test_new_preferences_and_legacy_preferences_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'settings.json'
            path.write_text('{"theme":"light","sound":false}')
            self.assertEqual(load_preferences(path).shortcuts, DEFAULT_KEYS)
            keys = ('z', *DEFAULT_KEYS[1:])
            preferences = Preferences(shortcuts=keys, welcome_seen=True)
            save_preferences(path, preferences)
            self.assertEqual(load_preferences(path), preferences)


class ReleaseDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if tk is None: raise unittest.SkipTest('Tk unavailable')
        try:
            root = tk.Tk(); root.destroy()
        except tk.TclError: raise unittest.SkipTest('No display')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.folder = Path(self.directory.name)
        self.root = tk.Tk()
        self.errors = []
        self.root.report_callback_exception = lambda kind, error, trace: self.errors.append(error)
        self.app = HogApp(self.root, preferences=Preferences(animations=False), cpu_delay=600000)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.directory.cleanup()
        self.assertEqual(self.errors, [])

    def wait_backup(self):
        deadline = time.monotonic() + 20
        while self.app.backup_future is not None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertIsNone(self.app.backup_future)

    def test_welcome_steps_finish_persist_and_reopen(self):
        self.app.preferences_path = self.folder/'settings.json'
        self.app.show_welcome()
        for _ in range(3): self.app.welcome_next_button.invoke()
        self.assertEqual(self.app.welcome_step, [3])
        self.app.welcome_next_button.invoke()
        self.assertIsNone(self.app.analysis_window)
        self.assertTrue(load_preferences(self.app.preferences_path).welcome_seen)
        self.app.show_welcome()
        self.assertEqual(self.app.welcome_step, [0])

    def test_remapped_key_plays_once_and_digits_still_select(self):
        self.app.preferences = replace(self.app.preferences, shortcuts=('z', *DEFAULT_KEYS[1:]))
        self.app.start_match(MatchConfig(2, seed=42))
        self.app._keyboard(SimpleNamespace(widget=self.root, state=0, keysym='0'))
        self.app._keyboard(SimpleNamespace(widget=self.root, state=0, keysym='Return'))
        self.assertEqual(len(self.app.events), 0)
        self.app._keyboard(SimpleNamespace(widget=self.root, state=0, keysym='z'))
        self.assertEqual(len(self.app.events), 1)
        self.assertEqual(self.app.events[0].num_rolls, 0)

    def test_focused_button_enter_activates_button_without_roll(self):
        self.app.start_match(MatchConfig(2, seed=42))
        button = self.app.count_buttons[3]
        button.focus_force(); self.root.update()
        button.event_generate('<Return>'); self.root.update()
        self.assertEqual(self.app.selected_count, 3)
        self.assertEqual(self.app.events, [])

    def test_entry_does_not_trigger_remapped_actions(self):
        self.app.show_setup(2)
        entry = tk.Entry(self.root)
        previous = self.app.preferences.theme
        self.app._keyboard(SimpleNamespace(widget=entry, state=0, keysym='t'))
        self.assertEqual(self.app.preferences.theme, previous)
        entry.destroy()

    def test_control_editor_rejects_conflict_then_applies(self):
        self.app.show_controls()
        self.app.control_vars[0].set('p'); self.app.controls_apply_button.invoke()
        self.assertIn('different', self.app.controls_status.cget('text'))
        self.app.control_vars[0].set('z'); self.app.controls_apply_button.invoke()
        self.assertEqual(self.app.preferences.shortcuts[0], 'z')

    def test_changed_shortcuts_update_live_button_hints(self):
        self.app.start_match(MatchConfig(2, seed=42))
        self.app.show_controls()
        self.app.control_vars[1].set('a'); self.app.control_vars[3].set('c')
        self.app.controls_apply_button.invoke()
        self.assertEqual(self.app.pause_button.cget('text'), 'Pause / A')
        self.assertEqual(self.app.advice_button.cget('text'), 'Coach / C')

    def test_archived_profile_remains_available_in_statistics(self):
        archived = self.app.store.create_profile('Alice')
        self.app.store.archive_profile(archived)
        self.app.store.create_profile('Bob')
        self.app.show_statistics(archived)
        self.assertEqual(self.app.statistics_profile.get(), 'Profile / Alice')

    def test_close_during_background_backup_validation_discards_result(self):
        from concurrent.futures import Future
        from unittest.mock import Mock
        pending = Future(); candidate = Mock()
        backup = self.folder/'portable.hogbackup'
        export_backup(backup, self.app.store, Preferences())
        self.app.show_data_center()
        with patch.object(self.app.worker, 'submit', return_value=pending):
            self.app.preview_portable_backup(backup)
        # Simulate a worker already running: closing must dispose its later result.
        pending.set_running_or_notify_cancel()
        self.app.close_analysis()
        pending.set_result(candidate)
        candidate.close.assert_called_once()
        self.assertIsNone(self.app.backup_future)

    def test_profile_manager_rename_archive_and_restore(self):
        identifier = self.app.store.create_profile('Alice')
        self.app.show_profile_manager()
        self.app.profile_rename_var.set('New Alice'); self.app.profile_rename_button.invoke()
        self.assertEqual(self.app.store.profiles()[0]['name'], 'New Alice')
        self.app.profile_archive_button.invoke()
        self.assertEqual(self.app.store.profiles(), [])
        self.app.profile_archive_button.invoke()
        self.assertEqual(self.app.store.profiles()[0]['id'], identifier)

    def test_backup_preview_then_confirmed_restore(self):
        self.app.preferences_path = self.folder/'settings.json'
        self.app.store.create_profile('Alice')
        backup = self.folder/'portable.hogbackup'
        export_backup(backup, self.app.store, Preferences(theme='light', welcome_seen=True))
        self.app.store.create_profile('Bob')
        self.app.show_data_center(); self.app.preview_portable_backup(backup); self.wait_backup()
        self.assertIn('1 profiles', self.app.backup_preview.cget('text'))
        with patch('hog_release_ui.messagebox.askyesno', return_value=True):
            self.app.apply_portable_backup()
        self.assertEqual(len(self.app.store.profiles()), 1)
        self.assertEqual(self.app.preferences.theme, 'light')
        self.assertEqual(len(list((self.folder/'backups').glob('*.hogbackup'))), 1)

    def test_restore_blocked_during_active_match(self):
        backup = self.folder/'portable.hogbackup'
        export_backup(backup, self.app.store, Preferences())
        self.app.start_match(MatchConfig(2, seed=42))
        self.app.show_data_center(); self.app.preview_portable_backup(backup); self.wait_backup()
        self.app.apply_portable_backup()
        self.assertIn('Finish or leave', self.app.backup_status.cget('text'))
        self.assertEqual(self.app.session.scores, (0, 0))

    def test_callback_recovery_pauses_and_writes_no_error_payload(self):
        self.app.preferences_path = self.folder/'settings.json'
        self.app.start_match(MatchConfig(0, seed=42))
        try: raise RuntimeError('private-token-example')
        except RuntimeError as error:
            with patch('hog_release_ui.messagebox.showerror'):
                self.app.handle_callback_error(type(error), error, error.__traceback__)
        self.assertTrue(self.app.paused)
        self.assertIsNone(self.app.pending)
        diagnostic = (self.folder/'last-error.log').read_text()
        self.assertIn('RuntimeError', diagnostic)
        self.assertNotIn('private-token-example', diagnostic)


if __name__ == '__main__': unittest.main()
