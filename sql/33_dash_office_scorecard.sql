-- =====================================================================
-- 33_dash_office_scorecard.sql
-- Purpose : Office scorecard page. One row per office per year, with the
--           counts needed to compute rates correctly in Looker Studio, plus
--           2024 leads against the forecast's expectation for that year.
-- Output  : mart.dash_office_scorecard (view)
-- Rates   : Build sign rate, cost per case and the within-5-minutes share as
--           Looker calculated fields from the SUMs (see dashboard guide). Never
--           average rates across offices or months.
-- =====================================================================
CREATE OR REPLACE VIEW `pi-intake-forecast.mart.dash_office_scorecard` AS
WITH states AS (SELECT * FROM UNNEST([
    STRUCT('ALL' AS state_abbr, 'All states' AS state, 0 AS state_order),
    ('MI', 'Michigan', 1), ('OH', 'Ohio', 2), ('PA', 'Pennsylvania', 3),
    ('GA', 'Georgia', 4), ('FL', 'Florida', 5), ('TX', 'Texas', 6)])),
yearly AS (
  SELECT office_id, office, state_abbr, year,
         SUM(leads)                                  AS leads,
         SUM(signed_cases)                           AS signed_cases,
         SUM(share_called_within_5min * leads)       AS leads_called_within_5min,
         SUM(marketing_spend)                        AS marketing_spend,
         SUM(staff_quits)                            AS staff_quits,
         AVG(median_callback_min)                    AS avg_monthly_median_callback_min,
         AVG(intake_load)                            AS avg_intake_load
  FROM `pi-intake-forecast.mart.office_month`
  GROUP BY office_id, office, state_abbr, year
),
expected AS (
  SELECT office_id, SUM(forecast) AS leads_expected_2024
  FROM `pi-intake-forecast.mart.forecast_monthly`
  WHERE level = 'office_leads' AND kind = 'backtest' AND origin_year = 2024
  GROUP BY office_id
)
SELECT
  y.office, y.office_id, st.state, y.year,
  y.leads, y.signed_cases, ROUND(y.leads_called_within_5min, 0) AS leads_called_within_5min,
  ROUND(y.marketing_spend, 0) AS marketing_spend, y.staff_quits,
  ROUND(y.avg_monthly_median_callback_min, 1) AS avg_monthly_median_callback_min,
  ROUND(y.avg_intake_load, 3) AS avg_intake_load,
  ROUND(SAFE_DIVIDE(y.signed_cases, y.leads), 4) AS sign_rate,
  ROUND(SAFE_DIVIDE(y.signed_cases, LAG(y.signed_cases) OVER (PARTITION BY y.office_id ORDER BY y.year)) - 1, 4)
                                              AS signed_change_vs_prior_year,
  IF(y.year = 2024, ROUND(e.leads_expected_2024, 0), NULL) AS leads_expected,
  IF(y.year = 2024, ROUND(SAFE_DIVIDE(y.leads, e.leads_expected_2024) - 1, 4), NULL) AS leads_vs_expected
FROM yearly y
JOIN states st USING (state_abbr)
LEFT JOIN expected e USING (office_id);
