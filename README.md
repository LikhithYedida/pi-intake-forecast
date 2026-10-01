# PI Case Intake Forecasting & Growth Analytics

**Forecasting when, where and what kind of personal injury cases arrive across a six-state law firm, and turning that forecast into staffing, marketing and profit decisions.**

## The business problem

Our firm runs 12 offices across Michigan, Ohio, Pennsylvania, Georgia, Florida and Texas. Today we plan staffing and marketing as if every month were the same. Case intake is strongly seasonal and differs by state:

- Michigan and Ohio auto cases rise with winter ice.
- Florida peaks with the winter tourist season.
- Motorcycle and pedestrian cases climb in summer.

The result: intake teams are stretched in peak months and idle in slow ones, ad budgets run flat, and office managers are judged on raw case counts that mostly reflect weather and traffic.

## Decisions this project supports

| Decision | What leadership gets |
| --- | --- |
| Staffing | Forecast signed cases per office per month, with a likely range |
| Marketing | The months and markets where each ad dollar signs the most cases |
| Revenue planning | Expected fee revenue over the next 24 months |
| Office performance | A market-share scorecard: did the market shrink, or did we lose ground? |
| Hiring & retention | Which roles we lose people from, in which months, and when to hire |

## Approach

```
Fee revenue = Market demand × Capture rate × Value per case
```

- **Market demand.** Injury-crash activity in our counties, from public NHTSA data. It is shaped by season, weather and population, so we forecast it rather than manage it.
- **Capture rate.** The share of that demand our firm signs. Marketing, intake speed and staffing move it.
- **Value per case.** Settlement × fee, timed by how long cases take to pay.

Separating demand from capture is what makes office performance fair to judge, and it is what turns the forecast into growth decisions.

## Data

- **Real, public:** NHTSA FARS crash data, NOAA weather (GHCN-Daily), U.S. Census ACS.
- **Simulated firm data:** leads, cases, payments, marketing spend, staffing and hours. These are generated on top of the real crash patterns using documented rates (see `reports/assumptions.md`).
- **Plant and recover:** the simulation plants known effects, and the models must recover them. This proves the method before it is trusted on real firm data.

## Stack

Python · BigQuery · SQL · statsmodels · LightGBM · Looker Studio

## Repo structure

```
data/raw/          public downloads (not committed)
data/simulated/    generated firm tables
pipelines/         data pulls, simulation, loading
sql/               BigQuery views: raw → clean → mart
notebooks/         seasonality, models, validation
reports/           scope, assumptions, director brief, model card
```

## Status

- [x] Environment, BigQuery and GitHub setup
- [x] Scope and assumptions
- [x] Public data pull (FARS crashes, NOAA weather, Census population)
- [ ] Firm simulation
- [ ] SQL layers
- [ ] Seasonality analysis and models
- [ ] Validation
- [ ] Looker Studio dashboard
- [ ] Director brief