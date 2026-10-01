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

## 2026-10-01: Day 1, continued

### Firm simulation
- Wrote `pipelines/simulate_firm.py`. It reads the real FARS crashes and NOAA weather, then generates the firm's internal data for 12 offices, Jan 2013 to Dec 2024.
- Output tables, saved to `data/simulated/` and loaded to BigQuery `raw.sim_*`:

| Table | Grain | Approx. rows |
| --- | --- | --- |
| `sim_offices` | office | 12 |
| `sim_leads` | lead | 200,000 |
| `sim_cases` | signed case | 57,000 |
| `sim_marketing_spend` | office × month × channel | 6,900 |
| `sim_employees` | employee | 1,000 |
| `sim_employee_months` | employee × month | 29,000 |

- True planted values are saved in `data/simulated/planted_truth.json`, so validation can compare against them later.

### Tuning (tested before handing over)

| Run | Problem | Fix |
| --- | --- | --- |
| 1 | Sign rate 42%; fees about $150M a year, too large for a mid-sized firm | Lowered base sign rates by about 28%; base leads 160 → 120 |
| 2 | Staff rarely overloaded (2%); more attorneys than case managers | Staffing at 90% of workload; case manager capacity 70, attorney 150; marketing raised to about 11% of fees; warm-up from 2013 |
| 3 | Intake still overstaffed, because 1–2 people per office rounds up | Intake capacity set to 60 qualified leads a month, so teams are larger and load varies |

### Simulation checks (test run with stand-in inputs)

| Planted effect | Planted | Recovered |
| --- | --- | --- |
| S3: callback within 5 min vs over 60 min | 1.5× | 1.46× (31.9% vs 21.9%) |
| S11: overloaded case manager monthly quit rate | 2.0× | 1.9× (4.5% vs 2.4%) |
| S4: MI/OH auto leads per snow day | +0.020 | +0.013 (simple check; the model will add controls) |

- Firm profile: about $85–95M in fees a year, $10M marketing, about 240 staff, overall sign rate 28%.
- Staffing affects outcomes: office-months in the slowest callback quartile sign 26.2% vs 31.0% in the fastest.

### Simulation results on real data (BigQuery checks)

| Planted effect | Planted | Recovered on real data |
| --- | --- | --- |
| S3: callback within 5 min vs over 60 min | 1.5x | 1.47x (32.0% vs 21.8% sign rate) |
| S11: overloaded case manager monthly quit rate | 2.0x | 2.15x (5.6% vs 2.6%) |

All six `raw.sim_*` tables loaded to BigQuery. The raw layer is complete.

## 2026-10-01: Warehouse layers

### Clean layer (`sql/1x_*.sql`): tidy, keyed, flagged
| File | Table | What it adds |
| --- | --- | --- |
| 10 | `clean.dim_month` | Calendar with COVID, Michigan reform, Florida reform and analysis-window flags |
| 11 | `clean.dim_office` | 12 offices with state, county and market size |
| 12 | `clean.leads` | Lead month and callback band (matches planted S3) |
| 13 | `clean.cases` | Sign month, days to close, staff cost (assumption S19) |
| 14 | `clean.fars_state_month` | Demand signal per state and month, split by case-type signal |
| 15 | `clean.fars_county_year` | County crashes per 100k people, with an office flag (for the growth map) |
| 16 | `clean.weather_month` | Weather keyed by office_id and month |
| 17 | `clean.staff_month` | Overload flag at 1.3x (matches planted S11) |
| 18 | `clean.marketing_spend` | Spend by office, month and channel |

### Mart layer (`sql/2x_*.sql`): one table per business question
| File | Table | Question it answers |
| --- | --- | --- |
| 20 | `mart.office_casetype_month` | What arrives, where and when? (forecasting) |
| 21 | `mart.office_month` | How is each office performing against its market? (scorecard) |
| 22 | `mart.case_economics` | What does each case earn after all costs? (profit) |
| 23 | `mart.workforce_month` | Who is overloaded, who leaves, when? (hiring) |

### How to rebuild
- `python pipelines/run_sql.py` rebuilds every clean and mart table in order.
- `python pipelines/run_sql.py --checks` runs `sql/checks/mart_checks.sql`: row counts, raw-to-mart reconciliation of leads and fees, input gaps, and margin completeness.

### Design decisions
- **Zero months kept.** The forecasting grid includes office, case type and month combinations with no leads, so models see true zeros rather than gaps.
- **Capture index, not market share.** FARS counts fatal crashes only, so signed cases per fatal crash is used as a demand-relative index, compared over time rather than read as a literal share.
- **Marketing cost per case** is the office-month spend divided by cases signed that month. This is a simple, auditable allocation; channel-level attribution is Phase 2.
