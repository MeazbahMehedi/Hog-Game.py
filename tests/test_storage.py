"""Temporary-database tests for profiles, exact resumption and tournaments."""

from copy import deepcopy
import csv
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from hog import GameSession, STRATEGIES, seeded_dice
from hog_match import MatchConfig
from hog_storage import Store, make_snapshot, restore_snapshot
from hog_tournament import run_tournament, export_tournament


def finish(session, events):
    while not session.finished:
        who = session.current_player
        count = STRATEGIES["adaptive"][0](session.scores[who], session.scores[1 - who])
        events.append(session.advance(count))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "data/hog.sqlite3"
        self.store = Store(self.path)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def test_profiles_survive_reopen_and_names_are_case_insensitive(self):
        identifier = self.store.create_profile("Alice")
        with self.assertRaises(ValueError):
            self.store.create_profile(" alice ")
        other = Store(self.path)
        self.assertEqual(other.profiles()[0]["id"], identifier)
        other.close()

    def test_bad_profile_names_rejected(self):
        for name in ("", "a" * 21, "A\nB", "\x1b[0m", "Guest / no profile"):
            with self.assertRaises(ValueError):
                self.store.create_profile(name)

    def test_exact_save_resume_even_without_seed(self):
        config = MatchConfig(seed=None)
        session = GameSession(dice=seeded_dice())
        events = [session.advance(5), session.advance(3)]
        identifier = uuid4().hex
        self.store.save(config, session, events, identifier)
        loaded_config, restored, history, restored_id = self.store.load()
        self.assertEqual((loaded_config, restored_id), (config, identifier))
        finish(session, events)
        finish(restored, history)
        self.assertEqual(events, history)
        self.assertEqual(session.scores, restored.scores)

    def test_invalid_saved_scoring_is_rejected(self):
        session = GameSession(dice=seeded_dice(42))
        events = [session.advance(3)]
        payload = make_snapshot(MatchConfig(seed=42), session, events, uuid4().hex)
        payload["events"][0]["score_after"] += 1
        with self.assertRaises(ValueError):
            restore_snapshot(payload)

    def test_rng_state_and_schema_validation(self):
        payload = make_snapshot(MatchConfig(), GameSession(dice=seeded_dice()), [], uuid4().hex)
        for change in ({"schema": 2}, {"rng_state": "pickle"}, {"rng_state": [3, [1], None]},
                       {"events": [{}]}, {"match_id": "bad"}):
            invalid = deepcopy(payload)
            invalid.update(change)
            with self.assertRaises(ValueError):
                restore_snapshot(invalid)

    def test_recording_is_idempotent_and_clears_its_save(self):
        identifier = self.store.create_profile("Alice")
        config = MatchConfig(num_players=1, profile_ids=(identifier, None))
        session = GameSession(dice=seeded_dice(42))
        events = []
        match_id = uuid4().hex
        self.store.save(config, session, events, match_id)
        finish(session, events)
        self.assertTrue(self.store.record_match(match_id, config, session, events))
        self.assertFalse(self.store.record_match(match_id, config, session, events))
        self.assertEqual(self.store.stats()[0]["played"], 1)
        self.assertEqual(len(self.store.history()), 1)
        with self.assertRaises(ValueError):
            self.store.load()

    def test_guest_history_does_not_create_profile_statistics(self):
        session = GameSession(dice=seeded_dice(5))
        events = []
        finish(session, events)
        self.store.record_match(uuid4().hex, MatchConfig(), session, events)
        self.assertEqual(self.store.stats(), [])
        self.assertEqual(len(self.store.history()), 1)

    def test_achievements_derive_from_recorded_turns(self):
        identifier = self.store.create_profile("Alice")
        config = MatchConfig(2, ("Alice", "Bob"), profile_ids=(identifier, None))
        session = GameSession(dice=seeded_dice(42))
        events = []
        while not session.finished:
            events.append(session.advance(0))
        self.store.record_match(uuid4().hex, config, session, events)
        unlocked = dict(self.store.achievements(identifier))
        self.assertTrue(unlocked["First finish"])
        self.assertTrue(unlocked["Free points"])
        self.assertFalse(unlocked["Ten matches"])

    def test_csv_exports_both_seats_and_escapes_formula_names(self):
        session = GameSession(dice=seeded_dice(42))
        events = []
        finish(session, events)
        self.store.record_match(uuid4().hex, MatchConfig(names=("=1+1", "Bob")), session, events)
        path = Path(self.folder.name) / "history.csv"
        self.store.export_history(path)
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "'=1+1")

    def test_computer_seats_cannot_hold_profile_ids(self):
        with self.assertRaises(ValueError):
            MatchConfig(0, profile_ids=(uuid4().hex, None))


class TournamentTests(unittest.TestCase):
    def test_round_robin_has_equal_seats_and_consistent_totals(self):
        result = run_tournament(("always5", "adaptive", "hard"), 2, 42)
        self.assertEqual(len(result["matches"]), 12)
        self.assertEqual(sum(row["wins"] for row in result["standings"]), 12)
        for row in result["standings"]:
            self.assertEqual(row["played"], 8)
            self.assertEqual(sum(match["first"] == row["strategy"] for match in result["matches"]), 4)
        self.assertEqual(result, run_tournament(("always5", "adaptive", "hard"), 2, 42))

    def test_tournament_persistence_and_csv(self):
        result = run_tournament(("always5", "hard"), 1, 1)
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "hog.sqlite3")
            store.save_tournament(result)
            loaded = json.loads(store.tournaments()[0]["payload"])
            self.assertEqual(loaded["matches"], result["matches"])
            path = Path(folder) / "tournament.csv"
            export_tournament(path, result)
            with path.open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 2)
            store.close()

    def test_invalid_tournament_parameters(self):
        for keys, games, seed in ((["hard"], 1, 42), (["hard", "hard"], 1, 42),
                                  (["hard", "unknown"], 1, 42), (["hard", "easy"], 0, 42)):
            with self.assertRaises(ValueError):
                run_tournament(keys, games, seed)


if __name__ == "__main__":
    unittest.main()
