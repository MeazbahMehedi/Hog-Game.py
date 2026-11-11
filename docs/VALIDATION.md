# v4.0.0 Validation

2026-10-29. Linux / Python 3.12.3 / Tk 8.6 on a virtual display.

The final full source suite passed **270 tests**, with all graphical test classes enabled (no GUI skips), in 24.958 seconds. All **18 doctest examples** passed. The original engine, CLI, animation, probability, save/resume, statistics, coaching, campaign and HTTP/TLS multiplayer checks remain included.

The 34 added tests cover profile identity retention on rename, archive/restore and historical statistics access; schema-2 migration backup; complete portable-data round trips; exact future saved dice outcomes; restore safety copies; export/write failure preservation; checksum, duplicate, missing-reference, scoring, campaign-reward, unearned-cosmetic, tournament-total and size/format rejection; legacy/current preferences; conflicting/invalid shortcuts; remapped single-roll behavior; live shortcut labels; focused Enter without a second roll; entry editing; welcome completion/reopening; confirmed restore; active-game restore blocking; abandoned background-validation cleanup; limited callback diagnostics; and Linux installer ownership, quoted paths, upgrades and removal.

Portable backups use a consistent SQLite read snapshot for export. Import validation builds an isolated database on a worker; ownership transfers after completion with no concurrent connection access. Only the Tk thread modifies the live game store. Closing a view disposes pending validation results. A successful safety export is required before SQLite's atomic backup copy replaces live data. Preferences are a separate settings write, and a failed write is reported after the database restore rather than claiming the two files form one atomic transaction.

A full backup test retains standard matches, the manual saved game, tournament records, two legitimate three-star campaign completions, earned equipment and archive membership. Invalid fixtures are modified and re-checksummed to verify that semantic checks, rather than just the checksum, reject them. Tournament results are checked for internal consistency, not re-simulated during import.

The retained real two-client network smoke tool completed a goal round and an alternating-seat rematch. Retained HTTPS tests verify rejection of an untrusted test certificate and acceptance with explicit trust; no private keys/certificates are shipped. No public internet/NAT deployment was tested.

Ten new screenshots capture actual Tk 8.6 windows with temporary demonstration profiles/matches/campaign data: dashboard, welcome, rules-tour step, controls, profile manager, validated backup preview, settings, standard game, compact layout and high contrast. Images were visually inspected. No personal database, actual user progress or online credentials are included.

The Linux x86-64 native client was rebuilt with Python 3.12.3, Tk 8.6, PyInstaller 6.22.3 and glibc 2.39. Its version was 4.0.0. Real-window native startup passed. An isolated per-user installation with spaces in its path passed install, installed version/startup, upgrade and uninstall checks, preserving an unrelated progress marker. The clean extracted ZIP also passed integrity, relative Markdown-link checks, all four source launcher versions, doctests, network smoke and native startup.

Windows and macOS native builds/installers were not executed. Inno Setup and DMG recipes plus a manual three-platform GitHub Actions workflow are supplied for target-machine validation. That workflow was not run or published from this environment. No signing/notarization, public relay deployment, physical audio check, screen-reader certification or compatibility with older glibc is claimed. GUI tests skip without a display; review skip counts when running elsewhere.

Schema-1/schema-2 data migration creates a matching backup before schema 3, preserving existing backup files. Standard saved-match JSON remains schema 1. Portable backups are a separate v4 format; raw SQLite files and previous release ZIPs are not portable-import inputs.
