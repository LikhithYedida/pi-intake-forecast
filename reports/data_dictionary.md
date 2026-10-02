# Data Dictionary

Generated from the live BigQuery warehouse `pi-intake-forecast` on 2026-10-01 by `pipelines/make_data_dictionary.py`. Do not edit by hand: re-run the script.

## Business glossary

| Term | Meaning |
| --- | --- |
| Lead | A potential client who contacted the firm. Not yet a case. |
| Signed case | A lead that signed a retainer. The firm's unit of work and revenue. |
| Sign rate | Signed cases / leads. How well intake converts demand. |
| Callback band | How fast intake called the lead back: within 5, 5-15, 15-60 or over 60 minutes. |
| Capture index | Signed cases per state fatal crash. A demand-relative index: compare it over time and between similar offices, not as a literal market share (fatal crashes are a fraction of all injury crashes). |
| Fee | The firm's share of a settlement: 33% pre-suit, 40% in suit, 20% for workers' comp. |
| Case costs advanced | Costs the firm pays up front (records, filing fees, experts). Reimbursed from the settlement on won cases; absorbed by the firm on lost cases. |
| Contribution margin | Fee - firm-absorbed costs - case staff cost - marketing cost. What a case contributes before overhead (intake staff, demand writers, rent, admin). Use it to compare case types, sources and offices, not as net profit. |
| Load ratio | Workload / capacity for a role. 1.0 = fully loaded; above 1.3 = overloaded. |
| Quit rate | Share of staff in a role who left in a month. |

## Tables at a glance

| Table | Rows | Purpose |
| --- | ---: | --- |
| `mart.case_economics` | 57,579 | THE PROFIT TABLE. |
| `mart.dash_case_profit` | 0 | Profit page. |
| `mart.dash_forecast` | 0 | Forecast page. |
| `mart.dash_kpis` | 0 | Overview page scorecards. |
| `mart.dash_office_scorecard` | 0 | Office scorecard page. |
| `mart.dash_seasonal` | 0 | Seasonal calendar page. |
| `mart.dash_staffing_plan` | 0 | Intake staffing plan for 2025. |
| `mart.dash_workforce` | 0 | Workforce page. |
| `mart.forecast_monthly` | 3,216 | . |
| `mart.office_casetype_month` | 9,216 | THE FORECASTING TABLE. |
| `mart.office_month` | 1,152 | THE SCORECARD TABLE. |
| `mart.seasonal_index` | 756 | . |
| `mart.workforce_month` | 5,754 | THE WORKFORCE TABLE. |
| `clean.cases` | 57,579 | Every signed case, with timing and the staff cost of working it. |
| `clean.dim_month` | 156 | Calendar of months with the flags every analysis needs. |
| `clean.dim_office` | 12 | The firm's 12 offices with state, home county and market size. |
| `clean.fars_county_year` | 5,437 | Yearly fatal crashes per county, joined to population. |
| `clean.fars_state_month` | 576 | Monthly fatal-crash counts per state, split by the signals that drive each case type. |
| `clean.leads` | 200,347 | Every lead, with its month and callback-speed band. |
| `clean.marketing_spend` | 6,912 | Marketing spend per office, month and channel. |
| `clean.staff_month` | 29,299 | One row per employee per month worked, with workload and quits. |
| `clean.weather_month` | 1,152 | Monthly weather per office, keyed by office_id and month date. |
| `raw.county_population` | 7,898 | County population and median income for every county in our six states, for every ACS 5-year release available. |
| `raw.fars_crashes` | 91,348 | Every fatal crash in our six states, 2017-2024, from NHTSA FARS, with truck, motorcycle and pedestrian flags. |
| `raw.sim_cases` | 57,579 | Every signed case with outcome, settlement, fee, costs and hours (simulated case management system). |
| `raw.sim_employee_months` | 29,299 | One row per employee per month worked, with workload, overtime and quits (simulated HR and timekeeping). |
| `raw.sim_employees` | 949 | Every employee with role, office, hire and termination dates (simulated HR system). |
| `raw.sim_leads` | 200,347 | Every inbound lead with case type, source, callback time and outcome (simulated intake system). |
| `raw.sim_marketing_spend` | 6,912 | Marketing spend by office, month and channel (simulated marketing ledger). |
| `raw.sim_offices` | 12 | The firm's 12 offices (simulated firm system). |
| `raw.weather_monthly` | 1,152 | Monthly weather per office (2017-2024) from NOAA GHCN-Daily. |

