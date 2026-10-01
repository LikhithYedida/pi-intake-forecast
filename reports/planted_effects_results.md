# Planted Effects: Results

Each effect was planted in the simulation, then recovered from the BigQuery warehouse by `tests/test_planted_effects.py`. A pass means the data pipeline preserves real effects and the measurement method finds them.

Large effects must land in a fixed pass range. Small effects (snow) are judged by a 95% confidence interval, which must contain the planted value; the placebo's must contain 0.

| Test | Planted | Recovered | Pass range / 95% CI | Result |
| --- | ---: | ---: | --- | --- |
| S3 callback within 5 min vs over 60 min (sign-rate lift) | 1.500 | 1.496 | 1.300 to 1.700 | PASS |
| S11 overloaded case managers (quit-rate lift) | 2.000 | 1.689 | 1.500 to 2.700 | PASS |
| S4 MI/OH auto leads per extra snow day (log-leads, 95% CI) | 0.020 | 0.016 | 0.005 to 0.027 | PASS |
| S4 placebo: Pennsylvania, not planted (95% CI must include 0) | 0.000 | -0.005 | -0.026 to 0.015 | PASS |
| Florida tort reform (settlement value, diff-in-diff) | 0.850 | 0.877 | 0.750 to 0.950 | PASS |

**5 of 5 passed.**
