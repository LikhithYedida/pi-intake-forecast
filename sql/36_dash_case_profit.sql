-- =====================================================================
-- 36_dash_case_profit.sql
-- Purpose : Profit page. Closed-case economics by state, case type, lead source
--           and close year. All components are sums, so any filter combination
--           adds up; build averages and rates as Looker calculated fields.
-- Output  : mart.dash_case_profit (view)
-- Margin  : contribution margin = fee - firm-absorbed costs - case staff cost
--           - marketing cost (before overhead; see mart.case_economics).
-- =====================================================================
CREATE OR REPLACE VIEW `pi-intake-forecast.mart.dash_case_profit` AS
WITH states AS (SELECT * FROM UNNEST([
    STRUCT('ALL' AS state_abbr, 'All states' AS state, 0 AS state_order),
    ('MI', 'Michigan', 1), ('OH', 'Ohio', 2), ('PA', 'Pennsylvania', 3),
    ('GA', 'Georgia', 4), ('FL', 'Florida', 5), ('TX', 'Texas', 6)]))
SELECT st.state, ce.case_type, ce.source, ce.close_year,
       COUNT(*)                              AS closed_cases,
       COUNTIF(NOT ce.is_lost)               AS won_cases,
       SUM(ce.settlement)          AS settlements,
       SUM(ce.fee)                 AS fees,
       SUM(ce.firm_absorbed_costs) AS firm_absorbed_costs,
       SUM(ce.staff_cost)          AS staff_cost,
       SUM(ce.marketing_cost)      AS marketing_cost,
       SUM(ce.contribution_margin) AS contribution_margin,
       SUM(ce.months_to_close)     AS total_months_to_close
FROM `pi-intake-forecast.mart.case_economics` ce
JOIN states st USING (state_abbr)
WHERE ce.status = 'Closed'
GROUP BY st.state, ce.case_type, ce.source, ce.close_year;
