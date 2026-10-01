-- =====================================================================
-- 16_clean_weather_month.sql
-- Purpose : Monthly weather per office, keyed by office_id and month date.
-- Output  : clean.weather_month  (office x month, 2017-2024)
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.clean.weather_month` AS
SELECT
  o.office_id,
  DATE(w.year, w.month, 1) AS month,
  w.stations_used,
  w.snow_stations,
  w.precip_mm,
  w.snowfall_mm,
  w.snow_days,
  w.rain_days,
  w.freeze_days,
  w.avg_high_c
FROM `pi-intake-forecast.raw.weather_monthly` w
JOIN `pi-intake-forecast.clean.dim_office` o ON o.office = w.office;
