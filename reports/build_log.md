# Build Log

A running record of what was built, when, and why. Newest entries at the bottom.

## 2026-10-01: Day 1

### Setup
- Installed Python 3.13, Git and the Google Cloud CLI. Created a VS Code project with a virtual environment.
- Created the Google Cloud project `pi-intake-forecast` (free trial billing, so no sandbox table expiry).
- Created BigQuery datasets `raw`, `clean` and `mart` (location US). Verified the connection with `pipelines/test_bq.py`.
- Created the GitHub repo `pi-intake-forecast`.

### Scope
- Wrote `README.md`, `reports/scope.md` and `reports/assumptions.md`.
- Scope fixed: 6 states, 12 offices, 8 case types, history 2017-2024, 5-page Looker Studio dashboard.

### Public data (raw layer)

| Table | Source | How | Status |
| --- | --- | --- | --- |
| `raw.fars_crashes` | NHTSA FARS 2017-2024 | `pipelines/pull_fars.py` (download, filter to six states, add truck / motorcycle / pedestrian flags) | Loaded |
| `raw.weather_monthly` | NOAA GHCN-Daily (BigQuery public data) | `sql/01_raw_weather_monthly.sql` | Loaded, check passed |
| `raw.county_population` | Census ACS 5-year (BigQuery public data) | `sql/02_raw_county_population.sql` | Loaded |

### Decisions and why
- **FARS from NHTSA, not BigQuery public data.** The public BigQuery copy only has 2015-2016.
- **FARS as the demand signal.** It covers fatal crashes only. It is used for seasonal shape and trend, as stated in assumption D1.
- **Weather averaged across stations within 25 km.** This is more robust than a single station, which can have gaps.
- **Population for all counties in the six states.** This enables the growth map later.

### Issues hit and fixes
- **FARS column error (`KeyError: 'STATE'`).** Newer NHTSA files start with a hidden byte-order mark. Fixed by cleaning column names in `read_member()`.
- **Raw zips pushed to GitHub.** `.gitignore` was not being read. Rewrote it, removed `data/raw` from tracking, amended the commit and force-pushed.

### Checks
All raw-layer checks are saved in `sql/checks/raw_checks.sql`, with expected results.
- Weather: the snowiest offices are Grand Rapids (80 mm/month), Cleveland (64), Pittsburgh (35) and Detroit (33). Pass.

### Next
- Simulate the firm layer (leads, cases, payments, spend, staff) on top of the real crash patterns.