## mart layer

Business-ready tables, one per question, plus the dash_* views that feed Looker Studio.

### `mart.case_economics`

THE PROFIT TABLE. Contribution margin on every signed case. Built by sql/22_mart_case_economics.sql.

Rows: 57,579

| Column | Type | Meaning |
| --- | --- | --- |
| `case_id` | STRING |  |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `office` | STRING |  |
| `state_abbr` | STRING | Two-letter state code. |
| `case_type` | STRING | One of 8 standard case types. |
| `source` | STRING | Lead source: TV, Digital, Referral, Organic web, Billboard & radio. |
| `sign_date` | DATE |  |
| `sign_month` | DATE |  |
| `lead_month` | DATE |  |
| `sign_year` | INTEGER |  |
| `status` | STRING |  |
| `went_to_suit` | BOOLEAN | True if a lawsuit was filed. |
| `is_lost` | BOOLEAN | True if the case closed with no recovery. |
| `close_date` | DATE |  |
| `close_year` | INTEGER |  |
| `days_to_close` | INTEGER | Days from signing to payment. |
| `months_to_close` | FLOAT | Months from signing to payment. |
| `settlement` | FLOAT | Gross settlement in US dollars. 0 = lost case. NULL = still open. |
| `fee` | FLOAT | Firm fee in US dollars. |
| `case_costs_advanced` | FLOAT | Costs the firm advanced on the case. |
| `firm_absorbed_costs` | FLOAT | Advanced costs the firm absorbed (lost cases only; won cases are reimbursed). |
| `staff_cost` | FLOAT | Case manager, attorney and paralegal hours x loaded hourly rates. |
| `marketing_cost` | FLOAT | Acquisition cost: office-month spend / cases signed that month. |
| `contribution_margin` | FLOAT | fee - firm_absorbed_costs - staff_cost - marketing_cost. Before overhead. |

### `mart.dash_case_profit`

Profit page. Closed-case economics by state, case type, lead source and close year. All components are sums, so any filter combination adds up; build averages and rates as Looker calculated fields. Built by sql/36_dash_case_profit.sql.

Rows: 0

| Column | Type | Meaning |
| --- | --- | --- |
| `state` | STRING |  |
| `case_type` | STRING | One of 8 standard case types. |
| `source` | STRING | Lead source: TV, Digital, Referral, Organic web, Billboard & radio. |
| `close_year` | INTEGER |  |
| `closed_cases` | INTEGER |  |
| `won_cases` | INTEGER |  |
| `settlements` | FLOAT |  |
| `fees` | FLOAT |  |
| `firm_absorbed_costs` | FLOAT | Advanced costs the firm absorbed (lost cases only; won cases are reimbursed). |
| `staff_cost` | FLOAT | Case manager, attorney and paralegal hours x loaded hourly rates. |
| `marketing_cost` | FLOAT | Acquisition cost: office-month spend / cases signed that month. |
| `contribution_margin` | FLOAT | fee - firm_absorbed_costs - staff_cost - marketing_cost. Before overhead. |
| `total_months_to_close` | FLOAT |  |

### `mart.dash_forecast`

Forecast page. One continuous timeline per level: monthly actuals 2017-2024, the 2024 held-out backtest, and the 2025 forecast with its 80% range. Built by sql/32_dash_forecast.sql.

