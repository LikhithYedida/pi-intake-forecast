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

### Warehouse results
- `run_sql.py` built all 13 tables. All 6 mart checks passed: 9,216 and 1,152 rows as expected; 136,728 leads and $950.8M in fees reconcile from raw to mart with zero difference; no gaps in crash or weather inputs.

## 2026-10-01: Senior review and fixes (v2)

A critical review of everything built so far, before any analysis reaches leadership.

### Correctness fixes
| # | Issue | Why it matters | Fix |
| --- | --- | --- | --- |
| 1 | Case costs subtracted on every case | In PI, the firm advances costs but recovers them from the settlement on won cases. Charging them on every case understated profit | `firm_absorbed_costs` = case costs on lost cases only (assumption S20) |
| 2 | "Margin" excluded overhead but did not say so | A director would ask where intake staff, rent and admin went | Renamed to `contribution_margin`, defined in the SQL header and the data dictionary |
| 3 | Snowfall understated | Rain-only weather stations counted as "0 snow" and pulled averages down | Each weather measure is averaged only across stations reporting it for 15+ days; `snow_stations` shows coverage (assumption D4) |

### Senior-level upgrades
| # | Upgrade | Value |
| --- | --- | --- |
| 4 | `pipelines/make_data_dictionary.py` | Generates `reports/data_dictionary.md` from the live warehouse, with a business glossary, and writes table and column descriptions into BigQuery so Looker Studio shows them |
| 5 | README architecture | Mermaid diagram, trust-and-quality controls, one-page reproduce steps |
| 6 | `tests/test_planted_effects.py` | Plant-and-recover as automated tests, including a placebo |

### Lesson from building the tests
The first version used fixed tolerances. The placebo (Pennsylvania snow, not planted) failed at -0.027, a reminder that:
1. **Sampling noise must set the bar.** Two offices give a noisy estimate. Small effects are now judged by a 95% confidence interval, not a fixed range.
2. **Controls matter.** On real data, snow also changes real crash counts, which feed demand. The snow test holds the state crash signal constant, so a real weather effect is not mistaken for the planted one.
After the change, all 5 tests passed in the offline test run.

### New checks
- `mart_checks.sql` Check 7: won cases absorb no case costs. Check 8: margin components add up.
- `raw_checks.sql` Check 4b: snow is measured at every northern office in winter.

### v2.1: edge case caught by Check 6
- After the rebuild, 7 of 8 checks passed. Check 6 found **20 closed cases with no contribution margin**.
- Cause: leads from the last days of December 2024 that signed in January 2025. Marketing cost was allocated by **sign month**, and there is no spend data for 2025.
- Fix: allocate marketing cost by **lead month**. This is also the better model, since marketing creates the lead, not the signature. `mart.case_economics` now carries `lead_month`.
- Takeaway: completeness checks on derived metrics catch boundary-of-data problems that row counts never will.

## 2026-10-01: Seasonality analysis

### What was built
- `notebooks/01_seasonality.py`: seasonal index per state and case type, findings in business language, three charts, and `mart.seasonal_index` in BigQuery for the Looker Studio calendar page.
- Outputs: `reports/seasonality_findings.md` and `reports/figures/seasonality_*.png`.

### Method
- Index: each month's signed cases / that year's average month, averaged over 2017-2024 excluding COVID, x 100. Dividing by each year's own average removes growth and one-off years.
- A peak or trough is only called when its 95% CI across years excludes 100.
- Seasons are the best consecutive 3-month window, wrapping over New Year, because staffing and marketing plans need a season, not scattered months.
- Dollar values use the expected fee per signed case (cases signed 2017-2022, lost cases at $0).

### Self-review before release (tested on stand-in data)
| # | Problem found | Fix |
| --- | --- | --- |
| 1 | Peak "seasons" were scattered months (e.g. Jul, Oct, Dec) | Best consecutive 3-month window |
| 2 | Busy months picked as an arbitrary top 3, though September was equally loaded | Busy = average intake load of 0.95 or more |
| 3 | Busy-month sign rate compared raw, so summer's case mix (more motorcycle, dog bite) could be blamed on intake | Mix-adjusted: each case type compared with itself |
| 4 | Chart led with a weak number (0.6 pts) | Title leads with the operational fact: callbacks slow from 6 to 9 minutes |
| 5 | Hiring advice dated from the case peak (Jul), after intake was already at capacity (May) | Hire 6-8 weeks before intake reaches capacity |
| 6 | "Ohio auto peaks Jun-Aug (top month Dec)" read as a contradiction | Series ranked and described by season strength |
| 7 | Chart subtitle clipped; bar label on the capacity line | Shortened; labels inside the bars |

