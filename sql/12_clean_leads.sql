-- =====================================================================
-- 12_clean_leads.sql
-- Purpose : Every lead, with its month and callback-speed band.
-- Output  : clean.leads  (one row per lead)
-- Bands   : match planted effect S3 (5 / 15 / 60 minutes)
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.clean.leads` AS
SELECT
  lead_id,
  office_id,
  lead_date,
  DATE_TRUNC(lead_date, MONTH) AS month,
  case_type,
  source,
  response_minutes,
  CASE
    WHEN response_minutes <= 5  THEN '1. Within 5 min'
    WHEN response_minutes <= 15 THEN '2. 5-15 min'
    WHEN response_minutes <= 60 THEN '3. 15-60 min'
    ELSE '4. Over 60 min'
  END AS callback_band,
  signed AS is_signed
FROM `pi-intake-forecast.raw.sim_leads`;
