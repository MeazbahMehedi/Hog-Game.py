# v1.2.0 Validation

Date: 2026-10-28.

## Environments

- Linux, Python 3.12.14, Tk 9.0.
- Linux, Python 3.12.3, Tk 8.6.14.
- A virtual X display was used to exercise and capture real Tk windows.

Native Windows and macOS execution was not tested in this build.

## Automated Checks

```bash
python -m unittest discover -s tests -v
python -m doctest hog.py dice.py
```

Result: **55 tests passed with no skips** when run with the virtual display,
under each Python/Tk environment. The 18 doctest examples also pass.

Without a graphical display, the real-window test class is skipped and the
remaining 46 tests run. On typical Linux CI, the full suite can run under:

```bash
xvfb-run -a python -m unittest discover -s tests -v
```

The previous release's 39 tests remain included. New coverage checks:

- Incremental sessions and full-game simulation produce identical turns and scores.
- A completed session rejects further moves; invalid moves leave state unchanged.
- Match configuration validates modes, names, strategies, and optional seeds.
- Real setup controls switch between human and computer states.
- Bad names or seeds cannot start a match.
- Human dice buttons advance exactly one turn and lock during a computer turn.
- Local two-human mode alternates without scheduling computer timers.
- Computer-only play agrees with the engine and advances via Tk's event loop.
- Home navigation confirms leaving a game and cancels pending computer callbacks.
- Rules windows can be reused, closed, and reopened.
- Finished matches support summary, final-table review, and replay.
- Dice controls and the action button fit a 1040x720 window.
- The desktop version flag works without opening a display.

## Actual Desktop Screenshots

```bash
python tools/capture_desktop.py
```

The optional capture tool uses Pillow to capture actual Tk client areas,
without compositing or generating a replacement UI. Captures were produced
with Python 3.12.3 / Tk 8.6 and reviewed for layout and readable controls.

The game screenshots follow a real seeded match: Player 0's choices follow
`adaptive`, the computer uses `sus`, and the seed is 42. The capture utility
submits human-side choices through the same control callbacks as ordinary play.
It does not replace scores, dice, or turn events. Result: 107-32 over 15 turns.

Images include home, setup, active game, zero-dice scoring, winner, and rules.
Historical terminal captures and transcripts are preserved from earlier releases.

## Preserved Behavior

The original scoring rules, adaptive strategy priority, terminal options,
experiment flags, and simulator function names remain. `GameSession` now owns
turn advancement so both interfaces use one scoring path.

The archived [v1.1.0 validation notes](history/v1.1.0-validation.md) record the
original release checks, including comparison against the uploaded coursework.

## Scope

- The desktop needs a graphical display and Tk support in the selected Python.
- A missing display or missing Tk produces a clear launcher error with a terminal fallback.
- A fixed desktop seed restarts on replay; terminal replay continues its session stream.
- No saved games, persistent profiles, animations, sound, or native executable yet.
