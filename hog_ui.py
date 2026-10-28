"""Hog v1.1.0: a dependency-free terminal interface.

Run without flags for the menu, or keep using the original -n 0/1/2 modes.
"""

import argparse

from hog import (GOAL, STRATEGIES, VERSION, boar_brawl, play, seeded_dice,
                 six_sided, sus_points, sus_update)

WIDTH = 76


class BackToMenu(Exception):
    """A player requested to leave the current screen or game."""


def heading(title, subtitle=""):
    print("\n" + "=" * WIDTH)
    print(f"  H O G / {title}                                      v{VERSION}")
    if subtitle:
        print("  " + subtitle)
    print("=" * WIDTH)


def get_int(prompt, lower, upper):
    """Accept bounded whole numbers; q/back returns to the menu."""
    while True:
        text = input(prompt).strip()
        if text.lower() in ("q", "quit", "back"):
            raise BackToMenu
        try:
            # int() handles Unicode digits safely, unlike isnumeric() + int().
            choice = int(text)
        except ValueError:
            print(f"  Enter a whole number from {lower} to {upper}, or q to go back.")
            continue
        if lower <= choice <= upper:
            return choice
        print(f"  Choose between {lower} and {upper}, or q to go back.")


def valid_name(text):
    value = text.strip()
    if not value or len(value) > 20 or not all(c.isprintable() for c in value):
        raise argparse.ArgumentTypeError("Names must contain 1-20 printable characters.")
    return value


def get_name(prompt, default):
    while True:
        text = input(f"  {prompt} [{default}]: ").strip()
        if text.lower() in ("q", "quit", "back"):
            raise BackToMenu
        try:
            return valid_name(text or default)
        except argparse.ArgumentTypeError as error:
            print("  " + str(error))


def show_strategies():
    heading("STRATEGY GUIDE", "Each strategy chooses between 0 and 10 dice.")
    for key, (_, title, description) in STRATEGIES.items():
        print(f"  {key:<10} {title}")
        print(f"             {description}")
    print("\n  Adaptive is the original custom strategy, not a trained AI model.")


def choose_strategy(prompt):
    print("\n  " + prompt)
    keys = list(STRATEGIES)
    for index, key in enumerate(keys, 1):
        print(f"    [{index}] {STRATEGIES[key][1]} ({key})")
    return keys[get_int("  Strategy [1-6]: ", 1, len(keys)) - 1]


def show_rules():
    heading("HOW TO PLAY", "Two players. One goal. Know when to take the free points.")
    print("  GOAL       Be first to end a turn with at least 100 points.")
    print("  YOUR TURN  Choose 0-10 dice. Player 0 starts the game.")
    print("\n  SOW SAD")
    print("  Any rolled 1 makes the turn worth just 1 point.")
    print("  Otherwise, add up all the rolled dice.")
    print("\n  BOAR BRAWL / choose zero dice")
    print("  Gain max(1, 3 x abs(opponent tens digit - your ones digit)).")
    print("  Example: your score 21, opponent 46 -> 9 points.")
    print("\n  SUS FUSS / after adding the turn points")
    print("  If your total has exactly 3 or 4 positive factors, increase it")
    print("  to the next larger prime. Example: 21 -> 23.")
    print("  This bonus applies to zero-dice turns too.")
    print("\n  CONTROLS   Enter a number to choose. q returns to the menu.")
    print("             Ctrl+C or end-of-input closes the session safely.")


def interactive_strategy(who, name=None):
    """Return a human-controlled strategy, compatible with the original UI."""
    label = name or f"Player {who}"

    def strategy(score, opponent_score):
        guaranteed = sus_update(0, score, opponent_score) - score
        print(f"\n  {label}, your score: {score} | Opponent: {opponent_score}")
        print(f"  Zero dice guarantees +{guaranteed} points, including any Sus Fuss.")
        return get_int("  Dice to roll [0-10, q to leave]: ", 0, 10)
    return strategy


def print_turn(event, names):
    """Render the engine's completed turn without rerolling any dice."""
    print(f"\n  TURN {event.number:02d} / {names[event.player]}")
    if event.num_rolls == 0:
        print(f"  Dice: none -> BOAR BRAWL +{event.turn_points}")
    else:
        outcomes = " ".join(f"[{value}]" for value in event.outcomes)
        print(f"  Dice: {outcomes}")
        if 1 in event.outcomes:
            print("  SOW SAD -> a 1 was rolled; turn points reduced to 1.")
        else:
            print(f"  Turn points: +{event.turn_points}")
    ordinary_total = event.score_before + event.turn_points
    print(f"  Score: {event.score_before} + {event.turn_points} = {ordinary_total}")
    if event.bonus:
        print(f"  SUS FUSS -> {ordinary_total} becomes {event.score_after} (+{event.bonus} bonus)")
    totals = [event.score_after, event.opponent_score]
    if event.player == 1:
        totals.reverse()
    print(f"  SCOREBOARD / {names[0]} {totals[0]} : {totals[1]} {names[1]}")


