# v3.5.0 Validation

2026-10-29. Final full source suite: Linux / Python 3.12.3 / Tk 8.6 on a virtual display. An earlier full run also passed on Python 3.12.14 / Tk 9.0.

236 automated checks passed with graphical classes enabled. All 18 doctest examples passed. The 29 new checks cover ready requirements, token isolation, seat/turn/count validation, duplicated/stale moves, authoritative scoring, zero-dice timeouts, disabled timers, heartbeat pauses/resume, grace expiry, rematches, departures/replacement joins, handshake retries, immutable snapshots, room limits, malformed bodies, request bounds, display-state validation, real HTTP/TLS clients, certificate trust rejection/acceptance, GUI reconnection, lost-response retries, unchanged local history, theme/layout behavior, and destroyed-view cycle cleanup before worker garbage collection.

A repeated-window run exposed Tcl interpreter finalization on a worker thread. The close path now drops dynamic view closures and collects their cycles on the Tk thread. A regression check verifies that a closed puzzle view releases its app before a worker performs garbage collection. The final Tk 8.6 full suite, including all multiplayer checks, passes with that fix.

The standalone tools/network_smoke.py check uses two actual HTTP clients, a completed goal match and an alternating-seat rematch. HTTPS tests generate a temporary local certificate, confirm rejection without trust, then connect with explicit trust. No test certificate or private key is shipped. Public internet/NAT routing and native Windows/macOS networking were not tested.

Eight current screenshots capture actual Tk 8.6 windows over a temporary loopback relay. Seeded demo scoring is used only by the capture relay for reproducibility; the production relay creates its own undisclosed random streams. All demo rooms shut down after capture.

The native Linux x86_64 client was rebuilt with Python 3.12.3, Tk 8.6, PyInstaller 6.22.3 and glibc 2.39. Version (3.5.0) and actual-window smoke startup passed. The clean extracted ZIP passed integrity, all relative Markdown links, all four source launcher versions, doctests, the two-client network smoke check and native startup. Older glibc compatibility, Windows/macOS native execution and physical audio were not verified.

No SQLite schema migration beyond the retained v3.4.0 schema-2 path is added. Online results and credentials are not saved into local profiles, campaign data, history, exports or manual saves. Rooms and tokens are in-memory relay state, not durable accounts. Reconnect tests cover the existing app token within grace, not recovery after a process restart.
