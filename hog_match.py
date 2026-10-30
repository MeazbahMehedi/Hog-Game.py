"""Validated desktop match setup, independent of Tk and the display."""

from dataclasses import dataclass

from hog import STRATEGIES


@dataclass(frozen=True)
class MatchConfig:
    """A local match: 0, 1, or 2 humans. In mode 1, Player 0 is human."""

    num_players: int = 1
    names: tuple = ("Player 0", "Computer")
    strategies: tuple = ("always5", "adaptive")
    seed: int | None = None

    def __post_init__(self):
        if type(self.num_players) is not int or self.num_players not in (0, 1, 2):
            raise ValueError("Choose a valid game mode.")
        if not isinstance(self.names, tuple) or len(self.names) != 2:
            raise ValueError("Enter two player names.")
        for name in self.names:
            if (not isinstance(name, str) or not name.strip() or len(name) > 20
                    or not all(character.isprintable() for character in name)):
                raise ValueError("Names must contain 1-20 printable characters.")
        if (not isinstance(self.strategies, tuple) or len(self.strategies) != 2
                or any(key not in STRATEGIES for key in self.strategies)):
            raise ValueError("Choose an available computer strategy.")
        if self.seed is not None and type(self.seed) is not int:
            raise ValueError("A seed must be a whole number, or leave it blank.")

    def is_human(self, player):
        if player not in (0, 1):
            raise ValueError("Player must be 0 or 1.")
        return self.num_players == 2 or (self.num_players == 1 and player == 0)
