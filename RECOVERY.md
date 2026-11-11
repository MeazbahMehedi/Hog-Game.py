# Progress and Recovery — v4.0.0

## Find your data

| OS | Folder |
| --- | --- |
| Windows | `%APPDATA%/Hog/` |
| macOS | `~/Library/Application Support/Hog/` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/Hog/` |

`settings.json` stores appearance, pace, accessibility, welcome completion and action keys. `hog.sqlite3` stores profiles, history, one manual save, tournaments, campaign attempts, equipment and archive membership. `backups/` receives automatic safety copies before portable restores. `last-error.log`, when present, contains the latest handled callback exception type and code locations.

The source folder and native installation folder are separate from progress. Updating or uninstalling the application does not intentionally remove these per-user files. Close all Hog windows before making a raw copy of the database.

## Make a portable backup

1. Open **Settings > Backup & recovery**.
2. Select **Export backup** and choose a `.hogbackup` destination.
3. Keep the file or copy it to another computer. The file includes local player names and recorded history.

The format is bounded JSON, not an executable archive or a raw SQLite import. It contains all profiles, standard history, the manual saved match, tournaments, completed campaign attempts, profile equipment, archive membership and preferences. It excludes unsaved live matches, incomplete campaign/practice runs, puzzle session counters and online rooms/credentials.

## Restore or undo a restore

1. Finish or leave the active standard match. Leave any reserved multiplayer seat through **Online > Leave room**; merely disconnecting keeps the seat reservation in the running app.
2. Open **Settings > Backup & recovery > Choose backup to preview**.
3. Wait for validation and review the record counts.
4. Select **Restore selected backup** and confirm replacement.
5. Read the status message for the automatic safety-copy path.

Validation runs in a worker against an isolated database. It checks the checksum, file/schema bounds, unique identities, profile references, standard scoring, exact saved RNG structure, fixed-seed campaign outcomes/rewards, earned equipment and tournament totals. It does not execute SQL or Python from a file. Tournament results are checked for internal consistency rather than re-simulated.

The file limit is 32 MiB and the per-collection record limit is 10,000. A checksum detects accidental file damage; it is not a signature. Only the v4 portable schema is supported. A release ZIP, CSV export, old raw database or arbitrary JSON file cannot be imported through this tool.

Restore replaces all local records; it never merges. A successful export of current data is required before SQLite's atomic database replacement. If safety-copy creation fails, replacement does not start. Preferences are applied after the database restore; if writing settings fails, the imported preferences remain active for the session and the status reports the write problem.

To undo, choose the relevant `backups/before-restore-<timestamp>.hogbackup` and repeat the preview/restore flow. Every successful restore makes another safety copy. The app does not rotate or delete these copies automatically.

## Settings are unreadable

Hog uses defaults and shows a dashboard notice. Reading does not modify the malformed file. Saving any preference, including welcome completion, replaces it with valid current settings. If you want to inspect the original, copy it before saving a setting. A failed settings write is shown in Settings; the current session can continue.

## Persistent storage could not open

The dashboard and player hub report temporary storage. This session can still be played and exported, but its database changes will not survive exit. Export before closing if there is progress to keep. Do not delete the existing database to dismiss the notice. Check folder permissions/free space or retain a copy and diagnose the file. A database from a future unsupported Hog version is rejected instead of downgraded.

## A UI action failed

The callback handler cancels main-match timers, stops sound and marks the local match paused. It shows a dialog and, when possible, overwrites `last-error.log` with the exception type and code locations. Messages, locals and network tokens are omitted. There is no automatic action retry. Review the table before using Resume, or return to the dashboard and export data.

The diagnostic is local and is not sent anywhere. It cannot recover a process crash, power loss, hard OS termination or arbitrary database corruption. Use manual save for a standard match you want to resume and portable backups for durable progress copies.

## Upgrade and downgrade

The first v4 launch on schema 1 or 2 saves `hog.sqlite3.v1-backup` or `hog.sqlite3.v2-backup`, if that file does not already exist. This uses SQLite's backup API before the transactional schema-3 upgrade. Existing backup files are never overwritten. A failed migration backup leaves the old database unmigrated and activates the temporary-store notice.

Close all Hog windows before raw database operations. Earlier releases reject schema 3; use the matching pre-upgrade backup for a downgrade. That older backup contains progress only through the upgrade time. Keep v4 portable backups separately so you can return to v4 later.

## Multiplayer connection recovery

Local backups cannot restore a multiplayer seat. A room token is kept only in the running client process; the server stores rooms in memory. Reopen Online in the same running app within the grace period to retry. An app/server restart is not cross-process recovery. See [ONLINE.md](ONLINE.md) for precise heartbeat, timer and reservation behavior.
