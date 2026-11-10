# v2.2.0 Validation

2026-10-29. Linux / Python 3.12.14 / Tk 9.0 with a virtual display.

110 automated checks pass with a display. All 18 doctest examples pass. Without a display, GUI classes skip.

New checks cover profile persistence and uniqueness, invalid names, exact seeded/unseeded resumption, scoring/state validation, match-ID deduplication, clearing the matching save, guest isolation, achievement derivation, CSV escaping, computer/profile restrictions, round-robin seat balance, deterministic results, tournament persistence, profile setup controls, paused resumption, and real-window tournament rendering/reopening.

Current screenshots capture real Tk windows on Linux / Tk 8.6. Demo history comes from three genuine seeded matches with profile choices; it is not included as a user database in the ZIP. Tournament captures come from a real 200-game round robin.

Native Windows/macOS execution and physical audio hardware are not claimed. Existing engine and AI assumptions remain documented in the README. Persistence is desktop-only and local; there is one manual save slot, no cloud sync, and no profile rename/delete UI.