Rows: 0

| Column | Type | Meaning |
| --- | --- | --- |
| `level` | STRING |  |
| `state` | STRING |  |
| `state_order` | INTEGER |  |
| `case_type` | STRING | One of 8 standard case types. |
| `month` | DATE | First day of the month. |
| `actual` | FLOAT |  |
| `backtest_2024` | FLOAT | What the model forecast for 2024 using only 2017-2023 data (held-out check). |
| `forecast_2025` | FLOAT | Forecast signed cases for the month (2025). |
| `range_low` | FLOAT | Lower edge of the 80% forecast range. |
| `range_high` | FLOAT | Upper edge of the 80% forecast range. |

### `mart.dash_kpis`

Overview page scorecards. One row of headline numbers. Built by sql/30_dash_kpis.sql.

Rows: 0

| Column | Type | Meaning |
| --- | --- | --- |
| `forecast_signed_2025` | FLOAT |  |
| `signed_2024` | INTEGER |  |
| `forecast_change_vs_2024` | FLOAT |  |
| `model_error_2024` | FLOAT |  |
| `baseline_error_2024` | FLOAT |  |
| `leads_2024` | INTEGER |  |
| `sign_rate_2024` | FLOAT |  |
| `median_callback_min_2024` | FLOAT |  |
| `marketing_2024` | FLOAT |  |
| `cost_per_signed_case_2024` | FLOAT |  |
| `fees_2024` | FLOAT |  |
| `contribution_margin_2024` | FLOAT |  |
| `contribution_margin_rate_2024` | FLOAT |  |

### `mart.dash_office_scorecard`

Office scorecard page. One row per office per year, with the counts needed to compute rates correctly in Looker Studio, plus 2024 leads against the forecast's expectation for that year. Built by sql/33_dash_office_scorecard.sql.

Rows: 0

| Column | Type | Meaning |
| --- | --- | --- |
| `office` | STRING |  |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `state` | STRING |  |
| `year` | INTEGER |  |
| `leads` | INTEGER | Inbound leads in the period. |
| `signed_cases` | INTEGER | Leads that signed a retainer in the period. |
| `leads_called_within_5min` | FLOAT |  |
| `marketing_spend` | FLOAT | Marketing spend in US dollars. |
| `staff_quits` | INTEGER |  |
| `avg_monthly_median_callback_min` | FLOAT |  |
| `avg_intake_load` | FLOAT |  |
| `sign_rate` | FLOAT | signed_cases / leads. |
| `signed_change_vs_prior_year` | FLOAT |  |
| `leads_expected` | FLOAT |  |
| `leads_vs_expected` | FLOAT | 2024 leads vs the forecast's expectation for 2024 (+5% = 5% above expectation). |

### `mart.dash_seasonal`

Seasonal calendar page. Seasonal index by state, case type and month. Built by sql/31_dash_seasonal.sql.

Rows: 0

| Column | Type | Meaning |
| --- | --- | --- |
| `state` | STRING |  |
| `state_order` | INTEGER |  |
| `case_type` | STRING | One of 8 standard case types. |
| `month_num` | INTEGER |  |
| `month_name` | STRING |  |
| `seasonal_index` | FLOAT | Seasonal index: 100 = an average month. |
| `pct_vs_average_month` | FLOAT |  |
| `signal` | STRING |  |
| `avg_monthly_signed_cases` | FLOAT |  |

### `mart.dash_staffing_plan`

Intake staffing plan for 2025. Specialists needed per office per month, staffed to the 80th percentile of forecast leads at 60 leads per specialist (assumption S10), against December 2024 headcount. Built by sql/34_dash_staffing_plan.sql.

Rows: 0

