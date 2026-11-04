# v2.0.0 Validation

Date: 2026-10-29. Linux / Python 3.12.14 / Tk 9.0 with a virtual display.

82 automated checks passed. All 18 doctest examples pass.

New coverage checks that animation does not consume scoring dice early, pause freezes and resumes correctly, reduced motion commits once, themes preserve matches, settings restore pause state, restart cancels old animations, and animated/nonanimated matches have identical events. Preferences tests cover corrupt files, atomic replacement failure, round trips, and text contrast. Audio tests check WAV assets, argument-list subprocess playback, Windows asynchronous flags, stopping, and safe failure through mocks.

Desktop PNGs are actual Tk window captures. Audio hardware and native Windows/macOS execution were not tested. Historical validation notes remain under history/.
