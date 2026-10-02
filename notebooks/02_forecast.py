# %% [markdown]
# # 02 Forecast: how many cases should each office expect, and how sure are we?
#
# **Question for leadership:** How many signed cases (and leads) should each state, case type
# and office expect over the next 12 months, with what range, and how much should we trust it?
#
# **Model** (one per series; 48 state x case-type series for signed cases, 12 office series for leads)
#   log(expected count) = level + month-of-year effect + linear trend + COVID adjustment
# A Poisson regression fitted by IRLS (plain numpy; every coefficient is inspectable). Over-dispersion
# is measured from the residuals, and forecast ranges are simulated from the fitted model, including
# uncertainty in the coefficients themselves. State and firm totals are the sums of the series, so
# every level adds up (bottom-up, coherent by construction).
#
# **What the model is NOT allowed to see:** future crash counts or weather. They are not known on the
# day a forecast is made, so using them would flatter the backtest and fail in production.
#
# **Validation** (rolling origin, on years the model never saw):
#   train 2017-2021 -> forecast 2022;  train 2017-2022 -> forecast 2023;  train 2017-2023 -> forecast 2024
# Compared with two baselines a manager could do in a spreadsheet:
#   seasonal naive  = same month last year
#   seasonal mean   = average of that calendar month in all training years (COVID excluded)
# Error metric: WAPE = sum |actual - forecast| / sum actual. Unlike MAPE, it is not distorted by
# months with very few cases.
#
# **Outputs**
# - `reports/forecast_report.md`: headline, accuracy vs baselines, calibration, confidence tiers, staffing plan
# - `reports/figures/forecast_*.png`
# - `mart.forecast_monthly` in BigQuery: backtest and 2025 forecast rows for Looker Studio

# %%
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT = "pi-intake-forecast"
FIG_DIR = Path("reports/figures")
REPORT = Path("reports/forecast_report.md")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
STATE_NAMES = {"MI": "Michigan", "OH": "Ohio", "PA": "Pennsylvania", "GA": "Georgia", "FL": "Florida", "TX": "Texas"}
STATE_ORDER = ["MI", "OH", "PA", "GA", "FL", "TX"]
FOLDS = [2022, 2023, 2024]           # each fold trains on all earlier years
FORECAST_YEAR = 2025                 # first year after the data
N_SIMS = 2000
# Method settings, chosen automatically by select_method() on the 2022-2023 backtests:
HALF_LIFE_YEARS: float | None = None  # recency weighting: an observation this many years old counts half
BLEND = 0.0                           # weight on same-month-last-year in the final forecast (0 = model only)
CANDIDATES = [(hl, b) for hl in (None, 3.0, 2.0, 1.5) for b in (0.0, 0.3, 0.5)]
SELECTION_FOLDS = [2022, 2023]        # used to choose the method
CONFIRMATION_FOLD = 2024              # held out from the choice, used to confirm it
SEED = 42
INTAKE_CAPACITY = 60                 # leads per intake specialist per month (assumption S10)
STAFF_TO = "p80"                     # staff intake to the 80th percentile of forecast leads
TIERS = [(0.10, "High"), (0.20, "Medium")]  # WAPE thresholds for confidence tiers; above = Low

INK, INK_2, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE, BLUE_BAND, GREY = "#2a78d6", "#b7d3f6", "#898781"
plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2, "axes.edgecolor": AXIS, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE, "axes.spines.top": False,
    "axes.spines.right": False,
})


# %% Load
def to_numpy_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """BigQuery returns pandas nullable types; convert to plain numpy types (see 01_seasonality.py)."""
    df = df.copy()
    for col in df.columns:
        dtype = str(df[col].dtype)
        if dtype == "boolean":
            df[col] = df[col].fillna(False).astype(bool)
        elif dtype in ("Int64", "Int32", "Int16", "Int8"):
            df[col] = df[col].astype("int64" if not df[col].isna().any() else "float64")
        elif dtype in ("Float64", "Float32") or dtype.startswith("decimal"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        elif dtype.startswith("string") or dtype == "str":
            df[col] = df[col].astype(object)
    if "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"])
    return df


def load_data() -> dict[str, pd.DataFrame]:
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    q = lambda sql: to_numpy_dtypes(client.query(sql).to_dataframe())
    return {
        "cases": q(f"""
            SELECT state_abbr, case_type, month, is_covid, SUM(signed_cases) AS y
            FROM `{PROJECT}.mart.office_casetype_month`
            GROUP BY state_abbr, case_type, month, is_covid"""),
        "leads": q(f"""
            SELECT office_id, office, state_abbr, month, is_covid, leads AS y
            FROM `{PROJECT}.mart.office_month`"""),
    }


