# The Game of Hog

A Python dice game simulator with a text-based interface and several automated playing strategies.

I completed this project for **Python Programming - Project 1**. The work focuses on implementing the game rules, simulating complete games, comparing strategies, and designing a custom strategy using control flow and higher-order functions.

## Features

- Two-player games with a default goal of 100 points.
- All three special rules: Sow Sad, Boar Brawl, and Sus Fuss.
- Automatic simulation, one human against a computer, or two human players.
- Turn-by-turn output showing dice outcomes, score changes, and Sus Fuss bonuses.
- Fixed-roll, score-based, and custom adaptive strategies.
- Tools for estimating average turn scores and strategy win rates.
- Deterministic dice for repeatable examples and checks.

## Game Rules

Players alternate turns, choosing **0 to 10 dice** per turn. The first player to finish a turn with **at least 100 points** wins.

### Sow Sad

If any rolled die shows `1`, the player earns only **1 point** for that turn. Otherwise, the player earns the sum of all dice outcomes. All chosen dice are rolled even when a `1` appears.

### Boar Brawl

Rolling **0 dice** earns points using this formula:

```python
max(1, 3 * abs(opponent_tens_digit - player_ones_digit))
```

For example, a player with `21` points against an opponent with `46` points earns `3 * abs(4 - 1) = 9` points.

### Sus Fuss

After the turn's points are added, a total score with exactly **3 or 4 positive factors** increases to the next larger prime number. This also applies after rolling 0 dice.

For example, `21` has four factors: `1`, `3`, `7`, and `21`. A total score of `21` therefore increases to `23`.

## Project Files

Keep these files together in the repository root:

| File | Purpose |
| --- | --- |
| `hog.py` | Game rules, simulator, strategy functions, and experiment helpers. |
| `hog_ui.py` | Text-based interface for automatic and interactive games. |
| `dice.py` | Fair dice and deterministic test dice. |
| `ucb.py` | Starter utilities, including the command-line entry-point decorator. |
| `README.md` | Project overview and usage instructions. |

**Filename setup:** If your downloaded files have a `(1)` suffix, rename them before running or uploading:

| Downloaded name | Required name |
| --- | --- |
| `hog(1).py` | `hog.py` |
| `hog_ui(1).py` | `hog_ui.py` |
| `dice(1).py` | `dice.py` |
| `ucb(1).py` | `ucb.py` |

The code imports these modules by their original names.

## Requirements

- Python 3
- A terminal or a Python IDE such as PyCharm

The project uses only Python's standard library. No additional packages are required.

## Run the Game

Open a terminal in the folder containing the project files. Use `python3` instead of `python` if that is your system's Python 3 command.

### Watch an automatic game

```bash
python hog_ui.py
```

Both computer players always roll five dice.

### Play against the computer

```bash
python hog_ui.py -n 1
```

You play as Player 0. The computer plays as Player 1 and always rolls five dice. Enter an integer from `0` to `10` when prompted.

### Play with two human players

```bash
python hog_ui.py -n 2
```

Both players take turns entering their choices in the same terminal.

To view the available command-line options:

```bash
python hog_ui.py --help
```

## Available Strategies

A strategy receives the current player's score and the opponent's score, then returns the number of dice to roll.

| Strategy | Behavior |
| --- | --- |
| `always_roll_5` | Always rolls five dice. |
| `always_roll(n)` | Returns a strategy that always rolls `n` dice. |
| `catch_up` | Rolls six dice when behind; otherwise rolls five. |
| `boar_strategy` | Rolls zero when Boar Brawl gives at least the threshold; otherwise uses the configured roll count. Defaults: threshold 11, six dice. |
| `sus_strategy` | Rolls zero when the combined Boar Brawl and Sus Fuss gain reaches the threshold; otherwise uses the configured roll count. Defaults: threshold 11, six dice. |
| `adaptive_strategy` | Chooses a roll count based on guaranteed points, both scores, and proximity to the goal. |

### My Adaptive Strategy

`adaptive_strategy` checks the following conditions in order:

1. Roll zero if the resulting score would reach the goal.
2. Roll zero if the guaranteed gain, including Sus Fuss, is at least 10 points.
3. Roll three dice if my score is at least 80.
4. Otherwise, roll eight dice if the opponent's score is at least 80.
5. Roll six dice if both scores are below 30.
6. Roll five dice in all other situations.

The strategy uses guaranteed points when they are valuable and adjusts its roll count as the game progresses. It is a heuristic; its performance can be explored with the comparison tools below.

## Simulate and Compare Strategies

Start Python from the project folder:

```bash
python
```

Then run a game with the custom strategy against a six-dice baseline:

```python
from hog import adaptive_strategy, always_roll, play, sus_update

score0, score1 = play(adaptive_strategy, always_roll(6), sus_update)
print("Adaptive strategy:", score0)
print("Always roll 6:", score1)
```

To display each turn of a game using custom strategies:

```python
from hog import adaptive_strategy, always_roll
from hog_ui import play_and_print

play_and_print(adaptive_strategy, always_roll(6))
```

Estimate the adaptive strategy's win rate:

```python
from hog import adaptive_strategy, average_win_rate

win_rate = average_win_rate(adaptive_strategy)
print(f"Estimated win rate against always_roll(6): {win_rate:.1%}")
```

`average_win_rate` averages results from 1,000 games in each starting position, for 2,000 games in total. Results vary because the dice are random.

Find the roll count from 1 to 10 with the highest estimated average turn score:

```python
from hog import max_scoring_num_rolls

print(max_scoring_num_rolls())
```

This estimates points earned from dice rolls under Sow Sad; it does not optimize a complete game strategy.

**Current command-line behavior:** `hog.py` accepts `--run_experiments` (or `-r`), but the flag is not connected to an experiment runner. Use the Python examples above to run experiments.

## Repeatable Examples

Run these examples in Python from the project folder:

```python
from dice import make_test_dice
from hog import boar_brawl, roll_dice, sus_points

print(roll_dice(3, make_test_dice(4, 5, 6)))  # 15
print(roll_dice(3, make_test_dice(4, 1, 6)))  # 1: Sow Sad
print(boar_brawl(21, 46))                    # 9
print(sus_points(21))                       # 23: Sus Fuss
```

Unlike fair dice, `make_test_dice` cycles through the supplied outcomes, making these examples repeatable.

## What I Practiced

- Functions, parameters, and return values.
- Conditionals, loops, and input validation.
- Higher-order functions, closures, and `*args`.
- Number operations, factor counting, and prime checking.
- Random simulation and repeated-sampling estimates.
- Separating game logic from a text-based interface.

## Credits

This project is based on the supplied **Python Programming - Project 1: The Game of Hog** assignment and starter code. My assignment solutions and custom adaptive strategy are implemented in `hog.py`. The supporting files provide dice functions, the text interface, and utilities; `ucb.py` identifies its utilities as originating from UC Berkeley projects.
