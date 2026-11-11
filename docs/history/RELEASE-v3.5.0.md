# GitHub Release Details

**Tag:** `v3.5.0`

**Title:** `v3.5.0 - Private Multiplayer Edition`

## Description

Play Hog with a friend through a private room on a relay you host.

### What's new

- Room invitation codes, a two-player ready lobby and synchronized desktop tables.
- Authoritative server dice/scoring with seat, turn and match validation.
- Optional turn timers with clearly marked zero-dice timeout moves.
- Presence indicators, timer pauses, temporary seat reconnection and automatic retry handling.
- Duplicate-move protection when a successful response is lost.
- Rematch voting with alternating starting seats.
- Standard-library HTTP(S) relay, certificate-verifying client and hosting guide.
- Tk view cleanup fix for background-worker garbage collection.
- Eight actual screenshots, updated cumulative README and archived prior documentation.

### Start locally

Run `python hog_server.py` in one terminal and `python hog_desktop.py` in another. Open Online and use `http://127.0.0.1:8765`. Both players need the same running, reachable relay plus a room code. Read ONLINE.md for LAN/HTTPS hosting. No public server is deployed by this ZIP.

Online results stay separate from local wins, campaign progress, statistics and saves. Seat credentials live only in app memory; app exit loses them, and relay restart removes rooms. Existing offline features and SQLite schema 2 are preserved.

### Validation

236 automated checks and 18 doctest examples passed on Linux. Real HTTP/TLS clients completed a round/rematch; tests cover response-loss retries, timeout moves, reconnect timing, malformed requests, token isolation and Tk lifecycle cleanup. The rebuilt Linux client passed version and actual-window smoke checks. Public internet/NAT routing and native Windows/macOS execution were not verified.

The final distribution-polish release remains next in the roadmap.
