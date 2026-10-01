# %% [markdown]
# # 01 Seasonality: when does each case type arrive, and what is it worth?
#
# **Question for leadership:** Which case types peak in which months in each state,
# and how should staffing and marketing move with them?
#
# **Method**
# 1. Seasonal index per state and case type: each month's signed cases divided by that
#    year's average month, averaged across 2017-2024 (COVID months excluded), x 100.
#    100 = an average month. Dividing by each year's own average removes growth and
#    one-off years, so only the recurring calendar pattern is left.
# 2. A month counts as a real peak or trough only when its 95% confidence interval
#    excludes 100. With 7 years per month, this screens out one lucky year.
# 3. Every finding is translated into signed cases and fee dollars, using the expected
#    fee per signed case (closed cases signed 2017-2022, lost cases included as $0).
#
# **Outputs**
# - `reports/seasonality_findings.md`: headline findings and recommendations
# - `reports/figures/seasonality_*.png`: charts for the README and director brief
# - `mart.seasonal_index` in BigQuery: feeds the Looker Studio seasonal calendar page
#
# Run as a script (`python notebooks/01_seasonality.py`) or cell by cell in VS Code
# (each `# %%` is a cell: click "Run Cell").

# %%
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

PROJECT = "pi-intake-forecast"
FIG_DIR = Path("reports/figures")
REPORT = Path("reports/seasonality_findings.md")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
STATE_NAMES = {"MI": "Michigan", "OH": "Ohio", "PA": "Pennsylvania", "GA": "Georgia", "FL": "Florida", "TX": "Texas"}
STATE_ORDER = ["MI", "OH", "PA", "GA", "FL", "TX"]   # north to south
MIN_MONTHLY_CASES = 15        # state x case-type series thinner than this are too noisy to call
INTAKE_LEAD_TIME_WEEKS = "6-8"  # recruit + train an intake specialist (assumption S10: 2-month hiring lag)
BUSY_LOAD = 0.95              # a calendar month is "at capacity" when average intake load reaches this

# Chart styling (dataviz reference palette, light mode)
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE, RED, NEUTRAL = "#2a78d6", "#e34948", "#f0efec"
DIVERGING = LinearSegmentedColormap.from_list("below_above", [BLUE, NEUTRAL, RED])
plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2, "axes.edgecolor": AXIS, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "axes.spines.top": False,
    "axes.spines.right": False,
})


# %% Load data from the warehouse
def to_numpy_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """BigQuery returns pandas nullable types (Int64, Float64, boolean). Plotting and numpy maths
    need plain types: whole numbers stay int (float if they have gaps), decimals become float,
    flags become bool (missing flag = False), text becomes plain object strings."""
    df = df.copy()
    for col in df.columns:
        dtype = str(df[col].dtype)
        if dtype == "boolean":
            df[col] = df[col].fillna(False).astype(bool)
        elif dtype in ("Int64", "Int32", "Int16", "Int8"):
            df[col] = df[col].astype("int64" if not df[col].isna().any() else "float64")
        elif dtype in ("Float64", "Float32") or dtype.startswith("decimal") or dtype == "object" and \
                df[col].map(lambda v: type(v).__name__ == "Decimal").any():
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        elif dtype in ("string", "str") or dtype.startswith("string"):
            df[col] = df[col].astype(object)
    return df


def load_data() -> dict[str, pd.DataFrame]:
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    q = lambda sql: to_numpy_dtypes(client.query(sql).to_dataframe())
    return {
        "ctm": q(f"""
            SELECT state_abbr, case_type, month, year, month_num, is_covid,
                   SUM(leads) AS leads, SUM(signed_cases) AS signed_cases
            FROM `{PROJECT}.mart.office_casetype_month`
            GROUP BY state_abbr, case_type, month, year, month_num, is_covid"""),
        "office_month": q(f"""
            SELECT office_id, state_abbr, month, year, month_num, is_covid, leads, signed_cases,
                   median_callback_min, share_called_within_5min, intake_load, intake_headcount
            FROM `{PROJECT}.mart.office_month`"""),
        "fee": q(f"""
            SELECT state_abbr, case_type, COUNT(*) AS closed_cases, AVG(fee) AS expected_fee
            FROM `{PROJECT}.mart.case_economics`
            WHERE status = 'Closed' AND sign_year BETWEEN 2017 AND 2022
            GROUP BY state_abbr, case_type"""),
    }


