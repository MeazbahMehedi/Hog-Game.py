# v3.1.0 Validation

2026-10-29. Source suite: Linux / Python 3.12.14 / Tk 9.0 with a virtual display.

135 automated checks passed, with no skipped graphical classes. All 18 doctest examples passed. The 13 additional checks cover Unicode/name initials, bonus/base separation, zero-dice labels, unreadable summary handling, real dashboard totals, navigation reflow, journal resize/manual choice, recorded-history preservation, risk previews, scoring breakdowns, cosmetic RNG isolation, timer cleanup, and compact control bounds across all three themes.

The existing suite also covers seeded simulator equivalence, animated turns, pause/restart, saved RNG state, profile deduplication, tutorials, practice isolation, read-only replays, AI policies, and tournaments.

Eight current screenshots capture real Tk 8.6 windows on a Linux virtual display. Example profiles/results are seeded in-memory data; no demo SQLite database is shipped. The compact dashboard scrolls to reach its lower cards. Larger text and a manually opened journal may require more window space.

Native build: Linux x86_64, Python 3.12.3, Tk 8.6, PyInstaller 6.22.3, glibc 2.39. The rebuilt executable passed `--version` (3.1.0) and an actual-window `--smoke-test` using temporary data. A clean extracted archive was checked for integrity, relative documentation links, source launcher versions, and native smoke startup. Windows/macOS native execution and physical audio were not verified.

No scoring rule, optimal-policy assumption, persistence schema, or data location changed. UI summaries and turn pulses do not consume scoring dice. Historical README/validation documents describe their own versions.
