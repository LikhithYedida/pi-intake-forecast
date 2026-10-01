-- =====================================================================
-- 13_clean_cases.sql
-- Purpose : Every signed case, with timing and the staff cost of working it.
-- Output  : clean.cases  (one row per signed case)
-- Staff cost uses loaded hourly rates (assumption S19):
--   case manager $45/h, attorney $150/h, paralegal $40/h
-- Open cases have no close_date, settlement or fee yet (snapshot 31 Dec 2025).
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.clean.cases` AS
SELECT
  case_id,
  lead_id,
  office_id,
  state_abbr,
  case_type,
  source,
  sign_date,
  DATE_TRUNC(sign_date, MONTH)          AS sign_month,
  went_to_suit,
  status,
  close_date,
  DATE_DIFF(close_date, sign_date, DAY) AS days_to_close,
  settlement,
  fee_pct,
  fee,
  case_costs,
  hours_case_manager,
  hours_attorney,
  hours_paralegal,
  ROUND(hours_case_manager * 45 + hours_attorney * 150 + hours_paralegal * 40, 2) AS staff_cost
FROM `pi-intake-forecast.raw.sim_cases`;
