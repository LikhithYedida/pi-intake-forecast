-- =====================================================================
-- 18_clean_marketing_spend.sql
-- Purpose : Marketing spend per office, month and channel.
-- Output  : clean.marketing_spend
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.clean.marketing_spend` AS
SELECT office_id, month, channel, spend
FROM `pi-intake-forecast.raw.sim_marketing_spend`;
