"""
Simulate the firm's internal data on top of real public data.

The public data (FARS crashes, NOAA weather) sets WHEN and WHERE demand happens.
This script generates what a real firm's systems would hold: leads, signed cases,
settlements, marketing spend and staff. Every rate comes from reports/assumptions.md.

Three effects are PLANTED on purpose, so later we can prove the models find them:
  S3  Leads called back within 5 minutes sign about 1.5x as often as after 1 hour.
  S4  Michigan and Ohio auto leads rise with snow days (beyond what fatal crashes show).
  S11 Case managers above 1.3x benchmark caseload quit about twice as often.
The true values are written to data/simulated/planted_truth.json.

Inputs
  data/raw/fars_crashes_6states.csv      made by pipelines/pull_fars.py
  raw.weather_monthly (BigQuery)         made by sql/01_raw_weather_monthly.sql

Outputs (CSV in data/simulated/, and BigQuery tables in the raw dataset)
  sim_offices, sim_leads, sim_cases, sim_marketing_spend, sim_employees, sim_employee_months

Run from the project root:
  python pipelines/simulate_firm.py              # simulate and load to BigQuery
  python pipelines/simulate_firm.py --no-upload  # simulate and save CSVs only
  python pipelines/simulate_firm.py --refresh-weather  # after rebuilding raw.weather_monthly
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = "pi-intake-forecast"
SEED = 42
SIM_START = "2013-01-01"   # firm history starts 4 years before public data, so caseloads and payments are mature by 2017
SIM_END = "2024-12-01"     # last month of leads (FARS ends 2024)
AS_OF = pd.Timestamp("2025-12-31")  # snapshot date: payments after this are not yet known
FARS_CSV = Path("data/raw/fars_crashes_6states.csv")
WEATHER_CACHE = Path("data/raw/weather_monthly.csv")
OUT_DIR = Path("data/simulated")

# ---------------------------------------------------------------------------
# Firm setup (see reports/scope.md and reports/assumptions.md)
# ---------------------------------------------------------------------------
OFFICES = pd.DataFrame(
    [
        ("DET", "Detroit", "MI", "26163", 1.00),
        ("GRR", "Grand Rapids", "MI", "26081", 0.55),
        ("CMH", "Columbus", "OH", "39049", 0.85),
        ("CLE", "Cleveland", "OH", "39035", 0.80),
        ("PHL", "Philadelphia", "PA", "42101", 1.05),
        ("PIT", "Pittsburgh", "PA", "42003", 0.70),
        ("ATL", "Atlanta", "GA", "13121", 1.10),
        ("SAV", "Savannah", "GA", "13051", 0.45),
        ("MIA", "Miami", "FL", "12086", 1.25),
        ("TPA", "Tampa", "FL", "12057", 0.90),
        ("HOU", "Houston", "TX", "48201", 1.35),
        ("DAL", "Dallas", "TX", "48113", 1.15),
    ],
    columns=["office_id", "office", "state_abbr", "county_fips", "market_size"],
)
BASE_LEADS = 120            # leads per month for an office of market_size 1.0
STATE_GROWTH = {"MI": 0.0, "OH": 0.0, "PA": 0.0, "GA": 0.02, "FL": 0.02, "TX": 0.025}  # yearly

# case_type: lead share, base sign rate, median settlement $, suit probability, median months to pay, demand signal
CASE_TYPES = pd.DataFrame(
    [
        ("Auto", 0.52, 0.22, 18_000, 0.15, 13, "auto"),
        ("Commercial truck", 0.05, 0.26, 120_000, 0.30, 22, "truck"),
        ("Motorcycle", 0.05, 0.24, 45_000, 0.20, 16, "moto"),
        ("Pedestrian & bicycle", 0.06, 0.23, 55_000, 0.20, 16, "ped"),
        ("Premises liability", 0.14, 0.16, 25_000, 0.20, 15, "premises"),
        ("Dog bite", 0.04, 0.20, 20_000, 0.10, 11, "dog"),
        ("Workers' compensation", 0.11, 0.18, 15_000, 0.15, 10, "wc"),
        ("Wrongful death", 0.03, 0.26, 350_000, 0.30, 24, "death"),
    ],
    columns=["case_type", "lead_share", "sign_rate", "settlement_median", "suit_prob", "months_to_pay", "signal"],
)
STATE_VALUE = {"MI": 0.90, "OH": 0.85, "PA": 1.05, "GA": 1.10, "FL": 1.00, "TX": 0.90}
FL_REFORM_DATE = pd.Timestamp("2023-03-24")  # Florida tort reform: lower values afterwards
FL_REFORM_VALUE = 0.85
LOSS_RATE = 0.08            # share of cases that end with no recovery

# lead source: share, sign-rate multiplier, case-value multiplier
SOURCES = pd.DataFrame(
    [
        ("TV", 0.30, 0.95, 1.00),
        ("Digital", 0.30, 1.00, 0.95),
        ("Referral", 0.15, 1.15, 1.20),
        ("Organic web", 0.15, 1.05, 1.00),
        ("Billboard & radio", 0.10, 0.95, 1.00),
    ],
    columns=["source", "share", "sign_mult", "value_mult"],
)

# PLANTED S3: callback speed -> sign-rate multiplier
RESPONSE_BANDS = [(5, 1.50), (15, 1.30), (60, 1.15), (np.inf, 1.00)]

# PLANTED S4: MI/OH auto leads x (1 + this x snow_days)
SNOW_AUTO_EFFECT = 0.02

# Marketing: monthly budget per unit of market size, diminishing returns on leads
BASE_SPEND = 75_000
SPEND_ELASTICITY = 0.35
CHANNEL_MIX = {"TV": 0.35, "Digital": 0.35, "Billboard & radio": 0.15, "Sponsorships": 0.15}
CAMPAIGNS = [  # office, start month, channel, extra spend share
    ("HOU", "2021-03-01", "TV", 0.60),
    ("ATL", "2023-09-01", "Digital", 0.50),
]
COVID_LEADS = {"2020-04": 0.70, "2020-05": 0.75, "2020-06": 0.85}  # fewer minor crashes in lockdown

# Staff roles: what drives workload, capacity per person, base monthly quit rate, hiring lag (months)
ROLES = {
    "Intake specialist":    ("leads", 60, 0.035, 2),
    "Case manager":         ("open_cases", 70, 0.022, 3),
    "Demand writer":        ("open_cases", 250, 0.020, 3),
    "Litigation paralegal": ("open_suits", 60, 0.018, 3),
    "Associate attorney":   ("open_cases", 150, 0.015, 4),
}
LEAN_STAFFING = 0.9   # firms staff to 90% of trailing workload, so peaks and quits create overload
QUIT_SEASON = {1: 1.4, 2: 1.4, 3: 1.4, 7: 1.2, 8: 1.2}  # after bonuses (Q1) and summer
OVERLOAD_LINE = 1.3
CM_OVERLOAD_QUIT_MULT = 2.0      # PLANTED S11
OTHER_OVERLOAD_QUIT_MULT = 1.3


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def load_inputs(refresh_weather: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not FARS_CSV.exists():
        raise SystemExit(f"{FARS_CSV} not found. Run pipelines/pull_fars.py first.")
    fars = pd.read_csv(FARS_CSV)

    if WEATHER_CACHE.exists() and not refresh_weather:
        weather = pd.read_csv(WEATHER_CACHE)
    else:
        from google.cloud import bigquery
        sql = f"SELECT office, year, month, snow_days, rain_days, freeze_days FROM `{PROJECT}.raw.weather_monthly`"
        weather = bigquery.Client(project=PROJECT).query(sql).to_dataframe()
        weather.to_csv(WEATHER_CACHE, index=False)
    return fars, weather


def build_demand_index(fars: pd.DataFrame, months: pd.DatetimeIndex) -> pd.DataFrame:
    """Monthly demand index per state and crash signal (1.0 = that state's average month).
    Blends the actual month with the same calendar month's average to cut noise in small counts.
    Months before FARS coverage use the calendar-month average."""
    f = fars.copy()
    for col in ["has_large_truck", "has_motorcycle", "has_pedestrian"]:
        f[col] = f[col].astype(str).str.lower().isin(["true", "1"])
    f["ym"] = pd.to_datetime(dict(year=f["year"], month=f["month"], day=1))
    agg = f.groupby(["state_abbr", "ym"]).agg(
        auto=("crash_id", "count"),
        truck=("has_large_truck", "sum"),
        moto=("has_motorcycle", "sum"),
        ped=("has_pedestrian", "sum"),
        death=("fatalities", "sum"),
    )
    fars_months = pd.date_range(f["ym"].min(), f["ym"].max(), freq="MS")
    grid = pd.MultiIndex.from_product([sorted(f["state_abbr"].unique()), fars_months], names=["state_abbr", "ym"])
    agg = agg.reindex(grid, fill_value=0).astype(float)

    idx = agg / agg.groupby(level="state_abbr").transform("mean")
    cal = idx.groupby([idx.index.get_level_values("state_abbr"), idx.index.get_level_values("ym").month]).mean()
    cal.index.names = ["state_abbr", "cal_month"]

    rows = []
    for state in agg.index.get_level_values("state_abbr").unique():
        for m in months:
            cal_val = cal.loc[(state, m.month)]
            if (state, m) in idx.index:
                rows.append((state, m, *(0.5 * idx.loc[(state, m)] + 0.5 * cal_val).values))
            else:
                rows.append((state, m, *cal_val.values))
    return pd.DataFrame(rows, columns=["state_abbr", "ym", *agg.columns]).set_index(["state_abbr", "ym"])


def build_weather(weather: pd.DataFrame, months: pd.DatetimeIndex) -> pd.DataFrame:
    """Snow, rain and freeze days per office-month; months without data use that office's calendar-month average."""
    w = weather.merge(OFFICES[["office", "office_id"]], on="office")
    w["ym"] = pd.to_datetime(dict(year=w["year"], month=w["month"], day=1))
    w = w.set_index(["office_id", "ym"])[["snow_days", "rain_days", "freeze_days"]].astype(float)
    cal = w.groupby([w.index.get_level_values(0), w.index.get_level_values(1).month]).mean()
    grid = pd.MultiIndex.from_product([OFFICES["office_id"], months], names=["office_id", "ym"])
    out = w.reindex(grid)
    for col in out.columns:
        fill = [cal.loc[(o, m.month), col] for o, m in out.index]
        out[col] = out[col].fillna(pd.Series(fill, index=out.index))
    return out.fillna(0.0)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
def marketing_plan(months: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for o in OFFICES.itertuples():
        budget = BASE_SPEND * o.market_size
        for m in months:
            for channel, share in CHANNEL_MIX.items():
                spend = budget * share * rng.normal(1.0, 0.05)
                for c_office, c_start, c_channel, extra in CAMPAIGNS:
                    if o.office_id == c_office and channel == c_channel and m >= pd.Timestamp(c_start):
                        spend += budget * extra
                rows.append((o.office_id, m, channel, round(spend, 2)))
    return pd.DataFrame(rows, columns=["office_id", "month", "channel", "spend"])


def seasonal_wave(month: int, amplitude: float) -> float:
    return 1 + amplitude * np.cos(2 * np.pi * (month - 7) / 12)  # peaks in July


def response_multiplier(minutes: np.ndarray) -> np.ndarray:
    mult = np.ones_like(minutes)
    for limit, value in reversed(RESPONSE_BANDS):
        mult = np.where(minutes <= limit, value, mult)
    return mult


def simulate(fars: pd.DataFrame, weather: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    months = pd.date_range(SIM_START, SIM_END, freq="MS")
    demand = build_demand_index(fars, months)
    wx = build_weather(weather, months)
    spend = marketing_plan(months, rng)
    spend_total = spend.groupby(["office_id", "month"])["spend"].sum()

    wx_mean = wx.groupby(level="office_id").mean()
    ct = CASE_TYPES.set_index("case_type")
    src = SOURCES.set_index("source")
    lead_rows, case_rows, emp_rows, emp_month_rows = [], [], [], []
    next_lead, next_case, next_emp = 1, 1, 1

    for o in OFFICES.itertuples():
        staff = []      # active employees: dicts
        pending = []    # (start_month_index, role)
        sign_dates, pay_dates, suits = [], [], []  # for open-caseload tracking
        lead_history = []

        def hire(role: str, month: pd.Timestamp) -> None:
            nonlocal next_emp
            staff.append({"employee_id": f"E{next_emp:05d}", "office_id": o.office_id, "role": role,
                          "hire_date": month + pd.Timedelta(days=int(rng.integers(0, 28))),
                          "term_date": pd.NaT})
            next_emp += 1

        # opening headcount
        for role, (driver, cap, _, _) in ROLES.items():
            start_n = int(np.ceil(BASE_LEADS * o.market_size / cap)) if driver == "leads" else 1
            for _ in range(start_n):
                hire(role, months[0] - pd.DateOffset(months=int(rng.integers(1, 36))))

        for t, m in enumerate(months):
            month_end = m + pd.offsets.MonthEnd(0)
            # --- new hires who start this month
            for start_t, role in [p for p in pending if p[0] == t]:
                hire(role, m)
            pending = [p for p in pending if p[0] != t]

            # --- leads
            n_intake = sum(1 for s in staff if s["role"] == "Intake specialist")
            years = (m.year - 2017) + (m.month - 1) / 12
            trend = (1 + STATE_GROWTH[o.state_abbr]) ** years
            mkt = (spend_total.loc[(o.office_id, m)] / (BASE_SPEND * o.market_size)) ** SPEND_ELASTICITY
            covid = COVID_LEADS.get(m.strftime("%Y-%m"), 1.0)
            w = wx.loc[(o.office_id, m)]
            dem = demand.loc[(o.state_abbr, m)]

            month_leads = []
            for c in CASE_TYPES.itertuples():
                if c.signal in dem.index:
                    idx = dem[c.signal]
                elif c.signal == "premises":
                    idx = 1 + 0.03 * (w.snow_days - wx_mean.loc[o.office_id, "snow_days"]) \
                            + 0.015 * (w.rain_days - wx_mean.loc[o.office_id, "rain_days"]) \
                            + 0.01 * (w.freeze_days - wx_mean.loc[o.office_id, "freeze_days"])
                elif c.signal == "dog":
                    idx = seasonal_wave(m.month, 0.25)
                else:  # workers' comp
                    idx = seasonal_wave(m.month, 0.08)
                if c.case_type == "Auto" and o.state_abbr in ("MI", "OH"):
                    idx *= 1 + SNOW_AUTO_EFFECT * w.snow_days            # PLANTED S4
                mean = BASE_LEADS * o.market_size * c.lead_share * max(idx, 0.3) * trend * mkt * covid
                n = rng.poisson(mean * rng.lognormal(0, 0.06))
                month_leads.append((c.case_type, n))
            total_leads = sum(n for _, n in month_leads)
            lead_history.append(total_leads)

            # callback speed depends on how stretched intake is
            load = total_leads / max(n_intake * ROLES["Intake specialist"][1], 1)
            median_min = float(np.clip(10 * load ** 2.5, 2, 240))

            for case_type, n in month_leads:
                if n == 0:
                    continue
                c = ct.loc[case_type]
                days = rng.integers(0, month_end.day, n)
                lead_dates = m + pd.to_timedelta(days, unit="D")
                sources = rng.choice(SOURCES["source"].to_numpy(), n, p=SOURCES["share"].to_numpy())
                minutes = np.round(rng.lognormal(np.log(median_min), 0.9, n), 1)
                p_sign = c.sign_rate * response_multiplier(minutes) * src.loc[sources, "sign_mult"].to_numpy()
                signed = rng.random(n) < np.clip(p_sign, 0, 0.9)

                for i in range(n):
                    lead_id = f"L{next_lead:07d}"
                    next_lead += 1
                    lead_rows.append((lead_id, o.office_id, lead_dates[i].date(), case_type, sources[i],
                                      minutes[i], bool(signed[i])))
                    if not signed[i]:
                        continue
                    sign_date = lead_dates[i] + pd.Timedelta(days=int(rng.integers(0, 8)))
                    suit = rng.random() < c.suit_prob
                    k = 1.6
                    median_m = c.months_to_pay * (1.4 if suit else 1.0)
                    scale = median_m / np.log(2) ** (1 / k)
                    months_to_pay = max(1.0, scale * rng.weibull(k))
                    close_date = sign_date + pd.Timedelta(days=int(months_to_pay * 30.4))
                    state_value = STATE_VALUE[o.state_abbr]
                    if o.state_abbr == "FL" and sign_date >= FL_REFORM_DATE:
                        state_value *= FL_REFORM_VALUE
                    lost = rng.random() < LOSS_RATE
                    settlement = 0.0 if lost else float(
                        rng.lognormal(np.log(c.settlement_median * state_value * src.loc[sources[i], "value_mult"]), 0.75)
                        * (1.4 if suit else 1.0))
                    fee_pct = 0.20 if case_type == "Workers' compensation" else (0.40 if suit else 0.33)
                    costs = settlement * rng.uniform(0.02, 0.06) + (rng.uniform(3_000, 15_000) if suit else 0.0)
                    hours_cm = months_to_pay * rng.uniform(2, 4)
                    hours_atty = 8 + (40 if suit else 0) + rng.lognormal(2, 0.5)
                    hours_para = (rng.uniform(30, 80) if suit else 0) + rng.uniform(2, 8)

                    closed = close_date <= AS_OF
                    share_done = 1.0 if closed else max(0.0, (AS_OF - sign_date) / (close_date - sign_date))
                    case_rows.append((
                        f"C{next_case:06d}", lead_id, o.office_id, o.state_abbr, case_type, sources[i],
                        sign_date.date(), bool(suit),
                        "Closed" if closed else "Open",
                        close_date.date() if closed else None,
                        round(settlement, 2) if closed else None,
                        fee_pct,
                        round(settlement * fee_pct, 2) if closed else None,
                        round(costs * share_done, 2),
                        round(hours_cm * share_done, 1), round(hours_atty * share_done, 1),
                        round(hours_para * share_done, 1),
                    ))
                    next_case += 1
                    sign_dates.append(sign_date)
                    pay_dates.append(close_date)
                    suits.append(suit)

            # --- workload at month end
            sd, pdt, st = np.array(sign_dates, dtype="datetime64[ns]"), np.array(pay_dates, dtype="datetime64[ns]"), np.array(suits)
            open_mask = (sd <= np.datetime64(month_end)) & (pdt > np.datetime64(month_end)) if len(sd) else np.array([], bool)
            drivers = {
                "leads": total_leads,
                "open_cases": int(open_mask.sum()),
                "open_suits": int((open_mask & st).sum()) if len(sd) else 0,
            }
            trailing = {"leads": float(np.mean(lead_history[-3:])), "open_cases": drivers["open_cases"],
                        "open_suits": drivers["open_suits"]}

            # --- staff: load, overtime, quits
            headcount = {r: sum(1 for s in staff if s["role"] == r) for r in ROLES}
            load_ratio = {r: drivers[d] / max(headcount[r] * cap, 1) for r, (d, cap, _, _) in ROLES.items()}
            for s in list(staff):
                role = s["role"]
                _, _, base_quit, _ = ROLES[role]
                ratio = load_ratio[role]
                overloaded = ratio > OVERLOAD_LINE
                quit_p = base_quit * QUIT_SEASON.get(m.month, 1.0)
                if overloaded:
                    quit_p *= CM_OVERLOAD_QUIT_MULT if role == "Case manager" else OTHER_OVERLOAD_QUIT_MULT
                left = rng.random() < quit_p
                overtime = max(0.0, (ratio - 1.0) * 40 + rng.normal(0, 3))
                emp_month_rows.append((s["employee_id"], o.office_id, role, m.date(), round(ratio, 3),
                                       round(overtime, 1), bool(left)))
                if left:
                    s["term_date"] = month_end - pd.Timedelta(days=int(rng.integers(0, 20)))
                    emp_rows.append(s)
                    staff.remove(s)

            # --- hiring: fill gaps to target, with a lag
            for role, (driver, cap, _, lag) in ROLES.items():
                target = max(1, int(np.ceil(LEAN_STAFFING * trailing[driver] / cap)))
                have = sum(1 for s in staff if s["role"] == role) + sum(1 for p in pending if p[1] == role)
                for _ in range(max(0, target - have)):
                    pending.append((t + lag, role))

        emp_rows.extend(staff)  # still employed at the end

    leads = pd.DataFrame(lead_rows, columns=["lead_id", "office_id", "lead_date", "case_type", "source",
                                             "response_minutes", "signed"])
    cases = pd.DataFrame(case_rows, columns=[
        "case_id", "lead_id", "office_id", "state_abbr", "case_type", "source", "sign_date", "went_to_suit",
        "status", "close_date", "settlement", "fee_pct", "fee", "case_costs",
        "hours_case_manager", "hours_attorney", "hours_paralegal"])
    employees = pd.DataFrame(emp_rows)[["employee_id", "office_id", "role", "hire_date", "term_date"]]
    employees["hire_date"] = pd.to_datetime(employees["hire_date"]).dt.date
    employees["term_date"] = pd.to_datetime(employees["term_date"]).dt.date
    employees = employees.sort_values("employee_id").reset_index(drop=True)
    employee_months = pd.DataFrame(emp_month_rows, columns=[
        "employee_id", "office_id", "role", "month", "load_ratio", "overtime_hours", "left_this_month"])
    spend["month"] = spend["month"].dt.date

    return {
        "sim_offices": OFFICES,
        "sim_leads": leads,
        "sim_cases": cases,
        "sim_marketing_spend": spend,
        "sim_employees": employees,
        "sim_employee_months": employee_months,
    }


def planted_truth() -> dict:
    return {
        "S3_response_time_sign_multiplier": {f"<= {lim} min": mult for lim, mult in RESPONSE_BANDS},
        "S4_mi_oh_auto_leads_per_snow_day": SNOW_AUTO_EFFECT,
        "S11_case_manager_quit_multiplier_when_overloaded": CM_OVERLOAD_QUIT_MULT,
        "overload_line": OVERLOAD_LINE,
        "florida_reform_value_multiplier": FL_REFORM_VALUE,
        "seed": SEED,
    }


def summarize(tables: dict[str, pd.DataFrame]) -> None:
    leads, cases, em = tables["sim_leads"], tables["sim_cases"], tables["sim_employee_months"]
    print("\nRows per table:")
    for name, df in tables.items():
        print(f"  {name:22s} {len(df):>9,}")
    print(f"\nOverall sign rate: {leads['signed'].mean():.1%}")
    band = pd.cut(leads["response_minutes"], [0, 5, 15, 60, np.inf], labels=["<=5", "5-15", "15-60", ">60"])
    print("Sign rate by callback time (planted S3):")
    print(leads.groupby(band, observed=True)["signed"].mean().map("{:.1%}".format).to_string())
    cm = em[em["role"] == "Case manager"]
    over = cm["load_ratio"] > OVERLOAD_LINE
    print(f"Case manager monthly quit rate: overloaded {cm.loc[over, 'left_this_month'].mean():.1%} "
          f"vs normal {cm.loc[~over, 'left_this_month'].mean():.1%} (planted S11; seasonality mixes in)")
    closed = cases[cases["status"] == "Closed"]
    print(f"Closed cases: {len(closed):,}   Open cases: {(cases['status'] == 'Open').sum():,}")
    print(f"Total fees on closed cases: ${closed['fee'].sum():,.0f}")


def save_and_upload(tables: dict[str, pd.DataFrame], upload: bool) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(OUT_DIR / f"{name}.csv", index=False)
    (OUT_DIR / "planted_truth.json").write_text(json.dumps(planted_truth(), indent=2))
    print(f"\nSaved CSVs and planted_truth.json to {OUT_DIR}/")
    if not upload:
        return
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    for name, df in tables.items():
        df = df.copy()
        for col in df.columns:  # date columns as real dates in BigQuery
            if col.endswith("_date") or col == "month":
                df[col] = pd.to_datetime(df[col])
                df[col] = df[col].dt.date
        client.load_table_from_dataframe(df, f"{PROJECT}.raw.{name}", job_config=config).result()
        print(f"  loaded raw.{name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-upload", action="store_true", help="save CSVs only, skip BigQuery")
    parser.add_argument("--refresh-weather", action="store_true",
                        help="re-read raw.weather_monthly from BigQuery instead of the local cache")
    args = parser.parse_args()

    print("Loading inputs...")
    fars, weather = load_inputs(refresh_weather=args.refresh_weather)
    print("Simulating 12 offices, 2013-2024 (this takes a few minutes)...")
    tables = simulate(fars, weather)
    summarize(tables)
    save_and_upload(tables, upload=not args.no_upload)
    print("\nDone.")


if __name__ == "__main__":
    main()
