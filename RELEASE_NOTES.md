# GitHub Release Details

**Tag:** `v3.2.0`

**Title:** `v3.2.0 - Statistics and Replay Edition`

## Description

Understand your Hog games with a new statistics workspace and an interactive match replay timeline.

### What's new

- Profile-specific statistics and explicit all-recorded-seat filtering.
- Dice-choice charts, rule counts, average turn gains, and per-opponent win rates.
- Personal records for scores, turn gains, bonuses, winning margins, and win streaks.
- Replay score progression charts with click-to-seek and a draggable timeline.
- Playback speeds from 0.5× to 4×, milestone jumps, and factual turn explanations.
- Validated read-only analysis with invalid-record exclusion notices.
- Eight new screenshots, cumulative README/changelog, and archived previous documentation.

All previous desktop and terminal features remain available. No scoring rules or database schema changed. Statistics use completed standard desktop games; practice and tournament results stay separate. Replay never rolls new dice or modifies history.

### Run

Extract the ZIP and run `python hog_desktop.py` with Python 3.10+ and Tkinter. A rebuilt Linux x86_64 package is included. Windows users can play from source or build locally with `build-windows.bat`; a Windows executable is not included.

### Validation

156 automated checks and 18 doctest examples passed on Linux. Timed playback, seeking, profile filters, record validation, theme redraws, and storage/RNG isolation are covered. The rebuilt Linux executable passed version and actual-window smoke checks. Windows/macOS native execution and physical audio were not verified.

AI coaching, campaign progression, and online multiplayer remain future releases.
