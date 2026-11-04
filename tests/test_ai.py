"""Independent probability checks and policy/analysis contracts."""

from collections import Counter
from itertools import product
import unittest

from hog import sus_update, STRATEGIES, seeded_dice, play
from hog_ai import (roll_distribution, analyze_moves, policy, hard_strategy,
                    medium_strategy, advice_text, compare_opponents)


class ProbabilityTests(unittest.TestCase):
    def test_distributions_match_exhaustive_enumeration(self):
        for count in range(1, 4):
            outcomes = Counter(1 if 1 in faces else sum(faces)
                               for faces in product(range(1, 7), repeat=count))
            actual = dict(roll_distribution(count))
            self.assertEqual(set(actual), set(outcomes))
            for points, ways in outcomes.items():
                self.assertAlmostEqual(actual[points], ways / 6 ** count)

    def test_probability_mass_and_risk(self):
        for count in range(1, 11):
            rows = roll_distribution(count)
            self.assertAlmostEqual(sum(weight for _, weight in rows), 1)
            self.assertAlmostEqual(dict(rows)[1], 1 - (5 / 6) ** count)

    def test_policy_is_bounded_and_actions_legal(self):
        values, choices = policy()
        self.assertTrue(all(0 <= value <= 1 + 1e-12 for row in values for value in row))
        self.assertTrue(all(0 <= count <= 10 for row in choices for count in row))

    def test_zero_dice_certain_win(self):
        for opponent in range(100):
            self.assertEqual(hard_strategy(99, opponent), 0)
            self.assertEqual(medium_strategy(99, opponent), 0)

    def test_bellman_values_match_independent_move_analysis(self):
        values, choices = policy()
        for score, opponent in ((0, 0), (53, 60), (88, 91), (99, 0), (14, 63)):
            rows = analyze_moves(score, opponent)
            best = max(row.win_probability for row in rows)
            self.assertAlmostEqual(values[score][opponent], best)
            self.assertAlmostEqual(rows[choices[score][opponent]].win_probability, best)

    def test_zero_dice_analysis_includes_sus_fuss(self):
        row = analyze_moves(53, 60)[0]
        self.assertEqual(row.expected_gain, 14)
        self.assertEqual(row.sow_sad_probability, 0)

    def test_advice_does_not_touch_game_rng(self):
        dice = seeded_dice(42)
        reference = seeded_dice(42)
        advice_text(53, 60)
        self.assertEqual([dice() for _ in range(30)], [reference() for _ in range(30)])

    def test_invalid_analysis_scores_rejected(self):
        for values in ((-1, 0), (100, 0), (True, 0), (0, 1.5)):
            with self.assertRaises(ValueError):
                analyze_moves(*values)

    def test_comparison_is_repeatable_and_seat_counts_valid(self):
        first = compare_opponents(3, 42)
        self.assertEqual(first, compare_opponents(3, 42))
        for key, seat0, seat1, rate, low, high in first:
            self.assertTrue(0 <= seat0 <= 3 and 0 <= seat1 <= 3)
            self.assertEqual(rate, (seat0 + seat1) / 6)
            self.assertTrue(low <= rate <= high)

    def test_new_opponents_complete_seeded_matches(self):
        for key in ("easy", "medium", "hard"):
            scores = play(STRATEGIES[key][0], STRATEGIES["adaptive"][0], sus_update,
                          dice=seeded_dice(42))
            self.assertGreaterEqual(max(scores), 100)


if __name__ == "__main__":
    unittest.main()
