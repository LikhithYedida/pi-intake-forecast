"""
Plant-and-recover tests: prove the warehouse lets us find effects we know are there.

The simulator planted known effects (data/simulated/planted_truth.json). Each test
pulls the data back out of the BigQuery warehouse, measures the effect, and asserts it
lands within a tolerance of the planted value. A placebo test checks that the snow effect
does NOT appear where it was not planted, so a pass is not luck or a bias in the method.

Run either way from the project root:
  python tests/test_planted_effects.py      # prints a results table, writes reports/planted_effects_results.md
  pytest tests/                             # standard test runner (pip install pytest)
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = "pi-intake-forecast"
TRUTH = json.loads(Path("data/simulated/planted_truth.json").read_text())
RESULTS_MD = Path("reports/planted_effects_results.md")


@lru_cache(maxsize=None)
def query(sql: str) -> pd.DataFrame:
    from google.cloud import bigquery
    return bigquery.Client(project=PROJECT).query(sql).to_dataframe()


# ---------------------------------------------------------------------------
# Measurements: pure pandas, so they can be unit-tested without BigQuery.
# ---------------------------------------------------------------------------
def callback_lift(df: pd.DataFrame) -> float:
    """Sign rate for callbacks within 5 min / sign rate for callbacks over 60 min."""
    rate = df.set_index("callback_band")["sign_rate"]
    return float(rate["1. Within 5 min"] / rate["4. Over 60 min"])


def overload_quit_lift(df: pd.DataFrame) -> float:
    """Monthly quit rate of overloaded case managers / quit rate of the rest."""
    rate = df.set_index("is_overloaded")["quit_rate"]
    return float(rate[True] / rate[False])


def snow_effect(df: pd.DataFrame) -> tuple[float, float]:
    """Extra log-leads per snow day, with its standard error.
    Fixed-effects regression: each month is compared only to the same calendar month
    in other years at the same office (removes ordinary seasonality), and the state's
    crash signal is held constant (snow also changes real crash counts, which feed demand;
    without this control a real weather effect would be mistaken for the planted one)."""
    d = df[df["leads"] > 0].copy()
    d["y"] = np.log(d["leads"])
    d["c"] = np.log(d["state_crash_signal"])
    g = d.groupby(["office_id", "month_num"])
    X = np.column_stack([d["snow_days"] - g["snow_days"].transform("mean"),
                         d["c"] - g["c"].transform("mean")])
    y = (d["y"] - g["y"].transform("mean")).to_numpy()
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = len(y) - X.shape[1] - g.ngroups
    se = np.sqrt(np.diag((resid @ resid) / dof * np.linalg.inv(X.T @ X)))
    return float(beta[0]), float(se[0])


def fl_reform_effect(df: pd.DataFrame) -> float:
    """Difference-in-differences of log settlement: Florida after/before reform,
    relative to the other states over the same dates. Cancels anything that changed
    for every state at once (for example, faster-closing cases in recent years)."""
    d = df.set_index(["is_fl", "after"])["mean_log_settlement"]
    return float(np.exp((d[(True, True)] - d[(True, False)]) - (d[(False, True)] - d[(False, False)])))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def measure_all() -> list[dict]:
    s3 = callback_lift(query("""
        SELECT callback_band, AVG(CAST(is_signed AS INT64)) AS sign_rate
        FROM `pi-intake-forecast.clean.leads`
        WHERE month BETWEEN '2017-01-01' AND '2024-12-01'
        GROUP BY callback_band"""))
    s11 = overload_quit_lift(query("""
        SELECT is_overloaded, AVG(CAST(left_this_month AS INT64)) AS quit_rate
        FROM `pi-intake-forecast.clean.staff_month`
        WHERE role = 'Case manager' AND month BETWEEN '2017-01-01' AND '2024-12-01'
        GROUP BY is_overloaded"""))
    auto = query("""
        SELECT office_id, state_abbr, month_num, leads, snow_days, state_crash_signal
        FROM `pi-intake-forecast.mart.office_casetype_month`
        WHERE case_type = 'Auto' AND state_abbr IN ('MI', 'OH', 'PA')""")
    s4, s4_se = snow_effect(auto[auto["state_abbr"].isin(["MI", "OH"])])
    pl, pl_se = snow_effect(auto[auto["state_abbr"] == "PA"])
    fl = fl_reform_effect(query("""
        SELECT state_abbr = 'FL' AS is_fl,
               sign_date >= '2023-03-24' AS after,
               AVG(LN(settlement)) AS mean_log_settlement
        FROM `pi-intake-forecast.mart.case_economics`
        WHERE status = 'Closed' AND NOT is_lost AND sign_date >= '2021-01-01'
        GROUP BY 1, 2"""))

    planted_s3 = TRUTH["S3_response_time_sign_multiplier"]["<= 5 min"] / TRUTH["S3_response_time_sign_multiplier"]["<= inf min"]
    return [
        dict(test="S3 callback within 5 min vs over 60 min (sign-rate lift)",
             planted=planted_s3, recovered=s3, low=1.30, high=1.70),
        dict(test="S11 overloaded case managers (quit-rate lift)",
             planted=TRUTH["S11_case_manager_quit_multiplier_when_overloaded"], recovered=s11, low=1.50, high=2.70),
        # Snow effects are small relative to monthly noise, so they are judged by a 95%
        # confidence interval: it must contain the planted value (and 0 for the placebo).
        dict(test="S4 MI/OH auto leads per extra snow day (log-leads, 95% CI)",
             planted=TRUTH["S4_mi_oh_auto_leads_per_snow_day"], recovered=s4,
             low=s4 - 1.96 * s4_se, high=s4 + 1.96 * s4_se, rule="ci"),
        dict(test="S4 placebo: Pennsylvania, not planted (95% CI must include 0)",
             planted=0.0, recovered=pl, low=pl - 1.96 * pl_se, high=pl + 1.96 * pl_se, rule="ci"),
        dict(test="Florida tort reform (settlement value, diff-in-diff)",
             planted=TRUTH["florida_reform_value_multiplier"], recovered=fl, low=0.75, high=0.95),
    ]


RESULTS = None


def results() -> list[dict]:
    global RESULTS
    if RESULTS is None:
        RESULTS = measure_all()
    return RESULTS


def passes(r: dict) -> bool:
    """Range rule: the recovered value must fall in the pass range.
    CI rule: the recovered value's 95% confidence interval must contain the planted value."""
    value = r["planted"] if r.get("rule") == "ci" else r["recovered"]
    return r["low"] <= value <= r["high"]


