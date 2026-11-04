"""Fair six-sided Hog analysis, independent of gameplay RNG and Tk.

Hard uses finite-state dynamic programming against an optimal opponent.
All moves gain points, so states can be solved in descending score-sum order.
"""

from dataclasses import dataclass
from functools import lru_cache
from collections import Counter


@lru_cache(maxsize=10)
def roll_distribution(count):
    if type(count) is not int or not 1 <= count <= 10:
        raise ValueError("Roll count must be 1-10.")
    totals = Counter({0: 1})
    for _ in range(count):
        following = Counter()
        for total, ways in totals.items():
            for face in range(2, 7):
                following[total + face] += ways
        totals = following
    denominator = 6 ** count
    return ((1, 1 - (5 / 6) ** count),) + tuple(
        (total, ways / denominator) for total, ways in sorted(totals.items()))


@dataclass(frozen=True)
class MoveAnalysis:
    dice: int
    expected_gain: float
    win_probability: float
    sow_sad_probability: float


def validate_scores(score, opponent):
    if any(type(value) is not int or not 0 <= value < 100 for value in (score, opponent)):
        raise ValueError("Analysis requires two active scores from 0 to 99.")


@lru_cache(maxsize=1)
def policy():
    from hog import sus_points, boar_brawl
    promoted = [sus_points(value) for value in range(161)]
    values = [[0.0] * 100 for _ in range(100)]
    choices = [[0] * 100 for _ in range(100)]
    distributions = [None] + [roll_distribution(count) for count in range(1, 11)]
    for total in range(198, -1, -1):
        for score in range(max(0, total - 99), min(99, total) + 1):
            opponent = total - score
            free = promoted[score + boar_brawl(score, opponent)]
            best = 1.0 if free >= 100 else 1 - values[opponent][free]
            choice = 0
            for count in range(1, 11):
                probability = 0.0
                for points, weight in distributions[count]:
                    after = promoted[score + points]
                    probability += weight * (1.0 if after >= 100 else 1 - values[opponent][after])
                if probability > best + 1e-12:
                    best, choice = probability, count
            values[score][opponent], choices[score][opponent] = best, choice
    return values, choices


def analyze_moves(score, opponent):
    from hog import sus_points, boar_brawl
    validate_scores(score, opponent)
    values, _ = policy()
    rows = []
    for count in range(11):
        distribution = ((boar_brawl(score, opponent), 1.0),) if count == 0 else roll_distribution(count)
        gain = probability = 0.0
        for points, weight in distribution:
            after = sus_points(score + points)
            gain += weight * (after - score)
            probability += weight * (1.0 if after >= 100 else 1 - values[opponent][after])
        rows.append(MoveAnalysis(count, gain, probability, 0.0 if count == 0 else 1 - (5 / 6) ** count))
    return tuple(rows)


def easy_strategy(score, opponent):
    return 5


@lru_cache(maxsize=10000)
def medium_strategy(score, opponent):
    from hog import sus_update, sus_points
    validate_scores(score, opponent)
    if sus_update(0, score, opponent) >= 100:
        return 0
    best_count, best_gain = 0, sus_update(0, score, opponent) - score
    for count in range(1, 11):
        gain = sum(weight * (sus_points(score + points) - score)
                   for points, weight in roll_distribution(count))
        if gain > best_gain + 1e-12:
            best_count, best_gain = count, gain
    return best_count


def hard_strategy(score, opponent):
    validate_scores(score, opponent)
    return policy()[1][score][opponent]


def advice_text(score, opponent, rows=None):
    rows = rows or analyze_moves(score, opponent)
    choice = hard_strategy(score, opponent)
    row = rows[choice]
    action = "Take zero dice" if choice == 0 else f"Roll {choice} dice"
    return (f"{action}. Expected gain: {row.expected_gain:.2f} points. "
            f"Model win chance: {row.win_probability:.1%}. "
            f"Sow Sad risk: {row.sow_sad_probability:.1%}. "
            "Model assumes fair six-sided dice, all three rules, goal 100, "
            "and optimal play by both players after this move. It cannot predict the next roll.")


def compare_opponents(games=40, seed=42, baseline="adaptive"):
    """Measured matches in both seats, with a fresh seeded stream per candidate."""
    from hog import STRATEGIES, seeded_dice
    from hog_experiments import compare_strategy, wilson_interval
    if type(games) is not int or not 1 <= games <= 2000:
        raise ValueError("Games per seat must be 1-2000.")
    if baseline not in STRATEGIES or type(seed) is not int:
        raise ValueError("Choose a strategy and an integer seed.")
    rows = []
    for key in ("always5", "adaptive", "sus", "easy", "medium", "hard"):
        first, second = compare_strategy(STRATEGIES[key][0], STRATEGIES[baseline][0], games, seeded_dice(seed))
        low, high = wilson_interval(first + second, games * 2)
        rows.append((key, first, second, (first + second) / (games * 2), low, high))
    return tuple(rows)
