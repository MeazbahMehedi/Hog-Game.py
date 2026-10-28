# GitHub Release Details

**Tag:** `v1.1.0`

**Title:** `v1.1.0 - Improved Terminal Edition`



The first upgrade to **The Game of Hog**, building on the original Python
Programming project with a complete terminal experience.

## What's New

- Main menu with human vs computer, two-player, and computer-only modes.
- Custom player names and six selectable computer strategies.
- Clear dice output, rule explanations, scoreboard, and zero-dice point preview.
- Match summaries and replay without restarting the program.
- Working strategy experiments with reproducible seeds and results for both
  starting positions.
- Refactored engine with turn events, faster number checks, safer inputs,
  and the original adaptive strategy preserved.
- Updated README, cumulative changelog, terminal captures, and 39 automated tests.

## Start Playing

Download and extract `hog-v1.1.0.zip`, open its project folder, and run:

```bash
python hog_ui.py
```

Requires Python 3.10 or newer. The game needs no additional packages.

## Try the Strategy Lab

```bash
python hog.py -r --games 100 --samples 500 --seed 42
```

## Validation

- All 39 unit and command-line tests pass.
- Executable documentation examples pass.
- Verified on Python 3.12.14 / Linux.

This release uses a terminal interface. The graphical desktop edition is the
next planned upgrade. See the README for the original v1.0.0 history, current
terminal captures, controls, and complete usage instructions.
