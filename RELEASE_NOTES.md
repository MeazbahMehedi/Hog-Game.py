# GitHub Release Details

**Tag:** `v2.2.0`

**Title:** `v2.2.0 - Profiles and Tournament Edition`

## Description

Hog now includes local player profiles, persistent statistics, six achievement milestones, match history, a local leaderboard, manual save/resume, and seeded computer tournaments with charts and CSV export.

Saved matches retain the exact future dice sequence, including unseeded games. SQLite transactions and match IDs prevent double-counting results. Guest matches and tournaments do not alter human profile standings.

All earlier rules, opponents, move advice, animations, themes, optional audio, and terminal tools remain included. The updated README documents current screenshots, previous versions, controls, local data, and limitations.

Extract and run `python hog_desktop.py`. Requires Python 3.10+, Tkinter, and a graphical desktop; no third-party Python packages are needed to play.

Verified: 110 automated checks and 18 documentation examples. The final showcase edition, v3.0.0, is planned next.
