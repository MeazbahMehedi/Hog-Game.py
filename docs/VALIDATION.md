# v1.1.0 Validation

Environment: Python 3.12.14 on Linux. Date: 2026-10-28.

## Automated Checks

```bash
python -m unittest discover -s tests -v
python -m doctest hog.py dice.py
```

Result: **39 tests passed**; doctest examples passed.

Coverage includes:

- Sow Sad consumes every chosen dice roll, including rolls after a 1.
- Assignment Boar Brawl examples and tens-digit extraction.
- Factor and prime calculations checked against simple definitions through 300.
- Sus Fuss checked against the mathematical definition for totals 0-300.
- Sus Fuss after both zero-dice and Sow Sad turns.
- Correct strategy argument order, alternating turns, and immediate stop at the goal.
- Turn observation does not change results or consume extra dice.
- Valid roll choices for all six strategies at every score pair from 0-99.
- Adaptive strategy priority, fixed-roll tie behavior, and averaging.
- Invalid values, Unicode numeric input, player-name controls, and clean end-of-input.
- Real subprocess execution of menus, named setup, opponent selection, replay,
  human vs computer, two-human mode, automatic mode, and experiment flags.
- Repeatable game and experiment output using a fixed seed.

An additional release check compared this edition with the uploaded original
solution: 50,000 score-pair comparisons across five scoring/strategy functions,
and 150 complete seeded games. All results agreed. This comparison used the
original upload outside the package and is separate from the 39 included tests.

## Documentation Captures

Generated with:

```bash
python tools/capture_terminal.py
```

The optional capture tool uses Pillow and a supported monospace font. Its images
are styled representations of actual subprocess output; raw transcripts are
included. PNGs were visually inspected for readable text and clipping.

Current-version match capture:

```bash
python hog_ui.py -n 0 --strategy0 adaptive --strategy1 sus --name0 Meazbah --name1 Computer --seed 42 --no-replay
```

Result: Meazbah 107, Computer 32, over 15 turns.

The experiment capture uses 100 games per seat, 500 turn samples per roll count,
and seed 42. Its complete output is in
`screenshots/v1.1.0-experiments.txt`. Results are sampled measurements.

The legacy image was captured from the original supplied modules with global
random seed 42, calling `hog_ui.play_with(0)`. That original source is not
duplicated in this release ZIP; its full output transcript is retained.

## Limits

- Native Windows and macOS execution were not tested in this environment.
- No graphical window is provided in this terminal release.
- The optional documentation image tool is separate from runtime requirements.
