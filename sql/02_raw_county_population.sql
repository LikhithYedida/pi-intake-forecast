-- =====================================================================
-- 02_raw_county_population.sql
-- Purpose : County population and median income for every county in our
--           six states, for every ACS 5-year release available.
-- Source  : bigquery-public-data.census_bureau_acs (public, no download needed)
-- Output  : pi-intake-forecast.raw.county_population
-- Grain   : county x ACS release year
-- Why all counties, not just our 12: the growth map uses them to find
--           high-demand counties where we have no office yet.
-- State FIPS: 26 MI, 39 OH, 42 PA, 13 GA, 12 FL, 48 TX
-- =====================================================================

CREATE OR REPLACE TABLE `pi-intake-forecast.raw.county_population` AS
SELECT
  geo_id                                            AS county_fips,
  2000 + CAST(SUBSTR(_TABLE_SUFFIX, 1, 2) AS INT64) AS year,
  total_pop,
  median_income
FROM `bigquery-public-data.census_bureau_acs.county_20*`
WHERE _TABLE_SUFFIX LIKE '%_5yr'
  AND SUBSTR(geo_id, 1, 2) IN ('26', '39', '42', '13', '12', '48')
ORDER BY county_fips, year;