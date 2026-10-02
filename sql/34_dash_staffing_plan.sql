-- =====================================================================
-- 34_dash_staffing_plan.sql
-- Purpose : Intake staffing plan for 2025. Specialists needed per office per
--           month, staffed to the 80th percentile of forecast leads at 60 leads
--           per specialist (assumption S10), against December 2024 headcount.
-- Output  : mart.dash_staffing_plan (view)
-- =====================================================================
CREATE OR REPLACE VIEW `pi-intake-forecast.mart.dash_staffing_plan` AS
WITH states AS (SELECT * FROM UNNEST([
    STRUCT('ALL' AS state_abbr, 'All states' AS state, 0 AS state_order),
    ('MI', 'Michigan', 1), ('OH', 'Ohio', 2), ('PA', 'Pennsylvania', 3),
    ('GA', 'Georgia', 4), ('FL', 'Florida', 5), ('TX', 'Texas', 6)])),
plan AS (
  SELECT office_id, office, state_abbr, month,
         forecast AS leads_forecast, p80 AS leads_p80,
         CAST(CEIL(p80 / 60) AS INT64) AS specialists_needed
  FROM `pi-intake-forecast.mart.forecast_monthly`
  WHERE level = 'office_leads' AND kind = 'forecast'
),
current_staff AS (
  SELECT office_id, intake_headcount AS specialists_dec_2024
  FROM `pi-intake-forecast.mart.office_month`
  WHERE month = '2024-12-01'
)
SELECT p.office, st.state, p.month, FORMAT_DATE('%b', p.month) AS month_name,
       ROUND(p.leads_forecast, 0) AS leads_forecast, ROUND(p.leads_p80, 0) AS leads_p80,
       p.specialists_needed, c.specialists_dec_2024,
       p.specialists_needed - c.specialists_dec_2024 AS gap_vs_dec_2024
FROM plan p
JOIN states st USING (state_abbr)
LEFT JOIN current_staff c USING (office_id);
