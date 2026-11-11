# GitHub Release Details

**Tag:** `v3.3.0`

**Title:** `v3.3.0 - Coaching and Challenges Edition`

## Description

Learn from your Hog decisions with an expanded offline coach, post-match analysis, and eight position puzzles.

### What's new

- Compare all dice choices by expected gain, model win chance, Sow Sad risk and immediate finish probability.
- Read explanations for considered moves, zero-dice options, numerical ties and guaranteed finish opportunities.
- Review completed matches from each player's pre-roll perspective, with seat filters and model-gap sorting.
- Solve eight puzzles with retries, tie-aware checking, solution reveals, and session learning progress.
- Open reviews directly from replay and result screens.
- Use compact two-row navigation and unique numbered match selectors.
- Updated README, nine actual screenshots, archived previous documentation, and cumulative changelog.

The coach uses the existing exact fair-dice policy under standard rules and optimal continuation by both players. It is not an LLM, a prediction of the next roll, or a measured win rate against a selected opponent. Puzzle progress lasts for the app session; no learning view changes profile results, history, saves, or scoring dice.

### Run

Extract the ZIP and run `python hog_desktop.py` with Python 3.10+ and Tkinter. A rebuilt Linux x86_64 one-folder package is included. Windows users can play from source or build locally with `build-windows.bat`; no prebuilt Windows executable is included.

### Validation

177 automated checks and 18 doctest examples passed on Linux. The rebuilt Linux executable passed version and actual-window smoke checks. Windows/macOS native execution and physical audio were not verified.

Persistent campaigns, unlockable cosmetics, and online multiplayer remain future releases.
