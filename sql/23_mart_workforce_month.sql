-- =====================================================================
-- 23_mart_workforce_month.sql
-- Purpose : THE WORKFORCE TABLE. Headcount, workload, overtime and quits
--           per office, role and month. Feeds the turnover calendar and
--           the hiring plan.
-- Output  : mart.workforce_month
-- Grain   : office x role x month, Jan 2017 - Dec 2024
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.mart.workforce_month` AS
SELECT
  s.office_id,
  o.office,
  o.state_abbr,
  s.role,
  s.month,
  EXTRACT(YEAR FROM s.month)          AS year,
  EXTRACT(MONTH FROM s.month)         AS month_num,
  FORMAT_DATE('%b', s.month)          AS month_name,
  COUNT(*)                            AS headcount,
  ROUND(AVG(s.load_ratio), 3)         AS avg_load,
  ROUND(COUNTIF(s.is_overloaded) / COUNT(*), 4) AS share_overloaded,
  ROUND(AVG(s.overtime_hours), 1)     AS avg_overtime_hours,
  COUNTIF(s.left_this_month)          AS quits,
  ROUND(COUNTIF(s.left_this_month) / COUNT(*), 4) AS quit_rate
FROM `pi-intake-forecast.clean.staff_month` s
JOIN `pi-intake-forecast.clean.dim_office` o ON o.office_id = s.office_id
WHERE s.month BETWEEN '2017-01-01' AND '2024-12-01'
GROUP BY s.office_id, o.office, o.state_abbr, s.role, s.month;
