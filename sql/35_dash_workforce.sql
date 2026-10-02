-- =====================================================================
-- 35_dash_workforce.sql
-- Purpose : Workforce page. Staff-months, quits and overloaded staff-months by
--           office, role, year and calendar month. Compute quit rate and
--           overload share in Looker as SUM(quits) / SUM(staff_months).
-- Output  : mart.dash_workforce (view)
-- =====================================================================
CREATE OR REPLACE VIEW `pi-intake-forecast.mart.dash_workforce` AS
WITH states AS (SELECT * FROM UNNEST([
    STRUCT('ALL' AS state_abbr, 'All states' AS state, 0 AS state_order),
    ('MI', 'Michigan', 1), ('OH', 'Ohio', 2), ('PA', 'Pennsylvania', 3),
    ('GA', 'Georgia', 4), ('FL', 'Florida', 5), ('TX', 'Texas', 6)]))
SELECT w.office, st.state, w.role, w.year, w.month_num, w.month_name,
       w.headcount                                   AS staff_months,
       w.quits,
       ROUND(w.share_overloaded * w.headcount, 0)    AS overloaded_staff_months,
       ROUND(w.avg_overtime_hours * w.headcount, 0)  AS overtime_hours
FROM `pi-intake-forecast.mart.workforce_month` w
JOIN states st USING (state_abbr);
