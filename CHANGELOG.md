# Changelog

All versions retain the Sow Sad, Boar Brawl, and Sus Fuss game rules.

## v3.3.0 - Coaching and Challenges Edition - 2026-10-29

- Added a learning hub with live coaching, completed-match decision review, and eight position puzzles.
- Expanded live advice into an 11-move comparison with expected gains, model win chances, Sow Sad risks and immediate finish probabilities.
- Added numeric, rule-based explanations and guaranteed-finish opportunity notes.
- Added worker-based pre-roll reviews with seat filters, gap sorting, learning labels and actual outcomes shown separately.
- Added tie-aware puzzle checking, retry hints, solution reveals, attempt counts and session-only unassisted solve progress.
- Added result/replay review links and two-row dashboard navigation in compact windows.
- Fixed ambiguous match selectors with numbered labels and added scrollable comparison views.
- Kept schema 1, data paths, saves, original scoring rules and standard-library source play.
- Added 21 tests for a total of 177 checks, plus 18 doctest examples.
- Added nine actual screenshots, cumulative documentation, and a rebuilt/tested Linux package.

## v3.2.0 - Statistics and Replay Edition - 2026-10-29

- Added a statistics workspace with profile identity filters and explicit all-seat scope.
- Added observed dice-choice frequencies, rule counts, mean turn gains, and per-opponent results.
- Added final-score, turn-gain, bonus, margin, and winning-streak records.
- Added replay score charts, timeline scrubbing, chart-click seeking, and milestone jumps.
- Added 0.5×/1×/2×/4× playback with visible Play/Pause state and timer cleanup.
- Added factual scoring explanations from recorded outcomes, without AI move judgments.
- Added validated record reading with duplicate-ID protection and invalid-record exclusion counts.
- Split shared vector dice, charts, statistics, and analysis-window presentation into focused modules.
- Kept schema 1, prior save/settings compatibility, original rules, and standard-library source play.
- Added 21 tests, bringing the suite to 156 checks plus 18 doctest examples.
- Captured eight real current screenshots and rebuilt/tested the Linux desktop package.

## v3.1.0 - Dashboard Edition - 2026-10-29

- Replaced the home menu with a scrollable dashboard, navigation rail/strip, real activity totals, recent results, and local player cards.
- Added name-initial avatars, helpful fresh-installation states, and quick access to retained features.
- Added separate turn-point, Sus Fuss, and resulting-score cells.
- Added selected-roll Sow Sad risk and exact zero-dice gain previews.
- Added journal show/hide controls and highlighted scoring-rule entries.
- Added adaptive dashboard/game layouts with a 960 × 720 standard-text minimum.
- Added an independent cosmetic turn pulse that respects pause and reduced motion.
- Kept schema 1 and existing data compatibility; no new runtime dependency.
- Added 13 tests, bringing the suite to 135, plus 18 doctest examples.
- Captured eight actual current-version screenshots and rebuilt/tested the Linux bundle.

## v3.0.0 - Showcase Edition - 2026-10-29

- Added four interactive tutorial exercises backed by real scoring functions.
- Added validated read-only match replay with first/previous/play/pause/next/last controls.
- Added practice goals, starting scores, seeds, opponent choice, and optional Sus Fuss.
- Isolated practice from profiles, saves, history, and optimal-policy advice.
- Added a high-contrast palette, larger label/control text, and an accessibility panel.
- Added a tested Linux x86_64 one-folder build, optional packaging requirements, and Windows/native build scripts.
- Added an in-memory desktop smoke-test command and installation guide.
- Expanded the suite to 122 checks; preserved previous release documentation and screenshots.
- Completed all six planned upgrades from the original coursework baseline.

## v2.2.0 - Profiles and Tournament Edition - 2026-10-29

- Added local profiles, human-seat assignment, persistent statistics, six achievements, and leaderboard.
- Added deduplicated desktop match history and CSV export with formula-prefix escaping.
- Added a manual save slot with validated JSON turn data and exact dice-generator state.
- Resume starts paused; an unfinished visual roll returns to the completed-turn boundary.
- Added seeded equal-seat computer round robins, charts, persisted results, and CSV export.
- SQLite transactions prevent duplicate statistics; guest and tournament records stay separate from profile totals.
- Added 16 checks, bringing the full suite to 110; preserved earlier documentation and screenshots.

## v2.1.0 - Smart Opponent Edition - 2026-10-29

- Added Easy (five dice), Medium (expected-gain), and Hard (optimal-policy) opponents.
- Added exact dice distributions and a dynamic-programming policy for all 10,000 active score pairs.
- Added optional move advice with all legal choices, expected gains, Sow Sad risks, and model win chances.
- Added a background graphical comparison lab with equal-seat matches and Wilson intervals.
- Preserved original strategies, scoring, animations, themes, sound, settings, and terminal modes.
- Added 12 regression checks; full suite now 94 checks. Archived v2.0.0 documentation and screenshots.
- Included a reproducible benchmark; model probabilities and sampled results are labeled separately.

## v2.0.0 - Animated Game Edition - 2026-10-29

- Added rotating/bouncing dice previews using independent cosmetic randomness.
- Added live light/dark themes, pause/resume, confirmed restart, and keyboard controls.
- Added reduced motion, optional WAV audio, computer pace, and atomically saved preferences.
- Settings pause running matches and restore their prior pause state.
- Added original generated WAV assets and graceful missing-audio fallback.
- Expanded verification to 82 checks and preserved prior README files and captures.
- Scoring, original strategies, terminal modes, and experiments remain unchanged.

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

## Release Plan Complete

All six planned upgrades have been delivered.
