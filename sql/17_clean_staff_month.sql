-- =====================================================================
-- 17_clean_staff_month.sql
-- Purpose : One row per employee per month worked, with workload and quits.
-- Output  : clean.staff_month
-- Overload line 1.3x capacity matches planted effect S11.
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.clean.staff_month` AS
SELECT
  employee_id,
  office_id,
  role,
  month,
  load_ratio,
  load_ratio > 1.3 AS is_overloaded,
  overtime_hours,
  left_this_month
FROM `pi-intake-forecast.raw.sim_employee_months`;