# %% Model: Poisson regression by IRLS, with over-dispersion and simulated ranges
def design(months: pd.Series, covid: pd.Series) -> np.ndarray:
    """Intercept, 11 month-of-year dummies (Jan = base), linear trend in years since 2017, COVID flag."""
    m = months.dt.month.to_numpy()
    X = np.zeros((len(months), 14))
    X[:, 0] = 1.0
    for k in range(2, 13):
        X[:, k - 1] = (m == k)
    X[:, 12] = (months.dt.year.to_numpy() - 2017) + (m - 1) / 12
    X[:, 13] = covid.to_numpy(dtype=float)
    return X


def fit_poisson(X: np.ndarray, y: np.ndarray, iters: int = 50, ridge: float = 1e-6,
                w: np.ndarray | None = None) -> dict:
    """Iteratively reweighted least squares for a log-link Poisson GLM, with optional observation
    weights w (recency weighting). Returns coefficients, their covariance (scaled by over-dispersion)
    and the dispersion phi."""
    w = np.ones(len(y)) if w is None else w
    keep = X.std(axis=0) > 0
    keep[0] = True
    Xk = X[:, keep]
    beta = np.zeros(Xk.shape[1])
    beta[0] = np.log(max(y.mean(), 0.1))
    for _ in range(iters):
        mu = np.exp(np.clip(Xk @ beta, -20, 20))
        z = Xk @ beta + (y - mu) / mu
        XtW = Xk.T * (mu * w)
        new = np.linalg.solve(XtW @ Xk + ridge * np.eye(len(beta)), XtW @ z)
        if np.max(np.abs(new - beta)) < 1e-8:
            beta = new
            break
        beta = new
    mu = np.exp(np.clip(Xk @ beta, -20, 20))
    n_eff = w.sum() ** 2 / (w ** 2).sum()                              # effective sample size
    dof = max(n_eff - len(beta), 1)
    phi = max(1.0, float((w * (y - mu) ** 2 / mu).sum() / w.sum() * n_eff / dof))   # Pearson over-dispersion
    cov = phi * np.linalg.inv((Xk.T * (mu * w)) @ Xk + ridge * np.eye(len(beta)))
    full = np.zeros(X.shape[1]); full[keep] = beta
    return dict(beta=full, keep=keep, cov=cov, phi=phi)


def simulate(fit: dict, X: np.ndarray, rng: np.random.Generator, n: int | None = None) -> np.ndarray:
    """Draws of future counts: coefficient uncertainty + negative-binomial noise with variance phi*mu."""
    n = n or N_SIMS
    Xk = X[:, fit["keep"]]
    betas = rng.multivariate_normal(fit["beta"][fit["keep"]], fit["cov"], size=n, method="cholesky")
    mu = np.exp(np.clip(betas @ Xk.T, -20, 20))                         # n x horizon
    if fit["phi"] <= 1.0001:
        return rng.poisson(mu).astype(float)
    r = mu / (fit["phi"] - 1)                                           # NB size so that var = phi * mu
    return rng.negative_binomial(r, r / (r + mu)).astype(float)


