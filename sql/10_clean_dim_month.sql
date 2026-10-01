-- =====================================================================
-- 10_clean_dim_month.sql
-- Purpose : Calendar of months with the flags every analysis needs.
-- Output  : clean.dim_month  (one row per month, Jan 2013 - Dec 2025)
-- Flags   : is_covid            Mar 2020 - Jun 2021 (abnormal traffic and intake)
--           is_after_mi_reform  from Jul 2020 (Michigan no-fault reform)
--           is_after_fl_reform  from Apr 2023 (first full month after Florida's 24 Mar 2023 tort reform)
--           in_analysis_window  Jan 2017 - Dec 2024 (years covered by public crash data)
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.clean.dim_month` AS
SELECT
  month,
  EXTRACT(YEAR FROM month)                     AS year,
  EXTRACT(MONTH FROM month)                    AS month_num,
  FORMAT_DATE('%b', month)                     AS month_name,
  EXTRACT(QUARTER FROM month)                  AS quarter,
  month BETWEEN '2020-03-01' AND '2021-06-01'  AS is_covid,
  month >= '2020-07-01'                        AS is_after_mi_reform,
  month >= '2023-04-01'                        AS is_after_fl_reform,
  month BETWEEN '2017-01-01' AND '2024-12-01'  AS in_analysis_window
FROM UNNEST(GENERATE_DATE_ARRAY('2013-01-01', '2025-12-01', INTERVAL 1 MONTH)) AS month;
