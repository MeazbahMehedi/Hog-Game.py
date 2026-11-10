# v3.0.0 Validation

2026-10-29. Source suite: Linux / Python 3.12.14 / Tk 9.0 with a virtual display.

122 automated checks passed. All 18 doctest examples pass. New tests cover actual tutorial answers, practice goals/rules/validation/seeds, replay score reconstruction and tamper rejection, read-only behavior, tutorial interaction, practice isolation, replay navigation without statistics changes, and live-match accessibility changes.

Native build: Linux x86_64, Python 3.12.3, Tk 8.6, PyInstaller 6.22.3, glibc 2.39. The packaged executable passed `--version` and a real-window `--smoke-test` using in-memory data. No Windows/macOS executable or native execution was verified. Optional audio hardware limitations remain.

Current screenshots capture real Tk windows on Linux / Tk 8.6. Tutorial and practice screenshots come from actual controls and rule calculations. Replay screenshots reconstruct genuine previously completed matches. No demo database is included.

The existing SQLite schema remains at version 1, and previous v2.2.0 standard records/saves remain compatible. Larger-text preferences default off for older settings files. Custom practice sessions are intentionally transient and do not use the 100-point optimal-policy advisor.
