# The Game of Hog

**v2.2.0 · Profiles and Tournament Edition · Python 3.10+ / Tkinter**

This release adds local player profiles, persistent statistics, achievements, match history, exact save/resume, leaderboards, and round-robin computer tournaments. All previous game modes, opponents, move advice, animations, themes, sound, and terminal tools remain included.

![Profiles and Tournament Edition](docs/screenshots/v2.2.0-home.png)

## What's New in v2.2.0

- Local profiles with case-insensitive unique names; no online account or password.
- Attach a profile to each human seat in Match setup, or play as a guest.
- Persistent matches played, wins, losses, best score, zero-dice turns, and prime bonuses.
- Six achievement milestones derived from completed profile matches.
- Desktop match history, a local profile leaderboard, and history CSV export.
- One manual save slot, retaining configuration, completed turns, profile identities, and exact future dice state.
- Resuming opens the match paused; press P to continue. Unfinished animations return to the last completed-turn boundary.
- Seeded computer round robins with equal starting seats, standings charts, persistent tournament results, and match-level CSV export.
- SQLite transactions and unique match IDs prevent replaying a result screen from double-counting wins.

### Create and Use Profiles

Open **Player hub** from Home, enter a name, and select **Create profile**. In Match setup, choose that profile for a human seat. Selecting it fills the display name; you may still customize the displayed name without changing the profile identity. A profile cannot occupy both seats, and computers cannot use human profiles.

![Profile assignment](docs/screenshots/v2.2.0-profile-setup.png)

Guest desktop matches enter history but do not create profile statistics. The original terminal game is deliberately separate and does not write to the desktop database. Computer tournaments also keep separate standings rather than changing human statistics.

![Profiles and achievements](docs/screenshots/v2.2.0-hub.png)

| Achievement | Unlock condition |
| --- | --- |
| First finish | Complete one profile match. |
| First victory | Win one profile match. |
| Five victories | Win five profile matches. |
| Ten matches | Complete ten profile matches. |
| Free points | Complete a match containing at least one zero-dice turn for that profile. |
| Prime time | Complete a match containing at least one Sus Fuss bonus for that profile. |

The leaderboard sorts profiles by wins, then matches played, then name. It is a local activity ranking, not an online rating or an Elo estimate.

![Local leaderboard](docs/screenshots/v2.2.0-leaderboard.png)

### Match History and CSV

The Player hub's **Match history** tab shows the latest 100 completed desktop matches. The CSV export includes all stored matches, one row per player, with UTC finish time, match ID, seat, name, score, win flag, turns, and scoring-rule counts. Spreadsheet formula prefixes in display names are escaped on export.

![Match history](docs/screenshots/v2.2.0-history.png)

### Save and Resume

Click **Save** during an unfinished desktop match. The match pauses and the latest save slot is replaced. Saving is manual; closing an unsaved game does not automatically save it. From Home, click **Resume saved**. The match reopens paused with the same scores, journal, player to move, identities, and future dice sequence, even when the original game had no seed.

If saved during a roll preview, only completed turns are stored. No scoring dice were consumed by that preview, so resuming at the turn boundary preserves the future result. Finishing that match clears its own save slot; finishing a different match does not clear another saved match.

![Resumed match](docs/screenshots/v2.2.0-resume.png)

A desktop replay starts a new match ID and, if set, restarts its seed. Resume keeps the old match ID and generator state. Completed matches are deduplicated by ID before statistics are updated.

### Computer Tournaments

Open **Tournaments** from Home. Select 2-9 distinct strategies, 1-200 games per starting seat, and an integer seed. Each pair plays the same number of games in both seat orders. A five-strategy tournament with 10 games per seat runs 200 matches, with 80 appearances per strategy.

![Round-robin tournament](docs/screenshots/v2.2.0-tournament.png)

Standings sort by wins, then total point difference, then strategy name. Bars show observed win rates over the selected opponents. These sampled results do not guarantee future performance. The tournament runs in a worker; keep its window open until results appear to save that run. The dropdown reopens previously saved tournament results. **Export tournament CSV** writes one row per game, with player strategies, scores, and winner.

### Local Data and Backups

The normal desktop launcher stores `hog.sqlite3` beside `settings.json` in the platform's Hog configuration directory listed below. The database holds profiles, completed desktop matches, one save slot, and tournament results. There is no cloud synchronization or telemetry. Close the app before copying this database for backup or transfer. A clean release ZIP contains no personal database or demo profiles.

If the database cannot be opened, the app shows a notice in Player hub and uses temporary in-memory storage for that session; existing data is not replaced. Save and history failures are reported without changing game rules. Profiles currently cannot be renamed or deleted through the interface.

## Retained from v2.1.0

