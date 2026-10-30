# GitHub Release Details

**Tag:** `v1.2.0`

**Title:** `v1.2.0 - Graphical Desktop Edition`



Hog now has a complete **graphical desktop interface** built with Tkinter.
This release builds on v1.1.0 while retaining its terminal game and strategy lab.

## What's New

- Desktop home screen with human vs computer, local two-player, and watch modes.
- Player names, six selectable computer strategies, and optional random seeds.
- Graphical dice showing actual outcomes, with rolled ones highlighted.
- Clickable 0-10 controls, Enter-to-confirm, active-player panels, and score bars.
- Zero-dice point previews and explanations of Sow Sad, Boar Brawl, and Sus Fuss.
- Scrollable match journal and a rules window.
- Winner screen with final scores and per-player statistics.
- Replay, new setup, and final-table review.
- Shared incremental engine keeping terminal and desktop scores consistent.
- Updated README with real desktop screenshots, previous-version history,
  archived v1.1.0 documentation, and cumulative changelog.

## Start Playing

Extract `hog-v1.2.0.zip`, open its project folder, and run:

```bash
python hog_desktop.py
```

Requires Python 3.10+, Tkinter, and a graphical desktop. No third-party Python
packages are needed to play. The terminal edition remains available:

```bash
python hog_ui.py
```

## Validation

- All 55 automated checks pass with a graphical display available.
- 18 executable documentation examples pass.
- Verified on Linux with Python 3.12.14 / Tk 9.0 and Python 3.12.3 / Tk 8.6.
- Tests include real window interactions, computer timers, mode switching,
  replay, rules, final-table review, and scoring consistency.

This version uses immediate dice results and a fixed dark palette.
Animation, sound, and selectable themes are planned for v2.0.0.