| Column | Type | Meaning |
| --- | --- | --- |
| `office` | STRING |  |
| `state` | STRING |  |
| `month` | DATE | First day of the month. |
| `month_name` | STRING |  |
| `leads_forecast` | FLOAT |  |
| `leads_p80` | FLOAT |  |
| `specialists_needed` | INTEGER | Intake specialists needed: 80th percentile of forecast leads / 60 per specialist. |
| `specialists_dec_2024` | INTEGER |  |
| `gap_vs_dec_2024` | INTEGER |  |

### `mart.dash_workforce`

Workforce page. Staff-months, quits and overloaded staff-months by office, role, year and calendar month. Compute quit rate and overload share in Looker as SUM(quits) / SUM(staff_months). Built by sql/35_dash_workforce.sql.

Rows: 0

| Column | Type | Meaning |
| --- | --- | --- |
| `office` | STRING |  |
| `state` | STRING |  |
| `role` | STRING |  |
| `year` | INTEGER |  |
| `month_num` | INTEGER |  |
| `month_name` | STRING |  |
| `staff_months` | INTEGER |  |
| `quits` | INTEGER | Staff who left that month. |
| `overloaded_staff_months` | FLOAT |  |
| `overtime_hours` | FLOAT | Overtime hours that month. |

### `mart.forecast_monthly`



Rows: 3,216

| Column | Type | Meaning |
| --- | --- | --- |
| `level` | STRING |  |
| `metric` | STRING |  |
| `state_abbr` | STRING | Two-letter state code. |
| `case_type` | STRING | One of 8 standard case types. |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `office` | STRING |  |
| `month` | DATE | First day of the month. |
| `origin_year` | INTEGER |  |
| `kind` | STRING |  |
| `actual` | FLOAT |  |
| `forecast` | FLOAT |  |
| `p025` | FLOAT |  |
| `p10` | FLOAT |  |
| `p50` | FLOAT |  |
| `p80` | FLOAT |  |
| `p90` | FLOAT |  |
| `p975` | FLOAT |  |
| `naive` | INTEGER |  |
| `seasonal_mean` | FLOAT |  |

### `mart.office_casetype_month`

THE FORECASTING TABLE. Leads and signed cases per office, case type and month, next to the demand signal and weather that explain them. Months with zero leads are kept as zeros. Built by sql/20_mart_office_casetype_month.sql.

Rows: 9,216

| Column | Type | Meaning |
| --- | --- | --- |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `office` | STRING |  |
| `state_abbr` | STRING | Two-letter state code. |
| `case_type` | STRING | One of 8 standard case types. |
| `month` | DATE | First day of the month. |
| `year` | INTEGER |  |
| `month_num` | INTEGER |  |
| `month_name` | STRING |  |
| `is_covid` | BOOLEAN | Mar 2020 - Jun 2021: abnormal traffic and intake. |
| `is_after_mi_reform` | BOOLEAN | From Jul 2020: Michigan no-fault reform in effect. |
| `is_after_fl_reform` | BOOLEAN | From Apr 2023: Florida tort reform in effect. |
| `leads` | INTEGER | Inbound leads in the period. |
| `signed_cases` | INTEGER | Leads that signed a retainer in the period. |
| `sign_rate` | FLOAT | signed_cases / leads. |
| `state_crash_signal` | INTEGER | State fatal-crash count that drives this case type (NULL where no crash signal applies). |
| `snow_days` | FLOAT | Average days with snowfall at nearby stations that measure snow. |
| `rain_days` | FLOAT | Average days with 2.5 mm or more of rain. |
| `freeze_days` | FLOAT | Average days with a minimum below 0 C. |
| `avg_high_c` | FLOAT | Average daily high temperature, Celsius. |

### `mart.office_month`

THE SCORECARD TABLE. One row per office per month with demand, intake, conversion, marketing and staffing side by side. Feeds the office scorecard, the capture-rate model and the Looker Studio overview. Built by sql/21_mart_office_month.sql.

Rows: 1,152