### Results on real data, and the review that followed
First run on the real warehouse: the firm peaks Aug-Oct (+7% in Oct, -10% in Feb); Michigan has the largest swing (43 points); Georgia the flattest (13). Reading the output as a director would surfaced three gaps:

| # | Gap | Change |
| --- | --- | --- |
| 1 | **Florida runs opposite to the firm** (peak Oct-Dec, trough Jun-Aug, when the north is busiest). The most actionable insight, and the report did not say it | New finding: states negatively correlated with the firm index are detected automatically, with a recommendation to pilot a shared virtual intake queue (cover peaks with existing headcount) |
| 2 | **The starting hypothesis was contradicted.** README claimed MI/OH auto rises with winter ice; Michigan auto actually peaks Jul-Sep in fatal-crash-driven demand | New "Hypotheses tested" section with a Supported / Partly / Not supported verdict. README rewritten to say what was confirmed and overturned. Explanation: winter crashes are frequent but less often fatal, so FARS understates winter injury demand; test with state injury-crash data (Phase 2) |
| 3 | "Capacity in Aug ... in those months" | Singular and plural wording by month count |

Lesson: a hypothesis in the README is a claim. When the data overturns it, the README changes, and the report says so.

## 2026-10-01: 12-month forecast

### What was built
- `notebooks/02_forecast.py`: 48 state x case-type models for signed cases and 12 office models for leads. Firm and state totals are built bottom-up. Outputs: `reports/forecast_report.md`, two charts, and `mart.forecast_monthly` (backtest and 2025 rows) for Looker Studio.
- Model: Poisson regression (level + month of year + trend + COVID flag), fitted by IRLS in plain numpy. PyPI was unreachable in the build environment, which turned into a design choice: no new dependency, and every coefficient is inspectable.
- No future crash or weather data is used: neither is known on the day a forecast is made.

### Validation design
- Rolling origin: 2017-21 -> 2022, 2017-22 -> 2023, 2017-23 -> 2024.
- Two spreadsheet-level baselines: same month last year, and the seasonal average. Metric: WAPE (robust to small months, unlike MAPE).
- Unit test before use: the model recovered known coefficients from simulated data (trend 0.032 vs 0.030 true; COVID -0.27 vs -0.30), and its 80% ranges held 84% on simulated truth.

### Self-review before release (stand-in data)
| # | Problem found | Fix |
| --- | --- | --- |
| 1 | Headline annual range was the sum of monthly bounds, overstating uncertainty | Annual ranges from simulated annual totals |
| 2 | Firm-level 80% range held only 67%: summing independent series assumes their surprises cancel, but real shocks hit many series at once | Point = bottom-up sum (levels add up); range width from a model fitted directly to the total. Firm coverage became 81%, state 79% |
| 3 | 42 of 48 segments tiered "Low" on monthly error, unfair to small segments | Noise floor added (error a perfect forecast would still make on small counts); tiers on quarterly error, the grain small segments are planned at. Model runs at about 1.08x the noise floor |
| 4 | The model was slightly worse than the seasonal average for small segments, and the report did not say so | Report now states plainly where the model does not win and recommends rolling small segments up |
| 5 | Staffing table said "quietest Jan, busiest Jan" for flat offices | Shows "Flat all year" |
| 6 | Accuracy chart led with the smallest gain (7%) | Data-driven title: beats the baseline at every level (7-20%), or says at how many levels it does |

### v2: first real-data result, and the fix
- **Real-data result (v1):** the model beat same-month-last-year at state (12.5% vs 14.0%), segment (28.3% vs 33.8%) and office-lead level (10.3% vs 11.2%), but **lost at firm level (6.3% vs 5.7%)**. The report said so in its headline, as designed. Warning signs: Ohio forecast +10.5%, Pennsylvania +9.1% vs 2024.
- **Diagnosis:** one linear trend fitted through 2017-2024 is bent by the COVID dip and rebound; same-month-last-year carries the most recent level automatically.
- **Fix:** two standard remedies offered as candidates: recency weighting (half-life 1.5, 2 or 3 years) and blending with same-month-last-year (30% or 50%); forecast combination is among the most reliable ways to cut error.
- **Selection without fooling ourselves:** 12 candidates scored on 2022-2023 only (average model/baseline error ratio across the four levels); the winner is then checked on 2024, which plays no part in the choice. The headline now quotes the 2024 check, the one number no modeling decision could flatter.
- The notebook runs the selection itself every time, so the method adapts if the data changes. On stand-in data it chose a 70/30 model/baseline blend, which beat the baseline at all four levels on the held-out year.
