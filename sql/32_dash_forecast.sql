-- =====================================================================
-- 32_dash_forecast.sql
-- Purpose : Forecast page. One continuous timeline per level: monthly actuals
--           2017-2024, the 2024 held-out backtest, and the 2025 forecast with
--           its 80% range.
-- Output  : mart.dash_forecast (view)
-- Levels  : Firm  = state 'All states'  + case_type 'All case types'
--           State = one state           + case_type 'All case types'
--           Segment = one state         + one case type
--           (Each row belongs to exactly one level, so filters never double count.
--            Firm by case type is not a forecast level.)
-- Use     : Time series, dimension = month, metrics = actual, backtest_2024,
--           forecast_2025, range_low, range_high. Default filters: All states,
--           All case types.
-- =====================================================================
CREATE OR REPLACE VIEW `pi-intake-forecast.mart.dash_forecast` AS
WITH states AS (SELECT * FROM UNNEST([
    STRUCT('ALL' AS state_abbr, 'All states' AS state, 0 AS state_order),
    ('MI', 'Michigan', 1), ('OH', 'Ohio', 2), ('PA', 'Pennsylvania', 3),
    ('GA', 'Georgia', 4), ('FL', 'Florida', 5), ('TX', 'Texas', 6)])),
seg AS (
  SELECT state_abbr, case_type, month, SUM(signed_cases) AS y
  FROM `pi-intake-forecast.mart.office_casetype_month`
  GROUP BY state_abbr, case_type, month
),
history AS (
  SELECT 'Segment' AS level, state_abbr, case_type, month, y FROM seg
  UNION ALL
  SELECT 'State' AS level, state_abbr, 'All case types' AS case_type, month, SUM(y) AS y
  FROM seg GROUP BY state_abbr, month
  UNION ALL
  SELECT 'Firm' AS level, 'ALL' AS state_abbr, 'All case types' AS case_type, month, SUM(y) AS y
  FROM seg GROUP BY month
),
fc AS (
  SELECT
    CASE level WHEN 'firm' THEN 'Firm' WHEN 'state' THEN 'State' ELSE 'Segment' END AS level,
    COALESCE(state_abbr, 'ALL')            AS state_abbr,
    COALESCE(case_type, 'All case types')  AS case_type,
    month, kind, forecast, p10, p90
  FROM `pi-intake-forecast.mart.forecast_monthly`
  WHERE metric = 'signed_cases'
    AND (kind = 'forecast' OR origin_year = 2024)
),
rows_ AS (
  SELECT level, state_abbr, case_type, month,
         CAST(y AS FLOAT64) AS actual, CAST(NULL AS FLOAT64) AS backtest_2024,
         CAST(NULL AS FLOAT64) AS forecast_2025, CAST(NULL AS FLOAT64) AS range_low,
         CAST(NULL AS FLOAT64) AS range_high
  FROM history
  UNION ALL
  SELECT level, state_abbr, case_type, month,
         NULL, IF(kind = 'backtest', forecast, NULL), IF(kind = 'forecast', forecast, NULL),
         p10, p90
  FROM fc
)
SELECT r.level, st.state, st.state_order, r.case_type, r.month,
       r.actual, ROUND(r.backtest_2024, 1) AS backtest_2024, ROUND(r.forecast_2025, 1) AS forecast_2025,
       ROUND(r.range_low, 1) AS range_low, ROUND(r.range_high, 1) AS range_high
FROM rows_ r
JOIN states st USING (state_abbr);