| Column | Type | Meaning |
| --- | --- | --- |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `office` | STRING |  |
| `state_abbr` | STRING | Two-letter state code. |
| `month` | DATE | First day of the month. |
| `year` | INTEGER |  |
| `month_num` | INTEGER |  |
| `month_name` | STRING |  |
| `is_covid` | BOOLEAN | Mar 2020 - Jun 2021: abnormal traffic and intake. |
| `is_after_mi_reform` | BOOLEAN | From Jul 2020: Michigan no-fault reform in effect. |
| `is_after_fl_reform` | BOOLEAN | From Apr 2023: Florida tort reform in effect. |
| `state_fatal_crashes` | INTEGER | All fatal crashes in the office's state that month (NHTSA FARS). |
| `snow_days` | FLOAT | Average days with snowfall at nearby stations that measure snow. |
| `rain_days` | FLOAT | Average days with 2.5 mm or more of rain. |
| `freeze_days` | FLOAT | Average days with a minimum below 0 C. |
| `avg_high_c` | FLOAT | Average daily high temperature, Celsius. |
| `leads` | INTEGER | Inbound leads in the period. |
| `signed_cases` | INTEGER | Leads that signed a retainer in the period. |
| `sign_rate` | FLOAT | signed_cases / leads. |
| `capture_index` | FLOAT | Signed cases per state fatal crash. Compare over time, not as market share. |
| `median_callback_min` | FLOAT | Median minutes to call a lead back. |
| `share_called_within_5min` | FLOAT | Share of leads called back within 5 minutes. |
| `marketing_spend` | FLOAT | Marketing spend in US dollars. |
| `cost_per_signed_case` | FLOAT | marketing_spend / signed_cases. |
| `intake_headcount` | INTEGER |  |
| `case_manager_headcount` | INTEGER |  |
| `attorney_headcount` | INTEGER |  |
| `total_headcount` | INTEGER |  |
| `intake_load` | FLOAT |  |
| `case_manager_load` | FLOAT |  |
| `staff_quits` | INTEGER |  |

### `mart.seasonal_index`



Rows: 756

| Column | Type | Meaning |
| --- | --- | --- |
| `state_abbr` | STRING | Two-letter state code. |
| `case_type` | STRING | One of 8 standard case types. |
| `month_num` | INTEGER |  |
| `month_name` | STRING |  |
| `seasonal_index` | FLOAT | Seasonal index: 100 = an average month. |
| `ci_low` | FLOAT |  |
| `ci_high` | FLOAT |  |
| `significant` | BOOLEAN |  |
| `years_used` | INTEGER |  |
| `avg_monthly_signed_cases` | FLOAT |  |

### `mart.workforce_month`

THE WORKFORCE TABLE. Headcount, workload, overtime and quits per office, role and month. Feeds the turnover calendar and the hiring plan. Built by sql/23_mart_workforce_month.sql.

Rows: 5,754

| Column | Type | Meaning |
| --- | --- | --- |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `office` | STRING |  |
| `state_abbr` | STRING | Two-letter state code. |
| `role` | STRING |  |
| `month` | DATE | First day of the month. |
| `year` | INTEGER |  |
| `month_num` | INTEGER |  |
| `month_name` | STRING |  |
| `headcount` | INTEGER | Staff in the role that month. |
| `avg_load` | FLOAT | Average load ratio across the role's staff. |
| `share_overloaded` | FLOAT | Share of staff in the role who were overloaded. |
| `avg_overtime_hours` | FLOAT |  |
| `quits` | INTEGER | Staff who left that month. |
| `quit_rate` | FLOAT | quits / headcount. |

## clean layer

Tidy, keyed and flagged versions of the raw tables.

### `clean.cases`

Every signed case, with timing and the staff cost of working it. Built by sql/13_clean_cases.sql.

Rows: 57,579

