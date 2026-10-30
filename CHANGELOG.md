# Changelog

All versions retain the Sow Sad, Boar Brawl, and Sus Fuss game rules.

## v1.2.0 - Graphical Desktop Edition - 2026-10-28

### Added

- Tkinter desktop home screen with solo, local two-human, and watch modes.
- Player naming, mode switching, strategy selectors, and optional seed setup.
- Actual-outcome canvas dice, clickable 0-10 controls, and Enter-to-confirm.
- Live score panels, progress bars, turn indicators, and zero-dice preview.
- Scoring explanations and a scrollable journal of completed turns.
- Winner screen, per-player statistics, replay, new setup, and final-table review.
- Rules window and confirmation before leaving an unfinished match.
- Incremental `GameSession` and validated display-independent `MatchConfig`.
- 16 additional automated tests, bringing the full suite to 55 tests.
- Six actual desktop screenshots, a capture utility, and archived v1.1.0 documentation.

### Changed

- `play` now advances `GameSession`, sharing scoring with the desktop interface.
- Computer turns use cancellable Tk timers instead of blocking UI loops.
- The terminal capture tool uses current-version filenames and preserves historical captures.
- The desktop supports windows down to 1040x720 and adapts initial height to the display.

### Preserved

- Terminal menus, CLI flags, strategy experiments, original function names,
  all three scoring rules, and the adaptive strategy's original decision order.
- Original `dice.py` and `ucb.py` support files.

### Scope

- Desktop replay restarts a fixed seed; terminal replay continues its session stream.
- No animations, sound, theme switching, persistent profiles, or saved games yet.

## v1.1.0 - Improved Terminal Edition - 2026-10-28

### Added

- Main menu, rules screen, and strategy guide.
- Player naming and selection among six computer strategies.
- Turn explanations, scoreboard, zero-dice preview, and match summary.
- Replay with the same player and strategy configuration.
- Independent seeded dice for reproducible sessions and experiments.
- A working experiment runner with roll-count estimates, equal seat counts,
  separate seat results, and approximate pooled Wilson intervals.
- Optional immutable turn events for interfaces.
- 39 automated tests and passing executable documentation examples.
- Current and legacy terminal captures, source transcripts, validation notes,
  GitHub release notes, and cumulative README history.

### Changed

- Launching `hog_ui.py` without flags now opens a menu; `-n 0` still starts
  an automatic game.
- Invalid game and sampling inputs raise `ValueError` instead of relying on
  assertions that disappear under Python's optimized mode.
- Factor and prime checks stop at the integer square root.
- `average_win_rate` accepts an optional `times_called` argument.
- The reusable simulator supports a keyword-only observer and does not print.

### Fixed

- `--run_experiments` previously accepted a flag without running anything.
- Removed the duplicate `winner` function definition.
- Corrected malformed indentation in the original `catch_up` doctest.
- Numbers below 2 are no longer reported as prime.
- Terminal integer input no longer uses an unsafe `isnumeric()` conversion.

### Preserved

- The original public game and strategy function names and positional
  simulator arguments, all three scoring rules, and the adaptive decision order.
- Original `dice.py` and `ucb.py` starter code.

## v1.0.0 - Original Project Baseline

The uploaded coursework solution is labeled v1.0.0 for project history.

- Implemented dice scoring, zero-dice scoring, factor counting, prime bonuses,
  full-game simulation, and higher-order strategy functions.
- Included always-roll, catch-up, Boar Brawl, Sus Fuss, and custom adaptive strategies.
- Supported automatic, one-human, and two-human games through the starter UI.
- Had no main menu, custom player labels, replay, or match summary.
- The experiment command-line flag was present but unfinished.

## Planned After Approval

- v2.0.0: animation and presentation improvements.
- v2.1.0: stronger opponents and move advice.
- v2.2.0: profiles, history, and tournaments.
- v3.0.0: final showcase edition.

These versions are a roadmap and are not part of the v1.2.0 package.