def play_and_print(strategy0, strategy1, *, names=("Player 0", "Player 1"), dice=None):
    """Play a full game and print turn details and a match summary."""
    events = []

    def observe(event):
        events.append(event)
        print_turn(event, names)

    heading("MATCH", f"{names[0]} vs {names[1]} | First to {GOAL}")
    scores = play(strategy0, strategy1, sus_update,
                  dice=dice if dice is not None else six_sided, observer=observe)
    winner = 0 if scores[0] > scores[1] else 1
    heading("MATCH COMPLETE", f"{names[winner]} wins!")
    print(f"  Final score / {names[0]} {scores[0]} : {scores[1]} {names[1]}")
    print(f"  Turns played: {len(events)}")
    for player in (0, 1):
        turns = [event for event in events if event.player == player]
        sow_sad = sum(1 in event.outcomes for event in turns)
        zero_dice = sum(event.num_rolls == 0 for event in turns)
        bonuses = sum(event.bonus > 0 for event in turns)
        print(f"  {names[player]}: {len(turns)} turns | {sow_sad} Sow Sad | "
              f"{zero_dice} zero-dice | {bonuses} Sus Fuss")
    return scores


def play_with(num_players, *, names=("Player 0", "Player 1"),
              strategy0="always5", strategy1="always5", dice=None):
    """Play one game in mode 0, 1, or 2 with configurable computer players."""
    if type(num_players) is not int or num_players not in (0, 1, 2):
        raise ValueError("num_players must be 0, 1, or 2.")
    first = (interactive_strategy(0, names[0]) if num_players >= 1
             else STRATEGIES[strategy0][0])
    second = (interactive_strategy(1, names[1]) if num_players == 2
              else STRATEGIES[strategy1][0])
    return play_and_print(first, second, names=names, dice=dice)


def match_loop(num_players, names, strategy0, strategy1, dice, no_replay=False):
    while True:
        play_with(num_players, names=names, strategy0=strategy0,
                  strategy1=strategy1, dice=dice)
        if no_replay:
            return
        print("\n  [1] Play again with the same setup   [0] Finish")
        if get_int("  Choose: ", 0, 1) == 0:
            return


def setup_match(num_players, dice):
    heading("MATCH SETUP", "Enter q at any prompt to return to the menu.")
    default0 = "Player 0" if num_players else "Computer 0"
    default1 = "Player 1" if num_players == 2 else "Computer 1"
    names = (get_name("First player name", default0),
             get_name("Second player name", default1))
    strategy0 = choose_strategy("Choose Computer 0's strategy") if num_players == 0 else "always5"
    strategy1 = choose_strategy("Choose Computer 1's strategy") if num_players != 2 else "always5"
    match_loop(num_players, names, strategy0, strategy1, dice)


def menu(dice, seed=None):
    while True:
        heading("TERMINAL EDITION", "Roll with a plan. Race to 100.")
        print("  [1] Play against the computer")
        print("  [2] Two human players")
        print("  [3] Watch computer strategies compete")
        print("  [4] Strategy lab")
        print("  [5] How to play")
        print("  [6] Strategy guide")
        print("  [0] Exit")
        if seed is not None:
            print(f"\n  Session seed: {seed}")
        try:
            choice = get_int("\n  Choose [0-6]: ", 0, 6)
            if choice == 0:
                return
            if choice in (1, 2, 3):
                setup_match({1: 1, 2: 2, 3: 0}[choice], dice)
            elif choice == 4:
                from hog_experiments import run_experiments
                games = get_int("  Games per starting seat [1-10000]: ", 1, 10000)
                run_experiments(games=games, seed=seed)
            elif choice == 5:
                show_rules()
            elif choice == 6:
                show_strategies()
        except BackToMenu:
            print("\n  Returned from the current screen. Choose a new option or 0 to exit.")


def run(*args):
    parser = argparse.ArgumentParser(description="Hog - Improved Terminal Edition")
    parser.add_argument("-n", "--num_players", "--num-players", type=int,
                        choices=(0, 1, 2), help="skip menu: 0, 1, or 2 human players")
    parser.add_argument("--strategy0", choices=STRATEGIES, default="always5",
                        help="Player 0's strategy in computer-only mode")
    parser.add_argument("--strategy1", choices=STRATEGIES, default="always5",
                        help="Player 1's strategy when controlled by the computer")
    parser.add_argument("--name0", type=valid_name, default="Player 0")
    parser.add_argument("--name1", type=valid_name, default="Player 1")
    parser.add_argument("--seed", type=int, help="reproduce the session's dice sequence")
    parser.add_argument("--no-replay", action="store_true", help="finish after one direct-mode game")
    parser.add_argument("--version", action="version", version=VERSION)
    parsed = parser.parse_args(list(args) if args else None)
    if parsed.no_replay and parsed.num_players is None:
        parser.error("--no-replay requires -n / --num-players")
    dice = seeded_dice(parsed.seed)
    try:
        if parsed.num_players is None:
            menu(dice, parsed.seed)
        else:
            match_loop(parsed.num_players, (parsed.name0, parsed.name1),
                       parsed.strategy0, parsed.strategy1, dice, parsed.no_replay)
    except BackToMenu:
        pass
    except (EOFError, KeyboardInterrupt):
        print("\n  Input ended. The current session has been closed.")
    print("\n  Thanks for playing Hog.\n")


if __name__ == "__main__":
    run()