| Column | Type | Meaning |
| --- | --- | --- |
| `case_id` | STRING |  |
| `lead_id` | STRING |  |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `state_abbr` | STRING | Two-letter state code. |
| `case_type` | STRING | One of 8 standard case types. |
| `source` | STRING | Lead source: TV, Digital, Referral, Organic web, Billboard & radio. |
| `sign_date` | DATE |  |
| `sign_month` | DATE |  |
| `went_to_suit` | BOOLEAN | True if a lawsuit was filed. |
| `status` | STRING |  |
| `close_date` | DATE |  |
| `days_to_close` | INTEGER | Days from signing to payment. |
| `settlement` | FLOAT | Gross settlement in US dollars. 0 = lost case. NULL = still open. |
| `fee_pct` | FLOAT | Fee percentage applied. |
| `fee` | FLOAT | Firm fee in US dollars. |
| `case_costs` | FLOAT |  |
| `hours_case_manager` | FLOAT |  |
| `hours_attorney` | FLOAT |  |
| `hours_paralegal` | FLOAT |  |
| `staff_cost` | FLOAT | Case manager, attorney and paralegal hours x loaded hourly rates. |

### `clean.dim_month`

Calendar of months with the flags every analysis needs. Built by sql/10_clean_dim_month.sql.

Rows: 156

| Column | Type | Meaning |
| --- | --- | --- |
| `month` | DATE | First day of the month. |
| `year` | INTEGER |  |
| `month_num` | INTEGER |  |
| `month_name` | STRING |  |
| `quarter` | INTEGER |  |
| `is_covid` | BOOLEAN | Mar 2020 - Jun 2021: abnormal traffic and intake. |
| `is_after_mi_reform` | BOOLEAN | From Jul 2020: Michigan no-fault reform in effect. |
| `is_after_fl_reform` | BOOLEAN | From Apr 2023: Florida tort reform in effect. |
| `in_analysis_window` | BOOLEAN |  |

### `clean.dim_office`

The firm's 12 offices with state, home county and market size. Built by sql/11_clean_dim_office.sql.

Rows: 12

| Column | Type | Meaning |
| --- | --- | --- |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `office` | STRING |  |
| `state_abbr` | STRING | Two-letter state code. |
| `county_fips` | STRING | Five-digit county FIPS code. |
| `market_size` | FLOAT |  |

### `clean.fars_county_year`

Yearly fatal crashes per county, joined to population. Built by sql/15_clean_fars_county_year.sql.

Rows: 5,437

| Column | Type | Meaning |
| --- | --- | --- |
| `county_fips` | STRING | Five-digit county FIPS code. |
| `state_abbr` | STRING | Two-letter state code. |
| `year` | INTEGER |  |
| `crashes` | INTEGER |  |
| `fatalities` | INTEGER |  |
| `population` | FLOAT |  |
| `crashes_per_100k` | FLOAT | Fatal crashes per 100,000 residents. |
| `has_office` | BOOLEAN | True if the firm has an office in the county. |

### `clean.fars_state_month`

Monthly fatal-crash counts per state, split by the signals that drive each case type. This is the MARKET DEMAND signal. Built by sql/14_clean_fars_state_month.sql.

Rows: 576

| Column | Type | Meaning |
| --- | --- | --- |
| `state_abbr` | STRING | Two-letter state code. |
| `month` | DATE | First day of the month. |
| `crashes_all` | INTEGER |  |
| `crashes_truck` | INTEGER |  |
| `crashes_motorcycle` | INTEGER |  |
| `crashes_pedestrian` | INTEGER |  |
| `fatalities` | INTEGER |  |

### `clean.leads`

Every lead, with its month and callback-speed band. Built by sql/12_clean_leads.sql.

Rows: 200,347

| Column | Type | Meaning |
| --- | --- | --- |
| `lead_id` | STRING |  |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `lead_date` | DATE |  |
| `month` | DATE | First day of the month. |
| `case_type` | STRING | One of 8 standard case types. |
| `source` | STRING | Lead source: TV, Digital, Referral, Organic web, Billboard & radio. |
| `response_minutes` | FLOAT | Minutes from lead arrival to first callback. |
| `callback_band` | STRING | Callback speed group: within 5, 5-15, 15-60, over 60 minutes. |
| `is_signed` | BOOLEAN | True if the lead signed. |

