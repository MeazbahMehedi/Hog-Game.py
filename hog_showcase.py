"""Display-independent tutorial, practice rules, and validated replay states."""

from dataclasses import dataclass

from dice import make_test_dice
from hog import GameSession, TurnEvent, boar_brawl, roll_dice, simple_update, sus_update


@dataclass(frozen=True)
class PracticeRules:
    goal: int = 50
    sus_fuss: bool = True
    starting_scores: tuple = (0, 0)
    seed: int | None = None
    opponent: str = "always5"

    def __post_init__(self):
        if type(self.goal) is not int or not 20 <= self.goal <= 200:
            raise ValueError("Practice goal must be 20-200.")
        if type(self.sus_fuss) is not bool:
            raise ValueError("Sus Fuss must be enabled or disabled.")
        if (not isinstance(self.starting_scores, tuple) or len(self.starting_scores) != 2
                or any(type(score) is not int or not 0 <= score < self.goal for score in self.starting_scores)):
            raise ValueError("Both starting scores must be nonnegative and below the goal.")
        if self.seed is not None and type(self.seed) is not int:
            raise ValueError("Use an integer seed or leave it blank.")
        if self.opponent not in ("always5", "always6", "catch-up"):
            raise ValueError("Choose a practice-compatible opponent.")

    def create_session(self):
        from hog import seeded_dice
        return GameSession(*self.starting_scores, dice=seeded_dice(self.seed), goal=self.goal,
                           update=sus_update if self.sus_fuss else simple_update)


def tutorial_lessons():
    """Expected answers are produced by the actual game rules."""
    return (
        ("Add the dice", "You roll 4, 5 and 6. How many points does this turn earn?",
         ("15", "1", "6"), str(roll_dice(3, make_test_dice(4, 5, 6))),
         "Without a rolled 1, add every die: 4 + 5 + 6 = 15."),
        ("Spot Sow Sad", "You roll 4, 1 and 6. How many points does this turn earn?",
         ("11", "1", "0"), str(roll_dice(3, make_test_dice(4, 1, 6))),
         "Any rolled 1 makes the whole turn worth just 1 point."),
        ("Take free points", "Your score is 21, the opponent has 46. What does choosing zero dice earn?",
         ("3", "1", "9"), str(boar_brawl(21, 46)),
         "Boar Brawl uses 3 x abs(4 - 1), so choosing zero dice earns 9."),
        ("Find the prime bonus", "You have 14 points and roll 3 and 4. What is your final total after Sus Fuss?",
         ("21", "23", "22"), str(sus_update(2, 14, 60, make_test_dice(3, 4))),
         "The total 21 has four factors. Sus Fuss increases it to the next prime: 23."),
    )


def replay_states(record):
    """Validate stored standard-match turns and reconstruct every score pair."""
    try:
        names = record["config"]["names"]
        if not isinstance(names, (tuple, list)) or len(names) != 2:
            raise ValueError("Invalid replay players.")
        for name in names:
            if not isinstance(name, str) or not name or len(name) > 20 or not all(char.isprintable() for char in name):
                raise ValueError("Invalid replay player name.")
        rows = record["events"]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
            raise ValueError("Invalid replay length.")
        session = GameSession()
        states = [{"scores": (0, 0), "event": None}]
        for raw in rows:
            event = TurnEvent(**{**raw, "outcomes": tuple(raw["outcomes"])})
            if len(event.outcomes) != event.num_rolls or any(type(value) is not int or not 1 <= value <= 6 for value in event.outcomes):
                raise ValueError("Invalid replay outcomes.")
            dice = iter(event.outcomes)
            session.dice = lambda: next(dice)
            actual = session.advance(event.num_rolls)
            if event != actual:
                raise ValueError("Replay scoring is inconsistent with the rules.")
            states.append({"scores": session.scores, "event": actual})
        if not session.finished or tuple(record["scores"]) != session.scores:
            raise ValueError("Replay final scores are inconsistent.")
        return tuple(states)
    except (KeyError, TypeError, StopIteration) as error:
        raise ValueError("Invalid replay record.") from error
