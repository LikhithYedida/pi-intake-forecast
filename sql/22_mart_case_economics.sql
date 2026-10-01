-- =====================================================================
-- 22_mart_case_economics.sql
-- Purpose : THE PROFIT TABLE. Margin on every signed case:
--           margin = fee - case costs - staff cost - marketing cost
--           Marketing cost per case = that office-month's spend divided
--           by the cases it signed that month.
-- Output  : mart.case_economics  (one row per signed case)
-- Open cases have no fee yet, so their margin is NULL.
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.mart.case_economics` AS
WITH spend AS (
  SELECT office_id, month, SUM(spend) AS spend
  FROM `pi-intake-forecast.clean.marketing_spend`
  GROUP BY office_id, month
),
signed AS (
  SELECT office_id, sign_month, COUNT(*) AS cases_signed
  FROM `pi-intake-forecast.clean.cases`
  GROUP BY office_id, sign_month
)
SELECT
  c.case_id,
  c.office_id,
  o.office,
  c.state_abbr,
  c.case_type,
  c.source,
  c.sign_date,
  c.sign_month,
  EXTRACT(YEAR FROM c.sign_date)                 AS sign_year,
  c.status,
  c.went_to_suit,
  c.close_date,
  EXTRACT(YEAR FROM c.close_date)                AS close_year,
  c.days_to_close,
  ROUND(c.days_to_close / 30.4, 1)               AS months_to_close,
  c.settlement,
  c.fee,
  c.case_costs,
  c.staff_cost,
  ROUND(SAFE_DIVIDE(sp.spend, sg.cases_signed), 2) AS marketing_cost,
  ROUND(c.fee - c.case_costs - c.staff_cost - SAFE_DIVIDE(sp.spend, sg.cases_signed), 2) AS margin,
  c.settlement = 0                               AS is_lost
FROM `pi-intake-forecast.clean.cases` c
JOIN `pi-intake-forecast.clean.dim_office` o ON o.office_id = c.office_id
LEFT JOIN spend sp  ON sp.office_id = c.office_id AND sp.month = c.sign_month
LEFT JOIN signed sg ON sg.office_id = c.office_id AND sg.sign_month = c.sign_month;