### `clean.marketing_spend`

Marketing spend per office, month and channel. Built by sql/18_clean_marketing_spend.sql.

Rows: 6,912

| Column | Type | Meaning |
| --- | --- | --- |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `month` | DATE | First day of the month. |
| `channel` | STRING |  |
| `spend` | FLOAT |  |

### `clean.staff_month`

One row per employee per month worked, with workload and quits. Built by sql/17_clean_staff_month.sql.

Rows: 29,299

| Column | Type | Meaning |
| --- | --- | --- |
| `employee_id` | STRING |  |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `role` | STRING |  |
| `month` | DATE | First day of the month. |
| `load_ratio` | FLOAT | Workload / capacity. Above 1.3 = overloaded. |
| `is_overloaded` | BOOLEAN | True if load_ratio is above 1.3. |
| `overtime_hours` | FLOAT | Overtime hours that month. |
| `left_this_month` | BOOLEAN | True if the employee left that month. |

### `clean.weather_month`

Monthly weather per office, keyed by office_id and month date. Built by sql/16_clean_weather_month.sql.

Rows: 1,152

| Column | Type | Meaning |
| --- | --- | --- |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `month` | DATE | First day of the month. |
| `stations_used` | INTEGER |  |
| `snow_stations` | INTEGER | Nearby stations reporting snow that month. 0 = snow not measured (southern offices). |
| `precip_mm` | FLOAT |  |
| `snowfall_mm` | FLOAT |  |
| `snow_days` | FLOAT | Average days with snowfall at nearby stations that measure snow. |
| `rain_days` | FLOAT | Average days with 2.5 mm or more of rain. |
| `freeze_days` | FLOAT | Average days with a minimum below 0 C. |
| `avg_high_c` | FLOAT | Average daily high temperature, Celsius. |

## raw layer

Data exactly as loaded: public sources and the simulated firm systems.

### `raw.county_population`

County population and median income for every county in our six states, for every ACS 5-year release available. Built by sql/02_raw_county_population.sql.

Rows: 7,898

| Column | Type | Meaning |
| --- | --- | --- |
| `county_fips` | STRING | Five-digit county FIPS code. |
| `year` | INTEGER |  |
| `total_pop` | FLOAT |  |
| `median_income` | FLOAT |  |

### `raw.fars_crashes`

Every fatal crash in our six states, 2017-2024, from NHTSA FARS, with truck, motorcycle and pedestrian flags. Loaded by pipelines/pull_fars.py.

Rows: 91,348

| Column | Type | Meaning |
| --- | --- | --- |
| `crash_id` | INTEGER |  |
| `state_abbr` | STRING | Two-letter state code. |
| `county_fips` | STRING | Five-digit county FIPS code. |
| `year` | INTEGER |  |
| `month` | INTEGER | First day of the month. |
| `day` | INTEGER |  |
| `crash_date` | DATE |  |
| `day_week` | INTEGER |  |
| `hour` | INTEGER |  |
| `fatalities` | INTEGER |  |
| `pedestrians` | INTEGER |  |
| `has_large_truck` | BOOLEAN |  |
| `has_motorcycle` | BOOLEAN |  |
| `has_pedestrian` | BOOLEAN |  |

### `raw.sim_cases`

Every signed case with outcome, settlement, fee, costs and hours (simulated case management system).

Rows: 57,579