- **Easy:** a fixed five-dice opponent for practice.
- **Medium:** maximizes exact expected score gain, including Sus Fuss; takes a guaranteed zero-dice win.
- **Hard:** chooses the move with the best model probability of winning the complete match against an optimal opponent.
- **Move advisor:** click **Move advice / H** during a human turn. See every legal move, expected gain, Sow Sad risk, and model win chance. Advice never plays your move.
- **Strategy comparison:** open from Home, choose a baseline and games per starting seat, then run real matches in a background worker. Bars show measured win rates; gold lines show approximate 95% Wilson intervals.
- Policy preparation and comparisons run outside Tk callbacks. The worker never touches widgets.
- Original six strategies remain; all nine are selectable in desktop and terminal modes.

![Optional move advice](docs/screenshots/v2.1.0-advisor.png)

The advisor displays a snapshot of the position shown at the top. It is requested explicitly, rather than shown automatically during ordinary play. If you continue playing with the window open, request fresh advice for the new position.

![Measured comparisons](docs/screenshots/v2.1.0-comparison.png)

### How the Hard Opponent Works

This edition uses exact finite-state probability calculations rather than noisy Monte Carlo move estimates. For each roll count, the program counts every possible non-one sum and includes the probability of Sow Sad. Zero dice is deterministic. Sus Fuss is applied to every possible resulting score.

The policy solves 10,000 active score pairs in descending total-score order. Every turn increases a score, so the dependency graph is acyclic. It selects the action maximizing `sum(P(outcome) * (1 - opponent_value(next_state)))`, treating a winning turn as value 1. Near ties favor fewer dice.

**Assumptions:** fair six-sided dice, the three original rules, goal 100, and optimal play by both players after the considered move. The displayed model chance is not a prediction of the next roll or a measured win rate against the selected opponent. No trained model, API, GPU, or network connection is involved.

Medium optimizes immediate points; Hard optimizes winning the match. Difficulty labels are not a guarantee of monotonically increasing empirical win rates against every heuristic.

### Measured Benchmark

An included run used 100 games per starting seat, seed 42, and the original adaptive strategy as baseline. Hard won **112/200 (56.0%)**, with an approximate 95% Wilson interval of **49.1%-62.7%**. Medium won 95/200 (47.5%). These are sampled results with overlapping uncertainty, not proof of superiority in every matchup. Full counts and intervals are in [benchmark.json](docs/benchmark.json).

The comparison screen evaluates six named candidates, including Easy and its identical five-dice baseline, against any of the nine strategies. It resets the same seed for each candidate, so runs are reproducible. `--games` in the terminal experiment lab still evaluates all nine available strategies.

## Start

Extract the ZIP, open the project folder, and run:

```bash
python hog_desktop.py
```

Python 3.10+, Tkinter, and a graphical desktop are required. No third-party Python packages are required to play. On Windows, `py -3 hog_desktop.py` also works. On Linux, Tk support may require `python3-tk`. Check with `python -m tkinter`.

## Retained from v2.0.0

- Dice roll previews rotate and bounce before the actual result is resolved once.
- Animation uses independent randomness and never alters seeded scoring outcomes.
- Switch between dark and light themes without resetting a match or setup fields.
- Pause freezes computer turns and an in-progress animation; resume continues it.
- Restart confirms before resetting scores and cancels pending callbacks.
- Settings automatically pause a running match, then restore its previous state.
- Reduced-motion mode resolves turns immediately.
- Optional original WAV effects for rolling, Sow Sad, bonuses, and wins.
- Relaxed, normal, and fast computer pacing.
- Display preferences are saved atomically outside the source folder.

![Light theme](docs/screenshots/v2.0.0-light.png)

![Settings](docs/screenshots/v2.0.0-settings.png)

## Controls

| Key | Action |
| --- | --- |
| 0–9 | Choose dice count |
| X | Choose 10 dice |
| Enter | Confirm a human move |
| P | Pause / resume |
| R | Restart match |
| T | Switch theme |
| M | Toggle optional sound |
| F1 | Rules |
| H | Request move advice during a human turn |
| Esc | Home, confirming before leaving a match |

Shortcuts do not interfere with typing in name/seed fields. Mouse controls remain available. Human inputs are locked during rolling and computer turns.

![Paused match](docs/screenshots/v2.0.0-paused.png)

## Sound and Preferences

Sound defaults to off. Windows uses built-in `winsound`; macOS uses `afplay`; Linux uses an available `paplay` or `aplay`. If no backend exists, the sound control is disabled and the game remains playable. An available player still needs a working audio device. Playback failures do not interrupt a match.

Preferences contain only theme, animation, sound, and computer pace. Locations:

- Windows: `%APPDATA%/Hog/settings.json`
- macOS: `~/Library/Application Support/Hog/settings.json`
- Linux: `${XDG_CONFIG_HOME:-~/.config}/Hog/settings.json`

Malformed settings fall back to defaults. If saving fails, changes still apply for the current session. Profiles, history, saves, and tournament results use the separate SQLite database described above.

Launch overrides:

