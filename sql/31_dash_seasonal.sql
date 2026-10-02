-- =====================================================================
-- 31_dash_seasonal.sql
-- Purpose : Seasonal calendar page. Seasonal index by state, case type and month.
-- Output  : mart.dash_seasonal (view)
-- Use     : Pivot table, rows = state (sort by state_order), columns = month_name
--           (sort by month_num), metric = seasonal_index, heatmap colouring.
--           Filter case_type = 'All case types' for the headline view.
-- =====================================================================
CREATE OR REPLACE VIEW `pi-intake-forecast.mart.dash_seasonal` AS
WITH states AS (SELECT * FROM UNNEST([
    STRUCT('ALL' AS state_abbr, 'All states' AS state, 0 AS state_order),
    ('MI', 'Michigan', 1), ('OH', 'Ohio', 2), ('PA', 'Pennsylvania', 3),
    ('GA', 'Georgia', 4), ('FL', 'Florida', 5), ('TX', 'Texas', 6)]))
SELECT
  st.state,
  st.state_order,
  si.case_type,
  si.month_num,
  si.month_name,
  ROUND(si.seasonal_index, 0)       AS seasonal_index,
  ROUND(si.seasonal_index - 100, 0) AS pct_vs_average_month,
  CASE WHEN NOT si.significant THEN 'Normal variation'
       WHEN si.seasonal_index > 100 THEN 'Real peak'
       ELSE 'Real trough' END       AS signal,
  si.avg_monthly_signed_cases
FROM `pi-intake-forecast.mart.seasonal_index` si
JOIN states st ON st.state_abbr = IF(si.state_abbr = 'Firm', 'ALL', si.state_abbr);