# %% Seasonal index
def seasonal_index(monthly: pd.DataFrame, keys: list[str], value: str = "signed_cases") -> pd.DataFrame:
    """Index (100 = average month) per key group and calendar month, with a 95% CI across years."""
    d = monthly[~monthly["is_covid"]].copy()
    year_mean = d.groupby(keys + ["year"])[value].transform("mean")
    d["ratio"] = d[value] / year_mean
    out = (d.groupby(keys + ["month_num"])
             .agg(index=("ratio", "mean"), sd=("ratio", "std"), years=("ratio", "size"),
                  avg_monthly=(value, "mean"))
             .reset_index())
    half = 1.96 * out["sd"] / np.sqrt(out["years"])
    out["index"] = 100 * out["index"]
    out["ci_low"] = out["index"] - 100 * half
    out["ci_high"] = out["index"] + 100 * half
    out["significant"] = (out["ci_low"] > 100) | (out["ci_high"] < 100)
    out["month_name"] = out["month_num"].map(lambda m: MONTHS[m - 1])
    return out.drop(columns="sd")


def build_indices(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    ctm = data["ctm"]
    all_types = ctm.groupby(["state_abbr", "month", "year", "month_num", "is_covid"], as_index=False)["signed_cases"].sum()
    firm_type = ctm.groupby(["case_type", "month", "year", "month_num", "is_covid"], as_index=False)["signed_cases"].sum()
    firm_all = all_types.groupby(["month", "year", "month_num", "is_covid"], as_index=False)["signed_cases"].sum()

    parts = [
        seasonal_index(ctm, ["state_abbr", "case_type"]),
        seasonal_index(all_types, ["state_abbr"]).assign(case_type="All case types"),
        seasonal_index(firm_type, ["case_type"]).assign(state_abbr="Firm"),
        seasonal_index(firm_all, []).assign(state_abbr="Firm", case_type="All case types"),
    ]
    idx = pd.concat(parts, ignore_index=True)
    cols = ["state_abbr", "case_type", "month_num", "month_name", "index", "ci_low", "ci_high",
            "significant", "years", "avg_monthly"]
    return idx[cols].round({"index": 1, "ci_low": 1, "ci_high": 1, "avg_monthly": 1})


# %% Peak and trough seasons: best consecutive 3-month window (can wrap Dec -> Jan)
def season_window(index_by_month: pd.Series, width: int = 3, peak: bool = True) -> list[int]:
    """Calendar months (1-12) of the consecutive window with the highest (or lowest) total index.
    Staffing and marketing plans need a season, not scattered months."""
    vals = index_by_month.reindex(range(1, 13)).to_numpy()
    sums = [sum(vals[(start + k) % 12] for k in range(width)) for start in range(12)]
    start = int(np.argmax(sums) if peak else np.argmin(sums))
    return [((start + k) % 12) + 1 for k in range(width)]


def season_start(months: list[int]) -> int:
    """First month of a run of months, wrapping Dec -> Jan (e.g. [1, 2, 12] starts in Dec)."""
    starts = [m for m in months if ((m - 2) % 12) + 1 not in months]
    return starts[0] if starts else min(months)


def in_season_order(months: list[int]) -> list[int]:
    start = season_start(months)
    return sorted(months, key=lambda m: (m - start) % 12)


def season_text(months: list[int]) -> str:
    """'Jun-Aug' or 'Dec-Feb' for consecutive months; a list otherwise."""
    ordered = in_season_order(months)
    consecutive = all((b - a) % 12 == 1 for a, b in zip(ordered, ordered[1:]))
    if consecutive and len(ordered) > 1:
        return f"{MONTHS[ordered[0] - 1]}-{MONTHS[ordered[-1] - 1]}"
    return months_text(ordered)


# %% Value: expected fee per signed case
def fee_lookup(fee: pd.DataFrame) -> dict[tuple[str, str], float]:
    """Expected fee per signed case by (state, case type); 'All case types' and 'Firm' are case-weighted."""
    out = {(r.state_abbr, r.case_type): r.expected_fee for r in fee.itertuples()}
    w = fee.assign(total=fee["expected_fee"] * fee["closed_cases"])
    for state, g in w.groupby("state_abbr"):
        out[(state, "All case types")] = g["total"].sum() / g["closed_cases"].sum()
    for ct, g in w.groupby("case_type"):
        out[("Firm", ct)] = g["total"].sum() / g["closed_cases"].sum()
    out[("Firm", "All case types")] = w["total"].sum() / w["closed_cases"].sum()
    return out


def peak_value(idx: pd.DataFrame, fees: dict, state: str, case_type: str, months: list[int]) -> tuple[float, float]:
    """Extra signed cases per year in the given months vs an average month, and their fee value."""
    s = idx[(idx["state_abbr"] == state) & (idx["case_type"] == case_type)].set_index("month_num")
    base = s["avg_monthly"].mean()                      # average month
    extra = sum((s.loc[m, "index"] / 100 - 1) * base for m in months)
    return extra, extra * fees.get((state, case_type), np.nan)


# %% Staffing: what peaks cost when intake is staffed flat
def intake_pressure(om: pd.DataFrame) -> pd.DataFrame:
    """Intake load, callback speed and sign rate by calendar month (firm-wide, COVID excluded)."""
    d = om[~om["is_covid"]]
    g = d.groupby("month_num").agg(
        leads=("leads", "sum"), signed=("signed_cases", "sum"),
        intake_load=("intake_load", "mean"), median_callback_min=("median_callback_min", "median"),
        within_5=("share_called_within_5min", "mean"), years=("year", "nunique"))
    g["sign_rate"] = g["signed"] / g["leads"]
    g["leads_per_year"] = g["leads"] / g["years"]
    g["month_name"] = [MONTHS[m - 1] for m in g.index]
    return g


def busy_months(pressure: pd.DataFrame) -> list[int]:
    """Calendar months at or near full intake capacity; falls back to the top 3 if none reach it."""
    busy = pressure.index[pressure["intake_load"] >= BUSY_LOAD].tolist()
    return busy or pressure["intake_load"].nlargest(3).index.tolist()


def peak_cost(pressure: pd.DataFrame, ctm: pd.DataFrame, fees: dict) -> dict:
    """Signed cases lost in the at-capacity months, MIX-ADJUSTED.
    Busy months also bring a different case mix (more motorcycle and dog-bite leads), and
    case types convert at different rates. Comparing raw sign rates would blame intake for
    that. Instead, each case type is compared with itself: busy-month sign rate vs the same
    case type's rate in normal months, applied to the busy months' own leads."""
    busy = busy_months(pressure)
    d = ctm[~ctm["is_covid"]].assign(is_busy=lambda x: x["month_num"].isin(busy))
    years = d["year"].nunique()
    by = d.groupby(["case_type", "is_busy"])[["leads", "signed_cases"]].sum().unstack("is_busy")
    rate_busy = by[("signed_cases", True)] / by[("leads", True)]
    rate_rest = by[("signed_cases", False)] / by[("leads", False)]
    busy_leads_per_year = by[("leads", True)] / years
    lost_by_type = (rate_rest - rate_busy) * busy_leads_per_year
    fee_by_type = pd.Series({ct: fees.get(("Firm", ct), np.nan) for ct in lost_by_type.index})
    lost = float(lost_by_type.sum())
    rest = pressure.drop(busy)
    sel = pressure.loc[busy]
    return dict(
        months=busy, busy_load=sel["intake_load"].mean(), rest_load=rest["intake_load"].mean(),
        busy_callback=sel["median_callback_min"].median(), rest_callback=rest["median_callback_min"].median(),
        busy_within_5=sel["within_5"].mean(), rest_within_5=rest["within_5"].mean(),
        busy_rate=float((rate_busy * busy_leads_per_year).sum() / busy_leads_per_year.sum()),
        rest_rate_same_mix=float((rate_rest * busy_leads_per_year).sum() / busy_leads_per_year.sum()),
        lost_cases=lost, lost_fees=float((lost_by_type * fee_by_type).sum()))


# %% Charts
def heatmap(matrix: pd.DataFrame, sig: pd.DataFrame, title: str, subtitle: str, path: Path) -> None:
    """Diverging heatmap centred at 100. Bold labels mark months whose 95% CI excludes 100."""
    matrix, sig = matrix.astype("float64"), sig.astype(bool)
    span = max(abs(matrix.values - 100).max(), 5)
    fig, ax = plt.subplots(figsize=(10, 0.48 * len(matrix) + 1.9))
    ax.imshow(matrix.values, cmap=DIVERGING, norm=TwoSlopeNorm(100, 100 - span, 100 + span), aspect="auto")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v, bold = matrix.iat[i, j], sig.iat[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=9,
                    fontweight="bold" if bold else "normal", color=INK if bold else INK_2)
    ax.set_xticks(range(12), MONTHS)
    ax.set_yticks(range(len(matrix)), matrix.index)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, 12), minor=True)
    ax.set_yticks(np.arange(-0.5, len(matrix)), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="minor", length=0)
    fig.text(0.01, 0.985, title, fontsize=13, fontweight="bold", va="top")
    fig.text(0.01, 0.985 - 0.32 / fig.get_figheight(), subtitle, fontsize=9.5, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.62 / fig.get_figheight()))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def pressure_chart(pressure: pd.DataFrame, cost: dict, path: Path) -> None:
    """Intake load by calendar month; at-capacity months in the accent colour, the rest in grey."""
    fig, ax = plt.subplots(figsize=(10, 4.2))
    busy = pressure.index.isin(cost["months"])
    colors = np.where(busy, RED, "#b9b8b2")
    ax.bar(pressure["month_name"], pressure["intake_load"], color=colors, width=0.62, zorder=2)
    ax.axhline(1.0, color=INK_2, linewidth=1, linestyle=(0, (4, 3)), zorder=3)
    ax.text(-0.45, 1.0, "Full capacity", ha="left", va="bottom", fontsize=9, color=INK_2)
    for x, (v, b) in enumerate(zip(pressure["intake_load"], busy)):
        if b:
            ax.text(x, v - 0.025, f"{v:.2f}", ha="center", va="top", fontsize=9, fontweight="bold", color="white")
    ax.set_ylabel("Intake load (workload / capacity)")
    ax.set_ylim(0, max(1.15, pressure["intake_load"].max() + 0.12))
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.tick_params(length=0)
    window = season_text(cost["months"])
    title = (f"Intake runs at capacity in {window}, and callbacks slow from "
             f"{cost['rest_callback']:.0f} to {cost['busy_callback']:.0f} minutes")
    fig.text(0.01, 0.97, title, fontsize=13, fontweight="bold", va="top")
    fig.text(0.01, 0.905, "Average intake load by calendar month, all offices, 2017-2024 excl. COVID. "
                          f"Red = load {BUSY_LOAD:.2f} or higher.", fontsize=9.5, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(path, dpi=200)
    plt.close(fig)


# %% Findings
def describe_state(idx: pd.DataFrame, fees: dict, state: str) -> dict:
    s = idx[(idx["state_abbr"] == state) & (idx["case_type"] == "All case types")].set_index("month_num")
    peak3 = season_window(s["index"], peak=True)
    low3 = season_window(s["index"], peak=False)
    extra, dollars = peak_value(idx, fees, state, "All case types", peak3)
    return dict(state=state, peak=int(s["index"].idxmax()), peak_idx=s["index"].max(),
                low=int(s["index"].idxmin()), low_idx=s["index"].min(),
                swing=s["index"].max() - s["index"].min(), peak3=peak3, low3=low3,
                extra_cases=extra, extra_fees=dollars, avg_monthly=s["avg_monthly"].mean())


def strongest_case_types(idx: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """State x case-type series with the strongest reliable SEASON: the best consecutive 3-month
    window's average lift over an average month. Requires enough volume and at least one month in
    the window whose 95% CI excludes 100, so one lucky year cannot make the list."""
    d = idx[(idx["state_abbr"] != "Firm") & (idx["case_type"] != "All case types")]
    rows = []
    for (state, ct), g in d.groupby(["state_abbr", "case_type"]):
        g = g.set_index("month_num")
        window = season_window(g["index"], peak=True)
        rows.append(dict(state_abbr=state, case_type=ct, window=window,
                         season_lift=g.loc[window, "index"].mean() - 100,
                         avg_monthly=g["avg_monthly"].mean(),
                         reliable=bool(g.loc[window, "significant"].any() and (g.loc[window, "index"] > 100).all())))
    summary = pd.DataFrame(rows)
    ok = summary[(summary["avg_monthly"] >= MIN_MONTHLY_CASES) & summary["reliable"]]
    return ok.nlargest(n, "season_lift")


def counter_seasonal_states(idx: pd.DataFrame) -> pd.DataFrame:
    """States whose calendar runs against the firm's: negative correlation with the firm index.
    These offices are quiet when the firm is busy, so their intake staff can absorb overflow."""
    firm = idx[(idx["state_abbr"] == "Firm") & (idx["case_type"] == "All case types")].set_index("month_num")["index"]
    rows = []
    for state in STATE_ORDER:
        s = idx[(idx["state_abbr"] == state) & (idx["case_type"] == "All case types")].set_index("month_num")["index"]
        rows.append(dict(state=state, corr=float(np.corrcoef(s.reindex(range(1, 13)), firm.reindex(range(1, 13)))[0, 1]),
                         peak=season_window(s), trough=season_window(s, peak=False)))
    out = pd.DataFrame(rows)
    return out[out["corr"] < 0].sort_values("corr")


def winter_hypothesis(idx: pd.DataFrame) -> dict:
    """Test the starting hypothesis that MI and OH auto intake rises in winter (Dec-Feb)."""
    d = idx[idx["state_abbr"].isin(["MI", "OH"]) & (idx["case_type"] == "Auto") & idx["month_num"].isin([12, 1, 2])]
    lift = float(d["index"].mean() - 100)
    peaks = {st: season_window(idx[(idx["state_abbr"] == st) & (idx["case_type"] == "Auto")]
                               .set_index("month_num")["index"]) for st in ["MI", "OH"]}
    above = lift > 0 and bool(d["significant"].any())
    winter_peak = any(set(w) & {12, 1, 2} for w in peaks.values())
    verdict = "Supported" if above and winter_peak else "Partly supported" if above else "Not supported"
    return dict(lift=lift, verdict=verdict, peaks=peaks)


def season_start_name(months: list[int]) -> str:
    return MONTHS[season_start(months) - 1]


def months_text(nums: list[int]) -> str:
    names = [MONTHS[m - 1] for m in nums]
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]


def money(x: float) -> str:
    return f"${x / 1e6:.1f}M" if abs(x) >= 1e6 else f"${x / 1e3:,.0f}K"


def write_report(idx: pd.DataFrame, fees: dict, pressure: pd.DataFrame, cost: dict) -> str:
    firm = describe_state(idx, fees, "Firm")
    states = pd.DataFrame([describe_state(idx, fees, s) for s in STATE_ORDER])
    biggest = states.loc[states["swing"].idxmax()]
    flattest = states.loc[states["swing"].idxmin()]
    top_types = strongest_case_types(idx)
    firm_types = idx[(idx["state_abbr"] == "Firm") & (idx["case_type"] != "All case types")]
    type_swing = firm_types.groupby("case_type")["index"].agg(lambda s: s.max() - s.min()).sort_values()
    loses_cases = cost["lost_cases"] > 0
    winter = winter_hypothesis(idx)
    hire_by = MONTHS[(season_start(cost["months"]) - 3) % 12]   # ~2 months before intake hits capacity

    findings = [
        f"**Seasonality differs sharply by state.** {STATE_NAMES[biggest['state']]} has the largest swing "
        f"({biggest['swing']:.0f} index points: peak {MONTHS[int(biggest['peak']) - 1]} at {biggest['peak_idx']:.0f}, "
        f"low {MONTHS[int(biggest['low']) - 1]} at {biggest['low_idx']:.0f}); {STATE_NAMES[flattest['state']]} is the "
        f"flattest ({flattest['swing']:.0f} points). One firm-wide staffing calendar would over-staff some offices "
        f"while under-staffing others in the same month.",
    ]
    for _, r in top_types.iterrows():
        extra, dollars = peak_value(idx, fees, r["state_abbr"], r["case_type"], r["window"])
        findings.append(
            f"**{STATE_NAMES[r['state_abbr']]} {r['case_type'].lower()} runs {r['season_lift']:+.0f}% in "
            f"{season_text(r['window'])}** against an average month (about {r['avg_monthly']:.0f} signed cases in an "
            f"average month). The season brings about {extra:,.0f} extra cases a year, worth {money(dollars)} in "
            f"expected fees.")
    type_finding = len(findings) + 1
    findings.append(
        f"**Case types move on different calendars.** Firm-wide, {type_swing.index[-1].lower()} is the most "
        f"seasonal case type ({type_swing.iloc[-1]:.0f}-point swing) and {type_swing.index[0].lower()} the steadiest "
        f"({type_swing.iloc[0]:.0f} points). Marketing creative and intake scripts should rotate with them.")
    counter = counter_seasonal_states(idx)
    firm_peak = season_text(firm["peak3"])
    pooling_finding = None
    if len(counter):
        names = [STATE_NAMES[s] for s in counter["state"]]
        detail = "; ".join(f"{STATE_NAMES[r.state]} peaks {season_text(r.peak)} and is quietest {season_text(r.trough)}"
                           for r in counter.itertuples())
        pooling_finding = len(findings) + 1
        findings.append(
            f"**{' and '.join(names)} run{'s' if len(names) == 1 else ''} opposite to the firm.** {detail}, "
            f"while the firm as a whole peaks {firm_peak}. Intake staff in "
            f"{'that office' if len(names) == 1 else 'those offices'} are least busy exactly when the rest of the "
            f"firm is busiest: a shared virtual intake team can cover peaks with existing headcount.")
    staffing_finding = len(findings) + 1
    n_busy = len(cost["months"])
    capacity = (f"**Intake reaches capacity in {season_text(cost['months'])}.** Average intake load is "
                f"{cost['busy_load']:.2f}x {'in that month' if n_busy == 1 else 'in those months'} vs "
                f"{cost['rest_load']:.2f}x otherwise; median callback "
                f"slows from {cost['rest_callback']:.0f} to {cost['busy_callback']:.0f} minutes, and the share of leads "
                f"called within 5 minutes falls from {cost['rest_within_5']:.0%} to {cost['busy_within_5']:.0%}. ")
    if loses_cases:
        capacity += (f"Comparing each case type with itself (so the summer case mix is not mistaken for an intake "
                     f"problem), busy months sign {cost['busy_rate']:.1%} of leads vs {cost['rest_rate_same_mix']:.1%} "
                     f"at normal-month rates: about **{cost['lost_cases']:,.0f} signed cases and "
                     f"{money(cost['lost_fees'])} in expected fees a year** left on the table.")
    else:
        capacity += ("Comparing each case type with itself, sign rates hold up in busy months, so the slowdown "
                     "is not yet costing cases. It is the early warning to watch.")
    findings.append(capacity)

    headline = (f"Firm-wide intake is seasonal: signed cases run **{firm['peak_idx'] - 100:+.0f}% in "
                f"{MONTHS[firm['peak'] - 1]}** and **{firm['low_idx'] - 100:+.0f}% in {MONTHS[firm['low'] - 1]}** "
                f"against an average month. The peak season ({season_text(firm['peak3'])}) brings about "
                f"**{firm['extra_cases']:,.0f} more signed cases a year** than three average months, worth "
                f"**{money(firm['extra_fees'])} in expected fees**.")
    headline += (f" Intake is staffed close to flat, so at peak it runs at capacity and loses about "
                 f"{money(cost['lost_fees'])} a year in fees (finding {staffing_finding})." if loses_cases else
                 f" Intake reaches capacity at peak (finding {staffing_finding}); planning for the season keeps it ahead.")

    lines = [
        "# Seasonality Findings",
        "",
        "*Generated by `notebooks/01_seasonality.py` from the BigQuery warehouse. Signed cases, 2017-2024, "
        "COVID months (Mar 2020 - Jun 2021) excluded. Index: 100 = an average month. A peak or trough is "
        "only called when its 95% confidence interval across years excludes 100. Seasons are the best "
        "consecutive 3-month window. Dollar values use the expected fee per signed case (cases signed "
        "2017-2022, lost cases at $0).*",
        "",
        "## Headline",
        "",
        headline,
        "",
        "## Findings",
        "",
        *[f"{i}. {f}" for i, f in enumerate(findings, start=1)],
        "",
        "## Recommendations",
        "",
        "| Decision | Recommendation | Owner | Evidence |",
        "| --- | --- | --- | --- |",
        f"| Staffing | Add seasonal or part-time intake capacity {INTAKE_LEAD_TIME_WEEKS} weeks before each office's "
        f"busy season; firm-wide, intake reaches capacity in {season_start_name(cost['months'])}, so hire by early "
        f"{hire_by} "
        f"| Director of Operations | Finding {staffing_finding} |",
        "| Staffing | Set each office's intake calendar from its own state's index, not a firm-wide average "
        "| Office managers | Finding 1 |",
        *([f"| Staffing | Pilot a shared virtual intake queue so {' and '.join(STATE_NAMES[s] for s in counter['state'])} "
           f"intake covers overflow from busy offices in {firm_peak} (and the reverse in "
           f"{'its' if len(counter) == 1 else 'their'} own peak) "
           f"| Director of Operations | Finding {pooling_finding} |"] if pooling_finding else []),
        f"| Marketing | Shift spend into the 4-6 weeks before each state's peak season; trim in the trough "
        f"({season_text(firm['low3'])} firm-wide) | Marketing | Headline, Finding 1 |",
        f"| Marketing | Rotate ad creative by case type with its season | Marketing | Findings 2-{type_finding} |",
        "| Performance | Judge office intake against its own seasonal expectation, not last month | Director "
        "| Seasonal index (`mart.seasonal_index`) |",
        "",
        "## Hypotheses tested",
        "",
        "| Starting hypothesis | Result | What it means |",
        "| --- | --- | --- |",
        f"| Michigan and Ohio auto intake rises in winter (ice) | "
        f"{winter['verdict']}: MI/OH auto runs {winter['lift']:+.0f}% in Dec-Feb; "
        f"peak seasons are Michigan {season_text(winter['peaks']['MI'])}, Ohio {season_text(winter['peaks']['OH'])} | "
        + {"Supported": "Winter staffing for auto is justified by the data.",
           "Partly supported": "Winter runs above an average month, but the main auto peak is elsewhere. Staff for the "
                               "main peak first; confirm the winter lift with injury-crash data (Phase 2).",
           "Not supported": "Demand here is driven by fatal-crash patterns, which peak with summer driving. Winter "
                            "crashes are more frequent but less often fatal, so fatal-crash data likely understates "
                            "winter injury demand. Do not staff for a winter auto surge yet; test it with Michigan "
                            "and Ohio injury-crash data (Phase 2)."}[winter["verdict"]] + " |",
        f"| Seasonality is the same across the firm | Not supported: swings range from {flattest['swing']:.0f} to "
        f"{biggest['swing']:.0f} points{', and ' + ' and '.join(STATE_NAMES[s] for s in counter['state']) + ' runs opposite' if len(counter) else ''} "
        "| Plan by office, not firm-wide |",
        "",
        "## State calendar",
        "",
        "| State | Peak season | Trough season | Swing (pts) | Extra signed cases/yr in peak season | Expected fees |",
        "| --- | --- | --- | ---: | ---: | ---: |",
        *[f"| {STATE_NAMES[r.state]} | {season_text(r.peak3)} | {season_text(r.low3)} | {r.swing:.0f} | "
          f"{r.extra_cases:,.0f} | {money(r.extra_fees)} |" for r in states.itertuples()],
        "",
        "## Charts",
        "",
        "![State calendar](figures/seasonality_state_heatmap.png)",
        "",
        "![Case-type calendar](figures/seasonality_casetype_heatmap.png)",
        "",
        "![Intake pressure](figures/seasonality_intake_pressure.png)",
        "",
        "## Limits",
        "",
        "- Firm intake is simulated on top of real NHTSA crash and NOAA weather patterns (see `reports/assumptions.md`). "
        "The method transfers to real firm data unchanged; the specific numbers describe the simulated firm.",
        "- Auto, truck, motorcycle, pedestrian and wrongful-death seasonality follows real fatal-crash patterns; "
        "premises, dog-bite and workers' comp seasonality is simulated.",
        "- Seven non-COVID years per calendar month: enough to call large, recurring peaks, not small ones. "
        "Unbolded cells in the heatmaps are within normal year-to-year variation.",
        "- The busy-month case loss is an association, mix-adjusted but not a controlled experiment. The callback "
        "effect itself is validated separately (planted effect S3).",
    ]
    text = "\n".join(lines) + "\n"
    REPORT.write_text(text, encoding="utf-8")
    return text


# %% Save the index to BigQuery for Looker Studio
def save_index(idx: pd.DataFrame) -> None:
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    out = idx.rename(columns={"index": "seasonal_index", "years": "years_used",
                              "avg_monthly": "avg_monthly_signed_cases"})
    client.load_table_from_dataframe(
        out, f"{PROJECT}.mart.seasonal_index",
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")).result()
    print(f"Loaded mart.seasonal_index ({len(out):,} rows)")


# %% Run everything
def run(data: dict[str, pd.DataFrame], upload: bool = True) -> str:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    idx = build_indices(data)
    fees = fee_lookup(data["fee"])
    pressure = intake_pressure(data["office_month"])
    cost = peak_cost(pressure, data["ctm"], fees)

    state = idx[(idx["case_type"] == "All case types") & (idx["state_abbr"] != "Firm")]
    grid = state.pivot(index="state_abbr", columns="month_num", values="index").loc[STATE_ORDER]
    sig = state.pivot(index="state_abbr", columns="month_num", values="significant").loc[STATE_ORDER]
    grid.index = [STATE_NAMES[s] for s in grid.index]
    biggest = (grid.max(axis=1) - grid.min(axis=1)).idxmax()
    heatmap(grid, sig,
            f"Each state runs on its own calendar: {biggest} swings the most",
            "Seasonal index of signed cases (100 = average month), 2017-2024 excl. COVID. "
            "Red = busier, blue = quieter. Bold = real peak or trough (95% CI).",
            FIG_DIR / "seasonality_state_heatmap.png")

    ct = idx[(idx["state_abbr"] == "Firm") & (idx["case_type"] != "All case types")]
    grid = ct.pivot(index="case_type", columns="month_num", values="index")
    sig = ct.pivot(index="case_type", columns="month_num", values="significant")
    order = (grid.max(axis=1) - grid.min(axis=1)).sort_values(ascending=False).index
    grid, sig = grid.loc[order], sig.loc[order]
    heatmap(grid, sig,
            f"{order[0]} is the most seasonal case type; {order[-1].lower()} the steadiest",
            "Firm-wide seasonal index of signed cases (100 = average month), sorted by swing. "
            "Bold = real peak or trough (95% CI).",
            FIG_DIR / "seasonality_casetype_heatmap.png")

    pressure_chart(pressure, cost, FIG_DIR / "seasonality_intake_pressure.png")
    text = write_report(idx, fees, pressure, cost)
    print(f"Wrote {REPORT} and 3 charts in {FIG_DIR}/")
    if upload:
        save_index(idx)
    return text


if __name__ == "__main__":
    import sys
    report = run(load_data(), upload="--no-upload" not in sys.argv)
    print("\n" + report.split("## Recommendations")[0])
