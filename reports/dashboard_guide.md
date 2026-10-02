# Looker Studio Dashboard: Build Guide and Specification

The dashboard reads only from the `mart.dash_*` views in BigQuery (built by `sql/3*.sql`). Every number on it ties back to the warehouse: `sql/checks/mart_checks.sql` checks 9-11 reconcile the dashboard views to their sources.

**Design rules**
1. **Every chart title states the finding**, not the topic: "Florida runs opposite to the firm", not "Seasonality by state".
2. **Rates are calculated fields, never averages.** A sign rate is `SUM(signed) / SUM(leads)` over whatever is filtered. Averaging office rates gives a 3-person office the same weight as a 6-person one, and the result is wrong.
3. **One question per page.** Filters sit in one row at the top of each page.
4. **Grey by default, one accent colour** on the thing the title talks about.

---

## 0. Set up (10 minutes)

1. Go to **lookerstudio.google.com** → **Blank report**.
2. When asked to add data, choose **BigQuery** → **My projects** → `pi-intake-forecast` → `mart` → `dash_kpis` → **Add**. Accept the prompt.
3. Add the other six views the same way: **Resource** menu → **Manage added data sources** → **Add a data source** → BigQuery → `mart` →
   `dash_seasonal`, `dash_forecast`, `dash_office_scorecard`, `dash_staffing_plan`, `dash_workforce`, `dash_case_profit`.
4. **Theme:** **Theme and layout** → **Simple** (light). Set the report font to a system sans (for example Roboto). Accent colour `#2a78d6`, grey `#b9b8b2`.
5. **Rename** the report: *PI Intake Forecast: Director Dashboard*. Add five pages (**Page** → **New page**) and name them as below.

### Calculated fields (add once per data source)

In each data source: **Resource** → **Manage added data sources** → **Edit** → **Add a field**.

| Data source | Field name | Formula | Format |
| --- | --- | --- | --- |
| dash_office_scorecard | Sign rate | `SUM(signed_cases) / SUM(leads)` | Percent |
| dash_office_scorecard | Called within 5 min | `SUM(leads_called_within_5min) / SUM(leads)` | Percent |
| dash_office_scorecard | Cost per signed case | `SUM(marketing_spend) / SUM(signed_cases)` | Currency (USD) |
| dash_workforce | Quit rate | `SUM(quits) / SUM(staff_months)` | Percent |
| dash_workforce | Overloaded share | `SUM(overloaded_staff_months) / SUM(staff_months)` | Percent |
| dash_case_profit | Average fee | `SUM(fees) / SUM(closed_cases)` | Currency (USD) |
| dash_case_profit | Contribution margin rate | `SUM(contribution_margin) / SUM(fees)` | Percent |
| dash_case_profit | Margin per case | `SUM(contribution_margin) / SUM(closed_cases)` | Currency (USD) |
| dash_case_profit | Win rate | `SUM(won_cases) / SUM(closed_cases)` | Percent |
| dash_case_profit | Avg months to close | `SUM(total_months_to_close) / SUM(closed_cases)` | Number, 1 decimal |

---

## Page 1. Overview: "Where we stand, and what 2025 looks like"

**Data:** `dash_kpis` (one row).

| Element | Setup |
| --- | --- |
| Title text | *2025: about [forecast_signed_2025] signed cases, [forecast_change_vs_2024] vs 2024*. Type the numbers once the scorecards show them |
| Scorecard row 1 | `forecast_signed_2025` (label "Signed cases forecast, 2025"), `forecast_change_vs_2024` (percent, "vs 2024"), `model_error_2024` (percent, "Forecast error, 2024 held-out"), `baseline_error_2024` (percent, "Same-month-last-year error") |
| Scorecard row 2 | `fees_2024` (currency, compact), `contribution_margin_rate_2024` (percent), `sign_rate_2024` (percent), `median_callback_min_2024` ("Median callback, minutes"), `cost_per_signed_case_2024` (currency) |
| Text box | Three findings, one line each, copied from `reports/seasonality_findings.md` and `reports/forecast_report.md`: Florida runs opposite to the firm; intake reaches capacity in August; the forecast beats same-month-last-year at all four levels on the held-out year |

Put the forecast-accuracy pair side by side: the director should see in one glance that the model beats the simple method.

---

## Page 2. Seasonal calendar: "Each state runs on its own calendar"

**Data:** `dash_seasonal`.

| Element | Setup |
| --- | --- |
| Filter | Drop-down on `case_type`, **default value "All case types"**, single select |
| Pivot table | Row dimension `state` (sort: `state_order` ascending, add `state_order` as a sort field). Column dimension `month_name` (sort by `month_num` ascending). Metric `seasonal_index` (aggregation: **Max**; each cell has one row) |
| Pivot styling | **Style** → Heatmap on the metric. Colours: low `#2a78d6` (blue), mid `#f0efec` (grey), high `#e34948` (red); set the mid value to **100** so 100 = neutral |
| Subtitle text | "100 = an average month. Red = busier, blue = quieter. Seasons from 2017-2024, COVID excluded." |
| Optional table | `state`, `month_name`, `pct_vs_average_month`, `signal`, filtered to `signal` ≠ "Normal variation": the list of statistically real peaks and troughs |

