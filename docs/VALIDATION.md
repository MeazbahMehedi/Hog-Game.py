# v3.2.0 Validation

2026-10-29. Source suite: Linux / Python 3.12.14 / Tk 9.0, using a virtual display.

156 automated checks passed with all graphical classes enabled. All 18 doctest examples passed. The 21 new checks cover both-seat accounting, identity-based profile filtering, computer/human opponent grouping, chronological win streaks, dice frequencies, scoring milestones, turn explanations, corrupt/legacy/duplicate records, chart-click bounds, active-profile defaults, empty states, actual timed replay playback, speed changes, seeking, restart-at-end, closure, minimum popup layout, theme redraws, and unchanged storage/live RNG.

After the final presentation adjustments, the 21 insights checks were rerun successfully. Existing tests continue to cover simulator equivalence, save/resume RNG state, transaction deduplication, AI policies, practice isolation, tutorials, animation, and terminal controls.

Eight current screenshots capture actual Tk 8.6 windows with seeded completed matches and temporary in-memory profiles. They are not generated mockups or measured strategy benchmarks. The supplied release contains no example SQLite database.

The Linux x86_64 package was rebuilt with Python 3.12.3, Tk 8.6, PyInstaller 6.22.3 and glibc 2.39. Its version is 3.2.0; version and actual-window smoke checks passed. The clean extracted ZIP passed integrity, relative Markdown-link, source launcher version, and native smoke checks. Older glibc compatibility, Windows/macOS native execution, and physical audio were not verified.

SQLite schema 1 and existing data locations remain unchanged. Statistics validate all completed desktop records, while replay offers the latest 100 stored records. Both are read-only snapshots. All-seat win rate is explicitly labeled as 50% by construction, and personal streaks require one profile. No historical record is repaired, deleted, or inferred during analysis.
