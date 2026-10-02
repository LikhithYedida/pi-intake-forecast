"""
Generate the data dictionary from the live warehouse, and push descriptions into BigQuery.

  python pipelines/make_data_dictionary.py             # write reports/data_dictionary.md + BigQuery descriptions
  python pipelines/make_data_dictionary.py --md-only   # write the Markdown only

What it does
  1. Reads every table in the raw, clean and mart datasets: rows, columns, types.
  2. Takes each table's purpose from the header of the SQL file that builds it
     (or from RAW_PURPOSE below for tables loaded by Python).
  3. Adds plain-English meanings for business columns from COLUMN_NOTES.
  4. Writes reports/data_dictionary.md, and sets the same descriptions on the
     BigQuery tables and columns, where Looker Studio and BigQuery show them.

Re-run it whenever a table changes, so the dictionary never drifts from the warehouse.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

PROJECT = "pi-intake-forecast"
DATASETS = [
    ("mart", "Business-ready tables, one per question, plus the dash_* views that feed Looker Studio."),
    ("clean", "Tidy, keyed and flagged versions of the raw tables."),
    ("raw", "Data exactly as loaded: public sources and the simulated firm systems."),
]
OUT = Path("reports/data_dictionary.md")

# Tables loaded by Python scripts have no SQL header, so their purpose lives here.
RAW_PURPOSE = {
    "fars_crashes": "Every fatal crash in our six states, 2017-2024, from NHTSA FARS, with truck, motorcycle and pedestrian flags. Loaded by pipelines/pull_fars.py.",
    "sim_offices": "The firm's 12 offices (simulated firm system). Loaded by pipelines/simulate_firm.py.",
    "sim_leads": "Every inbound lead with case type, source, callback time and outcome (simulated intake system).",
    "sim_cases": "Every signed case with outcome, settlement, fee, costs and hours (simulated case management system).",
    "sim_marketing_spend": "Marketing spend by office, month and channel (simulated marketing ledger).",
    "sim_employees": "Every employee with role, office, hire and termination dates (simulated HR system).",
    "sim_employee_months": "One row per employee per month worked, with workload, overtime and quits (simulated HR and timekeeping).",
}

# Business glossary: terms a director will ask about.
GLOSSARY = [
    ("Lead", "A potential client who contacted the firm. Not yet a case."),
    ("Signed case", "A lead that signed a retainer. The firm's unit of work and revenue."),
    ("Sign rate", "Signed cases / leads. How well intake converts demand."),
    ("Callback band", "How fast intake called the lead back: within 5, 5-15, 15-60 or over 60 minutes."),
    ("Capture index", "Signed cases per state fatal crash. A demand-relative index: compare it over time and between similar offices, not as a literal market share (fatal crashes are a fraction of all injury crashes)."),
    ("Fee", "The firm's share of a settlement: 33% pre-suit, 40% in suit, 20% for workers' comp."),
    ("Case costs advanced", "Costs the firm pays up front (records, filing fees, experts). Reimbursed from the settlement on won cases; absorbed by the firm on lost cases."),
    ("Contribution margin", "Fee - firm-absorbed costs - case staff cost - marketing cost. What a case contributes before overhead (intake staff, demand writers, rent, admin). Use it to compare case types, sources and offices, not as net profit."),
    ("Load ratio", "Workload / capacity for a role. 1.0 = fully loaded; above 1.3 = overloaded."),
    ("Quit rate", "Share of staff in a role who left in a month."),
]

# Plain-English meaning of business columns. Columns not listed get no description.
COLUMN_NOTES = {
    "office_id": "Three-letter office code (DET, MIA, ...).",
    "state_abbr": "Two-letter state code.",
    "county_fips": "Five-digit county FIPS code.",
    "month": "First day of the month.",
    "case_type": "One of 8 standard case types.",
    "source": "Lead source: TV, Digital, Referral, Organic web, Billboard & radio.",
    "leads": "Inbound leads in the period.",
    "signed_cases": "Leads that signed a retainer in the period.",
    "sign_rate": "signed_cases / leads.",
    "is_signed": "True if the lead signed.",
    "response_minutes": "Minutes from lead arrival to first callback.",
    "callback_band": "Callback speed group: within 5, 5-15, 15-60, over 60 minutes.",
    "median_callback_min": "Median minutes to call a lead back.",
    "share_called_within_5min": "Share of leads called back within 5 minutes.",
    "state_crash_signal": "State fatal-crash count that drives this case type (NULL where no crash signal applies).",
    "state_fatal_crashes": "All fatal crashes in the office's state that month (NHTSA FARS).",
    "capture_index": "Signed cases per state fatal crash. Compare over time, not as market share.",
    "snow_days": "Average days with snowfall at nearby stations that measure snow.",
    "snow_stations": "Nearby stations reporting snow that month. 0 = snow not measured (southern offices).",
    "rain_days": "Average days with 2.5 mm or more of rain.",
    "freeze_days": "Average days with a minimum below 0 C.",
    "avg_high_c": "Average daily high temperature, Celsius.",
    "marketing_spend": "Marketing spend in US dollars.",
    "cost_per_signed_case": "marketing_spend / signed_cases.",
    "settlement": "Gross settlement in US dollars. 0 = lost case. NULL = still open.",
    "fee": "Firm fee in US dollars.",
    "fee_pct": "Fee percentage applied.",
    "case_costs_advanced": "Costs the firm advanced on the case.",
    "firm_absorbed_costs": "Advanced costs the firm absorbed (lost cases only; won cases are reimbursed).",
    "staff_cost": "Case manager, attorney and paralegal hours x loaded hourly rates.",
    "marketing_cost": "Acquisition cost: office-month spend / cases signed that month.",
    "contribution_margin": "fee - firm_absorbed_costs - staff_cost - marketing_cost. Before overhead.",
    "is_lost": "True if the case closed with no recovery.",
    "went_to_suit": "True if a lawsuit was filed.",
    "days_to_close": "Days from signing to payment.",
    "months_to_close": "Months from signing to payment.",
    "load_ratio": "Workload / capacity. Above 1.3 = overloaded.",
    "avg_load": "Average load ratio across the role's staff.",
    "is_overloaded": "True if load_ratio is above 1.3.",
    "share_overloaded": "Share of staff in the role who were overloaded.",
    "headcount": "Staff in the role that month.",
    "quits": "Staff who left that month.",
    "quit_rate": "quits / headcount.",
    "left_this_month": "True if the employee left that month.",
    "overtime_hours": "Overtime hours that month.",
    "is_covid": "Mar 2020 - Jun 2021: abnormal traffic and intake.",
    "is_after_mi_reform": "From Jul 2020: Michigan no-fault reform in effect.",
    "is_after_fl_reform": "From Apr 2023: Florida tort reform in effect.",
    "crashes_per_100k": "Fatal crashes per 100,000 residents.",
    "has_office": "True if the firm has an office in the county.",
    "forecast_2025": "Forecast signed cases for the month (2025).",
    "backtest_2024": "What the model forecast for 2024 using only 2017-2023 data (held-out check).",
    "range_low": "Lower edge of the 80% forecast range.",
    "range_high": "Upper edge of the 80% forecast range.",
    "leads_vs_expected": "2024 leads vs the forecast's expectation for 2024 (+5% = 5% above expectation).",
    "specialists_needed": "Intake specialists needed: 80th percentile of forecast leads / 60 per specialist.",
    "seasonal_index": "Seasonal index: 100 = an average month.",
    "contribution_margin_rate": "contribution margin / fees.",
}


def sql_purposes() -> dict[str, str]:
    """Map dataset.table -> purpose, read from the header comments of sql/*.sql."""
    purposes = {}
    for f in sorted(Path("sql").glob("*.sql")):
        text = f.read_text(encoding="utf-8")
        target = re.search(r"CREATE OR REPLACE (?:TABLE|VIEW) `[^.`]+\.(\w+)\.(\w+)`", text)
        if not target:
            continue
        lines, capture = [], False
        for line in text.splitlines():
            if not line.startswith("--"):
                break
            body = line[2:].strip()
            if body.lower().startswith("purpose"):
                capture = True
                body = body.split(":", 1)[1].strip()
            elif capture and (re.match(r"^\w[\w ]*:", body) or set(body) <= {"="} or not body):
                break
            if capture:
                lines.append(body)
        purposes[f"{target.group(1)}.{target.group(2)}"] = " ".join(lines) + f" Built by sql/{f.name}."
    return purposes


def collect(client) -> list[dict]:
    purposes = sql_purposes()
    tables = []
    for dataset, _ in DATASETS:
        for item in sorted(client.list_tables(f"{PROJECT}.{dataset}"), key=lambda t: t.table_id):
            table = client.get_table(item.reference)
            key = f"{dataset}.{table.table_id}"
            tables.append({
                "key": key,
                "dataset": dataset,
                "purpose": purposes.get(key) or RAW_PURPOSE.get(table.table_id, ""),
                "rows": table.num_rows,
                "columns": [(f.name, f.field_type, COLUMN_NOTES.get(f.name, "")) for f in table.schema],
                "table": table,
            })
    return tables


def write_markdown(tables: list[dict]) -> None:
    out = [
        "# Data Dictionary",
        "",
        f"Generated from the live BigQuery warehouse `{PROJECT}` on {date.today():%Y-%m-%d} by "
        "`pipelines/make_data_dictionary.py`. Do not edit by hand: re-run the script.",
        "",
        "## Business glossary",
        "",
        "| Term | Meaning |",
        "| --- | --- |",
        *[f"| {term} | {meaning} |" for term, meaning in GLOSSARY],
        "",
        "## Tables at a glance",
        "",
        "| Table | Rows | Purpose |",
        "| --- | ---: | --- |",
        *[f"| `{t['key']}` | {t['rows']:,} | {t['purpose'].split('. ')[0].rstrip('.')}. |" for t in tables],
    ]
    for dataset, blurb in DATASETS:
        out += ["", f"## {dataset} layer", "", blurb]
        for t in [t for t in tables if t["dataset"] == dataset]:
            out += ["", f"### `{t['key']}`", "", t["purpose"], "", f"Rows: {t['rows']:,}", "",
                    "| Column | Type | Meaning |", "| --- | --- | --- |"]
            out += [f"| `{name}` | {ftype} | {note} |" for name, ftype, note in t["columns"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(tables)} tables)")


def push_descriptions(client, tables: list[dict]) -> None:
    from google.cloud import bigquery
    for t in tables:
        table = t["table"]
        table.description = t["purpose"][:16000]
        notes = {name: note for name, _, note in t["columns"] if note}
        table.schema = [
            bigquery.SchemaField.from_api_repr({**f.to_api_repr(), "description": notes[f.name]})
            if f.name in notes else f
            for f in table.schema
        ]
        client.update_table(table, ["description", "schema"])
    print(f"Set descriptions on {len(tables)} BigQuery tables")


def main() -> None:
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    tables = collect(client)
    write_markdown(tables)
    if "--md-only" not in sys.argv:
        push_descriptions(client, tables)


if __name__ == "__main__":
    main()