Title: **"Each state runs on its own calendar, and Florida runs opposite"**.

---

## Page 3. Forecast: "How many cases to expect in 2025"

**Data:** `dash_forecast`.

| Element | Setup |
| --- | --- |
| Filters | Drop-down `state` (default **All states**), drop-down `case_type` (default **All case types**), date range control (default 2022-01-01 to 2025-12-31) |
| Time series | Dimension `month`. Metrics: `actual` (grey `#898781`, solid), `backtest_2024` ("2024 forecast, held-out", blue dashed), `forecast_2025` (blue `#2a78d6`, solid, thicker), `range_low` and `range_high` (light blue `#b7d3f6`, thin dotted). **Style** → Missing data: *Line breaks* (not "zero"), so series only draw where they exist |
| Scorecards | `SUM(forecast_2025)` ("2025 forecast"), `SUM(actual)` with a date filter on 2024 ("2024 actual") |
| Note text | "Firm = All states + All case types. State = one state + All case types. Segment = one state + one case type. The 80% range should contain about 4 of every 5 months." |

Title: **"About [N] signed cases expected in 2025; the forecast beat same-month-last-year on the held-out year"**.

Why no "All states + one case type" view: that combination is not a forecast level, so the chart is empty by design rather than showing numbers the model never produced.

---

## Page 4. Office scorecard: "Which offices are ahead of or behind expectations"

**Data:** `dash_office_scorecard`, `dash_staffing_plan`.

| Element | Setup |
| --- | --- |
| Filter | Drop-down `year` (default **2024**), drop-down `state` |
| Table with bars | Dimension `office`, `state`. Metrics: `leads`, `leads_vs_expected` (percent; **Style** → bar or conditional colour: red below -5%, green above +5%), `signed_cases`, **Sign rate**, **Called within 5 min**, `avg_monthly_median_callback_min`, **Cost per signed case**. Sort by `leads_vs_expected` ascending, so offices furthest below expectation come first |
| Bar chart | Dimension `office`, metric **Sign rate**, sorted descending. Reference line at the firm average |
| Staffing table (`dash_staffing_plan`) | Pivot: rows `office`, columns `month_name` (sort by `month`), metric `specialists_needed` (Max), heatmap light-to-dark blue. Next to it a table: `office`, `specialists_dec_2024`, `MAX(specialists_needed)` |

Title: **"Offices judged against their own expected volume, not last month"**. `leads_vs_expected` compares 2024 actual leads with what the forecast expected for 2024, so seasonality and trend are already accounted for.

---

## Page 5. Workforce and profit: "Where we lose people, and where we make money"

**Data:** `dash_workforce`, `dash_case_profit`.

| Element | Setup |
| --- | --- |
| Filters | Drop-down `role` and `state` (workforce), `close_year` (profit, default 2024) |
| Workforce heatmap | Pivot: rows `role`, columns `month_name` (sort by `month_num`), metric **Quit rate**, heatmap white-to-red. Shows which roles lose people in which months |
| Workforce bars | Bar chart: dimension `role`, metrics **Quit rate** and **Overloaded share** as two separate charts side by side (never two axes on one chart) |
| Profit table | Dimension `case_type`. Metrics `closed_cases`, **Average fee**, **Win rate**, **Margin per case**, **Contribution margin rate**, **Avg months to close**. Sort by **Margin per case** descending |
| Profit bar | Dimension `source`, metric **Margin per case**, sorted descending: which lead sources bring the most valuable cases |
| Footnote | "Contribution margin = fee - firm-absorbed case costs - case staff cost - marketing cost. Before overhead (intake, rent, admin). Case costs are absorbed only on lost cases; won cases reimburse them from the settlement." |

Titles state the finding you see, for example: **"Case managers leave most in Q1, after bonuses"** and **"Truck and wrongful-death cases carry the highest margin per case"**. Check the data before typing a title.

---

## Share and publish

1. **Share** → **Manage access** → General access: **Anyone with the link can view**.
2. **File** → **Embed report** is not needed; copy the view link.
3. Add the link to the top of `README.md` ("Live dashboard: ...") and take one screenshot of each page into `reports/figures/dashboard_*.png` for the README.

## Checklist before showing anyone

- [ ] `python pipelines/run_sql.py --checks`: all 11 checks pass (9-11 tie the dashboard to the warehouse)
- [ ] Every title states a finding, and the finding matches the numbers on the page
- [ ] No chart averages a rate (all rates are calculated fields)
- [ ] Filters have sensible defaults (All states, All case types, 2024)
- [ ] Missing data draws as line breaks, not zeros
