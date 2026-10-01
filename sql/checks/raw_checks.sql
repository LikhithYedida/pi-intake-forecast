-- =====================================================================
-- raw_checks.sql
-- Sanity checks run after loading the raw layer. Each check lists what
-- a correct result looks like, so anyone can re-run and verify.
-- =====================================================================

-- Check 1: BigQuery's public FARS copy coverage.
-- Result on 2026-10-01: only accident_2015 and accident_2016,
-- so FARS 2017+ is downloaded from NHTSA by pipelines/pull_fars.py.
SELECT table_name
FROM `bigquery-public-data.nhtsa_traffic_fatalities.INFORMATION_SCHEMA.TABLES`
WHERE table_name LIKE 'accident_%'
ORDER BY table_name;

-- Check 2: FARS crashes by state and year.
-- Expect: 6 states x 2017-2024; TX and FL largest, MI and OH smallest.
SELECT state_abbr, year, COUNT(*) AS crashes
FROM `pi-intake-forecast.raw.fars_crashes`
GROUP BY state_abbr, year
ORDER BY state_abbr, year;

-- Check 3: Weather is believable.
-- Expect: Grand Rapids, Cleveland, Pittsburgh, Detroit snowiest; Miami warmest, no snow.
-- Result on 2026-10-01: Grand Rapids 80 mm/month, Cleveland 64, Pittsburgh 35, Detroit 33. Pass.
SELECT office,
       ROUND(AVG(snowfall_mm), 0) AS avg_monthly_snow_mm,
       ROUND(AVG(avg_high_c), 1)  AS avg_high_c
FROM `pi-intake-forecast.raw.weather_monthly`
GROUP BY office
ORDER BY avg_monthly_snow_mm DESC;

-- Check 4: Weather completeness.
-- Expect: 1,152 rows; no month without stations; no month missing rain or freeze data.
SELECT COUNT(*) AS office_months,
       COUNTIF(stations_used = 0)    AS months_without_stations,
       COUNTIF(precip_mm IS NULL)    AS months_missing_precip,
       COUNTIF(freeze_days IS NULL)  AS months_missing_freeze
FROM `pi-intake-forecast.raw.weather_monthly`;

-- Check 4b: Snow is measured where it matters (v2 fix).
-- Expect: every Michigan, Ohio and Pennsylvania office has snow-reporting
-- stations in Dec-Feb; southern offices may show 0 (no snow measured = none).
SELECT office, MIN(snow_stations) AS min_snow_stations_in_winter
FROM `pi-intake-forecast.raw.weather_monthly`
WHERE month IN (12, 1, 2)
GROUP BY office
ORDER BY min_snow_stations_in_winter;

-- Check 5: Population covers our 12 office counties.
-- Expect: 12 rows, one per office county, each with a recent total_pop.
SELECT county_fips, MAX(year) AS latest_year, ARRAY_AGG(total_pop ORDER BY year DESC LIMIT 1)[OFFSET(0)] AS latest_pop
FROM `pi-intake-forecast.raw.county_population`
WHERE county_fips IN ('26163','26081','39049','39035','42101','42003',
                      '13121','13051','12086','12057','48201','48113')
GROUP BY county_fips
ORDER BY county_fips;