def _check(i: int) -> None:
    r = results()[i]
    assert passes(r), f"{r['test']}: recovered {r['recovered']:.3f}, pass range {r['low']:.3f}-{r['high']:.3f}"


def test_s3_callback_speed():      _check(0)
def test_s11_overload_quits():     _check(1)
def test_s4_snow_effect():         _check(2)
def test_s4_placebo():             _check(3)
def test_florida_reform():         _check(4)


def main() -> None:
    rows = results()
    passed = 0
    lines = ["# Planted Effects: Results", "",
             "Each effect was planted in the simulation, then recovered from the BigQuery warehouse "
             "by `tests/test_planted_effects.py`. A pass means the data pipeline preserves real effects "
             "and the measurement method finds them.", "",
             "Large effects must land in a fixed pass range. Small effects (snow) are judged by a 95% "
             "confidence interval, which must contain the planted value; the placebo's must contain 0.", "",
             "| Test | Planted | Recovered | Pass range / 95% CI | Result |", "| --- | ---: | ---: | --- | --- |"]
    print(f"{'Test':62s} {'Planted':>8s} {'Found':>8s}  Range           Result")
    for r in rows:
        ok = passes(r)
        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"{r['test']:62s} {r['planted']:8.3f} {r['recovered']:8.3f}  {r['low']:.3f}-{r['high']:.3f}     {status}")
        lines.append(f"| {r['test']} | {r['planted']:.3f} | {r['recovered']:.3f} | {r['low']:.3f} to {r['high']:.3f} | {status} |")
    lines += ["", f"**{passed} of {len(rows)} passed.**"]
    RESULTS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{passed} of {len(rows)} passed. Results written to {RESULTS_MD}")
    if passed < len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