| Column | Type | Meaning |
| --- | --- | --- |
| `case_id` | STRING |  |
| `lead_id` | STRING |  |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `state_abbr` | STRING | Two-letter state code. |
| `case_type` | STRING | One of 8 standard case types. |
| `source` | STRING | Lead source: TV, Digital, Referral, Organic web, Billboard & radio. |
| `sign_date` | DATE |  |
| `went_to_suit` | BOOLEAN | True if a lawsuit was filed. |
| `status` | STRING |  |
| `close_date` | DATE |  |
| `settlement` | FLOAT | Gross settlement in US dollars. 0 = lost case. NULL = still open. |
| `fee_pct` | FLOAT | Fee percentage applied. |
| `fee` | FLOAT | Firm fee in US dollars. |
| `case_costs` | FLOAT |  |
| `hours_case_manager` | FLOAT |  |
| `hours_attorney` | FLOAT |  |
| `hours_paralegal` | FLOAT |  |

### `raw.sim_employee_months`

One row per employee per month worked, with workload, overtime and quits (simulated HR and timekeeping).

Rows: 29,299

| Column | Type | Meaning |
| --- | --- | --- |
| `employee_id` | STRING |  |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `role` | STRING |  |
| `month` | DATE | First day of the month. |
| `load_ratio` | FLOAT | Workload / capacity. Above 1.3 = overloaded. |
| `overtime_hours` | FLOAT | Overtime hours that month. |
| `left_this_month` | BOOLEAN | True if the employee left that month. |

### `raw.sim_employees`

Every employee with role, office, hire and termination dates (simulated HR system).

Rows: 949

| Column | Type | Meaning |
| --- | --- | --- |
| `employee_id` | STRING |  |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `role` | STRING |  |
| `hire_date` | DATE |  |
| `term_date` | DATE |  |

### `raw.sim_leads`

Every inbound lead with case type, source, callback time and outcome (simulated intake system).

Rows: 200,347

| Column | Type | Meaning |
| --- | --- | --- |
| `lead_id` | STRING |  |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `lead_date` | DATE |  |
| `case_type` | STRING | One of 8 standard case types. |
| `source` | STRING | Lead source: TV, Digital, Referral, Organic web, Billboard & radio. |
| `response_minutes` | FLOAT | Minutes from lead arrival to first callback. |
| `signed` | BOOLEAN |  |

### `raw.sim_marketing_spend`

Marketing spend by office, month and channel (simulated marketing ledger).

Rows: 6,912

| Column | Type | Meaning |
| --- | --- | --- |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `month` | DATE | First day of the month. |
| `channel` | STRING |  |
| `spend` | FLOAT |  |

### `raw.sim_offices`

The firm's 12 offices (simulated firm system). Loaded by pipelines/simulate_firm.py.

Rows: 12

| Column | Type | Meaning |
| --- | --- | --- |
| `office_id` | STRING | Three-letter office code (DET, MIA, ...). |
| `office` | STRING |  |
| `state_abbr` | STRING | Two-letter state code. |
| `county_fips` | STRING | Five-digit county FIPS code. |
| `market_size` | FLOAT |  |

### `raw.weather_monthly`

Monthly weather per office (2017-2024) from NOAA GHCN-Daily. Built by sql/01_raw_weather_monthly.sql.

Rows: 1,152

| Column | Type | Meaning |
| --- | --- | --- |
| `office` | STRING |  |
| `state_abbr` | STRING | Two-letter state code. |
| `county_fips` | STRING | Five-digit county FIPS code. |
| `year` | INTEGER |  |
| `month` | INTEGER | First day of the month. |
| `stations_used` | INTEGER |  |
| `snow_stations` | INTEGER | Nearby stations reporting snow that month. 0 = snow not measured (southern offices). |
| `precip_mm` | FLOAT |  |
| `snowfall_mm` | FLOAT |  |
| `snow_days` | FLOAT | Average days with snowfall at nearby stations that measure snow. |
| `rain_days` | FLOAT | Average days with 2.5 mm or more of rain. |
| `freeze_days` | FLOAT | Average days with a minimum below 0 C. |
| `avg_high_c` | FLOAT | Average daily high temperature, Celsius. |
