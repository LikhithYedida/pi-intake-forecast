-- =====================================================================
-- 20_mart_office_casetype_month.sql
-- Purpose : THE FORECASTING TABLE. Leads and signed cases per office,
--           case type and month, next to the demand signal and weather
--           that explain them. Months with zero leads are kept as zeros.
-- Output  : mart.office_casetype_month
-- Grain   : office x case type x month, Jan 2017 - Dec 2024
--           (12 offices x 8 case types x 96 months = 9,216 rows)
-- Demand signal per case type (state fatal crashes, NHTSA FARS):
--   Auto -> all crashes; Commercial truck -> truck crashes;
--   Motorcycle -> motorcycle crashes; Pedestrian & bicycle -> pedestrian crashes;
--   Wrongful death -> fatalities; other types have no crash signal (NULL).
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.mart.office_casetype_month` AS
WITH grid AS (
  SELECT o.office_id, o.office, o.state_abbr, ct.case_type, m.month
  FROM `pi-intake-forecast.clean.dim_office` o
  CROSS JOIN (SELECT DISTINCT case_type FROM `pi-intake-forecast.clean.leads`) ct
  CROSS JOIN `pi-intake-forecast.clean.dim_month` m
  WHERE m.in_analysis_window
),
lead_agg AS (
  SELECT office_id, case_type, month,
         COUNT(*)           AS leads,
         COUNTIF(is_signed) AS signed_cases
  FROM `pi-intake-forecast.clean.leads`
  GROUP BY office_id, case_type, month
)
SELECT
  g.office_id,
  g.office,
  g.state_abbr,
  g.case_type,
  g.month,
  dm.year,
  dm.month_num,
  dm.month_name,
  dm.is_covid,
  dm.is_after_mi_reform,
  dm.is_after_fl_reform,
  COALESCE(l.leads, 0)        AS leads,
  COALESCE(l.signed_cases, 0) AS signed_cases,
  ROUND(SAFE_DIVIDE(l.signed_cases, l.leads), 4) AS sign_rate,
  CASE g.case_type
    WHEN 'Auto'                 THEN f.crashes_all
    WHEN 'Commercial truck'     THEN f.crashes_truck
    WHEN 'Motorcycle'           THEN f.crashes_motorcycle
    WHEN 'Pedestrian & bicycle' THEN f.crashes_pedestrian
    WHEN 'Wrongful death'       THEN f.fatalities
  END AS state_crash_signal,
  w.snow_days,
  w.rain_days,
  w.freeze_days,
  w.avg_high_c
FROM grid g
JOIN `pi-intake-forecast.clean.dim_month` dm ON dm.month = g.month
LEFT JOIN lead_agg l
  ON l.office_id = g.office_id AND l.case_type = g.case_type AND l.month = g.month
LEFT JOIN `pi-intake-forecast.clean.fars_state_month` f
  ON f.state_abbr = g.state_abbr AND f.month = g.month
LEFT JOIN `pi-intake-forecast.clean.weather_month` w
  ON w.office_id = g.office_id AND w.month = g.month;
