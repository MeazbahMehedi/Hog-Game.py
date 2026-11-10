"""Tutorial answers, practice isolation, and read-only replay validation."""

from copy import deepcopy
from dataclasses import asdict
import unittest

from hog import seeded_dice, GameSession
from hog_showcase import PracticeRules, tutorial_lessons, replay_states
from hog_match import MatchConfig


class ShowcaseTests(unittest.TestCase):
    def record(self):
        session = GameSession(dice=seeded_dice(42))
        events = []
        while not session.finished:
            events.append(session.advance(0))
        return {"config": asdict(MatchConfig()), "scores": session.scores,
                "events": [asdict(event) for event in events]}

    def test_tutorial_answers_use_the_rules(self):
        lessons = tutorial_lessons()
        self.assertEqual([lesson[3] for lesson in lessons], ["15", "1", "9", "23"])
        self.assertTrue(all(lesson[3] in lesson[2] for lesson in lessons))

    def test_custom_goal_and_disabled_sus_fuss(self):
        session = PracticeRules(30, False, (7, 0), 42).create_session()
        session.dice = lambda: 1
        event = session.advance(1)
        self.assertEqual((session.goal, event.score_after), (30, 8))
        enabled = PracticeRules(30, True, (7, 0), 42).create_session()
        enabled.dice = lambda: 1
        self.assertEqual(enabled.advance(1).score_after, 11)

    def test_invalid_practice_settings(self):
        for changes in (dict(goal=19), dict(goal=201), dict(starting_scores=(50, 0)),
                        dict(opponent="hard"), dict(seed="42"), dict(sus_fuss=1)):
            with self.assertRaises(ValueError):
                PracticeRules(**changes)

    def test_practice_seed_is_repeatable(self):
        first = PracticeRules(seed=42).create_session()
        second = PracticeRules(seed=42).create_session()
        self.assertEqual(first.advance(6), second.advance(6))

    def test_replay_reconstructs_every_score_pair(self):
        record = self.record()
        states = replay_states(record)
        self.assertEqual(states[0]["scores"], (0, 0))
        self.assertEqual(states[-1]["scores"], record["scores"])
        self.assertEqual(len(states), len(record["events"]) + 1)

    def test_replay_rejects_tampered_scoring_and_final_scores(self):
        for field in ("event", "final"):
            record = self.record()
            if field == "event":
                record["events"][0]["score_after"] += 1
            else:
                record["scores"] = (1, 1)
            with self.assertRaises(ValueError):
                replay_states(record)

    def test_replay_requires_completed_match(self):
        record = self.record()
        record["events"] = record["events"][:1]
        with self.assertRaises(ValueError):
            replay_states(record)

    def test_replay_does_not_mutate_record(self):
        record = self.record()
        before = deepcopy(record)
        replay_states(record)
        self.assertEqual(record, before)


if __name__ == "__main__":
    unittest.main()
