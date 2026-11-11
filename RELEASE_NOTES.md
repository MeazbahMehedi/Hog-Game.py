# GitHub Release Details

**Tag:** `v3.4.0`

**Title:** `v3.4.0 - Campaign and Customization Edition`

## Description

Follow a six-stage Hog campaign, earn objective stars, and customize your local player profile.

### What's new

- A clickable campaign map with sequential stage unlocks.
- Named opponents with distinct existing strategy behaviors.
- Three objectives per stage and persistent best stars per profile.
- A wardrobe with earned dice skins, Panda/Crown avatar presets and Aurora/Twilight themes.
- Campaign milestone progress bars.
- Validated seeded attempts and duplicate-run protection.
- Nine new screenshots, cumulative README/changelog and archived earlier documentation.

Campaign results remain separate from standard wins, history, statistics, tournaments and the manual save slot. Cosmetic changes never alter scoring dice. Only completed campaign attempts are saved; position-puzzle learning remains session-only.

### Database upgrade

The first launch against a schema-1 database creates `hog.sqlite3.v1-backup` if absent, then migrates transactionally to schema 2. Existing profiles, matches, tournaments and manual saves are preserved. Earlier releases cannot open schema 2; retain the backup before downgrading. Close the app before copying/restoring its data.

### Run

Extract and run `python hog_desktop.py` with Python 3.10+ and Tkinter. A rebuilt Linux x86_64 package is included. Windows users can play from source or build locally with `build-windows.bat`; no prebuilt Windows executable is included.

### Validation

207 automated checks and 18 doctest examples passed on Linux. Coverage includes all six three-star completion paths, migration/backup failures, persistence, profile isolation, locked rewards, seeded validation and unchanged standard saves/RNG. The Linux executable passed version and actual-window smoke checks. Windows/macOS native execution and physical audio were not verified.

Online multiplayer and the final polish release remain future work.
