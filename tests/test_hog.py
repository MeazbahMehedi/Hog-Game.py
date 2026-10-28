"""Rule and engine regressions: python -m unittest discover -s tests -v."""

import contextlib
import io
import unittest

from dice import make_test_dice
import hog


class RulesTests(unittest.TestCase):
    def test_sow_sad_consumes_every_roll(self):
        dice = make_test_dice(1, 6, 5, 4)
        self.assertEqual(hog.roll_dice(3, dice), 1)
        self.assertEqual(dice(), 4)

    def test_sum_when_no_one_is_rolled(self):
        self.assertEqual(hog.roll_dice(4, make_test_dice(3, 2, 4, 2)), 11)

    def test_boar_brawl_assignment_examples(self):
        for scores, expected in [((21, 46), 9), ((45, 52), 1), ((2, 5), 6)]:
            with self.subTest(scores=scores):
                self.assertEqual(hog.boar_brawl(*scores), expected)

    def test_boar_uses_only_tens_digit(self):
        self.assertEqual(hog.boar_brawl(21, 146), 9)

    def test_zero_dice_does_not_call_dice(self):
        def forbidden():
            self.fail("Zero dice must not call the dice function")
        self.assertEqual(hog.take_turn(0, 21, 46, forbidden), 9)

    def test_factors_against_naive_definition(self):
        for value in range(1, 301):
            expected = sum(value % factor == 0 for factor in range(1, value + 1))
            self.assertEqual(hog.num_factors(value), expected, value)

    def test_primes_against_naive_definition(self):
        for value in range(-3, 301):
            expected = value >= 2 and all(value % d != 0 for d in range(2, value))
            self.assertEqual(hog.is_prime(value), expected, value)

    def test_sus_promotes_three_or_four_factors_only(self):
        for value in range(301):
            count = sum(value % d == 0 for d in range(1, value + 1))
            expected = value
            if count in (3, 4):
                expected += 1
                while not (expected >= 2 and all(expected % d for d in range(2, expected))):
                    expected += 1
            self.assertEqual(hog.sus_points(value), expected, value)

    def test_sus_applies_to_zero_dice(self):
        self.assertEqual(hog.sus_update(0, 53, 60), 67)

    def test_sus_applies_after_sow_sad(self):
        self.assertEqual(hog.sus_update(2, 7, 30, make_test_dice(1, 5)), 11)

    def test_simple_update_omits_prime_bonus(self):
        self.assertEqual(hog.simple_update(0, 53, 60), 62)

    def test_invalid_roll_counts(self):
        for value in (-1, 11, 1.5, True, "2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                hog.take_turn(value, 0, 0)

    def test_zero_roll_dice_and_zero_samples_rejected(self):
        for fn in (lambda: hog.roll_dice(0), lambda: hog.make_averaged(abs, 0),
                   lambda: hog.num_factors(0), lambda: hog.always_roll(True)):
            with self.assertRaises(ValueError):
                fn()


class EngineTests(unittest.TestCase):
    def test_exact_alternation_and_no_post_win_turn(self):
        calls = []

        def strategy0(score, opponent):
            calls.append((0, score, opponent))
            return 1

        def strategy1(score, opponent):
            calls.append((1, score, opponent))
            return 1

        result = hog.play(strategy0, strategy1, hog.simple_update,
                          dice=make_test_dice(3), goal=5)
        self.assertEqual(result, (6, 3))
        self.assertEqual(calls, [(0, 0, 0), (1, 0, 3), (0, 3, 3)])

    def test_game_already_over_skips_strategies(self):
        def forbidden(*args):
            self.fail("Game should already be over")
        self.assertEqual(hog.play(forbidden, forbidden, hog.sus_update, score1=100), (0, 100))

    def test_observer_does_not_change_dice_or_result(self):
        events = []
        first_dice = hog.seeded_dice(28)
        second_dice = hog.seeded_dice(28)
        expected = hog.play(hog.adaptive_strategy, hog.sus_strategy, hog.sus_update, dice=first_dice)
        observed = hog.play(hog.adaptive_strategy, hog.sus_strategy, hog.sus_update,
                            dice=second_dice, observer=events.append)
        self.assertEqual(expected, observed)
        self.assertEqual(first_dice(), second_dice())
        self.assertEqual([e.number for e in events], list(range(1, len(events) + 1)))
        self.assertTrue(all(len(e.outcomes) == e.num_rolls for e in events))

    def test_event_reports_zero_dice_and_bonus(self):
        events = []
        self.assertEqual(hog.play(hog.always_roll(0), hog.always_roll(0),
                                  hog.sus_update, 53, 60, goal=67,
                                  observer=events.append), (67, 60))
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0].outcomes, events[0].turn_points, events[0].bonus), ((), 9, 5))

    def test_engine_does_not_print(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            hog.play(hog.always_roll(0), hog.always_roll(0), hog.sus_update)
        self.assertEqual(output.getvalue(), "")

    def test_seeded_game_is_repeatable(self):
        def game():
            return hog.play(hog.adaptive_strategy, hog.catch_up,
                            hog.sus_update, dice=hog.seeded_dice(42))
        self.assertEqual(game(), game())

    def test_bad_strategy_return_is_rejected(self):
        with self.assertRaises(ValueError):
            hog.play(lambda *_: 11, hog.always_roll_5, hog.sus_update)


class StrategyTests(unittest.TestCase):
    def test_strategies_return_valid_counts_for_every_active_score(self):
        for strategy, _, _ in hog.STRATEGIES.values():
            for score in range(100):
                for opponent in range(100):
                    count = strategy(score, opponent)
                    self.assertIs(type(count), int)
                    self.assertTrue(0 <= count <= 10)

    def test_adaptive_priority_and_thresholds(self):
        cases = [((99, 0), 0), ((53, 60), 0), ((88, 80), 3),
                 ((8, 80), 8), ((0, 0), 6), ((43, 30), 5)]
        for scores, expected in cases:
            self.assertEqual(hog.adaptive_strategy(*scores), expected, scores)

    def test_boar_and_sus_strategies_have_different_information(self):
        self.assertEqual(hog.boar_strategy(53, 60), 6)
        self.assertEqual(hog.sus_strategy(53, 60), 0)

    def test_averaging_passes_all_arguments(self):
        averaged = hog.make_averaged(lambda a, b: a + b, 5)
        self.assertEqual(averaged(4, 2), 6)

    def test_best_count_tie_keeps_lowest(self):
        self.assertEqual(hog.max_scoring_num_rolls(make_test_dice(1), 20), 1)

    def test_average_win_rate_balances_seats(self):
        rate = hog.average_win_rate(hog.always_roll(0), hog.always_roll(0), times_called=5)
        self.assertEqual(rate, 0.5)


if __name__ == "__main__":
    unittest.main()
