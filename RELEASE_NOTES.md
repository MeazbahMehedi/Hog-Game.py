# GitHub Release Details

**Tag:** `v4.0.0`

**Title:** `v4.0.0 - Complete Desktop Edition`

## Description

Hog v4.0.0 completes the six-release improvement cycle with a more approachable interface and portable progress tools.

### What's new

- Four-step welcome tour with rules, controls, modes and progress guidance.
- Nine remappable action keys, conflict checking, saved defaults and updated button hints.
- Keyboard focus navigation and Enter activation of the selected button.
- Profile rename, archive and restore while retaining statistics and campaign rewards.
- Portable backups with background validation and record-count previews.
- Confirmed restore with a required automatic safety copy of current data.
- Unreadable-settings notices and callback-error pause with limited local diagnostics.
- Linux install/uninstall, Windows installer recipe, macOS disk-image builder and a manual build workflow.
- Ten current screenshots, cumulative README, recovery guide and archived v3.5.0 documentation.

All previous gameplay remains: nine computer strategies, six campaign stages, cosmetics, move coaching, puzzles, statistics, interactive replays, tournaments and private multiplayer. The original Hog scoring rules are preserved.

### Start

Run `python hog_desktop.py`. In PyCharm, run that file with a Tk-enabled Python 3.10+ interpreter. For private multiplayer, also start `python hog_server.py` separately and follow ONLINE.md.

### Backups and compatibility

Settings > Backup & recovery exports local progress. Preview validates the selected file before restore replaces data; it does not merge. Restore creates a safety copy first. Schema-1/schema-2 databases are backed up before migration to schema 3. Existing manual saves and settings remain supported. Earlier releases need the matching old database backup to downgrade.

### Validation and platform scope

270 automated tests and 18 doctest examples passed on Linux with real Tk windows enabled. The rebuilt Linux client passed native startup and isolated install/launch/upgrade/uninstall checks. Real HTTP/TLS multiplayer tests are retained. Windows/macOS recipes and CI are included, but their native builds were not executed here; no prebuilt Windows/macOS installer is attached. Signing, notarization, public relay hosting and external publication are not configured.

Attach `hog-v4.0.0.zip` to this release. The ZIP includes the full project, current documentation, historical screenshots and a Linux native client.
