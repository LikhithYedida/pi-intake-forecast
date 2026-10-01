# Project Scope

**Version 1.0 · 24-hour build · Owner: Senior Data Analyst, reporting to the Director of Operations**

## Objective

Deliver a working monthly forecast of case intake by state, office and case type. Pair it with a market-share scorecard, a workforce view and a profit view, all published in Looker Studio with a one-page director brief.

## Firm footprint

| State | Office | Home county | County FIPS |
| --- | --- | --- | --- |
| Michigan | Detroit | Wayne | 26163 |
| Michigan | Grand Rapids | Kent | 26081 |
| Ohio | Columbus | Franklin | 39049 |
| Ohio | Cleveland | Cuyahoga | 39035 |
| Pennsylvania | Philadelphia | Philadelphia | 42101 |
| Pennsylvania | Pittsburgh | Allegheny | 42003 |
| Georgia | Atlanta | Fulton | 13121 |
| Georgia | Savannah | Chatham | 13051 |
| Florida | Miami | Miami-Dade | 12086 |
| Florida | Tampa | Hillsborough | 12057 |
| Texas | Houston | Harris | 48201 |
| Texas | Dallas | Dallas | 48113 |

## Case types

| Case type | Demand signal |
| --- | --- |
| Auto (motor vehicle accident) | FARS crashes, passenger vehicles |
| Commercial truck | FARS crashes involving large trucks |
| Motorcycle | FARS crashes involving motorcycles |
| Pedestrian & bicycle | FARS crashes involving pedestrians or cyclists |
| Premises liability (slip and fall) | Simulated; seasonality from weather (ice, rain) |
| Dog bite | Simulated; summer seasonal pattern |
| Workers' compensation | Simulated; steady with a mild summer rise |
| Wrongful death | FARS fatal crashes, all types |

## Time window

- **History:** January 2017 to the latest full year available in FARS.
- **Forecast horizon:** 12 months.
- **Flagged periods:** COVID (Mar 2020 – Jun 2021); Michigan no-fault reform (effective July 2020); Florida tort reform (March 2023).

## Leadership decisions supported

1. **Staffing:** how many intake specialists and case managers each office needs next quarter.
2. **Marketing:** where and when the next ad dollar goes.
3. **Revenue:** expected fee revenue and when it lands.
4. **Office performance:** which offices are truly under or over performing.
5. **Hiring & retention:** which roles lose people in which months, and when to hire.

## Deliverables

- **Looker Studio dashboard (5 pages):**
    1. Overview
    2. Seasonal calendar
    3. Forecast vs. actual
    4. Office scorecard
    5. Workforce & profit
- **One-page director brief.**
- **GitHub repo** with pipeline, SQL, notebooks, README and model card.

## Success criteria

- The forecast beats the "same month last year" baseline on backtest.
- About 80% of actual months fall inside the 80% forecast range.
- The models recover the effects planted in the simulation.
- Every dashboard number traces to a source table.

## Phase 2 (after the 24-hour build)

- State crash databases for all six states (injury crashes, not only fatal).
- dbt for the SQL layers, with automated tests.
- Hierarchical forecast reconciliation; a Cox survival model for turnover.
- Growth map and revenue outlook pages.