"""The desktop and simulator must produce the exact same match."""

import unittest

from dice import make_test_dice
from hog import GameSession, STRATEGIES, play, seeded_dice, sus_update
from hog_match import MatchConfig


class SessionTests(unittest.TestCase):
    def test_incremental_matches_equal_full_simulator(self):
        for seed in range(10):
            session = GameSession(dice=seeded_dice(seed))
            strategies = (STRATEGIES["adaptive"][0], STRATEGIES["sus"][0])
            events = []
            while not session.finished:
                who = session.current_player
                count = strategies[who](session.scores[who], session.scores[1 - who])
                events.append(session.advance(count))
            expected_events = []
            scores = play(*strategies, sus_update, dice=seeded_dice(seed),
                          observer=expected_events.append)
            self.assertEqual(session.scores, scores)
            self.assertEqual(events, expected_events)
            self.assertEqual(session.winner, 0 if scores[0] > scores[1] else 1)

    def test_initial_state_and_first_move(self):
        session = GameSession(dice=make_test_dice(3))
        self.assertEqual((session.scores, session.current_player, session.winner), ((0, 0), 0, None))
        event = session.advance(1)
        self.assertEqual(event.outcomes, (3,))
        self.assertEqual((session.scores, session.current_player), ((3, 0), 1))

    def test_invalid_move_does_not_advance_state(self):
        session = GameSession()
        with self.assertRaises(ValueError):
            session.advance(11)
        self.assertEqual((session.scores, session.turn_number), ((0, 0), 1))

    def test_cannot_play_after_match_end(self):
        session = GameSession(score0=99, score1=0)
        event = session.advance(0)
        self.assertTrue(session.finished)
        with self.assertRaises(ValueError):
            session.advance(0)
        self.assertEqual(session.scores[0], event.score_after)

    def test_configuration_modes(self):
        for mode, expected in ((0, (False, False)), (1, (True, False)), (2, (True, True))):
            config = MatchConfig(num_players=mode)
            self.assertEqual(tuple(config.is_human(player) for player in (0, 1)), expected)

    def test_configuration_rejects_invalid_values(self):
        cases = [dict(num_players=3), dict(num_players=True), dict(names=("", "Bob")),
                 dict(names=("Alice\n", "Bob")), dict(names=("A" * 21, "Bob")),
                 dict(strategies=("unknown", "sus")), dict(seed="42"), dict(seed=True)]
        for keywords in cases:
            with self.subTest(keywords=keywords), self.assertRaises(ValueError):
                MatchConfig(**keywords)


if __name__ == "__main__":
    unittest.main()
