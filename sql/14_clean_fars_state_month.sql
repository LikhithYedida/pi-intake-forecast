-- =====================================================================
-- 14_clean_fars_state_month.sql
-- Purpose : Monthly fatal-crash counts per state, split by the signals
--           that drive each case type. This is the MARKET DEMAND signal.
-- Output  : clean.fars_state_month  (state x month, 2017-2024)
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.clean.fars_state_month` AS
SELECT
  state_abbr,
  DATE(year, month, 1)     AS month,
  COUNT(*)                 AS crashes_all,
  COUNTIF(has_large_truck) AS crashes_truck,
  COUNTIF(has_motorcycle)  AS crashes_motorcycle,
  COUNTIF(has_pedestrian)  AS crashes_pedestrian,
  SUM(fatalities)          AS fatalities
FROM `pi-intake-forecast.raw.fars_crashes`
GROUP BY 1, 2;  -- by position: "month" is both a raw column and the new date alias