```bash
python hog_desktop.py --theme light --no-animation --mute
```

## Rules and Modes

Choose human vs computer, two humans, or computer vs computer. Player 0 starts; first to finish a turn with at least 100 points wins.

- **Sow Sad:** any rolled 1 makes the turn worth 1 point; otherwise sum the dice.
- **Boar Brawl:** zero dice earns `max(1, 3 * abs(opponent_tens - player_ones))`.
- **Sus Fuss:** totals with exactly 3 or 4 positive factors rise to the next prime, including after zero-dice turns.

The original six strategies remain: `always5`, `always6`, `catch-up`, `boar`, `sus`, and the original `adaptive` heuristic. The winner screen offers replay, new setup, and final-table review. A fixed seed restarts on desktop replay.

![Game board](docs/screenshots/v2.0.0-game.png)

## Terminal and Experiments

```bash
python hog_ui.py
python hog.py -r --games 100 --samples 500 --seed 42
```

The experiment game count is per starting seat per strategy. Results are sampled estimates; both seats and approximate pooled Wilson intervals are reported.

## Previous Releases

| Version | Main changes |
| --- | --- |
| v1.0.0 | Original coursework simulator, rules, text interface, and adaptive strategy. |
| v1.1.0 | Terminal menus, names, opponent selection, replay, working experiments, seeds, and 39 checks. |
| v1.2.0 | First graphical desktop interface, journal, winner screen, incremental engine, and 55 checks. |
| v2.0.0 | Animation, themes, optional sound, pause/restart, shortcuts, settings persistence, and 82 checks. |
| v2.1.0 | Easy/Medium/Hard opponents, exact win-probability policy, optional advice, visual comparisons, and 94 checks. |
| **v2.2.0** | Profiles, statistics, six achievements, history, exact save/resume, local leaderboard, tournaments, CSV export, and 110 checks. |
| v3.0.0 | Planned: final showcase edition. |

![Previous desktop](docs/screenshots/v1.2.0-home.png)

![Previous terminal](docs/screenshots/v1.1.0-menu.png)

![Original project](docs/screenshots/v1.0.0-legacy.png)

![Previous animated edition](docs/screenshots/v2.0.0-home.png)

![Previous smart opponents](docs/screenshots/v2.1.0-home.png)

Full earlier documentation: [v2.1.0](docs/history/v2.1.0.md), [v2.0.0](docs/history/v2.0.0.md), [v1.2.0](docs/history/v1.2.0.md), [v1.1.0](docs/history/v1.1.0.md). See [CHANGELOG.md](CHANGELOG.md) for cumulative changes. Archived README files describe their historical releases.

## Architecture and Files

| Module | Responsibility |
| --- | --- |
| `hog.py` | Rules, strategy registry, incremental sessions, full-match simulator |
| `hog_ai.py` | Exact roll distributions, greedy and optimal policies, move advice, measured comparisons |
| `hog_match.py` | Validated match setup and human profile assignments |
| `hog_storage.py` | SQLite profiles, statistics, history, save validation, and exports |
| `hog_tournament.py` | Seeded equal-seat round robins and tournament CSV export |
| `hog_desktop.py` | Tk views, controls, animation and cancellable timers |
| `hog_preferences.py` | Palette tokens, validated settings, atomic saving |
| `hog_audio.py` | Optional nonblocking WAV playback |
| `hog_ui.py`, `hog_experiments.py` | Retained terminal tools |
| `assets/sounds/` | Four original generated WAV effects |
| `tests/` | Engine, CLI, GUI, animation, preferences, and audio regressions |
| `docs/` | Screenshots, archived documentation, validation |
| `tools/` | Optional captures and sound generation |

A move passes from the UI through animation to `GameSession.advance` exactly once. Completed turn events update scores and the journal. Pausing cancels the current timer; restart discards the old animation. Cosmetic previews use separate randomness from gameplay.

## Validation and Screenshots

```bash
python -m unittest discover -s tests -v
python -m doctest hog.py dice.py
```

110 checks passed on Python 3.12.14 / Tk 9.0 on a Linux virtual display, alongside 18 documentation examples. GUI classes skip when no display is available. Native Windows/macOS playback was verified with mocked backends, not physical audio devices. Native OS execution is not claimed.

Current PNGs capture actual Tk windows. Historical terminal images are styled renderings with raw transcripts preserved. Optional screenshot tools require Pillow; playing and tests do not. The WAV generator uses only the standard library.

This edition does not include online play, cloud accounts, match replay navigation, or packaged executables. These remain later-release work.

## Credits

Original project and adaptive strategy: **Md Meazbah Mehedi Prodhan**. Based on the supplied Python Programming Project 1 Hog assignment and starter files. Original `dice.py` and `ucb.py` are retained; `ucb.py` credits UC Berkeley project utilities. This expanded GitHub edition goes beyond the coursework restriction to edit only `hog.py`.
