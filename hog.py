"""The Game of Hog: rules, strategies, and a reusable simulator.

Based on the Python Programming Project 1 starter and the original student
solution. This edition keeps the assignment's public function names.
"""

from dataclasses import dataclass
from math import isqrt
from random import Random

from dice import six_sided, make_test_dice

GOAL = 100
VERSION = "1.1.0"


def _integer(value, name, minimum=0, maximum=None):
    """Validate user-controlled numbers even when Python uses -O."""
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer of at least {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be at most {maximum}.")
    return value


def roll_dice(num_rolls, dice=six_sided):
    """Roll exactly NUM_ROLLS dice; any 1 makes the turn worth 1 point.

    >>> roll_dice(3, make_test_dice(4, 5, 6))
    15
    >>> roll_dice(3, make_test_dice(4, 1, 6))
    1
    """
    _integer(num_rolls, "num_rolls", 1)
    total, sow_sad = 0, False
    for _ in range(num_rolls):
        outcome = dice()
        total += outcome
        sow_sad = sow_sad or outcome == 1
    return 1 if sow_sad else total


def boar_brawl(player_score, opponent_score):
    """Return the points awarded for choosing zero dice.

    >>> boar_brawl(21, 46)
    9
    >>> boar_brawl(45, 52)
    1
    """
    opponent_tens = opponent_score // 10 % 10
    player_ones = player_score % 10
    return max(1, 3 * abs(opponent_tens - player_ones))


def take_turn(num_rolls, player_score, opponent_score, dice=six_sided):
    """Return points earned on one turn, before Sus Fuss."""
    _integer(num_rolls, "num_rolls", 0, 10)
    if num_rolls == 0:
        return boar_brawl(player_score, opponent_score)
    return roll_dice(num_rolls, dice)


def simple_update(num_rolls, player_score, opponent_score, dice=six_sided):
    """Return the new total score, without Sus Fuss."""
    return player_score + take_turn(num_rolls, player_score, opponent_score, dice)


def is_prime(n):
    """Return whether N is prime; values below 2 are not prime."""
    if n < 2:
        return False
    for divisor in range(2, isqrt(n) + 1):
        if n % divisor == 0:
            return False
    return True


def num_factors(n):
    """Count positive factors, counting a square root only once.

    >>> num_factors(9), num_factors(21)
    (3, 4)
    """
    _integer(n, "n", 1)
    count = 0
    for divisor in range(1, isqrt(n) + 1):
        if n % divisor == 0:
            count += 1 if divisor * divisor == n else 2
    return count


def sus_points(score):
    """Promote totals with three or four factors to the next prime.

    >>> sus_points(21), sus_points(64), sus_points(67)
    (23, 64, 67)
    """
    _integer(score, "score")
    if score == 0 or num_factors(score) not in (3, 4):
        return score
    score += 1
    while not is_prime(score):
        score += 1
    return score


def sus_update(num_rolls, player_score, opponent_score, dice=six_sided):
    """Return the new total with all three rules enabled."""
    return sus_points(simple_update(num_rolls, player_score, opponent_score, dice))


@dataclass(frozen=True)
class TurnEvent:
    """A completed turn for interfaces; no additional dice are rolled."""

    number: int
    player: int
    num_rolls: int
    outcomes: tuple
    score_before: int
    opponent_score: int
    turn_points: int
    score_after: int

    @property
    def bonus(self):
        return self.score_after - self.score_before - self.turn_points


def play(strategy0, strategy1, update, score0=0, score1=0, dice=six_sided,
         goal=GOAL, *, observer=None):
    """Return final scores, calling one strategy exactly once per turn.

    The original positional arguments are preserved. An optional observer
    receives one TurnEvent after each completed turn. The engine never prints.
    """
    _integer(score0, "score0")
    _integer(score1, "score1")
    _integer(goal, "goal", 1)
    scores = [score0, score1]
    who, turn_number = 0, 1
    strategies = (strategy0, strategy1)
    while max(scores) < goal:
        before, opponent = scores[who], scores[1 - who]
        count = strategies[who](before, opponent)
        _integer(count, "strategy roll count", 0, 10)
        outcomes = []

        def recording_dice():
            value = dice()
            outcomes.append(value)
            return value

        scores[who] = update(count, before, opponent,
                             recording_dice if observer is not None else dice)
        if observer is not None:
            points = (boar_brawl(before, opponent) if count == 0
                      else 1 if 1 in outcomes else sum(outcomes))
            observer(TurnEvent(turn_number, who, count, tuple(outcomes),
                               before, opponent, points, scores[who]))
        who = 1 - who
        turn_number += 1
    return tuple(scores)


def always_roll_5(score, opponent_score):
    return 5


def always_roll(n):
    """Return a strategy that always rolls N dice.

    >>> always_roll(3)(99, 99)
    3
    """
    _integer(n, "n", 0, 10)

    def strategy(score, opponent_score):
        return n
    return strategy


def catch_up(score, opponent_score):
    """Roll six when behind, otherwise five.

    >>> catch_up(9, 4)
    5
    >>> catch_up(17, 18)
    6
    """
    return 6 if score < opponent_score else 5


def make_averaged(original_function, times_called=1000):
    """Return a function that averages repeated calls with the same arguments.

    >>> averaged = make_averaged(roll_dice, 40)
    >>> averaged(1, make_test_dice(4, 2, 5, 1))
    3.0
    """
    _integer(times_called, "times_called", 1)

    def averaged(*args):
        return sum(original_function(*args) for _ in range(times_called)) / times_called
    return averaged


def max_scoring_num_rolls(dice=six_sided, times_called=1000):
    """Return the best average-scoring roll count; lower counts win ties.

    >>> max_scoring_num_rolls(make_test_dice(1, 6))
    1
    """
    averaged = make_averaged(roll_dice, times_called)
    best_count, best_average = 1, float("-inf")
    for count in range(1, 11):
        average = averaged(count, dice)
        if average > best_average:
            best_count, best_average = count, average
    return best_count


def winner(strategy0, strategy1):
    """Return the winner's player index."""
    score0, score1 = play(strategy0, strategy1, sus_update)
    return 0 if score0 > score1 else 1


def average_win_rate(strategy, baseline=always_roll(6), times_called=1000):
    """Average wins across TIMES_CALLED games in each starting position."""
    averaged_winner = make_averaged(winner, times_called)
    return ((1 - averaged_winner(strategy, baseline))
            + averaged_winner(baseline, strategy)) / 2


def boar_strategy(score, opponent_score, threshold=11, num_rolls=6):
    return 0 if boar_brawl(score, opponent_score) >= threshold else num_rolls


def sus_strategy(score, opponent_score, threshold=11, num_rolls=6):
    gain = sus_update(0, score, opponent_score) - score
    return 0 if gain >= threshold else num_rolls


def adaptive_strategy(score, opponent_score):
    """The original student's adaptive strategy, using the default 100 goal."""
    free_points = sus_update(0, score, opponent_score) - score
    if score + free_points >= GOAL or free_points >= 10:
        return 0
    if score >= 80:
        return 3
    if opponent_score >= 80:
        return 8
    if score < 30 and opponent_score < 30:
        return 6
    return 5


STRATEGIES = {
    "always5": (always_roll_5, "Always roll 5", "A steady five-dice baseline."),
    "always6": (always_roll(6), "Always roll 6", "A six-dice comparison baseline."),
    "catch-up": (catch_up, "Catch up", "Roll six when behind, otherwise five."),
    "boar": (boar_strategy, "Boar Brawl", "Take zero dice for at least 11 free points."),
    "sus": (sus_strategy, "Sus Fuss", "Include the prime bonus when choosing zero dice."),
    "adaptive": (adaptive_strategy, "Adaptive", "The original custom score-aware strategy."),
}


def seeded_dice(seed=None):
    """Create independent fair six-sided dice, optionally reproducible."""
    rng = Random(seed)

    def dice():
        return rng.randint(1, 6)
    return dice


def run(*args):
    """Launch the experiment CLI; retained for assignment compatibility."""
    from hog_experiments import main
    return main(list(args) if args else None)


if __name__ == "__main__":
    run()
