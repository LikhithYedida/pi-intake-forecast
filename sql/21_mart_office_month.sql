-- =====================================================================
-- 21_mart_office_month.sql
-- Purpose : THE SCORECARD TABLE. One row per office per month with
--           demand, intake, conversion, marketing and staffing side by side.
--           Feeds the office scorecard, the capture-rate model and the
--           Looker Studio overview.
-- Output  : mart.office_month
-- Grain   : office x month, Jan 2017 - Dec 2024 (12 x 96 = 1,152 rows)
-- Capture rate here = signed cases per state fatal crash (a demand-relative
--   index; FARS is fatal-only, so compare it across time, not as a true share).
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.mart.office_month` AS
WITH leads AS (
  SELECT office_id, month,
         COUNT(*)                                       AS leads,
         COUNTIF(is_signed)                             AS signed_cases,
         APPROX_QUANTILES(response_minutes, 2)[OFFSET(1)] AS median_callback_min,
         COUNTIF(response_minutes <= 5) / COUNT(*)      AS share_called_within_5min
  FROM `pi-intake-forecast.clean.leads`
  GROUP BY office_id, month
),
spend AS (
  SELECT office_id, month, SUM(spend) AS marketing_spend
  FROM `pi-intake-forecast.clean.marketing_spend`
  GROUP BY office_id, month
),
staff AS (
  SELECT office_id, month,
         COUNTIF(role = 'Intake specialist')      AS intake_headcount,
         COUNTIF(role = 'Case manager')           AS case_manager_headcount,
         COUNTIF(role = 'Associate attorney')     AS attorney_headcount,
         COUNT(*)                                 AS total_headcount,
         AVG(IF(role = 'Intake specialist', load_ratio, NULL)) AS intake_load,
         AVG(IF(role = 'Case manager', load_ratio, NULL))      AS case_manager_load,
         COUNTIF(left_this_month)                 AS staff_quits
  FROM `pi-intake-forecast.clean.staff_month`
  GROUP BY office_id, month
)
SELECT
  o.office_id,
  o.office,
  o.state_abbr,
  m.month,
  m.year,
  m.month_num,
  m.month_name,
  m.is_covid,
  m.is_after_mi_reform,
  m.is_after_fl_reform,
  f.crashes_all                                   AS state_fatal_crashes,
  w.snow_days,
  w.rain_days,
  w.freeze_days,
  w.avg_high_c,
  l.leads,
  l.signed_cases,
  ROUND(SAFE_DIVIDE(l.signed_cases, l.leads), 4)  AS sign_rate,
  ROUND(SAFE_DIVIDE(l.signed_cases, f.crashes_all), 4) AS capture_index,
  ROUND(l.median_callback_min, 1)                 AS median_callback_min,
  ROUND(l.share_called_within_5min, 4)            AS share_called_within_5min,
  ROUND(s.marketing_spend, 2)                     AS marketing_spend,
  ROUND(SAFE_DIVIDE(s.marketing_spend, l.signed_cases), 2) AS cost_per_signed_case,
  st.intake_headcount,
  st.case_manager_headcount,
  st.attorney_headcount,
  st.total_headcount,
  ROUND(st.intake_load, 3)                        AS intake_load,
  ROUND(st.case_manager_load, 3)                  AS case_manager_load,
  st.staff_quits
FROM `pi-intake-forecast.clean.dim_office` o
CROSS JOIN `pi-intake-forecast.clean.dim_month` m
LEFT JOIN leads l  ON l.office_id = o.office_id AND l.month = m.month
LEFT JOIN spend s  ON s.office_id = o.office_id AND s.month = m.month
LEFT JOIN staff st ON st.office_id = o.office_id AND st.month = m.month
LEFT JOIN `pi-intake-forecast.clean.fars_state_month` f ON f.state_abbr = o.state_abbr AND f.month = m.month
LEFT JOIN `pi-intake-forecast.clean.weather_month` w ON w.office_id = o.office_id AND w.month = m.month
WHERE m.in_analysis_window;
