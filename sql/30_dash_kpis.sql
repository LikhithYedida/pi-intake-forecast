-- =====================================================================
-- 30_dash_kpis.sql
-- Purpose : Overview page scorecards. One row of headline numbers.
-- Output  : mart.dash_kpis (view)
-- Notes   : Forecast accuracy is the 2024 held-out check (see forecast_report.md).
--           Money figures are for cases CLOSED in 2024.
-- =====================================================================
CREATE OR REPLACE VIEW `pi-intake-forecast.mart.dash_kpis` AS
WITH fc AS (
  SELECT SUM(forecast) AS forecast_signed_2025
  FROM `pi-intake-forecast.mart.forecast_monthly`
  WHERE level = 'firm' AND kind = 'forecast'
),
check_2024 AS (
  SELECT SAFE_DIVIDE(SUM(ABS(actual - forecast)), SUM(actual)) AS model_error_2024,
         SAFE_DIVIDE(SUM(ABS(actual - naive)), SUM(actual))    AS baseline_error_2024
  FROM `pi-intake-forecast.mart.forecast_monthly`
  WHERE level = 'firm' AND kind = 'backtest' AND origin_year = 2024
),
intake AS (
  SELECT SUM(leads) AS leads_2024, SUM(signed_cases) AS signed_2024, SUM(marketing_spend) AS marketing_2024
  FROM `pi-intake-forecast.mart.office_month`
  WHERE year = 2024
),
callback AS (
  SELECT APPROX_QUANTILES(response_minutes, 2)[OFFSET(1)] AS median_callback_min_2024
  FROM `pi-intake-forecast.clean.leads`
  WHERE month BETWEEN '2024-01-01' AND '2024-12-01'
),
money AS (
  SELECT SUM(fee) AS fees_2024, SUM(contribution_margin) AS contribution_margin_2024
  FROM `pi-intake-forecast.mart.case_economics`
  WHERE status = 'Closed' AND close_year = 2024
)
SELECT
  ROUND(fc.forecast_signed_2025, 0)                                   AS forecast_signed_2025,
  intake.signed_2024,
  ROUND(SAFE_DIVIDE(fc.forecast_signed_2025, intake.signed_2024) - 1, 4) AS forecast_change_vs_2024,
  ROUND(check_2024.model_error_2024, 4)                               AS model_error_2024,
  ROUND(check_2024.baseline_error_2024, 4)                            AS baseline_error_2024,
  intake.leads_2024,
  ROUND(SAFE_DIVIDE(intake.signed_2024, intake.leads_2024), 4)        AS sign_rate_2024,
  ROUND(callback.median_callback_min_2024, 1)                         AS median_callback_min_2024,
  ROUND(intake.marketing_2024, 0)                                     AS marketing_2024,
  ROUND(SAFE_DIVIDE(intake.marketing_2024, intake.signed_2024), 0)    AS cost_per_signed_case_2024,
  ROUND(money.fees_2024, 0)                                           AS fees_2024,
  ROUND(money.contribution_margin_2024, 0)                            AS contribution_margin_2024,
  ROUND(SAFE_DIVIDE(money.contribution_margin_2024, money.fees_2024), 4) AS contribution_margin_rate_2024
FROM fc CROSS JOIN check_2024 CROSS JOIN intake CROSS JOIN callback CROSS JOIN money;
