# v2.1.0 Validation

2026-10-29. Linux / Python 3.12.14 / Tk 9.0, with a virtual display.

94 automated checks pass, alongside 18 doctest examples. New checks compare dice distributions with independent exhaustive enumeration for one to three dice, verify total probability and Sow Sad risk, check all policy values and action bounds, compare Bellman values with per-move analysis, validate guaranteed zero-dice wins, verify no gameplay randomness is consumed by advice, and exercise reproducible equal-seat comparisons. Real-window tests cover advisor rendering without playing a turn and background comparison results.

PNG captures use actual Tk windows on Linux / Tk 8.6. Existing platform and optional-audio limitations remain. Native Windows/macOS execution and physical audio output are not claimed.

The policy is exact to floating-point precision under its stated fair-six-sided, all-rules, 100-point, optimal-opponent assumptions. Benchmark results are sampled and recorded separately in benchmark.json.
