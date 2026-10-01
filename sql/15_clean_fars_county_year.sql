-- =====================================================================
-- 15_clean_fars_county_year.sql
-- Purpose : Yearly fatal crashes per county, joined to population.
--           Feeds the growth map: high-crash counties with no office.
-- Output  : clean.fars_county_year  (county x year)
-- =====================================================================
CREATE OR REPLACE TABLE `pi-intake-forecast.clean.fars_county_year` AS
WITH crashes AS (
  SELECT county_fips, state_abbr, year, COUNT(*) AS crashes, SUM(fatalities) AS fatalities
  FROM `pi-intake-forecast.raw.fars_crashes`
  GROUP BY county_fips, state_abbr, year
),
pop AS (  -- latest ACS release at or before each year
  SELECT c.county_fips, c.year,
         ARRAY_AGG(p.total_pop ORDER BY p.year DESC LIMIT 1)[SAFE_OFFSET(0)] AS population
  FROM crashes c
  LEFT JOIN `pi-intake-forecast.raw.county_population` p
    ON p.county_fips = c.county_fips AND p.year <= c.year
  GROUP BY c.county_fips, c.year
)
SELECT
  c.county_fips,
  c.state_abbr,
  c.year,
  c.crashes,
  c.fatalities,
  p.population,
  ROUND(SAFE_DIVIDE(c.crashes, p.population) * 100000, 2) AS crashes_per_100k,
  c.county_fips IN (SELECT county_fips FROM `pi-intake-forecast.clean.dim_office`) AS has_office
FROM crashes c
LEFT JOIN pop p USING (county_fips, year);
