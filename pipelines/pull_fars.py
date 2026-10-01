"""
Pull NHTSA FARS crash data (2017 onward) for the firm's six states and load it to BigQuery.

What it does
  1. Downloads each year's national FARS CSV zip from NHTSA (skips years not yet published).
  2. Keeps crashes in MI, OH, PA, GA, FL and TX.
  3. Adds case-type flags from the vehicle file: motorcycle, large truck, pedestrian.
  4. Saves one combined CSV and loads it to BigQuery table raw.fars_crashes.

Outputs
  data/raw/fars/FARS<year>NationalCSV.zip   original downloads, never edited
  data/raw/fars_crashes_6states.csv          one row per fatal crash
  pi-intake-forecast.raw.fars_crashes        same data in BigQuery

Run from the project root:
  python pipelines/pull_fars.py
"""
import re
import zipfile
from pathlib import Path

import pandas as pd
import requests
from google.cloud import bigquery

PROJECT = "pi-intake-forecast"
TABLE = f"{PROJECT}.raw.fars_crashes"
YEARS = range(2017, 2026)  # years not yet published are skipped automatically
STATES = {26: "MI", 39: "OH", 42: "PA", 13: "GA", 12: "FL", 48: "TX"}
URL = "https://static.nhtsa.gov/nhtsa/downloads/FARS/{y}/National/FARS{y}NationalCSV.zip"

RAW_DIR = Path("data/raw/fars")
OUT_CSV = Path("data/raw/fars_crashes_6states.csv")


def download(year: int) -> Path | None:
    """Download one year's zip unless we already have it."""
    path = RAW_DIR / f"FARS{year}NationalCSV.zip"
    if path.exists():
        print(f"  {year}: already downloaded")
        return path
    print(f"  {year}: downloading...")
    resp = requests.get(URL.format(y=year), timeout=600)
    if resp.status_code != 200:
        print(f"  {year}: not available (HTTP {resp.status_code}), skipping")
        return None
    path.write_bytes(resp.content)
    return path


def read_member(zf: zipfile.ZipFile, filename: str) -> pd.DataFrame:
    """Read one CSV from the zip. File names and column cases vary by year."""
    member = next((m for m in zf.namelist() if m.lower().split("/")[-1] == filename), None)
    if member is None:
        raise FileNotFoundError(f"{filename} not found in {zf.filename}")
    with zf.open(member) as f:
        df = pd.read_csv(f, encoding="latin-1", low_memory=False)
    # Newer files start with a hidden byte-order mark that turns "STATE" into "ï»¿STATE".
    # Keep only letters, digits and underscores in every column name.
    df.columns = [re.sub(r"[^A-Z0-9_]", "", str(c).upper()) for c in df.columns]
    return df


def crashes_for_year(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as zf:
        acc = read_member(zf, "accident.csv")
        veh = read_member(zf, "vehicle.csv")

    acc = acc[acc["STATE"].isin(STATES)]
    veh = veh[veh["STATE"].isin(STATES)]

    # FARS body types: 60-79 = medium/heavy trucks, 80-89 = motorcycles
    body = veh["BODY_TYP"]
    flags = (
        veh.assign(has_large_truck=body.between(60, 79), has_motorcycle=body.between(80, 89))
        .groupby("ST_CASE")[["has_large_truck", "has_motorcycle"]]
        .any()
    )

    cols = ["ST_CASE", "STATE", "COUNTY", "YEAR", "MONTH", "DAY", "DAY_WEEK", "HOUR", "FATALS", "PEDS"]
    out = acc[cols].merge(flags, left_on="ST_CASE", right_index=True, how="left")
    out[["has_large_truck", "has_motorcycle"]] = out[["has_large_truck", "has_motorcycle"]].fillna(False)
    out["has_pedestrian"] = out["PEDS"] > 0
    return out


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("Step 1/3: downloading FARS")
    frames = []
    for year in YEARS:
        path = download(year)
        if path is not None:
            year_df = crashes_for_year(path)
            print(f"  {year}: {len(year_df):,} crashes in our six states")
            frames.append(year_df)
    if not frames:
        raise SystemExit("No FARS years downloaded. Check your internet connection.")

    print("Step 2/3: combining and cleaning")
    df = pd.concat(frames, ignore_index=True)
    df.columns = [c.lower() for c in df.columns]
    df["state_abbr"] = df["state"].map(STATES)
    df["county_fips"] = (df["state"] * 1000 + df["county"]).astype(int).astype(str).str.zfill(5)
    df["crash_date"] = pd.to_datetime(
        dict(year=df["year"], month=df["month"], day=df["day"]), errors="coerce"
    ).dt.date
    df = df.rename(columns={"st_case": "crash_id", "fatals": "fatalities", "peds": "pedestrians"})
    df = df[[
        "crash_id", "state_abbr", "county_fips", "year", "month", "day", "crash_date",
        "day_week", "hour", "fatalities", "pedestrians",
        "has_large_truck", "has_motorcycle", "has_pedestrian",
    ]]
    df.to_csv(OUT_CSV, index=False)

    print("Step 3/3: loading to BigQuery")
    client = bigquery.Client(project=PROJECT)
    job = client.load_table_from_dataframe(
        df, TABLE, job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    )
    job.result()

    print(f"\nDone: {len(df):,} crashes loaded to {TABLE}")
    print("\nCrashes by state and year:")
    print(df.pivot_table(index="state_abbr", columns="year", values="crash_id", aggfunc="count"))


if __name__ == "__main__":
    main()