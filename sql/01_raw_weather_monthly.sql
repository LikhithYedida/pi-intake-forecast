-- =====================================================================
-- 01_raw_weather_monthly.sql
-- Purpose : Monthly weather per office (2017-2024) from NOAA GHCN-Daily.
-- Source  : bigquery-public-data.ghcn_d (public, no download needed)
-- Output  : pi-intake-forecast.raw.weather_monthly
-- Grain   : office x year x month (12 offices x 96 months = 1,152 rows)
-- Method  : All GHCN stations within 25 km of each office are averaged.
--           Only readings with no quality flag (qflag IS NULL) are used.
-- Units   : precip_mm, snowfall_mm in millimetres; avg_high_c in Celsius.
--           rain_days = days with >= 2.5 mm rain; freeze_days = days with min below 0 C.
-- Run in  : BigQuery console (about 10 GB scanned, within the free tier)
-- =====================================================================

CREATE OR REPLACE TABLE `pi-intake-forecast.raw.weather_monthly` AS
WITH offices AS (
  SELECT * FROM UNNEST([
    STRUCT('Detroit' AS office, 'MI' AS state_abbr, '26163' AS county_fips, 42.33 AS lat, -83.05 AS lon),
    ('Grand Rapids', 'MI', '26081', 42.96, -85.67),
    ('Columbus',     'OH', '39049', 39.96, -83.00),
    ('Cleveland',    'OH', '39035', 41.50, -81.69),
    ('Philadelphia', 'PA', '42101', 39.95, -75.17),
    ('Pittsburgh',   'PA', '42003', 40.44, -79.99),
    ('Atlanta',      'GA', '13121', 33.75, -84.39),
    ('Savannah',     'GA', '13051', 32.08, -81.09),
    ('Miami',        'FL', '12086', 25.76, -80.19),
    ('Tampa',        'FL', '12057', 27.95, -82.46),
    ('Houston',      'TX', '48201', 29.76, -95.37),
    ('Dallas',       'TX', '48113', 32.78, -96.80)
  ])
),
stations AS (
  SELECT o.office, o.state_abbr, o.county_fips, s.id
  FROM offices o
  JOIN `bigquery-public-data.ghcn_d.ghcnd_stations` s
    ON ST_DWITHIN(ST_GEOGPOINT(o.lon, o.lat), ST_GEOGPOINT(s.longitude, s.latitude), 25000)
),
daily AS (
  SELECT id, date, element, value
  FROM `bigquery-public-data.ghcn_d.ghcnd_20*`
  WHERE _TABLE_SUFFIX BETWEEN '17' AND '24'
    AND element IN ('PRCP', 'SNOW', 'TMIN', 'TMAX')
    AND qflag IS NULL
),
station_month AS (
  SELECT st.office, st.state_abbr, st.county_fips, d.id,
         EXTRACT(YEAR FROM d.date) AS year,
         EXTRACT(MONTH FROM d.date) AS month,
         SUM(IF(d.element = 'PRCP', d.value, 0)) / 10      AS precip_mm,
         SUM(IF(d.element = 'SNOW', d.value, 0))           AS snowfall_mm,
         COUNTIF(d.element = 'SNOW' AND d.value > 0)       AS snow_days,
         COUNTIF(d.element = 'PRCP' AND d.value >= 25)     AS rain_days,
         COUNTIF(d.element = 'TMIN' AND d.value < 0)       AS freeze_days,
         AVG(IF(d.element = 'TMAX', d.value / 10, NULL))   AS avg_high_c
  FROM daily d
  JOIN stations st ON d.id = st.id
  GROUP BY 1, 2, 3, 4, 5, 6
)
SELECT office, state_abbr, county_fips, year, month,
       COUNT(DISTINCT id)          AS stations_used,
       ROUND(AVG(precip_mm), 1)    AS precip_mm,
       ROUND(AVG(snowfall_mm), 1)  AS snowfall_mm,
       ROUND(AVG(snow_days), 1)    AS snow_days,
       ROUND(AVG(rain_days), 1)    AS rain_days,
       ROUND(AVG(freeze_days), 1)  AS freeze_days,
       ROUND(AVG(avg_high_c), 1)   AS avg_high_c
FROM station_month
GROUP BY 1, 2, 3, 4, 5
ORDER BY office, year, month;