"""Reproducible round robins: every pair plays equal games in both seats."""

import csv
from itertools import combinations

from hog import STRATEGIES, play, seeded_dice, sus_update


def run_tournament(keys=("always5", "adaptive", "sus", "medium", "hard"), games=10, seed=42):
    keys = tuple(keys)
    if len(keys) < 2 or len(keys) > 9 or len(set(keys)) != len(keys) or any(key not in STRATEGIES for key in keys):
        raise ValueError("Choose 2-9 distinct available strategies.")
    if type(games) is not int or not 1 <= games <= 200 or type(seed) is not int:
        raise ValueError("Use 1-200 games per seat and an integer seed.")
    table = {key: {"strategy": key, "played": 0, "wins": 0, "points_for": 0,
                   "points_against": 0} for key in keys}
    matches = []
    dice = seeded_dice(seed)
    for left, right in combinations(keys, 2):
        for _ in range(games):
            for first, second in ((left, right), (right, left)):
                scores = play(STRATEGIES[first][0], STRATEGIES[second][0], sus_update, dice=dice)
                winner = first if scores[0] > scores[1] else second
                for key, own, other in ((first, scores[0], scores[1]), (second, scores[1], scores[0])):
                    row = table[key]
                    row["played"] += 1
                    row["wins"] += key == winner
                    row["points_for"] += own
                    row["points_against"] += other
                matches.append({"first": first, "second": second, "score0": scores[0],
                                "score1": scores[1], "winner": winner})
    standings = sorted(table.values(), key=lambda row: (-row["wins"],
                       -(row["points_for"] - row["points_against"]), row["strategy"]))
    return {"schema": 1, "seed": seed, "games_per_seat": games, "strategies": keys,
            "standings": standings, "matches": matches}


def export_tournament(path, result):
    with open(path, "w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=("first", "second", "score0", "score1", "winner"))
        writer.writeheader()
        writer.writerows(result["matches"])
