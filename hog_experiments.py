"""Seedable strategy experiments; Python standard library only."""

import argparse
import math

from hog import (STRATEGIES, VERSION, play, roll_dice, seeded_dice, sus_update)


def positive_integer(text):
    try:
        value = int(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Enter a positive integer.") from error
    if value < 1:
        raise argparse.ArgumentTypeError("Enter a positive integer.")
    return value


def wilson_interval(wins, games):
    """Approximate 95% binomial interval, useful for reading noisy estimates."""
    z = 1.96
    proportion = wins / games
    denominator = 1 + z * z / games
    center = (proportion + z * z / (2 * games)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / games
                           + z * z / (4 * games * games)) / denominator
    return max(0, center - margin), min(1, center + margin)


def compare_strategy(strategy, baseline, games_per_seat, dice):
    """Give the candidate the same number of games in each starting seat."""
    wins_first = wins_second = 0
    for _ in range(games_per_seat):
        first, second = play(strategy, baseline, sus_update, dice=dice)
        wins_first += first > second
        first, second = play(baseline, strategy, sus_update, dice=dice)
        wins_second += second > first
    return wins_first, wins_second


def run_experiments(games=200, samples=1000, seed=None, baseline="always6"):
    """Print real measurements. GAMES means games per starting position."""
    dice = seeded_dice(seed)
    print(f"HOG / STRATEGY LAB                                      v{VERSION}")
    print("=" * 76)
    print(f"Baseline: {baseline} | {games} games per seat | {games * 2} per strategy")
    print(f"Dice samples: {samples} per roll count | Seed: {seed}")
    print("All games use Sow Sad, Boar Brawl and Sus Fuss. Goal: 100.")
    print("\nTURN SCORE EXPERIMENT / Sow Sad only")
    best_count, best_average = 1, float("-inf")
    for count in range(1, 11):
        average = sum(roll_dice(count, dice) for _ in range(samples)) / samples
        print(f"  {count:2d} dice    {average:6.2f} average points")
        if average > best_average:
            best_count, best_average = count, average
    print(f"Best sampled roll count: {best_count} (ties choose the lower count)")
    print("\nSTRATEGY COMPARISON / candidate wins against baseline")
    print(f"{'Strategy':<14} {'First seat':>11} {'Second seat':>12} {'Overall':>10}  {'95% interval':>15}")
    rows = []
    for key, (strategy, _, _) in STRATEGIES.items():
        first, second = compare_strategy(strategy, STRATEGIES[baseline][0], games, dice)
        total = games * 2
        wins = first + second
        low, high = wilson_interval(wins, total)
        print(f"{key:<14} {first / games:>10.1%} {second / games:>11.1%} "
              f"{wins / total:>9.1%}  {low:>6.1%} - {high:.1%}")
        rows.append((key, first, second, wins / total))
    print("\nEstimates vary with sample size and seed; no strategy is guaranteed best.")
    print("Intervals are approximate Wilson binomial intervals for pooled wins.")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hog strategy experiment runner")
    parser.add_argument("-r", "--run_experiments", "--run-experiments",
                        action="store_true", help="run the strategy lab")
    parser.add_argument("--games", type=positive_integer, default=200,
                        help="games per starting seat per strategy (default: 200)")
    parser.add_argument("--samples", type=positive_integer, default=1000,
                        help="samples for each roll count (default: 1000)")
    parser.add_argument("--seed", type=int, help="optional reproducible random seed")
    parser.add_argument("--baseline", choices=STRATEGIES, default="always6")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args(argv)
    if args.run_experiments:
        run_experiments(args.games, args.samples, args.seed, args.baseline)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
