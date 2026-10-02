-- =====================================================================
-- mart_checks.sql
-- Checks after building the clean and mart layers. Every check should
-- return the "Expect" result. pipelines/run_sql.py --checks runs them all.
-- =====================================================================

-- Check 1: forecasting table has every office x case type x month.
-- Expect: 9216 rows (12 x 8 x 96)
SELECT COUNT(*) AS rows_found, 9216 AS rows_expected
FROM `pi-intake-forecast.mart.office_casetype_month`;

-- Check 2: scorecard table has every office x month.
-- Expect: 1152 rows (12 x 96)
SELECT COUNT(*) AS rows_found, 1152 AS rows_expected
FROM `pi-intake-forecast.mart.office_month`;

-- Check 3: leads reconcile from raw to mart (2017-2024).
-- Expect: difference = 0
SELECT
  (SELECT COUNT(*) FROM `pi-intake-forecast.raw.sim_leads` WHERE lead_date BETWEEN '2017-01-01' AND '2024-12-31') AS raw_leads,
  (SELECT SUM(leads) FROM `pi-intake-forecast.mart.office_casetype_month`) AS mart_leads,
  (SELECT COUNT(*) FROM `pi-intake-forecast.raw.sim_leads` WHERE lead_date BETWEEN '2017-01-01' AND '2024-12-31')
    - (SELECT SUM(leads) FROM `pi-intake-forecast.mart.office_casetype_month`) AS difference;

-- Check 4: fees reconcile from raw to mart.
-- Expect: difference = 0
SELECT
  (SELECT ROUND(SUM(fee), 0) FROM `pi-intake-forecast.raw.sim_cases`) AS raw_fees,
  (SELECT ROUND(SUM(fee), 0) FROM `pi-intake-forecast.mart.case_economics`) AS mart_fees,
  (SELECT ROUND(SUM(fee), 0) FROM `pi-intake-forecast.raw.sim_cases`)
    - (SELECT ROUND(SUM(fee), 0) FROM `pi-intake-forecast.mart.case_economics`) AS difference;

-- Check 5: no gaps in demand or weather inputs.
-- Expect: 0 and 0
SELECT
  COUNTIF(state_fatal_crashes IS NULL) AS months_missing_crashes,
  COUNTIF(snow_days IS NULL)           AS months_missing_weather
FROM `pi-intake-forecast.mart.office_month`;

-- Check 6: every closed case has a contribution margin, and no open case has one.
-- Expect: 0 and 0
SELECT
  COUNTIF(status = 'Closed' AND contribution_margin IS NULL)   AS closed_without_margin,
  COUNTIF(status = 'Open' AND contribution_margin IS NOT NULL) AS open_with_margin
FROM `pi-intake-forecast.mart.case_economics`;

-- Check 7: won cases absorb no case costs (v2 fix: costs are reimbursed from settlements).
-- Expect: 0
SELECT COUNTIF(NOT is_lost AND firm_absorbed_costs > 0) AS won_cases_charged_costs
FROM `pi-intake-forecast.mart.case_economics`
WHERE status = 'Closed';

-- Check 8: margin components add up.
-- Expect: difference = 0
SELECT ROUND(SUM(ROUND(fee - firm_absorbed_costs - staff_cost - marketing_cost, 2))
             - SUM(contribution_margin), 2) AS difference
FROM `pi-intake-forecast.mart.case_economics`
WHERE status = 'Closed';

-- Check 9: dashboard forecast ties to the forecast table (firm, 2025).
-- Expect: difference = 0
SELECT ROUND((SELECT SUM(forecast_2025) FROM `pi-intake-forecast.mart.dash_forecast`
              WHERE state = 'All states' AND case_type = 'All case types')
           - (SELECT SUM(forecast) FROM `pi-intake-forecast.mart.forecast_monthly`
              WHERE level = 'firm' AND kind = 'forecast'), 0) AS difference;

-- Check 10: dashboard history ties to the warehouse (firm signed cases, 2017-2024).
-- Expect: difference = 0
SELECT (SELECT SUM(actual) FROM `pi-intake-forecast.mart.dash_forecast`
        WHERE state = 'All states' AND case_type = 'All case types')
     - (SELECT SUM(signed_cases) FROM `pi-intake-forecast.mart.office_month`) AS difference;

-- Check 11: dashboard profit ties to case economics (contribution margin, closed cases).
-- Expect: difference = 0
SELECT ROUND((SELECT SUM(contribution_margin) FROM `pi-intake-forecast.mart.dash_case_profit`)
           - (SELECT SUM(contribution_margin) FROM `pi-intake-forecast.mart.case_economics`
              WHERE status = 'Closed'), 0) AS difference;
