-- =====================================================================
-- 22_mart_case_economics.sql
-- Purpose : THE PROFIT TABLE. Contribution margin on every signed case.
--
--   contribution_margin = fee
--                       - firm_absorbed_costs   (case costs the firm eats)
--                       - staff_cost            (case manager, attorney, paralegal hours)
--                       - marketing_cost        (acquisition cost of the case)
--
-- How PI case costs really work (v2 fix):
--   The firm ADVANCES case costs (filing fees, records, experts). On a won
--   case they are reimbursed to the firm out of the client's settlement, so
--   they are not a firm expense. On a lost case the firm absorbs them.
--   Therefore firm_absorbed_costs = case_costs only when the case is lost.
--
-- Contribution margin, not net profit: it excludes intake staff, demand
-- writers, rent and admin overhead, which are not tied to a single case.
-- Use it to compare case types, sources and offices, not as firm profit.
--
-- Marketing cost per case = spend in the office-month the LEAD arrived /
-- cases signed from that month's leads. (v2.1 fix: marketing creates the lead,
-- so cost belongs to the lead month. Allocating by sign month left cases from
-- late-December leads that signed in January with no spend to draw on.)
-- Output : mart.case_economics  (one row per signed case)
-- Open cases have no outcome yet, so fee and margin are NULL.
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.mart.case_economics` AS
WITH spend AS (
  SELECT office_id, month, SUM(spend) AS spend
  FROM `pi-intake-forecast.clean.marketing_spend`
  GROUP BY office_id, month
),
cases AS (
  SELECT c.*, l.month AS lead_month
  FROM `pi-intake-forecast.clean.cases` c
  JOIN `pi-intake-forecast.clean.leads` l USING (lead_id)
),
signed AS (
  SELECT office_id, lead_month, COUNT(*) AS cases_signed
  FROM cases
  GROUP BY office_id, lead_month
),
base AS (
  SELECT
    c.*,
    o.office,
    c.status = 'Closed' AND c.settlement = 0                     AS is_lost,
    ROUND(SAFE_DIVIDE(sp.spend, sg.cases_signed), 2)              AS marketing_cost
  FROM cases c
  JOIN `pi-intake-forecast.clean.dim_office` o ON o.office_id = c.office_id
  LEFT JOIN spend sp  ON sp.office_id = c.office_id AND sp.month = c.lead_month
  LEFT JOIN signed sg ON sg.office_id = c.office_id AND sg.lead_month = c.lead_month
)
SELECT
  case_id,
  office_id,
  office,
  state_abbr,
  case_type,
  source,
  sign_date,
  sign_month,
  lead_month,
  EXTRACT(YEAR FROM sign_date)                     AS sign_year,
  status,
  went_to_suit,
  is_lost,
  close_date,
  EXTRACT(YEAR FROM close_date)                    AS close_year,
  days_to_close,
  ROUND(days_to_close / 30.4, 1)                   AS months_to_close,
  settlement,
  fee,
  case_costs                                       AS case_costs_advanced,
  IF(status = 'Closed', IF(is_lost, case_costs, 0), NULL) AS firm_absorbed_costs,
  staff_cost,
  marketing_cost,
  IF(status = 'Closed',
     ROUND(fee - IF(is_lost, case_costs, 0) - staff_cost - marketing_cost, 2),
     NULL)                                         AS contribution_margin
FROM base;