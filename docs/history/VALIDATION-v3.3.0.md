# v3.3.0 Validation

2026-10-29. Source: Linux / Python 3.12.14 / Tk 9.0 with a virtual display.

177 automated checks passed with graphical tests enabled. All 18 doctest examples passed. The 21 additional checks cover existing-policy agreement, guaranteed and fractional immediate finish probabilities, all legal ties, the eight puzzle positions, invalid input, assumptions/objectives, both players' pre-roll positions, outcome-independent values, read-only/tamper behavior, live coach isolation, review filters/sorting, puzzle retries/reveals/session progress, pending callback cancellation, saved-slot/live RNG preservation, minimum popup controls, and unique match selection.

Nine current screenshots capture actual Tk 8.6 windows. Seeded example records and profiles exist only in memory during capture. No demonstration database or personal gameplay data is included.

The native Linux x86_64 package was rebuilt with Python 3.12.3, Tk 8.6, PyInstaller 6.22.3 and glibc 2.39. The executable passed version (3.3.0) and actual-window smoke checks. A clean extracted ZIP passed archive integrity, relative Markdown-link checks, all source launcher version checks, doctests, and the native smoke launch. Windows/macOS native execution, older glibc compatibility and physical audio were not verified.

The coach evaluates the standard optimal-play model, not the actual heuristic opponent. Review gaps are pre-roll decision metrics, not hindsight judgments or additive loss probabilities. Puzzle ties use a 1e-9 probability tolerance. Attempt counts include retries; revealed answers do not unlock unassisted solves. Learning progress resets at application exit and is not stored in profile statistics.

No database migration, scoring-rule change, save mutation, new runtime dependency, network request, or new gameplay random-number call is introduced by the learning views.