def forecast_series(hist: pd.DataFrame, future: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """Simulated draws (N_SIMS x len(future)) for one series. Future months are never COVID."""
    if hist["y"].sum() == 0:
        return np.zeros((N_SIMS, len(future)))
    w = None
    if HALF_LIFE_YEARS:
        age = (hist["month"].max() - hist["month"]).dt.days.to_numpy() / 365.25
        w = 0.5 ** (age / HALF_LIFE_YEARS)
    fit = fit_poisson(design(hist["month"], hist["is_covid"]), hist["y"].to_numpy(float), w=w)
    return simulate(fit, design(future["month"], pd.Series(False, index=future.index)), rng)


# %% Baselines
def baselines(hist: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
    """Seasonal naive (same month last year) and seasonal mean (that month's non-COVID average)."""
    h = hist.set_index("month")["y"]
    naive = [h.get(m - pd.DateOffset(years=1), np.nan) for m in future["month"]]
    clean = hist[~hist["is_covid"]]
    means = clean.groupby(clean["month"].dt.month)["y"].mean()
    return pd.DataFrame({"naive": naive, "seasonal_mean": future["month"].dt.month.map(means).to_numpy()},
                        index=future.index)


# %% Run one target (signed cases by state x case type, or leads by office)
def run_target(df: pd.DataFrame, keys: list[str], rng: np.random.Generator,
               years: list[int] | None = None) -> tuple[pd.DataFrame, dict]:
    """Backtest folds + final forecast for every series. Returns long rows and the draws for aggregation."""
    rows, draws = [], {}
    df = df[df["month"] < f"{FORECAST_YEAR}-01-01"].sort_values("month")
    for key, g in df.groupby(keys):
        key = key if isinstance(key, tuple) else (key,)
        for year in years or FOLDS + [FORECAST_YEAR]:
            hist = g[g["month"] < f"{year}-01-01"]
            if year == FORECAST_YEAR:
                future = pd.DataFrame({"month": pd.date_range(f"{year}-01-01", periods=12, freq="MS")})
                actual = np.full(12, np.nan)
            else:
                future = g[g["month"].dt.year == year][["month"]].reset_index(drop=True)
                actual = g[g["month"].dt.year == year]["y"].to_numpy(float)
            sims = forecast_series(hist, future, rng)
            base = baselines(hist, future)
            if BLEND > 0:
                # Combine with same-month-last-year: move each month's draws to the blended centre,
                # keeping the model's spread (as a ratio).
                model_mean = sims.mean(axis=0)
                naive = base["naive"].to_numpy(float)
                target = np.where(np.isnan(naive), model_mean, (1 - BLEND) * model_mean + BLEND * naive)
                sims = sims * np.divide(target, model_mean, out=np.ones_like(target), where=model_mean > 0)
            draws[(key, year)] = sims
            q = np.percentile(sims, [2.5, 10, 50, 80, 90, 97.5], axis=0)
            for i, m in enumerate(future["month"]):
                rows.append(dict(zip(keys, key), month=m, origin_year=year,
                                 kind="forecast" if year == FORECAST_YEAR else "backtest",
                                 actual=actual[i], forecast=sims[:, i].mean(), p025=q[0, i], p10=q[1, i],
                                 p50=q[2, i], p80=q[3, i], p90=q[4, i], p975=q[5, i],
                                 naive=base["naive"].iat[i], seasonal_mean=base["seasonal_mean"].iat[i]))
    return pd.DataFrame(rows), draws


def aggregate(rows: pd.DataFrame, draws: dict, keys: list[str], group: list[str],
              source: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    """Totals for firm or state.
    Point forecast = SUM of the series forecasts (bottom-up), so every level adds up exactly.
    Range = from a model fitted DIRECTLY to the total. Summing independently simulated series would
    assume their surprises cancel out; in reality shocks (a marketing push, a bad-weather year) hit many
    series at once, so the total's own history is the honest guide to its uncertainty. The direct
    model's spread (as a ratio to its mean) is applied around the bottom-up point."""
    out, agg_draws = [], {}
    series = rows.drop_duplicates(keys)[keys]
    groups = series.groupby(group) if group else [((), series)]
    for gkey, members in groups:
        gkey = gkey if isinstance(gkey, tuple) else (gkey,)
        member_keys = [tuple(r) for r in members[keys].to_numpy()]
        mask = source.set_index(keys).index.isin(member_keys)
        total = source[mask].groupby("month", as_index=False).agg(y=("y", "sum"), is_covid=("is_covid", "first"))
        for year in FOLDS + [FORECAST_YEAR]:
            bottom_up = sum(draws[(k, year)] for k in member_keys).mean(axis=0)
            hist = total[total["month"] < f"{year}-01-01"]
            months = pd.DataFrame({"month": pd.date_range(f"{year}-01-01", periods=12, freq="MS")})
            direct = forecast_series(hist, months, rng)
            scaled = direct / direct.mean(axis=0) * bottom_up            # direct spread, bottom-up centre
            agg_draws[(gkey, year)] = scaled
            sub = rows[(rows["origin_year"] == year) & rows.set_index(keys).index.isin(member_keys)]
            parts = sub.groupby("month")[["actual", "naive", "seasonal_mean"]].sum(min_count=1).reindex(months["month"])
            q = np.percentile(scaled, [2.5, 10, 50, 80, 90, 97.5], axis=0)
            for i, m in enumerate(months["month"]):
                out.append(dict(zip(group, gkey), month=m, origin_year=year,
                                kind="forecast" if year == FORECAST_YEAR else "backtest",
                                actual=parts["actual"].iat[i], forecast=bottom_up[i], p025=q[0, i], p10=q[1, i],
                                p50=q[2, i], p80=q[3, i], p90=q[4, i], p975=q[5, i],
                                naive=parts["naive"].iat[i], seasonal_mean=parts["seasonal_mean"].iat[i]))
    return pd.DataFrame(out), agg_draws


def annual_ranges(agg_draws: dict, label: dict | None = None) -> pd.DataFrame:
    """80% range of the ANNUAL total per group, from the simulated monthly paths (not summed monthly
    bounds, which overstate uncertainty because months do not all miss in the same direction)."""
    out = []
    for (gkey, year), sims in agg_draws.items():
        if year != FORECAST_YEAR:
            continue
        total = sims.sum(axis=1)
        name = gkey[0] if gkey else "Firm"
        out.append(dict(group=name, mean=total.mean(), p10=np.percentile(total, 10), p90=np.percentile(total, 90)))
    return pd.DataFrame(out).set_index("group")


# %% Method selection: choose on 2022-2023, confirm on 2024
def level_wapes(case_rows: pd.DataFrame, lead_rows: pd.DataFrame, years: list[int]) -> dict:
    """Point-forecast WAPE (model and same-month-last-year) at each planning level for the given years."""
    c = case_rows[case_rows["origin_year"].isin(years)]
    l = lead_rows[lead_rows["origin_year"].isin(years)]
    firm = c.groupby("month")[["actual", "forecast", "naive"]].sum()
    state = c.groupby(["state_abbr", "month"])[["actual", "forecast", "naive"]].sum()
    out = {}
    for name, d in [("firm", firm), ("state", state), ("segment", c), ("office_leads", l)]:
        out[name] = (wape(d["actual"], d["forecast"]), wape(d["actual"], d["naive"]))
    return out


def select_method(cases: pd.DataFrame, leads: pd.DataFrame) -> tuple[tuple, pd.DataFrame]:
    """Try every candidate setting. Score = average across the four levels of model WAPE / baseline WAPE
    on the SELECTION folds only (below 1.00 = beats same-month-last-year). The winner is then checked on
    the CONFIRMATION fold, which played no part in the choice, so the reported accuracy is not flattered
    by the selection itself."""
    global HALF_LIFE_YEARS, BLEND, N_SIMS
    saved = (HALF_LIFE_YEARS, BLEND, N_SIMS)
    N_SIMS = 300                                   # point forecasts only; fewer draws is enough
    results = []
    years = SELECTION_FOLDS + [CONFIRMATION_FOLD]
    for hl, blend in CANDIDATES:
        HALF_LIFE_YEARS, BLEND = hl, blend
        rng = np.random.default_rng(SEED)
        c_rows, _ = run_target(cases, ["state_abbr", "case_type"], rng, years=years)
        l_rows, _ = run_target(leads, ["office_id", "office", "state_abbr"], rng, years=years)
        sel = level_wapes(c_rows, l_rows, SELECTION_FOLDS)
        conf = level_wapes(c_rows, l_rows, [CONFIRMATION_FOLD])
        results.append(dict(
            half_life=hl, blend=blend,
            selection_score=np.mean([m / n for m, n in sel.values()]),
            confirmation_score=np.mean([m / n for m, n in conf.values()]),
            **{f"sel_{k}": v[0] for k, v in sel.items()},
            **{f"conf_{k}": v[0] for k, v in conf.items()},
            **{f"conf_naive_{k}": v[1] for k, v in conf.items()}))
    HALF_LIFE_YEARS, BLEND, N_SIMS = saved
    table = pd.DataFrame(results).sort_values("selection_score").reset_index(drop=True)
    best = table.iloc[0]
    return (None if pd.isna(best["half_life"]) else float(best["half_life"]), float(best["blend"])), table


def describe_method(hl: float | None, blend: float) -> str:
    parts = ["all years weighted equally" if not hl else f"recent years weighted more (half-life {hl:g} years)"]
    parts.append("model only" if blend == 0 else f"blended {1 - blend:.0%} model / {blend:.0%} same-month-last-year")
    return ", ".join(parts)


# %% Accuracy
def wape(actual: pd.Series, pred: pd.Series) -> float:
    ok = actual.notna() & pred.notna()
    return float((actual[ok] - pred[ok]).abs().sum() / actual[ok].sum()) if actual[ok].sum() else np.nan


def accuracy(bt: pd.DataFrame) -> dict:
    b = bt[bt["kind"] == "backtest"]
    return dict(model=wape(b["actual"], b["forecast"]), naive=wape(b["actual"], b["naive"]),
                seasonal_mean=wape(b["actual"], b["seasonal_mean"]),
                cover80=float(((b["actual"] >= b["p10"]) & (b["actual"] <= b["p90"])).mean()),
                cover95=float(((b["actual"] >= b["p025"]) & (b["actual"] <= b["p975"])).mean()),
                months=len(b))


def noise_floor(mean_per_month: float) -> float:
    """WAPE a PERFECT forecast would still score on Poisson counts with this monthly mean:
    E|Y - mu| / mu, about sqrt(2 / (pi * mu)). Small segments cannot be forecast tightly month by month."""
    return float(np.sqrt(2 / (np.pi * mean_per_month))) if mean_per_month > 0 else np.nan


def quarterly_wape(g: pd.DataFrame) -> float:
    q = g.assign(q=g["month"].dt.to_period("Q")).groupby("q")[["actual", "forecast"]].sum()
    return wape(q["actual"], q["forecast"])


def tier(w: float) -> str:
    for limit, name in TIERS:
        if w <= limit:
            return name
    return "Low"


# %% Charts
def firm_chart(firm: pd.DataFrame, hist: pd.DataFrame, acc: dict, path: Path) -> None:
    """Monthly firm signed cases: history, then the 2025 forecast with its 80% range."""
    fc = firm[firm["kind"] == "forecast"]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.plot(hist["month"], hist["y"], color=GREY, linewidth=1.6, label="Actual")
    ax.fill_between(fc["month"], fc["p10"], fc["p90"], color=BLUE_BAND, linewidth=0, label="80% range")
    ax.plot(fc["month"], fc["forecast"], color=BLUE, linewidth=2, label="Forecast")
    ax.axvline(pd.Timestamp(f"{FORECAST_YEAR}-01-01"), color=AXIS, linewidth=1, linestyle=(0, (4, 3)))
    lo = min(hist["y"].min(), fc["p10"].min())
    ax.set_ylim(lo * 0.85, None)
    ax.text(pd.Timestamp(f"{FORECAST_YEAR}-01-01") - pd.Timedelta(days=20), lo * 0.88, f"{FORECAST_YEAR} forecast \u2192",
            fontsize=9, color=INK_2, ha="right", va="bottom")
    ax.set_ylabel("Signed cases per month")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.tick_params(length=0)
    ax.legend(loc="upper left", frameon=False, ncol=3, fontsize=9)
    total = fc["forecast"].sum()
    fig.text(0.01, 0.97, f"The firm should sign about {total:,.0f} cases in {FORECAST_YEAR}",
             fontsize=13, fontweight="bold", va="top")
    fig.text(0.01, 0.905, f"Monthly signed cases, all offices. Backtest error {acc['model']:.1%} (WAPE) vs "
             f"{acc['naive']:.1%} for same-month-last-year. Shaded: 80% range per month.",
             fontsize=9.5, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def accuracy_chart(table: pd.DataFrame, path: Path) -> None:
    """Backtest WAPE by level: model vs the same-month-last-year baseline. Lower is better."""
    fig, ax = plt.subplots(figsize=(10, 3.9))
    y = np.arange(len(table))
    h = 0.36
    ax.barh(y - h / 2 - 0.02, table["naive"] * 100, height=h, color="#b9b8b2", label="Same month last year")
    ax.barh(y + h / 2 + 0.02, table["model"] * 100, height=h, color=BLUE, label="Model")
    for i, r in enumerate(table.itertuples()):
        ax.text(r.naive * 100 + 0.3, i - h / 2 - 0.02, f"{r.naive:.1%}", va="center", fontsize=9, color=INK_2)
        ax.text(r.model * 100 + 0.3, i + h / 2 + 0.02, f"{r.model:.1%}", va="center", fontsize=9,
                fontweight="bold")
    ax.set_yticks(y, table["level"])
    ax.invert_yaxis()
    ax.set_xlabel("Backtest error, WAPE (%)  - lower is better")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.tick_params(length=0)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    ax.set_xlim(0, max(table["naive"].max(), table["model"].max()) * 100 * 1.18)
    ax.set_axisbelow(True)
    cuts = 1 - table["model"] / table["naive"]
    if (cuts > 0).all():
        title = f"The model beats same-month-last-year at every level, cutting error {cuts.min():.0%}-{cuts.max():.0%}"
    else:
        title = f"The model beats same-month-last-year at {(cuts > 0).sum()} of {len(cuts)} levels"
    fig.text(0.01, 0.97, title, fontsize=13, fontweight="bold", va="top")
    fig.text(0.01, 0.9, f"Backtest on {', '.join(map(str, FOLDS))}, each forecast from data the model never saw.",
             fontsize=9.5, color=INK_2, va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.85))
    fig.savefig(path, dpi=200)
    plt.close(fig)


# %% Report
def write_report(levels: dict[str, pd.DataFrame], acc: dict[str, dict], tiers: pd.DataFrame,
                 staffing: pd.DataFrame, cases_hist: pd.DataFrame, annual: pd.DataFrame,
                 selection: pd.DataFrame) -> str:
    last_year = cases_hist[cases_hist["month"].dt.year == FORECAST_YEAR - 1]["y"].sum()
    total, lo, hi = annual.loc["Firm", ["mean", "p10", "p90"]]
    a_f, a_s, a_t = acc["firm"], acc["state"], acc["state_type"]
    best = selection.iloc[0]
    conf = {k: (best[f"conf_{k}"], best[f"conf_naive_{k}"]) for k in ["firm", "state", "segment", "office_leads"]}
    wins = [k for k, (m, n) in conf.items() if m < n]
    firm_m, firm_n = conf["firm"]
    cut = 1 - firm_m / firm_n

    st = annual.drop(index="Firm")
    hist_by_state = cases_hist[cases_hist["month"].dt.year == FORECAST_YEAR - 1].groupby("state_abbr")["y"].sum()
    tier_counts = tiers["tier"].value_counts()
    high_share = tiers.loc[tiers["tier"] == "High", "forecast_2025"].sum() / tiers["forecast_2025"].sum()
    peak = staffing.groupby("month")["specialists_needed"].sum()
    trough_n, peak_n = int(peak.min()), int(peak.max())
    peak_month = MONTHS[peak.idxmax().month - 1]

    level_names = {"firm": "firm", "state": "state", "segment": "segment", "office_leads": "office-lead"}
    lines = [
        "# Forecast Report",
        "",
        f"*Generated by `notebooks/02_forecast.py`. Signed cases and leads, trained on 2017-{FORECAST_YEAR - 1}; "
        f"backtested on {', '.join(map(str, FOLDS))}, each year forecast only from the years before it. "
        "WAPE = total absolute error / total actual.*",
        "",
        "## Headline",
        "",
        f"The firm should sign about **{total:,.0f} cases in {FORECAST_YEAR}** (80% range {lo:,.0f}-{hi:,.0f}), "
        f"vs {last_year:,.0f} in {FORECAST_YEAR - 1} ({total / last_year - 1:+.1%}). "
        f"On {CONFIRMATION_FOLD}, a year held out from every modeling choice, the firm-level monthly error was "
        f"**{firm_m:.1%}** vs {firm_n:.1%} for the same-month-last-year method"
        + (f" ({cut:.0%} better)" if cut > 0 else "") + ". "
        + (f"The forecast beats that baseline at all four planning levels, so it is ready for staffing and budget "
           f"planning." if len(wins) == 4 else
           f"It beats the baseline at {len(wins)} of 4 levels ({', '.join(level_names[w] for w in wins)}); "
           f"where it does not, use the two side by side."),
        "",
        "## How the method was chosen",
        "",
        f"{len(selection)} candidate methods were scored on {' and '.join(map(str, SELECTION_FOLDS))} only: plain or "
        "recency-weighted models, alone or blended with same-month-last-year (combining forecasts is one of the most "
        "reliable ways to cut error). Score = average across the four levels of model error / baseline error; "
        f"below 1.00 beats the baseline. The winner was then checked on {CONFIRMATION_FOLD}, which played no part "
        f"in the choice. **Chosen: {describe_method(HALF_LIFE_YEARS, BLEND)}.**",
        "",
        f"| Rank | Method | Score {'-'.join(map(str, SELECTION_FOLDS))} (choice) | Score {CONFIRMATION_FOLD} (check) |",
        "| ---: | --- | ---: | ---: |",
        *[f"| {i + 1} | {describe_method(None if pd.isna(r.half_life) else r.half_life, r.blend)} | "
          f"{r.selection_score:.3f} | {r.confirmation_score:.3f} |" for i, r in enumerate(selection.head(5).itertuples())],
        "",
        f"**{CONFIRMATION_FOLD} check, by level** (model vs same month last year): "
        + "; ".join(f"{level_names[k]} {m:.1%} vs {n:.1%}" for k, (m, n) in conf.items()) + ".",
        "",
        "## Accuracy on unseen years",
        "",
        f"All three backtest years with the chosen method. {' and '.join(map(str, SELECTION_FOLDS))} also informed "
        f"the choice of method, so the {CONFIRMATION_FOLD} check above is the cleanest single measure.",
        "",
        "| Level | Series | Model WAPE | Same month last year | Seasonal average | 80% range held | 95% range held |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        *[f"| {name} | {n} | **{a['model']:.1%}** | {a['naive']:.1%} | {a['seasonal_mean']:.1%} | "
          f"{a['cover80']:.0%} | {a['cover95']:.0%} |"
          for name, n, a in [("Firm", 1, a_f), ("State", 6, a_s), ("State x case type", 48, a_t),
                             ("Office leads", 12, acc["office_leads"])]],
        "",
        f"**Are the ranges honest?** A well-calibrated 80% range should hold about 80% of actual months. "
        f"It held {a_f['cover80']:.0%} at firm level, {a_s['cover80']:.0%} at state level and {a_t['cover80']:.0%} "
        "for segments. "
        + ("The ranges are trustworthy for planning." if all(0.72 <= a["cover80"] <= 0.88 for a in (a_f, a_s, a_t)) else
           ("Some ranges are too narrow: treat them as optimistic and plan to the 95% range."
            if min(a["cover80"] for a in (a_f, a_s, a_t)) < 0.72
            else "Some ranges are wider than needed: they are safe, if conservative.")),
        "",
        *[f"**Where the model does not win:** at {name} level the simple seasonal average ({a['seasonal_mean']:.1%}) "
          f"matches or beats the model ({a['model']:.1%}). Small segments carry little trend to learn, so the "
          "model's extra terms add noise there. Use the model where it wins, and roll small segments up."
          for name, a in [("firm", a_f), ("state", a_s), ("segment", a_t)] if a["model"] >= a["seasonal_mean"] - 0.002],
        "",
        "## Forecast by state",
        "",
        f"| State | {FORECAST_YEAR - 1} actual | {FORECAST_YEAR} forecast | Change | 80% range |",
        "| --- | ---: | ---: | ---: | --- |",
        *[f"| {STATE_NAMES[s]} | {hist_by_state.get(s, 0):,.0f} | {st.loc[s, 'mean']:,.0f} | "
          f"{st.loc[s, 'mean'] / hist_by_state.get(s, np.nan) - 1:+.1%} | {st.loc[s, 'p10']:,.0f}-{st.loc[s, 'p90']:,.0f} |"
          for s in STATE_ORDER if s in st.index],
        "",
        "## How much to trust each segment",
        "",
        "Small segments are noisy month to month no matter how good the model is: a segment averaging 10 cases "
        "a month carries about 25% error from pure chance, even with a perfect forecast (the *noise floor*). "
        "So each state x case-type segment is tiered on its **quarterly** backtest error, the grain at which a "
        f"small case type is planned: **High** (WAPE up to {TIERS[0][0]:.0%}), **Medium** (up to {TIERS[1][0]:.0%}), "
        f"**Low** (above). {tier_counts.get('High', 0)} segments are High, {tier_counts.get('Medium', 0)} Medium and "
        f"{tier_counts.get('Low', 0)} Low; High segments carry {high_share:.0%} of forecast volume. "
        f"Month by month, the model's error is on average {tiers['vs_floor'].median():.2f}x the noise floor "
        "(1.00x = as good as any forecast can be).",
        "",
        "| Case type | " + " | ".join(STATE_NAMES[s] for s in STATE_ORDER) + " |",
        "| --- | " + " | ".join(":---:" for _ in STATE_ORDER) + " |",
        *[f"| {ct} | " + " | ".join(f"{g.set_index('state_abbr').loc[s, 'tier']} ({g.set_index('state_abbr').loc[s, 'wape']:.0%})"
                                    for s in STATE_ORDER) + " |"
          for ct, g in tiers.groupby("case_type")],
        "",
        "*Cells: tier (quarterly WAPE).*",
        "",
        "## Intake staffing plan",
        "",
        f"Intake is staffed to the **80th percentile** of forecast leads ({INTAKE_CAPACITY} leads per specialist a "
        f"month), so a busier-than-expected month is covered 4 times in 5 without overtime. Firm-wide the plan needs "
        f"**{trough_n} specialists in the quietest month and {peak_n} at peak ({peak_month})**: a swing of "
        f"{peak_n - trough_n} seasonal or shared roles, not permanent hires.",
        "",
        "| Office | Quietest month | Specialists | Busiest month | Specialists |",
        "| --- | --- | ---: | --- | ---: |",
        *[(f"| {o} | Flat all year | {g['specialists_needed'].min()} | Flat all year | {g['specialists_needed'].max()} |"
           if g["specialists_needed"].nunique() == 1 else
           f"| {o} | {MONTHS[g.loc[g['specialists_needed'].idxmin(), 'month'].month - 1]} | "
           f"{g['specialists_needed'].min()} | {MONTHS[g.loc[g['specialists_needed'].idxmax(), 'month'].month - 1]} | "
           f"{g['specialists_needed'].max()} |") for o, g in staffing.groupby("office")],
        "",
        "## Charts",
        "",
        "![Firm forecast](figures/forecast_firm.png)",
        "",
        "![Accuracy vs baseline](figures/forecast_accuracy.png)",
        "",
        "## Limits",
        "",
        "- Calendar-only model: it knows seasonality, trend and COVID, not future marketing changes, new offices or "
        "law changes. When those are planned, adjust the forecast explicitly and record the adjustment.",
        "- One-year horizon. Beyond that, trend uncertainty dominates.",
        "- Firm data is simulated on real crash and weather patterns; the method transfers unchanged to real data.",
        "- Annual ranges come from the simulated totals, so they are narrower than adding up monthly ranges: "
        "months do not all miss in the same direction.",
    ]
    text = "\n".join(lines) + "\n"
    REPORT.write_text(text, encoding="utf-8")
    return text


# %% Save to BigQuery for Looker Studio
def save_forecasts(levels: dict[str, pd.DataFrame]) -> None:
    from google.cloud import bigquery
    frames = []
    for level, df in levels.items():
        d = df.copy()
        d["level"] = level
        d["metric"] = "leads" if level == "office_leads" else "signed_cases"
        frames.append(d)
    out = pd.concat(frames, ignore_index=True)
    cols = ["level", "metric", "state_abbr", "case_type", "office_id", "office", "month", "origin_year", "kind",
            "actual", "forecast", "p025", "p10", "p50", "p80", "p90", "p975", "naive", "seasonal_mean"]
    for c in cols:
        if c not in out:
            out[c] = None
    out = out[cols]
    out["month"] = pd.to_datetime(out["month"]).dt.date
    client = bigquery.Client(project=PROJECT)
    client.load_table_from_dataframe(out, f"{PROJECT}.mart.forecast_monthly",
                                     job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")).result()
    print(f"Loaded mart.forecast_monthly ({len(out):,} rows)")


# %% Run everything
def run(data: dict[str, pd.DataFrame], upload: bool = True) -> str:
    global HALF_LIFE_YEARS, BLEND
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    cases, leads = data["cases"], data["leads"]

    print(f"Choosing the method: {len(CANDIDATES)} candidates scored on {SELECTION_FOLDS}...")
    (HALF_LIFE_YEARS, BLEND), selection = select_method(cases, leads)
    print(f"Chosen: {describe_method(HALF_LIFE_YEARS, BLEND)}")
    rng = np.random.default_rng(SEED)

    print("Forecasting 48 state x case-type series (3 backtest years + final)...")
    st_rows, st_draws = run_target(cases, ["state_abbr", "case_type"], rng)
    print("Forecasting 12 office lead series...")
    ld_rows, _ = run_target(leads, ["office_id", "office", "state_abbr"], rng)

    print("Building firm and state totals...")
    firm_rows, firm_draws = aggregate(st_rows, st_draws, ["state_abbr", "case_type"], [], cases, rng)
    state_rows, state_draws = aggregate(st_rows, st_draws, ["state_abbr", "case_type"], ["state_abbr"], cases, rng)
    levels = {
        "firm": firm_rows,
        "state": state_rows,
        "state_type": st_rows,
        "office_leads": ld_rows,
    }
    acc = {k: accuracy(v) for k, v in levels.items()}

    bt = st_rows[st_rows["kind"] == "backtest"]
    tiers = (bt.groupby(["state_abbr", "case_type"])
               .apply(lambda g: pd.Series({"monthly_wape": wape(g["actual"], g["forecast"]),
                                           "wape": quarterly_wape(g),
                                           "floor": noise_floor(g["actual"].mean())}), include_groups=False)
               .reset_index())
    tiers["tier"] = tiers["wape"].map(tier)
    tiers["vs_floor"] = tiers["monthly_wape"] / tiers["floor"]
    vol = st_rows[st_rows["kind"] == "forecast"].groupby(["state_abbr", "case_type"])["forecast"].sum()
    tiers = tiers.merge(vol.rename("forecast_2025").reset_index(), on=["state_abbr", "case_type"])

    staffing = ld_rows[ld_rows["kind"] == "forecast"][["office", "month", "forecast", "p80"]].copy()
    staffing["specialists_needed"] = np.ceil(staffing[STAFF_TO] / INTAKE_CAPACITY).astype(int)

    firm_hist = cases.groupby("month", as_index=False)["y"].sum()
    firm_hist = firm_hist[firm_hist["month"] < f"{FORECAST_YEAR}-01-01"]
    firm_chart(levels["firm"], firm_hist, acc["firm"], FIG_DIR / "forecast_firm.png")
    acc_table = pd.DataFrame([dict(level=n, model=acc[k]["model"], naive=acc[k]["naive"]) for n, k in
                              [("Firm", "firm"), ("State", "state"), ("State x case type", "state_type"),
                               ("Office leads", "office_leads")]])
    accuracy_chart(acc_table, FIG_DIR / "forecast_accuracy.png")

    annual = pd.concat([annual_ranges(firm_draws), annual_ranges(state_draws)])
    text = write_report(levels, acc, tiers, staffing, cases, annual, selection)
    print(f"Wrote {REPORT} and 2 charts in {FIG_DIR}/")
    if upload:
        save_forecasts(levels)
    return text


if __name__ == "__main__":
    import sys
    report = run(load_data(), upload="--no-upload" not in sys.argv)
    print("\n" + report.split("## Forecast by state")[0])
