# GitHub Release Details

**Tag:** `v3.1.0`

**Title:** `v3.1.0 - Dashboard Edition`

## Description

Hog gets a redesigned dashboard and match table, with clearer navigation and scoring feedback.

### What's new

- Dashboard navigation, activity totals, player cards, and recent match summaries.
- Name-initial avatars and helpful empty states for new players.
- Clearer score cards and separate turn points, Sus Fuss bonus, and resulting score.
- Dice-choice previews with Sow Sad risk and guaranteed zero-dice gain.
- Collapsible, highlighted match journal.
- Adaptive layouts for smaller windows and a motion-aware active-turn pulse.
- Updated README, eight real screenshots, cumulative changelog, and archived earlier documentation.

All previous game rules, nine strategies, profiles, achievements, tournaments, save/resume, tutorials, practice, replay viewer, themes, accessibility, and terminal tools remain available. Existing local data is compatible without a schema migration.

### Run

Extract the ZIP and run `python hog_desktop.py`. Python 3.10+ and Tkinter are required. A rebuilt Linux x86_64 one-folder package is included. Windows users can play from source or build locally using `build-windows.bat`; a Windows executable is not included.

### Validation

135 automated checks and 18 doctest examples passed on Linux. The rebuilt Linux executable passed version and real-window smoke checks. Windows/macOS native execution and physical audio were not verified.

Later roadmap features, including statistics charts, coaching, campaigns, and online multiplayer, are not part of this release.
