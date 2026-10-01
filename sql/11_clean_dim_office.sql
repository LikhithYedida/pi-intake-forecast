-- =====================================================================
-- 11_clean_dim_office.sql
-- Purpose : The firm's 12 offices with state, home county and market size.
-- Output  : clean.dim_office
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.clean.dim_office` AS
SELECT
  office_id,
  office,
  state_abbr,
  LPAD(CAST(county_fips AS STRING), 5, '0') AS county_fips,
  market_size
FROM `pi-intake-forecast.raw.sim_offices`;
